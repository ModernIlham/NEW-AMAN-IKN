"""Uji master referensi ruangan (fondasi KIR/DBR)."""
from ruangan_utils import ringkas_lokasi, validate_ruangan


def test_validate_ruangan():
    assert validate_ruangan({"kode_ruangan": "R.101", "nama_ruangan": "Ruang Rapat"}) == []
    assert any("Kode ruangan" in e for e in validate_ruangan({"nama_ruangan": "X"}))
    assert any("Nama ruangan" in e for e in validate_ruangan({"kode_ruangan": "R.1"}))
    # dua-duanya kosong → dua error
    assert len(validate_ruangan({})) == 2


def test_ringkas_lokasi():
    full = {"gedung": "Gedung A", "lantai": "2", "kode_ruangan": "R.101",
            "nama_ruangan": "Ruang Rapat"}
    assert ringkas_lokasi(full) == "Gedung A · Lt. 2 · R.101 — Ruang Rapat"
    # sebagian: tanpa gedung/lantai
    assert ringkas_lokasi({"kode_ruangan": "R.9", "nama_ruangan": "Gudang"}) == "R.9 — Gudang"
    # hanya nama
    assert ringkas_lokasi({"nama_ruangan": "Lobi"}) == "Lobi"
    # aman untuk kosong/None
    assert ringkas_lokasi({}) == "" and ringkas_lokasi(None) == ""
