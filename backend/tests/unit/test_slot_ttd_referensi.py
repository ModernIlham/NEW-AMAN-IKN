"""Slot tanda tangan DILAYANI dari `/pejabat/referensi`, bukan disalin ke layar.

Layar Master Satker & penerbitan LPB memakai daftar slot dari endpoint ini.
Kalau daftarnya diam-diam hilang atau kehilangan label/peran, dropdown-nya
tetap terender tapi tanpa keterangan — operator memilih tanpa tahu slot itu
apa. Uji ini menagih bentuknya, bukan sekadar keberadaannya.
"""
import asyncio

import routes.pejabat as rp
from penandatangan_dokumen import KUNCI_SLOT, SLOT_TTD
from pejabat_utils import PERAN_PEJABAT


def _referensi():
    return asyncio.run(rp.referensi_pejabat(_user={"role": "admin"}))


def test_referensi_membawa_semua_slot():
    slot = _referensi()["slot_tanda_tangan"]
    assert [s["kunci"] for s in slot] == KUNCI_SLOT
    assert len(slot) >= 3


def test_tiap_slot_punya_label_peran_dan_arti():
    for s in _referensi()["slot_tanda_tangan"]:
        assert s["label"].strip(), s
        assert s["peran"].strip(), s
        assert s["arti"].strip(), s


def test_peran_cadangan_tiap_slot_dikenal_registry_peran():
    # Peran jaring terakhir yang salah ketik = slot yang TIDAK PERNAH terisi
    # otomatis, dan layar menampilkan "peran " kosong pada opsi bawaannya.
    for s in _referensi()["slot_tanda_tangan"]:
        assert s["peran"] in PERAN_PEJABAT, s["peran"]
        assert s["peran_uraian"] == PERAN_PEJABAT[s["peran"]]


def test_uraian_peran_bukan_string_kosong():
    for s in _referensi()["slot_tanda_tangan"]:
        assert s["peran_uraian"].strip()


def test_sumbernya_satu_dengan_resolver():
    # Kalau endpoint kelak menyalin daftarnya sendiri, uji ini jatuh.
    slot = {s["kunci"]: s["peran"] for s in _referensi()["slot_tanda_tangan"]}
    assert slot == {k: v["peran"] for k, v in SLOT_TTD.items()}
