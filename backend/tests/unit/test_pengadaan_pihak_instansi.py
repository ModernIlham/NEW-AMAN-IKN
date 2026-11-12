"""Tautan pihak register perolehan ke direktori instansi luar (PGW-11).

- Teks `pihak` tetap tersimpan; tautan opsional; tanpa pemeriksaan skema.
- Tautan ikut TERKUNCI bersama identitas dokumen (BAST PPK terbit / LPB).
- Tautan yang tidak berubah saat ubah dipertahankan tanpa ditanyakan ulang ke
  direktori — mengubah keterangan tak boleh gagal karena instansinya sudah
  tidak ada.
"""
import pytest
from fastapi import HTTPException

import routes.pengadaan as rp
from test_pengadaan_ubah import USER, _catat, _jalan, _payload, _unwrap, dbx  # noqa: F401

PT = {"id": "pt1", "nama": "PT Sumber Rejeki", "kelompok": "pihak_ketiga", "tataran": "",
      "jenis": "badan_usaha_swasta", "aktif": True}
KOP = {"id": "kop1", "nama": "Koperasi Lama", "kelompok": "pihak_ketiga", "tataran": "",
       "jenis": "koperasi", "aktif": False}


def _isi(dbx):
    _jalan(dbx.instansi_luar.insert_many([dict(PT), dict(KOP)]))


def _baru(**kw):
    dasar = dict(jenis="pembelian", pihak="PT Sumber Rejeki", nomor_bast="BAST-9/2026",
                 tanggal_bast="2026-03-10",
                 barang=[rp.BarangIn(uraian="Printer", kode="3050102001", jumlah=1,
                                     harga_satuan=2_500_000)])
    dasar.update(kw)
    return _jalan(_unwrap(rp.buat_perolehan)(rp.PerolehanIn(**dasar), user=USER))


def test_buat_dengan_tautan_menyalin_snapshot(dbx):
    _isi(dbx)
    r = _baru(pihak_instansi_id="pt1")
    assert r["peringatan_kebijakan"] == [] and r["pihak"] == "PT Sumber Rejeki"
    simpan = _jalan(dbx.pengadaan.find_one({"id": r["id"]}, {"_id": 0}))
    assert (simpan["pihak_instansi_id"], simpan["pihak_kelompok"],
            simpan["pihak_jenis_instansi"]) == ("pt1", "pihak_ketiga", "badan_usaha_swasta")
    assert "peringatan_kebijakan" not in simpan


def test_buat_nonaktif_peringatan_dan_tautan_patah_400(dbx):
    _isi(dbx)
    assert _baru(pihak_instansi_id="kop1")["peringatan_kebijakan"] == [
        "Instansi pihak ini berstatus nonaktif di direktori"]
    with pytest.raises(HTTPException) as e:
        _baru(pihak_instansi_id="hantu", nomor_bast="BAST-10/2026")
    assert e.value.status_code == 400


def test_ubah_mempertahankan_tautan_lama_walau_instansi_sudah_tiada(dbx):
    _jalan(_catat(dbx, pihak_instansi_id="hilang", pihak_kelompok="pihak_ketiga",
                  pihak_tataran="", pihak_jenis_instansi="koperasi"))
    r = _jalan(_unwrap(rp.ubah_perolehan)("p1", _payload(
        keterangan="dirapikan", pihak_instansi_id="hilang"), user=USER))
    assert r["keterangan"] == "dirapikan"
    simpan = _jalan(dbx.pengadaan.find_one({"id": "p1"}, {"_id": 0}))
    assert (simpan["pihak_instansi_id"], simpan["pihak_jenis_instansi"]) == ("hilang", "koperasi")


def test_ubah_menautkan_dan_mencatat_audit(dbx, monkeypatch):
    _isi(dbx)
    _jalan(_catat(dbx))
    jejak = []

    async def _rekam(*a, **k):
        jejak.append(k.get("changes"))
    monkeypatch.setattr(rp, "log_audit", _rekam)
    _jalan(_unwrap(rp.ubah_perolehan)("p1", _payload(pihak_instansi_id="pt1"), user=USER))
    assert {"field": "pihak_instansi_id", "from": "", "to": "pt1"} in jejak[0]


def test_tautan_terkunci_bersama_identitas_setelah_bast_ppk(dbx):
    _isi(dbx)
    _jalan(_catat(dbx, bast_ppk={"nomor": "BAST-PPK/1"}))
    with pytest.raises(HTTPException) as e:
        _jalan(_unwrap(rp.ubah_perolehan)("p1", _payload(pihak_instansi_id="pt1", barang=None),
                                          user=USER))
    assert e.value.status_code == 409 and "pihak_instansi_id" in e.value.detail
