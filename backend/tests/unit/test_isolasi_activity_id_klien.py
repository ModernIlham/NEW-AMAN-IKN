"""Endpoint yang menerima `activity_id` DARI KLIEN wajib memanggil guard kegiatan.

Akar masalahnya ada di `shared_utils.scope_query_aset`:

    if not kode or "activity_id" in q:
        return q          # <- lepas TANPA menyaring

Cabang kedua itu disengaja — begitu kueri sudah menunjuk satu kegiatan,
penyaringan per-satker diserahkan ke `pastikan_akses_kegiatan_id`. Rancangan itu
sah, tetapi bergantung sepenuhnya pada pemanggil yang disiplin: sekali sebuah
endpoint menerima `activity_id` dari klien lalu LUPA memanggil guard-nya, isolasi
antar-satker lenyap untuk endpoint itu — tanpa satu pun galat.

Itu bukan kekhawatiran teoretis. Tinjauan keamanan 2026-08-16 menemukan dua
endpoint yang persis begitu: `GET /assets/groups` dan `GET /assets/all-ids`.
Operator satker A cukup mengirim `activity_id` milik satker B untuk memperoleh
rincian anggota kelompok (lokasi, pemegang, kondisi) atau seluruh id asetnya.

Uji ini menyisir sumber dan menagih pasangan itu, supaya endpoint BERIKUTNYA
tidak mengulanginya diam-diam.
"""
import ast
import os

import pytest

ROUTES = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "routes"))

# Nama guard yang dianggap memadai. `pastikan_akses_aset` menerima dokumen aset
# (bukan id kegiatan) tetapi menegakkan kepemilikan yang sama, jadi ikut sah.
GUARD = ("pastikan_akses_kegiatan_id", "pastikan_akses_kegiatan", "pastikan_akses_aset",
         # Helper penyaring lain yang menegakkan isolasi yang sama.
         "_batas_activity_satker", "scope_query_field_satker")

# Endpoint yang MEMANG boleh lintas-satker beserta alasannya. Daftar ini sengaja
# kecil dan wajib beralasan — bukan tempat menampung endpoint yang belum sempat
# diperbaiki.
DIKECUALIKAN = {
    # (berkas, nama fungsi): alasan
    ("activities.py", "get_inventory_activities"): "daftar kegiatan justru sudah disaring per satker di kuerinya sendiri",
    # Guard-nya ada di helper bersama `_docx_surat_pernyataan_inv`
    # (routes/reports.py:4642) yang dipanggil kedua endpoint ini.
    ("reports.py", "generate_sp_hasil_docx"): "guard di _docx_surat_pernyataan_inv",
    ("reports.py", "generate_sp_pelaksanaan_docx"): "guard di _docx_surat_pernyataan_inv",
    # `scope_query_aset` dipanggil LEBIH DULU atas kueri tanpa activity_id,
    # baru activity_id ditambahkan lewat $and — urutan yang benar, dan
    # alasannya sudah ditulis panjang di docstring endpoint itu.
    ("siman.py", "daftar_selisih_siman"): "scope diterapkan sebelum activity_id ditambahkan via $and",
}


def _fungsi_endpoint(path):
    """[(nama, sumber)] untuk tiap fungsi ber-dekorator router di satu berkas."""
    with open(path, encoding="utf-8") as f:
        sumber = f.read()
    try:
        pohon = ast.parse(sumber)
    except SyntaxError:
        return []
    keluar = []
    for simpul in ast.walk(pohon):
        if not isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        berdekorator_router = any(
            "router" in ast.dump(d) and any(
                m in ast.dump(d) for m in ("'get'", "'post'", "'patch'", "'put'", "'delete'"))
            for d in simpul.decorator_list)
        if berdekorator_router:
            keluar.append((simpul.name, ast.get_source_segment(sumber, simpul) or ""))
    return keluar


def _terima_activity_id_dari_klien(simpul_sumber):
    """True bila `activity_id` adalah PARAMETER fungsi (query/path), bukan
    nilai yang diambil server dari dokumen yang sudah diperiksa."""
    try:
        pohon = ast.parse(simpul_sumber)
    except SyntaxError:
        return False
    fn = pohon.body[0]
    args = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    return "activity_id" in args


