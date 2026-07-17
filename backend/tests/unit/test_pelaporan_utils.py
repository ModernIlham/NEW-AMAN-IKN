"""Uji logika murni periode pelaporan ber-kunci (pustaka §2.3)."""
from pelaporan_utils import (
    STATUS_PERIODE, cari_periode, info_tenggat_periode, kunci_unik_periode,
    label_periode_pelaporan, penanda_final, rekap_periode,
    validate_buka_periode, validate_kunci_periode, validate_periode,
    validate_tenggat,
)


def test_label_dan_kunci_unik():
    assert label_periode_pelaporan(2026, 1) == "Semester I 2026"
    assert label_periode_pelaporan(2026, 2) == "Semester II 2026"
    assert label_periode_pelaporan(2026) == "Tahunan 2026"
    assert kunci_unik_periode(2026, 1) == "2026-S1"
    assert kunci_unik_periode(2026) == "2026-T"
    assert set(STATUS_PERIODE) == {"terbuka", "terkunci"}


def test_validate_periode():
    assert validate_periode({"tahun": 2026, "semester": 1}) == []
    assert validate_periode({"tahun": 2026, "semester": None}) == []
    assert len(validate_periode({"tahun": "2026", "semester": 3})) == 2


def test_transisi_kunci_buka():
    assert validate_kunci_periode({"status": "terbuka"}) == []
    assert validate_kunci_periode({"status": "terkunci"}) != []
    assert validate_buka_periode({"status": "terkunci"},
                                 {"alasan": "Koreksi audit BPK"}) == []
    assert len(validate_buka_periode({"status": "terbuka"}, {"alasan": ""})) == 2


def test_cari_dan_rekap():
    items = [
        {"tahun": 2026, "semester": 1, "status": "terkunci",
         "tanggal_kunci": "2026-07-05T08:00:00"},
        {"tahun": 2026, "semester": None, "status": "terbuka"},
    ]
    assert cari_periode(items, 2026, 1)["status"] == "terkunci"
    assert cari_periode(items, 2026) is items[1]
    assert cari_periode(items, 2025, 2) is None
    assert rekap_periode(items) == {"total": 2, "terbuka": 1, "terkunci": 1}


def test_penanda_final():
    terkunci = {"status": "terkunci", "tanggal_kunci": "2026-07-05T08:00:00"}
    assert penanda_final(terkunci) == " — FINAL (terkunci per 2026-07-05)"
    assert penanda_final({"status": "terbuka"}) == ""
    assert penanda_final(None) == ""
    assert penanda_final({"status": "terkunci"}) == " — FINAL"


def test_validate_tenggat():
    assert validate_tenggat({"tenggat": "2026-07-20"}) == []
    assert validate_tenggat({"tenggat": ""}) == []      # kosong = hapus
    assert validate_tenggat({"tenggat": "bukan-tanggal"}) != []


def test_info_tenggat_periode():
    terbuka = {"status": "terbuka", "tenggat": "2026-07-20"}
    assert info_tenggat_periode(terbuka, "2026-07-12") == {
        "tenggat": "2026-07-20", "lewat": False, "sisa_hari": 8}
    assert info_tenggat_periode(terbuka, "2026-07-20")["sisa_hari"] == 0
    assert info_tenggat_periode(terbuka, "2026-07-21")["lewat"] is True
    # Terkunci / tanpa tenggat → tidak diingatkan
    assert info_tenggat_periode({"status": "terkunci",
                                 "tenggat": "2026-07-20"},
                                "2026-07-25")["tenggat"] is None
    assert info_tenggat_periode({"status": "terbuka"}, "2026-07-12") == {
        "tenggat": None, "lewat": False, "sisa_hari": None}


# ── Narasi tanggal Berita Acara (terbilang) ──
from pelaporan_utils import narasi_hari_tanggal, terbilang_id


def test_terbilang_id_dasar():
    assert terbilang_id(0) == "nol"
    assert terbilang_id(7) == "tujuh"
    assert terbilang_id(11) == "sebelas"
    assert terbilang_id(17) == "tujuh belas"
    assert terbilang_id(20) == "dua puluh"
    assert terbilang_id(31) == "tiga puluh satu"
    assert terbilang_id(100) == "seratus"
    assert terbilang_id(1999) == "seribu sembilan ratus sembilan puluh sembilan"
    assert terbilang_id(2026) == "dua ribu dua puluh enam"


def test_terbilang_id_tak_valid():
    assert terbilang_id(-1) == ""
    assert terbilang_id("abc") == ""
    assert terbilang_id(None) == ""


def test_narasi_hari_tanggal_lengkap():
    # 2026-07-17 adalah hari Jumat
    n = narasi_hari_tanggal("2026-07-17T08:00:00Z")
    assert n == {"hari": "Jumat", "tanggal_terbilang": "Tujuh Belas",
                 "bulan": "Juli", "tahun_terbilang": "Dua Ribu Dua Puluh Enam"}


def test_narasi_hari_tanggal_tak_valid():
    assert narasi_hari_tanggal("") is None
    assert narasi_hari_tanggal("bukan tanggal") is None
    assert narasi_hari_tanggal("9999-12-31") is None  # placeholder SIMAN
