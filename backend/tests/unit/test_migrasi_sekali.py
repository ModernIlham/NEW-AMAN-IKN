"""Penanda migrasi startup (S6) — backfill sekali seumur hidup, bukan tiap boot.

Tiga backfill di `server.py` dulu berjalan pada SETIAP boot × jumlah worker;
dua di antaranya collscan penuh `assets`. Kini tiap backfill digerbangi
penanda `migrasi:*` di `app_runtime`. Aturan yang dikunci uji di sini:

  1. Kunci TERPISAH per migrasi — satu kunci gabungan berarti migrasi
     keempat kelak terlewat diam-diam bila tiga pertama sudah tertanda.
  2. Tandai HANYA setelah kerja sukses — menandai lebih awal mengubah
     "non-fatal, akan diulang" menjadi "gagal permanen dan senyap".
  3. Ragu = ulangi (fail-open): ketiga backfill idempoten; melewatkannya
     merusak data, mengulanginya cuma buang waktu.
  4. Pembersihan pasca-restore HANYA menyentuh prefiks `migrasi:` —
     kursor migrasi WebP & stempel activity-tracker hidup di koleksi yang
     sama dan tak boleh ikut tersapu.

`app_runtime` ada di SKIP_COLLECTIONS sehingga penanda TIDAK dikosongkan
restore — pembersihan eksplisit di routes/backup.py adalah bagian dari
kebenaran fitur ini, bukan pelengkap (tanpanya: arsip lama dipulihkan, aset
ber-status yatim hidup kembali, dan normalisasinya tak pernah jalan lagi).
"""
import asyncio
import pathlib
import re

import pytest

import server
import shared_utils
import routes.pengesahan as pengesahan

BACKEND = pathlib.Path(__file__).resolve().parents[2]


class _Hasil:
    modified_count = 0


class _KoleksiAset:
    def __init__(self, lempar_sekali=False):
        self.panggilan = []
        self._lempar = lempar_sekali

    async def update_many(self, filter_, update):
        if self._lempar:
            self._lempar = False
            raise RuntimeError("mongo hiccup")
        self.panggilan.append(filter_)
        return _Hasil()


class _AppRuntime:
    """Tiruan app_runtime: dokumen ber-_id bermakna, upsert, regex delete."""

    def __init__(self, isi=None):
        self.isi = dict(isi or {})
        self.gagal_baca = False

    async def find_one(self, filter_, proj=None):
        if self.gagal_baca:
            raise RuntimeError("mongo tak terjangkau")
        _id = filter_["_id"]
        return {"_id": _id} if _id in self.isi else None

    async def update_one(self, filter_, update, upsert=False):
        self.isi[filter_["_id"]] = update.get("$set", {})

    async def delete_many(self, filter_):
        pola = filter_["_id"]["$regex"]
        kena = [k for k in self.isi if re.match(pola, k)]
        for k in kena:
            del self.isi[k]

        class _R:
            deleted_count = len(kena)
        return _R()


class _Db:
    def __init__(self, app_runtime=None, aset=None):
        self.app_runtime = app_runtime or _AppRuntime()
        self.assets = aset or _KoleksiAset()


def _jalankan(monkeypatch, db, tiket_dipanggil):
    async def _tiket_palsu():
        tiket_dipanggil.append(1)

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(shared_utils, "db", db)
    monkeypatch.setattr(pengesahan, "backfill_ticket_numbers", _tiket_palsu)
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        loop.run_until_complete(server.jalankan_backfill_startup())
    finally:
        loop.close()


KUNCI = ["migrasi:occ_version_v1", "migrasi:status_inventaris_v1",
         "migrasi:tiket_kegiatan_v1"]


class TestBootPertama:
    def test_menjalankan_ketiganya_lalu_menandai(self, monkeypatch):
        db, tiket = _Db(), []
        _jalankan(monkeypatch, db, tiket)
        assert len(db.assets.panggilan) == 2
        assert len(tiket) == 1
        assert sorted(db.app_runtime.isi) == sorted(KUNCI)


class TestBootKedua:
    def test_nol_pemindaian(self, monkeypatch):
        """Inti S6: penanda ada → tak satu pun backfill menyentuh data."""
        db = _Db(app_runtime=_AppRuntime({k: {} for k in KUNCI}))
        tiket = []
        _jalankan(monkeypatch, db, tiket)
        assert db.assets.panggilan == []
        assert tiket == []


class TestKunciTerpisah:
    def test_satu_penanda_tidak_mematikan_yang_lain(self, monkeypatch):
        db = _Db(app_runtime=_AppRuntime({"migrasi:occ_version_v1": {}}))
        tiket = []
        _jalankan(monkeypatch, db, tiket)
        # OCC dilewati; normalisasi status & tiket tetap jalan.
        assert len(db.assets.panggilan) == 1
        assert "inventory_status" in db.assets.panggilan[0]
        assert len(tiket) == 1


class TestKegagalanTidakMenandai:
    def test_gagal_diulang_boot_berikutnya(self, monkeypatch):
        db = _Db(aset=_KoleksiAset(lempar_sekali=True))
        _jalankan(monkeypatch, db, [])
        # Panggilan pertama (OCC) melempar → TIDAK tertanda; dua lainnya
        # sukses dan tertanda.
        assert "migrasi:occ_version_v1" not in db.app_runtime.isi
        assert "migrasi:status_inventaris_v1" in db.app_runtime.isi
        # Boot berikutnya: OCC jalan lagi (kini sukses) lalu tertanda.
        _jalankan(monkeypatch, db, [])
        assert "migrasi:occ_version_v1" in db.app_runtime.isi


class TestRaguBerartiUlangi:
    def test_query_penanda_melempar_backfill_TETAP_jalan(self, monkeypatch):
        """Fail-open disengaja: melewatkan backfill merusak data, mengulang
        hanya membuang waktu — `sudah_dimigrasi` yang melempar wajib False."""
        db = _Db()
        db.app_runtime.gagal_baca = True
        tiket = []
        _jalankan(monkeypatch, db, tiket)
        assert len(db.assets.panggilan) == 2
        assert len(tiket) == 1


class TestPembersihanPascaRestore:
    def test_hanya_prefiks_migrasi_yang_tersapu(self, monkeypatch):
        db = _Db(app_runtime=_AppRuntime({
            "migrasi:occ_version_v1": {},
            "migrasi:status_inventaris_v1": {},
            "webp_thumb_cursor": {"posisi": "abc"},
            "webp_lease": {"pemegang": "w1"},
            "activity_tracker:stamp": {},
        }))
        monkeypatch.setattr(shared_utils, "db", db)
        loop = asyncio.get_event_loop_policy().new_event_loop()
        try:
            n = loop.run_until_complete(shared_utils.bersihkan_penanda_migrasi())
        finally:
            loop.close()
        assert n == 2
        assert sorted(db.app_runtime.isi) == [
            "activity_tracker:stamp", "webp_lease", "webp_thumb_cursor"]

    def test_restore_benar_benar_memanggilnya(self):
        """Penjaga tingkat-sumber (pola yang sama dengan uji skrip shell):
        pemanggilan harus ada di routes/backup.py, SETELAH pemulihan data
        (repair_ticket_counters) — uji perilaku penuh butuh Mongo hidup,
        yang dilarang di direktori ini."""
        src = (BACKEND / "routes" / "backup.py").read_text(encoding="utf-8")
        i_repair = src.index("repair_ticket_counters()")
        i_bersih = src.index("bersihkan_penanda_migrasi")
        assert i_bersih > i_repair
