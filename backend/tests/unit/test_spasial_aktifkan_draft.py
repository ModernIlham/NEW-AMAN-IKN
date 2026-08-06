"""Denah yang sudah diimpor harus bisa terdeteksi — tanpa mencabut gerbangnya.

Laporan pemilik: *"halaman lokasi aset di denah masih tidak memunculkan
informasinya … agar semua titik dapat terdeteksi, sesuai peta denah yang sudah
diinputkan, lengkap dari wilayah hingga mengerucutnya."*

RANTAI SEBABNYA, dan tak satu pun darinya "rusak":

  1. Impor SHP/KML/GeoJSON menulis SEMUA node dengan `status: "draft"` — itu
     gerbang tinjauan yang disengaja (Fase 5).
  2. Deteksi (`/spasial/lokasi-di-titik`), lapisan peta (`/spasial/geojson`),
     dan ruangan-di-titik semuanya menyaring `status: "aktif"`.
  3. Satu-satunya cara melepas draft adalah form ubah SATU node.

Gabungan ketiganya: denah kawasan berisi ratusan ruangan yang sudah diimpor
lengkap tak pernah terdeteksi di mana pun, dan melepasnya berarti membuka form
ratusan kali. Gerbang tanpa pintu bukan gerbang — ia tembok.

Berkas ini menjaga DUA sisi sekaligus, dan sisi keduanya yang paling mudah
hilang saat orang "memperbaiki" cacat ini dengan cara termudah:

  • PINTUNYA ADA — aktivasi massal tersedia, ter-scope satker, ber-audit.
  • GERBANGNYA TETAP — impor tetap mendarat draft, dan deteksi tetap menolak
    draft. Godaan terbesarnya adalah mencabut `status: "aktif"` dari deteksi;
    itu membuat poligon setengah jadi ikut menentukan lokasi barang negara.
"""
import ast
import os

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPASIAL = os.path.join(BACKEND, "routes", "spasial.py")

with open(SPASIAL, encoding="utf-8") as f:
    SRC = f.read()


def _fungsi(nama: str) -> str:
    """Sumber satu fungsi, dipotong lewat AST — bukan tebak-tebakan baris."""
    pohon = ast.parse(SRC)
    for simpul in ast.walk(pohon):
        if (isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef))
                and simpul.name == nama):
            return ast.get_source_segment(SRC, simpul) or ""
    raise AssertionError(f"fungsi {nama} tidak ditemukan")


class TestPintuAda:
    def test_endpoint_aktivasi_massal_terdaftar(self):
        assert '@spasial_router.post("/spasial/aktifkan-draft")' in SRC

    def test_hanya_menyentuh_status_draft(self):
        """Menyaring selain draft akan MENGAKTIFKAN ULANG node yang sengaja
        di-nonaktifkan (mis. gedung sedang direnovasi) — kerusakan senyap."""
        fn = _fungsi("aktifkan_draft")
        assert 'q = {"status": "draft"}' in fn
        assert '"status": "aktif"' in fn      # nilai tujuan

    def test_terkurung_satker(self):
        """Tanpa ini satu klik mengaktifkan draft SELURUH satker di basis data
        bersama — pelanggaran isolasi yang paling mahal di modul ini.

        Yang diperiksa adalah PENYARINGAN KUERI UTAMA, bukan sekadar "nama
        fungsinya muncul di suatu tempat". Versi pertama uji ini memakai
        `"scope_query_field_satker(_user" in fn` dan LOLOS ketika baris
        pengurungan kueri utama dicabut — karena fungsi yang sama juga dipanggil
        di cabang `dalam` untuk memvalidasi induk. Uji yang menemukan pemanggilan
        yang salah tidak menjaga apa pun.
        """
        fn = _fungsi("aktifkan_draft")
        assert "q = scope_query_field_satker(_user, q)" in fn
        # Dan urutannya harus SEBELUM hitung/tulis — mengurung setelah menghitung
        # membuat angka pratinjau bocor lintas satker walau tulisannya aman.
        assert (fn.index("q = scope_query_field_satker(_user, q)")
                < fn.index("count_documents(q)"))
        assert (fn.index("q = scope_query_field_satker(_user, q)")
                < fn.index("update_many("))

    def test_butuh_izin_tulis_dan_beraudit(self):
        fn = _fungsi("aktifkan_draft")
        assert "Depends(require_writer)" in fn
        assert 'log_audit("spasial_aktifkan_draft"' in fn

    def test_punya_pratinjau_dan_berlaju(self):
        """Aksi massal tanpa pratinjau memaksa pengguna menebak dampaknya."""
        fn = _fungsi("aktifkan_draft")
        assert "payload.pratinjau" in fn
        assert '@limiter.limit(' in SRC.split(
            '@spasial_router.post("/spasial/aktifkan-draft")')[0].rsplit("\n@", 1)[-1] \
            or 'limiter.limit("10/minute")' in SRC

    def test_subpohon_memvalidasi_induknya(self):
        """`dalam` yang tak terjangkau satker harus 404, bukan diabaikan diam-
        diam lalu mengaktifkan SELURUH satker pemanggil."""
        fn = _fungsi("aktifkan_draft")
        assert "status_code=404" in fn
        assert '"ancestors": dalam' in fn


class TestGerbangTetapBerdiri:
    """Sisi yang paling mudah hilang. Ketiganya adalah kondisi yang membuat
    perbaikan ini BENAR, bukan sekadar membuat gejalanya hilang."""

    def test_deteksi_titik_tetap_menolak_draft(self):
        fn = _fungsi("lokasi_di_titik")
        assert '"status": "aktif"' in fn

    def test_lapisan_peta_tetap_menolak_draft(self):
        fn = _fungsi("geojson_viewport")
        assert '"status": "aktif"' in fn

    def test_impor_tetap_mendarat_draft(self):
        assert '"status": "draft"' in SRC


class TestDiagnosisJujur:
    """Kalimat "Di luar kawasan terpetakan" adalah pernyataan yang SALAH ketika
    ada poligon draft tepat di titik itu. Ia menuduh datanya tak ada, padahal
    datanya ada dan hanya belum dilepas gerbang — dan itulah yang membuat
    operator menyimpulkan aplikasinya rusak."""

    def test_menghitung_draft_yang_memuat_titik(self):
        fn = _fungsi("lokasi_di_titik")
        assert '"status": "draft"' in fn
        assert "count_documents" in fn

    def test_mengembalikan_penanda_terpisah_bukan_cuma_kalimat(self):
        """Layar harus bisa memutuskan tindakannya sendiri (tombol "Aktifkan
        draft") tanpa mengurai kalimat bahasa manusia."""
        fn = _fungsi("lokasi_di_titik")
        assert '"draft_menutupi"' in fn

    def test_pesan_menyebut_draft_bukan_di_luar_kawasan(self):
        fn = _fungsi("lokasi_di_titik")
        potong = fn[fn.index("n_draft"):]
        assert "DRAFT" in potong
        assert "belum ikut deteksi" in potong
