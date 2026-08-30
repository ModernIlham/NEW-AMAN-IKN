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
import time
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable
import pymongo
from bson import ObjectId
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)

# Unique identifier per worker process — used to skip loopback events
WORKER_ID = os.environ.get("WORKER_ID") or f"worker-{uuid.uuid4().hex[:10]}"

COLLECTION_NAME = "ws_events"
CAPPED_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB ring buffer
CAPPED_MAX_DOCS = 20000                 # Max 20k events kept

# Jendela minimum antara dua `find()` bila kursor habis TANPA memberi apa pun.
#
# KENAPA ADA — ini memperbaiki cacat yang membakar satu core CPU selama
# berminggu-minggu. Kursor TAILABLE_AWAIT seharusnya MENAHAN hingga 2 detik
# menunggu dokumen baru; bila ia justru habis seketika, `while True` di bawah
# langsung menerbitkan `find()` berikutnya tanpa jeda sama sekali.
#
# Diagnosa 29 Agustus 2026 di produksi: **6.943.415 query dalam 17,1 jam**
# (112,5 per detik) berbanding hanya **59 getmore**. Kursor yang benar-benar
# menahan menghasilkan JUTAAN getmore; 59 berarti tiap putaran adalah `find()`
# baru, bukan kelanjutan kursor. Tiap `find()` itu memindai seluruh 20.000
# dokumen `ws_events` (koleksi ini hanya punya indeks `_id_`), dan pada 8 ms
# per pindaian itu ≈ 90% satu core — persis 93,1% yang terbaca.
#
# Diukur ulang di luar produksi dengan kursor tiruan yang habis seketika dan
# round-trip 8 ms: **121 find()/detik**, cocok dengan produksi dalam 8%.
#
# Jeda ini TIDAK menambah apa pun saat kursornya sehat: kursor yang menahan 2
# detik sudah melewati jendela ini, jadi sisanya nol.
JEDA_KURSOR_MATI = 0.1
# Berapa putaran kosong-dan-cepat beruntun sebelum keadaannya diumumkan. Cacat
# di atas berjalan berminggu-minggu tanpa satu pun baris log; diam bukan tanda
# sehat.
AMBANG_LAPOR_KURSOR_MATI = 100

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


async def _id_mulai(db) -> ObjectId:
    """`_id` dokumen TERBARU saat gelung mulai — titik awal tailing.

    Dipakai menggantikan `ts` sebagai penanda posisi. Alasannya bukan gaya:
    `ws_events` hanya punya indeks `_id_`, jadi filter `{"ts": {"$gt": ...}}`
    **memindai seluruh 20.000 dokumen** tiap kali kursor dibuat, sementara
    `{"_id": {"$gt": ...}}` adalah pencarian indeks. Diagnosa 30 Agustus 2026
    membaca `_id_` pada koleksi ini dipakai **0 kali** — indeksnya ada dan
    menganggur, sementara 145 MILIAR dokumen dipindai sia-sia.

    ObjectId monoton menurut waktu, jadi ia penanda posisi yang sah untuk
    koleksi capped (urutan sisip = urutan alami).
    """
    try:
        terakhir = await db[COLLECTION_NAME].find_one(sort=[("$natural", -1)])
        if terakhir and terakhir.get("_id") is not None:
            return terakhir["_id"]
    except Exception as e:  # noqa: BLE001
        logger.warning("[event_bus] Gagal membaca posisi awal (%s) — mulai dari waktu sekarang",
                       type(e).__name__)
    return ObjectId.from_datetime(datetime.now(timezone.utc))


async def _tail_loop(db, handler: Callable[[str, dict], Awaitable[None]]):
    """Long-running task: tail the capped collection and invoke handler for each event
    originating from OTHER workers. Robust to cursor timeouts and collection drops."""
    logger.info(f"[event_bus] Tail loop starting (worker_id={WORKER_ID})")
    # Mulai dari peristiwa TERBARU — yang lama dilewati.
    last_id = await _id_mulai(db)
    mati_beruntun = 0
    while True:
        try:
            query = {"_id": {"$gt": last_id}, "worker_id": {"$ne": WORKER_ID}}
            cursor = db[COLLECTION_NAME].find(
                query,
                cursor_type=pymongo.CursorType.TAILABLE_AWAIT,
                batch_size=20,
                # `max_await_time_ms` adalah METODE BERANTAI, bukan atribut.
                # Baris ini dulu berbunyi `cursor.max_await_time_ms = 2000`,
                # yang diam-diam MENIMPA metodenya dengan sebuah integer —
                # `maxAwaitTimeMS` tak pernah sampai ke server, dan kursornya
                # memakai bawaan. Python tak mengeluh saat sebuah metode
                # ditimpa nilai, jadi cacat ini tak berbunyi sama sekali.
            ).max_await_time_ms(2000)

            mulai = time.monotonic()
            kosong = True
            async for doc in cursor:
                kosong = False
                try:
                    last_id = doc.get("_id", last_id)
                    activity_id = doc.get("activity_id", "")
                    if not activity_id:
                        continue
                    # Strip bus metadata and forward payload to local handler
                    payload = {k: v for k, v in doc.items() if k not in {"_id", "activity_id", "ts", "worker_id"}}
                    await handler(activity_id, payload)
                except Exception as inner:
                    logger.warning(f"[event_bus] Handler error: {inner}")

            # Kursor habis. Bila ia habis TANPA memberi apa pun dan lebih cepat
            # daripada jendela tunggunya, awaitData tidak bekerja — dan tanpa
            # jeda di sini `while True` akan menerbitkan `find()` berikutnya
            # seketika, berulang ratusan kali per detik. Lihat JEDA_KURSOR_MATI.
            sisa = JEDA_KURSOR_MATI - (time.monotonic() - mulai)
            if kosong and sisa > 0:
                mati_beruntun += 1
                if mati_beruntun == AMBANG_LAPOR_KURSOR_MATI:
                    logger.warning(
                        "[event_bus] Kursor tailable habis seketika %d kali "
                        "beruntun — awaitData tampaknya tidak bekerja. Laju "
                        "find() ditahan ke %.0f/detik; fanout WS tetap jalan "
                        "dengan latensi hingga %.0f ms.",
                        mati_beruntun, 1 / JEDA_KURSOR_MATI,
                        JEDA_KURSOR_MATI * 1000)
                await asyncio.sleep(sisa)
            else:
                mati_beruntun = 0
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
