"""Uji logika murni penyusutan (PMK 65/2017 + KMK 295/2019 jo. 266/2023)."""
import pytest

from penilaian_utils import (
    GOLONGAN_TANPA_SUSUT, MASA_MANFAAT_DEFAULT, build_asset_revaluasi_projection,
    hitung_penyusutan, rekap_penyusutan, semester_index, status_susut,
    validate_masa_manfaat,
)


class TestRevaluasiProjection:
    """Proyeksi master saat revaluasi final (#254): nilai_wajar_terakhir + jejak."""
    KOREKSI = {
        "id": "k-1", "asset_id": "a-9", "nilai_lama": 100_000_000.0,
        "nilai_baru": 150_000_000.0, "jenis": "revaluasi",
        "nomor_dokumen": "LAP-DJKN-2026-01", "tanggal_dokumen": "2026-03-15T00:00:00",
    }

    def test_set_nilai_wajar_terakhir_dan_jejak(self):
        proj = build_asset_revaluasi_projection(self.KOREKSI, "2026-03-20T08:00:00")
        assert proj["nilai_wajar_terakhir"] == 150_000_000.0
        rev = proj["revaluasi"]
        assert rev["nilai_wajar"] == 150_000_000.0
        assert rev["nilai_lama"] == 100_000_000.0
        assert rev["nomor_dokumen"] == "LAP-DJKN-2026-01"
        assert rev["tanggal_dokumen"] == "2026-03-15"   # dipotong 10 char
        assert rev["koreksi_id"] == "k-1"
        assert rev["diproyeksikan_pada"] == "2026-03-20T08:00:00"

    def test_tidak_menimpa_purchase_price(self):
        # proyeksi HANYA field revaluasi — nilai perolehan historis tetap utuh
        proj = build_asset_revaluasi_projection(self.KOREKSI, "2026-03-20")
        assert "purchase_price" not in proj

    def test_nilai_kosong_aman_jadi_nol(self):
        proj = build_asset_revaluasi_projection({"id": "k", "asset_id": "a"}, "2026-01-01")
        assert proj["nilai_wajar_terakhir"] == 0.0
        assert proj["revaluasi"]["nilai_lama"] == 0.0


def _aset(**over):
    base = {"id": "a1", "asset_code": "3020101001", "NUP": "1",
            "asset_name": "Mobil Dinas", "purchase_price": 280_000_000,
            "purchase_date": "2023-03-15", "condition": "Baik"}
    base.update(over)
    return base


def test_semester_index():
    assert semester_index("2026-01-01") == 2026 * 2
    assert semester_index("2026-06-30") == 2026 * 2
    assert semester_index("2026-07-01") == 2026 * 2 + 1
    assert semester_index("") is None


def test_status_susut_normal_dan_pengecualian():
    status, _, masa = status_susut(_aset())
    assert status == "susut" and masa == 7  # alat angkutan darat bermotor
    status, alasan, _ = status_susut(_aset(asset_code="2010104001"))
    assert status == "tidak" and "Tanah" in alasan
    status, alasan, _ = status_susut(_aset(condition="Rusak Berat"))
    assert status == "henti" and "penghapusan" in alasan
    status, alasan, _ = status_susut(_aset(asset_code="3999901001"))
    assert status == "tanpa_referensi" and "39999" in alasan
    status, alasan, _ = status_susut(_aset(purchase_date=""))
    assert status == "tanpa_referensi" and "perolehan" in alasan


def test_hitung_garis_lurus_semesteran_konvensi_penuh():
    # Perolehan Mar 2023 (Sem I 2023); posisi per 2026-07-12 → semester
    # yang sudah berakhir: Sem I 23 s.d. Sem I 26 = 7 semester
    d = hitung_penyusutan(280_000_000, 7, "2023-03-15", "2026-07-12")
    assert d["masa_semester"] == 14
    assert d["beban_per_semester"] == pytest.approx(20_000_000)
    assert d["semester_terpakai"] == 7
    assert d["akumulasi"] == pytest.approx(140_000_000)
    assert d["nilai_buku"] == pytest.approx(140_000_000)
    assert d["habis"] is False


