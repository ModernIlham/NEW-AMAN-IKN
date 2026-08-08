"""Penjadwal latar dihentikan sebelum koneksi Mongo ditutup — temuan U22.

`shutdown_event` menghentikan event bus, Meilisearch, dan Redis — lalu langsung
`client.close()`. Tiga loop periodik yang dijadwalkan saat startup TIDAK pernah
dibatalkan:

    start_backup_scheduler()   -> backup_scheduler_loop()
    start_job_maintenance()    -> _job_maintenance_loop()
    start_webp_converter()     -> _loop()

`client.close()` lalu mencabut koneksi dari bawah loop yang mungkin sedang di
tengah kuerinya. Akibatnya dua: traceback menakutkan di log tiap kali shutdown
(yang lama-lama diabaikan orang, sehingga traceback SUNGGUHAN ikut terabaikan),
dan — lebih buruk — sebuah loop bisa terpotong di antara dua tulisan tanpa
sempat menjalankan blok `except`-nya sendiri.

**Yang sengaja TIDAK dilakukan** dan dijaga uji di bawah: membatalkan seluruh
isi `_BG_TASKS`. Himpunan itu juga menampung `run_backup_task` dan
`run_restore_task` yang sedang berjalan. Membatalkan RESTORE di tengah jalan
adalah keputusan integritas data, bukan kebersihan shutdown — restore punya
jalur rollback sendiri, dan memicunya dari shutdown berarti memulai pemulihan
yang detik berikutnya ikut mati bersama prosesnya.
"""
import asyncio
import inspect
import pathlib
import re

import pytest

import jobs
import webp_converter

BACKEND = pathlib.Path(__file__).resolve().parents[2]


def _tanpa_komentar(teks: str) -> str:
    """Penjaga struktural harus kebal prosa — komentar di berkas ini dan di
    kode produksinya menyebut `_BG_TASKS`, `cancel()`, dan `client.close()`
    berkali-kali."""
    teks = re.sub(r'"""[\s\S]*?"""', "", teks)
    return re.sub(r"^\s*#.*$", "", teks, flags=re.M)


class TestUrutanShutdown:
    SRC = (BACKEND / "server.py").read_text(encoding="utf-8")
    KODE = _tanpa_komentar(SRC)

    def test_ketiga_penjadwal_dihentikan(self):
        i = self.KODE.index("async def shutdown_event")
        blok = self.KODE[i:i + 3000]
        for fn in ("stop_job_maintenance", "stop_webp_converter",
                   "stop_backup_scheduler"):
            assert fn in blok, fn

    def test_dihentikan_SEBELUM_client_close(self):
        """Inti U22: urutannya yang jadi soal, bukan sekadar keberadaannya.

        Menutup koneksi lebih dulu berarti loop yang sedang berkueri menerima
        galat koneksi alih-alih pembatalan yang tertib.
        """
        i = self.KODE.index("async def shutdown_event")
        blok = self.KODE[i:]
        i_stop = blok.index("stop_job_maintenance")
        i_close = blok.index("client.close()")
        assert i_stop > -1 and i_close > -1
        assert i_stop < i_close, "penjadwal dihentikan setelah koneksi ditutup"

    def test_kegagalan_menghentikan_TIDAK_menggagalkan_shutdown(self):
        # Shutdown yang melempar meninggalkan proses menggantung sampai
        # supervisor membunuhnya — dan itu justru mematikan kesempatan
        # pembersihan yang lain.
        i = self.KODE.index("stop_job_maintenance")
        blok = self.KODE[max(0, i - 400):i + 600]
        assert "try:" in blok and "except Exception" in blok

    def test_client_close_tetap_dipanggil(self):
        # Penjaga urutan di atas juga hijau bila `client.close()` DIHAPUS.
        assert "client.close()" in self.KODE


@pytest.mark.asyncio
class TestStopIdempotenDanAman:
    """Ketiga fungsi stop dipanggil dari jalur yang sama; perilakunya harus
    seragam dan tak pernah melempar."""

    async def test_stop_tanpa_start_aman(self):
        # Startup bisa gagal separuh jalan (tiap `start_*` dibungkus try),
        # jadi shutdown WAJIB tahan terhadap penjadwal yang tak pernah hidup.
        jobs._maintenance_task = None
        webp_converter._task = None
        await jobs.stop_job_maintenance()
        await webp_converter.stop_webp_converter()

    async def test_stop_dua_kali_aman(self):
        async def _abadi():
            await asyncio.sleep(3600)

        jobs._maintenance_task = asyncio.create_task(_abadi())
        await jobs.stop_job_maintenance()
        await jobs.stop_job_maintenance()      # tak boleh melempar

    async def test_task_benar_benar_berhenti(self):
        jalan = {"ya": True}

        async def _loop():
            try:
                await asyncio.sleep(3600)
            finally:
                jalan["ya"] = False

        jobs._maintenance_task = asyncio.create_task(_loop())
        await asyncio.sleep(0)
        await jobs.stop_job_maintenance()
        assert jalan["ya"] is False
        assert jobs._maintenance_task is None

    async def test_task_yang_meledak_saat_dibatalkan_tidak_merambat(self):
        """Loop bisa punya `finally` yang ikut gagal saat koneksi sudah goyah.
        Shutdown tetap harus lanjut ke pembersihan berikutnya."""
        async def _loop():
            try:
                await asyncio.sleep(3600)
            finally:
                raise RuntimeError("finally ikut gagal")

        webp_converter._task = asyncio.create_task(_loop())
        await asyncio.sleep(0)
        await webp_converter.stop_webp_converter()   # tak boleh melempar


class TestJobBackupRestoreSENGAJADibiarkan:
    """Batas lingkup yang dikunci, bukan kelalaian."""

    SRC = (BACKEND / "routes" / "backup.py").read_text(encoding="utf-8")

    def test_stop_hanya_menyasar_loop_penjadwal(self):
        fn = inspect.getsource(
            __import__("routes.backup", fromlist=["stop_backup_scheduler"])
            .stop_backup_scheduler)
        kode = _tanpa_komentar(fn)
        assert "_scheduler_task" in kode
        # Membatalkan seluruh _BG_TASKS akan ikut membunuh restore berjalan.
        assert "_BG_TASKS" not in kode, kode

    def test_penjadwal_disimpan_terpisah_dari_himpunan_job(self):
        assert "_scheduler_task = _track_bg(" in self.SRC

    def test_alasannya_tertulis_di_kode(self):
        # Batas lingkup yang tak dijelaskan akan dibaca sebagai kelalaian dan
        # "diperbaiki" oleh orang berikutnya — justru merusak restore.
        i = self.SRC.index("async def stop_backup_scheduler")
        doc = self.SRC[i:i + 1200]
        assert "restore" in doc.lower()
        assert "integritas data" in doc.lower()
