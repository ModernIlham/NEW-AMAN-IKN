"""Tes hierarki digit Segmen Akun BAS (referensi_akun_utils) — murni."""
import json
from pathlib import Path

from referensi_akun_utils import (KELOMPOK_LABEL, baris_csv_referensi,
                                  label_kelompok)

_SEED = Path(__file__).parent.parent.parent / "data" / "referensi_akun_bas.json"
_SEGMEN = {"1": "Aset", "2": "Kewajiban", "3": "Ekuitas", "4": "Pendapatan",
           "5": "Belanja", "6": "Transfer", "7": "Pembiayaan",
           "8": "Non-Anggaran"}


def test_semua_kelompok_di_seed_berlabel():
    """Anti-drift: tiap prefiks 2-digit di referensi resmi HARUS punya label
    kelompok eksplisit — seed baru dengan kelompok baru menagih label baru."""
    data = json.loads(_SEED.read_text())
    prefiks = {str(a.get("kode") or "")[:2] for a in data["akun"]}
    tanpa_label = sorted(p for p in prefiks if p not in KELOMPOK_LABEL)
    assert not tanpa_label, f"Kelompok tanpa label: {tanpa_label}"


def test_label_kelompok_dikenal_dan_fallback():
    assert label_kelompok("521111") == "Belanja Barang dan Jasa"
    assert label_kelompok("132111") == "Aset Tetap"
    assert label_kelompok("117111") == "Aset Lancar"
    # tak dikenal → generik, tidak pernah kosong utk kode valid
    assert label_kelompok("991111") == "Kelompok 99"
    assert label_kelompok("") == ""
    assert label_kelompok(None) == ""


def test_kelompok_konsisten_dengan_segmennya():
    """Digit pertama tiap kunci kelompok harus segmen yang sah (1–8)."""
    for p in KELOMPOK_LABEL:
        assert len(p) == 2 and p[0] in _SEGMEN, p


def test_baris_csv_referensi_hierarki():
    items = [
        {"kode": "521111", "nama": "Belanja Keperluan Perkantoran",
         "sumber": "resmi", "uraian_bmn": "ATK", "kapitalisasi": "tidak",
         "kategori_neraca": "-"},
        {"kode": "132111", "nama": "Peralatan dan Mesin", "sumber": "satker"},
    ]
    rows = baris_csv_referensi(items, _SEGMEN)
    assert rows[0][0] == "Kode" and len(rows) == 3
    assert rows[1][:7] == ["521111", "Belanja Keperluan Perkantoran", "5",
                           "Belanja", "52", "Belanja Barang dan Jasa", "521"]
    assert rows[1][7:] == ["resmi", "ATK", "tidak", "-"]
    assert rows[2][:7] == ["132111", "Peralatan dan Mesin", "1", "Aset",
                           "13", "Aset Tetap", "132"]
    # field opsional kosong → string kosong, bukan None
    assert rows[2][8] == ""


def test_baris_csv_referensi_kosong():
    rows = baris_csv_referensi([], _SEGMEN)
    assert len(rows) == 1
    rows = baris_csv_referensi(None, None)
    assert len(rows) == 1
