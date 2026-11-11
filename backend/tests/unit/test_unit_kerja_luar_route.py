"""Rute unit kerja luar (PGW-05) — cermin test_unit_kerja_route.py untuk
lingkup satker luar.

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kontrak 6.2, aturan
penampungan 3.3 butir 3, invarian 7–8.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.organisasi_luar as rol
import routes.unit_kerja_luar as rukl

ADMIN = {"username": "admin", "role": "admin", "kode_satker": "111111"}
SUPER = {"username": "pusat", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _galat(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rol, rukl, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    # Koleksi internal yang TIDAK boleh berubah oleh modul ini.
    _jalan(fake.pegawai.insert_one({"id": "pi", "nama": "Internal",
                                    "eselon1": "Setjen", "eselon2": "Biro Umum"}))
    _jalan(fake.unit_kerja.insert_one({"id": "ui", "nama_unit": "Biro Umum", "eselon": "2"}))
    _jalan(fake.assets.insert_one({"id": "ai", "eselon1": "Setjen", "eselon2": "Biro Umum"}))
    return fake


def _satker(nama="Kementerian X", satker="Sekretariat", **kw):
    return _jalan(rol.buat_instansi_luar(rol.InstansiLuarIn(
        kelompok="eksternal", jenis="kementerian_lembaga", nama=nama,
        satker_pertama=rol.SatkerLuarIn(nama_satker=satker, **kw)),
        user=ADMIN))["satker"]


def _buat(sid, nama, eselon, parent_id=""):
    return _jalan(rukl.buat_unit_kerja_luar(rukl.UnitLuarIn(
        satker_luar_id=sid, nama_unit=nama, eselon=eselon, parent_id=parent_id),
        user=ADMIN))["id"]


def _ubah(uid, **kw):
    return _jalan(rukl.ubah_unit_kerja_luar(uid, rukl.UnitLuarUbah(**kw), user=ADMIN))


def _pohon(sid):
    e1 = _buat(sid, "Setjen", "1")
    e2 = _buat(sid, "Biro Umum", "2", e1)
    e2b = _buat(sid, "Biro Keuangan", "2", e1)
    e3 = _buat(sid, "Bagian RT", "3", e2)
    return e1, e2, e2b, e3


def _internal_utuh(dbx):
    assert _jalan(dbx.pegawai.find_one({"id": "pi"}, {"_id": 0})) == {
        "id": "pi", "nama": "Internal", "eselon1": "Setjen", "eselon2": "Biro Umum"}
    assert _jalan(dbx.unit_kerja.count_documents({})) == 1
    assert _jalan(dbx.assets.find_one({"id": "ai"}, {"_id": 0}))["eselon2"] == "Biro Umum"


# ── aturan pohon (salinan kasus internal) ──────────────────────────────────
def test_eselon_satu_berinduk_dan_tingkat_dilompati_ditolak(dbx):
    sid = _satker()["id"]
    e1 = _buat(sid, "Setjen", "1")
    assert _galat(rukl.buat_unit_kerja_luar(rukl.UnitLuarIn(
        satker_luar_id=sid, nama_unit="Kedeputian", eselon="1", parent_id=e1),
        user=ADMIN)).status_code == 400
    assert _galat(rukl.buat_unit_kerja_luar(rukl.UnitLuarIn(
        satker_luar_id=sid, nama_unit="Bagian RT", eselon="3", parent_id=e1),
        user=ADMIN)).status_code == 400


def test_akar_mengikuti_eselon_satker_luar(dbx):
    sid = _satker(eselon_satker="3")["id"]
    _buat(sid, "Bagian Umum", "3")          # puncak satker Eselon III tanpa induk
    daftar = _jalan(rukl.daftar_unit_kerja_luar(satker_luar_id=sid, _user=ADMIN))
    assert daftar["level_akar"] == 3 and daftar["jumlah"] == 1


def test_nama_saja_diubah_tidak_melepaskan_induk_dan_kembar_ditolak(dbx):
    sid = _satker()["id"]
    e1, e2, e2b, e3 = _pohon(sid)
    _ubah(e2, nama_unit="Biro Umum dan Kepegawaian")
    u = _jalan(dbx.unit_kerja_luar.find_one({"id": e2}, {"_id": 0}))
    assert u["parent_id"] == e1
    assert _galat(rukl.ubah_unit_kerja_luar(e2b, rukl.UnitLuarUbah(
        nama_unit="Biro Umum dan Kepegawaian"), user=ADMIN)).status_code == 400


def test_pindah_ke_keturunan_sendiri_ditolak(dbx):
    sid = _satker()["id"]
    e1, e2, e2b, e3 = _pohon(sid)
    assert _galat(rukl.ubah_unit_kerja_luar(e2, rukl.UnitLuarUbah(parent_id=e3),
                                            user=ADMIN)).status_code == 400


def test_unit_tak_dikenal_404(dbx):
    assert _galat(rukl.ubah_unit_kerja_luar("x", rukl.UnitLuarUbah(nama_unit="A"),
                                            user=ADMIN)).status_code == 404


# ── tidak tercampur ────────────────────────────────────────────────────────
def test_induk_dari_satker_lain_ditolak(dbx):
    x, y = _satker("Kementerian X")["id"], _satker("Kementerian Y")["id"]
    induk_y = _buat(y, "Setjen", "1")
    assert _galat(rukl.buat_unit_kerja_luar(rukl.UnitLuarIn(
        satker_luar_id=x, nama_unit="Biro", eselon="2", parent_id=induk_y),
        user=ADMIN)).status_code == 400


def test_satker_wajib_dan_wadah_perorangan_menolak_semua(dbx):
    assert _galat(rukl.daftar_unit_kerja_luar(_user=ADMIN)).status_code == 400
    wadah = _jalan(rol.pastikan_wadah_perorangan(ADMIN))["satker"]
    assert _galat(rukl.daftar_unit_kerja_luar(satker_luar_id=wadah["id"],
                                              _user=ADMIN)).status_code == 400
    assert _galat(rukl.buat_unit_kerja_luar(rukl.UnitLuarIn(
        satker_luar_id=wadah["id"], nama_unit="A", eselon="1"),
        user=ADMIN)).status_code == 400
    assert _galat(rukl.bangun_unit_luar_dari_pegawai(rukl.BangunLuarIn(
        satker_luar_id=wadah["id"]), user=ADMIN)).status_code == 400


# ── perambatan hanya ke orang luar satker itu ──────────────────────────────
def test_ganti_nama_merambat_ke_orang_satker_ini_saja(dbx):
    x, y = _satker("Kementerian X")["id"], _satker("Kementerian Y")["id"]
    e1, e2, _, _ = _pohon(x)
    _pohon(y)
    _jalan(dbx.pegawai_luar.insert_many([
        {"id": "ox", "satker_luar_id": x, "eselon1": "Setjen", "eselon2": "Biro Umum"},
        {"id": "oy", "satker_luar_id": y, "eselon1": "Setjen", "eselon2": "Biro Umum"}]))
    hasil = _ubah(e2, nama_unit="Biro Umum dan Kepegawaian")
    assert hasil["ikut_diperbarui"] == {"pegawai": 1}
    ox = _jalan(dbx.pegawai_luar.find_one({"id": "ox"}, {"_id": 0}))
    oy = _jalan(dbx.pegawai_luar.find_one({"id": "oy"}, {"_id": 0}))
    assert ox["eselon2"] == "Biro Umum dan Kepegawaian"
    assert oy["eselon2"] == "Biro Umum"
    _internal_utuh(dbx)


def test_perambatan_tak_menyeret_unit_senama_di_cabang_lain(dbx):
    sid = _satker()["id"]
    e1 = _buat(sid, "Setjen", "1")
    a = _buat(sid, "Biro A", "2", e1)
    b = _buat(sid, "Biro B", "2", e1)
    ta = _buat(sid, "Bagian TU", "3", a)
    _buat(sid, "Bagian TU", "3", b)
    _jalan(dbx.pegawai_luar.insert_many([
        {"id": "o1", "satker_luar_id": sid, "eselon1": "Setjen", "eselon2": "Biro A",
         "eselon3": "Bagian TU"},
        {"id": "o2", "satker_luar_id": sid, "eselon1": "Setjen", "eselon2": "Biro B",
         "eselon3": "Bagian TU"}]))
    _ubah(ta, nama_unit="Bagian Tata Usaha A")
    o2 = _jalan(dbx.pegawai_luar.find_one({"id": "o2"}, {"_id": 0}))
    assert o2["eselon3"] == "Bagian TU"


# ── hapus & bangun ─────────────────────────────────────────────────────────
def test_hapus_super_admin_dan_409_bila_beranak_atau_dipakai(dbx):
    from auth_utils import require_super_admin
    assert _galat(require_super_admin(ADMIN)).status_code == 403
    sid = _satker()["id"]
    e1, e2, e2b, e3 = _pohon(sid)
    assert _galat(rukl.hapus_unit_kerja_luar(e2, user=SUPER)).status_code == 409
    _jalan(dbx.pegawai_luar.insert_one({"id": "o", "satker_luar_id": sid,
                                        "eselon2": "Biro Keuangan"}))
    assert _galat(rukl.hapus_unit_kerja_luar(e2b, user=SUPER)).status_code == 409
    _jalan(rukl.hapus_unit_kerja_luar(e3, user=SUPER))
    assert _jalan(dbx.unit_kerja_luar.count_documents({"id": e3})) == 0
    _internal_utuh(dbx)


def test_bangun_dari_orang_idempoten_dan_per_satker(dbx):
    x, y = _satker("Kementerian X")["id"], _satker("Kementerian Y")["id"]
    _jalan(dbx.pegawai_luar.insert_many([
        {"id": "o1", "satker_luar_id": x, "eselon1": "Setjen", "eselon2": "Biro Umum"},
        {"id": "o2", "satker_luar_id": y, "eselon1": "Ditjen", "eselon2": "Direktorat"}]))
    h1 = _jalan(rukl.bangun_unit_luar_dari_pegawai(rukl.BangunLuarIn(satker_luar_id=x),
                                                   user=ADMIN))
    h2 = _jalan(rukl.bangun_unit_luar_dari_pegawai(rukl.BangunLuarIn(satker_luar_id=x),
                                                   user=ADMIN))
    assert (h1["dibuat"], h2["dibuat"]) == (2, 0)
    nama = {u["nama_unit"] for u in _jalan(dbx.unit_kerja_luar.find(
        {"satker_luar_id": x}, {"_id": 0}).to_list(10))}
    assert nama == {"Setjen", "Biro Umum"}
    assert _jalan(dbx.unit_kerja_luar.count_documents({"satker_luar_id": y})) == 0
    assert all("kode_satker" not in u for u in _jalan(
        dbx.unit_kerja_luar.find({}, {"_id": 0}).to_list(10)))
    _internal_utuh(dbx)


def test_modul_tidak_menulis_koleksi_internal_dan_tanpa_scope():
    import re
    from pathlib import Path
    src = Path(rukl.__file__).read_text(encoding="utf-8")
    assert not re.search(r"db\.(pegawai|unit_kerja|satker|assets)\."
                         r"(insert|update|delete|bulk_write|replace)", src)
    assert "scope_query_field_satker(" not in src and "scope_query_aset(" not in src
