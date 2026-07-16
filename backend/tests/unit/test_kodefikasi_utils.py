"""Test logika murni kodefikasi (kodefikasi_utils.py) — tanpa Mongo.

Menjaga struktur 5 level (1/3/5/7/10 digit) tidak bergeser diam-diam:
modul Pembukuan, Persediaan, dan Pengadaan semuanya bergantung padanya.
"""
from kodefikasi_utils import (
    GOLONGAN_DEFAULTS, LENGTH_TO_LEVEL, LEVEL_LABELS, LEVEL_LENGTHS,
    derive_level, hierarchy_prefixes, is_persediaan_kode, normalize_kode,
    parent_of, parse_import_rows, validate_kode,
)


class TestStruktur:
    def test_level_lengths_lima_level_naik_monoton(self):
        assert list(LEVEL_LENGTHS.keys()) == [1, 2, 3, 4, 5]
        lengths = list(LEVEL_LENGTHS.values())
        assert lengths == sorted(lengths)
        assert lengths[0] == 1 and lengths[-1] == 10  # golongan 1 digit, penuh 10

    def test_setiap_level_punya_label(self):
        assert set(LEVEL_LABELS) == set(LEVEL_LENGTHS)
        assert all(LEVEL_LABELS[lv] for lv in LEVEL_LENGTHS)

    def test_golongan_default_8_dan_prefix_unik(self):
        assert len(GOLONGAN_DEFAULTS) == 8
        kode = [k for k, _ in GOLONGAN_DEFAULTS]
        assert kode == [str(i) for i in range(1, 9)]
        assert GOLONGAN_DEFAULTS[0] == ("1", "Persediaan")


class TestDeriveLevel:
    def test_panjang_valid(self):
        assert derive_level("3") == 1
        assert derive_level("301") == 2
        assert derive_level("30102") == 3
        assert derive_level("3010203") == 4
        assert derive_level("3010203001") == 5

    def test_panjang_invalid(self):
        for kode in ("", "30", "3010", "301020", "30102030", "301020300", "30102030011"):
            assert derive_level(kode) is None

    def test_length_to_level_konsisten(self):
        for level, length in LEVEL_LENGTHS.items():
            assert LENGTH_TO_LEVEL[length] == level


class TestValidateKode:
    def test_valid(self):
        for kode in ("1", "301", "30102", "3010203", "3010203001"):
            ok, err = validate_kode(kode)
            assert ok and err == ""

    def test_kosong(self):
        ok, err = validate_kode("")
        assert not ok and "kosong" in err.lower()

    def test_non_digit(self):
        ok, err = validate_kode("3a1")
        assert not ok and "angka" in err

    def test_panjang_salah(self):
        ok, err = validate_kode("3010")
        assert not ok and "level 1-5" in err


class TestParentHierarki:
    def test_parent_berjenjang(self):
        assert parent_of("3") is None
        assert parent_of("301") == "3"
        assert parent_of("30102") == "301"
        assert parent_of("3010203") == "30102"
        assert parent_of("3010203001") == "3010203"

    def test_parent_kode_invalid(self):
        assert parent_of("") is None
        assert parent_of("3010") is None

    def test_hierarchy_prefixes_penuh(self):
        assert hierarchy_prefixes("3010203001") == [
            (1, "3"), (2, "301"), (3, "30102"), (4, "3010203"), (5, "3010203001"),
        ]

    def test_hierarchy_prefixes_sebagian(self):
        assert hierarchy_prefixes("301") == [(1, "3"), (2, "301")]
        assert hierarchy_prefixes("") == []

    def test_hierarchy_prefixes_kode_persediaan_16_digit_dipotong_10(self):
        # Route lookup memotong ke 10 digit dulu — di sini pastikan prefix
        # 16 digit pun menghasilkan 5 level pertama yang benar.
        prefixes = hierarchy_prefixes("1010101001000001"[:10])
        assert prefixes[0] == (1, "1")
        assert prefixes[-1] == (5, "1010101001")


