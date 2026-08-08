"""Backup menulis JSON BERTAHAP — temuan S2 (puncak RAM 3 salinan per koleksi).

Pola lama di `run_backup_task` dan safety-snapshot `run_restore_task`:
kumpulkan seluruh koleksi ke `list`, `json.dumps` seluruhnya jadi satu
string, `writestr` meng-encode-nya lagi — tiga salinan hidup berbarengan.
Terukur (tracemalloc, dokumen aset ±470 byte): 200.000 dokumen → puncak
1,1 GB; versi bertahap → 0,3 MB, dengan berkas ZIP identik.

Format TIDAK berubah: hasilnya tetap satu array JSON sah (pembaca lama
`json.loads(zf.read(...))` tak tersentuh), satu dokumen per baris —
membuka jalan membaca bertahap kelak tanpa mengubah format arsip.

Sisa cakupan S2 yang SENGAJA belum di sini (dicatat supaya tak dikira
selesai): sisi BACA restore masih `json.loads` seluruh koleksi + salinan
BSON `insert_many` — puncak terukur 688 MB pada 200.000 dokumen.
"""
import asyncio
import inspect
import json
import tracemalloc
import zipfile

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.backup as rb


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def fake_db(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rb, "db", fake, raising=False)
    return fake


def _tulis(tmp_path, col, keep_id=False):
    p = tmp_path / "arsip.zip"
    with zipfile.ZipFile(str(p), "w", zipfile.ZIP_DEFLATED) as zf:
        n = _jalan(rb._tulis_koleksi_json(zf, col, keep_id))
    return p, n


class TestKesetaraanFormat:
    def test_roundtrip_isi_dan_urutan_identik(self, fake_db, tmp_path):
        docs = [{"id": f"a{i}", "asset_name": f"Aset {i}", "NUP": str(i)}
                for i in range(300)]
        _jalan(fake_db.assets.insert_many([dict(d) for d in docs]))
        harapan = _jalan(_kumpul(fake_db, "assets", keep_id=False))

        p, n = _tulis(tmp_path, "assets")
        with zipfile.ZipFile(str(p)) as zf:
            hasil = json.loads(zf.read("assets.json"))
        assert n == 300
        assert hasil == harapan

    def test_koleksi_kosong_persis_json_dumps_lama(self, fake_db, tmp_path):
        p, n = _tulis(tmp_path, "assets")
        with zipfile.ZipFile(str(p)) as zf:
            assert zf.read("assets.json") == json.dumps([]).encode() == b"[]"
        assert n == 0

    def test_keep_id_dipertahankan_untuk_counters(self, fake_db, tmp_path):
        # `counters._id` adalah nama sequence tiket — membuangnya merusak
        # penomoran pasca-restore.
        _jalan(fake_db.counters.insert_one({"_id": "tiket_2026", "seq": 41}))
        p, _ = _tulis(tmp_path, "counters", keep_id=True)
        with zipfile.ZipFile(str(p)) as zf:
            hasil = json.loads(zf.read("counters.json"))
        assert hasil[0]["_id"] == "tiket_2026"

        _jalan(fake_db.assets.insert_one({"id": "a1"}))
        (tmp_path / "b").mkdir()
        p2, _ = _tulis(tmp_path / "b", "assets", keep_id=False)
        with zipfile.ZipFile(str(p2)) as zf:
            assert "_id" not in json.loads(zf.read("assets.json"))[0]


async def _kumpul(db, col, keep_id):
    return [rb.serialize_doc(d, keep_id=keep_id)
            async for d in db[col].find({})]


