"""Mode pemeliharaan saat restore — temuan C30.

Restore mengosongkan koleksi satu per satu (`delete_many({})` lalu isi
ulang) sementara aplikasi TETAP melayani penuh — dengan `--workers 2`,
worker saudara tak tahu apa-apa dan tetap menerima tulisan di atas DB yang
sedang setengah terhapus. Middleware di bawah membalas 503 untuk lalu
lintas biasa selama restore berlangsung.

DESAIN: status pemeliharaan DITURUNKAN dari dokumen job yang sudah ada —
`db.backup_jobs.find_one({"active_lock": "GLOBAL"})` — bukan bendera baru
yang dinyalakan/dimatikan manual. Tiga alasan, masing-masing pernah jadi
kegagalan nyata di kelasnya:

  1. Bendera manual punya kasus gagal terburuk: worker mati (OOM) di tengah
     wipe meninggalkan aplikasi 503 SELAMANYA sampai manusia menyunting DB.
     Di sini aturan dievaluasi saat BACA (denyut `updated_at` < 30 menit,
     cutoff yang sama dengan `cleanup_stale_jobs`) — pemeliharaan padam
     sendiri, tidak ada bendera yang bisa nyangkut.
  2. Dokumen `active_lock` sudah atomik (indeks parsial unik single-flight)
     dan `update_job` meng-`$unset`-nya di setiap status terminal — sukses,
     gagal, maupun setelah rollback. Nol baris ditambahkan ke backup.py.
  3. Kebal arsip buatan tangan: `backup_jobs` ada di SKIP_COLLECTIONS dan
     tak pernah diiterasi restore, jadi ZIP yang disunting manual tak bisa
     mewipe sumber kebenaran gerbang ini di tengah jalan. JANGAN
     "menyederhanakan" ini menjadi dokumen bendera di koleksi lain.
"""
import time
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

# Jalur yang TETAP dilayani selama pemeliharaan.
#
# `/api/health` SENGAJA TIDAK ADA di daftar ini — dan itu inti temuannya:
# frontend/lib/connectivity.js hanya melihat `res.ok`, jadi 503 di
# /api/health adalah SATU-SATUNYA cara memberi tahu PWA untuk MENAHAN
# antrean simpan luringnya. Mengecualikannya (tetap 200) membuat
# `flushPending` menembakkan seluruh antrean ke server yang 503 dan tiap
# item ditandai gagal beruntun — menukar satu penyakit dengan penyakit lain.
JALUR_BEBAS = ("/health", "/api/health/deep", "/api/backup/", "/api/ws")


def jalur_bebas(path: str) -> bool:
    return any((path or "").startswith(p) for p in JALUR_BEBAS)


def pemeliharaan_dari_job(job, sekarang, batas_menit: int = 30) -> bool:
    """MURNI. True bila job RESTORE yang aktif masih berdenyut.

    Hanya `type == "restore"` — backup hanya MEMBACA; men-503-kan aplikasi
    selama backup harian adalah regresi ketersediaan yang tak diminta
    siapa pun. `queued` ikut dihitung: jendela antara insert dokumen di
    start_restore dan baris pertama run_restore_task adalah justru saat
    safety-backup membaca seluruh DB.
    """
    if not job or job.get("type") != "restore":
        return False
    if job.get("status") not in ("queued", "running"):
        return False
    u = job.get("updated_at")
    if not u:
        return False
    try:
        t = datetime.fromisoformat(str(u))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (sekarang - t).total_seconds() < batas_menit * 60


# Cache per-worker: /api/health disondir tiap event `online` peramban, dan
# middleware ini menyentuh Mongo. TTL 3 detik membatasinya ke ≤0,33 kueri/
# detik/worker lewat indeks parsial single-flight — TANPA TTL ini, satu
# kueri per request untuk SELURUH aplikasi. Konsekuensi dua arah jendela
# 3 detik diketahui: awal restore, worker lain masih melayani tulisan
# hingga 3 detik (kecil dibanding durasi wipe; menutupnya butuh pub/sub
# lintas-worker); akhir restore, 503 berlanjut hingga 3 detik (jinak).
_CACHE_TTL = 3.0
_cache = (0.0, False)


async def pemeliharaan_aktif() -> bool:
    global _cache
    t, nilai = _cache
    now = time.monotonic()
    if now - t < _CACHE_TTL:
        return nilai
    try:
        from db import db
        job = await db.backup_jobs.find_one(
            {"active_lock": "GLOBAL"},
            {"type": 1, "status": 1, "updated_at": 1})
        nilai = pemeliharaan_dari_job(job, datetime.now(timezone.utc))
    except Exception:
        # GAGAL-BUKA disengaja: Mongo yang tak terjangkau BUKAN pemeliharaan.
        # Membalas 503-pemeliharaan ke semua orang membuat satu masalah
        # koneksi menyamar jadi restore yang tak pernah ada.
        nilai = False
    _cache = (now, nilai)
    return nilai


class PemeliharaanMiddleware:
    """ASGI murni (pola AktivitasMiddleware) — 503 + Retry-After selama
    restore. WebSocket sengaja lolos (scope != http): memutus semua socket
    massal memicu badai reconnect; konsekuensinya klien bisa menerima event
    realtime tentang data yang sedang setengah terhapus — batas yang
    diketahui, bukan kelalaian. OPTIONS lolos: preflight CORS tak boleh
    dijawab 503."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope.get("type") != "http"
                or scope.get("method") == "OPTIONS"
                or jalur_bebas(scope.get("path", ""))
                or not await pemeliharaan_aktif()):
            await self.app(scope, receive, send)
            return
        resp = JSONResponse(
            status_code=503,
            content={"detail": "Sistem sedang dalam pemeliharaan "
                               "(pemulihan data). Coba lagi beberapa saat.",
                     "pemeliharaan": True},
            headers={"Retry-After": "60"})
        await resp(scope, receive, send)
