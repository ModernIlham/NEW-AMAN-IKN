"""Uji Master Unit Kerja berjenjang (Eselon I–V) — murni."""
from unit_kerja_utils import (ESELON_SAH, opsi_bertingkat, unit_dari_pegawai,
                              validate_unit)


def test_validate_unit():
    assert validate_unit({"nama_unit": "Sekretariat", "eselon": "1"}) == []
    assert any("Nama" in e for e in validate_unit({"eselon": "1"}))
    assert any("Eselon" in e for e in
               validate_unit({"nama_unit": "X", "eselon": "9"}))
    # eselon >1 wajib induk
    assert any("induk" in e.lower() for e in
               validate_unit({"nama_unit": "Bagian", "eselon": "2"},
                             punya_induk=False))
    assert validate_unit({"nama_unit": "Bagian", "eselon": "2"},
                         punya_induk=True) == []
    assert ESELON_SAH == ("1", "2", "3", "4", "5")


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
