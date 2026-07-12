"""Uji logika murni modul Pemeliharaan (PP 27/2014 Ps. 46-47)."""
import pytest

from pemeliharaan_utils import (
    JENIS_PEMELIHARAAN, KONDISI_SETELAH_VALID, indikasi_kapitalisasi,
    jatuh_tempo, kelompok_dhpb, parse_biaya, rekap_pemeliharaan,
    rentang_periode, status_jadwal, tahun_dari_tanggal, tambah_bulan,
    urut_riwayat, validate_jadwal, validate_pemeliharaan,
)

HARI_INI = "2026-07-12"


def _payload(**over):
    base = {
        "asset_id": "a1",
        "tanggal": "2026-07-01",
        "jenis": "sedang",
        "uraian": "Servis AC ruang arsip",
        "biaya": 350000,
        "kondisi_setelah": "",
    }
    base.update(over)
    return base


def _rec(**over):
    base = {
        "asset_id": "a1", "asset_code": "3100102001", "NUP": "1",
        "asset_name": "AC Split", "tanggal": "2026-03-10",
        "jenis": "sedang", "biaya": 100000, "created_at": "2026-03-10T01:00:00",
    }
    base.update(over)
    return base


# ── parse_biaya ──────────────────────────────────────────────────────────

def test_parse_biaya_kosong_jadi_nol():
    assert parse_biaya(None) == 0.0
    assert parse_biaya("") == 0.0
    assert parse_biaya("  ") == 0.0


def test_parse_biaya_angka_dan_koma_desimal():
    assert parse_biaya("1500000") == 1500000.0
    assert parse_biaya("1234,5") == 1234.5
    assert parse_biaya(250.75) == 250.75


def test_parse_biaya_negatif_atau_bukan_angka():
    assert parse_biaya(-1) is None
    assert parse_biaya("abc") is None


# ── validate_pemeliharaan ────────────────────────────────────────────────

def test_validasi_lolos_payload_lengkap():
    assert validate_pemeliharaan(_payload(), HARI_INI) == []


def test_validasi_tanggal_wajib_dan_format():
    assert any("Tanggal" in e for e in validate_pemeliharaan(_payload(tanggal=""), HARI_INI))
    assert any("Tanggal" in e for e in validate_pemeliharaan(_payload(tanggal="31-12-2026"), HARI_INI))


def test_validasi_tanggal_masa_depan_ditolak():
    errs = validate_pemeliharaan(_payload(tanggal="2026-07-13"), HARI_INI)
    assert any("masa depan" in e for e in errs)
    # tepat hari ini boleh
    assert validate_pemeliharaan(_payload(tanggal=HARI_INI), HARI_INI) == []


def test_validasi_jenis_harus_terdaftar():
    errs = validate_pemeliharaan(_payload(jenis="renovasi"), HARI_INI)
    assert any("Jenis" in e for e in errs)
    for j in JENIS_PEMELIHARAAN:
        assert validate_pemeliharaan(_payload(jenis=j), HARI_INI) == []


def test_validasi_uraian_wajib():
    assert any("Uraian" in e for e in validate_pemeliharaan(_payload(uraian="  "), HARI_INI))


def test_validasi_biaya_dan_kondisi():
    assert any("Biaya" in e for e in validate_pemeliharaan(_payload(biaya="x"), HARI_INI))
    assert any("Kondisi" in e for e in validate_pemeliharaan(
        _payload(kondisi_setelah="Hancur"), HARI_INI))
    for k in KONDISI_SETELAH_VALID:
        assert validate_pemeliharaan(_payload(kondisi_setelah=k), HARI_INI) == []


# ── indikasi kapitalisasi (PMK 181/2016) ─────────────────────────────────

def test_indikasi_kapitalisasi_peralatan_mesin_ambang_1jt():
    assert indikasi_kapitalisasi(1_000_000, "3100102001") is True
    assert indikasi_kapitalisasi(999_999, "3100102001") is False


