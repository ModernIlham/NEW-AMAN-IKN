"""Integrasi Redis — cache LINTAS-WORKER OPSIONAL & ber-feature-flag.

MENGAPA
-------
VPS menjalankan 2 worker uvicorn. Cache ringkasan (stats/filter-options/
analytics/kategori) selama ini `TTLCache` PER-WORKER, sehingga:
  1. `invalidate_asset_cache()` hanya mengosongkan cache worker yang menangani
     tulis — worker lain menyajikan data BASI sampai TTL habis (60–300 dtk).
  2. Hit-rate rendah (tiap worker meng-cache sendiri).
Redis menjadikan cache BERSAMA: satu sumber, invalidasi seketika lintas worker,
beban Mongo turun.

FEATURE FLAG (tidak ada yang rusak bila mati)
--------------------------------------------
Aktif HANYA bila `REDIS_URL` di-set di `backend/.env`. Bila kosong → seluruh
fungsi cache jatuh-balik ke `TTLCache` per-worker lama (lihat shared_utils).
Bila Redis mati/menolak → operasi cache di-swallow (miss → hitung ulang dari
Mongo); aplikasi tetap jalan. Rollback = hapus `REDIS_URL` lalu restart.

INVALIDASI TANPA SCAN (generation counter)
------------------------------------------
Tiap namespace punya penghitung generasi `aman:gen:<ns>` (INCR saat invalidasi).
Kunci nilai menyertakan generasi: `aman:cache:<ns>:<gen>:<key>`. Invalidasi =
`INCR gen` (O(1), atomik, seketika lintas worker) — kunci generasi lama menjadi
yatim & kedaluwarsa via TTL. Tak perlu memindai/menghapus banyak kunci.

KEAMANAN
--------
Redis bind ke 127.0.0.1 (localhost VPS) + password (requirepass) di `REDIS_URL`.
Kunci cache menyertakan kode_satker pada key-nya (dibangun pemanggil) sehingga
isolasi satker tetap terjaga — sama seperti cache in-memory sebelumnya.
"""
import os
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# ── Feature flag (dibaca sekali saat import) ────────────────────────────────
REDIS_URL = (os.environ.get("REDIS_URL") or "").strip()

_PREFIX = "aman:cache:"
_GENP = "aman:gen:"


def redis_aktif() -> bool:
    """True bila Redis dikonfigurasi (REDIS_URL ter-set)."""
    return bool(REDIS_URL)


# ── Klien async (singleton malas; redis-py di-import hanya bila dipakai) ─────
_client = None


def _get_client():
    global _client
    if _client is None:
        # Import di-tunda: bila paket redis tak terpasang & REDIS_URL kosong,
        # modul tetap bisa di-import (fitur cukup nonaktif).
        import redis.asyncio as aioredis
        _client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _client


async def tutup_client() -> None:
    """Tutup klien Redis saat shutdown aplikasi (dipanggil server.py)."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None


# ── Operasi cache (semua best-effort; error → miss/no-op) ────────────────────
async def redis_get(ns: str, key: str):
    """Ambil nilai cache ter-deserialisasi, atau None bila miss/nonaktif/gagal."""
    if not redis_aktif():
        return None
    try:
        c = _get_client()
        gen = await c.get(_GENP + ns) or "0"
        raw = await c.get(f"{_PREFIX}{ns}:{gen}:{key}")
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        logger.warning("Redis get %s gagal (fallback hitung ulang): %s", ns, e)
        return None


async def redis_set(ns: str, key: str, value, ttl: int) -> None:
    """Simpan nilai cache (JSON) dengan TTL detik. No-op bila nonaktif/gagal."""
    if not redis_aktif():
        return
    try:
        c = _get_client()
        gen = await c.get(_GENP + ns) or "0"
        await c.set(f"{_PREFIX}{ns}:{gen}:{key}",
                    json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.warning("Redis set %s gagal (non-fatal): %s", ns, e)


# ── Invalidasi (bump generasi; fire-and-forget dari konteks sync) ───────────
_bg_tasks: set = set()


async def _bump(namespaces) -> None:
    try:
        c = _get_client()
        for ns in namespaces:
            await c.incr(_GENP + ns)
    except Exception as e:
        logger.warning("Redis bump generasi gagal (non-fatal): %s", e)


def bump_namespaces(namespaces) -> None:
    """Naikkan generasi namespace (invalidasi seketika lintas worker).
    Fire-and-forget — aman dipanggil dari fungsi sync di jalur tulis; no-op
    bila Redis nonaktif atau tak ada event loop berjalan."""
    if not redis_aktif():
        return
    try:
        task = asyncio.ensure_future(_bump(list(namespaces)))
    except RuntimeError:
        # Tak ada event loop (mis. konteks sync murni) — lewati diam-diam.
        return
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def ping() -> bool:
    """True bila Redis merespons PING (untuk health-check). False bila nonaktif/gagal."""
    if not redis_aktif():
        return False
    try:
        return bool(await _get_client().ping())
    except Exception:
        return False
