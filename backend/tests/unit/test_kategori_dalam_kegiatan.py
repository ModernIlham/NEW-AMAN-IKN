"""Filter kategori menawarkan yang ADA di kegiatan, bukan seluruh master.

Master kodefikasi BMN berisi belasan ribu entri, sementara satu kegiatan
inventarisasi lazimnya memakai puluhan. Menawarkan seluruh master di kotak
filter berarti menyuruh operator mencari puluhan jarum di tumpukan yang ratusan
kali lebih besar — dan itulah keadaan sebelum perubahan ini.

Daftar "terpakai" diambil dari `db.assets` yang SUDAH ter-scope satker dan
kegiatan, bukan dari `db.categories` (master global tanpa kode satker). Itu
bukan detail rapi-rapi: menyaring master akan salah kandang, dan menyaring
`db.assets` tanpa scope akan membocorkan kategori satker lain — yang dengan
sendirinya membocorkan jenis barang yang mereka kelola.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.assets as ra

USER = {"username": "operator", "role": "admin", "name": "Op", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (ra, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)

    async def _miss(*a, **k):
        return None

    async def _abai(*a, **k):
        return None

    # Cache dimatikan: uji ini menguji kueri, bukan lapisan cache — dan tanpa
    # ini satu uji mewarisi hasil uji sebelumnya lewat TTLCache proses.
    monkeypatch.setattr(ra, "cache_get", _miss, raising=False)
    monkeypatch.setattr(ra, "cache_set", _abai, raising=False)
    return fake


async def _seed(dbx):
    await dbx.inventory_activities.insert_many([
        {"id": "keg1", "nama_kegiatan": "Kegiatan A", "kode_satker": ""},
        {"id": "keg2", "nama_kegiatan": "Kegiatan B", "kode_satker": ""},
    ])
    await dbx.assets.insert_many([
        {"id": "a1", "activity_id": "keg1", "category": "Meja Kerja"},
        {"id": "a2", "activity_id": "keg1", "category": "Kursi Rapat"},
        {"id": "a3", "activity_id": "keg1", "category": "Meja Kerja"},
        {"id": "a4", "activity_id": "keg2", "category": "Kapal Motor"},
        {"id": "a5", "activity_id": "keg1", "category": ""},
        {"id": "a6", "activity_id": "keg1"},
    ])


class TestDaftarTerpakai:
    def test_hanya_kategori_di_kegiatan_itu(self, dbx):
        async def skenario():
            await _seed(dbx)
            r = await _unwrap(ra.get_filter_options)(activity_id="keg1", _user=USER)
            assert r["categories"] == ["Kursi Rapat", "Meja Kerja"], r["categories"]
            assert "Kapal Motor" not in r["categories"], (
                "kategori dari kegiatan lain ikut ditawarkan")
        _jalan(skenario())

    def test_tanpa_duplikat_dan_terurut(self, dbx):
        async def skenario():
            await _seed(dbx)
            r = await _unwrap(ra.get_filter_options)(activity_id="keg1", _user=USER)
            assert r["categories"] == sorted(set(r["categories"]))
        _jalan(skenario())

    def test_kosong_dan_null_dibuang(self, dbx):
        """Aset tanpa kategori tak boleh melahirkan pilihan hampa di dropdown."""
        async def skenario():
            await _seed(dbx)
            r = await _unwrap(ra.get_filter_options)(activity_id="keg1", _user=USER)
            assert all(str(k).strip() for k in r["categories"])
            assert None not in r["categories"]
        _jalan(skenario())

    def test_tanpa_kegiatan_mencakup_semua_yang_terlihat(self, dbx):
        async def skenario():
            await _seed(dbx)
            r = await _unwrap(ra.get_filter_options)(activity_id="", _user=USER)
            assert set(r["categories"]) == {"Meja Kerja", "Kursi Rapat", "Kapal Motor"}
        _jalan(skenario())

    def test_kegiatan_tanpa_aset_memberi_daftar_kosong(self, dbx):
        """Bukan galat — klien memakai daftar kosong sebagai isyarat "tak ada
        informasi pemakaian" lalu jatuh ke master penuh."""
        async def skenario():
            await _seed(dbx)
            await dbx.inventory_activities.insert_one(
                {"id": "keg3", "nama_kegiatan": "Kosong", "kode_satker": ""})
            r = await _unwrap(ra.get_filter_options)(activity_id="keg3", _user=USER)
            assert r["categories"] == []
        _jalan(skenario())


class TestIsolasiSatker:
    def test_kategori_satker_lain_tidak_bocor(self, dbx):
        """Daftar kategori yang dipakai satu satker menyingkapkan jenis barang
        yang mereka kelola. Ia harus mengikuti scope yang sama dengan asetnya."""
        async def skenario():
            await dbx.inventory_activities.insert_many([
                {"id": "kegA", "nama_kegiatan": "A", "kode_satker": "111111"},
                {"id": "kegB", "nama_kegiatan": "B", "kode_satker": "999999"},
            ])
            await dbx.assets.insert_many([
                {"id": "x1", "activity_id": "kegA", "category": "Meja Kerja"},
                {"id": "x2", "activity_id": "kegB", "category": "Kapal Motor"},
            ])
            r = await _unwrap(ra.get_filter_options)(
                activity_id="", _user={**USER, "role": "operator",
                                       "kode_satker": "111111"})
            assert r["categories"] == ["Meja Kerja"], r["categories"]
        _jalan(skenario())


class TestKunciResponsDipakai:
    def test_kunci_categories_ada_di_respons(self, dbx):
        """Respons ini pernah memuat kunci yang tak pernah dikonsumsi klien
        (`inventory_statuses`). Kunci baru harus benar-benar sampai."""
        async def skenario():
            await _seed(dbx)
            r = await _unwrap(ra.get_filter_options)(activity_id="keg1", _user=USER)
            assert "categories" in r
        _jalan(skenario())

    def test_klien_membaca_kunci_itu(self):
        """Anti-drift lintas bahasa: nama kunci di server dan yang dibaca klien
        harus sama persis. Salah satu huruf, dan filternya diam-diam kembali
        menawarkan seluruh master tanpa satu pun galat."""
        import os
        akar = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        with open(os.path.join(akar, "frontend", "src", "components", "assets",
                               "DashboardToolbar.jsx"), encoding="utf-8") as f:
            toolbar = f.read()
        assert "filterOptions?.categories" in toolbar, (
            "klien tak membaca `categories` dari filter-options")
