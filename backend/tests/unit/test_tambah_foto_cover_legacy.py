"""Tambah foto tidak boleh menghilangkan sumber cover legacy yang masih terbaca.

Endpoint baca memang fallback ke photos inline bila blob GridFS hilang. PATCH
harus mempertahankan kemampuan baca itu sebelum mengosongkan array inline.
Mongo/blob tiruan; gambar PNG asli dan handler PATCH/GET produksi tetap diuji.
"""
import asyncio
import base64
import copy
import io
from types import SimpleNamespace

import pytest
from mongomock_motor import AsyncMongoMockClient
from PIL import Image

import routes.assets as ra

USER = {"username": "uji", "role": "admin", "kode_satker": ""}


class Req:
    def __init__(self, body=None):
        self.headers = {}
        self.body = body

    async def json(self):
        return self.body


def gambar(warna):
    buffer = io.BytesIO()
    Image.new("RGB", (160, 120), warna).save(buffer, format="PNG")
    raw = buffer.getvalue()
    return raw, "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


async def diam(*args, **kwargs):
    return None


@pytest.fixture
def penyimpanan(monkeypatch):
    db = AsyncMongoMockClient()["uji_cover"]
    blobs, unggahan, hapusan = {}, [], []

    async def simpan(uri):
        gid = f"foto-baru-{len(unggahan)}"
        blobs[gid] = base64.b64decode(uri.split(",", 1)[1])
        unggahan.append(gid)
        return gid

    async def baca(gid):
        return blobs.get(gid)

    async def hapus(gid):
        hapusan.append(gid)
        blobs.pop(gid, None)

    monkeypatch.setattr(ra, "db", db)
    for name in ("pastikan_akses_aset", "ensure_activity_not_sealed", "notify_asset_change", "log_audit"):
        monkeypatch.setattr(ra, name, diam)
    monkeypatch.setattr(ra, "store_photo_to_gridfs", simpan)
    monkeypatch.setattr(ra, "get_photo_from_gridfs", baca)
    monkeypatch.setattr(ra, "delete_photo_from_gridfs", hapus)
    monkeypatch.setattr(ra, "invalidate_asset_cache", lambda: None)
    monkeypatch.setattr(ra, "jadwalkan_sync", lambda *args: None)
    monkeypatch.setattr(ra.sp, "penempatan_dari_inventarisasi", diam)
    return db, blobs, unggahan, hapusan


@pytest.mark.parametrize("jenis", ["gridfs", "inline", "campuran_sehat", "campuran_blob_hilang"])
def test_cover_dan_foto_lama_tetap_bisa_dibuka_setelah_tambah_foto(penyimpanan, jenis):
    db, blobs, unggahan, hapusan = penyimpanan
    lama, uri_lama = gambar("green")
    baru, uri_baru = gambar("blue")

    async def skenario():
        if jenis in ("gridfs", "campuran_sehat"):
            blobs["cover-lama"] = lama
        await db.assets.insert_one({
            "id": "a1", "asset_code": "3100102001", "NUP": "1", "asset_name": "Kamera Uji",
            "activity_id": "k1", "category": "Dummy", "version": 3,
            "created_at": "2026-09-01T00:00:00+00:00", "thumbnail_index": 0,
            "photos": [] if jenis == "gridfs" else [uri_lama],
            "photo_gridfs_ids": [] if jenis == "inline" else ["cover-lama"],
            "photo_thumbnails": [ra.create_thumbnail(uri_lama)],
        })
        sebelum = await ra.get_asset_photo_full("a1", 0, Req(), _user=USER)
        assert sebelum.body == lama
        await ra.patch_asset("a1", Req({"photo_ops": {
            "keep": [0], "add": [uri_baru], "thumbnail_index": 0, "base_version": 3,
        }}), USER)
        sesudah = await ra.get_asset_photo_full("a1", 0, Req(), _user=USER)
        assert sesudah.body == lama, "foto pertama harus tetap utuh, bukan hanya thumbnail"
        assert (await ra.get_asset_photo_full("a1", 1, Req(), _user=USER)).body == baru
        doc = await db.assets.find_one({"id": "a1"})
        assert doc["thumbnail_index"] == 0
        assert doc["photos"] == []
        assert len(doc["photo_gridfs_ids"]) == 2
        assert doc["version"] == 4
        assert hapusan == [], "menambah foto bukan izin menghapus foto lama"
        assert len(unggahan) == (2 if jenis in ("inline", "campuran_blob_hilang") else 1)

    asyncio.run(skenario())


@pytest.mark.parametrize("gagal", ["unggah_cover", "unggah_baru", "konflik_db", "galat_db"])
def test_pemulihan_gagal_tidak_menghapus_salinan_cover_terakhir(penyimpanan, monkeypatch, gagal):
    db, blobs, unggahan, hapusan = penyimpanan
    lama, uri_lama = gambar("green")
    _, uri_baru = gambar("blue")
    simpan_asli = ra.store_photo_to_gridfs

    async def simpan(uri):
        if (gagal == "unggah_cover" and uri == uri_lama) or (gagal == "unggah_baru" and uri == uri_baru):
            raise OSError("simulasi unggahan gagal")
        return await simpan_asli(uri)

    monkeypatch.setattr(ra, "store_photo_to_gridfs", simpan)

    async def skenario():
        await db.assets.insert_one({
            "id": "a1", "asset_code": "3100102001", "NUP": "1", "asset_name": "Kamera Uji",
            "activity_id": "k1", "category": "Dummy", "version": 3,
            "created_at": "2026-09-01T00:00:00+00:00", "thumbnail_index": 0,
            "photos": [uri_lama], "photo_gridfs_ids": ["cover-lama"],
            "photo_thumbnails": [ra.create_thumbnail(uri_lama)],
        })
        sebelum = copy.deepcopy(await db.assets.find_one({"id": "a1"}))
        if gagal in ("konflik_db", "galat_db"):
            async def tulis_gagal(*args, **kwargs):
                if gagal == "galat_db":
                    raise OSError("simulasi DB gagal")
                return SimpleNamespace(matched_count=0)
            # mongomock_motor membuat wrapper baru setiap akses db.assets;
            # pin wrapper yang disuntik galat agar handler memakai yang sama.
            aset = db.assets
            monkeypatch.setattr(aset, "update_one", tulis_gagal)
            monkeypatch.setattr(ra, "db", SimpleNamespace(assets=aset))
        with pytest.raises(ra.HTTPException) as err:
            await ra.patch_asset("a1", Req({"photo_ops": {
                "keep": [0], "add": [uri_baru], "thumbnail_index": 0, "base_version": 3,
            }}), USER)
        assert err.value.status_code == (409 if gagal == "konflik_db" else 500)
        assert await db.assets.find_one({"id": "a1"}) == sebelum
        assert (await ra.get_asset_photo_full("a1", 0, Req(), _user=USER)).body == lama
        assert blobs == {}, "blob percobaan baru harus dibersihkan, bukan foto lama"
        assert set(hapusan) == set(unggahan)
        assert "cover-lama" not in hapusan

    asyncio.run(skenario())
