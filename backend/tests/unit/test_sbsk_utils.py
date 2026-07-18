"""Uji SBSK (PMK 138/2024) + sanding usulan vs aset eksisting — logika murni."""
from perencanaan_utils import (
    SBSK_SEED_DEFAULT, _umur_tahun, sanding_usulan_aset, validate_sbsk,
)

ASET = [
    {"asset_code": "3020104001", "condition": "Rusak Berat",
     "purchase_date": "2015-03-01", "purchase_price": 250_000_000},
    {"asset_code": "3020104002", "condition": "Baik",
     "purchase_date": "2023-01-10", "purchase_price": 300_000_000},
    {"asset_code": "3050101001", "condition": "Baik",
     "purchase_date": "2024-06-01", "purchase_price": 15_000_000},
]


def test_validate_sbsk():
    assert validate_sbsk({"kategori": "kendaraan", "peruntukan": "Eselon II",
                          "satuan": "unit", "standar": 1}) == []
    err = validate_sbsk({"kategori": "planet", "peruntukan": "", "satuan": "",
                         "standar": 0})
    assert len(err) == 4
    assert validate_sbsk({"kategori": "barang", "peruntukan": "x",
                          "satuan": "unit", "standar": "abc"})


def test_umur_tahun():
    assert _umur_tahun("2015-03-01", "2026-07-18") == 11
    assert _umur_tahun("2015-08-01", "2026-07-18") == 10   # belum ulang tahun
    assert _umur_tahun("", "2026-07-18") is None
    assert _umur_tahun("2030-01-01", "2026-07-18") == 0    # tak pernah negatif


def test_sanding_penggantian_wajar():
    out = sanding_usulan_aset(
        {"kode_barang": "302", "uraian": "Pengadaan kendaraan dinas eselon II",
         "volume": 1},
        ASET, "2026-07-18", list(SBSK_SEED_DEFAULT))
    assert out["jumlah_eksisting"] == 2                 # hanya prefix 302
    assert out["kondisi"] == {"Rusak Berat": 1, "Baik": 1}
    assert out["nilai_eksisting"] == 550_000_000
    assert any("wajar sebagai penggantian" in c for c in out["catatan"])
    assert out["standar_relevan"]                        # match "eselon"


def test_sanding_tanpa_eksisting_dan_volume_berlebih():
    kosong = sanding_usulan_aset(
        {"kode_barang": "601", "uraian": "Koleksi", "volume": 2}, ASET,
        "2026-07-18", [])
    assert kosong["jumlah_eksisting"] == 0
    assert any("pengadaan baru" in c for c in kosong["catatan"])
    lebih = sanding_usulan_aset(
        {"kode_barang": "305", "uraian": "Komputer", "volume": 10}, ASET,
        "2026-07-18", [])
    assert any("melebihi populasi" in c for c in lebih["catatan"])
    # Tanpa kode barang → tanpa sanding otomatis, tidak crash
    polos = sanding_usulan_aset({"uraian": "x", "volume": 1}, ASET,
                                "2026-07-18", [])
    assert polos["jumlah_eksisting"] == 0 and polos["catatan"] == []
