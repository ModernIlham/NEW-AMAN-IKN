"""Lingkup unit organisasi yang dicatat pada kegiatan.

Permintaan pemilik: *"buat sistem tampil sesuai eselon yang dicatat di dalam
kegiatan sehingga tetap menyajikan data sesuai dengan tupoksinya dan tidak
membingungkan akibat semakin banyak data input."*

Sampai sekarang lingkup itu berupa teks bebas dua tingkat yang diketik pada
form kegiatan, tak pernah dihubungkan dengan master unit mana pun — sehingga
sistem "hanya sampai Eselon II" dan salah ketik melahirkan unit yang tak ada.
`lingkup_unit` menggantikannya dengan rujukan ke pohon, tingkat berapa pun.

Yang dijaga di sini: id yang tak dikenal DITOLAK, bukan didiamkan. Lingkup
adalah penyaring — id mati tidak menyaring apa pun, sehingga kegiatan yang
dimaksudkan terbatas pada satu Biro justru menampilkan seluruh satker.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.activities as ra

USER = {"username": "admin", "role": "admin", "kode_satker": "111111"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (ra, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    _jalan(fake.unit_kerja.insert_many([
        {"id": "u1", "nama_unit": "Setjen", "eselon": "1", "parent_id": None,
         "kode_satker": "111111"},
        {"id": "u2", "nama_unit": "Biro Umum", "eselon": "2",
         "parent_id": "u1", "kode_satker": "111111"},
        {"id": "z9", "nama_unit": "Biro Asing", "eselon": "2",
         "parent_id": None, "kode_satker": "222222"},
    ]))
    return fake


def _keg(**kw):
    dasar = {"nomor_surat": "S-1", "nama_kegiatan": "Inventarisasi",
             "kode_satker": "111111", "nama_satker": "Satker Uji"}
    return ra.InventoryActivityCreate(**{**dasar, **kw})


def test_lingkup_yang_sah_diterima_dan_dirapikan(dbx):
    a = _keg(lingkup_unit=["u2", " u1 ", "u2"])
    _jalan(ra._validasi_lingkup_unit(a, USER))
    assert a.lingkup_unit == ["u2", "u1"]      # duplikat dibuang, urutan tetap


def test_id_yang_tak_dikenal_DITOLAK_bukan_didiamkan(dbx):
    with pytest.raises(HTTPException) as e:
        _jalan(ra._validasi_lingkup_unit(_keg(lingkup_unit=["u1", "hantu"]),
                                         USER))
    assert e.value.status_code == 400
    assert "tidak dikenal" in str(e.value.detail)


def test_unit_milik_satker_lain_ditolak(dbx):
    # Dari sisi satker ini, unit satker lain dan unit yang tak ada sama saja.
    with pytest.raises(HTTPException) as e:
        _jalan(ra._validasi_lingkup_unit(_keg(lingkup_unit=["z9"]), USER))
    assert e.value.status_code == 400


def test_lingkup_kosong_diterima_sebagai_seluruh_satker(dbx):
    a = _keg(lingkup_unit=[])
    _jalan(ra._validasi_lingkup_unit(a, USER))
    assert a.lingkup_unit == []


def test_lingkup_berisi_spasi_saja_dianggap_kosong(dbx):
    a = _keg(lingkup_unit=["", "   "])
    _jalan(ra._validasi_lingkup_unit(a, USER))
    assert a.lingkup_unit == []


def test_field_lingkup_ikut_tersimpan_pada_dokumennya(dbx):
    # Kedua rute memakai model_dump(), jadi yang dijaga adalah field itu
    # memang ada pada modelnya — bukan diam-diam hilang saat disimpan.
    assert "lingkup_unit" in _keg(lingkup_unit=["u1"]).model_dump()
    assert "lingkup_unit" in ra.InventoryActivityResponse.model_fields