def _tanpa_baris_impor(sumber):
    """Sumber tanpa baris `from ... import ...`.

    Tanpa ini uji tertipu: mencabut PANGGILAN guard tetapi membiarkan namanya di
    baris impor membuat pencarian substring tetap ketemu. Uji-mutasi 2026-08-16
    membuktikannya — mutasi lolos hijau sampai penyaring ini ditambahkan.
    """
    return "\n".join(b for b in sumber.splitlines()
                      if not b.strip().startswith(("from ", "import ")))


# Helper yang MEMBAWA guard di dalamnya. Endpoint yang mendelegasikan
# perakitan kueri ke salah satunya dianggap terjaga — TETAPI hanya karena
# `TestHelperPembawaGuardBenarBenarMenjaga` di bawah membuktikan helper itu
# sendiri memanggil guard. Ini berbeda dengan mengecualikan endpoint: di sini
# rantainya tetap terbukti, dan mencabut guard dari helper akan menjatuhkan
# seluruh endpoint yang bergantung padanya sekaligus.
HELPER_PEMBAWA_GUARD = {
    "kueri_aset_terlihat": "assets.py",
}


def _memanggil_guard(sumber):
    bersih = _tanpa_baris_impor(sumber)
    if any(f"{g}(" in bersih for g in GUARD):
        return True
    return any(f"await {h}(" in bersih for h in HELPER_PEMBAWA_GUARD)


def kandidat():
    keluar = []
    for nama_berkas in sorted(os.listdir(ROUTES)):
        if not nama_berkas.endswith(".py"):
            continue
        for nama_fn, sumber in _fungsi_endpoint(os.path.join(ROUTES, nama_berkas)):
            if not _terima_activity_id_dari_klien(sumber):
                continue
            if (nama_berkas, nama_fn) in DIKECUALIKAN:
                continue
            keluar.append((nama_berkas, nama_fn, sumber))
    return keluar


class TestPembacaanBenar:
    """Penjaga anti-hampa: bila penyisiran gagal, daftar kandidat jadi kosong
    dan uji utama lolos tanpa memeriksa apa pun."""

    def test_kandidat_terbaca_cukup_banyak(self):
        k = kandidat()
        assert len(k) >= 20, f"hanya {len(k)} endpoint ber-activity_id terbaca — penyisir rusak?"

    def test_dua_endpoint_yang_pernah_bocor_ikut_terbaca(self):
        pasangan = {(b, f) for b, f, _ in kandidat()}
        assert ("batch.py", "get_asset_groups") in pasangan
        assert ("batch.py", "get_all_asset_ids") in pasangan


class TestGuardTerpasang:
    def test_setiap_endpoint_ber_activity_id_memanggil_guard(self):
        lalai = []
        for berkas, fn, sumber in kandidat():
            if not _memanggil_guard(sumber):
                lalai.append(f"{berkas}::{fn}")
        assert lalai == [], (
            "Endpoint berikut menerima activity_id dari klien tetapi tidak "
            "memanggil guard kepemilikan kegiatan. `scope_query_aset` TIDAK "
            "menyaring bila activity_id sudah ada di kueri, jadi isolasi "
            f"antar-satker mati untuk endpoint ini: {lalai}")


class TestHelperPembawaGuardBenarBenarMenjaga:
    """Delegasi hanya sah selama yang didelegasikan memang menjaga.

    Tanpa uji ini, `HELPER_PEMBAWA_GUARD` berubah dari jalan pintas yang aman
    menjadi daftar pemutih: cukup menamai satu fungsi di situ, dan setiap
    endpoint yang memanggilnya lolos pemeriksaan tanpa satu pun guard nyata.
    """

    def test_setiap_helper_memanggil_guard_sendiri(self):
        lalai = []
        for nama_helper, berkas in HELPER_PEMBAWA_GUARD.items():
            with open(os.path.join(ROUTES, berkas), encoding="utf-8") as f:
                pohon = ast.parse(f.read())
                f.seek(0)
                sumber_berkas = f.read()
            fn = next((n for n in ast.walk(pohon)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name == nama_helper), None)
            if fn is None:
                lalai.append(f"{berkas}::{nama_helper} (fungsi tak ditemukan)")
                continue
            badan = _tanpa_baris_impor(ast.get_source_segment(sumber_berkas, fn) or "")
            if not any(f"{g}(" in badan for g in GUARD):
                lalai.append(f"{berkas}::{nama_helper}")
        assert lalai == [], (
            "Helper berikut terdaftar sebagai pembawa guard tetapi tidak "
            f"memanggil guard apa pun: {lalai}")

    def test_endpoint_yang_mendelegasikan_memang_ada(self):
        """Penjaga anti-hampa: bila tak ada satu pun endpoint yang memakai
        jalur delegasi, mekanisme di atas hanya menambah kerumitan."""
        pemakai = [f"{b}::{f}" for b, f, s in kandidat()
                   if any(f"await {h}(" in _tanpa_baris_impor(s)
                          for h in HELPER_PEMBAWA_GUARD)]
        assert "assets.py::get_assets" in pemakai, pemakai
        assert "assets.py::get_assets_stats" in pemakai, pemakai


