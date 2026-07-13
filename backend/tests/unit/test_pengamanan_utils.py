"""Test logika murni pengamanan (pengamanan_utils.py) — tanpa Mongo."""
from pengamanan_utils import (
    JENIS_KEKURANGAN, ada_foto, is_sengketa, kekurangan_aset, rekap_kesehatan,
)


def _lengkap():
    return {"id": "a1", "asset_code": "3010101001", "NUP": "1",
            "asset_name": "Laptop", "kode_register": "ab12" * 8,
            "location": "Lt. 2", "user": "Budi", "bast_file_id": "f1",
            "photo_gridfs_ids": ["g1"], "inventory_status": "Ditemukan"}


class TestKekurangan:
    def test_aset_lengkap_tanpa_kekurangan(self):
        assert kekurangan_aset(_lengkap()) == []

    def test_semua_kekurangan_terdeteksi(self):
        kosong = {"photos": [], "photo_gridfs_ids": []}
        assert kekurangan_aset(kosong) == ["foto", "register", "lokasi", "pengguna", "bast"]

    def test_foto_inline_legacy_dihitung(self):
        a = {**_lengkap(), "photo_gridfs_ids": [], "photos": ["data:image/..."]}
        assert ada_foto(a) is True
        assert "foto" not in kekurangan_aset(a)

    def test_label_kekurangan_lengkap(self):
        assert set(JENIS_KEKURANGAN) == {"foto", "register", "lokasi", "pengguna", "bast"}
        assert all(JENIS_KEKURANGAN[k] for k in JENIS_KEKURANGAN)


class TestSengketa:
    def test_status_sengketa(self):
        assert is_sengketa({"inventory_status": "Sengketa"}) is True

    def test_nomor_perkara_atau_pihak(self):
        assert is_sengketa({"nomor_perkara": "12/PDT/2026"}) is True
        assert is_sengketa({"pihak_bersengketa": "PT X"}) is True
        assert is_sengketa({"inventory_status": "Ditemukan"}) is False


class TestRekap:
    def test_rekap_gabungan(self):
        assets = [
            _lengkap(),
            {"id": "a2", "asset_name": "Kursi", "photos": [], "photo_gridfs_ids": [],
             "location": "Gudang", "inventory_status": "Ditemukan"},
            {"id": "a3", "asset_name": "Tanah", "kode_register": "x", "location": "Kav B",
             "user": "Rina", "bast_file_id": "f", "photo_gridfs_ids": ["g"],
             "inventory_status": "Sengketa", "nomor_perkara": "12/PDT/2026",
             "pihak_bersengketa": "PT X", "keterangan_sengketa": "Batas lahan"},
        ]
        per, lengkap, sengketa = rekap_kesehatan(assets)
        assert lengkap == 2                      # a1 dan a3 lengkap datanya
        assert per["foto"] == 1 and per["register"] == 1
        assert per["pengguna"] == 1 and per["bast"] == 1
        assert per["lokasi"] == 0
        assert len(sengketa) == 1
        assert sengketa[0]["nomor_perkara"] == "12/PDT/2026"

    def test_kosong(self):
        per, lengkap, sengketa = rekap_kesehatan([])
        assert lengkap == 0 and sengketa == []
        assert all(v == 0 for v in per.values())


class TestRegisterKasus:
    def test_validasi_kasus(self):
        from pengamanan_utils import validate_kasus
        ok = {"kategori": "dikuasai_pihak_lain", "uraian": "Tanah diokupasi",
              "pihak_lawan": "Warga sekitar"}
        assert validate_kasus(ok) == []
        errors = validate_kasus({"kategori": "aneh", "uraian": " ",
                                 "pihak_lawan": ""})
        assert len(errors) == 3

    def test_transisi_kasus(self):
        from pengamanan_utils import validate_transisi_kasus
        assert validate_transisi_kasus({"status": "identifikasi"}, "litigasi") == []
        assert validate_transisi_kasus({"status": "mediasi"}, "selesai") == []
        # Mundur / dari terminal / status asing → ditolak
        assert validate_transisi_kasus({"status": "litigasi"}, "mediasi")
        assert validate_transisi_kasus({"status": "selesai"}, "litigasi")
        assert validate_transisi_kasus({"status": "identifikasi"}, "banding")

    def test_rekap_kasus(self):
        from pengamanan_utils import rekap_kasus
        items = [
            {"status": "identifikasi", "kategori": "dikuasai_pihak_lain"},
            {"status": "litigasi", "kategori": "berperkara"},
            {"status": "selesai", "kategori": "berperkara"},
        ]
        r = rekap_kasus(items)
        assert r["jumlah"] == 3 and r["aktif"] == 2
        assert r["per_status"]["selesai"] == 1
        assert r["per_kategori"]["berperkara"] == 2
        assert rekap_kasus([])["aktif"] == 0


