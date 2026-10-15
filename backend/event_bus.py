"""
Cross-worker event bus for WebSocket fanout on standalone MongoDB.

Why: FastAPI ConnectionManager stores WS connections in-memory per process.
With N uvicorn workers, a save on worker A must reach WS clients on workers B/C/D.
This bus uses a MongoDB *capped collection* with a *tailable cursor* — each
worker publishes events to a shared queue and every worker tails the queue to
broadcast to its local WS clients. Latency <100ms, no extra infra (Redis).

If capped storage is unavailable, bounded periodic invalidation reconciles local
clients; no uncapped event history is accumulated. Worker IDs skip loopback.
"""
import os
import uuid
import logging
import asyncio
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable
import pymongo
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)

# Unique identifier per worker process — used to skip loopback events
WORKER_ID = os.environ.get("WORKER_ID") or f"worker-{uuid.uuid4().hex[:10]}"

COLLECTION_NAME = "ws_events"
CAPPED_SIZE_BYTES = 1 * 1024 * 1024    # 1 MB ring buffer
CAPPED_MAX_DOCS = 1000                  # Maks 1.000 peristiwa disimpan

# KENAPA DIKECILKAN dari 10 MB / 20.000 dokumen.
#
# Dokumentasi MongoDB menyebutnya terang: **kursor tailable TIDAK memakai
# indeks**, jadi tiap kali kursor dibuat ulang ia memindai koleksi dari awal.
# Bacaan produksi 30 Agustus 2026 mengukurnya: **19.291 dokumen dipindai per
# pindaian** — praktis seluruh cincin — dan pindaian itu terjadi ~10 kali per
# detik karena kursornya mati seketika (lihat JEDA_KURSOR_MATI).
#
# Biaya pindaian sebanding lurus dengan ISI cincin, jadi mengecilkannya 20×
# memurahkan tiap putaran 20× — tanpa menyentuh latensi fanout sama sekali.
#
# Kenapa 1.000 cukup: cincin ini hanya penyangga antar-worker, dan peristiwa
# dikonsumsi dalam ~100 ms. Laju sisip terukur **485 dalam 22 jam** (0,006 per
# detik). Seribu slot adalah cadangan berjam-jam, bukan menit.

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
_publish_gap_pending = False
_next_gap_retry = 0.0
_bus_available = True
RESYNC_INTERVAL_DETIK = 60.0
HANDLER_TIMEOUT_DETIK = 15.0
CURSOR_CLOSE_TIMEOUT_DETIK = 5.0
# At most two capped-ring generations; event IDs are equality tokens only.
DEDUP_MAX = 2 * CAPPED_MAX_DOCS


async def _kecilkan_bila_kebesaran(db, opts: dict) -> None:
    """Kecilkan cincin yang dibuat versi lama (10 MB / 20.000) ke ukuran kini.

    HANYA MENGECILKAN, tak pernah membesarkan: `collMod` yang membesar tak
    memberi manfaat apa pun di sini dan hanya menambah biaya pindaian. Bila
    servernya tak mendukung `collMod` untuk koleksi capped (< MongoDB 6.0),
    kegagalannya dicatat lalu diabaikan — cincin lama tetap bekerja, cuma
    lebih mahal.

    Peristiwa lama yang terpangkas TIDAK berarti: ia penyangga fanout WS yang
    isinya sudah dikonsumsi dalam hitungan milidetik, bukan catatan.
    """
    o = {}
    for c in (opts.get("cursor", {}).get("firstBatch") or []):
        o = c.get("options", {}) or {}
        break
    maks = o.get("max")
    besar = o.get("size")
    if not ((isinstance(maks, int) and maks > CAPPED_MAX_DOCS)
            or (isinstance(besar, int) and besar > CAPPED_SIZE_BYTES)):
        return
    try:
        await db.command({
            "collMod": COLLECTION_NAME,
            "cappedSize": CAPPED_SIZE_BYTES,
            "cappedMax": CAPPED_MAX_DOCS,
        })
        logger.info(
            "[event_bus] Cincin '%s' dikecilkan dari (%s dok / %s bita) ke "
            "(%d dok / %d bita) — tiap pindaian kursor tailable jadi lebih murah",
            COLLECTION_NAME, maks, besar, CAPPED_MAX_DOCS, CAPPED_SIZE_BYTES)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "[event_bus] Gagal mengecilkan cincin '%s' (%s) — tetap jalan "
            "dengan ukuran lama", COLLECTION_NAME, type(e).__name__)


async def ensure_capped_collection(db) -> bool:
    """Create the capped collection if it doesn't exist. Returns True if capped
    collection is available, False for periodic reconciliation fallback."""
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
                await _kecilkan_bila_kebesaran(db, opts)
                logger.info(f"[event_bus] Using existing capped collection '{COLLECTION_NAME}'")
                return True
            else:
                logger.warning(f"[event_bus] Collection '{COLLECTION_NAME}' is not capped; periodic reconciliation required")
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
        logger.warning("[event_bus] Could not ensure capped collection (%s); periodic reconciliation required", type(e).__name__)
        return False