class TestPenguncianPerbaikan:
    def test_json_dumps_tak_pernah_menerima_LIST(self, fake_db, tmp_path,
                                                 monkeypatch):
        """Mata-mata deterministik: pola lama `json.dumps(docs)` menerima
        `list`; versi bertahap men-dumps SATU dict per panggilan. Mati
        seketika bila ada yang mengembalikan pola lama."""
        _jalan(fake_db.assets.insert_many(
            [{"id": f"a{i}"} for i in range(300)]))
        tipe = []
        asli = json.dumps

        def _mata_mata(obj, *a, **kw):
            tipe.append(type(obj))
            return asli(obj, *a, **kw)
        monkeypatch.setattr(rb.json, "dumps", _mata_mata)
        _tulis(tmp_path, "assets")
        assert tipe, "json.dumps tak terpanggil sama sekali?"
        assert list not in tipe

    def test_puncak_memori_bertahap_jauh_di_bawah_pola_lama(self, fake_db,
                                                            tmp_path):
        """Ambang RELATIF (bukan angka keramat): pola lama diukur pada
        dataset yang SAMA di proses yang sama, lalu versi bertahap dituntut
        < 1/5-nya — kebal terhadap overhead mongomock/lingkungan CI."""
        isi = "x" * 1000
        _jalan(fake_db.assets.insert_many(
            [{"id": f"a{i}", "blob": isi} for i in range(5000)]))

        async def _pola_lama():
            docs = []
            async for doc in rb.db.assets.find({}):
                docs.append(rb.serialize_doc(doc, keep_id=False))
            (tmp_path / "lama.zip").write_bytes(b"")
            with zipfile.ZipFile(str(tmp_path / "lama.zip"), "w",
                                 zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("assets.json",
                            json.dumps(docs, ensure_ascii=False, default=str))

        tracemalloc.start()
        _jalan(_pola_lama())
        _, puncak_lama = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tracemalloc.start()
        _tulis(tmp_path, "assets")
        _, puncak_baru = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert puncak_baru * 5 < puncak_lama, (puncak_baru, puncak_lama)

    def test_safety_snapshot_juga_memakai_helper(self):
        """Mutasi terpenting butir ini: memperbaiki HANYA run_backup_task
        dan meninggalkan safety-snapshot memakai pola lama — persis
        setengah-perbaikan yang paling mungkin terjadi."""
        src = inspect.getsource(rb.run_restore_task)
        a = src.index("safety_data_zip")
        b = src.index("Safety backup GridFS")
        blok = src[a:b]
        assert "_tulis_koleksi_json(" in blok
        assert "docs = []" not in blok

    def test_run_backup_task_juga(self):
        src = inspect.getsource(rb.run_backup_task)
        assert "_tulis_koleksi_json(" in src
        assert "docs = []" not in src


class TestPagarTeknisZip:
    """Tiga properti ZipInfo yang gampang hilang saat refactor."""

    def test_entri_tetap_terkompresi_deflate(self, fake_db, tmp_path):
        # ZipInfo TIDAK mewarisi kompresi ZipFile: tanpa compress_type
        # eksplisit entri jadi STORED — terukur 9,3x lebih besar, dan guard
        # disk (gridfs + 200MB margin) bisa jebol pada DB besar.
        _jalan(fake_db.assets.insert_many(
            [{"id": f"a{i}", "blob": "y" * 500} for i in range(50)]))
        p, _ = _tulis(tmp_path, "assets")
        with zipfile.ZipFile(str(p)) as zf:
            info = zf.getinfo("assets.json")
            assert info.compress_type == zipfile.ZIP_DEFLATED
            assert info.compress_size < info.file_size

    def test_stempel_waktu_entri_bukan_1980(self, fake_db, tmp_path):
        # `zf.open(nama_str)` memberi tanggal default ZipInfo (1980-01-01);
        # untuk arsip CADANGAN tanggal entri punya nilai forensik.
        _jalan(fake_db.assets.insert_one({"id": "a1"}))
        p, _ = _tulis(tmp_path, "assets")
        with zipfile.ZipFile(str(p)) as zf:
            assert zf.getinfo("assets.json").date_time[0] >= 2026

    def test_force_zip64_terpasang(self, fake_db, tmp_path, monkeypatch):
        # Tanpa force_zip64, entri >2 GiB membuat close() melempar — tepat
        # pada DB terbesar, satu-satunya kasus di mana perbaikan ini penting.
        _jalan(fake_db.assets.insert_one({"id": "a1"}))
        rekam = []
        asli = zipfile.ZipFile.open

        def _open(self, name, mode="r", *a, **kw):
            if mode == "w":
                rekam.append(kw)
            return asli(self, name, mode, *a, **kw)
        monkeypatch.setattr(zipfile.ZipFile, "open", _open)
        _tulis(tmp_path, "assets")
        assert rekam and all(kw.get("force_zip64") is True for kw in rekam)


class TestUjungKeUjung:
    def test_run_backup_task_menghasilkan_arsip_sah_dan_angka_benar(
            self, fake_db, tmp_path, monkeypatch):
        """Menangkap dua regresi yang hanya muncul saat runtime: dua handle
        tulis terbuka bersamaan (ValueError), dan nilai balik helper yang
        diabaikan sehingga `total_records` di metadata/job berbohong."""
        _jalan(fake_db.assets.insert_many(
            [{"id": f"a{i}"} for i in range(7)]))
        _jalan(fake_db.users.insert_many(
            [{"username": f"u{i}"} for i in range(3)]))
        # update_job() meng-update tanpa upsert — dokumen job harus sudah ada.
        _jalan(fake_db.backup_jobs.insert_one(
            {"job_id": "job-uji", "status": "queued"}))

        monkeypatch.setattr(rb, "BACKUP_TEMP_DIR", tmp_path, raising=False)
        monkeypatch.setattr(rb, "UPLOADS_DIR", tmp_path / "tidak-ada",
                            raising=False)

        async def _gridfs_stub(zf, progress_cb=None):
            return 0
        monkeypatch.setattr(rb, "export_gridfs", _gridfs_stub, raising=False)

        import collections
        import shutil as _sh
        DU = collections.namedtuple("usage", "total used free")
        monkeypatch.setattr(_sh, "disk_usage",
                            lambda p: DU(10**12, 0, 10**12))

        _jalan(rb.run_backup_task("job-uji", "penguji"))

        zips = list(tmp_path.glob("*.zip"))
        assert zips, "arsip tidak tercipta"
        with zipfile.ZipFile(str(zips[0])) as zf:
            assert zf.testzip() is None
            meta = json.loads(zf.read("metadata.json"))
            assert meta["total_records"] == 10
            assert json.loads(zf.read("assets.json"))[0]["id"] == "a0"

        job = _jalan(rb.db.backup_jobs.find_one({"job_id": "job-uji"}))
        assert job["status"] == "completed"
        assert job["total_records"] == 10
