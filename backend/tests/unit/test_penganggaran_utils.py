"""Uji logika murni register usulan penganggaran (PMK 62/2023 + 153/2021)."""
import pytest

from penganggaran_utils import (
    AKUN_BAS, JENIS_ANGGARAN, STATUS_ANGGARAN, TRANSISI_ANGGARAN,
    rekap_anggaran, sanding_per_akun, validate_transisi_anggaran,
    validate_usulan_anggaran,
)


def _u(**over):
    base = {"jenis": "pemeliharaan", "uraian": "Servis besar genset",
            "tahun_anggaran": "2027", "nilai_usulan": 25_000_000,
            "akun": "523", "status": "diusulkan"}
    base.update(over)
    return base


def test_validasi_usulan():
    assert validate_usulan_anggaran(_u()) == []
    assert any("Jenis" in e for e in validate_usulan_anggaran(_u(jenis="belanja")))
    assert any("Uraian" in e for e in validate_usulan_anggaran(_u(uraian=" ")))
    assert any("Tahun" in e for e in validate_usulan_anggaran(_u(tahun_anggaran="27")))
    assert any("lebih dari 0" in e
               for e in validate_usulan_anggaran(_u(nilai_usulan=0)))
    assert any("Akun" in e for e in validate_usulan_anggaran(_u(akun="521")))
    # Akun harus sesuai jenis: pemeliharaan ≠ 53x, pengadaan ≠ 523
    assert any("tidak sesuai jenis" in e
               for e in validate_usulan_anggaran(_u(akun="532")))
    assert validate_usulan_anggaran(
        _u(jenis="pengadaan", akun="532")) == []
    assert validate_usulan_anggaran(_u(akun="")) == []  # akun opsional


def test_transisi_nilai_wajib_per_tahap():
    u = _u()
    assert any("Nilai disetujui" in e
               for e in validate_transisi_anggaran(u, "disetujui_telaah", {}))
    assert validate_transisi_anggaran(
        u, "disetujui_telaah", {"nilai_disetujui": 20_000_000}) == []
    assert validate_transisi_anggaran(u, "ditolak", {}) == []
    # Tidak boleh lompat langsung ke DIPA/realisasi
    assert any("tidak sah" in e
               for e in validate_transisi_anggaran(u, "masuk_dipa", {}))
    u2 = _u(status="disetujui_telaah")
    errs = validate_transisi_anggaran(u2, "masuk_dipa", {"nilai_dipa": 1})
    assert any("Nomor DIPA" in e for e in errs)
    assert validate_transisi_anggaran(
        u2, "masuk_dipa", {"nomor_dipa": "DIPA-1/2027", "nilai_dipa": 18_000_000}) == []
    u3 = _u(status="masuk_dipa")
    assert any("realisasi" in e
               for e in validate_transisi_anggaran(u3, "terealisasi", {}))
    assert validate_transisi_anggaran(
        u3, "terealisasi", {"nilai_realisasi": 17_500_000}) == []
    # Status final tak punya jalan keluar; registry konsisten
    assert TRANSISI_ANGGARAN["terealisasi"] == set()
    assert TRANSISI_ANGGARAN["ditolak"] == set()
    for dari, tujuan in TRANSISI_ANGGARAN.items():
        assert dari in STATUS_ANGGARAN and tujuan <= set(STATUS_ANGGARAN)


def test_rekap_dan_serapan():
    items = [
        _u(nilai_usulan=10_000_000),
        _u(jenis="pengadaan", akun="532", status="masuk_dipa",
           nilai_usulan=50_000_000, nilai_disetujui=40_000_000,
           nilai_dipa=40_000_000),
        _u(status="terealisasi", nilai_usulan=20_000_000,
           nilai_disetujui=20_000_000, nilai_dipa=20_000_000,
           nilai_realisasi=15_000_000),
    ]
    r = rekap_anggaran(items)
    assert r["jumlah"] == 3
    assert r["per_status"]["diusulkan"] == 1 and r["per_status"]["masuk_dipa"] == 1
    assert r["per_jenis"]["pemeliharaan"] == 2 and r["per_jenis"]["pengadaan"] == 1
    assert r["nilai"]["usulan"] == pytest.approx(80_000_000)
    assert r["nilai"]["dipa"] == pytest.approx(60_000_000)
    assert r["serapan_persen"] == pytest.approx(25.0)
    assert rekap_anggaran([])["serapan_persen"] == 0.0