class TestDomainPersediaan:
    def test_prefix_1_persediaan(self):
        assert is_persediaan_kode("1")
        assert is_persediaan_kode("1010101001")

    def test_prefix_lain_bukan(self):
        for kode in ("2", "301", "8010101001", ""):
            assert not is_persediaan_kode(kode)


class TestNormalizeKode:
    def test_buang_spasi_dan_artefak_float_excel(self):
        assert normalize_kode(" 301 ") == "301"
        assert normalize_kode("3010203001.0") == "3010203001"
        assert normalize_kode(3) == "3"
        assert normalize_kode(None) == ""


class TestParseImportRows:
    def test_baris_valid_level_diturunkan(self):
        entries, errors, dupes = parse_import_rows([
            {"kode": "3", "uraian": "Peralatan dan Mesin"},
            {"kode": "301", "uraian": "Alat Besar"},
        ])
        assert errors == [] and dupes == 0
        assert entries[0] == {"kode": "3", "uraian": "Peralatan dan Mesin",
                              "level": 1, "parent_kode": None}
        assert entries[1]["level"] == 2 and entries[1]["parent_kode"] == "3"

    def test_kolom_alternatif_kode_barang_nama(self):
        entries, errors, _ = parse_import_rows([
            {"kode_barang": "30102", "nama": "Alat Besar Apung"},
        ])
        assert errors == []
        assert entries[0]["kode"] == "30102"
        assert entries[0]["uraian"] == "Alat Besar Apung"

    def test_baris_kosong_dilewati(self):
        entries, errors, _ = parse_import_rows([
            {"kode": "", "uraian": ""},
            {"kode": None, "uraian": None},
        ])
        assert entries == [] and errors == []

    def test_error_kode_invalid_dan_uraian_kosong(self):
        entries, errors, _ = parse_import_rows([
            {"kode": "30x", "uraian": "Salah"},
            {"kode": "301", "uraian": ""},
        ])
        assert entries == []
        assert len(errors) == 2
        assert "Baris 2" in errors[0] and "Baris 3" in errors[1]

    def test_duplikat_baris_terakhir_menang(self):
        entries, errors, dupes = parse_import_rows([
            {"kode": "301", "uraian": "Lama"},
            {"kode": "301", "uraian": "Baru"},
        ])
        assert errors == [] and dupes == 1
        assert len(entries) == 1 and entries[0]["uraian"] == "Baru"

    def test_kode_float_excel(self):
        entries, errors, _ = parse_import_rows([
            {"kode": "301.0", "uraian": "Alat Besar"},
        ])
        assert errors == [] and entries[0]["kode"] == "301"

    def test_siman_header_golongan_dan_bidang(self):
        # Keluaran SIMAN V2 per level: header khas per file
        entries, errors, _ = parse_import_rows([
            {"Kode Golongan": "1", "Nama Golongan": "PERSEDIAAN"},
        ])
        assert errors == [] and entries[0]["kode"] == "1" and entries[0]["level"] == 1
        entries, _, _ = parse_import_rows([
            {"Kode Golongan": "1", "Kode Bidang": "01",
             "Kode Bidang Barang": "101", "Nama Bidang": "BARANG PAKAI HABIS"},
        ])
        assert entries[0]["kode"] == "101" and entries[0]["level"] == 2

    def test_siman_pilih_kode_terdalam_bukan_induk(self):
        # File "sub kelompok": ada kolom induk 5 digit & kode penuh 7 digit —
        # harus memilih yang 7 digit (terdalam), bukan induknya.
        entries, _, _ = parse_import_rows([
            {"Kode Kelompok Barang": "10101", "Kode Sub Kelompok": "01",
             "Kode Sub Kelompok Barang": "1010101", "Nama Sub Kelompok": "BAHAN BANGUNAN"},
        ])
        assert entries[0]["kode"] == "1010101" and entries[0]["level"] == 4

    def test_siman_subsub_dengan_metadata(self):
        entries, errors, _ = parse_import_rows([
            {"Kode Sub Kelompok Barang": "1010101", "Kode Sub Subkelompok": "001",
             "Kode Barang": "1010101001", "Nama Sub Subkelompok": "Aspal",
             "Satuan": "", "Dasar": "PMK 29/PMK.06/2010",
             "Jenis BMN": "BARANG PERSEDIAAN", "TB/STB": "STB",
             "Bukti Kepemilikan": "Tidak Memiliki"},
        ])
        assert errors == []
        e = entries[0]
        assert e["kode"] == "1010101001" and e["level"] == 5 and e["uraian"] == "Aspal"
        assert e["dasar"] == "PMK 29/PMK.06/2010"
        assert e["jenis_bmn"] == "BARANG PERSEDIAAN"
        assert e["tb_stb"] == "STB"
        assert e["bukti_kepemilikan"] == "Tidak Memiliki"
        assert "satuan" not in e  # kosong tidak disimpan


