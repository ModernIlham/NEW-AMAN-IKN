"""Uji RANTAI Master Kode Klasifikasi Arsip → nomor surat.

Keluhan pemilik: "Master Kode Klasifikasi Arsip di setting penomeran ketika
sudah diisi ditambahkan, efeknya tidak menghasilkan apa apa pada bagian dari
penomeran". Rantainya memang putus di dua tempat, dan keduanya senyap:

1. ATURAN "SEMUA" DITOLAK. Layar pengaturan menambahkan baris aturan baru
   dengan kedua filternya kosong dan keterangannya sendiri berbunyi "kosong =
   berlaku untuk semua" — tapi validator menolak baris seperti itu, sehingga
   SELURUH simpanan pengaturan gagal 400. Aturan pertama yang dibuat siapa pun
   selalu gagal tersimpan, jadi kode klasifikasi tak pernah dipakai merakit
   nomor. Mesin `pilih_klasifikasi` sendiri sudah mendukungnya sejak awal.

2. KATALOG TAK PERNAH MENGAKU MENGANGGUR. Master klasifikasi memang cuma
   katalog; yang mengubah nomor adalah aturan otomatis / kode bawaan / isian
   manual. Tanpa penanda terpakai-atau-tidak, kode yang menganggur tampak
   persis sama dengan kode yang bekerja — sehingga "sudah diisi tapi tak ada
   efeknya" terlihat seperti kerusakan.

Uji di sini mengunci rantai itu ujung ke ujung: simpan pengaturan → pratinjau
nomor → nomor yang benar-benar terbit.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from routes.persuratan import KlasifikasiIn, PengaturanIn, SuratKeluarIn

ADMIN = {"username": "a", "role": "admin", "kode_satker": "527010"}
ADMIN_LAIN = {"username": "b", "role": "admin", "kode_satker": "999999"}
SUPER = {"username": "pusat", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


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


# ── (1) Aturan "berlaku untuk semua" bisa disimpan & benar-benar dipakai ────

def test_aturan_semua_tersimpan_dan_mengubah_nomor(dbx):
    """INTI. Aturan bawaan yang ditawarkan layar (kedua filter kosong) harus
    tersimpan DAN kodenya muncul pada nomor — inilah yang dulu gagal 400
    sehingga "efeknya tidak menghasilkan apa apa"."""
    async def skenario():
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "", "jenis_naskah": "", "kode": "UM.01"}]),
            user=ADMIN)
        atur = await rp._pengaturan("527010")
        pratinjau = await rp.pratinjau_nomor(
            jenis_naskah="Nota Dinas", modul="umum", _user=ADMIN)
        return atur, pratinjau
    atur, pratinjau = _jalan(skenario())
    assert atur["peta_klasifikasi"] == [
        {"modul": "", "jenis_naskah": "", "kode": "UM.01"}]
    assert pratinjau["kode_klasifikasi"] == "UM.01"
    assert pratinjau["sumber_klasifikasi"] == "pemetaan"
    assert "UM.01" in pratinjau["nomor"]


def test_aturan_semua_tak_menindih_aturan_spesifik(dbx):
    """Aturan 'semua' adalah JARING. Kalau ia menimpa aturan spesifik,
    mengizinkannya justru merusak pemetaan yang sudah dipakai satker."""
    async def skenario():
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "", "jenis_naskah": "", "kode": "UM.01"},
                {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "PL.02"}]),
            user=ADMIN)
        return (await rp.pratinjau_nomor(jenis_naskah="Laporan",
                                         modul="pelaporan", _user=ADMIN),
                await rp.pratinjau_nomor(jenis_naskah="Nota Dinas",
                                         modul="umum", _user=ADMIN))
    spesifik, sisanya = _jalan(skenario())
    assert spesifik["kode_klasifikasi"] == "PL.02"
    assert sisanya["kode_klasifikasi"] == "UM.01"


def test_aturan_kembar_ditolak_dengan_pesan_yang_menunjuk(dbx):
    """Baris kedua tak akan pernah dipakai — lebih baik ditolak terang-terangan
    daripada tersimpan lalu diam-diam tak berpengaruh (persis keluhan awal)."""
    from fastapi import HTTPException

    async def skenario():
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "pelaporan", "jenis_naskah": "", "kode": "PL.02"},
                {"modul": "pelaporan", "jenis_naskah": "", "kode": "XX.99"}]),
            user=ADMIN)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400
    assert "#1" in str(e.value.detail)


def test_nomor_yang_benar_benar_terbit_memakai_kodenya(dbx):
    """Pratinjau boleh saja benar sementara jalur booking memakai kode lain —
    uji ini menutup celah itu dengan memesan nomor sungguhan."""
    async def skenario():
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "pelaporan", "jenis_naskah": "", "kode": "PL.02"}]),
            user=ADMIN)
        return await _unwrap(rp.booking_surat_keluar)(
            SuratKeluarIn(perihal="Penyampaian LHI", modul="pelaporan",
                          jenis_naskah="Laporan"),
            user=ADMIN)
    surat = _jalan(skenario())
    assert surat["kode_klasifikasi"] == "PL.02"
    assert "PL.02" in surat["nomor"]


# ── (2) Katalog mengaku terpakai atau menganggur ────────────────────────────

async def _seed_katalog(dbx):
    for kode, uraian in (("PL.02", "Pelaporan"), ("UM.01", "Umum"),
                         ("KU.03", "Keuangan")):
        await rp.tambah_klasifikasi(
            KlasifikasiIn(kode=kode, uraian=uraian), user=ADMIN)


def test_kode_yang_belum_dipasang_ditandai_belum_dipakai(dbx):
    """Inilah jawaban langsung atas 'sudah diisi tapi tak ada efeknya':
    servernya kini yang mengatakannya, bukan pemakainya yang harus menebak."""
    async def skenario():
        await _seed_katalog(dbx)
        return await rp.daftar_klasifikasi(_user=ADMIN)
    items = {k["kode"]: k for k in _jalan(skenario())["items"]}
    for kode in ("PL.02", "UM.01", "KU.03"):
        assert items[kode]["dipakai_aturan"] == 0
        assert items[kode]["bawaan"] is False


def test_kode_yang_dipasang_aturan_dihitung(dbx):
    async def skenario():
        await _seed_katalog(dbx)
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "pelaporan", "jenis_naskah": "", "kode": "PL.02"},
                {"modul": "wasdal", "jenis_naskah": "", "kode": "PL.02"}]),
            user=ADMIN)
        return await rp.daftar_klasifikasi(_user=ADMIN)
    items = {k["kode"]: k for k in _jalan(skenario())["items"]}
    assert items["PL.02"]["dipakai_aturan"] == 2
    assert items["UM.01"]["dipakai_aturan"] == 0


def test_kode_bawaan_dihitung_terpakai_walau_tanpa_aturan(dbx):
    """Kode bawaan memengaruhi SETIAP nomor yang tak kena aturan — menyebutnya
    'belum dipakai' akan menyesatkan ke arah sebaliknya."""
    async def skenario():
        await _seed_katalog(dbx)
        await rp.set_pengaturan_persuratan(
            PengaturanIn(kode_klasifikasi_default="UM.01"), user=ADMIN)
        return await rp.daftar_klasifikasi(_user=ADMIN)
    items = {k["kode"]: k for k in _jalan(skenario())["items"]}
    assert items["UM.01"]["bawaan"] is True
    assert items["PL.02"]["bawaan"] is False


def test_penanda_terpakai_dihitung_per_satker_pemanggil(dbx):
    """Aturan satker A tak boleh membuat kode Bersama tampak terpakai di
    satker B — penandanya harus ikut pengaturan EFEKTIF si pemanggil."""
    async def skenario():
        await rp.tambah_klasifikasi(
            KlasifikasiIn(kode="PL.02", uraian="Pelaporan"), user=SUPER)
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "pelaporan", "jenis_naskah": "", "kode": "PL.02"}]),
            user=ADMIN)
        return (await rp.daftar_klasifikasi(_user=ADMIN),
                await rp.daftar_klasifikasi(_user=ADMIN_LAIN))
    punya_aturan, tanpa_aturan = _jalan(skenario())
    assert punya_aturan["items"][0]["dipakai_aturan"] == 1
    assert tanpa_aturan["items"][0]["dipakai_aturan"] == 0


def test_satker_mewarisi_aturan_universal_ikut_terhitung(dbx):
    """Selama satker belum punya aturan sendiri, aturan Universal-lah yang
    benar-benar berlaku baginya — dan penandanya wajib mengatakan itu."""
    async def skenario():
        await rp.tambah_klasifikasi(
            KlasifikasiIn(kode="UM.01", uraian="Umum"), user=SUPER)
        await rp.set_pengaturan_persuratan(
            PengaturanIn(peta_klasifikasi=[
                {"modul": "", "jenis_naskah": "", "kode": "UM.01"}]),
            user=SUPER)
        return await rp.daftar_klasifikasi(_user=ADMIN)
    items = _jalan(skenario())["items"]
    assert items[0]["dipakai_aturan"] == 1
