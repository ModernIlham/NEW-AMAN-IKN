"""Uji perhitungan murni laporan eksekutif."""
from report_utils import hitung_status_stiker


def test_hitung_status_stiker_atas_semua_aset():
    aset = [
        {"stiker_status": "Sudah Terpasang", "inventory_status": "Ditemukan"},
        {"stiker_status": "Belum Terpasang", "inventory_status": "Ditemukan"},
        {"stiker_status": "Belum Terpasang", "inventory_status": "Belum Diinventarisasi"},
        {"inventory_status": "Belum Diinventarisasi"},  # stiker_status kosong → belum
    ]
    terpasang, belum, pct = hitung_status_stiker(aset)
    assert terpasang == 1
    assert belum == 3          # bug lama: 0 karena hanya menghitung 'Ditemukan'
    assert pct == 25           # 1/4


def test_hitung_status_stiker_kosong_dan_none_aman():
    assert hitung_status_stiker([]) == (0, 0, 0)
    assert hitung_status_stiker(None) == (0, 0, 0)
    assert hitung_status_stiker([None, {}]) == (0, 2, 0)


def test_hitung_status_stiker_semua_terpasang():
    aset = [{"stiker_status": "Sudah Terpasang"} for _ in range(3)]
    assert hitung_status_stiker(aset) == (3, 0, 100)
