"""Uji grid stiker optimal (memenuhi seluruh ruang kertas) — murni."""
from stiker_utils import (GAP_MM, MARGIN_MM, TARGET_STIKER, grid_optimal,
                          kelompokkan_per_ukuran)

A4 = (210.0, 297.0)
A3 = (297.0, 420.0)


def _cek_penuh(page, kolom, baris, lw, lh):
    """Grid harus mengisi PENUH area cetak (sisa hanya margin+gap)."""
    w_total = kolom * lw + (kolom - 1) * GAP_MM
    h_total = baris * lh + (baris - 1) * GAP_MM
    assert abs(w_total - (page[0] - 2 * MARGIN_MM)) < 0.01
    assert abs(h_total - (page[1] - 2 * MARGIN_MM)) < 0.01


def test_grid_optimal_a4():
    t = TARGET_STIKER
    k, b, lw, lh = grid_optimal(*A4, t["besar"]["w"], t["besar"]["h"])
    assert (k, b) == (2, 6) and abs(lw - 98.25) < 0.01 and abs(lh - 46.25) < 0.01
    _cek_penuh(A4, k, b, lw, lh)
    k, b, lw, lh = grid_optimal(*A4, t["sedang"]["w"], t["sedang"]["h"])
    assert (k, b) == (3, 9)
    _cek_penuh(A4, k, b, lw, lh)
    k, b, lw, lh = grid_optimal(*A4, t["kecil"]["w"], t["kecil"]["h"])
    assert (k, b) == (4, 12)
    _cek_penuh(A4, k, b, lw, lh)


def test_grid_optimal_a3_lebih_padat():
    t = TARGET_STIKER
    hasil = {}
    for u in ("besar", "sedang", "kecil"):
        k, b, lw, lh = grid_optimal(*A3, t[u]["w"], t[u]["h"])
        _cek_penuh(A3, k, b, lw, lh)
        hasil[u] = k * b
        # dimensi label tidak melenceng jauh dari target (±20%)
        assert abs(lw - t[u]["w"]) / t[u]["w"] < 0.2
        assert abs(lh - t[u]["h"]) / t[u]["h"] < 0.2
    assert hasil["besar"] == 27   # 3x9 — jauh melebihi 16 grid lama
    assert hasil["sedang"] == 65  # 5x13
    assert hasil["kecil"] == 102  # 6x17


def test_grid_optimal_kertas_kecil_tetap_satu():
    k, b, lw, lh = grid_optimal(80, 60, 95, 45)
    assert k == 1 and b == 1 and lw > 0 and lh > 0


def test_kelompokkan_per_ukuran():
    aset = [
        {"id": "1", "stiker_ukuran": "kecil"},
        {"id": "2", "stiker_ukuran": "besar"},
        {"id": "3"},                       # kosong → default sedang
        {"id": "4", "stiker_ukuran": "aneh"},  # tak dikenal → default
        {"id": "5", "stiker_ukuran": "BESAR"},  # case-insensitive
    ]
    hasil = kelompokkan_per_ukuran(aset)
    urutan = [u for u, _ in hasil]
    assert urutan == ["besar", "sedang", "kecil"]
    peta = dict(hasil)
    assert [a["id"] for a in peta["besar"]] == ["2", "5"]
    assert [a["id"] for a in peta["sedang"]] == ["3", "4"]
    assert [a["id"] for a in peta["kecil"]] == ["1"]
    assert kelompokkan_per_ukuran([]) == []
