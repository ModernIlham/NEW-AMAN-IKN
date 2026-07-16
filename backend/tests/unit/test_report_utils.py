"""Uji perhitungan murni laporan eksekutif."""
from report_utils import distribusi_pengguna, hitung_status_stiker


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


def test_distribusi_pengguna_key_nip_nama_dari_master():
    peg = {"1990": {"nip": "1990", "nama": "Budi Santoso", "unit_kerja": "Bagian Umum"}}
    aset = [
        {"pengguna_nip": "1990", "user": "Budi", "purchase_price": 1000},
        {"pengguna_nip": "1990", "user": "Budi", "purchase_price": 2000},
        {"pengguna_nip": "2001", "user": "Sari S.", "purchase_price": 5000},  # tak terdaftar
        {"pengguna_nip": "", "user": "", "purchase_price": 500},              # tanpa NIP
    ]
    rows, ringkas = distribusi_pengguna(aset, peg)
    # terurut nilai desc: 2001 (5000) > 1990 (3000) > tanpa NIP (500)
    assert [r["nip"] for r in rows] == ["2001", "1990", ""]
    b = next(r for r in rows if r["nip"] == "1990")
    assert b["nama"] == "Budi Santoso" and b["unit_kerja"] == "Bagian Umum"
    assert b["terdaftar"] is True and b["count"] == 2 and b["value"] == 3000
    # NIP 2001 tak ada di master → pakai nama dari aset, terdaftar False
    s = next(r for r in rows if r["nip"] == "2001")
    assert s["nama"] == "Sari S." and s["terdaftar"] is False
    # grup tanpa NIP
    t = next(r for r in rows if r["tanpa_nip"])
    assert t["nama"] == "Tanpa Pengguna / NIP"
    assert ringkas["jumlah_pengguna"] == 2      # 1990 & 2001
    assert ringkas["jumlah_tak_terdaftar"] == 1  # 2001
    assert ringkas["ada_tanpa_nip"] is True


def test_distribusi_pengguna_kosong():
    rows, ringkas = distribusi_pengguna([], {})
    assert rows == []
    assert ringkas == {"jumlah_pengguna": 0, "jumlah_tak_terdaftar": 0, "ada_tanpa_nip": False}
