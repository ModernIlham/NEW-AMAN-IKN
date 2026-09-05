"""Seluruh kolom sheet "Data Aset" sejajar dengan headernya.

Kolom XLSX ditulis dengan indeks yang DIKETIK TANGAN
(`worksheet.write(row, 27, …)`). Menyisipkan satu kolom di tengah menggeser
semua kolom sesudahnya, dan berkas ekspornya tetap terbentuk dengan rapi —
hanya saja setiap nilai berada satu kolom di sebelah kiri judulnya. Tak ada
yang gagal, tak ada yang memberi tahu, dan yang membacanya membandingkan
"Supplier" dengan nomor kontrak.

Penjaga untuk `temuan_pencatatan` sudah ada di `test_sub_klasifikasi_selaras`
dan memang menangkap penggeseran saat Eselon III–V disisipkan. Tetapi ia
menjaga SATU kolom: penggeseran yang berhenti sebelum kolom terakhir akan
lolos begitu saja. Yang di bawah ini memeriksa seluruhnya.
"""
import os
import re

from asset_fields import ASSET_SCALAR_FIELDS
from routes.exports import ASSET_SHEET_HEADERS

_SRC = open(os.path.join(os.path.dirname(__file__), "..", "..",
                         "routes", "exports.py"), encoding="utf-8").read()

#: Kolom yang nilainya bukan field aset langsung (dirakit di tempat).
_BUKAN_FIELD = {"Foto", "Foto Stiker", "Jumlah Foto", "Tanggal Input"}

#: Tiga kolom pertama ditulis dari variabel yang sudah dirapikan lebih dulu
#: (kode dinormalkan, NUP dipisahkan), bukan langsung dari `asset.get`.
#: Dipetakan di sini supaya ketiganya ikut diperiksa kesejajarannya.
_DARI_VARIABEL = {"asset_code": "asset_code", "asset_nup": "NUP",
                  "asset_name": "asset_name"}


def _tulisan():
    """{indeks kolom: nama field} dari blok penulisan baris aset."""
    keluar = {}
    for m in re.finditer(
            r"worksheet\.write\(row, (\d+), (?:str\()?asset\.get\('(\w+)'",
            _SRC):
        keluar[int(m.group(1))] = m.group(2)
    for m in re.finditer(r"worksheet\.write\(row, (\d+), (\w+), cell_format\)",
                         _SRC):
        field = _DARI_VARIABEL.get(m.group(2))
        if field:
            keluar[int(m.group(1))] = field
    return keluar


def test_tiap_kolom_ditulis_di_bawah_judulnya():
    label = {f.name: f.xlsx_label for f in ASSET_SCALAR_FIELDS}
    salah = {}
    for idx, field in _tulisan().items():
        judul = label.get(field)
        if not judul:
            continue                      # kolom di luar registry (mis. year)
        if idx >= len(ASSET_SHEET_HEADERS) or ASSET_SHEET_HEADERS[idx] != judul:
            salah[field] = (
                idx,
                ASSET_SHEET_HEADERS[idx] if idx < len(ASSET_SHEET_HEADERS)
                else "(di luar header)",
                judul)
    assert not salah, (
        "kolom tak sejajar dengan judulnya — field: (indeks, judul di sana, "
        "judul seharusnya) = " + repr(salah))


def test_tak_ada_dua_field_berebut_satu_kolom():
    # Penggeseran yang keliru arah menimpa kolom tetangganya; jumlah tulisan
    # yang lebih banyak daripada indeks uniknya adalah tandanya.
    idx = [int(m.group(1)) for m in re.finditer(
        r"worksheet\.write\(row, (\d+), ", _SRC)]
    # Indeks 0 dan 1 (dua kolom foto) memang ditulis di beberapa cabang.
    idx_isi = [i for i in idx if i > 1]
    assert len(idx_isi) == len(set(idx_isi)), (
        f"indeks kolom ganda: {sorted(i for i in set(idx_isi) if idx_isi.count(i) > 1)}")


def test_seluruh_eselon_satu_sampai_lima_punya_kolomnya():
    for n, judul in ((1, "Eselon I"), (2, "Eselon II"), (3, "Eselon III"),
                     (4, "Eselon IV"), (5, "Eselon V")):
        assert judul in ASSET_SHEET_HEADERS, f"kolom {judul} hilang"
        assert _tulisan().get(ASSET_SHEET_HEADERS.index(judul)) == f"eselon{n}"


def test_header_tak_menyisakan_judul_tanpa_penulis():
    # Judul yang tak pernah ditulisi menghasilkan kolom kosong sepanjang
    # berkas — terbaca sebagai data yang hilang, bukan kolom yang terlupa.
    ditulis = set(_tulisan().values())
    label = {f.name: f.xlsx_label for f in ASSET_SCALAR_FIELDS}
    kosong = [j for j in ASSET_SHEET_HEADERS
              if j not in _BUKAN_FIELD
              and not any(label.get(f) == j for f in ditulis)]
    assert not kosong, f"judul kolom tanpa penulisnya: {kosong}"
