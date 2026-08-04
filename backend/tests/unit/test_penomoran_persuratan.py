"""Uji MESIN PENOMORAN persuratan — reset bulanan + nomor sisipan (backdate).

Dua fitur ini mengubah kunci deret nomor resmi. Salah satu saja meleset —
counter tak ter-seed, lantai migrasi bocor ke bulan berikutnya, sub-nomor
sisipan balapan — hasilnya nomor surat ganda atau deret yang tak pernah
kembali ke 001, dan keduanya tak bisa diperbaiki tanpa menomori ulang arsip.
Uji memakai mongomock (tanpa Mongo betulan) meniru pola test_lpb_persediaan_ppk.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from routes.persuratan import SuratKeluarIn, SuratMasukIn

USER = {"username": "arsiparis", "role": "admin", "kode_satker": "527010"}


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


def _keluar(**kw):
    dasar = {"perihal": "Laporan uji", "jenis_naskah": "Laporan",
             "modul": "umum"}
    dasar.update(kw)
    return SuratKeluarIn(**dasar)


class TestResetBulanan:
    def test_bulan_berganti_nomor_kembali_ke_satu(self, dbx):
        async def skenario():
            a = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-03"), user=USER)
            b = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-04"), user=USER)
            c = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-09-01"), user=USER)
            assert (a["no_agenda"], b["no_agenda"]) == (1, 2)
            assert c["no_agenda"] == 1, "awal bulan baru wajib kembali ke 001"
            # Nomor lengkap tetap unik: unsur bulan membedakan 001/VIII vs 001/IX
            assert a["nomor"] != c["nomor"]
            assert "VIII" in a["nomor"] and "IX" in c["nomor"]
        _jalan(skenario())

    def test_setelan_tahunan_deret_menyambung_lintas_bulan(self, dbx):
        async def skenario():
            await dbx.persuratan_settings.insert_one(
                {"type": "satker", "kode_satker": USER["kode_satker"],
                 "reset_urut": "tahunan"})
            a = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-31"), user=USER)
            b = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-09-01"), user=USER)
            assert (a["no_agenda"], b["no_agenda"]) == (1, 2)
        _jalan(skenario())

    def test_transisi_meneruskan_deret_tahunan_lalu_bulan_baru_reset(self, dbx):
        """Migrasi tahunan→bulanan: bulan berjalan MENERUSKAN posisi counter
        tahunan (nomor hangus tak terbit ulang), bulan berikutnya mulai 001 —
        counter tahunan hanya boleh jadi lantai SEKALI."""
        async def skenario():
            kode = USER["kode_satker"]
            # Jejak era tahunan: counter di posisi 76, surat terakhir Agustus.
            await dbx.counters.insert_one(
                {"_id": f"surat_keluar_2026:{kode}", "seq": 76})
            await dbx.surat.insert_one(
                {"id": "lama-1", "jenis": "keluar", "tahun": 2026,
                 "no_agenda": 74, "kode_satker": kode,
                 "tanggal_surat": "2026-08-01", "created_at": "2026-08-01T00:00:00"})
            a = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-04"), user=USER)
            assert a["no_agenda"] == 77, (
                "bulan transisi wajib meneruskan posisi counter tahunan (76) — "
                "meneruskan maks dokumen (74) menerbitkan ulang nomor hangus")
            b = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-09-01"), user=USER)
            assert b["no_agenda"] == 1, (
                "lantai counter tahunan bocor ke bulan berikutnya — "
                "deret tak pernah kembali ke 001")
        _jalan(skenario())

    def test_surat_masuk_ikut_reset_bulanan(self, dbx, monkeypatch):
        async def skenario():
            m1 = await rp.agenda_surat_masuk(SuratMasukIn(
                nomor_surat="X-1", pengirim="KPKNL", perihal="uji"), user=USER)
            assert m1["no_agenda"] == 1
            # Bulan agenda berganti → dokumen bulan lalu tak terhitung seed.
            await dbx.surat.update_one(
                {"id": m1["id"]},
                {"$set": {"created_at": "2000-01-01T00:00:00+00:00"}})
            await dbx.counters.delete_many({})
            m2 = await rp.agenda_surat_masuk(SuratMasukIn(
                nomor_surat="X-2", pengirim="KPKNL", perihal="uji"), user=USER)
            assert m2["no_agenda"] == 1
        _jalan(skenario())


class TestNomorSisipan:
    async def _seed_agustus(self):
        await rp.booking_surat_keluar(
            _keluar(tanggal_surat="2026-08-01"), user=USER)   # 001
        await rp.booking_surat_keluar(
            _keluar(tanggal_surat="2026-08-03"), user=USER)   # 002

    def test_sisipan_menempel_nomor_terakhir_tanggal_itu(self, dbx):
        async def skenario():
            await self._seed_agustus()
            s = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01", sisipan=True), user=USER)
            assert (s["no_agenda"], s["sisipan"]) == (1, 1)
            assert "001.01" in s["nomor"]
            # Sisipan kedua tanggal sama → sub berikutnya, bukan duplikat.
            s2 = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01", sisipan=True), user=USER)
            assert (s2["no_agenda"], s2["sisipan"]) == (1, 2)
            assert "001.02" in s2["nomor"]
        _jalan(skenario())

    def test_sisipan_tanggal_di_antara_menempel_nomor_sebelumnya(self, dbx):
        async def skenario():
            await self._seed_agustus()
            # 2026-08-02 tak punya surat — jangkar = nomor terakhir SEBELUMNYA.
            s = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-02", sisipan=True), user=USER)
            assert (s["no_agenda"], s["sisipan"]) == (1, 1)
        _jalan(skenario())

    def test_sisipan_tanpa_jangkar_ditolak_dengan_arahan(self, dbx):
        from fastapi import HTTPException
        async def skenario():
            with pytest.raises(HTTPException) as galat:
                await rp.booking_surat_keluar(
                    _keluar(tanggal_surat="2026-08-01", sisipan=True),
                    user=USER)
            assert "booking biasa" in str(galat.value.detail)
        _jalan(skenario())

    def test_sisipan_tak_menaikkan_counter_utama(self, dbx):
        async def skenario():
            await self._seed_agustus()
            await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01", sisipan=True), user=USER)
            c = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-04"), user=USER)
            assert c["no_agenda"] == 3, (
                "sisipan ikut memakan deret utama — nomor 003 melompat")
        _jalan(skenario())

    def test_counter_sisipan_terseed_dari_dokumen(self, dbx):
        """Pemulihan backup tanpa koleksi counters tak boleh menduplikat .01."""
        async def skenario():
            await self._seed_agustus()
            await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01", sisipan=True), user=USER)
            await dbx.counters.delete_many(
                {"_id": {"$regex": ":s1$"}})
            s2 = await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01", sisipan=True), user=USER)
            assert s2["sisipan"] == 2
        _jalan(skenario())


class TestPratinjau:
    def test_pratinjau_sisipan_tanpa_mutasi(self, dbx):
        async def skenario():
            await rp.booking_surat_keluar(
                _keluar(tanggal_surat="2026-08-01"), user=USER)
            p = await rp.pratinjau_nomor(
                tanggal_surat="2026-08-01", sisipan=True, _user=USER)
            assert p["urut_berikut"] == "001.01"
            # Dua kali pratinjau → hasil sama (counter tidak naik).
            p2 = await rp.pratinjau_nomor(
                tanggal_surat="2026-08-01", sisipan=True, _user=USER)
            assert p2["urut_berikut"] == "001.01"
        _jalan(skenario())

    def test_pratinjau_sisipan_tanpa_jangkar_menjelaskan(self, dbx):
        async def skenario():
            p = await rp.pratinjau_nomor(
                tanggal_surat="2026-08-01", sisipan=True, _user=USER)
            assert p["nomor"] == "" and "booking biasa" in p["sisipan_galat"]
        _jalan(skenario())


class TestPengaturanReset:
    def test_bulanan_tanpa_unsur_bulan_ditolak(self, dbx):
        from fastapi import HTTPException
        from routes.persuratan import PengaturanIn
        async def skenario():
            with pytest.raises(HTTPException) as galat:
                await rp.set_pengaturan_persuratan(PengaturanIn(
                    format_nomor="{urut}/{tahun}", reset_urut="bulanan"),
                    user=USER)
            assert "bulan" in str(galat.value.detail)
        _jalan(skenario())

    def test_nilai_reset_asing_ditolak(self, dbx):
        from fastapi import HTTPException
        from routes.persuratan import PengaturanIn
        async def skenario():
            with pytest.raises(HTTPException):
                await rp.set_pengaturan_persuratan(
                    PengaturanIn(reset_urut="mingguan"), user=USER)
        _jalan(skenario())
