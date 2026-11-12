"""Tautan penyedia transaksi MASUK persediaan ke direktori instansi luar
(PGW-11).

- Tautan eksplisit tersimpan di jurnal & LPB; id tak dikenal → 400 SEBELUM
  stok berubah.
- Tanpa tautan eksplisit, penerimaan yang merujuk perolehan Pengadaan
  tertaut mewarisi tautan pihak perolehan itu.
- Jurnal tetap ramping: tanpa tautan, field tautan tidak ditulis.
- Jurnal & LPB terdaftar sebagai perujuk (instansi tak bisa dihapus).
"""
import pytest
from fastapi import HTTPException

import routes.persediaan as rps
import tautan_instansi as ti
from test_lpb_persediaan_ppk import USER, _jalan, _seed, _unwrap, dbx  # noqa: F401

PT = {"id": "pt1", "nama": "PT Sumber Rejeki", "kelompok": "pihak_ketiga", "tataran": "",
      "jenis": "badan_usaha_swasta", "aktif": True}
KOP = {"id": "kop1", "nama": "Koperasi Lama", "kelompok": "pihak_ketiga", "tataran": "",
       "jenis": "koperasi", "aktif": False}


def _isi(dbx, tautkan_perolehan=False):
    _jalan(_seed(dbx))
    _jalan(dbx.instansi_luar.insert_many([dict(PT), dict(KOP)]))
    if tautkan_perolehan:
        _jalan(dbx.pengadaan.update_one({"id": "perol-1"}, {"$set": {
            "pihak_instansi_id": "pt1", "pihak_kelompok": "pihak_ketiga",
            "pihak_tataran": "", "pihak_jenis_instansi": "badan_usaha_swasta"}}))


def _masuk(**kw):
    dasar = dict(jenis="pembelian", jumlah=5, harga_satuan=55_000, penyedia="CV Lokal")
    dasar.update(kw)
    return _jalan(_unwrap(rps.transaksi_masuk)("psd-1", rps.TransaksiMasukIn(**dasar), user=USER))


def _massal(**kw):
    dasar = dict(arah="masuk", jenis="pembelian", no_bukti="LPB-9", jenis_dokumen="Kuitansi",
                 tgl_dokumen="2026-03-10", penyedia="PT Sumber Rejeki", booking_otomatis=False,
                 items=[rps.ItemMassalIn(persediaan_id="psd-1", jumlah=3, harga_satuan=55_000)])
    dasar.update(kw)
    return _jalan(_unwrap(rps.transaksi_massal)(rps.TransaksiMassalIn(**dasar), user=USER))


def test_tanpa_tautan_jurnal_tetap_ramping(dbx):
    _isi(dbx)
    r = _masuk()
    assert r["peringatan_kebijakan"] == []
    assert not any(k.startswith("penyedia_") for k in r["transaksi"])


def test_tautan_eksplisit_tersimpan_di_jurnal(dbx):
    _isi(dbx)
    r = _masuk(penyedia="PT Sumber Rejeki", penyedia_instansi_id="pt1")
    j = _jalan(dbx.transaksi_persediaan.find_one({"id": r["transaksi"]["id"]}, {"_id": 0}))
    assert (j["penyedia"], j["penyedia_instansi_id"], j["penyedia_kelompok"]) == (
        "PT Sumber Rejeki", "pt1", "pihak_ketiga")


def test_tautan_patah_400_sebelum_stok_berubah(dbx):
    _isi(dbx)
    with pytest.raises(HTTPException) as e:
        _masuk(penyedia_instansi_id="hantu")
    assert e.value.status_code == 400
    item = _jalan(dbx.persediaan.find_one({"id": "psd-1"}))
    assert item["stok"] == 0 and item["batches"] == []
    assert _jalan(dbx.transaksi_persediaan.count_documents({})) == 0


def test_warisan_dari_perolehan_pengadaan_tertaut(dbx):
    _isi(dbx, tautkan_perolehan=True)
    r = _masuk(perolehan_id="perol-1", penyedia="PT Sumber Rejeki")
    assert (r["transaksi"]["penyedia_instansi_id"], r["transaksi"]["penyedia_jenis_instansi"]) == (
        "pt1", "badan_usaha_swasta")


def test_tautan_eksplisit_mengalahkan_warisan_dan_nonaktif_diperingatkan(dbx):
    _isi(dbx, tautkan_perolehan=True)
    r = _masuk(perolehan_id="perol-1", penyedia_instansi_id="kop1")
    assert r["transaksi"]["penyedia_instansi_id"] == "kop1"
    assert r["peringatan_kebijakan"] == ["Instansi penyedia ini berstatus nonaktif di direktori"]


def test_massal_menautkan_jurnal_dan_lpb_serta_menolak_di_muka(dbx):
    _isi(dbx)
    h = _massal(penyedia_instansi_id="pt1")
    assert h["sukses"] == 1 and "peringatan_kebijakan" not in h
    lpb = _jalan(dbx.lpb.find_one({"id": h["lpb_id"]}, {"_id": 0}))
    assert lpb["penyedia_instansi_id"] == "pt1"
    j = _jalan(dbx.transaksi_persediaan.find_one({"no_bukti": "LPB-9"}, {"_id": 0}))
    assert j["penyedia_instansi_id"] == "pt1"
    with pytest.raises(HTTPException) as e:
        _massal(penyedia_instansi_id="hantu", no_bukti="LPB-10")
    assert e.value.status_code == 400
    assert _jalan(dbx.transaksi_persediaan.count_documents({"no_bukti": "LPB-10"})) == 0


def test_jurnal_dan_lpb_terdaftar_sebagai_perujuk(dbx):
    _isi(dbx)
    _massal(penyedia_instansi_id="pt1")
    assert _jalan(ti.modul_perujuk(dbx, "pt1")) == ["Persediaan", "LPB persediaan"]
