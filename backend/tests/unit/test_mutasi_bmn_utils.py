"""Uji jurnal mutasi BMN & reklasifikasi (Gelombang 7, pustaka §2.6)."""
from mutasi_bmn_utils import (
    KODE_TRANSAKSI_BMN, arah_transaksi, buat_pasangan_reklasifikasi,
    deteksi_reklasifikasi_siman, rekap_mutasi_periode, validate_entri_mutasi,
)


def test_kode_transaksi_selaras_pustaka():
    # Kode inti SIMAK/SAKTI hadir dengan arah yang benar
    assert arah_transaksi("100") == "tambah"
    assert arah_transaksi("101") == "tambah"
    assert arah_transaksi("107") == "tambah"   # reklas masuk
    assert arah_transaksi("304") == "kurang"   # reklas keluar
    assert arah_transaksi("301") == "kurang"
    assert arah_transaksi("203") == "netral"   # perubahan kondisi
    assert arah_transaksi("999") == ""
    for k, (uraian, arah) in KODE_TRANSAKSI_BMN.items():
        assert uraian and arah in ("tambah", "kurang", "netral")


def test_validate_entri_mutasi():
    ok = {"kode_transaksi": "101", "asset_id": "a1",
          "tanggal_buku": "2026-07-17", "nilai": 1000}
    assert validate_entri_mutasi(ok) == []
    assert any("Kode transaksi" in e for e in validate_entri_mutasi(
        {**ok, "kode_transaksi": "abc"}))
    assert any("asset_id" in e for e in validate_entri_mutasi(
        {**ok, "asset_id": ""}))
    assert any("tanggal_buku" in e for e in validate_entri_mutasi(
        {**ok, "tanggal_buku": "17/07/2026"}))
    assert any("nilai" in e for e in validate_entri_mutasi(
        {**ok, "nilai": "x"}))


def test_pasangan_reklasifikasi_304_107():
    aset = {"id": "a1", "asset_code": "3050104001", "NUP": "7",
            "purchase_price": "12.500.000"}
    keluar, masuk = buat_pasangan_reklasifikasi(
        aset, "3060102001", "3", "2026-07-17", "salah golong", "opr")
    # Pasangan tak terpisahkan: periode sama, nilai bruto keluar = masuk
    assert keluar["kode_transaksi"] == "304" and masuk["kode_transaksi"] == "107"
    assert keluar["tanggal_buku"] == masuk["tanggal_buku"] == "2026-07-17"
    assert keluar["nilai"] == masuk["nilai"] > 0
    # Keluar dari kode/NUP lama; masuk ke kode/NUP baru
    assert keluar["kode_barang"] == "3050104001" and keluar["nup"] == "7"
    assert masuk["kode_barang"] == "3060102001" and masuk["nup"] == "3"
    assert "salah golong" in keluar["keterangan"]


def test_rekap_mutasi_periode():
    entries = [
        {"kode_barang": "3050104001", "kode_transaksi": "101",
         "tanggal_buku": "2026-03-01", "jumlah": 2, "nilai": 200},
        {"kode_barang": "3050104001", "kode_transaksi": "304",
         "tanggal_buku": "2026-04-01", "jumlah": 1, "nilai": 100},
        {"kode_barang": "3050104001", "kode_transaksi": "203",   # netral
         "tanggal_buku": "2026-04-02", "jumlah": 1, "nilai": 0},
        {"kode_barang": "3050104001", "kode_transaksi": "101",   # di luar periode
         "tanggal_buku": "2026-08-01", "jumlah": 5, "nilai": 500},
    ]
    r = rekap_mutasi_periode(entries, "2026-01-01", "2026-06-30")
    b = r["3050104001"]
    assert b["tambah_n"] == 2 and b["tambah_rp"] == 200
    assert b["kurang_n"] == 1 and b["kurang_rp"] == 100
    # Netral tidak menggeser saldo tetapi tercatat per jenis
    assert b["per_kode_transaksi"]["203"]["n"] == 1
    assert "3050104001" in r and len(r) == 1


def test_deteksi_reklasifikasi_siman():
    aset = {"kode_register": "1234567890123456", "asset_code": "3050104001",
            "NUP": "7"}
    # Register cocok + kode beda → sinyal reklasifikasi
    r = deteksi_reklasifikasi_siman(aset, {
        "kode_register": "1234567890123456", "kode_barang": "3060102001",
        "nup": "3"})
    assert r["kode_lama"] == "3050104001" and r["kode_baru"] == "3060102001"
    # Register cocok + kode sama → bukan reklasifikasi
    assert deteksi_reklasifikasi_siman(aset, {
        "kode_register": "1234567890123456", "kode_barang": "3050104001",
        "nup": "7"}) == {}
    # Register beda/kosong → bukan sinyal (fallback kunci kode+NUP)
    assert deteksi_reklasifikasi_siman(aset, {
        "kode_register": "9999", "kode_barang": "3060102001", "nup": "3"}) == {}
    assert deteksi_reklasifikasi_siman({}, {}) == {}
