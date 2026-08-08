"""Sapuan job macet saat startup, dan denyut yang membuatnya sah — temuan C29.

Laporan menuliskan butir ini sebagai satu baris: panggil `bersihkan_job_basi`
di blok startup, jangan tunggu `sleep(3600)` pertama. Klaimnya benar —
`_job_maintenance_loop` hanya menyapu Pusat Unduhan saat startup, sehingga
`db.background_jobs` tak pernah tersentuh sampai satu jam penuh berlalu.

Tetapi memasang sapuan itu apa adanya akan **menukar satu bug dengan bug yang
lebih buruk.**

`bersihkan_job_basi` menyimpulkan "mati" dari `updated_at` yang tua.
Kesimpulan itu hanya sah bila `updated_at` benar-benar berarti "masih hidup" —
dan sebelum PR ini, ia tidak berarti begitu. Ada dua celah panjang tanpa satu
pun pembaruan:

  • **Menunggu semaphore.** `_EKSPOR_SEM` / `_IMPOR_SEM` membatasi konkurensi
    build berat. Job kedua duduk di antrean, bisa bermenit-menit, dengan
    `updated_at` yang masih dari saat ia dibuat.
  • **Selama kerjanya sendiri.** Ekspor XLSX melompat dari progres 10 langsung
    ke 90; di antaranya `bangun_xlsx_bytes` berjalan tanpa satu pun
    `update_job`. Justru ekspor besar — yang paling lama — yang paling rentan.

Dan korbannya nyata, bukan teoretis: deploy ini jalan dengan
`uvicorn --workers 2` (`scripts/vps-deploy.sh:203`). Satu worker mati — OOM
saat ekspor besar adalah penyebab paling masuk akal — lalu di-respawn uvicorn,
menjalankan startup, dan menyapu job milik worker saudaranya yang masih sehat.
Korban yang paling mungkin: ekspor besar yang lain.

Karena itu berkas ini menguji DUA hal sebagai satu kesatuan, dan satu uji
khusus menagih keduanya tak boleh dipisah.
"""
import ast
import asyncio
import inspect
import pathlib

import pytest

import jobs

BACKEND = pathlib.Path(__file__).resolve().parents[2]
ROUTES = BACKEND / "routes"


