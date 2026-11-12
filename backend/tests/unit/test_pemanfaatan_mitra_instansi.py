"""Tautan mitra Pemanfaatan ke direktori instansi luar (PGW-11).

Pola aditif: teks `mitra` tetap tersimpan sebagai snapshot; tautan opsional;
skema yang tak lazim bagi jenis mitranya hanya PERINGATAN — keputusan sahnya
tetap pada persetujuan Pengelola Barang.
"""
import pytest
from fastapi import HTTPException

import routes.pemanfaatan as rp
from test_pemanfaatan_usulan import ADMIN, USER, _hari, _jalan, _unwrap, dbx  # noqa: F401

INSTANSI = [
    {"id": "kab1", "nama": "Kabupaten Penajam Paser Utara", "kelompok": "eksternal",
     "tataran": "daerah", "jenis": "pemerintah_kabkota", "aktif": True},
    {"id": "pt1", "nama": "PT Mitra Sarana", "kelompok": "pihak_ketiga", "tataran": "",
     "jenis": "badan_usaha_swasta", "aktif": True},
    {"id": "kop1", "nama": "Koperasi Lama", "kelompok": "pihak_ketiga", "tataran": "",
     "jenis": "koperasi", "aktif": False},
]


def _payload(**kw):
    dasar = {"bentuk": "pinjam_pakai", "mitra": "Pemkab PPU", "mulai": _hari(1),
             "berakhir": _hari(300), "nomor_persetujuan": "S-1/KNL/2026",
             "nomor_perjanjian": "PJ-1/2026"}
    dasar.update(kw)
    return rp.PemanfaatanIn(**dasar)


def _isi(dbx):
    _jalan(dbx.instansi_luar.insert_many([dict(i) for i in INSTANSI]))


def test_tautan_sah_disimpan_tanpa_peringatan_dan_teks_tetap(dbx):
    _isi(dbx)
    r = _jalan(_unwrap(rp.buat_pemanfaatan)(_payload(mitra_instansi_id="kab1"), user=USER))
    assert r["peringatan_kebijakan"] == []
    assert r["mitra"] == "Pemkab PPU"    # snapshot teks tak ditimpa nama direktori
    simpan = _jalan(dbx.pemanfaatan.find_one({"id": r["id"]}, {"_id": 0}))
    assert (simpan["mitra_instansi_id"], simpan["mitra_kelompok"], simpan["mitra_tataran"],
            simpan["mitra_jenis_instansi"]) == ("kab1", "eksternal", "daerah",
                                                "pemerintah_kabkota")
    assert "peringatan_kebijakan" not in simpan


def test_skema_tak_lazim_hanya_peringatan_bukan_penolakan(dbx):
    _isi(dbx)
    r = _jalan(_unwrap(rp.buat_pemanfaatan)(
        _payload(mitra="PT Mitra Sarana", mitra_instansi_id="pt1"), user=USER))
    assert r["id"] and len(r["peringatan_kebijakan"]) == 1
    assert "Pinjam pakai" in r["peringatan_kebijakan"][0] and "Sewa" in r["peringatan_kebijakan"][0]
    kspi = _jalan(_unwrap(rp.buat_pemanfaatan)(
        _payload(bentuk="kspi", mitra="PT Mitra Sarana", mitra_instansi_id="pt1"), user=USER))
    assert kspi["peringatan_kebijakan"] == [
        "KSPI hanya bagi badan usaha berbentuk perseroan terbatas (PT)"]


def test_instansi_nonaktif_diperingatkan(dbx):
    _isi(dbx)
    r = _jalan(_unwrap(rp.buat_pemanfaatan)(
        _payload(bentuk="sewa", mitra="Koperasi Lama", mitra_instansi_id="kop1",
                 ntpn="NTPN123"), user=USER))
    assert any("nonaktif" in p for p in r["peringatan_kebijakan"])


def test_tautan_patah_ditolak_dan_tanpa_tautan_perilaku_lama(dbx):
    with pytest.raises(HTTPException) as e:
        _jalan(_unwrap(rp.buat_pemanfaatan)(_payload(mitra_instansi_id="hilang"), user=USER))
    assert e.value.status_code == 400 and "direktori" in e.value.detail
    r = _jalan(_unwrap(rp.buat_pemanfaatan)(_payload(), user=USER))
    assert r["peringatan_kebijakan"] == [] and r["mitra_instansi_id"] == ""


def test_ubah_memperbarui_dan_melepas_tautan(dbx):
    _isi(dbx)
    r = _jalan(_unwrap(rp.buat_pemanfaatan)(_payload(mitra_instansi_id="kab1"), user=USER))
    lepas = _jalan(_unwrap(rp.ubah_pemanfaatan)(r["id"], _payload(), user=USER))
    assert lepas["mitra_instansi_id"] == "" and lepas["mitra_kelompok"] == ""


def test_usulan_baru_membawa_tautan_sampai_menjadi_perjanjian(dbx):
    _isi(dbx)

    async def skenario():
        u = await _unwrap(rp.buat_usulan_pemanfaatan)(rp.UsulanPemanfaatanIn(
            jenis="baru", bentuk="pinjam_pakai", mitra="Pemkab PPU",
            mitra_instansi_id="kab1", mulai=_hari(10), berakhir=_hari(300)), user=USER)
        assert u["mitra_kelompok"] == "eksternal" and u["peringatan_kebijakan"] == []
        for status, nomor in (("diajukan", "ND-7/2026"), ("disetujui", "S-88/KNL/2026"),
                              ("perjanjian", "PJ-88/2026")):
            await _unwrap(rp.transisi_usulan_pemanfaatan)(
                u["id"], rp.TransisiUsulanPemanfaatanIn(status=status, nomor_dokumen=nomor),
                admin=ADMIN)
        p = await dbx.pemanfaatan.find_one({"usulan_id": u["id"]}, {"_id": 0})
        assert (p["mitra_instansi_id"], p["mitra_tataran"]) == ("kab1", "daerah")
    _jalan(skenario())
