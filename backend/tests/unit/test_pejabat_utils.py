"""Uji referensi pejabat penatausahaan BMN (#290, PMK 181/2016)."""
from pejabat_utils import (
    PERAN_PEJABAT, UNIT_AKUNTANSI,
    pejabat_aktif_untuk_peran, validate_pejabat,
)


def test_referensi_memuat_peran_dan_unit_inti():
    assert "kuasa_pengguna_barang" in PERAN_PEJABAT
    assert "penatausahaan_bmn" in PERAN_PEJABAT
    # Jenjang unit akuntansi PMK 181/2016 lengkap
    for k in ("uapb", "uappb_e1", "uappb_w", "uakpb", "uapkpb"):
        assert k in UNIT_AKUNTANSI and UNIT_AKUNTANSI[k]["penanggung_jawab"]


def test_validate_pejabat():
    ok = {"nama": "Budi", "peran": ["kuasa_pengguna_barang"], "unit_akuntansi": "uakpb"}
    assert validate_pejabat(ok) == []
    # nama wajib
    assert any("Nama" in e for e in validate_pejabat({"peran": ["ppk"]}))
    # peran wajib & harus dikenal
    assert any("peran" in e.lower() for e in validate_pejabat({"nama": "A", "peran": []}))
    assert any("tidak dikenal" in e for e in
               validate_pejabat({"nama": "A", "peran": ["operator_ajaib"]}))
    # unit akuntansi tak dikenal
    assert any("Unit akuntansi" in e for e in
               validate_pejabat({"nama": "A", "peran": ["ppk"], "unit_akuntansi": "xxx"}))
    # rentang tanggal terbalik
    assert any("berlaku" in e for e in validate_pejabat(
        {"nama": "A", "peran": ["ppk"],
         "berlaku_mulai": "2026-12-31", "berlaku_selesai": "2026-01-01"}))


def _pj(nama, peran, mulai="", selesai="", aktif=True):
    return {"nama": nama, "peran": peran, "berlaku_mulai": mulai,
            "berlaku_selesai": selesai, "aktif": aktif}


def test_pejabat_aktif_untuk_peran():
    daftar = [
        _pj("KPB Lama", ["kuasa_pengguna_barang"], "2023-01-01", "2025-06-30"),
        _pj("KPB Baru", ["kuasa_pengguna_barang"], "2025-07-01", ""),
        _pj("Operator", ["penatausahaan_bmn"], "2024-01-01", ""),
        _pj("Nonaktif", ["kuasa_pengguna_barang"], "2026-01-01", "", aktif=False),
    ]
    # Tanggal 2026 → KPB Baru (SK terbaru & masih berlaku); nonaktif diabaikan
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2026-07-16")
    assert pj and pj["nama"] == "KPB Baru"
    # Tanggal 2024 → KPB Lama (KPB Baru belum berlaku)
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2024-05-01")
    assert pj and pj["nama"] == "KPB Lama"
    # Peran lain
    assert pejabat_aktif_untuk_peran(daftar, "penatausahaan_bmn", "2026-07-16")["nama"] == "Operator"
    # Peran tanpa pejabat → None
    assert pejabat_aktif_untuk_peran(daftar, "ppk", "2026-07-16") is None
    # Rentang kosong = terbuka; input kosong aman
    assert pejabat_aktif_untuk_peran([], "ppk", None) is None
