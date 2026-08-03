"""Uji FILTER LAPORAN EKSEKUTIF (routes/reports.py).

Mengunci janji fitur: filter yang aktif di layar ikut menyaring Laporan
Eksekutif / Barang Serupa / Data Aset, memakai builder query yang SAMA
dengan daftar aset (tak boleh drift), dan ringkasannya tercetak di laporan.
"""
import pytest

from routes.reports import (FilterLaporan, filter_laporan,
                            filter_laporan_dari_map)


def test_tanpa_filter_kosong_dan_tak_aktif():
    f = filter_laporan_dari_map({})
    assert f.query == {}
    assert f.aktif is False
    assert f.ringkasan == ""


def test_filter_sederhana_jadi_query_dan_ringkasan():
    f = filter_laporan_dari_map({
        "condition": "Rusak Berat", "inventory_status": "Ditemukan"})
    assert f.aktif is True
    assert f.query["condition"] == "Rusak Berat"
    assert f.query["inventory_status"] == "Ditemukan"
    assert "Kondisi: Rusak Berat" in f.ringkasan
    assert "Status Inventarisasi: Ditemukan" in f.ringkasan


def test_activity_id_tak_pernah_ikut_dari_filter():
    # Laporan SELALU per kegiatan dari path param; filter tak boleh
    # menyisipkan activity_id lain (cegah lintas-kegiatan).
    f = filter_laporan_dari_map({"activity_id": "kegiatan-lain",
                                 "condition": "Baik"})
    assert "activity_id" not in f.query
    assert f.query["condition"] == "Baik"


def test_rentang_harga_dan_tanggal():
    f = filter_laporan_dari_map({"price_min": "1000000", "price_max": "5000000",
                                 "beli_dari": "2026-01-01",
                                 "beli_sampai": "2026-06-30"})
    # Harga dibandingkan via $expr + $convert (harga bisa tersimpan sebagai
    # string) — bentuk ini datang dari builder bersama, bukan disalin di sini.
    teks = str(f.query.get("$expr"))
    assert "1000000" in teks and "5000000" in teks and "purchase_price" in teks
    assert f.query["purchase_date"] == {"$gte": "2026-01-01", "$lte": "2026-06-30"}
    assert "Harga ≥: 1000000" in f.ringkasan and "Tgl beli ≤: 2026-06-30" in f.ringkasan


def test_harga_bukan_angka_diabaikan_bukan_error():
    f = filter_laporan_dari_map({"price_min": "abc"})
    assert "purchase_price" not in f.query


def test_lokasi_eselon_pakai_regex_literal_aman():
    f = filter_laporan_dari_map({"location": "Ruang A+B (1)",
                                 "eselon1_filter": "Kedeputian"})
    # Nilai di-escape sebagai regex literal — karakter khusus tak meledak.
    assert "location" in f.query and "eselon1" in f.query
    pola = f.query["location"]["$regex"]
    assert r"\+" in pola and r"\(1\)" in pola   # '+' & '(' jadi literal
    assert f.query["eselon1"]["$regex"] == "Kedeputian"


def test_dependency_menghasilkan_objek_yang_sama():
    f = filter_laporan(condition="Baik", location="Gudang")
    assert isinstance(f, FilterLaporan)
    assert f.query["condition"] == "Baik"
    assert f.aktif is True
    # Parameter kosong tak boleh menambah kunci apa pun.
    assert set(f.query) == {"condition", "location"}


def test_pencarian_terlalu_pendek_diabaikan():
    # Builder bersama menolak kata kunci < 2 huruf (cegah pindai penuh).
    assert filter_laporan_dari_map({"search": "a"}).query == {}
    assert "$or" in filter_laporan_dari_map({"search": "lenovo"}).query