def test_hitung_semester_perolehan_belum_dibukukan():
    # Posisi di semester yang sama dengan perolehan → belum ada pembebanan
    d = hitung_penyusutan(8_000_000, 4, "2026-02-01", "2026-06-29")
    assert d["semester_terpakai"] == 0 and d["akumulasi"] == 0
    # Tepat setelah semester berganti → 1 semester dibukukan
    d = hitung_penyusutan(8_000_000, 4, "2026-02-01", "2026-07-01")
    assert d["semester_terpakai"] == 1
    assert d["akumulasi"] == pytest.approx(1_000_000)


def test_hitung_habis_masa_manfaat_nilai_buku_nol():
    d = hitung_penyusutan(8_000_000, 4, "2018-01-01", "2026-07-12")
    assert d["habis"] is True
    assert d["akumulasi"] == pytest.approx(8_000_000)
    assert d["nilai_buku"] == 0.0  # nol, bukan Rp1


def test_rekap_pisah_bucket_dan_total():
    assets = [
        _aset(id="a1"),                                            # susut
        _aset(id="a2", asset_code="2010104001"),                   # tanah → tidak
        _aset(id="a3", condition="Rusak Berat"),                   # henti
        _aset(id="a4", asset_code="3999901001"),                   # tanpa referensi
        _aset(id="a5", purchase_price=8_000_000, asset_code="3100101001",
              purchase_date="2018-01-01"),                         # komputer, habis
    ]
    r = rekap_penyusutan(assets, "2026-07-12")
    assert r["total"]["jumlah"] == 2
    assert len(r["henti"]) == 1 and r["henti"][0]["id"] == "a3"
    assert len(r["tanpa_referensi"]) == 1 and r["tanpa_referensi"][0]["id"] == "a4"
    assert sum(r["tidak"].values()) == 1
    assert r["jumlah_habis"] == 1
    g3 = next(g for g in r["per_golongan"] if g["golongan"] == "3")
    assert g3["nilai_perolehan"] == pytest.approx(288_000_000)
    assert g3["nilai_buku"] == pytest.approx(140_000_000)  # a1 140jt + a5 0


def test_rekap_kosong_aman():
    r = rekap_penyusutan([], "2026-07-12")
    assert r["per_golongan"] == [] and r["total"]["jumlah"] == 0


def test_validate_masa_manfaat():
    assert validate_masa_manfaat("30201", 7) == []
    assert validate_masa_manfaat("40101", 50) == []
    assert any("5 digit" in e for e in validate_masa_manfaat("302", 7))
    assert any("5 digit" in e for e in validate_masa_manfaat("3020a", 7))
    assert any("Golongan" in e for e in validate_masa_manfaat("20101", 7))  # tanah
    assert any("1-60" in e for e in validate_masa_manfaat("30201", 0))
    assert any("1-60" in e for e in validate_masa_manfaat("30201", "x"))


class TestKoreksiNilai:
    def test_validasi_koreksi(self):
        from penilaian_utils import validate_koreksi_nilai
        ok = {"jenis": "revaluasi", "jenis_dokumen": "lhip",
              "nomor_dokumen": "LHIP-12/2026", "tanggal_dokumen": "2026-06-30",
              "nilai_lama": 100_000_000, "nilai_baru": 250_000_000,
              "dampak_masa_manfaat": "masa_manfaat_baru",
              "masa_manfaat_semester": 40}
        assert validate_koreksi_nilai(ok) == []
        errors = validate_koreksi_nilai(
            {"jenis": "markup", "jenis_dokumen": "memo", "nomor_dokumen": " ",
             "tanggal_dokumen": "30-06-2026", "nilai_lama": -1,
             "nilai_baru": "x", "dampak_masa_manfaat": "reset"})
        assert len(errors) == 7
        # Masa manfaat baru wajib angka semester > 0
        assert validate_koreksi_nilai(
            {**ok, "masa_manfaat_semester": 0})

    def test_rekap_koreksi(self):
        from penilaian_utils import rekap_koreksi_nilai
        items = [
            {"jenis": "revaluasi", "status_sakti": "belum_dicatat",
             "nilai_lama": 100, "nilai_baru": 250},
            {"jenis": "koreksi_pencatatan", "status_sakti": "tercatat_sakti",
             "nilai_lama": 50, "nilai_baru": 40},
            {"jenis": "penilaian_tujuan_tertentu",
             "status_sakti": "belum_dicatat",
             "nilai_lama": 0, "nilai_baru": 999},
        ]
        r = rekap_koreksi_nilai(items)
        assert r["jumlah"] == 3
        assert r["belum_tercatat_sakti"] == 1  # tujuan tertentu tak dihitung
        assert r["selisih_total"] == 140       # (250-100) + (40-50)
        assert r["per_jenis"]["penilaian_tujuan_tertentu"] == 1


