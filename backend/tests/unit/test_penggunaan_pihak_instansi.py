"""Tautan pihak asal/tujuan tiket proses Penggunaan ke direktori instansi
luar (PGW-11).

Pola aditif: teks pihak tetap tersimpan; tautan opsional; skema yang tak
lazim bagi jenis PENERIMA (pihak tujuan, arah keluar) hanya PERINGATAN.
"""
import pytest
from fastapi import HTTPException

import kebijakan_penerima as kp
import routes.penggunaan as rg
from test_transfer_masuk import USER, _jalan, _unwrap, dbx  # noqa: F401

INSTANSI = [
    {"id": "kl1", "nama": "Kementerian Pekerjaan Umum", "kelompok": "eksternal",
     "tataran": "pusat", "jenis": "kementerian_lembaga", "aktif": True},
    {"id": "pt1", "nama": "PT Operator Nusantara", "kelompok": "pihak_ketiga",
     "tataran": "", "jenis": "badan_usaha_swasta", "aktif": True},
    {"id": "kop1", "nama": "Koperasi Lama", "kelompok": "pihak_ketiga", "tataran": "",
     "jenis": "koperasi", "aktif": False},
]


def _isi(dbx):
    _jalan(dbx.instansi_luar.insert_many([dict(i) for i in INSTANSI]))
    _jalan(dbx.assets.insert_one({"id": "a1", "asset_code": "3100102001", "NUP": 1,
                                  "asset_name": "Genset", "kode_satker": ""}))


def _buat(**kw):
    dasar = {"jenis_proses": "penggunaan_sementara", "arah": "keluar",
             "pihak_asal": "Otorita IKN", "pihak_tujuan": "Kemen PU",
             "asset_ids": ["a1"], "tanggal_mulai": "2026-12-01",
             "tanggal_berakhir": "2027-05-01"}
    dasar.update(kw)
    return _jalan(_unwrap(rg.buat_proses)(rg.ProsesIn(**dasar), user=USER))


def test_tanpa_tautan_perilaku_lama(dbx):
    _isi(dbx)
    r = _buat()
    assert r["peringatan_kebijakan"] == []
    simpan = _jalan(dbx.penggunaan_proses.find_one({"id": r["id"]}, {"_id": 0}))
    assert simpan["pihak_tujuan_instansi_id"] == "" and simpan["pihak_asal_kelompok"] == ""
    assert "peringatan_kebijakan" not in simpan


def test_tautan_sah_disalin_dan_teks_tetap(dbx):
    _isi(dbx)
    r = _buat(pihak_tujuan_instansi_id="kl1")
    assert r["peringatan_kebijakan"] == []
    assert r["pihak_tujuan"] == "Kemen PU"
    simpan = _jalan(dbx.penggunaan_proses.find_one({"id": r["id"]}, {"_id": 0}))
    assert (simpan["pihak_tujuan_instansi_id"], simpan["pihak_tujuan_kelompok"],
            simpan["pihak_tujuan_tataran"], simpan["pihak_tujuan_jenis_instansi"]) == (
        "kl1", "eksternal", "pusat", "kementerian_lembaga")


def test_skema_tak_lazim_pihak_tujuan_keluar_hanya_peringatan(dbx):
    _isi(dbx)
    r = _buat(pihak_tujuan="PT Operator", pihak_tujuan_instansi_id="pt1")
    assert r["id"] and len(r["peringatan_kebijakan"]) == 1
    assert "jenis pihak" in r["peringatan_kebijakan"][0]
    assert "Penggunaan sementara" in r["peringatan_kebijakan"][0]


def test_arah_masuk_tidak_memeriksa_skema(dbx):
    _isi(dbx)
    r = _jalan(_unwrap(rg.buat_proses)(rg.ProsesIn(
        jenis_proses="dioperasikan_pihak_lain", arah="masuk", pihak_asal="PT Operator",
        pihak_tujuan="Otorita IKN", pihak_tujuan_instansi_id="pt1",
        asset_ids=["a1"], tanggal_mulai="2026-12-01", tanggal_berakhir="2027-05-01"),
        user=USER))
    assert r["peringatan_kebijakan"] == []


def test_alih_status_tidak_diperiksa_tetapi_nonaktif_diperingatkan(dbx):
    _isi(dbx)
    r = _buat(jenis_proses="alih_status", pihak_tujuan="Koperasi Lama",
              pihak_tujuan_instansi_id="kop1", pihak_asal_instansi_id="kop1")
    assert r["peringatan_kebijakan"] == [
        "Instansi pihak asal ini berstatus nonaktif di direktori",
        "Instansi pihak tujuan ini berstatus nonaktif di direktori"]


def test_tautan_patah_400(dbx):
    _isi(dbx)
    with pytest.raises(HTTPException) as e:
        _buat(pihak_asal_instansi_id="hantu")
    assert e.value.status_code == 400
    assert "Pihak asal" in e.value.detail
    assert _jalan(dbx.penggunaan_proses.count_documents({})) == 0


def test_periksa_skema_sebutan_bawaan_mitra():
    assert "jenis mitra" in kp.periksa_skema("sewa", "pemerintah_provinsi")[0]
    assert kp.periksa_skema(kp.SKEMA_DARI_PROSES.get("alih_status"), "koperasi") == []
