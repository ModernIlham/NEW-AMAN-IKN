"""Layar Pengaturan berhenti mengklaim cadangan yang tak ada — temuan C5.

Penjadwal menulis `terakhir = <hari ini>` **sebelum** backup dijalankan. Sebagai
penjaga anti-jalan-ganda antar worker itu benar dan atomik. Masalahnya, layar
Pengaturan menampilkan field yang SAMA sebagai "Terakhir jalan" — sehingga
backup yang GAGAL tetap terbaca "sudah jalan hari ini", dan satu-satunya jejak
kegagalan adalah satu baris `logger.warning` yang tak pernah dibaca siapa pun.

Peredamnya jujur dan perlu disebut: retensi SUDAH digerbangi keberhasilan, jadi
kegagalan tidak memangkas arsip lama. Skenario terburuknya "cadangan menua
tanpa ada yang tahu", bukan "tidak ada cadangan sama sekali". Yang diperbaiki
di sini adalah bagian "tanpa ada yang tahu"-nya.

Dua sifat yang diurung:
  1. KLAIM (`terakhir`) dan HASIL (`terakhir_sukses`) adalah dua field berbeda,
     dan hanya hasil yang boleh dipakai layar;
  2. saat gagal, klaim harian DIKOSONGKAN sehingga siklus 5 menit berikutnya
     mencoba lagi hari itu juga — bukan menyerah sampai besok.
"""
import asyncio
import inspect
import pathlib

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.backup as rb

FE = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def lingkungan(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rb, "db", fake, raising=False)
    monkeypatch.setattr(rb, "_terapkan_retensi", lambda *a, **k: None, raising=False)

    async def _tak_melakukan_apa_apa(*a, **k):
        return None
    monkeypatch.setattr(rb, "run_backup_task", _tak_melakukan_apa_apa, raising=False)

    async def _seed():
        await fake.report_settings.insert_one({
            "type": "backup_otomatis", "aktif": True, "jam": "02:00",
            "retensi": 7, "terakhir": "2026-08-08",   # klaim hari ini
        })
    _jalan(_seed())
    return fake


def _pasang_hasil_job(dbx, status, message=""):
    """Sisipkan job dengan status tertentu untuk job_id apa pun yang dibuat."""
    async def _tandai():
        j = await dbx.backup_jobs.find_one({}, {"_id": 0, "job_id": 1})
        await dbx.backup_jobs.update_one(
            {"job_id": j["job_id"]},
            {"$set": {"status": status, "message": message}})
    return _tandai


def _setelan(dbx):
    async def _q():
        return await dbx.report_settings.find_one({"type": "backup_otomatis"}, {"_id": 0})
    return _jalan(_q())


class TestBackupSukses:
    def test_mencatat_terakhir_sukses(self, lingkungan, monkeypatch):
        dbx = lingkungan

        async def _jalankan(job_id, *a, **k):
            await dbx.backup_jobs.update_one(
                {"job_id": job_id}, {"$set": {"status": "completed"}})
        monkeypatch.setattr(rb, "run_backup_task", _jalankan, raising=False)

        _jalan(rb._jalankan_backup_otomatis(7))
        s = _setelan(dbx)
        assert s["status_terakhir"] == "sukses"
        assert s["terakhir_sukses"]          # terisi stempel waktu
        assert s["galat_terakhir"] == ""

    def test_klaim_harian_TETAP_agar_tak_jalan_dua_kali(self, lingkungan, monkeypatch):
        dbx = lingkungan

        async def _jalankan(job_id, *a, **k):
            await dbx.backup_jobs.update_one(
                {"job_id": job_id}, {"$set": {"status": "completed"}})
        monkeypatch.setattr(rb, "run_backup_task", _jalankan, raising=False)

        _jalan(rb._jalankan_backup_otomatis(7))
        assert _setelan(dbx)["terakhir"] == "2026-08-08"

    def test_retensi_diterapkan(self, lingkungan, monkeypatch):
        dbx = lingkungan
        dipanggil = []

        async def _jalankan(job_id, *a, **k):
            await dbx.backup_jobs.update_one(
                {"job_id": job_id}, {"$set": {"status": "completed"}})
        monkeypatch.setattr(rb, "run_backup_task", _jalankan, raising=False)
        monkeypatch.setattr(rb, "_terapkan_retensi",
                            lambda n: dipanggil.append(n), raising=False)

        _jalan(rb._jalankan_backup_otomatis(7))
        assert dipanggil == [7]


