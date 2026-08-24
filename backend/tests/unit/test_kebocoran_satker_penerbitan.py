"""Dokumen ber-register WAJIB bersatker — penutup kebocoran lintas satker.

Laporan pemilik: *"pada saat mengganti role masih ada kebocoran data di
registrasi persuratan saat pembuatan LPB."*

Diukur sebelum ditambal, dengan menjalankan jalurnya sungguhan:

  - Super-admin PUSAT (belum memilih Satker Aktif) memesan nomor LPB.
  - Suratnya tersimpan berstempel `kode_satker: ""`.
  - `scope_query_field_satker` SENGAJA meloloskan "" (kompatibilitas data era
    lama), sehingga surat itu tampil di Registrasi Persuratan satker 527001
    DAN 999999 — dua satker yang tak ada hubungannya dengan dokumen itu.
  - Lebih berat lagi: `_seed_agenda` memperlakukan surat tanpa stempel sebagai
    milik satker yang membacanya, jadi satker yang baru menerbitkan surat
    PERTAMANYA mendapat nomor 002 — nomor 001 sudah dihabiskan surat yang
    bukan miliknya.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp

PUSAT = {"username": "superadmin", "role": "admin", "kode_satker": ""}
SATKER_A = {"username": "opa", "role": "operator", "kode_satker": "527001"}
SATKER_B = {"username": "opb", "role": "operator", "kode_satker": "999999"}


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
    for m in (rp, su):
        monkeypatch.setattr(m, "db", fake, raising=False)
        if hasattr(m, "log_audit"):
            monkeypatch.setattr(m, "log_audit", _diam, raising=False)
    return fake


class TestPenerbitanTanpaSatkerDitolak:
    def test_pemanggil_pusat_tanpa_satker_aktif_DITOLAK(self, dbx):
        async def skenario():
            with pytest.raises(rp.HTTPException) as e:
                await rp.booking_nomor_lpb(PUSAT, "2026-08-24", perihal="LPB")
            assert e.value.status_code == 400
        _jalan(skenario())

    def test_penolakannya_menunjuk_jalan_keluarnya(self, dbx):
        """Penolakan yang tak menyebut caranya membuat orang mengira sistemnya
        rusak — padahal ia hanya perlu memilih Satker Aktif."""
        async def skenario():
            with pytest.raises(rp.HTTPException) as e:
                await rp.booking_nomor_lpb(PUSAT, "2026-08-24", perihal="LPB")
            assert "Satker Aktif" in str(e.value.detail)
        _jalan(skenario())

    def test_penolakan_tak_meninggalkan_surat_yatim(self, dbx):
        """Gerbangnya berdiri SEBELUM nomor dipesan dan surat ditulis; kalau
        tidak, penolakan justru melahirkan surat "" yang mau dicegahnya."""
        async def skenario():
            with pytest.raises(rp.HTTPException):
                await rp.booking_nomor_lpb(PUSAT, "2026-08-24", perihal="LPB")
            assert await dbx.surat.count_documents({}) == 0
        _jalan(skenario())

    def test_penolakan_tak_menghabiskan_nomor_agenda(self, dbx):
        """Counter yang terlanjur maju membuat satker kehilangan nomor 001
        tanpa satu pun surat terbit."""
        async def skenario():
            with pytest.raises(rp.HTTPException):
                await rp.booking_nomor_lpb(PUSAT, "2026-08-24", perihal="LPB")
            assert await dbx.counters.count_documents({}) == 0
        _jalan(skenario())

    def test_satker_DOKUMEN_menyelamatkan_pemanggil_pusat(self, dbx):
        """Super-admin memang boleh mengerjakan dokumen satker lain — selama
        satker DOKUMENNYA diketahui, nomornya terbit di buku agenda pemiliknya
        dan tak ada yang perlu ditolak."""
        async def skenario():
            nomor, sid = await rp.booking_nomor_lpb(
                PUSAT, "2026-08-24", perihal="LPB", kode_satker="527001")
            assert nomor
            surat = await dbx.surat.find_one({"id": sid})
            assert surat["kode_satker"] == "527001"
        _jalan(skenario())

    def test_operator_ber_satker_tak_terganggu(self, dbx):
        async def skenario():
            nomor, sid = await rp.booking_nomor_lpb(
                SATKER_A, "2026-08-24", perihal="LPB")
            assert nomor
            surat = await dbx.surat.find_one({"id": sid})
            assert surat["kode_satker"] == "527001"
        _jalan(skenario())


class TestTakAdaLagiSuratTanpaStempel:
    def test_surat_terbitan_baru_tak_pernah_terlihat_satker_lain(self, dbx):
        """INTI laporan pemilik. Sebelum ditambal, surat ini terlihat oleh
        527001 DAN 999999 sekaligus."""
        from shared_utils import scope_query_field_satker

        async def skenario():
            await rp.booking_nomor_lpb(SATKER_A, "2026-08-24", perihal="LPB A")
            terlihat_b = await dbx.surat.count_documents(
                scope_query_field_satker(SATKER_B, {"jenis": "keluar"}))
            assert terlihat_b == 0, "surat satker A bocor ke register satker B"
            terlihat_a = await dbx.surat.count_documents(
                scope_query_field_satker(SATKER_A, {"jenis": "keluar"}))
            assert terlihat_a == 1
        _jalan(skenario())

    def test_nomor_agenda_satker_lain_tak_ikut_terpakai(self, dbx):
        """Surat satker A tak boleh menggeser deret satker B — sebelum
        ditambal, surat pusat berstempel "" membuat satker berikutnya mulai
        dari 002."""
        async def skenario():
            n_a, _ = await rp.booking_nomor_lpb(SATKER_A, "2026-08-24", perihal="A")
            n_b, _ = await rp.booking_nomor_lpb(SATKER_B, "2026-08-24", perihal="B")
            assert n_a == n_b, (
                f"deret dua satker saling menggeser: {n_a} vs {n_b}")
        _jalan(skenario())


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


class TestRegistrasiManualJugaBersatker:
    """Jalur yang PALING sering dipakai orang: Registrasi Persuratan.

    Laporan pemilik menyebut "registrasi persuratan" — dan memang bukan hanya
    booking otomatis LPB yang bocor. Booking MANUAL surat keluar dan pencatatan
    surat masuk memakai pola yang sama (`_ks = kode_satker_user(user)`),
    sehingga pemanggil pusat menstempelnya "" pula.
    """

    def test_surat_keluar_manual_tanpa_satker_DITOLAK(self, dbx):
        async def skenario():
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.booking_surat_keluar)(
                    rp.SuratKeluarIn(perihal="Undangan rapat"), user=PUSAT)
            assert e.value.status_code == 400
            assert "Satker Aktif" in str(e.value.detail)
            assert await dbx.surat.count_documents({}) == 0
            assert await dbx.counters.count_documents({}) == 0
        _jalan(skenario())

    def test_surat_masuk_manual_tanpa_satker_DITOLAK(self, dbx):
        async def skenario():
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.agenda_surat_masuk)(
                    rp.SuratMasukIn(nomor_surat="B-9/2026", pengirim="KPKNL",
                                    perihal="Permintaan data"), user=PUSAT)
            assert e.value.status_code == 400
            assert "Satker Aktif" in str(e.value.detail)
            assert await dbx.surat.count_documents({}) == 0
        _jalan(skenario())

    def test_operator_ber_satker_tetap_bisa_mencatat_keduanya(self, dbx):
        """Pembanding yang membuat kedua uji di atas bermakna: penjaga yang
        menolak SEMUA orang juga akan melewatkannya."""
        async def skenario():
            k = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Undangan rapat"), user=SATKER_A)
            m = await _unwrap(rp.agenda_surat_masuk)(
                rp.SuratMasukIn(nomor_surat="B-9/2026", pengirim="KPKNL",
                                perihal="Permintaan data"), user=SATKER_A)
            assert k["kode_satker"] == "527001"
            assert m["kode_satker"] == "527001"
        _jalan(skenario())

    def test_surat_manual_satker_A_tak_terlihat_satker_B(self, dbx):
        from shared_utils import scope_query_field_satker

        async def skenario():
            await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Rahasia satker A"), user=SATKER_A)
            assert await dbx.surat.count_documents(
                scope_query_field_satker(SATKER_B, {})) == 0
        _jalan(skenario())
