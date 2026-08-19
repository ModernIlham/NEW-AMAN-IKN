"""Kartu ringkasan menjawab pertanyaan yang SAMA dengan daftar di bawahnya.

Laporan pemilik: memasang filter lanjutan menyaring daftar asetnya, tetapi
"Total Aset / Total Nilai / Aktif / Maintenance" di atasnya tidak bergerak
sedikit pun. Sebabnya bukan efek yang lupa dipicu — statistiknya memang
dimuat ulang — melainkan `GET /assets/stats` yang hanya MENERIMA tiga
parameter (cari, kategori, kegiatan) dan merakit kuerinya sendiri, terpisah
dari builder yang dipakai daftar.

Itu kegagalan yang paling sulit dicurigai: dua angka untuk satu layar, dan
yang lebih besar tampak lebih meyakinkan.

Yang dijaga di sini:
  1. Kedua endpoint menerima daftar parameter filter yang SAMA — supaya filter
     ke-19 tidak lahir hanya di salah satunya.
  2. Angkanya benar-benar mengikuti filter, dan `total_assets` selalu sama
     dengan jumlah baris yang dikembalikan daftar untuk filter yang sama.
  3. Kunci cache mengikuti seluruh isi kueri. Kunci lama (`satker|kegiatan|
     cari|kategori`) akan membuat dua filter berbeda berbagi satu entri, dan
     selama satu menit angka filter sebelumnya disajikan sebagai angka filter
     yang baru — salah, tapi tampak wajar.
"""
import asyncio
import inspect

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.assets as ra

USER = {"username": "operator", "role": "admin", "name": "Operator",
        "kode_satker": ""}

# Parameter yang memang hanya milik DAFTAR (bentuk halaman & urutan) — tak ada
# artinya bagi angka agregat.
KHUSUS_DAFTAR = {"sort_by", "page", "page_size"}


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


