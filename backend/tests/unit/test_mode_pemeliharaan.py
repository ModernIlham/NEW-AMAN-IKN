"""Mode pemeliharaan saat restore — temuan C30.

Restore mengosongkan koleksi (`delete_many({})` lalu isi ulang) sementara
aplikasi tetap melayani penuh; dengan `--workers 2` worker saudara menerima
tulisan di atas DB setengah terhapus. Middleware membalas 503 selama
restore — status DITURUNKAN dari dokumen `active_lock` yang sudah ada
(padam sendiri lewat denyut 30 menit; tak ada bendera yang bisa nyangkut).

Uji terpenting di berkas ini: `/api/health` TIDAK dikecualikan.
connectivity.js hanya melihat `res.ok` — 503 di sanalah satu-satunya cara
memberi tahu PWA menahan antrean simpan luringnya. "Memperbaikinya" agar
selalu 200 membuat flushPending menembakkan seluruh antrean ke server 503
dan tiap item ditandai gagal beruntun.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import pemeliharaan as pm


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


def _job(**isi):
    d = {"type": "restore", "status": "running",
         "updated_at": NOW.isoformat()}
    d.update(isi)
    return d


class TestKebijakanJob:
    def test_restore_running_segar(self):
        assert pm.pemeliharaan_dari_job(_job(), NOW) is True

    def test_restore_queued_juga(self):
        # Jendela antara insert dokumen di start_restore dan baris pertama
        # run_restore_task — justru saat safety-backup membaca seluruh DB.
        assert pm.pemeliharaan_dari_job(_job(status="queued"), NOW) is True

    def test_backup_TIDAK_memicu(self):
        # Backup hanya MEMBACA; men-503-kan aplikasi selama backup harian
        # adalah regresi ketersediaan yang tak diminta siapa pun.
        assert pm.pemeliharaan_dari_job(_job(type="backup"), NOW) is False

    def test_status_terminal_padam(self):
        assert pm.pemeliharaan_dari_job(_job(status="completed"), NOW) is False
        assert pm.pemeliharaan_dari_job(_job(status="failed"), NOW) is False

    def test_denyut_basi_padam_sendiri(self):
        # Worker OOM di tengah wipe: tanpa auto-lepas ini, aplikasi 503
        # SELAMANYA sampai manusia menyunting DB. Cutoff = cleanup_stale_jobs.
        basi = (NOW - timedelta(minutes=31)).isoformat()
        assert pm.pemeliharaan_dari_job(_job(updated_at=basi), NOW) is False
        segar = (NOW - timedelta(minutes=29)).isoformat()
        assert pm.pemeliharaan_dari_job(_job(updated_at=segar), NOW) is True

    def test_job_none_dan_updated_at_cacat(self):
        assert pm.pemeliharaan_dari_job(None, NOW) is False
        assert pm.pemeliharaan_dari_job(_job(updated_at=""), NOW) is False
        assert pm.pemeliharaan_dari_job(_job(updated_at="sampah"), NOW) is False
        # Naive datetime tidak melempar (dianggap UTC).
        naive = (NOW.replace(tzinfo=None)).isoformat()
        assert pm.pemeliharaan_dari_job(_job(updated_at=naive), NOW) is True


class TestKebijakanJalur:
    def test_api_health_TIDAK_bebas(self):
        """UJI TERPENTING. connectivity.js hanya melihat `res.ok`, jadi 503
        di /api/health adalah SATU-SATUNYA sinyal bagi PWA untuk menahan
        antrean simpan luringnya selama restore. Menambahkan "/api/health"
        ke JALUR_BEBAS adalah persis 'perbaikan' naluriah yang menukar satu
        penyakit dengan penyakit lain — baca komentar JALUR_BEBAS dulu."""
        assert pm.jalur_bebas("/api/health") is False

    def test_jalur_yang_memang_bebas(self):
        for p in ("/health", "/api/health/deep",
                  "/api/backup/progress/xyz", "/api/ws/keg-1"):
            assert pm.jalur_bebas(p) is True, p

    def test_jalur_biasa_terkena(self):
        for p in ("/api/assets", "/api/auth/login", "/api/media/foo"):
            assert pm.jalur_bebas(p) is False, p


class _AppDalam:
    def __init__(self):
        self.dipanggil = 0

    async def __call__(self, scope, receive, send):
        self.dipanggil += 1
        await send({"type": "http.response.start", "status": 200,
                    "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def _kirim(mw, scope):
    pesan = []

    async def send(m):
        pesan.append(m)

    async def receive():
        return {"type": "http.request"}
    await mw(scope, receive, send)
    return pesan


def _scope(path, tipe="http", method="GET"):
    return {"type": tipe, "path": path, "method": method}


class TestMiddleware:
    def _mw(self, monkeypatch, aktif=True):
        dalam = _AppDalam()
        mw = pm.PemeliharaanMiddleware(dalam)

        async def _aktif():
            return aktif
        monkeypatch.setattr(pm, "pemeliharaan_aktif", _aktif)
        return mw, dalam

    def test_aktif_jalur_biasa_503_dan_app_tak_dipanggil(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch)
        pesan = _jalan(_kirim(mw, _scope("/api/assets")))
        awal = next(m for m in pesan if m["type"] == "http.response.start")
        assert awal["status"] == 503
        header = {k.decode(): v.decode() for k, v in awal["headers"]}
        assert header.get("retry-after") == "60"
        assert dalam.dipanggil == 0

    def test_aktif_api_health_juga_503(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch)
        pesan = _jalan(_kirim(mw, _scope("/api/health")))
        awal = next(m for m in pesan if m["type"] == "http.response.start")
        assert awal["status"] == 503
        assert dalam.dipanggil == 0

    def test_aktif_progress_backup_diteruskan(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch)
        _jalan(_kirim(mw, _scope("/api/backup/progress/abc")))
        assert dalam.dipanggil == 1

    def test_websocket_lolos(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch)
        _jalan(_kirim(mw, _scope("/api/assets", tipe="websocket")))
        assert dalam.dipanggil == 1

    def test_preflight_options_lolos(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch)
        _jalan(_kirim(mw, _scope("/api/assets", method="OPTIONS")))
        assert dalam.dipanggil == 1

    def test_tidak_aktif_semua_diteruskan(self, monkeypatch):
        mw, dalam = self._mw(monkeypatch, aktif=False)
        for p in ("/api/assets", "/api/health", "/api/auth/login"):
            _jalan(_kirim(mw, _scope(p)))
        assert dalam.dipanggil == 3


class _DbMeledak:
    class _Koleksi:
        async def find_one(self, *a, **kw):
            raise RuntimeError("mongo tumbang")

    @property
    def backup_jobs(self):
        return self._Koleksi()


class _DbPencatat:
    def __init__(self, job=None):
        self.n = 0
        self._job = job

    @property
    def backup_jobs(self):
        induk = self

        class _K:
            async def find_one(self, *a, **kw):
                induk.n += 1
                return induk._job
        return _K()


class TestPembacaBerCache:
    def _reset(self):
        pm._cache = (0.0, False)

    def test_gagal_buka(self, monkeypatch):
        # Mongo mati ≠ pemeliharaan: membalas 503 ke semua orang membuat
        # satu masalah koneksi menyamar jadi restore yang tak pernah ada.
        self._reset()
        import db as modul_db
        monkeypatch.setattr(modul_db, "db", _DbMeledak(), raising=False)
        assert _jalan(pm.pemeliharaan_aktif()) is False

    def test_ttl_cache_membatasi_kueri(self, monkeypatch):
        # /api/health disondir tiap event `online`; tanpa TTL ini = satu
        # kueri Mongo per request untuk SELURUH aplikasi.
        self._reset()
        import db as modul_db
        pencatat = _DbPencatat(job=None)
        monkeypatch.setattr(modul_db, "db", pencatat, raising=False)
        _jalan(pm.pemeliharaan_aktif())
        _jalan(pm.pemeliharaan_aktif())
        _jalan(pm.pemeliharaan_aktif())
        assert pencatat.n == 1
        self._reset()


class TestUrutanMiddlewareDanArahBalik:
    def test_pemeliharaan_di_dalam_cors(self):
        """Starlette membangun tumpukan terbalik: yang ditambahkan terakhir
        jadi terluar. Pemeliharaan harus DI DALAM CORS supaya 503-nya
        membawa header CORS — di luar, peramban melaporkan kegagalan
        JARINGAN dan PWA salah menafsirkan. Diperiksa lewat urutan
        `add_middleware` di sumber (impor server terlalu berat di sini)."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[2] / "server.py"
               ).read_text(encoding="utf-8")
        i_pm = src.index("app.add_middleware(PemeliharaanMiddleware)")
        i_cors = src.index("app.add_middleware(\n    CORSMiddleware")
        assert i_pm < i_cors

    def test_backup_jobs_tetap_di_skip_collections(self):
        # Sumber kebenaran gerbang ini tak boleh bisa di-wipe oleh restore —
        # arsip ZIP buatan tangan berisi backup_jobs.json sekalipun.
        from backup_utils import SKIP_COLLECTIONS, collections_to_process
        assert "backup_jobs" in SKIP_COLLECTIONS
        assert "backup_jobs" not in collections_to_process(
            ["assets", "backup_jobs", "users"])