def test_susun_riwayat_nilai():
    from penilaian_utils import susun_riwayat_nilai
    aset = {"purchase_date": "2020-03-15", "purchase_price": 10_000_000}
    koreksi = [
        {"tanggal_dokumen": "2023-12-01", "jenis": "revaluasi",
         "nilai_lama": 10_000_000, "nilai_baru": 25_000_000,
         "nomor_dokumen": "LHIP-1", "status_sakti": "tercatat_sakti"},
        # Informasional: tidak mengubah nilai buku terkini
        {"tanggal_dokumen": "2024-06-01", "jenis": "penilaian_tujuan_tertentu",
         "nilai_lama": 25_000_000, "nilai_baru": 30_000_000,
         "nomor_dokumen": "LP-9", "status_sakti": "belum_dicatat"},
        # Lebih awal dari revaluasi → harus terurut di depan
        {"tanggal_dokumen": "2022-01-10", "jenis": "koreksi_pencatatan",
         "nilai_lama": 10_000_000, "nilai_baru": 12_000_000,
         "nomor_dokumen": "BA-2", "status_sakti": "tercatat_sakti"},
    ]
    r = susun_riwayat_nilai(aset, koreksi)
    # Peristiwa: perolehan + 3 koreksi, terurut menaik tanggal
    assert [p["jenis"] for p in r["peristiwa"]] == [
        "perolehan", "koreksi_pencatatan", "revaluasi", "penilaian_tujuan_tertentu"]
    assert r["peristiwa"][0]["nilai_baru"] == 10_000_000
    assert r["peristiwa"][0]["nilai_lama"] is None
    assert r["peristiwa"][2]["selisih"] == 15_000_000
    assert r["nilai_perolehan"] == 10_000_000
    # Nilai terkini = revaluasi (25 jt); yang informasional (30 jt) diabaikan
    assert r["nilai_terkini"] == 25_000_000
    assert r["jumlah_koreksi"] == 3
    assert r["peristiwa"][3]["informasional"] is True
    # Tanpa koreksi → nilai terkini = perolehan
    kosong = susun_riwayat_nilai(aset, [])
    assert kosong["nilai_terkini"] == 10_000_000 and kosong["jumlah_koreksi"] == 0
    assert susun_riwayat_nilai({}, [])["nilai_perolehan"] == 0


def test_baris_csv_koreksi():
    from penilaian_utils import HEADER_CSV_KOREKSI, baris_csv_koreksi
    # Daftar kosong → hanya header
    assert baris_csv_koreksi([]) == [HEADER_CSV_KOREKSI]
    assert baris_csv_koreksi(None) == [HEADER_CSV_KOREKSI]
    rows = baris_csv_koreksi([{
        "asset_code": "3020101001", "NUP": "1", "asset_name": "Mobil Dinas",
        "jenis": "revaluasi", "jenis_dokumen": "lhip",
        "nomor_dokumen": "LHIP-1", "tanggal_dokumen": "2023-12-01T00:00",
        "nilai_lama": 10_000_000.4, "nilai_baru": 25_000_000.6,
        "dampak_masa_manfaat": "tetap", "masa_manfaat_semester": 0,
        "penilai_pelaksana": "KPKNL", "status_sakti": "tercatat_sakti",
        "catatan": "sesuai LHIP", "created_by": "admin",
    }])
    assert rows[0] == HEADER_CSV_KOREKSI
    r = rows[1]
    # Kode jenis/dokumen/SAKTI diterjemahkan ke label
    assert r[3] == "Revaluasi / penilaian kembali"
    assert r[4].startswith("LHIP")
    assert r[13] == "Sudah divalidasi & di-approve di SAKTI"
    # Tanggal dipangkas 10 char; nilai dibulatkan; selisih = baru - lama
    assert r[6] == "2023-12-01"
    assert r[7] == 10_000_000 and r[8] == 25_000_001
    assert r[9] == 15_000_001
    # Field hilang → string kosong, bukan None
    kosong = baris_csv_koreksi([{"jenis": "koreksi_pencatatan"}])[1]
    assert kosong[0] == "" and kosong[7] == 0 and kosong[9] == 0
