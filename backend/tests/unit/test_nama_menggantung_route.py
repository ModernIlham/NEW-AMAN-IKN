"""Tak boleh ada nama yang DIBACA tetapi tak pernah terikat di fungsi route.

Kelas cacat yang sangat mudah lolos: sepotong kode dipindahkan ke fungsi lain
(mis. parser dipindah agar bisa berjalan di thread), variabelnya ikut pindah,
tetapi PEMBACANYA tertinggal. Python tak mengeluh sampai baris itu benar-benar
dijalankan — lalu endpoint-nya 500 setiap kali dipanggil.

Tiga temuan nyata yang melahirkan uji ini:

  1. `siman.py::import_siman` membaca `peta_header` dan `sheet_dipakai` yang
     sudah pindah ke `_parse_siman_xlsx` → SETIAP impor SIMAN V2 berakhir 500,
     apa pun isi filenya. Ini dilaporkan pemilik dari lapangan.
  2. `pegawai.py::impor_pegawai` memanggil `asyncio.to_thread` sementara
     `asyncio` tak pernah diimpor di berkas itu.
  3. `pemeliharaan.py::posting_kapitalisasi` memakai `parse_harga` yang hanya
     diimpor di dalam fungsi LAIN pada berkas yang sama.

Ketiganya tak terlihat oleh uji fungsi murni: setiap potongnya lulus, yang
putus justru sambungan di antaranya. Hanya pemindaian statis — atau menjalankan
endpoint-nya sungguhan — yang bisa melihatnya, dan pemindaian jauh lebih murah
untuk 30+ berkas route.
"""
import ast
import builtins
import os

ROUTES = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "routes"))

# Nama yang memang disediakan runtime/konvensi dan tak pernah terikat eksplisit.
DIMAAFKAN = {"__name__", "__file__", "__doc__"}


def _nama_terikat(simpul):
    """Semua nama yang TERIKAT di dalam sebuah fungsi (termasuk bersarang)."""
    out = set()
    for n in ast.walk(simpul):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
    return out


def _nama_modul(pohon):
    """Nama tingkat modul — termasuk yang berada di dalam blok `try`/`if`."""
    out = set(dir(builtins)) | DIMAAFKAN
    for n in ast.walk(pohon):
        # Hanya penetapan di tingkat modul yang relevan; penetapan di dalam
        # fungsi sudah tertangkap `_nama_terikat` pada fungsinya sendiri.
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ClassDef):
            out.add(n.name)
    for n in ast.walk(pohon):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(n.name)
    return out


def _berkas_route():
    return [f for f in sorted(os.listdir(ROUTES)) if f.endswith(".py")]


def _menggantung(berkas):
    with open(os.path.join(ROUTES, berkas), encoding="utf-8") as f:
        pohon = ast.parse(f.read())
    modul = _nama_modul(pohon)
    temuan = []
    # Hanya fungsi TINGKAT MODUL yang dianalisis. Fungsi bersarang membaca
    # nama dari lingkup induknya (closure) — memeriksanya sendiri-sendiri
    # menghasilkan belasan positif palsu, dan uji yang banjir positif palsu
    # akan segera diabaikan orang. `_nama_terikat` sudah menelusuri seluruh
    # isi fungsi induk termasuk yang bersarang, jadi nama yang benar-benar
    # tak pernah terikat di mana pun tetap tertangkap.
    for fn in [n for n in pohon.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        terikat = _nama_terikat(fn) | modul
        dibaca = {n.id for n in ast.walk(fn)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        for nama in sorted(dibaca - terikat):
            temuan.append(f"{berkas}::{fn.name} membaca '{nama}'")
    return temuan


class TestPembacaanBenar:
    """Penjaga anti-hampa: pemindai yang rusak akan melaporkan nol temuan
    untuk alasan yang salah."""

    def test_berkas_route_terbaca_banyak(self):
        assert len(_berkas_route()) >= 20, _berkas_route()

    def test_pemindai_mengenali_nama_menggantung_buatan(self):
        import tempfile
        contoh = (
            "def f():\n"
            "    x = 1\n"
            "    return x + y\n"          # y tak pernah terikat
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "uji.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(contoh)
            global ROUTES
            asli, ROUTES = ROUTES, d
            try:
                assert _menggantung("uji.py") == ["uji.py::f membaca 'y'"]
            finally:
                ROUTES = asli

    def test_closure_tidak_dilaporkan_sebagai_menggantung(self):
        """Fungsi bersarang yang membaca variabel induknya adalah pola yang
        sah dan dipakai di banyak berkas route."""
        import tempfile
        contoh = (
            "def luar(warna):\n"
            "    def dalam():\n"
            "        return warna\n"
            "    return dalam()\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "uji.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(contoh)
            global ROUTES
            asli, ROUTES = ROUTES, d
            try:
                assert _menggantung("uji.py") == []
            finally:
                ROUTES = asli

    def test_nama_yang_terikat_di_dalam_fungsi_tidak_dilaporkan(self):
        """Impor di dalam fungsi (pola lazy-import berkas ini) sah — kalau
        pemindai menganggapnya menggantung, ia akan banjir positif palsu dan
        segera diabaikan orang."""
        import tempfile
        contoh = (
            "def f():\n"
            "    from math import sqrt\n"
            "    return sqrt(4)\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "uji.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(contoh)
            global ROUTES
            asli, ROUTES = ROUTES, d
            try:
                assert _menggantung("uji.py") == []
            finally:
                ROUTES = asli


def test_tidak_ada_nama_menggantung_di_seluruh_route():
    temuan = [t for b in _berkas_route() for t in _menggantung(b)]
    assert temuan == [], (
        "Nama berikut dibaca tetapi tak pernah terikat — endpoint-nya akan "
        f"NameError (500) begitu baris itu dijalankan: {temuan}")
