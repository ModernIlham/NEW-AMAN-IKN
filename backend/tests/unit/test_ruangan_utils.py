"""Uji master referensi ruangan (fondasi KIR/DBR)."""
import pytest
from ruangan_utils import kelompok_dbr, ringkas_lokasi, ruangan_aset, validate_ruangan


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


def test_ruangan_aset():
    # melekat ke Ruangan → nama ruangan di 'user'
    assert ruangan_aset({"operasional_jenis": "Ruangan", "user": "R.101",
                         "location": "Gedung A"}) == "R.101"
    # selain itu → location teks bebas
    assert ruangan_aset({"location": "Gudang Utama"}) == "Gudang Utama"
    # kosong → penanda, aset tak hilang dari DBR
    assert ruangan_aset({}) == "(lokasi belum dicatat)"


def test_kelompok_dbr():
    assets = [
        {"asset_name": "Meja", "location": "R.101", "purchase_price": "1000000"},
        {"asset_name": "Kursi", "location": "R.101", "purchase_price": "500000"},
        {"asset_name": "AC", "operasional_jenis": "Ruangan", "user": "R.202",
         "purchase_price": "3000000"},
        {"asset_name": "Entah", "purchase_price": "0"},  # tanpa lokasi
    ]
    rows = kelompok_dbr(assets)
    assert [r["ruangan"] for r in rows] == ["R.101", "R.202", "(lokasi belum dicatat)"]
    r101 = rows[0]
    assert r101["jumlah"] == 2 and r101["nilai"] == pytest.approx(1_500_000)
    assert rows[1]["jumlah"] == 1 and rows[1]["nilai"] == pytest.approx(3_000_000)
    # "(lokasi belum dicatat)" selalu terakhir
    assert rows[-1]["ruangan"] == "(lokasi belum dicatat)" and rows[-1]["jumlah"] == 1
    assert kelompok_dbr([]) == []