class TestBackupGagal:
    def _gagal(self, dbx, monkeypatch, pesan="Disk penuh"):
        async def _jalankan(job_id, *a, **k):
            await dbx.backup_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "message": pesan}})
        monkeypatch.setattr(rb, "run_backup_task", _jalankan, raising=False)
        _jalan(rb._jalankan_backup_otomatis(7))
        return _setelan(dbx)

    def test_TIDAK_mengklaim_pernah_sukses(self, lingkungan, monkeypatch):
        s = self._gagal(lingkungan, monkeypatch)
        assert s["status_terakhir"] == "gagal"
        assert not s.get("terakhir_sukses")

    def test_alasannya_disimpan_bukan_hanya_di_log(self, lingkungan, monkeypatch):
        s = self._gagal(lingkungan, monkeypatch, "Disk penuh di /var")
        assert "Disk penuh" in s["galat_terakhir"]

    def test_gagal_tanpa_pesan_tetap_menjelaskan_sesuatu(self, lingkungan, monkeypatch):
        s = self._gagal(lingkungan, monkeypatch, "")
        assert s["galat_terakhir"].strip() != ""

    def test_klaim_harian_DIKOSONGKAN_agar_dicoba_lagi(self, lingkungan, monkeypatch):
        # Inti "bonus murah" dari laporan: tanpa ini, satu kegagalan pukul 02:00
        # berarti tidak ada cadangan SAMA SEKALI sampai besok pukul 02:00.
        s = self._gagal(lingkungan, monkeypatch)
        assert s["terakhir"] == ""

    def test_retensi_TIDAK_diterapkan(self, lingkungan, monkeypatch):
        dipanggil = []
        monkeypatch.setattr(rb, "_terapkan_retensi",
                            lambda n: dipanggil.append(n), raising=False)
        self._gagal(lingkungan, monkeypatch)
        assert dipanggil == [], "arsip lama tak boleh dipangkas saat backup gagal"

    def test_sukses_lama_TIDAK_terhapus_oleh_kegagalan_baru(self, lingkungan, monkeypatch):
        """Cadangan kemarin masih ada — layar tak boleh melupakannya."""
        dbx = lingkungan
        _jalan(dbx.report_settings.update_one(
            {"type": "backup_otomatis"},
            {"$set": {"terakhir_sukses": "2026-08-07T02:00:00+00:00"}}))
        s = self._gagal(dbx, monkeypatch)
        assert s["terakhir_sukses"] == "2026-08-07T02:00:00+00:00"
        assert s["status_terakhir"] == "gagal"   # tapi statusnya tetap jujur


class TestLayarPengaturan:
    def test_menampilkan_HASIL_bukan_KLAIM(self):
        src = (FE / "pages" / "PengaturanPage.jsx").read_text(encoding="utf-8")
        assert "oto.terakhir_sukses" in src
        # `oto.terakhir` (klaim penjadwalan) tak boleh lagi dirender apa adanya.
        assert "Terakhir jalan: {oto.terakhir}" not in src

    def test_kegagalan_punya_lencana_sendiri(self):
        src = (FE / "pages" / "PengaturanPage.jsx").read_text(encoding="utf-8")
        assert 'oto.status_terakhir === "gagal"' in src
        assert "oto-gagal-badge" in src

    def test_belum_pernah_sukses_dinyatakan_terus_terang(self):
        # Kosong-tanpa-keterangan terbaca sebagai "baik-baik saja".
        src = (FE / "pages" / "PengaturanPage.jsx").read_text(encoding="utf-8")
        assert "Belum pernah berhasil" in src


def test_field_hasil_terbawa_ke_respons_endpoint():
    """Default WAJIB memuat field baru — kalau tidak, UI melihat `undefined`
    pada instalasi yang backup otomatisnya belum pernah jalan."""
    for k in ("terakhir_sukses", "status_terakhir", "galat_terakhir"):
        assert k in rb._SETELAN_OTOMATIS_DEFAULT, k
    # Dan endpoint GET menyebar setelan tersimpan di atas default itu.
    assert "_SETELAN_OTOMATIS_DEFAULT" in inspect.getsource(rb.get_setelan_otomatis)
