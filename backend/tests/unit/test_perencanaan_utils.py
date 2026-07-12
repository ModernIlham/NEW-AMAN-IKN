"""Uji logika murni Perencanaan (kandidat RKBMN pemeliharaan, PMK 153/2021)."""
import pytest

from perencanaan_utils import KONDISI_LAYAK, kelayakan_rkbmn, rekap_rkbmn


def _aset(**over):
    base = {"id": "a1", "asset_code": "3060102135", "NUP": "1",
            "asset_name": "Laptop Dinas", "condition": "Baik",
            "status": "Aktif", "location": "R. Kerja"}
    base.update(over)
    return base


def test_kelayakan_baik_dan_rusak_ringan_layak():
    for k in KONDISI_LAYAK:
        ok, alasan = kelayakan_rkbmn(_aset(condition=k))
        assert ok is True and alasan == ""
    # Maintenance tetap dioperasikan → layak
    assert kelayakan_rkbmn(_aset(status="Maintenance"))[0] is True


def test_kelayakan_rusak_berat_menang_atas_status():
    ok, alasan = kelayakan_rkbmn(_aset(condition="Rusak Berat", status="Aktif"))
    assert ok is False and "penghapusan" in alasan


def test_kelayakan_nonaktif_dan_idle():
    ok, alasan = kelayakan_rkbmn(_aset(status="Nonaktif"))
    assert ok is False and "Nonaktif" in alasan
    ok, alasan = kelayakan_rkbmn(_aset(status="Idle"))
    assert ok is False and "idle" in alasan.lower()


def test_kelayakan_kondisi_kosong_diminta_lengkapi():
    ok, alasan = kelayakan_rkbmn(_aset(condition=""))
    assert ok is False and "lengkapi" in alasan.lower()


def test_rekap_pisah_urut_dan_biaya():
    assets = [
        _aset(id="a1", asset_name="AC Split", condition="Rusak Ringan"),
        _aset(id="a2", asset_name="Genset", condition="Baik"),
        _aset(id="a3", asset_name="Kursi Patah", condition="Rusak Berat"),
    ]
    biaya = {"a1": {"jumlah": 2, "total_biaya": 750_000},
             "a2": {"jumlah": 1, "total_biaya": 3_000_000}}
    r = rekap_rkbmn(assets, biaya)
    # Layak terurut biaya riwayat terbesar (bahan pertimbangan usulan)
    assert [x["id"] for x in r["layak"]] == ["a2", "a1"]
    assert r["layak"][0]["riwayat_biaya"] == pytest.approx(3_000_000)
    assert r["tidak"][0]["id"] == "a3" and "alasan" in r["tidak"][0]
    assert r["ringkasan"] == {"total": 3, "layak": 2, "tidak": 1,
                              "total_biaya_riwayat": pytest.approx(3_750_000)}


def test_rekap_kosong_aman():
    r = rekap_rkbmn([], {})
    assert r["layak"] == [] and r["tidak"] == []
    assert r["ringkasan"]["total"] == 0
