"""Uji Master Unit Kerja berjenjang (Eselon I–V) — murni."""
import organisasi_utils as org
from unit_kerja_utils import ESELON_SAH, opsi_bertingkat, unit_dari_pegawai


def test_eselon_sah_bersumber_dari_satu_registry():
    # `validate_unit` di modul ini pernah menjadi salinan kedua aturan eselon
    # dan sudah menyimpang dari rutenya sebelum sempat dipakai bersama. Yang
    # tersisa hanyalah bentuk STRING-nya; angkanya tetap satu sumber.
    assert ESELON_SAH == ("1", "2", "3", "4", "5")
    assert ESELON_SAH == tuple(str(b["level"]) for b in org.daftar_level())
    import unit_kerja_utils as uk
    assert not hasattr(uk, "validate_unit")


UNITS = [
    {"id": "u1", "nama_unit": "Sekretariat", "eselon": "1", "parent_id": None},
    {"id": "u2", "nama_unit": "Kedeputian X", "eselon": "1", "parent_id": None},
    {"id": "u3", "nama_unit": "Biro Umum", "eselon": "2", "parent_id": "u1"},
    {"id": "u4", "nama_unit": "Direktorat Y", "eselon": "2", "parent_id": "u2"},
    {"id": "u5", "nama_unit": "Bagian TU", "eselon": "3", "parent_id": "u3"},
]


def test_opsi_bertingkat_mengikuti_induk():
    ops = opsi_bertingkat(UNITS, {"eselon1": "Sekretariat"})
    assert ops["eselon1"] == ["Sekretariat", "Kedeputian X"]
    assert ops["eselon2"] == ["Biro Umum"]  # hanya anak Sekretariat
    ops2 = opsi_bertingkat(UNITS, {"eselon1": "Kedeputian X"})
    assert ops2["eselon2"] == ["Direktorat Y"]
    # induk belum dipilih → semua opsi level itu (tetap membantu)
    ops3 = opsi_bertingkat(UNITS, {})
    assert set(ops3["eselon2"]) == {"Biro Umum", "Direktorat Y"}
    # eselon3 mengikuti eselon2 terpilih
    ops4 = opsi_bertingkat(UNITS, {"eselon2": "Biro Umum"})
    assert ops4["eselon3"] == ["Bagian TU"]
    assert opsi_bertingkat([], {})["eselon1"] == []


def test_unit_dari_pegawai():
    pegawai = [
        {"eselon1": "Sekretariat", "eselon2": "Biro Umum", "eselon3": "Bagian TU"},
        {"eselon1": "Sekretariat", "eselon2": "Biro Umum"},   # duplikat jalur
        {"eselon1": "Kedeputian X", "eselon2": "Direktorat Y"},
        {"eselon1": "", "eselon2": "Yatim"},  # jalur putus → eselon2 diabaikan
        {},
    ]
    hasil = unit_dari_pegawai(pegawai)
    kunci = {(h["eselon"], h["nama_unit"], h["induk_nama"]) for h in hasil}
    assert ("1", "Sekretariat", "") in kunci
    assert ("2", "Biro Umum", "Sekretariat") in kunci
    assert ("3", "Bagian TU", "Biro Umum") in kunci
    assert ("2", "Direktorat Y", "Kedeputian X") in kunci
    assert not any(h["nama_unit"] == "Yatim" for h in hasil)
    assert len(hasil) == 5  # unik
    assert unit_dari_pegawai([]) == []
