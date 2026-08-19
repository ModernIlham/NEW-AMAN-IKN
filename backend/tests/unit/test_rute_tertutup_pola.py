"""Rute LITERAL tidak boleh tertelan rute ber-parameter yang didaftarkan lebih dulu.

Laporan pemilik: membuka Master Persediaan → `GET /api/persediaan/permohonan`
menjawab **404**. Endpoint-nya ada dan benar; yang salah adalah URUTAN
pendaftaran router. `persediaan_router` memuat `/persediaan/{item_id}` yang
cocok dengan segmen apa pun, dan ia didaftarkan SEBELUM router permohonan —
sehingga permintaan itu ditangkap sebagai "ambil item ber-id 'permohonan'",
lalu menjawab 404 karena tak ada item dengan id tersebut.

Yang membuatnya sulit dicurigai: POST `/persediaan/permohonan` tetap BEKERJA,
sebab `/persediaan/{item_id}` hanya punya GET/PUT/DELETE. Jadi permohonan bisa
DIBUAT tetapi tak bisa DITAMPILKAN — dan 404-nya tampak seperti "datanya tak
ada", bukan seperti "rutenya salah alamat".

Uji ini memindai server.py secara STATIS: mengurutkan `include_router`,
membaca jalur tiap router menurut urutan deklarasinya, lalu memeriksa apakah
sebuah jalur literal akan lebih dulu tertangkap pola sebelumnya. Statis, bukan
dengan mengimpor aplikasinya, karena impor `server` menyalakan koneksi
rate-limiter dan menggantung di lingkungan uji bebas-infra.
"""
import ast
import os
import re

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER = os.path.join(BACKEND, "server.py")
ROUTES = os.path.join(BACKEND, "routes")

METODE = ("get", "post", "put", "patch", "delete")


def _peta_router_ke_modul(pohon):
    """{nama_variabel_router: nama_modul} dari `from routes.X import Y`."""
    peta = {}
    for n in ast.walk(pohon):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("routes."):
            modul = n.module.split(".", 1)[1]
            for a in n.names:
                peta[a.asname or a.name] = modul
    return peta


def _urutan_include(pohon):
    """[nama_variabel_router] menurut urutan `include_router(...)` dipanggil."""
    urut = []
    for n in ast.walk(pohon):
        if (isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name)):
            urut.append(n.args[0].id)
    return urut


def _rute_modul(modul):
    """[(metode, jalur)] menurut urutan deklarasi di berkas route."""
    berkas = os.path.join(ROUTES, f"{modul}.py")
    if not os.path.exists(berkas):
        return []
    with open(berkas, encoding="utf-8") as f:
        pohon = ast.parse(f.read())
    keluar = []
    for fn in ast.walk(pohon):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in fn.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)):
                continue
            if d.func.attr not in METODE or not d.args:
                continue
            arg = d.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keluar.append((d.func.attr, arg.value, fn.lineno))
    keluar.sort(key=lambda x: x[2])
    return [(m, j) for m, j, _ in keluar]


def _daftar_rute_terurut():
    with open(SERVER, encoding="utf-8") as f:
        pohon = ast.parse(f.read())
    peta = _peta_router_ke_modul(pohon)
    urut = []
    for var in _urutan_include(pohon):
        modul = peta.get(var)
        if not modul:
            continue
        for metode, jalur in _rute_modul(modul):
            urut.append((metode, jalur, f"{modul}::{var}"))
    return urut


def _pola(jalur):
    """Jalur ber-parameter → regex yang mencocokkan SATU segmen per parameter."""
    bagian = re.escape(jalur)
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", bagian) + "$")


def _tertutup():
    rute = _daftar_rute_terurut()
    temuan = []
    for i, (metode, jalur, asal) in enumerate(rute):
        if "{" in jalur:
            continue                       # hanya jalur literal yang bisa tertutup
        for metode2, jalur2, asal2 in rute[:i]:
            if metode2 != metode or "{" not in jalur2:
                continue
            if _pola(jalur2).match(jalur):
                temuan.append(
                    f"{metode.upper()} {jalur} ({asal}) tertutup "
                    f"{metode2.upper()} {jalur2} ({asal2})")
                break
    return temuan


class TestPembacaanBenar:
    """Penjaga anti-hampa: pemindai rusak → daftar kosong → uji lolos percuma."""

    def test_rute_terbaca_banyak(self):
        assert len(_daftar_rute_terurut()) >= 300, len(_daftar_rute_terurut())

    def test_pola_mencocokkan_satu_segmen_saja(self):
        p = _pola("/persediaan/{item_id}")
        assert p.match("/persediaan/permohonan")
        assert not p.match("/persediaan/permohonan/x"), (
            "pola menelan lebih dari satu segmen — akan melaporkan positif palsu")

    def test_rute_permohonan_memang_terbaca(self):
        rute = {(m, j) for m, j, _ in _daftar_rute_terurut()}
        assert ("get", "/persediaan/permohonan") in rute
        assert ("get", "/persediaan/{item_id}") in rute


def test_tidak_ada_rute_literal_yang_tertutup():
    temuan = _tertutup()
    assert temuan == [], (
        "Jalur literal berikut tak akan pernah tercapai — permintaannya "
        "ditangkap rute ber-parameter yang didaftarkan lebih dulu, dan "
        f"jawabannya menjadi 404/galat yang menyesatkan: {temuan}")
