"""Laporan Eksekutif per Barang Serupa tidak boleh membekukan aplikasi.

Temuan tinjauan keamanan 2026-08-17, lolos verifikasi adversarial. Tiga hal
menumpuk di satu endpoint yang bisa dipicu SATU KLIK oleh pengguna biasa:

  1. Foto sampul tiap kelompok diambil ulang dari GridFS lalu didekode Pillow
     + LANCZOS + WEBP — terukur ~0,2-0,4 detik per foto.
  2. Dekode itu berjalan LANGSUNG di event loop, sehingga selama total
     durasinya SELURUH permintaan lain berhenti dilayani: simpan aset
     lapangan, login, heartbeat lock.
  3. Tidak ada batas jumlah kelompok sama sekali.

Yang paling menipu adalah alasan nomor 1 dianggap langka. Komentar lama
menyebutnya "fallback untuk aset hasil migrasi", padahal `create_asset`
SELALU menulis `photos: []` — jadi cabang GridFS itu justru jalur NORMAL
setiap aset modern, bukan pengecualian.

Perbaikannya memakai barang yang sudah ada: `gallery_thumbnail` 256px WebP
tersimpan per aset, sementara template hanya menampilkannya pada 26-46px.
"""
import os
import re

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _sumber(*bagian):
    with open(os.path.join(BACKEND, *bagian), encoding="utf-8") as f:
        return f.read()


def _fungsi(src, nama):
    import ast
    for simpul in ast.walk(ast.parse(src)):
        if isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef)) and simpul.name == nama:
            return ast.get_source_segment(src, simpul) or ""
    raise AssertionError(f"fungsi {nama} tidak ditemukan")


class TestThumbnailTersimpanDipakaiLebihDulu:
    def test_pipeline_memproyeksikan_thumbnail(self):
        fn = _fungsi(_sumber("routes", "reports.py"), "_build_executive_grouped_data")
        assert '"gallery_thumbnail": 1' in fn, (
            "thumbnail tersimpan tidak diproyeksikan — setiap kelompok akan "
            "kembali mendekode ulang dari GridFS")

    def test_thumbnail_dipakai_sebelum_gridfs(self):
        fn = _fungsi(_sumber("routes", "reports.py"), "_build_executive_grouped_data")
        i_pakai = fn.index("thumb_map.get(rep_id)")
        i_gridfs = fn.index("_gridfs_photo_data_uri(")
        assert i_pakai < i_gridfs, (
            "GridFS harus jadi jalan TERAKHIR, bukan yang pertama dicoba")

    def test_gridfs_tetap_ada_sebagai_jalan_terakhir(self):
        """Aset era lama yang benar-benar hanya punya blob GridFS tetap harus
        bisa menampilkan foto — perbaikan ini menghemat, bukan memangkas."""
        fn = _fungsi(_sumber("routes", "reports.py"), "_build_executive_grouped_data")
        assert "_gridfs_photo_data_uri(" in fn


class TestDekodeLepasDariEventLoop:
    def test_downscale_lewat_to_thread(self):
        fn = _fungsi(_sumber("routes", "reports.py"), "_gridfs_photo_data_uri")
        assert "await asyncio.to_thread(_downscale_to_data_uri" in fn, (
            "dekode Pillow masih di event loop — satu laporan menghentikan "
            "seluruh permintaan lain selama pemrosesan")

    def test_tidak_ada_pemanggilan_sinkron_tersisa(self):
        fn = _fungsi(_sumber("routes", "reports.py"), "_gridfs_photo_data_uri")
        tanpa_to_thread = re.sub(r"await asyncio\.to_thread\([^)]*\)", "", fn)
        assert "_downscale_to_data_uri(" not in tanpa_to_thread


class TestGerbangJumlahKelompok:
    def test_ambang_ada_dan_masuk_akal(self):
        from routes.reports import MAKS_KELOMPOK_LAPORAN
        assert 500 <= MAKS_KELOMPOK_LAPORAN <= 5000

    def test_melebihi_ambang_ditolak_bukan_dipangkas(self):
        """Memangkas diam-diam lebih berbahaya daripada menolak: laporan resmi
        akan memuat sebagian data tanpa ada yang menyadarinya."""
        fn = _fungsi(_sumber("routes", "reports.py"), "_build_executive_grouped_data")
        blok = fn[fn.index("raw_groups = []"):]
        assert "MAKS_KELOMPOK_LAPORAN" in blok
        assert "HTTPException" in blok
        assert "status_code=400" in blok
        # Tidak boleh diam-diam dipotong dengan break/slice.
        potong = blok[:blok.index("HTTPException")]
        assert "break" not in potong

    def test_pesan_menyarankan_jalan_keluar(self):
        fn = _fungsi(_sumber("routes", "reports.py"), "_build_executive_grouped_data")
        assert "Persempit" in fn and ("CSV" in fn or "Excel" in fn)
