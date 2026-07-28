"""Uji ENDPOINT rekap SIMAN per kegiatan — Mongo in-process, tanpa jaringan.

LAPORAN LAPANGAN yang ditutup di sini: "Sinkronisasi SIMAN V2 tidak ada
pembagian per kegiatan sehingga jika banyak kegiatan inventarisasi informasi
per kegiatannya tidak diinformasikan sehingga bingung."

Angka global ("3 selisih") memang benar, tetapi tak bisa ditindaklanjuti: ia
tak memberi tahu kegiatan mana yang harus dibuka. Yang diuji di sini adalah
janji perbaikannya — rekapnya benar per kegiatan, penyaringnya benar-benar
menyaring, dan aset tanpa kegiatan tidak hilang diam-diam.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.siman as rs

# kode_satker "" = super-admin lintas satker → guard akses no-op, sehingga uji
# ini fokus pada rekap (isolasi satker punya uji sendiri di modul lain).
USER = {"username": "admin", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rs, "db", fake)
    monkeypatch.setattr(rs, "log_audit", _diam)
    import shared_utils as su_mod
    monkeypatch.setattr(su_mod, "db", fake)
    return fake


def _aset(i, keg, status):
    return {"id": i, "activity_id": keg, "asset_code": "3.05.01.05.007",
            "NUP": i[-1], "asset_name": f"Barang {i}", "kode_satker": "",
            "siman": {"status": status, "selisih": [{"field": "asset_name",
                                                     "label": "Nama",
                                                     "aman": "A", "siman": "B"}]}}


async def _seed(dbx):
    await dbx.inventory_activities.insert_many([
        {"id": "keg1", "nama_kegiatan": "Inventarisasi Semester I", "kode_satker": ""},
        {"id": "keg2", "nama_kegiatan": "Inventarisasi Semester II", "kode_satker": ""},
    ])
    await dbx.assets.insert_many([
        _aset("a1", "keg1", "selisih"),
        _aset("a2", "keg1", "selisih"),
        _aset("a3", "keg1", "cocok"),
        _aset("a4", "keg2", "selisih"),
        _aset("a5", "keg2", "cocok"),
        _aset("a6", "keg2", "tidak_di_siman"),
        _aset("a7", "", "selisih"),          # belum terikat kegiatan mana pun
    ])


def test_rekap_memecah_angka_per_kegiatan(dbx):
    """INTI PERBAIKAN. Global bilang "4 selisih"; yang dibutuhkan operator
    adalah 2 di Semester I, 1 di Semester II, 1 belum berkegiatan."""
    _jalan(_seed(dbx))
    per = _jalan(rs._rekap_per_kegiatan(USER))
    peta = {p["activity_id"]: p for p in per}

    assert peta["keg1"]["nama_kegiatan"] == "Inventarisasi Semester I"
    assert (peta["keg1"]["selisih"], peta["keg1"]["cocok"]) == (2, 1)
    assert (peta["keg2"]["selisih"], peta["keg2"]["cocok"]) == (1, 1)
    assert peta["keg2"]["tidak_di_siman"] == 1
    assert peta["keg1"]["total"] == 3

    # Jumlah seluruh baris rekap WAJIB sama dengan angka global — rekap yang
    # tak menjumlah balik justru menambah kebingungan, bukan menguranginya.
    assert sum(p["selisih"] for p in per) == 4
    assert sum(p["cocok"] for p in per) == 2


def test_aset_tanpa_kegiatan_tak_hilang_diam_diam(dbx):
    """Aset yang belum terikat kegiatan justru yang paling perlu dilihat —
    membuangnya dari rekap membuat angka rekap tak pernah menjumlah balik."""
    _jalan(_seed(dbx))
    per = _jalan(rs._rekap_per_kegiatan(USER))
    tanpa = [p for p in per if not p["activity_id"]]
    assert len(tanpa) == 1
    assert tanpa[0]["selisih"] == 1
    assert tanpa[0]["nama_kegiatan"] == "(tanpa kegiatan)"


def test_kegiatan_terhapus_diberi_label_jujur(dbx):
    """activity_id menunjuk kegiatan yang sudah tak ada: jangan tampil sebagai
    baris kosong tanpa nama — katakan apa adanya."""
    _jalan(dbx.assets.insert_one(_aset("z1", "keg_hantu", "selisih")))
    per = _jalan(rs._rekap_per_kegiatan(USER))
    hantu = [p for p in per if p["activity_id"] == "keg_hantu"]
    assert len(hantu) == 1
    assert hantu[0]["nama_kegiatan"] == "(kegiatan tak ditemukan)"


def test_urutan_menaruh_yang_perlu_ditindak_di_atas(dbx):
    """Panel ini dibaca dari atas. Kegiatan tanpa selisih tak boleh menutupi
    kegiatan yang punya selisih."""
    _jalan(_seed(dbx))
    per = _jalan(rs._rekap_per_kegiatan(USER))
    selisih = [p["selisih"] for p in per]
    assert selisih == sorted(selisih, reverse=True)


def test_daftar_selisih_disaring_ke_satu_kegiatan(dbx):
    """Pasangan dari rekap: mengklik "Semester I" harus benar-benar
    mempersempit daftar, bukan sekadar menyorotnya."""
    _jalan(_seed(dbx))
    fn = rs.daftar_selisih_siman

    semua = _jalan(fn(page=1, page_size=50, activity_id="", _user=USER))
    assert semua["total"] == 4

    satu = _jalan(fn(page=1, page_size=50, activity_id="keg1", _user=USER))
    assert satu["total"] == 2
    assert {i["id"] for i in satu["items"]} == {"a1", "a2"}
    assert satu["activity_id"] == "keg1"


def test_saring_tanpa_kegiatan_memakai_penanda_strip(dbx):
    """"-" = aset yang belum terikat kegiatan. Tanpa penanda tersendiri, baris
    "(tanpa kegiatan)" di rekap akan mengklik ke daftar yang tak tersaring."""
    _jalan(_seed(dbx))
    hasil = _jalan(rs.daftar_selisih_siman(
        page=1, page_size=50, activity_id="-", _user=USER))
    assert hasil["total"] == 1
    assert hasil["items"][0]["id"] == "a7"


def test_baris_selisih_menyebut_kegiatan_asalnya(dbx):
    """Daftar gabungan tanpa nama kegiatan per baris = persis keluhan awal:
    deretan aset tanpa petunjuk berasal dari kegiatan yang mana."""
    _jalan(_seed(dbx))
    hasil = _jalan(rs.daftar_selisih_siman(
        page=1, page_size=50, activity_id="", _user=USER))
    nama = {i["id"]: i.get("nama_kegiatan") for i in hasil["items"]}
    assert nama["a1"] == "Inventarisasi Semester I"
    assert nama["a4"] == "Inventarisasi Semester II"


def test_penyaring_tak_bisa_menembus_batas_satker(dbx):
    """Penyaring kegiatan mempersempit lingkup, TIDAK pernah melebarkannya.

    Pengguna satker A menyaring ke kegiatan milik satker B harus mendapat nol —
    bukan data satker B. Uji ini menjaga agar parameter baru tak diam-diam
    menjadi jalan pintas IDOR.
    """
    _jalan(dbx.assets.insert_many([
        {"id": "sa1", "activity_id": "kegA", "kode_satker": "111111",
         "asset_code": "x", "NUP": "1", "asset_name": "Milik A",
         "siman": {"status": "selisih", "selisih": []}},
        {"id": "sb1", "activity_id": "kegB", "kode_satker": "222222",
         "asset_code": "y", "NUP": "1", "asset_name": "Milik B",
         "siman": {"status": "selisih", "selisih": []}},
    ]))
    user_a = {"username": "a", "role": "admin", "kode_satker": "111111"}
    hasil = _jalan(rs.daftar_selisih_siman(
        page=1, page_size=50, activity_id="kegB", _user=user_a))
    assert hasil["total"] == 0
    assert hasil["items"] == []


def test_pengguna_ter_scope_TETAP_bisa_menyaring_kegiatannya_sendiri(dbx):
    """Pasangan wajib dari uji IDOR di atas.

    Menutup kebocoran itu gampang kebablasan: bila penyaring digabungkan
    dengan cara yang salah, ia berubah jadi no-op — nol hasil untuk SIAPA PUN
    yang bukan super-admin, dan fiturnya mati tanpa suara sementara uji
    keamanannya tetap hijau. Uji ini menuntut jalur yang sah tetap hidup.
    """
    _jalan(dbx.inventory_activities.insert_many([
        {"id": "kegA", "nama_kegiatan": "Inventarisasi A", "kode_satker": "111111"},
        {"id": "kegA2", "nama_kegiatan": "Inventarisasi A-2", "kode_satker": "111111"},
    ]))
    _jalan(dbx.assets.insert_many([
        {"id": "sa1", "activity_id": "kegA", "kode_satker": "111111",
         "asset_code": "x", "NUP": "1", "asset_name": "Milik A",
         "siman": {"status": "selisih", "selisih": []}},
        {"id": "sa2", "activity_id": "kegA2", "kode_satker": "111111",
         "asset_code": "x", "NUP": "2", "asset_name": "Milik A dua",
         "siman": {"status": "selisih", "selisih": []}},
    ]))
    user_a = {"username": "a", "role": "admin", "kode_satker": "111111"}

    semua = _jalan(rs.daftar_selisih_siman(
        page=1, page_size=50, activity_id="", _user=user_a))
    assert semua["total"] == 2, "prasyarat: kedua aset memang terlihat oleh A"

    satu = _jalan(rs.daftar_selisih_siman(
        page=1, page_size=50, activity_id="kegA", _user=user_a))
    assert satu["total"] == 1 and satu["items"][0]["id"] == "sa1"