class TestArsipDokumen:
    def test_validasi_dokumen(self):
        from pengamanan_utils import validate_dokumen
        ok = {"jenis": "sertipikat", "nomor": "SHP 12/2020",
              "lokasi_simpan": "pengelola_barang", "berlaku_sampai": ""}
        assert validate_dokumen(ok) == []
        errors = validate_dokumen({"jenis": "akta", "nomor": " ",
                                   "lokasi_simpan": "brankas",
                                   "berlaku_sampai": "12-07-2026"})
        assert len(errors) == 4

    def test_rekap_dokumen(self):
        from pengamanan_utils import rekap_dokumen
        items = [
            {"jenis": "sertipikat", "lampiran": [{"file_id": "x"}],
             "berlaku_sampai": ""},
            {"jenis": "stnk", "lampiran": [], "berlaku_sampai": "2026-01-01"},
            {"jenis": "stnk", "lampiran": [], "berlaku_sampai": "2027-01-01"},
        ]
        r = rekap_dokumen(items, "2026-07-12")
        assert r["jumlah"] == 3 and r["ber_lampiran"] == 1
        assert r["per_jenis"]["stnk"] == 2
        assert r["kedaluwarsa"] == 1
        assert rekap_dokumen([], "2026-07-12")["jumlah"] == 0


class TestSertipikasi:
    def test_validasi_kategori(self):
        from pengamanan_utils import validate_kategori_sertipikasi
        assert validate_kategori_sertipikasi(
            {"jenis": "sertipikat", "kategori_sertipikasi": "k1"}) == []
        assert validate_kategori_sertipikasi(
            {"jenis": "sertipikat", "kategori_sertipikasi": ""}) == []
        # Bukan sertipikat / kategori asing → ditolak
        assert validate_kategori_sertipikasi(
            {"jenis": "bpkb", "kategori_sertipikasi": "k1"})
        assert validate_kategori_sertipikasi(
            {"jenis": "sertipikat", "kategori_sertipikasi": "k9"})

    def test_rekap_sertipikasi(self):
        from pengamanan_utils import rekap_sertipikasi
        items = [
            {"jenis": "sertipikat", "kategori_sertipikasi": "k1"},
            {"jenis": "sertipikat", "kategori_sertipikasi": "shp_terbit"},
            {"jenis": "sertipikat", "kategori_sertipikasi": ""},
            {"jenis": "bpkb", "kategori_sertipikasi": ""},
        ]
        r = rekap_sertipikasi(items)
        assert r["jumlah_sertipikat"] == 3
        assert r["per_kategori"]["k1"] == 1
        assert r["per_kategori"]["shp_terbit"] == 1
        assert r["tanpa_kategori"] == 1


class TestChecklistPengamanan:
    def test_validasi_checklist(self):
        from pengamanan_utils import validate_checklist
        ok = {"jenis_objek": "tanah",
              "butir": {"patok_batas": True, "sertipikat": False}}
        assert validate_checklist(ok) == []
        assert validate_checklist({"jenis_objek": "kapal", "butir": {}})
        assert validate_checklist({"jenis_objek": "tanah", "butir": {}})
        errors = validate_checklist(
            {"jenis_objek": "kendaraan", "butir": {"patok_batas": True}})
        assert errors and "patok_batas" in errors[0]

    def test_skor_dan_rekap(self):
        from pengamanan_utils import rekap_checklist, skor_checklist
        penuh = {"jenis_objek": "lainnya",
                 "butir": {"simpan_terkunci": True, "apar_gudang": True,
                           "tercatat_dbr": True, "dokumen_perolehan": True}}
        sebagian = {"jenis_objek": "tanah", "butir": {"patok_batas": True}}
        assert skor_checklist(penuh)["persen"] == 100
        s = skor_checklist(sebagian)
        assert s["terpenuhi"] == 1 and s["total"] == 5
        r = rekap_checklist([penuh, sebagian])
        assert r["jumlah"] == 2 and r["penuh"] == 1
        assert r["per_jenis"]["tanah"] == 1