def _param(fn):
    return {n for n in inspect.signature(_unwrap(fn)).parameters if not n.startswith("_")}


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (ra, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    # Cache dimatikan: uji ini menguji KUERI, bukan lapisan cache. Tanpa ini
    # satu uji mewarisi angka milik uji sebelumnya lewat TTLCache proses.
    async def _miss(*a, **k):
        return None

    async def _abai(*a, **k):
        return None

    monkeypatch.setattr(ra, "cache_get", _miss, raising=False)
    monkeypatch.setattr(ra, "cache_set", _abai, raising=False)
    return fake


async def _seed(dbx):
    await dbx.inventory_activities.insert_one(
        {"id": "keg1", "nama_kegiatan": "Inventarisasi", "kode_satker": ""})
    await dbx.assets.insert_many([
        {"id": "a1", "activity_id": "keg1", "asset_name": "Printer",
         "category": "Peralatan", "condition": "Baik", "status": "Aktif",
         "location": "Gedung A", "purchase_price": 1_000_000},
        {"id": "a2", "activity_id": "keg1", "asset_name": "Kursi",
         "category": "Peralatan", "condition": "Rusak Berat", "status": "Maintenance",
         "location": "Gedung A", "purchase_price": 500_000},
        {"id": "a3", "activity_id": "keg1", "asset_name": "Meja",
         "category": "Mebel", "condition": "Rusak Berat", "status": "Aktif",
         "location": "Gedung B", "purchase_price": 250_000},
    ])


class TestParameterTidakBolehBerbeda:
    """Akar cacatnya bukan satu filter yang terlewat, melainkan dua daftar
    parameter yang boleh berbeda tanpa ada yang menagih."""

    def test_stats_menerima_semua_filter_milik_daftar(self):
        kurang = _param(ra.get_assets) - _param(ra.get_assets_stats) - KHUSUS_DAFTAR
        assert kurang == set(), (
            f"GET /assets/stats tidak menerima filter: {sorted(kurang)} — "
            "kartu ringkasan akan mengabaikannya diam-diam")

    def test_stats_tidak_menerima_filter_asing(self):
        lebih = _param(ra.get_assets_stats) - _param(ra.get_assets)
        assert lebih == set(), f"parameter hanya ada di /stats: {sorted(lebih)}"

    def test_keduanya_merakit_kueri_lewat_jalur_yang_sama(self):
        """Kalau salah satu kembali merakit kuerinya sendiri, kesamaan daftar
        parameter di atas tak lagi menjamin kesamaan hasil."""
        for fn in (ra.get_assets, ra.get_assets_stats):
            sumber = inspect.getsource(_unwrap(fn))
            assert "await kueri_aset_terlihat(" in sumber, fn.__name__
            assert "build_asset_search_query(" not in sumber, (
                f"{fn.__name__} merakit kueri sendiri lagi")


class _Kursor:
    """Kursor agregasi tiruan — mongomock belum mengenal `$convert` yang dipakai
    penjumlahan nilai perolehan, sehingga pipeline aslinya tak bisa dijalankan
    di sini. Yang diuji justru bagian yang dulu salah: `$match` apa yang masuk
    ke pipeline itu."""

    def __init__(self, hasil):
        self._hasil = hasil

    async def to_list(self, _n):
        return self._hasil


def _tangkap_match(dbx, monkeypatch):
    """Rekam `$match` yang dikirim endpoint statistik ke agregasi.

    Ditambal di tingkat KELAS, bukan pada objek koleksi: `db.assets` di
    mongomock membuat objek baru setiap kali diakses, sehingga menambal satu
    instans tak berpengaruh pada akses berikutnya (dan uji akan lulus/gagal
    karena alasan yang salah).

    Pipeline DAFTAR tetap dijalankan asli — hanya pipeline statistik yang
    dicegat, dikenali dari agregat `total_value` miliknya.
    """
    tercatat = []
    asli = type(dbx.assets).aggregate

    def _agregasi(self, pipeline, *a, **k):
        if any("total_value" in str(tahap) for tahap in pipeline):
            tercatat.append(pipeline)
            return _Kursor([])
        return asli(self, pipeline, *a, **k)

    monkeypatch.setattr(type(dbx.assets), "aggregate", _agregasi, raising=False)
    return tercatat


class TestAngkaMengikutiFilter:
    """Bukti tingkat-kueri: `$match` yang dipakai statistik memilih baris yang
    sama persis dengan daftar. Sebelum perbaikan, `$match`-nya hanya memuat
    activity_id — filter lanjutan tak pernah sampai ke sana."""

    def test_filter_kondisi_masuk_ke_match(self, dbx, monkeypatch):
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(
                activity_id="keg1", condition=["Rusak Berat"], _user=USER)
            cocok = jejak[0][0]["$match"]
            assert cocok.get("condition") == "Rusak Berat", (
                f"filter kondisi tak sampai ke agregasi: {cocok}")
            assert await dbx.assets.count_documents(cocok) == 2
        _jalan(skenario())

    def test_beberapa_filter_beririsan(self, dbx, monkeypatch):
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(
                activity_id="keg1", condition=["Rusak Berat"],
                location=["Gedung A"], _user=USER)
            assert await dbx.assets.count_documents(jejak[0][0]["$match"]) == 1
        _jalan(skenario())

    def test_rentang_harga_masuk_ke_match(self, dbx, monkeypatch):
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(
                activity_id="keg1", price_min=400_000, _user=USER)
            assert "$expr" in jejak[0][0]["$match"], "rentang harga hilang"
        _jalan(skenario())

    def test_tanpa_filter_tetap_seluruh_kegiatan(self, dbx, monkeypatch):
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(activity_id="keg1", _user=USER)
            assert await dbx.assets.count_documents(jejak[0][0]["$match"]) == 3
        _jalan(skenario())

    # Rentang harga sengaja TIDAK ada di daftar ini: klausanya memakai `$expr`
    # + `$convert`, dan mongomock tak mengenal `$convert` sehingga
    # `count_documents` atasnya meledak. Kesamaannya tetap dibuktikan oleh
    # `test_match_statistik_identik_dengan_kueri_daftar` di bawah, yang
    # membandingkan kueri — bukan menghitung baris.
    @pytest.mark.parametrize("filter_uji", [
        {"condition": ["Rusak Berat"]},
        {"status": ["Aktif"]},
        {"location": ["Gedung A"]},
        {"category": "Mebel"},
        {"condition": ["Baik"], "status": ["Aktif"]},
        {"condition": ["Baik", "Rusak Berat"], "location": ["Gedung A"]},
    ])
    def test_cakupan_statistik_sama_dengan_daftar(self, dbx, monkeypatch, filter_uji):
        """Invarian sesungguhnya. Angka apa pun yang berbeda dari daftar di
        bawahnya adalah salah, tak peduli mana yang tampak 'lebih benar'."""
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(
                activity_id="keg1", _user=USER, **filter_uji)
            n_statistik = await dbx.assets.count_documents(jejak[0][0]["$match"])
            d = await _unwrap(ra.get_assets)(
                activity_id="keg1", _user=USER, **filter_uji)
            assert n_statistik == d["total"], (
                f"{filter_uji}: kartu menghitung {n_statistik}, "
                f"daftar menghitung {d['total']}")
        _jalan(skenario())


    @pytest.mark.parametrize("filter_uji", [
        {"condition": ["Rusak Berat"]},
        {"location": ["Gedung A"]},
        {"price_min": 400_000, "price_max": 900_000},
        {"beli_dari": "2026-01-01", "beli_sampai": "2026-12-31"},
        {"nomor_spm": "SPM-9", "user_filter": "Budi", "pengguna_nip": "1990"},
        {"stiker_status": ["Sudah"], "inventory_status": ["Ditemukan"]},
        {"eselon1_filter": ["Setjen"], "eselon2_filter": ["Biro Umum"]},
        {"search": "printer"},
    ])
    def test_match_statistik_identik_dengan_kueri_daftar(self, dbx, monkeypatch, filter_uji):
        """Perbandingan KUERI, bukan jumlah baris — sehingga filter yang tak
        bisa dihitung mongomock (harga, tanggal) tetap ikut terjaga.

        Dibandingkan lewat sidik `kunci_cache_kueri` karena nilai kueri memuat
        regex terkompilasi: dua regex dengan pola sama TIDAK sama menurut `==`,
        jadi perbandingan dict biasa akan gagal untuk alasan yang keliru.
        """
        async def skenario():
            await _seed(dbx)
            jejak = _tangkap_match(dbx, monkeypatch)
            await _unwrap(ra.get_assets_stats)(
                activity_id="keg1", _user=USER, **filter_uji)
            harapan = await ra.kueri_aset_terlihat(
                USER, activity_id="keg1", **filter_uji)
            assert (ra.kunci_cache_kueri(USER, jejak[0][0]["$match"])
                    == ra.kunci_cache_kueri(USER, harapan)), (
                f"{filter_uji}: kueri statistik berbeda dari kueri daftar\n"
                f"statistik: {jejak[0][0]['$match']}\nharapan  : {harapan}")
        _jalan(skenario())


class TestKunciCacheIkutSeluruhKueri:
    def test_filter_berbeda_menghasilkan_kunci_berbeda(self):
        a = ra.kunci_cache_kueri(USER, {"activity_id": "keg1", "condition": "Baik"})
        b = ra.kunci_cache_kueri(USER, {"activity_id": "keg1", "condition": "Rusak Berat"})
        assert a != b, (
            "dua filter berbagi satu entri cache — selama satu menit angka "
            "filter sebelumnya disajikan sebagai angka filter yang baru")

    def test_kueri_sama_menghasilkan_kunci_sama(self):
        a = ra.kunci_cache_kueri(USER, {"activity_id": "keg1", "status": "Aktif"})
        b = ra.kunci_cache_kueri(USER, {"activity_id": "keg1", "status": "Aktif"})
        assert a == b

    def test_urutan_penyisipan_tidak_mengubah_kunci(self):
        a = ra.kunci_cache_kueri(USER, {"activity_id": "keg1", "status": "Aktif"})
        b = ra.kunci_cache_kueri(USER, {"status": "Aktif", "activity_id": "keg1"})
        assert a == b, "kunci ikut berubah karena urutan — cache-nya jadi mubazir"

    def test_satker_berbeda_tidak_berbagi_kunci(self):
        q = {"activity_id": "keg1"}
        a = ra.kunci_cache_kueri({**USER, "kode_satker": "111111"}, q)
        b = ra.kunci_cache_kueri({**USER, "kode_satker": "999999"}, q)
        assert a != b, "cache statistik bocor antar-satker"
