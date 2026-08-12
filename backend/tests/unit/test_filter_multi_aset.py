"""Unit: filter aset MULTI-NILAI — satu filter boleh memilih banyak nilai.

Yang dijaga di sini:
  1. Nilai TUNGGAL menghasilkan klausa yang PERSIS SAMA dengan sebelum fitur
     ini ada (bukan `$in` beranggota satu) — permintaan lama & rencana indeks
     tak berubah.
  2. Daftar KOSONG = tanpa filter, bukan "tidak cocok apa pun".
  3. Bentuk `$in` di tingkat FIELD, sehingga tak pernah menabrak `$and`/`$or`
     milik pencarian teks bebas maupun `$expr` rentang harga.
  4. Jalur nyata Mongo: banyak nilai = gabungan (ATAU) di dalam satu filter,
     tetapi irisan (DAN) antar-filter.
  5. Ringkasan filter di laporan menyebut SELURUH nilai, bukan yang pertama.
"""
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

from routes.assets import (build_asset_search_query, klausa_persis,
                           klausa_substring, nilai_filter)


def _jalan(coro):
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestNormalisasiNilai:
    def test_terima_str_maupun_daftar(self):
        assert nilai_filter("Baik") == ["Baik"]
        assert nilai_filter(["Baik", "Rusak"]) == ["Baik", "Rusak"]

    def test_buang_kosong_spasi_dan_duplikat(self):
        assert nilai_filter([" Aktif ", "Aktif", "", "   ", None]) == ["Aktif"]
        assert nilai_filter(None) == []
        assert nilai_filter([]) == []

    def test_urutan_dipertahankan(self):
        assert nilai_filter(["C", "A", "B"]) == ["C", "A", "B"]

    def test_sentinel_query_fastapi_diabaikan(self):
        """`filter_laporan` juga dipanggil sebagai fungsi Python biasa; di
        jalur itu parameter kosong bernilai objek `Query(default=[])`, bukan
        daftar. Tanpa penyaringan, sentinel itu jadi 'filter' teks sampah."""
        from fastapi import Query
        assert nilai_filter(Query(default=[])) == []
        assert nilai_filter([Query(default=[])]) == []
        # Objek lain yang bukan skalar teks/angka pun diabaikan.
        assert nilai_filter([object()]) == []


class TestBentukKlausa:
    def test_persis_tunggal_sama_seperti_dulu(self):
        # BUKAN {"$in": ["Baik"]} — bentuk lama dipertahankan persis.
        assert klausa_persis("Baik") == "Baik"
        assert klausa_persis(["Baik"]) == "Baik"

    def test_persis_banyak_pakai_in(self):
        assert klausa_persis(["Baik", "Rusak"]) == {"$in": ["Baik", "Rusak"]}

    def test_substring_tunggal_sama_seperti_dulu(self):
        assert klausa_substring("Gudang") == {"$regex": re.escape("Gudang"),
                                              "$options": "i"}

    def test_substring_banyak_pakai_regex_terkompilasi(self):
        # Dict {"$regex": ...} di dalam $in diperlakukan Mongo sebagai dokumen
        # literal dan TAK PERNAH cocok — karenanya wajib regex terkompilasi.
        k = klausa_substring(["Gedung A", "Gudang"])
        assert set(k) == {"$in"}
        assert all(isinstance(r, re.Pattern) for r in k["$in"])
        assert [r.pattern for r in k["$in"]] == [re.escape("Gedung A"),
                                                 re.escape("Gudang")]
        assert all(r.flags & re.IGNORECASE for r in k["$in"])

    def test_kosong_berarti_tanpa_filter(self):
        assert klausa_persis([]) is None
        assert klausa_persis("") is None
        assert klausa_substring([]) is None