class TestPolisAsuransi:
    def test_validasi_polis(self):
        from pengamanan_utils import validate_polis
        ok = {"nomor_polis": "ABMN-001/2026", "kategori_objek": "program_preferen",
              "sumber_dana": "dipa", "mulai": "2026-01-01",
              "berakhir": "2027-01-01", "nilai_pertanggungan": 5_000_000_000,
              "premi": 12_000_000}
        assert validate_polis(ok) == []
        errors = validate_polis({"nomor_polis": " ", "kategori_objek": "vip",
                                 "sumber_dana": "kas", "mulai": "2026-01-01",
                                 "berakhir": "2025-01-01",
                                 "nilai_pertanggungan": -1, "premi": "x"})
        assert len(errors) == 6

    def test_info_dan_rekap_polis(self):
        from pengamanan_utils import info_polis, rekap_polis
        p_aktif = {"mulai": "2026-01-01", "berakhir": "2027-01-01",
                   "nilai_pertanggungan": 100}
        p_segera = {"mulai": "2025-09-01", "berakhir": "2026-08-01",
                    "nilai_pertanggungan": 50}
        p_habis = {"mulai": "2025-01-01", "berakhir": "2026-01-01",
                   "nilai_pertanggungan": 25}
        today = "2026-07-12"
        assert info_polis(p_aktif, today)["status"] == "aktif"
        segera = info_polis(p_segera, today)
        assert segera["status"] == "segera_berakhir" and segera["sisa_hari"] == 20
        assert info_polis(p_habis, today)["status"] == "berakhir"
        assert info_polis({"mulai": "2026-08-01", "berakhir": "2027-08-01"},
                          today)["status"] == "akan_datang"
        r = rekap_polis([p_aktif, p_segera, p_habis], today)
        assert r["jumlah"] == 3
        assert r["per_status"]["aktif"] == 1
        assert r["per_status"]["segera_berakhir"] == 1
        assert r["nilai_pertanggungan_aktif"] == 150

    def test_baris_csv_polis(self):
        from pengamanan_utils import HEADER_CSV_POLIS, baris_csv_polis
        # Kosong / None → hanya header
        assert baris_csv_polis([], "2026-07-12") == [HEADER_CSV_POLIS]
        assert baris_csv_polis(None, "2026-07-12") == [HEADER_CSV_POLIS]
        rows = baris_csv_polis([{
            "asset_code": "40101", "NUP": "3", "asset_name": "Gedung Kantor",
            "nomor_polis": "POL-1", "penanggung": "Konsorsium Asuransi BMN",
            "kategori_objek": "nonprogram_mandatory",
            "nilai_pertanggungan": 1_000_000.6, "premi": 5_000.4,
            "sumber_dana": "dipa", "mulai": "2026-01-01T00:00",
            "berakhir": "2027-01-01", "keterangan": "-", "created_by": "admin",
        }], "2026-07-12")
        assert rows[0] == HEADER_CSV_POLIS
        r = rows[1]
        # Label kategori/sumber dana/status terbaca; nilai dibulatkan
        assert r[5] == "BMN Nonprogram — Mandatory"
        assert r[6] == 1_000_001 and r[7] == 5_000
        assert r[8] == "DIPA K/L"
        assert r[9] == "2026-01-01"       # tanggal dipangkas 10 char
        assert r[11] == "Aktif"           # status masa berlaku
        assert isinstance(r[12], int)     # sisa_hari terisi
        # Field hilang → string kosong; status tak terhitung → ""
        kosong = baris_csv_polis([{"nomor_polis": "P2"}], "2026-07-12")[1]
        assert kosong[0] == "" and kosong[6] == 0 and kosong[11] == ""

    def test_baris_csv_kasus(self):
        from pengamanan_utils import HEADER_CSV_KASUS, baris_csv_kasus
        # Kosong / None → hanya header
        assert baris_csv_kasus([]) == [HEADER_CSV_KASUS]
        assert baris_csv_kasus(None) == [HEADER_CSV_KASUS]
        rows = baris_csv_kasus([{
            "asset_code": "40101", "NUP": "7", "asset_name": "Tanah Kantor",
            "lokasi": "Jl. Merdeka", "kategori": "berperkara",
            "status": "litigasi", "uraian": "Gugatan perdata",
            "pihak_lawan": "PT X", "nomor_perkara": "12/PDT/2026",
            "pendamping": "Kejaksaan", "created_at": "2026-01-05T08:00:00+00:00",
            "updated_at": "2026-06-10T09:30:00+00:00", "created_by": "admin",
        }])
        assert rows[0] == HEADER_CSV_KASUS
        r = rows[1]
        # Label kategori/status terbaca; tanggal dipangkas 10 char
        assert r[4] == "Sengketa/berperkara di pengadilan"
        assert r[5] == "Litigasi"
        assert r[8] == "12/PDT/2026"
        assert r[10] == "2026-01-05" and r[11] == "2026-06-10"
        assert r[12] == "admin"
        # Field hilang → string kosong; kategori tak dikenal → apa adanya
        kosong = baris_csv_kasus([{"kategori": "xx", "status": "yy"}])[1]
        assert kosong[0] == "" and kosong[4] == "xx" and kosong[5] == "yy"
        assert kosong[10] == "" and kosong[11] == ""
