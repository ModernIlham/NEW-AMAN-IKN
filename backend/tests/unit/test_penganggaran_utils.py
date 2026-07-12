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


def test_registry_akun():
    assert set(JENIS_ANGGARAN) == {"pengadaan", "pemeliharaan"}
    assert all(k.startswith("53") or k == "523" for k in AKUN_BAS)
