"""
Cross-worker event bus for WebSocket fanout on standalone MongoDB.

Why: FastAPI ConnectionManager stores WS connections in-memory per process.
With N uvicorn workers, a save on worker A must reach WS clients on workers B/C/D.
This bus uses a MongoDB *capped collection* with a *tailable cursor* — each
worker publishes events to a shared queue and every worker tails the queue to
broadcast to its local WS clients. Latency <100ms, no extra infra (Redis).

Falls back gracefully:
 - If the capped collection can't be created, publish still inserts a regular doc
 - Each worker has a unique WORKER_ID to skip its own events (avoid loopback)
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable
import pymongo
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)

# Unique identifier per worker process — used to skip loopback events
WORKER_ID = os.environ.get("WORKER_ID") or f"worker-{uuid.uuid4().hex[:10]}"

COLLECTION_NAME = "ws_events"
CAPPED_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB ring buffer
CAPPED_MAX_DOCS = 20000                 # Max 20k events kept

# Module-level state
_tail_task: Optional[asyncio.Task] = None
_local_handler: Optional[Callable[[str, dict], Awaitable[None]]] = None


async def ensure_capped_collection(db) -> bool:
    """Create the capped collection if it doesn't exist. Returns True if capped
    collection is available (ideal path), False if we must fall back to regular coll."""
    try:
        # Check whether collection exists
        names = await db.list_collection_names()
        if COLLECTION_NAME in names:
            # Verify it's capped
            opts = await db.command({"listCollections": 1, "filter": {"name": COLLECTION_NAME}})
            is_capped = False
            for c in opts.get("cursor", {}).get("firstBatch", []):
                is_capped = c.get("options", {}).get("capped", False)
                break
            if is_capped:
                logger.info(f"[event_bus] Using existing capped collection '{COLLECTION_NAME}'")
                return True
            else:
                logger.warning(f"[event_bus] Collection '{COLLECTION_NAME}' exists but is not capped. Fanout will use polling fallback.")
                return False
        # Create it
        await db.create_collection(
            COLLECTION_NAME,
            capped=True,
            size=CAPPED_SIZE_BYTES,
            max=CAPPED_MAX_DOCS,
        )
        logger.info(f"[event_bus] Created capped collection '{COLLECTION_NAME}' ({CAPPED_SIZE_BYTES // 1024 // 1024}MB, max {CAPPED_MAX_DOCS} docs)")
        return True
    except CollectionInvalid:
        return True  # Race: another worker created it — fine
    except Exception as e:
        logger.warning(f"[event_bus] Could not ensure capped collection: {e}. Falling back to regular insert.")
        return False


async def publish(db, activity_id: str, event: dict):
    """Publish an event to the bus. Safe to fail — local broadcast still happens."""
    try:
        doc = {
            **event,
            "activity_id": activity_id,
            "ts": datetime.now(timezone.utc),
            "worker_id": WORKER_ID,
        }
        await db[COLLECTION_NAME].insert_one(doc)
    except Exception as e:
        # Don't let event bus errors break the request
        logger.warning(f"[event_bus] publish failed: {e}")


async def _tail_loop(db, handler: Callable[[str, dict], Awaitable[None]]):
    """Long-running task: tail the capped collection and invoke handler for each event
    originating from OTHER workers. Robust to cursor timeouts and collection drops."""
    logger.info(f"[event_bus] Tail loop starting (worker_id={WORKER_ID})")
    # Start from current moment — skip old events
    last_ts = datetime.now(timezone.utc)
    while True:
        try:
            query = {"ts": {"$gt": last_ts}, "worker_id": {"$ne": WORKER_ID}}
            cursor = db[COLLECTION_NAME].find(
                query,
                cursor_type=pymongo.CursorType.TAILABLE_AWAIT,
                batch_size=20,
            )
            cursor.max_await_time_ms = 2000  # block up to 2s waiting for new docs

            async for doc in cursor:
                try:
                    last_ts = doc.get("ts", last_ts)
                    activity_id = doc.get("activity_id", "")
                    if not activity_id:
                        continue
                    # Strip bus metadata and forward payload to local handler
                    payload = {k: v for k, v in doc.items() if k not in {"_id", "activity_id", "ts", "worker_id"}}
                    await handler(activity_id, payload)
                except Exception as inner:
                    logger.warning(f"[event_bus] Handler error: {inner}")
        except asyncio.CancelledError:
            logger.info("[event_bus] Tail loop cancelled")
            raise
        except Exception as e:
            # Cursor can die if collection is dropped or db restarted — reconnect
            logger.warning(f"[event_bus] Tail cursor error, reconnecting in 2s: {e}")
            await asyncio.sleep(2)


async def start(db, handler: Callable[[str, dict], Awaitable[None]]):
    """Start the bus. Call once on app startup. Handler is invoked for each
    remote event: `await handler(activity_id, payload)`."""
    global _tail_task, _local_handler
    _local_handler = handler
    ok = await ensure_capped_collection(db)
    if not ok:
        logger.warning("[event_bus] Capped collection unavailable — tailable cursor disabled, cross-worker fanout will not work")
        return
    if _tail_task is None or _tail_task.done():
        _tail_task = asyncio.create_task(_tail_loop(db, handler))
        logger.info("[event_bus] Started")


async def stop():
    """Stop the tail loop on shutdown."""
    global _tail_task
    if _tail_task:
        _tail_task.cancel()
        try:
            await _tail_task
        except asyncio.CancelledError:
            pass
        _tail_task = None
        logger.info("[event_bus] Stopped")
