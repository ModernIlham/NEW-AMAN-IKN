"""Pelacak aktivitas request — untuk pekerjaan latar yang "idle-aware".

Menyediakan sinyal SEDERHANA & LINTAS-WORKER: "kapan request terakhir masuk?".
Dipakai konverter WebP latar (webp_converter.py) agar HANYA bekerja saat
aplikasi benar-benar sepi, dan berhenti begitu ada aktivitas — demi menjaga
performa aplikasi.

Cara kerja:
- Middleware ASGI tipis (`AktivitasMiddleware`) mencatat setiap request nyata.
- Untuk menghindari tulis DB per-request, penulisan "waktu aktivitas terakhir"
  ke Mongo di-THROTTLE: paling sering sekali per ``INTERVAL_FLUSH`` detik per
  worker. Di bawah beban, ini ≤1 tulis kecil/5 dtk/worker (dapat diabaikan);
  saat sepi, tak ada tulis sama sekali sehingga stempel waktu "menua" dan
  worker latar menganggap aplikasi idle.
- ``aplikasi_idle()`` membaca stempel bersama itu → keputusan idle berlaku
  untuk SELURUH worker (2–4 proses uvicorn), bukan hanya worker lokal.

Path health-check (dan sejenis) diabaikan agar heartbeat infrastruktur tak
dianggap "aktivitas pengguna".
"""
import time
from datetime import datetime, timezone

# Path yang TIDAK dihitung sebagai aktivitas nyata (heartbeat/health probe).
_SKIP_PREFIXES = ("/api/health", "/health", "/api/ws")
_DOC_ID = "aktivitas_terakhir"
INTERVAL_FLUSH = 5.0  # detik — throttle tulis DB per worker

_last_flush_monotonic = 0.0


def _relevan(path: str) -> bool:
    if not path:
        return False
    return not any(path.startswith(p) for p in _SKIP_PREFIXES)


async def _tulis_stempel():
    """Tulis waktu aktivitas terakhir ke Mongo (best-effort, non-fatal)."""
    try:
        from db import db
        await db.app_runtime.update_one(
            {"_id": _DOC_ID},
            {"$set": {"waktu": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception:
        # Pelacakan idle bersifat pembantu — jangan pernah ganggu request.
        pass


async def catat_aktivitas(path: str):
    """Catat satu request nyata; tulis stempel ke DB dengan throttle."""
    global _last_flush_monotonic
    if not _relevan(path):
        return
    now = time.monotonic()
    if now - _last_flush_monotonic < INTERVAL_FLUSH:
        return
    _last_flush_monotonic = now
    await _tulis_stempel()


async def aplikasi_idle(idle_detik: float) -> bool:
    """True bila TIDAK ada request nyata selama >= ``idle_detik`` (lintas-worker).

    Bila stempel belum pernah ada (mis. baru start & belum ada trafik),
    dianggap idle.
    """
    try:
        from db import db
        doc = await db.app_runtime.find_one({"_id": _DOC_ID}, {"waktu": 1})
    except Exception:
        return False  # ragu → anggap TIDAK idle (konservatif, jaga performa)
    if not doc or not doc.get("waktu"):
        return True
    waktu = doc["waktu"]
    if waktu.tzinfo is None:
        waktu = waktu.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - waktu).total_seconds() >= idle_detik


class AktivitasMiddleware:
    """Middleware ASGI murni — mencatat aktivitas request tanpa mengganggu
    body/streaming. Dipasang tipis; overhead hanya cek monotonic + (jarang)
    satu upsert kecil."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            # Setelah respons selesai — tak menunda pengiriman ke klien.
            try:
                await catat_aktivitas(scope.get("path", ""))
            except Exception:
                pass
