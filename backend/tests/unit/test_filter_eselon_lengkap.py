"""Filter eselon tak boleh berhenti di tengah pada endpoint mana pun.

Filter eselon dijahit tangan di banyak tempat: setiap endpoint mendeklarasikan
`eselonN_filter` sendiri lalu meneruskannya ke `build_asset_search_query`.
`routes/batch.py` bahkan mencatat sendiri bahwa ia pernah drift.

Bentuk kegagalannya tak pernah berupa galat: endpoint yang ketinggalan satu
tingkat MENERIMA parameternya (FastAPI mengabaikan query string tak dikenal),
menjalankan kuerinya tanpa penyaring itu, dan mengembalikan LEBIH BANYAK aset
daripada yang diminta. Tak ada yang gagal — hanya jawabannya yang salah, ke
arah yang tak mencurigakan, karena daftar yang lebih panjang tak pernah
terlihat seperti kekeliruan.

Karena itu penjagaannya di level sumber: bila satu tingkat disebut, kelimanya
harus disebut, di setiap berkas dan pada setiap pemanggilan.
"""
import os
import re

_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "routes")

#: Berkas rute yang memang mengekspos filter aset.
_BERKAS = ("assets.py", "exports.py", "stiker.py", "batch.py", "reports.py")

_TINGKAT = (1, 2, 3, 4, 5)


def _sumber(nama):
    return open(os.path.join(_DIR, nama), encoding="utf-8").read()


def test_tiap_berkas_menyebut_kelima_tingkat():
    kurang = {}
    for nama in _BERKAS:
        s = _sumber(nama)
        ada = [n for n in _TINGKAT if f"eselon{n}_filter" in s]
        if ada and len(ada) != len(_TINGKAT):
            kurang[nama] = [n for n in _TINGKAT if n not in ada]
    assert not kurang, f"berkas yang filter eselonnya terputus: {kurang}"


def test_tiap_deklarasi_query_punya_kelima_saudaranya():
    # Deklarasi dihitung per berkas: sebuah endpoint yang menambah eselon1–2
    # saja akan membuat cacahnya timpang.
    timpang = {}
    for nama in _BERKAS:
        s = _sumber(nama)
        cacah = {n: len(re.findall(rf"eselon{n}_filter: List\[str\] = Query", s))
                 for n in _TINGKAT}
        if len(set(cacah.values())) > 1:
            timpang[nama] = cacah
    assert not timpang, f"jumlah deklarasi filter tak sama rata: {timpang}"


def test_tiap_penerusan_membawa_kelima_tingkat():
    timpang = {}
    for nama in _BERKAS:
        s = _sumber(nama)
        cacah = {n: len(re.findall(rf"eselon{n}_filter=", s)) for n in _TINGKAT}
        if len(set(cacah.values())) > 1:
            timpang[nama] = cacah
    assert not timpang, f"penerusan filter tak sama rata: {timpang}"


def test_builder_menyaring_kelima_kolomnya():
    # Parameter yang diterima tetapi tak pernah dipakai menyaring adalah
    # bentuk kegagalan yang paling sunyi: permintaannya diterima, jawabannya
    # lebih panjang daripada seharusnya.
    s = _sumber("assets.py")
    for n in _TINGKAT:
        assert re.search(
            rf'\("eselon{n}", klausa_substring\(eselon{n}_filter\)\)', s), (
            f"eselon{n}_filter diterima tetapi tak dipakai menyaring")


def test_ringkasan_laporan_menyebut_kelima_tingkat():
    # Ringkasan yang tercetak di kepala laporan harus menyebut SELURUH filter
    # aktif; tingkat yang hilang dari sini membuat dokumen tampak lebih luas
    # daripada isinya.
    from routes.reports import _LABEL_FILTER, _FILTER_MULTI
    label = dict(_LABEL_FILTER)
    for n, romawi in zip(_TINGKAT, ("I", "II", "III", "IV", "V")):
        kunci = f"eselon{n}_filter"
        assert label.get(kunci) == f"Eselon {romawi}", f"{kunci} tak berlabel"
        assert kunci in _FILTER_MULTI, f"{kunci} tak diperlakukan multi-nilai"