def test_indikasi_kapitalisasi_gedung_ambang_25jt():
    assert indikasi_kapitalisasi(25_000_000, "4010101001") is True
    assert indikasi_kapitalisasi(24_999_999, "4010101001") is False


def test_indikasi_kapitalisasi_golongan_tanpa_ambang_false():
    # Golongan di luar peta ambang (mis. tanah '2') tidak ditandai
    assert indikasi_kapitalisasi(100_000_000, "2010104001") is False
    assert indikasi_kapitalisasi(1_000_000, "") is False
    assert indikasi_kapitalisasi("bukan-angka", "3100102001") is False


# ── tahun & urutan ───────────────────────────────────────────────────────

def test_tahun_dari_tanggal():
    assert tahun_dari_tanggal("2026-03-10") == 2026
    assert tahun_dari_tanggal("") == 0
    assert tahun_dari_tanggal("bukan-tanggal") == 0


def test_urut_riwayat_terbaru_dulu_dengan_tiebreak_created_at():
    a = _rec(tanggal="2026-01-05", created_at="2026-01-05T01:00:00")
    b = _rec(tanggal="2026-03-01", created_at="2026-03-01T01:00:00")
    c = _rec(tanggal="2026-01-05", created_at="2026-01-05T09:00:00")
    urut = urut_riwayat([a, b, c])
    assert urut == [b, c, a]
    assert urut_riwayat([]) == []


# ── rekap ────────────────────────────────────────────────────────────────

def test_rekap_total_per_jenis_per_tahun():
    records = [
        _rec(tanggal="2025-11-01", biaya=200000),
        _rec(tanggal="2026-02-01", biaya=100000),
        _rec(tanggal="2026-05-01", jenis="berat", biaya=750000),
    ]
    r = rekap_pemeliharaan(records)
    assert r["jumlah"] == 3
    assert r["total_biaya"] == pytest.approx(1050000)
    assert r["per_jenis"]["sedang"] == {"jumlah": 2, "biaya": pytest.approx(300000)}
    assert r["per_jenis"]["berat"]["biaya"] == pytest.approx(750000)
    assert r["per_tahun"][2026]["jumlah"] == 2
    assert r["per_tahun"][2025]["biaya"] == pytest.approx(200000)
    # tahun terurut menurun untuk pilihan filter UI
    assert list(r["per_tahun"]) == [2026, 2025]


def test_rekap_saring_tahun_tetap_hitung_semua_tahun():
    records = [
        _rec(tanggal="2025-11-01", biaya=200000),
        _rec(tanggal="2026-02-01", biaya=100000),
    ]
    r = rekap_pemeliharaan(records, tahun=2026)
    assert r["jumlah"] == 1
    assert r["total_biaya"] == pytest.approx(100000)
    # per_tahun tidak ikut tersaring (dipakai UI utk daftar tahun tersedia)
    assert set(r["per_tahun"]) == {2025, 2026}


def test_rekap_per_aset_terurut_biaya_terbesar_dan_tanggal_terakhir():
    records = [
        _rec(asset_id="a1", asset_name="AC Split", tanggal="2026-01-01", biaya=100000),
        _rec(asset_id="a1", asset_name="AC Split", tanggal="2026-06-01", biaya=50000),
        _rec(asset_id="a2", asset_name="Genset", tanggal="2026-02-01", biaya=900000),
    ]
    r = rekap_pemeliharaan(records)
    assert [a["asset_id"] for a in r["per_aset"]] == ["a2", "a1"]
    a1 = r["per_aset"][1]
    assert a1["jumlah"] == 2
    assert a1["total_biaya"] == pytest.approx(150000)
    assert a1["terakhir"] == "2026-06-01"


def test_rekap_kosong_aman():
    r = rekap_pemeliharaan([])
    assert r["jumlah"] == 0 and r["total_biaya"] == 0.0
    assert r["per_aset"] == [] and r["per_tahun"] == {}


# ── Jadwal berkala ───────────────────────────────────────────────────────