# ── FK kodefikasi tervalidasi: level_terdaftar_terdalam (§5A gap #7, #262) ──
from kodefikasi_utils import level_terdaftar_terdalam


def test_level_terdaftar_penuh():
    # Kode 10 digit (level 5) terdaftar utuh → level 5
    assert level_terdaftar_terdalam("3050104001", {"3050104001"}) == 5


def test_level_terdaftar_berjenjang():
    # Terdaftar sampai level 3 (5 digit) → 3
    kode = "3050104001"
    assert level_terdaftar_terdalam(kode, {"3", "305", "30501"}) == 3
    # Hanya golongan → 1
    assert level_terdaftar_terdalam(kode, {"3"}) == 1


def test_level_terdaftar_kosong():
    # Tak ada satu pun prefix terdaftar → 0
    assert level_terdaftar_terdalam("3050104001", set()) == 0
    assert level_terdaftar_terdalam("3050104001", {"9", "801"}) == 0


def test_level_terdaftar_none_aman():
    assert level_terdaftar_terdalam(None, {"3"}) == 0
    assert level_terdaftar_terdalam("", {"3"}) == 0


# ── Validasi lunak kode aset: cek_kode_kodefikasi (§5A Prinsip 2, #269) ──
from kodefikasi_utils import cek_kode_kodefikasi


def test_cek_kode_kosong_tanpa_peringatan():
    r = cek_kode_kodefikasi("", {"3"})
    assert r["status"] == "kosong" and r["peringatan"] is False
    assert cek_kode_kodefikasi(None, {"3"})["status"] == "kosong"


def test_cek_kode_ok_terdaftar_penuh():
    r = cek_kode_kodefikasi("3050104001", {"3050104001"})
    assert r["status"] == "ok" and r["peringatan"] is False
    assert r["level_kode"] == 5 and r["level_terdaftar"] == 5


def test_cek_kode_panjang_tak_valid():
    r = cek_kode_kodefikasi("3010", {"3"})
    assert r["status"] == "panjang_kode_tak_valid" and r["peringatan"] is True
    assert r["level_kode"] is None


def test_cek_kode_golongan_tak_terdaftar():
    r = cek_kode_kodefikasi("3050104001", set())
    assert r["status"] == "golongan_tak_terdaftar" and r["peringatan"] is True
    assert r["level_terdaftar"] == 0 and "Golongan '3'" in r["pesan"]


def test_cek_kode_spesifik_tak_terdaftar():
    # Terdaftar sampai level 3 (5 digit), kode level 5 → spesifik belum terdaftar
    r = cek_kode_kodefikasi("3050104001", {"3", "305", "30501"})
    assert r["status"] == "kode_spesifik_tak_terdaftar" and r["peringatan"] is True
    assert r["level_kode"] == 5 and r["level_terdaftar"] == 3


def test_cek_kode_normalisasi_float_excel():
    r = cek_kode_kodefikasi("305.0", {"305"})
    assert r["kode"] == "305" and r["status"] == "ok"
