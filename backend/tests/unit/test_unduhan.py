"""Uji PUSAT UNDUHAN (routes/unduhan.py) — tanpa Mongo/HTTP sungguhan.

Yang dikunci di sini:
- pagar `path_unduhan_valid` (traversal, skema, area terlarang);
- alur mulai → antre (hapus_pada = +30 hari, batas 3 job aktif per user);
- daftar hanya milik pemilik; unduh 404 sebelum siap; isolasi satker
  fail-closed pada akses file;
- worker menyimpan hasil panggilan internal ke GridFS + status done
  (transport HTTP dipalsukan — endpoint dalam tak benar-benar dipanggil);
- sapuan retensi: blob GridFS yatim (dokumen sudah di-TTL) terhapus,
  blob ber-dokumen hidup dibiarkan, job macet di-relabel error.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.unduhan as ru

USER = {"username": "budi", "role": "petugas", "kode_satker": "KD1"}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


class _Req:
    """Request palsu — cukup .headers.get untuk mulai_unduhan."""
    def __init__(self, headers=None):
        self.headers = headers or {"authorization": "Bearer uji"}


class _BucketPalsu:
    """fs_bucket palsu: catat tulis & hapus & baca di memori."""
    def __init__(self):
        self.tersimpan = {}
        self.terhapus = []

    def open_upload_stream_with_id(self, file_id, filename=None, metadata=None):
        bucket = self

        class _Aliran:
            def __init__(self):
                self.buf = b""
                self.dibatalkan = False

            async def write(self, data):
                self.buf += data

            async def close(self):
                bucket.tersimpan[str(file_id)] = {
                    "filename": filename, "metadata": metadata,
                    "data": self.buf}

            async def abort(self):
                self.dibatalkan = True
        return _Aliran()

    async def open_download_stream(self, file_id):
        data = self.tersimpan.get(str(file_id), {}).get("data")
        if data is None:
            raise FileNotFoundError(file_id)

        class _Baca:
            def __init__(self):
                self._sisa = data

            async def readchunk(self):
                out, self._sisa = self._sisa, b""
                return out
        return _Baca()

    async def delete(self, file_id):
        self.terhapus.append(file_id)


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(ru, "db", fake, raising=False)
    monkeypatch.setattr(ru, "_COL", fake.unduhan, raising=False)
    monkeypatch.setattr(ru, "fs_bucket", _BucketPalsu(), raising=False)
    monkeypatch.setattr(ru, "JEDA_ANTAR_JOB", 0, raising=False)
    return fake


# ---------------------------------------------------------------- validasi path
def test_path_valid_menerima_path_laporan():
    assert ru.path_unduhan_valid(
        "/inventory-activities/abc123/executive-grouped-pdf"
        "?detail_fields=merk,tahun")
    assert ru.path_unduhan_valid("/export/xlsx")
    assert ru.path_unduhan_valid("/laporan-satker/2026/pdf")


def test_path_valid_menolak_yang_berbahaya():
    assert not ru.path_unduhan_valid("relatif/tanpa-garis-miring")
    assert not ru.path_unduhan_valid("/foo/../../etc/passwd")
    assert not ru.path_unduhan_valid("http://jahat.example/x")
    assert not ru.path_unduhan_valid("/foo\\bar")
    assert not ru.path_unduhan_valid("/backup/download/x")
    assert not ru.path_unduhan_valid("/unduhan/mulai")   # tanpa rekursi
    assert not ru.path_unduhan_valid("/auth/login")
    assert not ru.path_unduhan_valid("/jobs/abc/download")
    assert not ru.path_unduhan_valid("")
    assert not ru.path_unduhan_valid("/a" * 1500)


def test_path_valid_menolak_bypass_percent_encoding():
    # httpx ASGITransport merutekan pada path terdekode: '/%75sers' → '/users'.
    # Validator harus melihat bentuk terdekode, bukan string mentah.
    assert not ru.path_unduhan_valid("/%75sers/list")       # /users
    assert not ru.path_unduhan_valid("/%62ackup/download/x")  # /backup
    assert not ru.path_unduhan_valid("/auth/%2e%2e/x")        # traversal enc
    assert not ru.path_unduhan_valid("/%2561uth/login")       # double-encode


# --------------------------------------------------------------------- mulai
def test_mulai_unduhan_antre_dengan_retensi_30_hari(dbx, monkeypatch):
    async def _diam(*a, **k):
        return None
    monkeypatch.setattr(ru, "_jalankan_unduhan", _diam)

    async def skenario():
        hasil = await _unwrap(ru.mulai_unduhan)(
            ru.MulaiUnduhanIn(path="/export/csv?activity_id=a1",
                              nama_file="aset.csv", label="Ekspor CSV"),
            _Req(), user=dict(USER))
        doc = await dbx.unduhan.find_one({"unduhan_id": hasil["unduhan_id"]})
        assert doc["status"] == "queued"
        assert doc["dibuat_oleh"] == "budi"
        assert doc["kode_satker"] == "KD1"
        selisih = doc["hapus_pada"] - doc["created_at"]
        assert abs(selisih - timedelta(days=30)) < timedelta(minutes=1)
    _jalan(skenario())


def test_mulai_unduhan_menolak_path_buruk_dan_batas_aktif(dbx, monkeypatch):
    async def _diam(*a, **k):
        return None
    monkeypatch.setattr(ru, "_jalankan_unduhan", _diam)

    async def skenario():
        with pytest.raises(HTTPException) as e:
            await _unwrap(ru.mulai_unduhan)(
                ru.MulaiUnduhanIn(path="http://x", nama_file="f.pdf"),
                _Req(), user=dict(USER))
        assert e.value.status_code == 400

        for i in range(ru.MAKS_AKTIF_PER_USER):
            await dbx.unduhan.insert_one(
                {"unduhan_id": f"u{i}", "dibuat_oleh": "budi",
                 "status": "running"})
        with pytest.raises(HTTPException) as e:
            await _unwrap(ru.mulai_unduhan)(
                ru.MulaiUnduhanIn(path="/export/csv", nama_file="f.csv"),
                _Req(), user=dict(USER))
        assert e.value.status_code == 409
    # Cap per-user tak boleh melebihi kapasitas 1 slot per worker.
    assert ru.MAKS_AKTIF_PER_USER == 1
    _jalan(skenario())


# -------------------------------------------------------------- daftar & file
def test_daftar_hanya_milik_pemilik(dbx):
    async def skenario():
        kini = datetime.now(timezone.utc)
        await dbx.unduhan.insert_one(
            {"unduhan_id": "a", "dibuat_oleh": "budi", "status": "done",
             "created_at": kini})
        await dbx.unduhan.insert_one(
            {"unduhan_id": "b", "dibuat_oleh": "sari", "status": "done",
             "created_at": kini})
        hasil = await _unwrap(ru.daftar_unduhan)(user=dict(USER))
        ids = [i["unduhan_id"] for i in hasil["items"]]
        assert ids == ["a"]
    _jalan(skenario())


def test_unduh_file_belum_siap_404_dan_isolasi_satker(dbx, monkeypatch):
    async def skenario():
        await dbx.unduhan.insert_one(
            {"unduhan_id": "u1", "dibuat_oleh": "budi", "status": "running",
             "kode_satker": "KD1"})
        with pytest.raises(HTTPException) as e:
            await _unwrap(ru.unduh_file)("u1", user=dict(USER))
        assert e.value.status_code == 404      # belum done

        # admin satker LAIN → 403 (fail-closed)
        fid = str(ObjectId())
        ru.fs_bucket.tersimpan[fid] = {"data": b"ISI-PDF"}
        await dbx.unduhan.update_one(
            {"unduhan_id": "u1"},
            {"$set": {"status": "done", "artifact_id": fid,
                      "artifact_type": "application/pdf"}})
        admin_lain = {"username": "adminb", "role": "admin",
                      "kode_satker": "KD2"}
        with pytest.raises(HTTPException) as e:
            await _unwrap(ru.unduh_file)("u1", user=admin_lain)
        assert e.value.status_code == 403

        resp = await _unwrap(ru.unduh_file)("u1", user=dict(USER))
        assert resp.media_type == "application/pdf"
        # Alirkan streaming body → pastikan isi benar.
        potongan = b""
        async for p in resp.body_iterator:
            potongan += p if isinstance(p, bytes) else p.encode()
        assert potongan == b"ISI-PDF"
    _jalan(skenario())


# --------------------------------------------------------------------- worker
class _RespPalsu:
    def __init__(self, status=200, data=b"%PDF-1.4 isi",
                 ctype="application/pdf"):
        self.status_code = status
        self.headers = {"content-type": ctype}
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def aread(self):
        return self._data

    async def aiter_bytes(self, _n):
        yield self._data


class _KlienPalsu:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, headers=None):
        assert method == "GET" and url.startswith("/api/")
        return _RespPalsu()


def test_worker_simpan_hasil_ke_gridfs(dbx, monkeypatch):
    class _HttpxPalsu:
        ASGITransport = lambda *a, **k: None            # noqa: E731
        Timeout = lambda *a, **k: None                  # noqa: E731
        AsyncClient = _KlienPalsu
    monkeypatch.setattr(ru, "httpx", _HttpxPalsu)
    monkeypatch.setattr(ru, "_app_internal", lambda: None)

    async def skenario():
        await dbx.unduhan.insert_one(
            {"unduhan_id": "w1", "nama_file": "laporan.pdf",
             "status": "queued", "dibuat_oleh": "budi"})
        await ru._jalankan_unduhan("w1", "/laporan/x", {})
        doc = await dbx.unduhan.find_one({"unduhan_id": "w1"})
        assert doc["status"] == "done"
        assert doc["artifact_id"]
        assert doc["artifact_type"] == "application/pdf"
        blob = ru.fs_bucket.tersimpan[doc["artifact_id"]]
        assert blob["data"] == b"%PDF-1.4 isi"
        assert blob["metadata"]["unduhan_id"] == "w1"
    _jalan(skenario())


def test_worker_galat_http_jadi_error_dengan_detail(dbx, monkeypatch):
    class _Klien404(_KlienPalsu):
        def stream(self, method, url, headers=None):
            return _RespPalsu(status=404,
                              data=b'{"detail": "Kegiatan tidak ditemukan"}')

    class _HttpxPalsu:
        ASGITransport = lambda *a, **k: None            # noqa: E731
        Timeout = lambda *a, **k: None                  # noqa: E731
        AsyncClient = _Klien404
    monkeypatch.setattr(ru, "httpx", _HttpxPalsu)
    monkeypatch.setattr(ru, "_app_internal", lambda: None)

    async def skenario():
        await dbx.unduhan.insert_one(
            {"unduhan_id": "w2", "nama_file": "x.pdf", "status": "queued"})
        await ru._jalankan_unduhan("w2", "/laporan/x", {})
        doc = await dbx.unduhan.find_one({"unduhan_id": "w2"})
        assert doc["status"] == "error"
        assert "Kegiatan tidak ditemukan" in doc["error_message"]
    _jalan(skenario())


# ------------------------------------------------------------------- retensi
def test_sapuan_hapus_blob_yatim_dan_relabel_macet(dbx):
    async def skenario():
        kini = datetime.now(timezone.utc)
        # Blob dengan dokumen HIDUP → dibiarkan.
        await dbx.unduhan.insert_one(
            {"unduhan_id": "hidup", "status": "done",
             "updated_at": kini})
        await dbx["fs.files"].insert_one(
            {"_id": "b1", "metadata": {"unduhan_id": "hidup"},
             "uploadDate": datetime.utcnow()})
        # Blob YATIM (dokumen sudah di-TTL) → dihapus.
        await dbx["fs.files"].insert_one(
            {"_id": "b2", "metadata": {"unduhan_id": "sudah-ttl"},
             "uploadDate": datetime.utcnow()})
        # Job macet >90 menit → error.
        await dbx.unduhan.insert_one(
            {"unduhan_id": "macet", "status": "running",
             "updated_at": kini - timedelta(hours=3)})

        n = await ru.bersihkan_unduhan_kedaluwarsa()
        assert n == 1
        assert ru.fs_bucket.terhapus == ["b2"]
        macet = await dbx.unduhan.find_one({"unduhan_id": "macet"})
        assert macet["status"] == "error"
        hidup = await dbx.unduhan.find_one({"unduhan_id": "hidup"})
        assert hidup["status"] == "done"
    _jalan(skenario())


def test_potong_detail_mengurai_json_dan_memangkas():
    assert ru._potong_detail(b'{"detail": "Akses ditolak"}') == "Akses ditolak"
    assert ru._potong_detail("teks polos") == "teks polos"
    assert len(ru._potong_detail("x" * 999)) == 300
    assert ru._potong_detail(b"\xff\xfe rusak").strip() != ""
