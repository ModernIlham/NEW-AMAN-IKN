"""Uji logika murni kandidat penghapusan (PMK 83/2016)."""
import pytest

from penghapusan_utils import (
    JALUR_KANDIDAT, STATUS_USULAN, TRANSISI_USULAN, boleh_transisi,
    jalur_kandidat, rekap_kandidat, validate_transisi,
)


def _aset(**over):
    base = {"id": "a1", "asset_code": "3060102135", "NUP": "1",
            "asset_name": "Kursi Rapat", "purchase_price": 750_000,
            "condition": "Baik", "inventory_status": "Ditemukan",
            "location": "R. Rapat", "uraian_tidak_ditemukan": ""}
    base.update(over)
    return base


def test_jalur_prioritas_tidak_ditemukan_di_atas_rusak_berat():
    assert jalur_kandidat(_aset()) is None
    assert jalur_kandidat(_aset(condition="Rusak Berat")) == "rusak_berat"
    assert jalur_kandidat(_aset(inventory_status="Tidak Ditemukan")) == "tidak_ditemukan"
    # Barang tak ditemukan tidak bisa dimusnahkan — jalur penelusuran/TGR
    assert jalur_kandidat(_aset(condition="Rusak Berat",
                                inventory_status="Tidak Ditemukan")) == "tidak_ditemukan"


def test_rekap_per_jalur_nilai_dan_urutan():
    assets = [
        _aset(id="a1", condition="Rusak Berat", purchase_price=100_000),
        _aset(id="a2", condition="Rusak Berat", purchase_price=5_000_000),
        _aset(id="a3", inventory_status="Tidak Ditemukan",
              purchase_price=2_000_000, uraian_tidak_ditemukan="Hilang saat pindahan"),
        _aset(id="a4"),  # sehat — bukan kandidat
    ]
    r = rekap_kandidat(assets)
    rb = r["jalur"]["rusak_berat"]
    assert rb["jumlah"] == 2 and rb["nilai"] == pytest.approx(5_100_000)
    assert [x["id"] for x in rb["rows"]] == ["a2", "a1"]  # harga terbesar dulu
    td = r["jalur"]["tidak_ditemukan"]
    assert td["jumlah"] == 1 and td["rows"][0]["keterangan"] == "Hilang saat pindahan"
    assert r["ringkasan"] == {"jumlah": 3, "nilai": pytest.approx(7_100_000)}
    for k in JALUR_KANDIDAT:
        assert r["jalur"][k]["label"] and r["jalur"][k]["alasan"]


def test_rekap_kosong_aman():
    r = rekap_kandidat([])
    assert r["ringkasan"] == {"jumlah": 0, "nilai": 0.0}


def test_transisi_usulan_sah_dan_tidak():
    assert boleh_transisi("diusulkan", "diproses") is True
    assert boleh_transisi("diusulkan", "ditolak") is True
    assert boleh_transisi("diproses", "sk_terbit") is True
    assert boleh_transisi("diusulkan", "sk_terbit") is False  # tidak boleh lompat
    assert boleh_transisi("sk_terbit", "diusulkan") is False  # final
    assert boleh_transisi("ditolak", "diproses") is False     # final
    # Semua status transisi terdaftar di label
    for dari, tujuan in TRANSISI_USULAN.items():
        assert dari in STATUS_USULAN
        assert tujuan <= set(STATUS_USULAN)


def test_validate_transisi_sk_wajib_nomor():
    assert validate_transisi("diproses", "sk_terbit", "SK-1/2026") == []
    errs = validate_transisi("diproses", "sk_terbit", "")
    assert any("Nomor SK" in e for e in errs)
    errs = validate_transisi("diusulkan", "sk_terbit", "SK-1/2026")
    assert any("tidak sah" in e for e in errs)
    errs = validate_transisi("diusulkan", "status_aneh")
    assert any("tidak dikenal" in e for e in errs)
