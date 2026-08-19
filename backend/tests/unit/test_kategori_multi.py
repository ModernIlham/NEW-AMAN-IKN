"""Kategori boleh dipilih LEBIH DARI SATU — di semua pintu sekaligus.

Enam filter lain sudah multi-nilai sejak lama; kategori tertinggal sebagai
kesetaraan tunggal. Membuatnya multi bukan pekerjaan satu endpoint: perakit
kuerinya (`build_asset_search_query`) dipakai bersama oleh daftar, statistik,
ekspor geo, laporan, stiker, dan pengambilan seluruh id.

Kalau hanya sebagian pintu yang menerima daftar, yang terjadi bukan galat
melainkan sesuatu yang jauh lebih sulit dilihat: layar menyaring tiga kategori,
sedangkan berkas ekspornya menyaring satu — dan keduanya tampak wajar.

Yang dijaga:
  1. Satu nilai menghasilkan kueri yang PERSIS SAMA dengan sebelum fitur ini
     ada (`{"category": "X"}`, bukan `$in` beranggota satu) — bookmark, klien
     luring lama, dan rencana indeks tak berubah.
  2. Daftar kosong = tanpa filter, bukan "tak cocok apa pun".
  3. SETIAP fungsi yang mengalirkan `category` ke perakit kueri menerima daftar.
  4. Ringkasan filter yang TERCETAK di laporan menyebut seluruh kategori.
"""
import ast
import inspect
import os

import pytest
from mongomock_motor import AsyncMongoMockClient

from routes.assets import build_asset_search_query

ROUTES = os.path.join(os.path.dirname(__file__), "..", "..", "routes")

# Perakit kueri aset. Fungsi yang mengalirkan `category` ke salah satunya wajib
# menerima daftar — kalau tidak, pintunya menyaring beda dari pintu lain.
PERAKIT = ("build_asset_search_query", "kueri_aset_terlihat")

# Jalur TIDAK LANGSUNG yang tak terlihat pemindai: `filter_laporan` mengoper
# `locals()` ke `filter_laporan_dari_map`, jadi tak ada panggilan perakit di
# badannya sendiri. Didaftarkan manual supaya tetap tertagih.
TAMBAHAN = {("reports.py", "filter_laporan")}


def _semua_fungsi():
    """[(berkas, simpul_fungsi)] untuk seluruh berkas route."""
    keluar = []
    for nama_berkas in sorted(os.listdir(ROUTES)):
        if not nama_berkas.endswith(".py"):
            continue
        with open(os.path.join(ROUTES, nama_berkas), encoding="utf-8") as f:
            try:
                pohon = ast.parse(f.read())
            except SyntaxError:
                continue
        for fn in ast.walk(pohon):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                keluar.append((nama_berkas, fn))
    return keluar


def _meneruskan_ke(fn, nama_tujuan):
    """True bila `fn` memanggil salah satu `nama_tujuan` sambil mengoper
    kategori — baik lewat `category=` maupun lewat `**kwargs`.

    Cabang `**kwargs` penting: `_bangun_query_stiker(asset_ids, **f)` tidak
    punya parameter `category` sama sekali, ia meneruskan seluruh filter apa
    adanya. Pemindai yang hanya mengenali `category=` buta terhadap pola ini,
    dan kedua endpoint stiker lolos tanpa pernah diperiksa.
    """
    for simpul in ast.walk(fn):
        if not (isinstance(simpul, ast.Call)
                and getattr(simpul.func, "id", None) in nama_tujuan):
            continue
        for k in simpul.keywords:
            if k.arg == "category" or k.arg is None:   # `arg is None` = **kwargs
                return True
    return False


def _fungsi_pengalir():
    """[(berkas, nama_fn)] — fungsi yang mengalirkan `category` ke perakit kueri.

    TRANSITIF, dan itu bukan kemewahan: `stiker.py` tidak memanggil perakitnya
    langsung melainkan lewat `_bangun_query_stiker`. Pemindai satu tingkat
    melewatkan kedua endpoint stiker — dan justru yang terlewat itulah yang
    berbahaya, karena kegagalannya diam: stiker tercetak untuk kategori yang
    berbeda dari yang tampil di layar.
    """
    fungsi = _semua_fungsi()
    perakit = set(PERAKIT)
    pengalir = set()
    while True:
        tambah_perakit = set()
        for berkas, fn in fungsi:
            if fn.name in perakit:
                continue
            args = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
            punya_category = "category" in args
            meneruskan_semua = fn.args.kwarg is not None
            if not (punya_category or meneruskan_semua):
                continue
            if not _meneruskan_ke(fn, perakit):
                continue
            if punya_category:
                # Ia menyebut kategori sendiri → anotasinya wajib diperiksa.
                pengalir.add((berkas, fn.name))
            berdekorator = any("router" in ast.dump(d) for d in fn.decorator_list)
            if not berdekorator:
                # Helper: naik jadi perakit supaya PEMANGGILNYA tertagih di
                # putaran berikutnya.
                tambah_perakit.add(fn.name)
        if not tambah_perakit - perakit:
            break
        perakit |= tambah_perakit
    return pengalir | TAMBAHAN


