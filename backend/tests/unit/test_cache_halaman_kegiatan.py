"""Halaman Pilih Kegiatan tidak lagi mengagregasi seluruh aset satker tiap dibuka.

Audit performa 26 Nov 2026: `/inventory-activities` (jumlah & nilai aset per
kegiatan) dan `/inventarisasi/aset-lintas-kegiatan` ($group atas SELURUH aset
satker) dihitung ulang di setiap pembukaan halaman. Kini hasilnya di-cache
per lingkup satker dan DIBERSIHKAN setiap tulis aset (`invalidate_asset_cache`).
"""
import asyncio
import inspect

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.activities as ra
import routes.timeline as rt
import shared_utils as su

USER_A = {"id": "ua", "username": "a", "role": "admin", "kode_satker": "A"}
USER_B = {"id": "ub", "username": "b", "role": "admin", "kode_satker": "B"}


@pytest.fixture
def database(monkeypatch):
    fake = AsyncMongoMockClient()["cache_kegiatan"]
    for mod in (ra, rt, su):
        monkeypatch.setattr(mod, "db", fake)
    # mongomock tak mendukung `$trim` di ekspresi harga resmi; yang diuji di
    # sini cache-nya, bukan penguraian harga (punya ujinya sendiri).
    monkeypatch.setattr(ra, "ekspresi_harga", lambda: {"$ifNull": ["$purchase_price", 0]})
    su.invalidate_asset_cache()
    yield fake
    su.invalidate_asset_cache()


def _aset(i, keg, kode="3100102001", nup=None):
    return {"id": f"{keg}-{i}", "activity_id": keg, "asset_code": kode, "NUP": str(nup or i),
            "asset_name": f"Aset {i}", "purchase_price": 1000, "inventory_status": "Ditemukan",
            "condition": "Baik", "updated_at": "2026-11-01T00:00:00+00:00"}


async def seed(db):
    await db.inventory_activities.insert_many([
        {"id": "k1", "kode_satker": "A", "name": "Kegiatan 1", "ticket_number": "T1",
         "created_at": "2026-11-01"},
        {"id": "k2", "kode_satker": "A", "name": "Kegiatan 2", "ticket_number": "T2",
         "created_at": "2026-11-02"},
        {"id": "kb", "kode_satker": "B", "name": "Kegiatan B", "ticket_number": "TB",
         "created_at": "2026-11-03"},
    ])
    await db.assets.insert_many([_aset(1, "k1"), _aset(2, "k1"), _aset(1, "k2", nup=5),
                                 _aset(9, "kb", kode="9999999999", nup=1),
                                 _aset(8, "kb", kode="9999999999", nup=1)])


def _jumlah(daftar):
    return {a["id"]: a["total_assets"] for a in daftar}


def test_daftar_kegiatan_angka_di_cache_dan_dibersihkan_tulis_aset(database):
    async def run():
        await seed(database)
        assert _jumlah(await ra.get_inventory_activities(_user=USER_A)) == {"k1": 2, "k2": 1}
        await database.assets.insert_one(_aset(3, "k1"))
        # Tanpa invalidasi: angka dari cache (bukti agregasi tak diulang).
        assert _jumlah(await ra.get_inventory_activities(_user=USER_A))["k1"] == 2
        su.invalidate_asset_cache()   # dipanggil setiap jalur tulis aset
        assert _jumlah(await ra.get_inventory_activities(_user=USER_A))["k1"] == 3
    asyncio.run(run())


def test_kegiatan_baru_langsung_muncul_walau_angka_di_cache(database):
    async def run():
        await seed(database)
        await ra.get_inventory_activities(_user=USER_A)
        await database.inventory_activities.insert_one(
            {"id": "k3", "kode_satker": "A", "name": "Baru", "ticket_number": "T3",
             "created_at": "2026-11-05"})
        hasil = await ra.get_inventory_activities(_user=USER_A)
        assert _jumlah(hasil) == {"k1": 2, "k2": 1, "k3": 0}
    asyncio.run(run())


def test_nilai_tetap_berformat_sama_dari_cache(database):
    async def run():
        await seed(database)
        pertama = await ra.get_inventory_activities(_user=USER_A)
        kedua = await ra.get_inventory_activities(_user=USER_A)
        pilih = lambda d: [(a["id"], a["total_value"], a["total_value_exact"]) for a in d]
        assert pilih(pertama) == pilih(kedua)
    asyncio.run(run())


def test_aset_lintas_kegiatan_di_cache_per_satker(database):
    async def run():
        await seed(database)
        # Satker A: tak ada barang yang sama di dua kegiatan.
        assert (await rt.aset_lintas_kegiatan(user=USER_A))["jumlah"] == 0
        # Satker B: dua dokumen satu identitas tetapi SATU kegiatan → bukan lintas.
        assert (await rt.aset_lintas_kegiatan(user=USER_B))["jumlah"] == 0
        await database.assets.insert_one(_aset(1, "k2", nup=1) | {"id": "k2-dup"})
        assert (await rt.aset_lintas_kegiatan(user=USER_A))["jumlah"] == 0   # cache
        su.invalidate_asset_cache()
        hasil = await rt.aset_lintas_kegiatan(user=USER_A)
        assert hasil["jumlah"] == 1
        # Cache satker A tak pernah tersaji ke satker B.
        assert (await rt.aset_lintas_kegiatan(user=USER_B))["jumlah"] == 0
    asyncio.run(run())


def test_kunci_cache_memisahkan_satker_dan_query():
    k1 = su.kunci_cache_dari_kueri(USER_A, {"activity_id": {"$in": ["k1"]}})
    assert k1 != su.kunci_cache_dari_kueri(USER_B, {"activity_id": {"$in": ["k1"]}})
    assert k1 != su.kunci_cache_dari_kueri(USER_A, {"activity_id": {"$in": ["k2"]}})
    assert k1 == su.kunci_cache_dari_kueri(USER_A, {"activity_id": {"$in": ["k1"]}})


def test_namespace_kegiatan_ikut_dibersihkan_invalidasi_aset():
    src = inspect.getsource(su.invalidate_asset_cache)
    assert "_cache_kegiatan.clear()" in src and '"kegiatan"' in src
    assert su._CACHE_TTL["kegiatan"] <= 300


def test_gzip_level_6_bukan_bawaan_9():
    import server
    gz = [m for m in server.app.user_middleware if m.cls.__name__ == "GZipMiddleware"]
    assert gz and gz[0].kwargs.get("compresslevel") == 6
