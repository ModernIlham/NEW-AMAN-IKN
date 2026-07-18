"""Tes hierarki digit Segmen Akun BAS (referensi_akun_utils) — murni."""
import json
from pathlib import Path

from referensi_akun_utils import (KELOMPOK_LABEL, LEVEL_LABEL,
                                  baris_csv_referensi, jalur_digit,
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


def test_label_kelompok_sesuai_nama_resmi_kep211():
    """Kunci nama kelompok ke lampiran resmi KEP-211/PB/2018 — cegah regresi
    ke label heuristik lama (mis. 19 'Aset Lainnya Khusus BUN')."""
    resmi = {
        "19": "Akun Setup", "23": "Dicadangkan untuk Komitmen Belanja",
        "29": "Akun Setup", "31": "Ekuitas", "39": "Ekuitas",
        "49": "Pendapatan Penyesuaian", "59": "Beban Penyesuaian",
        "61": "Dana Bagi Hasil (DBH)", "62": "Dana Alokasi Umum (DAU)",
        "66": "Dana Desa", "69": "Beban Transfer Lain-lain",
        "79": "Pengeluaran Pembiayaan Lain-lain",
        "81": "Penerimaan Non Anggaran", "82": "Pengeluaran Non Anggaran",
    }
    for kode, nama in resmi.items():
        assert KELOMPOK_LABEL[kode] == nama, kode


def test_kelompok_konsisten_dengan_segmennya():
    """Digit pertama tiap kunci kelompok harus segmen yang sah (1–8)."""
    for p in KELOMPOK_LABEL:
        assert len(p) == 2 and p[0] in _SEGMEN, p


def test_baris_csv_referensi_hierarki():
    items = [
        {"kode": "521111", "nama": "Belanja Keperluan Perkantoran",
         "sumber": "resmi", "uraian_bmn": "ATK", "kapitalisasi": "tidak",
         "kategori_neraca": "-", "penjelasan": "Belanja untuk perkantoran"},
        {"kode": "132111", "nama": "Peralatan dan Mesin", "sumber": "satker"},
    ]
    rows = baris_csv_referensi(items, _SEGMEN, hierarki={"521": "BELANJA BARANG"})
    assert rows[0][0] == "Kode" and rows[0][-1] == "Penjelasan" and len(rows) == 3
    assert rows[0][7] == "Nama Jenis"
    assert rows[1][:8] == ["521111", "Belanja Keperluan Perkantoran", "5",
                           "Belanja", "52", "Belanja Barang dan Jasa", "521",
                           "BELANJA BARANG"]
    assert rows[1][8:] == ["resmi", "ATK", "tidak", "-",
                           "Belanja untuk perkantoran"]
    assert rows[2][:8] == ["132111", "Peralatan dan Mesin", "1", "Aset",
                           "13", "Aset Tetap", "132", ""]
    # field opsional kosong → string kosong, bukan None
    assert rows[2][9] == "" and rows[2][-1] == ""


def test_jalur_digit_lengkap():
    """Makna tiap pola digit: level 1..6 dgn uraian hierarki resmi."""
    hier = {"1": "ASET", "11": "ASET LANCAR", "117": "PERSEDIAAN",
            "1171": "Persediaan", "11711": "Persediaan Bahan Operasional"}
    jalur = jalur_digit("117111", hier, nama_sendiri="Barang Konsumsi")
    assert len(jalur) == 6
    assert [j["kode"] for j in jalur] == ["1", "11", "117", "1171", "11711", "117111"]
    assert jalur[0]["uraian"] == "ASET" and jalur[0]["label"] == LEVEL_LABEL[1]
    assert jalur[2]["uraian"] == "PERSEDIAAN"
    assert jalur[5]["uraian"] == "Barang Konsumsi"  # level 6 = nama akun sendiri
    # level tanpa nama resmi → uraian kosong tapi tetap muncul
    jalur2 = jalur_digit("991111", {"9": "X"}, "Aneh")
    assert len(jalur2) == 6 and jalur2[1]["uraian"] == "" and jalur2[5]["uraian"] == "Aneh"
    # kode pendek/kosong tidak crash
    assert jalur_digit("52", {"5": "BELANJA"}, "")[0]["uraian"] == "BELANJA"
    assert jalur_digit("", {}, "") == []


def test_seed_hierarki_cakupan():
    """Seed membawa hierarki level-digit; level 1-2 harus menutup semua
    prefiks master (anti-drift saat seed diganti)."""
    data = json.loads(_SEED.read_text())
    hier = data.get("hierarki") or {}
    assert len(hier) > 1000
    pref1 = {str(a["kode"])[:1] for a in data["akun"]}
    pref2 = {str(a["kode"])[:2] for a in data["akun"]}
    assert all(p in hier for p in pref1), pref1 - set(hier)
    tanpa2 = {p for p in pref2 if p not in hier}
    # toleransi kecil utk kelompok legacy (32, 67 tak ada di KEP-211)
    assert len(tanpa2) <= 3, tanpa2


def test_baris_csv_penjelasan_warisan_ditandai():
    """Penjelasan warisan induk diberi prefiks penanda di CSV."""
    items = [{"kode": "111119", "nama": "Kas ...", "sumber": "resmi",
              "penjelasan": "Definisi kelompok kas", "penjelasan_warisan": True}]
    rows = baris_csv_referensi(items, _SEGMEN)
    assert rows[1][-1].startswith("[penjelasan kelompok induk]")


def test_baris_csv_referensi_kosong():
    rows = baris_csv_referensi([], _SEGMEN)
    assert len(rows) == 1
    rows = baris_csv_referensi(None, None)
    assert len(rows) == 1