def _resync_payload(reason):
    return {"type": "resync_required", "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()}


async def _deliver(handler, activity_id, payload):
    # Python 3.11 wait_for can consume external cancellation if its child
    # finishes in the same loop turn. Deliver directly in this task so shutdown
    # cannot leave a cancelling tail alive forever after a completed handler.
    async with asyncio.timeout(HANDLER_TIMEOUT_DETIK):
        await handler(activity_id, payload)


async def _flush_publish_gap(db):
    """Recovery marker after a failed publish; no credentials or asset payload."""
    global _publish_gap_pending, _next_gap_retry
    if not _publish_gap_pending or not _bus_available or time.monotonic() < _next_gap_retry:
        return
    _next_gap_retry = time.monotonic() + 2.0
    try:
        await db[COLLECTION_NAME].insert_one({
            **_resync_payload("publish_failed"), "activity_id": "*",
            "ts": datetime.now(timezone.utc), "worker_id": WORKER_ID,
            "_bus_event_id": uuid.uuid4().hex,
        })
        _publish_gap_pending = False
        _next_gap_retry = 0.0
    except Exception:
        pass  # retry on the next tail/publish iteration


async def publish(db, activity_id: str, event: dict):
    """Publish best effort; loss triggers explicit reconciliation, not silence."""
    global _publish_gap_pending
    try:
        if not _bus_available:
            raise RuntimeError("Capped event storage is unavailable")
        await db[COLLECTION_NAME].insert_one({
            **event, "activity_id": activity_id,
            "ts": datetime.now(timezone.utc), "worker_id": WORKER_ID,
            "_bus_event_id": uuid.uuid4().hex,
        })
    except Exception as e:
        _publish_gap_pending = True
        logger.warning("[event_bus] publish failed (%s); reconciliation required", type(e).__name__)
        if _local_handler:
            try:
                await _deliver(_local_handler, "*", _resync_payload("publish_failed"))
            except Exception:
                pass
        return False
    await _flush_publish_gap(db)
    return True


async def _id_mulai(db):
    """Latest NATURAL insertion token; equality only, never ObjectId ordering."""
    last = await db[COLLECTION_NAME].find_one(sort=[("$natural", -1)])
    return last.get("_id") if last else None


def _event_key(doc):
    value = doc.get("_bus_event_id")
    if value:
        return "event:" + str(value)
    value = doc.get("_id")
    return type(value).__name__ + ":" + str(value)


class RingReplay:
    """Bounded equality dedup and natural-order continuity across cursor restarts."""
    def __init__(self, anchor=None):
        self.seen = OrderedDict()
        self.last_key = (type(anchor).__name__ + ":" + str(anchor)) if anchor is not None else None
        self.bootstrap = anchor is not None
        self.waiting = self.last_key
        self.cursor_last = None

    def begin_cursor(self):
        self.waiting = self.last_key
        self.cursor_last = None

    def _remember(self, key):
        self.seen[key] = None
        self.seen.move_to_end(key)
        while len(self.seen) > DEDUP_MAX:
            self.seen.popitem(last=False)

    def accept(self, doc):
        # Continuity anchors always use Mongo _id, including new envelopes that
        # also carry a UUID event ID for duplicate publication/replay detection.
        token = type(doc.get("_id")).__name__ + ":" + str(doc.get("_id"))
        key = _event_key(doc)
        self.cursor_last = token
        gap = False
        if self.waiting is not None:
            if token == self.waiting:
                self.waiting = None
                self.bootstrap = False
                self._remember(key)
                return False, False
            if self.bootstrap:
                self._remember(key)
                return False, False
            if key not in self.seen:
                # A new insertion precedes our missing anchor in natural order:
                # rollover/drop occurred. Forward new events and require resync.
                self.waiting = None
                gap = True
        if key in self.seen:
            return False, gap
        self._remember(key)
        self.last_key = token
        return True, gap

    def end_batch(self):
        if self.waiting is None:
            return False
        # Initial anchor rolled out before the first scan, or an entire missing
        # cursor position disappeared. The authoritative read must reconcile.
        self.waiting = None
        self.bootstrap = False
        self.last_key = self.cursor_last
        return True


async def _tail_loop(db, handler: Callable[[str, dict], Awaitable[None]]):
    """Natural-order capped tail with bounded replay, dedup and explicit gaps.

    Keep an ALIVE cursor across empty batches: a new query every empty batch
    throws away getMore/awaitData and repeatedly scans the ring. Dead cursors
    retain the 100ms throttle, including when a restart sees only duplicates.
    """
    logger.info("[event_bus] Tail loop starting (worker_id=%s)", WORKER_ID)
    replay = None
    reconnect = False
    last_resync = time.monotonic()
    mati_beruntun = 0
    while True:
        cursor = None
        mulai = time.monotonic()
        try:
            if replay is None:
                replay = RingReplay(await _id_mulai(db))
            replay.begin_cursor()
            cursor = db[COLLECTION_NAME].find(
                {}, cursor_type=pymongo.CursorType.TAILABLE_AWAIT,
                batch_size=20).max_await_time_ms(2000)
            iterator = cursor.__aiter__()
            while True:
                await _flush_publish_gap(db)
                if time.monotonic() - last_resync >= RESYNC_INTERVAL_DETIK:
                    await _deliver(handler, "*", _resync_payload("periodic_reconcile"))
                    last_resync = time.monotonic()
                read_started = time.monotonic()
                try:
                    doc = await iterator.__anext__()
                except StopAsyncIteration:
                    gap = replay.end_batch()
                    if reconnect or gap:
                        await _deliver(handler, "*", _resync_payload("cursor_reconnected" if reconnect else "ring_gap"))
                        reconnect = False
                        last_resync = time.monotonic()
                    if time.monotonic() - last_resync >= RESYNC_INTERVAL_DETIK:
                        await _deliver(handler, "*", _resync_payload("periodic_reconcile"))
                        last_resync = time.monotonic()
                    if not getattr(cursor, "alive", False):
                        break
                    # A conforming getMore waits2s. An alive-but-empty cursor
                    # returning immediately must also respect the idle bound.
                    idle_delay = JEDA_KURSOR_MATI - (time.monotonic() - read_started)
                    await asyncio.sleep(max(0, idle_delay))
                    continue
                accepted, gap = replay.accept(doc)
                if reconnect or gap:
                    await _deliver(handler, "*", _resync_payload("cursor_reconnected" if reconnect else "ring_gap"))
                    reconnect = False
                    last_resync = time.monotonic()
                if not accepted or doc.get("worker_id") == WORKER_ID:
                    continue
                activity_id = doc.get("activity_id") or ""
                if not activity_id:
                    continue
                payload = {k: v for k, v in doc.items()
                           if k not in {"_id", "activity_id", "ts", "worker_id", "_bus_event_id"}}
                try:
                    await _deliver(handler, activity_id, payload)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await _deliver(handler, activity_id, _resync_payload("handler_failed"))
                if time.monotonic() - last_resync >= RESYNC_INTERVAL_DETIK:
                    await _deliver(handler, "*", _resync_payload("periodic_reconcile"))
                    last_resync = time.monotonic()
            sisa = JEDA_KURSOR_MATI - (time.monotonic() - mulai)
            if sisa > 0:
                mati_beruntun += 1
                if mati_beruntun == AMBANG_LAPOR_KURSOR_MATI:
                    logger.warning("[event_bus] Kursor mati berulang; awaitData tidak bekerja, find dibatasi %.0f/detik", 1 / JEDA_KURSOR_MATI)
                await asyncio.sleep(sisa)
            else:
                mati_beruntun = 0
        except asyncio.CancelledError:
            raise
        except Exception as e:
            reconnect = True
            logger.warning("[event_bus] Tail reconnect (%s)", type(e).__name__)
            await asyncio.sleep(2)
        finally:
            if cursor is not None and hasattr(cursor, "close"):
                try:
                    async with asyncio.timeout(CURSOR_CLOSE_TIMEOUT_DETIK):
                        await cursor.close()
                except Exception:
                    logger.warning("[event_bus] Cursor cleanup failed or exceeded its shutdown deadline")


async def _reconcile_loop(handler):
    """Safe fallback, without an unbounded non-capped event collection."""
    while True:
        try:
            await _deliver(handler, "*", _resync_payload("event_bus_unavailable"))
        except Exception:
            logger.warning("[event_bus] Periodic reconciliation failed")
        await asyncio.sleep(RESYNC_INTERVAL_DETIK)


async def start(db, handler: Callable[[str, dict], Awaitable[None]]):
    """Start the bus. Call once on app startup. Handler is invoked for each
    remote event: `await handler(activity_id, payload)`."""
    global _tail_task, _local_handler, _bus_available
    _local_handler = handler
    # Rollback switch retains the safe reconciliation contract; never restore
    # the invalid global ObjectId-order assumption to disable a new algorithm.
    mode = os.environ.get("AMAN_EVENT_BUS_MODE", "natural").strip().lower()
    if mode not in {"natural", "reconcile"}:
        logger.warning("[event_bus] Unknown transport mode; using reconciliation")
    ok = await ensure_capped_collection(db) if mode == "natural" else False
    _bus_available = ok
    if not ok:
        logger.warning("[event_bus] Capped collection unavailable — periodic reconciliation enabled")
        if _tail_task is None or _tail_task.done():
            _tail_task = asyncio.create_task(_reconcile_loop(handler))
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
