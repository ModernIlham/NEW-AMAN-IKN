"""Uji ISOLASI PER-SATKER master klasifikasi arsip + asal-usul pengaturan.

Mode gagal yang dijaga di sini senyap semuanya: entri klasifikasi satu satker
tampil (atau terhapus!) di satker lain, admin satker mengelola entri Bersama,
guard "masih dipakai" memblokir hapus karena kode senama milik satker LAIN,
dan tombol Simpan pengaturan diam-diam memaku salinan nilai Universal sebagai
override satker sehingga satker berhenti mengikuti perubahan Universal.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from routes.persuratan import KlasifikasiIn, PengaturanIn
from persuratan_utils import gabung_klasifikasi, sumber_pengaturan

ADMIN_A = {"username": "a", "role": "admin", "kode_satker": "527010"}
ADMIN_B = {"username": "b", "role": "admin", "kode_satker": "999999"}
SUPER = {"username": "pusat", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    for nama in ("jadwalkan_sync", "jadwalkan_hapus"):
        monkeypatch.setattr(rp, nama, lambda *a, **k: None, raising=False)
    return fake


# ── Fungsi murni ─────────────────────────────────────────────────────────────

def test_gabung_klasifikasi_satker_menimpa_bersama():
    bersama = [{"kode": "PL.02", "uraian": "Pelaporan"},
               {"kode": "UM.01", "uraian": "Umum"}]
    satker = [{"kode": "PL.02", "uraian": "Pelaporan versi satker"},
              {"kode": "KU.03", "uraian": "Keuangan"}]
    hasil = gabung_klasifikasi(bersama, satker)
    assert [k["kode"] for k in hasil] == ["KU.03", "PL.02", "UM.01"]
    assert next(k for k in hasil if k["kode"] == "PL.02")["uraian"] == (
        "Pelaporan versi satker")


def test_sumber_pengaturan_membedakan_tiga_asal():
    g = {"format_nomor": "X-{urut}", "kode_unit": "OIKN"}
    s = {"kode_unit": "PPTHD", "reset_urut": ""}
    asal = sumber_pengaturan(g, s)
    assert asal["kode_unit"] == "satker"          # override terisi
    assert asal["format_nomor"] == "global"       # warisan Universal
    assert asal["reset_urut"] == "bawaan"         # '' bukan pengisi
    assert asal["peta_klasifikasi"] == "bawaan"


# ── CRUD ber-scope ───────────────────────────────────────────────────────────

def test_entri_satker_tak_tampil_di_satker_lain(dbx):
    async def skenario():
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.01", uraian="Khusus A"),
                                    user=ADMIN_A)
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="BR.01", uraian="Bersama"),
                                    user=SUPER)
        a = await rp.daftar_klasifikasi(_user=ADMIN_A)
        b = await rp.daftar_klasifikasi(_user=ADMIN_B)
        return a, b
    a, b = _jalan(skenario())
    assert {k["kode"] for k in a["items"]} == {"KH.01", "BR.01"}
    assert {k["kode"] for k in b["items"]} == {"BR.01"}, \
        "entri milik satker A bocor ke satker B"


def test_admin_satker_tak_boleh_kelola_entri_bersama(dbx):
    async def skenario():
        e = await rp.tambah_klasifikasi(KlasifikasiIn(kode="BR.02"), user=SUPER)
        with pytest.raises(HTTPException) as ex1:
            await rp.hapus_klasifikasi(e["id"], user=ADMIN_A)
        with pytest.raises(HTTPException) as ex2:
            await rp.ubah_klasifikasi(e["id"], KlasifikasiIn(kode="BR.03"),
                                      user=ADMIN_A)
        return ex1.value.status_code, ex2.value.status_code
    assert _jalan(skenario()) == (403, 403)


def test_kode_senama_dua_satker_sah_tapi_bentrok_dalam_satu_scope(dbx):
    async def skenario():
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.02"), user=ADMIN_A)
        # Satker lain boleh punya kode senama (pedoman berbeda per satker).
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.02"), user=ADMIN_B)
        # Dalam satu scope tetap unik.
        with pytest.raises(HTTPException) as ex:
            await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.02"), user=ADMIN_A)
        return ex.value.status_code
    assert _jalan(skenario()) == 409


def test_satker_boleh_override_kode_bersama(dbx):
    """Kode senama dengan entri Bersama = OVERRIDE pedoman satker (sah);
    daftar efektif menampilkan versi satker menggantikan Bersama."""
    async def skenario():
        await rp.tambah_klasifikasi(
            KlasifikasiIn(kode="UM.01", uraian="Umum (Bersama)"), user=SUPER)
        await rp.tambah_klasifikasi(
            KlasifikasiIn(kode="UM.01", uraian="Umum versi satker"), user=ADMIN_A)
        return await rp.referensi_persuratan(_user=ADMIN_A)
    ref = _jalan(skenario())
    um = [k for k in ref["klasifikasi"] if k["kode"] == "UM.01"]
    assert len(um) == 1 and um[0]["uraian"] == "Umum versi satker"


def test_hapus_tak_terhalang_kode_senama_satker_lain(dbx):
    """Peta satker B merujuk 'KH.03' miliknya sendiri — satker A harus tetap
    boleh menghapus 'KH.03' MILIKNYA (rujukan B tidak jatuh ke entri A)."""
    async def skenario():
        ea = await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.03"), user=ADMIN_A)
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.03"), user=ADMIN_B)
        await dbx.persuratan_settings.insert_one(
            {"type": "satker", "kode_satker": "999999",
             "peta_klasifikasi": [{"modul": "umum", "jenis_naskah": "",
                                   "kode": "KH.03"}]})
        return await rp.hapus_klasifikasi(ea["id"], user=ADMIN_A)
    assert _jalan(skenario())["ok"] is True


def test_hapus_terhalang_bila_peta_satker_sendiri_memakainya(dbx):
    async def skenario():
        e = await rp.tambah_klasifikasi(KlasifikasiIn(kode="KH.04"), user=ADMIN_A)
        await dbx.persuratan_settings.insert_one(
            {"type": "satker", "kode_satker": "527010",
             "peta_klasifikasi": [{"modul": "umum", "jenis_naskah": "",
                                   "kode": "KH.04"}]})
        with pytest.raises(HTTPException) as ex:
            await rp.hapus_klasifikasi(e["id"], user=ADMIN_A)
        return ex.value.status_code
    assert _jalan(skenario()) == 409


def test_hapus_entri_bersama_terhalang_rujukan_satker_tanpa_entri_sendiri(dbx):
    """Entri Bersama masih dirujuk peta satker B (B tak punya entri sendiri) →
    hapus ditolak; setelah B punya entri sendiri berkode sama, rujukan B jatuh
    ke miliknya dan entri Bersama boleh dihapus."""
    async def skenario():
        e = await rp.tambah_klasifikasi(KlasifikasiIn(kode="BR.04"), user=SUPER)
        await dbx.persuratan_settings.insert_one(
            {"type": "satker", "kode_satker": "999999",
             "peta_klasifikasi": [{"modul": "umum", "jenis_naskah": "",
                                   "kode": "BR.04"}]})
        try:
            await rp.hapus_klasifikasi(e["id"], user=SUPER)
            gagal_pertama = None
        except HTTPException as ex:
            gagal_pertama = ex.status_code
        await rp.tambah_klasifikasi(KlasifikasiIn(kode="BR.04"), user=ADMIN_B)
        hasil = await rp.hapus_klasifikasi(e["id"], user=SUPER)
        return gagal_pertama, hasil["ok"]
    assert _jalan(skenario()) == (409, True)


def test_referensi_menggabung_dengan_entri_satker_menang(dbx):
    async def skenario():
        await dbx.klasifikasi_arsip.insert_many([
            # Era lama: tanpa field kode_satker sama sekali = Bersama.
            {"id": "l1", "kode": "PL.02", "uraian": "Pelaporan (Bersama)",
             "aktif": True},
            {"id": "l2", "kode": "NA.01", "uraian": "Nonaktif", "aktif": False},
            {"id": "s1", "kode": "PL.02", "uraian": "Pelaporan versi satker",
             "kode_satker": "527010", "aktif": True},
            {"id": "s2", "kode": "KH.05", "uraian": "Khusus",
             "kode_satker": "527010", "aktif": True},
            {"id": "x1", "kode": "ZZ.09", "uraian": "Milik satker lain",
             "kode_satker": "999999", "aktif": True},
        ])
        return await rp.referensi_persuratan(_user=ADMIN_A)
    ref = _jalan(skenario())
    peta = {k["kode"]: k for k in ref["klasifikasi"]}
    assert set(peta) == {"PL.02", "KH.05"}
    assert peta["PL.02"]["uraian"] == "Pelaporan versi satker"


# ── Pengaturan: asal-usul & kembali-ke-Universal ─────────────────────────────

def test_get_pengaturan_membawa_scope_dan_sumber(dbx):
    async def skenario():
        await dbx.persuratan_settings.insert_one(
            {"type": "global", "kode_unit": "OIKN",
             "format_nomor": "{kode_keamanan}-{urut}/{bulan}/{tahun}"})
        await dbx.persuratan_settings.insert_one(
            {"type": "satker", "kode_satker": "527010", "kode_unit": "PPTHD"})
        return await rp.get_pengaturan_persuratan(_user=ADMIN_A)
    d = _jalan(skenario())
    assert d["scope"] == "527010"
    assert d["kode_unit"] == "PPTHD"
    assert d["sumber"]["kode_unit"] == "satker"
    assert d["sumber"]["format_nomor"] == "global"
    assert d["sumber"]["reset_urut"] == "bawaan"


def test_kosongkan_field_satker_kembali_ikut_universal(dbx):
    """Override kode_unit satker dihapus (kirim '') → nilai efektif kembali
    warisan Universal, BUKAN string kosong / salinan terpaku."""
    async def skenario():
        await dbx.persuratan_settings.insert_one(
            {"type": "global", "kode_unit": "OIKN"})
        await rp.set_pengaturan_persuratan(
            PengaturanIn(kode_unit="PPTHD"), user=ADMIN_A)
        satu = await rp.get_pengaturan_persuratan(_user=ADMIN_A)
        await rp.set_pengaturan_persuratan(
            PengaturanIn(kode_unit=""), user=ADMIN_A)
        dua = await rp.get_pengaturan_persuratan(_user=ADMIN_A)
        return satu, dua
    satu, dua = _jalan(skenario())
    assert (satu["kode_unit"], satu["sumber"]["kode_unit"]) == ("PPTHD", "satker")
    assert (dua["kode_unit"], dua["sumber"]["kode_unit"]) == ("OIKN", "global")


def test_reset_urut_kosong_sah_untuk_satker_tapi_ditolak_global(dbx):
    async def skenario():
        hasil = await rp.set_pengaturan_persuratan(
            PengaturanIn(reset_urut=""), user=ADMIN_A)
        with pytest.raises(HTTPException) as ex:
            await rp.set_pengaturan_persuratan(
                PengaturanIn(reset_urut=""), user=SUPER)
        return hasil["reset_urut"], ex.value.status_code
    reset, kode = _jalan(skenario())
    assert reset == "bulanan"      # efektif jatuh ke bawaan
    assert kode == 400


def test_validasi_reset_bulanan_menilai_nilai_universal_yang_akan_berlaku(dbx):
    """Satker menghapus override format ('') saat efektif Universal TANPA
    unsur bulan dan reset bulanan → harus DITOLAK atas nilai Universal yang
    akan benar-benar berlaku (bukan lolos karena string kosong)."""
    async def skenario():
        await dbx.persuratan_settings.insert_one(
            {"type": "global", "format_nomor": "{urut}/{tahun}",
             "reset_urut": "bulanan"})
        await dbx.persuratan_settings.insert_one(
            {"type": "satker", "kode_satker": "527010",
             "format_nomor": "{urut}/{bulan}/{tahun}"})
        with pytest.raises(HTTPException) as ex:
            await rp.set_pengaturan_persuratan(
                PengaturanIn(format_nomor=""), user=ADMIN_A)
        return ex.value.status_code, ex.value.detail
    kode, detail = _jalan(skenario())
    assert kode == 400 and "bulan" in detail