def test_sanding_per_akun():
    items = [
        _u(nilai_usulan=10_000_000),                       # 523
        _u(nilai_usulan=5_000_000, nilai_dipa=4_000_000,
           nilai_realisasi=1_000_000),                     # 523
        _u(jenis="pengadaan", akun="532", nilai_usulan=50_000_000,
           nilai_dipa=40_000_000, nilai_realisasi=40_000_000),
        _u(akun="", nilai_usulan=2_000_000),               # tanpa akun
    ]
    rows = sanding_per_akun(items)
    assert [r["akun"] for r in rows] == ["523", "532", "lainnya"]
    r523 = rows[0]
    assert r523["jumlah"] == 2
    assert r523["usulan"] == pytest.approx(15_000_000)
    assert r523["dipa"] == pytest.approx(4_000_000)
    assert r523["serapan_persen"] == pytest.approx(25.0)
    r532 = rows[1]
    assert r532["label"] == AKUN_BAS["532"]
    assert r532["serapan_persen"] == pytest.approx(100.0)
    assert rows[2]["label"] == "Tanpa akun"
    assert rows[2]["serapan_persen"] == 0.0
    assert sanding_per_akun([]) == []


def test_sanding_per_triwulan():
    from penganggaran_utils import sanding_per_triwulan

    def _real(tanggal, **over):
        return _u(status="terealisasi",
                  riwayat=[{"status": "diusulkan", "tanggal": "2026-01-05"},
                           {"status": "terealisasi", "tanggal": tanggal}],
                  **over)

    items = [
        # TW I 2026: realisasi 40 dari DIPA 100
        _real("2026-02-15T10:00:00+00:00", tahun_anggaran="2026",
              nilai_dipa=100, nilai_realisasi=40),
        # TW III 2026: realisasi 60 dari DIPA 100
        _real("2026-08-01", tahun_anggaran="2026",
              nilai_dipa=100, nilai_realisasi=60),
        # Masih masuk_dipa (belum realisasi) → hanya menambah DIPA
        _u(status="masuk_dipa", tahun_anggaran="2026", nilai_dipa=50),
        # Terealisasi tanpa riwayat tanggal → masuk tanpa_triwulan
        _u(status="terealisasi", tahun_anggaran="2026",
           nilai_dipa=0, nilai_realisasi=10),
        # Tahun lain tanpa DIPA/realisasi → tidak ditampilkan
        _u(tahun_anggaran="2025"),
    ]
    rows = sanding_per_triwulan(items)
    assert [g["tahun_anggaran"] for g in rows] == ["2026"]
    g = rows[0]
    assert g["dipa"] == pytest.approx(250)
    assert g["realisasi"] == pytest.approx(110)
    assert g["tanpa_triwulan"] == 1
    assert g["serapan_persen"] == pytest.approx(44.0)
    tw1, tw2, tw3, tw4 = g["per_triwulan"]
    assert (tw1["nama"], tw1["jumlah"], tw1["realisasi"]) == ("TW I", 1, 40)
    assert tw1["serapan_kumulatif_persen"] == pytest.approx(16.0)
    assert tw2["realisasi"] == 0 and tw2["kumulatif"] == pytest.approx(40)
    assert tw3["kumulatif"] == pytest.approx(100)
    assert tw3["serapan_kumulatif_persen"] == pytest.approx(40.0)
    assert tw4["kumulatif"] == pytest.approx(100)  # tanpa_triwulan tak masuk TW
    assert sanding_per_triwulan([]) == []


def test_registry_akun():
    assert set(JENIS_ANGGARAN) == {"pengadaan", "pemeliharaan"}
    assert all(k.startswith("53") or k == "523" for k in AKUN_BAS)


class TestKalenderPenganggaran:
    def test_validasi_tahapan(self):
        from penganggaran_utils import validate_tahapan_kalender
        ok = {"nama": "Penyampaian RKBMN ke Biro", "tanggal": "2026-08-15",
              "tahun_anggaran": "2028"}
        assert validate_tahapan_kalender(ok) == []
        errors = validate_tahapan_kalender(
            {"nama": " ", "tanggal": "15-08-2026", "tahun_anggaran": "28"})
        assert len(errors) == 3

    def test_info_tenggat_tahapan(self):
        from penganggaran_utils import info_tenggat_tahapan
        t = {"tanggal": "2026-08-15"}
        info = info_tenggat_tahapan(t, "2026-08-05")
        assert info == {"tanggal": "2026-08-15", "lewat": False,
                        "sisa_hari": 10}
        lewat = info_tenggat_tahapan(t, "2026-08-20")
        assert lewat["lewat"] is True and lewat["sisa_hari"] == 0
        assert info_tenggat_tahapan({"tanggal": "x"}, "2026-08-05")["tanggal"] is None

    def test_rekap_kalender(self):
        from penganggaran_utils import rekap_kalender
        items = [{"tanggal": "2026-08-15"},   # 10 hari lagi → mendatang
                 {"tanggal": "2026-12-01"},   # >30 hari → tidak dihitung
                 {"tanggal": "2026-08-01"},   # lewat
                 {"tanggal": "rusak"}]        # tanggal invalid → diabaikan
        r = rekap_kalender(items, "2026-08-05")
        assert r == {"jumlah": 4, "lewat": 1, "mendatang_30_hari": 1}
        assert rekap_kalender([], "2026-08-05")["jumlah"] == 0