class TestPembangunQuery:
    def test_tujuh_filter_menerima_banyak_nilai(self):
        q = build_asset_search_query(
            condition=["Baik", "Rusak Ringan"], status=["Aktif", "Dihentikan"],
            stiker_status=["Sudah", "Belum"],
            inventory_status=["Ditemukan", "Sengketa"],
            location=["Gedung A", "Gudang"], eselon1_filter=["Setjen", "Itjen"],
            eselon2_filter=["Biro Umum", "Biro SDM"])
        assert q["condition"] == {"$in": ["Baik", "Rusak Ringan"]}
        assert q["status"] == {"$in": ["Aktif", "Dihentikan"]}
        assert q["stiker_status"] == {"$in": ["Sudah", "Belum"]}
        assert q["inventory_status"] == {"$in": ["Ditemukan", "Sengketa"]}
        for f in ("location", "eselon1", "eselon2"):
            assert set(q[f]) == {"$in"} and len(q[f]["$in"]) == 2

    def test_nilai_tunggal_tak_mengubah_query_lama(self):
        assert build_asset_search_query(condition="Baik") == \
            build_asset_search_query(condition=["Baik"]) == {"condition": "Baik"}

    def test_daftar_kosong_tak_menambah_kunci(self):
        q = build_asset_search_query(condition=[], status=[], location=[])
        assert q == {}

    def test_koma_di_nilai_tetap_satu_nilai(self):
        # Alasan kontrak kawat memakai parameter BERULANG, bukan pemisah koma.
        q = build_asset_search_query(location=["Gedung A, Lantai 2"])
        assert q["location"]["$regex"] == re.escape("Gedung A, Lantai 2")

    def test_tak_menabrak_pencarian_teks_bebas(self):
        # Pencarian multi-kata memakai $and di tingkat atas; filter multi harus
        # tetap berupa klausa per-FIELD agar keduanya hidup berdampingan.
        q = build_asset_search_query(search="meja kayu",
                                     status=["Aktif", "Rusak"])
        assert "$and" in q
        assert q["status"] == {"$in": ["Aktif", "Rusak"]}

    def test_tak_menabrak_rentang_harga(self):
        q = build_asset_search_query(price_min=1000.0, price_max=5000.0,
                                     condition=["Baik", "Rusak Berat"])
        assert "$expr" in q
        assert q["condition"] == {"$in": ["Baik", "Rusak Berat"]}

    def test_regex_diescape_pada_jalur_banyak_nilai(self):
        q = build_asset_search_query(location=["(a+)+", "["])
        assert [r.pattern for r in q["location"]["$in"]] == \
            [re.escape("(a+)+"), re.escape("[")]


class TestJalurMongoNyata:
    """Query yang dibangun benar-benar menyaring seperti yang dijanjikan."""

    def _seed(self, db):
        return db.assets.insert_many([
            {"id": "a1", "condition": "Baik", "status": "Aktif",
             "location": "Gedung A Lantai 2"},
            {"id": "a2", "condition": "Rusak Ringan", "status": "Aktif",
             "location": "Gudang Pusat"},
            {"id": "a3", "condition": "Rusak Berat", "status": "Dihentikan",
             "location": "Gedung B"},
        ])

    def test_banyak_nilai_menggabung_dalam_satu_filter(self):
        async def skenario():
            db = AsyncMongoMockClient()["uji"]
            await self._seed(db)
            q = build_asset_search_query(condition=["Baik", "Rusak Berat"])
            ada = [d["id"] async for d in db.assets.find(q, {"_id": 0, "id": 1})]
            assert sorted(ada) == ["a1", "a3"]
        _jalan(skenario())

    def test_substring_banyak_nilai_benar_benar_cocok(self):
        async def skenario():
            db = AsyncMongoMockClient()["uji"]
            await self._seed(db)
            q = build_asset_search_query(location=["gedung a", "gudang"])
            ada = [d["id"] async for d in db.assets.find(q, {"_id": 0, "id": 1})]
            assert sorted(ada) == ["a1", "a2"]
        _jalan(skenario())

    def test_antar_filter_tetap_irisan(self):
        async def skenario():
            db = AsyncMongoMockClient()["uji"]
            await self._seed(db)
            # (Baik ATAU Rusak Berat) DAN status Aktif → hanya a1.
            q = build_asset_search_query(
                condition=["Baik", "Rusak Berat"], status=["Aktif"])
            ada = [d["id"] async for d in db.assets.find(q, {"_id": 0, "id": 1})]
            assert ada == ["a1"]
        _jalan(skenario())

    def test_tanpa_filter_mengembalikan_semua(self):
        async def skenario():
            db = AsyncMongoMockClient()["uji"]
            await self._seed(db)
            q = build_asset_search_query(condition=[], status=[])
            ada = [d["id"] async for d in db.assets.find(q, {"_id": 0, "id": 1})]
            assert sorted(ada) == ["a1", "a2", "a3"]
        _jalan(skenario())


