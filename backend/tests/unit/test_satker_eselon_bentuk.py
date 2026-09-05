"""Struktur eselon satker: satu bentuk, dan tak terhapus saat profil disimpan.

Dua cacat yang dijaga di sini, keduanya bekerja tanpa satu pun pesan galat.

1. **Menyimpan profil satker MENGHAPUS struktur eselonnya.** `doc` pada PUT
   menulis `eselon1` tanpa syarat, sementara layar Satker tak pernah
   mengirimnya sama sekali — tak ada `eselon1` pada `FORM_KOSONG`-nya. Jadi
   setiap kali admin mengganti alamat, telepon, atau apa pun, struktur
   Eselon I/II satker itu terhapus, dan kegiatan baru kehilangan isian
   otomatisnya. Penulis kodenya sudah menyadari kelas cacat ini dan
   memperbaikinya untuk `penandatangan` pada fungsi yang SAMA — komentarnya
   masih ada di sana — tetapi `eselon1` terlewat.

2. **Bentuknya ada dua.** Daftar string (tulisan PUT lama) dan daftar dict
   bersarang (auto-registrasi kegiatan). Menuntut `List[str]` saja membuat
   satker hasil auto-registrasi ditolak 422 begitu profilnya disunting.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.satker as rs

# Admin yang TERIKAT satker ini — jalur yang sebenarnya dipakai layar
# Satker; guard isolasi (REVIEW-9 R9) menolak admin satker lain.
ADMIN = {"username": "admin", "role": "admin", "kode_satker": "111111"}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rs, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(rs, "log_audit", _diam, raising=False)
    return fake


def _simpan(**isi):
    payload = rs.SatkerIn(**{"kode_satker": "111111",
                             "nama_satker": "Satker Uji", **isi})
    return _jalan(rs.simpan_satker("111111", payload, admin=ADMIN))


def _baca(dbx):
    return _jalan(dbx.satker.find_one({"kode_satker": "111111"}, {"_id": 0}))


# ── 1. Penyimpanan profil tak menghapus struktur eselon ─────────────────

def test_menyimpan_profil_TANPA_eselon_tak_menghapus_yang_sudah_ada(dbx):
    _simpan(eselon1=[{"nama": "Setjen", "eselon2": ["Biro Umum"]}])
    assert _baca(dbx)["eselon1"] == [{"nama": "Setjen",
                                      "eselon2": ["Biro Umum"]}]
    # Simpanan berikutnya hanya mengganti alamat — persis yang dikirim layar
    # Satker, yang tak punya kotak eselon sama sekali.
    _simpan(alamat="Jl. Nusantara 1")
    sisa = _baca(dbx)
    assert sisa["alamat"] == "Jl. Nusantara 1"
    assert sisa["eselon1"] == [{"nama": "Setjen", "eselon2": ["Biro Umum"]}], \
        "struktur eselon terhapus saat profil disimpan"


def test_mengirim_daftar_KOSONG_memang_mengosongkannya(dbx):
    # "Tak dikirim" dan "dikosongkan" beda maksud; yang kedua harus tetap bisa.
    _simpan(eselon1=[{"nama": "Setjen", "eselon2": []}])
    _simpan(eselon1=[])
    assert _baca(dbx)["eselon1"] == []


def test_satker_baru_tanpa_eselon_tak_membawa_field_hantu(dbx):
    _simpan(alamat="Jl. Nusantara 1")
    assert "eselon1" not in _baca(dbx)


# ── 2. Dua bentuk diterima, satu bentuk disimpan ────────────────────────

def test_bentuk_daftar_STRING_lama_tetap_diterima(dbx):
    # Tulisan PUT versi lama. Menolaknya membuat data yang sudah ada di basis
    # data tak dapat disunting oleh pemiliknya sendiri.
    _simpan(eselon1=["Setjen", "Kedeputian X"])
    assert _baca(dbx)["eselon1"] == [
        {"nama": "Setjen", "eselon2": []},
        {"nama": "Kedeputian X", "eselon2": []}]


def test_bentuk_dict_auto_registrasi_tetap_diterima(dbx):
    _simpan(eselon1=[{"nama": "Setjen", "eselon2": ["Biro Umum"]}])
    assert _baca(dbx)["eselon1"] == [{"nama": "Setjen",
                                      "eselon2": ["Biro Umum"]}]


def test_dua_rupa_bercampur_disimpan_sebagai_satu_bentuk(dbx):
    _simpan(eselon1=["Setjen", {"nama": "Kedeputian X",
                                "eselon2": ["Direktorat Y"]}])
    tersimpan = _baca(dbx)["eselon1"]
    assert all(set(x) == {"nama", "eselon2"} for x in tersimpan), tersimpan


def test_baris_tanpa_nama_tak_ikut_tersimpan(dbx):
    _simpan(eselon1=["", {"nama": "  "}, {"nama": "Setjen"}])
    assert _baca(dbx)["eselon1"] == [{"nama": "Setjen", "eselon2": []}]