def _anotasi_category(berkas, nama_fn):
    with open(os.path.join(ROUTES, berkas), encoding="utf-8") as f:
        sumber = f.read()
    pohon = ast.parse(sumber)
    fn = next(n for n in ast.walk(pohon)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == nama_fn)
    for a in list(fn.args.args) + list(fn.args.kwonlyargs):
        if a.arg == "category":
            return ast.unparse(a.annotation) if a.annotation else ""
    return ""


class TestSemuaPintuMenerimaDaftar:
    def test_pemindai_menemukan_cukup_banyak(self):
        """Penjaga anti-hampa: pemindai yang rusak menghasilkan himpunan kosong
        dan uji utama lolos tanpa memeriksa apa pun."""
        assert len(_fungsi_pengalir()) >= 6, sorted(_fungsi_pengalir())

    def test_pintu_yang_sudah_terbukti_ikut_terbaca(self):
        p = _fungsi_pengalir()
        for pasangan in (("assets.py", "get_assets"),
                         ("assets.py", "get_assets_stats"),
                         ("exports.py", "export_geo"),
                         ("exports.py", "filter_aset_ekspor"),
                         ("batch.py", "get_all_asset_ids"),
                         ("stiker.py", "cetak_stiker_label"),
                         ("reports.py", "filter_laporan")):
            assert pasangan in p, f"{pasangan} tak terbaca — pemindai rusak?"

    def test_setiap_pintu_menerima_daftar(self):
        lalai = [f"{b}::{f} → {_anotasi_category(b, f)!r}"
                 for b, f in sorted(_fungsi_pengalir())
                 if "List[str]" not in _anotasi_category(b, f)]
        assert lalai == [], (
            "Pintu berikut masih menerima kategori tunggal. Layar akan "
            "menyaring beberapa kategori sementara pintu ini hanya satu — "
            f"dan keduanya tampak wajar: {lalai}")


class TestBentukKueri:
    def test_satu_nilai_tetap_kesetaraan_biasa(self):
        """Bukan `$in` beranggota satu: permintaan lama harus menghasilkan
        kueri yang identik supaya rencana indeksnya tak berubah."""
        assert build_asset_search_query(category="Meja")["category"] == "Meja"
        assert build_asset_search_query(category=["Meja"])["category"] == "Meja"

    def test_banyak_nilai_jadi_in(self):
        q = build_asset_search_query(category=["Meja", "Kursi"])
        assert q["category"] == {"$in": ["Meja", "Kursi"]}

    def test_kosong_berarti_tanpa_filter(self):
        for kosong in ("", [], None, ["", "  "]):
            assert "category" not in build_asset_search_query(category=kosong), kosong

    def test_duplikat_dibuang_urutan_dipertahankan(self):
        q = build_asset_search_query(category=["Kursi", "Meja", "Kursi"])
        assert q["category"] == {"$in": ["Kursi", "Meja"]}

    def test_beririsan_dengan_filter_lain(self):
        q = build_asset_search_query(category=["Meja", "Kursi"], condition=["Baik"])
        assert q["category"] == {"$in": ["Meja", "Kursi"]}
        assert q["condition"] == "Baik"


class TestJalurMongoNyata:
    def test_dua_kategori_menggabung_bukan_menyempit(self):
        import asyncio

        async def skenario():
            db = AsyncMongoMockClient()["uji"]
            await db.assets.insert_many([
                {"id": "a1", "category": "Meja"},
                {"id": "a2", "category": "Kursi"},
                {"id": "a3", "category": "Lemari"},
            ])
            q = build_asset_search_query(category=["Meja", "Kursi"])
            ids = sorted([d["id"] async for d in db.assets.find(q)])
            assert ids == ["a1", "a2"]

        loop = asyncio.get_event_loop_policy().new_event_loop()
        try:
            loop.run_until_complete(skenario())
        finally:
            loop.close()


class TestRingkasanLaporan:
    """Ringkasan filter DICETAK di kepala laporan. Kalau ia hanya menyebut satu
    kategori padahal tiga yang disaring, pembaca menyimpulkan dokumennya lebih
    sempit daripada isinya — dan itu kesimpulan yang dibawa ke berkas resmi."""

    def _ringkasan(self, **filter_uji):
        from routes.reports import filter_laporan_dari_map
        dasar = {"search": "", "category": [], "condition": [], "status": [],
                 "location": [], "eselon1_filter": [], "eselon2_filter": [],
                 "stiker_status": [], "inventory_status": [], "price_min": "",
                 "price_max": "", "nomor_spm": "", "perolehan_dari": "",
                 "user_filter": "", "pengguna_nip": "", "beli_dari": "",
                 "beli_sampai": ""}
        dasar.update(filter_uji)
        return filter_laporan_dari_map(dasar).ringkasan

    def test_menyebut_seluruh_kategori(self):
        r = self._ringkasan(category=["Meja", "Kursi", "Lemari"])
        assert "Kategori: Meja, Kursi, Lemari" in r, r

    def test_satu_kategori_tetap_apa_adanya(self):
        assert "Kategori: Meja" in self._ringkasan(category=["Meja"])

    def test_tanpa_kategori_tak_menyebut_apa_pun(self):
        assert "Kategori" not in self._ringkasan(condition=["Baik"])