@pytest.mark.asyncio
class TestDenyutJob:
    async def test_menyentuh_updated_at_berkala(self, monkeypatch):
        sentuhan = []

        async def _palsu(job_id, **f):
            sentuhan.append(job_id)

        monkeypatch.setattr(jobs, "update_job", _palsu)
        async with jobs.denyut_job("job-1", detik=0.01):
            await asyncio.sleep(0.06)
        assert len(sentuhan) >= 3, sentuhan
        assert set(sentuhan) == {"job-1"}

    async def test_berdenyut_walau_blok_TIDAK_melakukan_apa_pun(self, monkeypatch):
        """Justru kasus yang penting: menunggu semaphore.

        Job yang mengantre tak menjalankan kode apa pun — kalau denyutnya
        bergantung pada kemajuan kerja, ia takkan pernah berdenyut, dan sapuan
        akan membunuhnya justru karena ia sabar menunggu giliran.
        """
        n = []
        monkeypatch.setattr(jobs, "update_job",
                            lambda job_id, **f: n.append(1) or asyncio.sleep(0))
        sem = asyncio.Semaphore(0)
        async def _lepas():
            await asyncio.sleep(0.05)
            sem.release()
        asyncio.get_running_loop().create_task(_lepas())
        async with jobs.denyut_job("job-antre", detik=0.01):
            await sem.acquire()
        assert len(n) >= 3, n

    async def test_berhenti_setelah_blok_selesai(self, monkeypatch):
        n = []
        monkeypatch.setattr(jobs, "update_job",
                            lambda job_id, **f: n.append(1) or asyncio.sleep(0))
        async with jobs.denyut_job("job-2", detik=0.01):
            await asyncio.sleep(0.03)
        setelah = len(n)
        await asyncio.sleep(0.05)
        assert len(n) == setelah, "denyut masih jalan setelah blok selesai"

    async def test_denyut_PULIH_setelah_kegagalan_sesaat(self, monkeypatch):
        """Yang dijaga: denyut harus TERUS berdetak setelah gagal sekali.

        Versi pertama uji ini hanya menagih "job tetap selesai" — dan itu uji
        yang kosong. Galat di dalam `_loop()` terjadi di TASK TERPISAH, jadi ia
        memang tak pernah merambat ke badan `async with` dengan atau tanpa
        `try/except`. Mutasi "cabut try/except" lolos karenanya.
        Kerusakan sebenarnya lebih halus: satu galat sesaat MEMBUNUH task
        denyutnya diam-diam, job berhenti berdetak sampai selesai, dan sapuan
        job macet lalu menandainya mati — persis kegagalan yang hendak dicegah.
        """
        n = {"panggil": 0}

        async def _kadang_gagal(job_id, **f):
            n["panggil"] += 1
            if n["panggil"] == 1:
                raise RuntimeError("mongo lagi ngambek")

        monkeypatch.setattr(jobs, "update_job", _kadang_gagal)
        async with jobs.denyut_job("job-3", detik=0.01):
            await asyncio.sleep(0.06)
            hasil = "selesai"
        assert hasil == "selesai"
        assert n["panggil"] >= 3, f"denyut mati setelah gagal sekali ({n['panggil']}x)"

    async def test_galat_di_dalam_blok_tetap_merambat(self, monkeypatch):
        # Kebalikannya: denyut tak boleh MENELAN kegagalan job.
        monkeypatch.setattr(jobs, "update_job",
                            lambda job_id, **f: asyncio.sleep(0))
        with pytest.raises(ValueError):
            async with jobs.denyut_job("job-4", detik=0.01):
                raise ValueError("job gagal")

    async def test_pembatalan_tetap_merambat(self, monkeypatch):
        # Shutdown membatalkan task job; denyut tak boleh menyembunyikannya,
        # sebab pemanggil memakai CancelledError untuk menandai job "dibatalkan".
        monkeypatch.setattr(jobs, "update_job",
                            lambda job_id, **f: asyncio.sleep(0))
        with pytest.raises(asyncio.CancelledError):
            async with jobs.denyut_job("job-5", detik=0.01):
                raise asyncio.CancelledError()


class TestSapuanStartup:
    SRC = inspect.getsource(jobs._job_maintenance_loop)

    def test_menyapu_background_jobs_saat_startup(self):
        """Inti C29."""
        sebelum_loop = self.SRC.split("while True:")[0]
        assert "bersihkan_job_basi(" in sebelum_loop, sebelum_loop

    def test_ambangnya_pendek_bukan_60_menit(self):
        sebelum_loop = self.SRC.split("while True:")[0]
        assert "bersihkan_job_basi(5)" in sebelum_loop

    def test_sapuan_awal_tidak_menjatuhkan_startup(self):
        # Startup yang gagal karena sapuan pemeliharaan = server tak menyala
        # sama sekali. Harga yang terlalu mahal untuk pembersihan opsional.
        sebelum_loop = self.SRC.split("while True:")[0]
        i = sebelum_loop.index("bersihkan_job_basi(")
        assert "try:" in sebelum_loop[:i]
        assert "except Exception" in sebelum_loop[i:]

    def test_sapuan_per_jam_TETAP_ada(self):
        # Sapuan startup melengkapi, bukan menggantikan: proses yang hidup
        # berbulan-bulan tetap butuh sapuan berkala.
        setelah = self.SRC.split("while True:")[1]
        assert "bersihkan_job_basi(60)" in setelah