def test_tambah_bulan_normal_dan_lintas_tahun():
    assert tambah_bulan("2026-03-15", 3) == "2026-06-15"
    assert tambah_bulan("2026-11-10", 3) == "2027-02-10"
    assert tambah_bulan("2026-12-01", 1) == "2027-01-01"


def test_tambah_bulan_jepit_akhir_bulan():
    assert tambah_bulan("2026-01-31", 1) == "2026-02-28"
    assert tambah_bulan("2024-01-31", 1) == "2024-02-29"  # kabisat
    assert tambah_bulan("2026-08-31", 1) == "2026-09-30"
    assert tambah_bulan("tidak-valid", 1) == ""


def test_validate_jadwal():
    assert validate_jadwal({"interval_bulan": 6, "mulai": "2026-07-01"}) == []
    assert any("Interval" in e for e in validate_jadwal({"interval_bulan": 0, "mulai": "2026-07-01"}))
    assert any("Interval" in e for e in validate_jadwal({"interval_bulan": "x", "mulai": "2026-07-01"}))
    assert any("mulai" in e for e in validate_jadwal({"interval_bulan": 6, "mulai": ""}))


def test_jatuh_tempo_dari_mulai_lalu_dari_terakhir():
    j = {"interval_bulan": 6, "mulai": "2026-07-01", "terakhir": ""}
    assert jatuh_tempo(j) == "2026-07-01"
    j["terakhir"] = "2026-07-05"
    assert jatuh_tempo(j) == "2027-01-05"


def test_status_jadwal_terlambat_segera_terjadwal():
    assert status_jadwal("2026-07-11", HARI_INI) == "terlambat"
    assert status_jadwal(HARI_INI, HARI_INI) == "segera"          # hari ini = due
    assert status_jadwal("2026-07-26", HARI_INI) == "segera"      # tepat ambang 14 hari
    assert status_jadwal("2026-07-27", HARI_INI) == "terjadwal"
    assert status_jadwal("", HARI_INI) == "terjadwal"             # tanpa due → netral


# ── DHPB: periode & pengelompokan ────────────────────────────────────────

def test_rentang_periode_tahun_penuh_dan_semester():
    assert rentang_periode(2026) == ("2026-01-01", "2026-12-31", "Tahun Anggaran 2026")
    assert rentang_periode(2026, 1) == ("2026-01-01", "2026-06-30", "Semester I Tahun Anggaran 2026")
    assert rentang_periode(2026, 2) == ("2026-07-01", "2026-12-31", "Semester II Tahun Anggaran 2026")


def test_kelompok_dhpb_urut_aset_dan_kronologis():
    records = [
        _rec(asset_id="a2", asset_name="Genset", tanggal="2026-02-01", biaya=900000),
        _rec(asset_id="a1", asset_name="AC Split", tanggal="2026-06-01", biaya=50000,
             created_at="2026-06-01T01:00:00"),
        _rec(asset_id="a1", asset_name="AC Split", tanggal="2026-01-01", biaya=100000,
             created_at="2026-01-01T01:00:00"),
    ]
    grup, total = kelompok_dhpb(records)
    # Grup terurut nama aset (AC Split dulu), catatan kronologis naik
    assert [g["asset_id"] for g in grup] == ["a1", "a2"]
    assert [r["tanggal"] for r in grup[0]["items"]] == ["2026-01-01", "2026-06-01"]
    assert grup[0]["subtotal"] == pytest.approx(150000)
    assert grup[1]["subtotal"] == pytest.approx(900000)
    assert total == pytest.approx(1050000)


def test_kelompok_dhpb_kosong_dan_tanpa_asset_id():
    grup, total = kelompok_dhpb([])
    assert grup == [] and total == 0.0
    # Catatan legacy tanpa asset_id tetap terkelompok via kode+NUP
    r1 = _rec(asset_id=None, asset_code="X", NUP="1", biaya=10)
    r2 = _rec(asset_id=None, asset_code="X", NUP="1", biaya=15)
    grup, total = kelompok_dhpb([r1, r2])
    assert len(grup) == 1 and len(grup[0]["items"]) == 2
    assert total == pytest.approx(25)
