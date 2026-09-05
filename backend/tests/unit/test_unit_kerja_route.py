"""Rute master unit kerja — pembuatan, penyuntingan, dan perambatan namanya.

Sebelum ada penyuntingan, unit yang salah ketik dan sudah punya anak tak dapat
diperbaiki sama sekali: menghapusnya ditolak karena masih membawahi, dan tak
ada jalan lain selain membongkar seluruh cabangnya lalu menyusunnya ulang.
Organisasi yang berkembang justru sering berganti nama dan berpindah induk.

Tiga sifat dijaga di sini:

1. **Aturan eselonnya SATU.** Rute dan modul murninya tak boleh lagi berbeda
   pendapat — rute lama menolak Eselon I berinduk dengan pesan "harus Eselon
   0", tingkat yang bukan tingkat mana pun.
2. **Penggantian nama IKUT merambat** ke pegawai dan aset, yang menyimpan
   unitnya sebagai nama. Yang tidak merambat bukan penggantian nama,
   melainkan penambahan unit kembar.
3. **Perambatan itu tidak melewati batas satker**, dan tidak menyeret unit
   lain yang kebetulan bernama sama di cabang berbeda.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.unit_kerja as ruk

USER = {"username": "admin", "role": "admin", "kode_satker": "111111"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (ruk, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(ruk, "log_audit", _diam, raising=False)
    return fake


def _buat(nama, eselon, parent_id="", user=USER):
    return _jalan(ruk.buat_unit_kerja(
        ruk.UnitIn(nama_unit=nama, eselon=eselon, parent_id=parent_id),
        user=user))["id"]


def _pohon(dbx):
    """Setjen → Biro Umum → Bagian RT; dan Biro Keuangan sebagai saudara."""
    e1 = _buat("Setjen", "1")
    e2 = _buat("Biro Umum", "2", e1)
    e2b = _buat("Biro Keuangan", "2", e1)
    e3 = _buat("Bagian RT", "3", e2)
    return e1, e2, e2b, e3


# ── 1. Satu aturan eselon ───────────────────────────────────────────────

def test_eselon_satu_berinduk_ditolak_dengan_alasan_yang_benar(dbx):
    e1 = _buat("Setjen", "1")
    with pytest.raises(HTTPException) as e:
        _buat("Kedeputian", "1", e1)
    # Rute lama berkata "harus Eselon 0" — tingkat yang tak pernah ada.
    assert "puncak" in str(e.value.detail)
    assert "0" not in str(e.value.detail)


def test_tingkat_tak_boleh_dilompati_saat_dibuat(dbx):
    e1 = _buat("Setjen", "1")
    with pytest.raises(HTTPException) as e:
        _buat("Bagian RT", "3", e1)
    assert "dilompati" in str(e.value.detail)


def test_eselon_di_luar_satu_sampai_lima_ditolak(dbx):
    with pytest.raises(HTTPException) as e:
        _buat("Entah", "9")
    assert "Eselon I–V" in str(e.value.detail)


# ── 2. Unit dapat diperbaiki ────────────────────────────────────────────

def test_ganti_nama_unit_yang_masih_membawahi(dbx):
    _, e2, _, _ = _pohon(dbx)
    r = _jalan(ruk.ubah_unit_kerja(
        e2, ruk.UnitUbah(nama_unit="Biro Umum dan Keuangan"), user=USER))
    assert r["ok"] and r["jalur"] == "Setjen / Biro Umum dan Keuangan"
    u = _jalan(dbx.unit_kerja.find_one({"id": e2}, {"_id": 0}))
    assert u["nama_unit"] == "Biro Umum dan Keuangan"


def test_nama_saja_diubah_TIDAK_melepaskan_induknya(dbx):
    # `parent_id` yang tak dikirim harus dibedakan dari yang dikosongkan.
    _, e2, _, _ = _pohon(dbx)
    _jalan(ruk.ubah_unit_kerja(e2, ruk.UnitUbah(nama_unit="Biro Baru"),
                               user=USER))
    u = _jalan(dbx.unit_kerja.find_one({"id": e2}, {"_id": 0}))
    assert u["parent_id"], "induknya ikut terlepas"


def test_pindah_ke_induk_lain_yang_setingkat(dbx):
    _, _, e2b, e3 = _pohon(dbx)
    r = _jalan(ruk.ubah_unit_kerja(e3, ruk.UnitUbah(parent_id=e2b), user=USER))
    assert r["jalur"] == "Setjen / Biro Keuangan / Bagian RT"


def test_pindah_ke_keturunan_sendiri_ditolak(dbx):
    # Ditolak oleh aturan tingkat, bukan oleh penjaga gelang: dengan induk
    # wajib tepat satu tingkat di atas, keturunan sebuah unit selalu lebih
    # dalam daripada unit itu sendiri, sehingga tak pernah menjadi calon induk
    # yang sah. Penjaga gelangnya diuji langsung di test_organisasi_utils.
    _, e2, _, e3 = _pohon(dbx)
    with pytest.raises(HTTPException) as e:
        _jalan(ruk.ubah_unit_kerja(e2, ruk.UnitUbah(parent_id=e3), user=USER))
    assert e.value.status_code == 400
    assert "dilompati" in str(e.value.detail)


def test_ubah_eselon_unit_yang_masih_membawahi_ditolak(dbx):
    _, e2, _, _ = _pohon(dbx)
    with pytest.raises(HTTPException) as e:
        _jalan(ruk.ubah_unit_kerja(e2, ruk.UnitUbah(eselon="3"), user=USER))
    assert "membawahi" in str(e.value.detail)


def test_unit_kembar_di_induk_yang_sama_ditolak(dbx):
    _, e2, e2b, _ = _pohon(dbx)
    with pytest.raises(HTTPException) as e:
        _jalan(ruk.ubah_unit_kerja(e2b, ruk.UnitUbah(nama_unit="Biro Umum"),
                                   user=USER))
    assert "sudah terdaftar" in str(e.value.detail)


def test_unit_tak_dikenal_menghasilkan_404(dbx):
    with pytest.raises(HTTPException) as e:
        _jalan(ruk.ubah_unit_kerja("hantu", ruk.UnitUbah(nama_unit="X"),
                                   user=USER))
    assert e.value.status_code == 404


# ── 3. Perambatan nama ke pegawai dan aset ──────────────────────────────

def test_ganti_nama_ikut_merambat_ke_pegawai_dan_aset(dbx):
    _, e2, _, _ = _pohon(dbx)
    _jalan(dbx.pegawai.insert_many([
        {"id": "p1", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Umum"},
        {"id": "p2", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Umum", "eselon3": "Bagian RT"},   # ikut, di bawahnya
        {"id": "p3", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Keuangan"},                        # TIDAK ikut
    ]))
    _jalan(dbx.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "111111"}))
    _jalan(dbx.assets.insert_many([
        {"id": "a1", "activity_id": "k1", "eselon1": "Setjen",
         "eselon2": "Biro Umum"},
        {"id": "a2", "activity_id": "k1", "eselon1": "Setjen",
         "eselon2": "Biro Keuangan"},
    ]))

    r = _jalan(ruk.ubah_unit_kerja(
        e2, ruk.UnitUbah(nama_unit="Biro Umum dan Keuangan"), user=USER))
    assert r["ikut_diperbarui"] == {"pegawai": 2, "aset": 1}

    nama = {p["id"]: p.get("eselon2")
            for p in _jalan(dbx.pegawai.find({}, {"_id": 0}).to_list(10))}
    assert nama == {"p1": "Biro Umum dan Keuangan",
                    "p2": "Biro Umum dan Keuangan",
                    "p3": "Biro Keuangan"}
    aset = {a["id"]: a.get("eselon2")
            for a in _jalan(dbx.assets.find({}, {"_id": 0}).to_list(10))}
    assert aset == {"a1": "Biro Umum dan Keuangan", "a2": "Biro Keuangan"}


def test_perambatan_tak_menyeret_unit_senama_di_cabang_lain(dbx):
    # Dua "Bagian TU" di bawah dua Biro berbeda adalah dua unit berlainan.
    e1 = _buat("Setjen", "1")
    e2 = _buat("Biro Umum", "2", e1)
    e2b = _buat("Biro Keuangan", "2", e1)
    tu_a = _buat("Bagian TU", "3", e2)
    _buat("Bagian TU", "3", e2b)
    _jalan(dbx.pegawai.insert_many([
        {"id": "p1", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Umum", "eselon3": "Bagian TU"},
        {"id": "p2", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Keuangan", "eselon3": "Bagian TU"},
    ]))
    r = _jalan(ruk.ubah_unit_kerja(
        tu_a, ruk.UnitUbah(nama_unit="Bagian Tata Usaha"), user=USER))
    assert r["ikut_diperbarui"]["pegawai"] == 1
    nama = {p["id"]: p.get("eselon3")
            for p in _jalan(dbx.pegawai.find({}, {"_id": 0}).to_list(10))}
    assert nama == {"p1": "Bagian Tata Usaha", "p2": "Bagian TU"}


def test_perambatan_aset_tak_melewati_batas_satker(dbx):
    # `assets` TIDAK membawa kode_satker; ia di-scope lewat kegiatan induknya.
    # Penyaring berbasis field akan mencocokkan dokumen yang field-nya tak ada
    # — yaitu aset satker mana pun — dan penulisan ini merambat ke luar satker.
    _, e2, _, _ = _pohon(dbx)
    _jalan(dbx.inventory_activities.insert_many([
        {"id": "k1", "kode_satker": "111111"},
        {"id": "k2", "kode_satker": "222222"},
    ]))
    _jalan(dbx.assets.insert_many([
        {"id": "a1", "activity_id": "k1", "eselon1": "Setjen",
         "eselon2": "Biro Umum"},
        {"id": "a2", "activity_id": "k2", "eselon1": "Setjen",
         "eselon2": "Biro Umum"},                       # satker LAIN
    ]))
    r = _jalan(ruk.ubah_unit_kerja(e2, ruk.UnitUbah(nama_unit="Biro Baru"),
                                   user=USER))
    assert r["ikut_diperbarui"]["aset"] == 1
    a2 = _jalan(dbx.assets.find_one({"id": "a2"}, {"_id": 0}))
    assert a2["eselon2"] == "Biro Umum", "aset satker lain ikut berubah"


def test_pindah_induk_menulis_ulang_jalur_pegawai(dbx):
    _, _, e2b, e3 = _pohon(dbx)
    _jalan(dbx.pegawai.insert_one(
        {"id": "p1", "kode_satker": "111111", "eselon1": "Setjen",
         "eselon2": "Biro Umum", "eselon3": "Bagian RT"}))
    _jalan(ruk.ubah_unit_kerja(e3, ruk.UnitUbah(parent_id=e2b), user=USER))
    p = _jalan(dbx.pegawai.find_one({"id": "p1"}, {"_id": 0}))
    assert p["eselon2"] == "Biro Keuangan" and p["eselon3"] == "Bagian RT"


def test_aset_unit_eselon_tiga_kini_IKUT_berubah(dbx):
    # Aset dulu berhenti di Eselon II, sehingga unit Eselon III ke bawah tak
    # dapat dikenali di sana dan asetnya sengaja tak disentuh. Kini aset
    # membawa lima tingkat seperti pegawai, dan pembatasan itu gugur bersama
    # sebabnya — tetapi hanya untuk aset yang jalurnya memang cocok.
    _, _, _, e3 = _pohon(dbx)
    _jalan(dbx.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "111111"}))
    _jalan(dbx.assets.insert_many([
        {"id": "a1", "activity_id": "k1", "eselon1": "Setjen",
         "eselon2": "Biro Umum", "eselon3": "Bagian RT"},
        {"id": "a2", "activity_id": "k1", "eselon1": "Setjen",
         "eselon2": "Biro Umum"},          # berhenti di Eselon II — bukan ini
    ]))
    r = _jalan(ruk.ubah_unit_kerja(e3, ruk.UnitUbah(nama_unit="Bagian Umum"),
                                   user=USER))
    assert r["ikut_diperbarui"]["aset"] == 1
    aset = {a["id"]: a.get("eselon3")
            for a in _jalan(dbx.assets.find({}, {"_id": 0}).to_list(10))}
    assert aset == {"a1": "Bagian Umum", "a2": None}


# ── 4. Lingkup kegiatan dicocokkan dengan master unit ───────────────────

def test_cocokkan_lingkup_mengembalikan_jalur_lengkapnya(dbx):
    _pohon(dbx)
    r = _jalan(ruk.cocokkan_lingkup(
        ruk.LingkupTeksIn(eselon1=[{"nama": "Setjen",
                                    "eselon2": ["Biro Umum"]}]), user=USER))
    # Induknya IKUT, lalu anaknya — urutan baca yang sama dengan yang diketik.
    assert [u["jalur"] for u in r["unit"]] == ["Setjen", "Setjen / Biro Umum"]
    assert [u["eselon"] for u in r["unit"]] == ["1", "2"]
    assert r["tak_cocok"] == []


def test_cocokkan_lingkup_melaporkan_yang_tak_ketemu(dbx):
    _pohon(dbx)
    r = _jalan(ruk.cocokkan_lingkup(
        ruk.LingkupTeksIn(eselon1=[{"nama": "Setjen",
                                    "eselon2": ["Biro Hantu"]}]), user=USER))
    # Induknya tetap terpilih; yang tak ketemu hanya anaknya, dan itu disebut.
    assert [u["jalur"] for u in r["unit"]] == ["Setjen"]
    assert r["tak_cocok"] == ["Setjen / Biro Hantu"]


def test_cocokkan_lingkup_tak_melihat_unit_satker_lain(dbx):
    _pohon(dbx)
    r = _jalan(ruk.cocokkan_lingkup(
        ruk.LingkupTeksIn(eselon1=[{"nama": "Setjen", "eselon2": []}]),
        user={"username": "asing", "role": "admin", "kode_satker": "222222"}))
    assert r["lingkup_unit"] == [] and r["tak_cocok"] == ["Setjen"]