class TestSapuanDanDenyutTAKBOLEHDipisah:
    """Penjaga terpenting di berkas ini.

    Sapuan 5 menit hanya aman karena SEMUA worker job berdenyut. Menambah
    worker job baru tanpa denyut — atau mencabut denyut dari yang ada —
    mengembalikan cacat dalam bentuk yang lebih halus: job sehat ditandai
    "Timeout (job macet)", dan pengguna melihat ekspornya gagal padahal ia
    masih berjalan dan sebentar lagi menulis hasilnya.
    """

    # Worker yang memakai jobs.py dan punya fase panjang tanpa update_job.
    WORKER = {
        "exports.py": "_jalankan_ekspor_xlsx",
        "spasial.py": "_jalankan_impor",
        "categories.py": "_do_bulk_import",
    }

    def test_setiap_worker_job_memakai_denyut(self):
        kurang = []
        for berkas, fn in self.WORKER.items():
            src = (ROUTES / berkas).read_text(encoding="utf-8")
            pohon = ast.parse(src)
            badan = None
            for n in ast.walk(pohon):
                if isinstance(n, ast.AsyncFunctionDef) and n.name == fn:
                    badan = ast.get_source_segment(src, n)
                    break
            if badan is None:
                kurang.append(f"{berkas}: fungsi {fn} tak ditemukan")
            elif "denyut_job(" not in badan:
                kurang.append(f"{berkas}:{fn} tanpa denyut_job")
        assert kurang == [], kurang

    def test_denyut_ekspor_membungkus_SEMAPHORE_juga(self):
        """Job yang mengantre adalah kasus paling rentan, bukan paling aman.

        Kalau denyutnya dipasang DI DALAM semaphore, job yang menunggu giliran
        tetap senyap — dan justru itu keadaan yang paling lama.
        """
        src = (ROUTES / "exports.py").read_text(encoding="utf-8")
        i_denyut = src.index("async with denyut_job(job_id)")
        i_sem = src.index("async with _EKSPOR_SEM")
        assert i_denyut < i_sem, "denyut dipasang di dalam semaphore"

    def test_denyut_spasial_membungkus_SEMAPHORE_juga(self):
        src = (ROUTES / "spasial.py").read_text(encoding="utf-8")
        assert "async with denyut_job(job_id), _IMPOR_SEM:" in src

    def test_selang_denyut_jauh_lebih_pendek_dari_ambang_sapuan(self):
        """Rasio ini yang membuat sapuannya masuk akal.

        Denyut 30 dtk vs ambang 5 menit = sepuluh denyut hilang berturut-turut
        sebelum sebuah job dinyatakan mati. Menaikkan selang denyut mendekati
        ambang sapuan mengubah hiccup jaringan menjadi vonis mati.
        """
        ambang_detik = 5 * 60
        assert jobs.DENYUT_DETIK * 5 <= ambang_detik, jobs.DENYUT_DETIK


@pytest.mark.asyncio
class TestBersihkanJobBasi:
    """Perilaku fungsi sapuannya sendiri, dengan koleksi tiruan."""

    async def test_hanya_menyasar_status_belum_selesai(self, monkeypatch):
        ditangkap = {}

        class _Koleksi:
            async def update_many(self, filt, upd):
                ditangkap["filter"] = filt
                ditangkap["update"] = upd
                class _R: modified_count = 3
                return _R()

        monkeypatch.setattr(jobs, "_JOBS", _Koleksi())
        n = await jobs.bersihkan_job_basi(5)
        assert n == 3
        assert set(ditangkap["filter"]["status"]["$in"]) == {"queued", "running", "importing"}
        # Job yang sudah 'done'/'error' tak boleh disentuh ulang.
        assert "done" not in ditangkap["filter"]["status"]["$in"]

    async def test_menandai_selesai_agar_klien_berhenti_polling(self, monkeypatch):
        ditangkap = {}

        class _Koleksi:
            async def update_many(self, filt, upd):
                ditangkap.update(upd["$set"])
                class _R: modified_count = 1
                return _R()

        monkeypatch.setattr(jobs, "_JOBS", _Koleksi())
        await jobs.bersihkan_job_basi(5)
        assert ditangkap["status"] == "error"
        assert ditangkap["done"] is True      # tanpa ini klien polling selamanya
        assert ditangkap["error_message"]

    async def test_ambang_minimal_satu_menit(self, monkeypatch):
        """`bersihkan_job_basi(0)` akan menyapu job yang BARU SAJA dibuat."""
        ditangkap = {}

        class _Koleksi:
            async def update_many(self, filt, upd):
                ditangkap["batas"] = filt["updated_at"]["$lt"]
                class _R: modified_count = 0
                return _R()

        monkeypatch.setattr(jobs, "_JOBS", _Koleksi())
        await jobs.bersihkan_job_basi(0)
        selisih = jobs._now() - ditangkap["batas"]
        assert selisih.total_seconds() >= 55
