"""Uji ENDPOINT untuk empat perbaikan backend gelombang G3.

Keempatnya cacat yang lolos hijau CI justru karena endpoint tak pernah
dijalankan: version yang tak naik, idempotensi yang kedaluwarsa, photo_ops
tanpa ikatan versi, dan updated_at yang tak terstempel. Mongo in-process
(mongomock_motor) — tanpa server, tanpa jaringan.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.assets as ra
import routes.batch as rb

USER = {"username": "uji", "role": "admin", "kode_satker": ""}


class _Req:
    """Objek request minimum — hanya headers & json yang disentuh handler."""
    def __init__(self, headers=None, body=None):
        self.headers = headers or {}
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("tanpa body")
        return self._body


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    for mod in (ra, rb):
        monkeypatch.setattr(mod, "db", fake)
        for nama in ("log_audit",):
            if hasattr(mod, nama):
                monkeypatch.setattr(mod, nama, _diam)
    # Penjaga akses & segel: bukan yang diuji di berkas ini.
    for nama in ("pastikan_akses_aset", "ensure_activity_not_sealed",
                 "pastikan_akses_kegiatan_id"):
        if hasattr(ra, nama):
            monkeypatch.setattr(ra, nama, _diam)
    return fake


# ── B1: Ubah Massal menaikkan version ───────────────────────────────────────

def test_batch_update_menaikkan_version(dbx, monkeypatch):
    """Tanpa $inc version, penjaga OCC/If-Match BUTA terhadap ubah massal:
    klien luring yang membawa versi lama tetap lolos CAS lalu menimpa hasil
    ubah massal tanpa satu pun 409."""
    async def skenario():
        await dbx.assets.insert_many([
            {"id": "a1", "activity_id": "keg1", "version": 3, "condition": "Baik"},
            {"id": "a2", "activity_id": "keg1", "version": 7, "condition": "Baik"},
        ])
        await dbx.inventory_activities.insert_one({"id": "keg1", "status_pengesahan": "draft"})

        monkeypatch.setattr(rb, "log_audit", _diam, raising=False)
        fn = _unwrap(rb.batch_update_assets)

        class Data:
            asset_ids = ["a1", "a2"]
            updates = {"condition": "Rusak Ringan"}

        await fn(Data(), _Req(), None, None, None, USER)
        a1 = await dbx.assets.find_one({"id": "a1"})
        a2 = await dbx.assets.find_one({"id": "a2"})
        assert a1["condition"] == "Rusak Ringan"
        assert a1["version"] == 4, f"version a1 tak naik: {a1['version']}"
        assert a2["version"] == 8, f"version a2 tak naik: {a2['version']}"
    _jalan(skenario())


# ── B2: idempotensi CREATE permanen lewat dokumen aset ──────────────────────

def test_replay_create_setelah_cache_kedaluwarsa_tidak_membuat_kembar(dbx):
    """Cache respons ber-TTL 24 jam; antrean luring bisa jauh lebih tua.
    Dokumen aset menyimpan idem_key sejak dibuat, jadi replay yang datang
    setelah cache lenyap tetap dikembalikan sebagai aset yang SAMA."""
    async def skenario():
        # Simulasi: percobaan pertama SUDAH menulis aset (ber-idem_key), tetapi
        # respons hilang dan cache idempotency_keys sudah kedaluwarsa (kosong).
        await dbx.assets.insert_one({
            "id": "asli-1", "asset_code": "3100102001", "NUP": "1",
            "asset_name": "Meja", "category": "Dummy", "activity_id": "keg1",
            "version": 1, "idem_key": "kunci-luring-lama",
            "created_at": "2026-07-01T00:00:00+00:00",
            "updated_at": "2026-07-01T00:00:00+00:00",
        })

        fn = _unwrap(ra.create_asset)

        class AsetMasuk:
            # Hanya dipakai bila handler LOLOS dari jalur replay — di uji ini
            # tak boleh sampai ke sana.
            def model_dump(self):
                raise AssertionError("handler tidak boleh membangun dokumen baru")

        # kunci_idem menggabungkan kunci klien + identitas user; pakai fungsi
        # aslinya agar uji tak bergantung pada format internal.
        kunci = ra.kunci_idem("kunci-klien", USER) if hasattr(ra, "kunci_idem") else None
        # Samakan idem_key aset tersimpan dengan kunci efektif yang akan dicari.
        await dbx.assets.update_one({"id": "asli-1"}, {"$set": {"idem_key": kunci}})

        hasil = await fn(AsetMasuk(), _Req(headers={"Idempotency-Key": "kunci-klien"}), USER)
        assert hasil.id == "asli-1", "replay harus mengembalikan aset yang sudah ada"
        assert await dbx.assets.count_documents({}) == 1, "tak boleh lahir kembaran"
    _jalan(skenario())


# ── B4: photo_ops terikat versi ─────────────────────────────────────────────

def test_photo_ops_base_version_beda_ditolak_409(dbx):
    """`keep` adalah indeks POSISIONAL pada array foto. Bila array sudah
    bergeser sejak klien menghitungnya, keep yang sama menunjuk foto yang
    BERBEDA — harus 409, bukan diterapkan diam-diam."""
    async def skenario():
        await dbx.assets.insert_one({
            "id": "a1", "activity_id": "keg1", "version": 5,
            "asset_code": "X", "NUP": "1", "asset_name": "Meja",
            "photos": [], "photo_gridfs_ids": ["g1", "g2"], "photo_thumbnails": ["t1", "t2"],
        })
        fn = _unwrap(ra.patch_asset)
        with pytest.raises(ra.HTTPException) as e:
            await fn("a1", _Req(body={
                "photo_ops": {"keep": [0], "add": [], "thumbnail_index": 0,
                              "base_version": 3},   # dihitung saat versi 3, kini 5
            }), USER)
        assert e.value.status_code == 409
        # Susunan foto TIDAK berubah — penolakan terjadi sebelum menyentuh apa pun.
        a = await dbx.assets.find_one({"id": "a1"})
        assert a["photo_gridfs_ids"] == ["g1", "g2"]
    _jalan(skenario())


def test_photo_ops_base_version_cocok_diterima(dbx, monkeypatch):
    async def skenario():
        await dbx.assets.insert_one({
            "id": "a1", "activity_id": "keg1", "version": 5,
            "asset_code": "X", "NUP": "1", "asset_name": "Meja",
            "category": "Dummy", "created_at": "2026-01-01T00:00:00+00:00",
            "photos": [], "photo_gridfs_ids": ["g1", "g2"], "photo_thumbnails": ["t1", "t2"],
            "thumbnail_index": 0,
        })
        # Notifikasi WebSocket & regenerasi thumbnail — bukan yang diuji.
        monkeypatch.setattr(ra, "notify_asset_change", _diam, raising=False)
        for nama in ("create_thumbnail", "create_gallery_thumbnail"):
            if hasattr(ra, nama):
                monkeypatch.setattr(ra, nama, lambda *_a, **_k: "")
        async def _tanpa_gridfs(*a, **k):
            return None
        for nama in ("read_photo_from_gridfs", "delete_photo_from_gridfs"):
            if hasattr(ra, nama):
                monkeypatch.setattr(ra, nama, _tanpa_gridfs)
        monkeypatch.setattr(ra, "invalidate_asset_cache", lambda *a, **k: None, raising=False)
        monkeypatch.setattr(ra, "jadwalkan_sync", lambda *a, **k: None, raising=False)

        fn = _unwrap(ra.patch_asset)
        await fn("a1", _Req(body={
            "photo_ops": {"keep": [1], "add": [], "thumbnail_index": 0,
                          "base_version": 5},       # cocok dengan versi kini
        }), USER)
        a = await dbx.assets.find_one({"id": "a1"})
        assert a["photo_gridfs_ids"] == ["g2"], "keep [1] harus menyisakan foto kedua"
        assert a["version"] == 6
    _jalan(skenario())


# ── B3: rotasi menstempel updated_at ────────────────────────────────────────

def test_rotasi_menstempel_updated_at(dbx, monkeypatch):
    """Delta sinkron luring memfilter pada updated_at. Rotasi yang hanya
    menaikkan version tak pernah sampai ke cache perangkat lapangan."""
    async def skenario():
        stempel_lama = "2026-01-01T00:00:00+00:00"
        await dbx.assets.insert_one({
            "id": "a1", "activity_id": "keg1", "version": 2,
            "photos": ["data:image/jpeg;base64,QUJD"],  # inline legacy → tanpa GridFS read
            "photo_gridfs_ids": [], "photo_thumbnails": [""],
            "thumbnail_index": 0, "updated_at": stempel_lama,
        })
        # Pekerjaan berat (PIL/GridFS) dipangkas — yang diuji STEMPELNYA.
        monkeypatch.setattr(ra, "rotate_jpeg_bytes", lambda b, d: b)
        async def _gid(*a, **k):
            return "gid-baru"
        monkeypatch.setattr(ra, "store_photo_to_gridfs", _gid)
        for nama in ("generate_photo_thumbnail", "create_thumbnail", "create_gallery_thumbnail"):
            if hasattr(ra, nama):
                monkeypatch.setattr(ra, nama, lambda *_a, **_k: "")
        monkeypatch.setattr(ra, "invalidate_asset_cache", lambda *a, **k: None, raising=False)
        monkeypatch.setattr(ra, "jadwalkan_sync", lambda *a, **k: None, raising=False)

        fn = _unwrap(ra.rotate_asset_photo)
        await fn("a1", 0, _Req(body={"degrees": 90}), USER)
        a = await dbx.assets.find_one({"id": "a1"})
        assert a["version"] == 3
        assert a.get("updated_at") and a["updated_at"] != stempel_lama, (
            "updated_at tak terstempel — rotasi tak akan pernah ikut delta sinkron")
    _jalan(skenario())
