"""Penjaga ANTI-DRIFT: import lokal tak boleh membayangi impor tingkat modul.

Kelas bug yang dijaga (pernah membuat "unggah dokumen lalu minta TTD" 500):
sebuah `from X import f` di DALAM blok bersyarat (if/try/for/with) membuat `f`
menjadi nama LOKAL untuk SELURUH badan fungsi — aturan scoping Python, bukan
per-blok. Akibatnya pemakaian `f` di cabang lain fungsi yang sama (yang dulu
membaca impor tingkat modul dengan aman) meledak `UnboundLocalError` → 500,
dan hanya pada kombinasi input tertentu sehingga lolos dari uji jalur bahagia.

Contoh nyata yang ditangkap: `routes/ttd.py::buat_permintaan` meng-import
`scope_query_field_satker` di dalam `if doc_type in {bast,lpb}`, sementara
gerbang "Meninggal Dunia" di bawahnya memakai nama yang sama untuk SEMUA
doc_type → permintaan TTD ber-penanda-tangan NIP selalu 500.

Aturannya sederhana dan mudah dipatuhi: kalau namanya SUDAH diimpor di tingkat
modul, JANGAN meng-import-nya lagi di dalam fungsi. Import lokal tetap boleh
untuk nama yang memang tidak ada di tingkat modul (mis. memutus impor melingkar).
"""
import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[2]
_BLOK_BERSYARAT = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
                   ast.With, ast.AsyncWith)


def _nama_impor(simpul):
    for a in simpul.names:
        yield a.asname or a.name.split(".")[0]


def _impor_modul(pohon):
    """Nama yang diikat oleh impor di TINGKAT MODUL."""
    nama = set()
    for s in pohon.body:
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            nama.update(_nama_impor(s))
    return nama


def _impor_lokal_bersyarat(fn):
    """(nama, baris) impor di dalam fungsi yang berada dalam blok bersyarat.

    Scope bersarang (fungsi/lambda di dalam fungsi) dilewati — ia punya scope
    sendiri sehingga tak membayangi induknya.
    """
    hasil = []

    def telusur(simpul, bersyarat):
        for anak in ast.iter_child_nodes(simpul):
            if isinstance(anak, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda)):
                continue
            if bersyarat and isinstance(anak, (ast.Import, ast.ImportFrom)):
                hasil.extend((n, anak.lineno) for n in _nama_impor(anak))
            telusur(anak, bersyarat or isinstance(anak, _BLOK_BERSYARAT))

    telusur(fn, False)
    return hasil


def test_tak_ada_import_lokal_yang_membayangi_impor_modul():
    temuan = []
    for berkas in sorted((BACKEND).rglob("*.py")):
        rel = berkas.relative_to(BACKEND)
        if rel.parts[0] in ("tests", "scripts") or "__pycache__" in rel.parts:
            continue
        pohon = ast.parse(berkas.read_text(), filename=str(berkas))
        modul = _impor_modul(pohon)
        if not modul:
            continue
        for fn in ast.walk(pohon):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for nama, baris in _impor_lokal_bersyarat(fn):
                if nama in modul:
                    temuan.append(f"{rel}:{baris} — fungsi '{fn.name}' "
                                  f"meng-import ulang '{nama}' (sudah ada di "
                                  f"tingkat modul) di dalam blok bersyarat")
    assert not temuan, (
        "Import lokal membayangi impor tingkat modul — berisiko "
        "UnboundLocalError pada cabang lain fungsi yang sama. Hapus import "
        "lokalnya (nama sudah tersedia dari tingkat modul):\n  "
        + "\n  ".join(temuan))