class TestRingkasanLaporan:
    """Laporan mencetak ringkasan filter; kalau hanya nilai pertama yang
    disebut, pembaca menyimpulkan dokumennya lebih sempit dari isinya."""

    def test_ringkasan_menyebut_semua_nilai(self):
        from routes.reports import filter_laporan_dari_map
        f = filter_laporan_dari_map({
            "condition": ["Rusak Berat", "Rusak Ringan"],
            "status": "Aktif"})
        assert "Kondisi: Rusak Berat, Rusak Ringan" in f.ringkasan
        assert "Status: Aktif" in f.ringkasan
        assert f.aktif is True

    def test_query_laporan_ikut_multi(self):
        from routes.reports import filter_laporan_dari_map
        f = filter_laporan_dari_map({"status": ["Aktif", "Dihentikan"]})
        assert f.query["status"] == {"$in": ["Aktif", "Dihentikan"]}

    def test_tanpa_filter_tetap_kosong(self):
        from routes.reports import filter_laporan_dari_map
        f = filter_laporan_dari_map({"condition": [], "status": ""})
        assert f.query == {} and f.ringkasan == "" and f.aktif is False


class TestPilihSemuaHalamanSatuBuilder:
    """`/assets/all-ids` dulu punya pembangun query DUPLIKAT yang sudah drift:
    eselon1 dicocokkan persis (di daftar: substring) dan filter harga/tanggal/
    SPM/pengguna tak ada sama sekali — sehingga "Pilih semua N aset" menandai
    himpunan yang BERBEDA dari yang tampil di layar."""

    def test_endpoint_memakai_builder_bersama(self):
        import inspect

        import routes.batch as rb
        sumber = inspect.getsource(rb.get_all_asset_ids)
        assert "build_asset_search_query" in sumber, \
            "all-ids harus memakai builder bersama, bukan query sendiri"

    @pytest.mark.parametrize("param", [
        "price_min", "price_max", "nomor_spm", "perolehan_dari",
        "user_filter", "pengguna_nip", "beli_dari", "beli_sampai",
    ])
    def test_filter_yang_dulu_hilang_kini_diterima(self, param):
        import inspect

        import routes.batch as rb
        assert param in inspect.signature(rb.get_all_asset_ids).parameters


class TestEksporBerkasIkutFilter:
    """Empat ekspor BERKAS (CSV, PDF, XLSX sinkron, XLSX job latar) dulu hanya
    menerima `activity_id`: menyaring layar lalu menekan Ekspor tetap
    menghasilkan berkas berisi SELURUH aset kegiatan. Berkasnya sah, hanya
    isinya jauh lebih luas dari yang diminta — kegagalan senyap."""

    @pytest.mark.parametrize("nama", [
        "export_csv", "export_pdf", "export_xlsx", "export_xlsx_async"])
    def test_keempat_ekspor_menerima_filter(self, nama):
        import inspect

        import routes.exports as re_
        params = inspect.signature(getattr(re_, nama)).parameters
        assert "filter_aset" in params, f"{nama} tak menerima filter"

    def test_dependency_memakai_builder_bersama(self):
        import inspect

        import routes.exports as re_
        sumber = inspect.getsource(re_.filter_aset_ekspor)
        assert "build_asset_search_query" in sumber

    def test_dependency_multi_nilai_jadi_in(self):
        from routes.exports import filter_aset_ekspor
        q = filter_aset_ekspor(condition=["Baik", "Rusak Berat"])
        assert q["condition"] == {"$in": ["Baik", "Rusak Berat"]}

    def test_dependency_tanpa_filter_kosong(self):
        from routes.exports import filter_aset_ekspor
        assert filter_aset_ekspor() == {}

    def test_kegiatan_disisipkan_di_atas_filter(self):
        from routes.exports import _query_ekspor
        q = _query_ekspor({"condition": "Baik"}, "keg-1")
        assert q == {"condition": "Baik", "activity_id": "keg-1"}
        # Tanpa kegiatan (ekspor lintas-kegiatan) kuncinya tak muncul.
        assert _query_ekspor({"condition": "Baik"}, None) == {"condition": "Baik"}

    def test_filter_asal_tak_dimutasi(self):
        from routes.exports import _query_ekspor
        asal = {"condition": "Baik"}
        _query_ekspor(asal, "keg-1")
        assert asal == {"condition": "Baik"}