class TestCabangFailOpenMasihSepertiYangDiasumsikan:
    """Bila `scope_query_aset` suatu hari menyaring sendiri walau activity_id
    sudah ada, seluruh uji di atas kehilangan alasannya. Kunci asumsinya."""

    def test_scope_melepas_ketika_activity_id_sudah_ada(self):
        import asyncio
        from shared_utils import scope_query_aset

        async def jalan():
            user = {"kode_satker": "621001", "role": "operator"}
            q = await scope_query_aset(user, {"activity_id": "milik-satker-lain"})
            return q

        loop = asyncio.get_event_loop_policy().new_event_loop()
        try:
            q = loop.run_until_complete(jalan())
        finally:
            loop.close()
        assert q == {"activity_id": "milik-satker-lain"}, (
            "scope_query_aset kini menyaring sendiri — perbarui alasan berkas uji ini")


@pytest.mark.parametrize("berkas,fn", [
    ("batch.py", "get_asset_groups"),
    ("batch.py", "get_all_asset_ids"),
])
def test_perbaikan_kebocoran_2026_08_masih_terpasang(berkas, fn):
    """Regresi khusus dua endpoint yang temuannya sudah terbukti."""
    sumber = dict(((b, f), s) for b, f, s in kandidat())[(berkas, fn)]
    assert "await pastikan_akses_kegiatan_id(" in _tanpa_baris_impor(sumber)


class TestStatistikEksporIkutTerScope:
    """PDF ekspor aset: blok statistik WAJIB memakai kueri yang sama dengan
    pencacahannya.

    Dulu baris itu berbunyi `{"$match": query} if activity_id else {"$match": {}}`.
    Saat kegiatan tidak dipilih, penyaringan satker DIBUANG dan agregasi
    menjumlahkan purchase_price SELURUH koleksi — kotak ringkasan PDF mencetak
    nilai BMN seluruh satker sementara tabelnya hanya berisi aset satker sendiri.
    Dokumen itu rutin dikirim ke KPKNL.

    Uji ini bersifat STRUKTURAL (membaca sumber), bukan render-balik seperti
    uji laporan lain di repo ini. Alasannya jujur: agregasi `$convert` tidak
    didukung mongomock, jadi merender PDF-nya di uji unit tidak mungkin tanpa
    Mongo sungguhan. Yang dikunci karena itu adalah bentuk kuerinya.
    """

    def _sumber_export_pdf(self):
        p = os.path.join(ROUTES, "exports.py")
        with open(p, encoding="utf-8") as f:
            sumber = f.read()
        import ast as _ast
        for simpul in _ast.walk(_ast.parse(sumber)):
            if isinstance(simpul, (_ast.FunctionDef, _ast.AsyncFunctionDef)) \
                    and simpul.name == "export_pdf":
                return _ast.get_source_segment(sumber, simpul) or ""
        raise AssertionError("fungsi export_pdf tidak ditemukan")

    def test_tidak_ada_match_kosong(self):
        src = self._sumber_export_pdf()
        assert '{"$match": {}}' not in src, (
            "blok statistik kembali memakai matcher kosong — nilai BMN seluruh "
            "satker akan tercetak di PDF satker mana pun")

    def test_statistik_memakai_query_yang_sama_dengan_pencacahan(self):
        src = self._sumber_export_pdf()
        assert 'count_documents(query)' in src
        assert 'stats_pipeline = [{"$match": query}' in src, (
            "statistik harus memakai `query` yang sama dengan count_documents, "
            "tanpa percabangan berdasar activity_id")
