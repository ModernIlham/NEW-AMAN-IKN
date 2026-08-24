"""Gerbang "dokumen ber-satker wajib bersatker" — dan penjaga anti-drift-nya.

Laporan pemilik: *"pada saat mengganti role masih ada kebocoran data ... cek
juga semua generate yang lainnya agar tidak ada kebocoran satker."*

Sisiran menemukan 36 tempat yang menstempel `kode_satker` dari pemanggil.
Selama pemanggilnya bisa TAK BERSATKER (akun pusat yang belum memilih Satker
Aktif), setiap tempat itu menulis stempel "" — dan `scope_query_field_satker`
SENGAJA meloloskan "" sebagai kompatibilitas data era lama, sehingga
dokumennya tampil di register SEMUA satker.

DUA LAPIS UJI, dan keduanya perlu:

1. Gerbangnya sendiri (`require_writer_satker` / `require_admin_satker`).
2. Gerbangnya benar-benar TERPASANG pada endpoint yang menstempel. Uji
   endpoint di repo ini memanggil handler LANGSUNG, sehingga dependency
   FastAPI tak pernah ikut berjalan — gerbang yang lupa dipasang TIDAK akan
   membuat satu pun uji lain gagal. Penjaga struktural inilah satu-satunya
   yang menangkapnya, dan ia pula yang mengikat endpoint yang ditulis besok.
"""
import ast
import asyncio
import pathlib

import pytest

AKAR = pathlib.Path(__file__).resolve().parents[2]
ROUTES = AKAR / "routes"

# Endpoint yang stempel ""-nya PUNYA ARTI, bukan kelalaian — masing-masing
# dengan alasannya. Daftar ini sengaja pendek dan harus tetap pendek.
DIKECUALIKAN = {
    ("persuratan.py", "tambah_klasifikasi"):
        'stempel "" berarti klasifikasi arsip "Bersama" (dipakai semua satker)',
    ("persuratan.py", "set_pengaturan_persuratan"):
        'stempel "" berarti pengaturan "Universal" yang di-overlay per satker',
    ("unduhan.py", "mulai_unduhan"):
        "daftar unduhan disaring per-PENGGUNA (dibuat_oleh), bukan per-satker",
    ("geofence.py", "buat_aturan"):
        "sudah menurunkan satker dari perangkatnya bila pemanggil tak bersatker",
}

GERBANG = {"require_writer_satker", "require_admin_satker"}


def _dep_pada_signature(fn: ast.AsyncFunctionDef) -> set:
    """Nama fungsi di dalam `Depends(...)` pada argumen bawaan signature."""
    out = set()
    for d in list(fn.args.defaults) + list(fn.args.kw_defaults):
        if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "Depends":
            for a in d.args:
                if isinstance(a, ast.Name):
                    out.add(a.id)
    return out


def _nama_dari_kode_satker_user(fn: ast.AsyncFunctionDef) -> set:
    """Variabel lokal yang diisi dari `kode_satker_user(...)`."""
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) \
                and getattr(n.value.func, "id", "") == "kode_satker_user":
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def _menyisipkan(fn: ast.AsyncFunctionDef) -> bool:
    """Fungsi ini benar-benar MENULIS dokumen baru?

    Pembeda penting: endpoint BACA juga menyusun dict ber-kunci
    `"kode_satker": kode_satker_user(user)` — tetapi itu QUERY penyaring, dan
    menyaring ke satker sendiri justru perilaku yang benar. Tanpa pembeda ini
    penjaga anti-drift menuduh belasan endpoint baca dan daftar
    pengecualiannya membengkak sampai tak bermakna lagi.
    """
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("insert_one", "insert_many"):
            return True
    return False


def _menstempel_dari_pemanggil(fn: ast.AsyncFunctionDef) -> bool:
    """Fungsi ini menulis `"kode_satker": <turunan pemanggil>` ke dokumen?"""
    if not _menyisipkan(fn):
        return False
    lokal = _nama_dari_kode_satker_user(fn)
    for n in ast.walk(fn):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and k.value == "kode_satker"):
                continue
            if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "kode_satker_user":
                return True
            if isinstance(v, ast.Name) and v.id in lokal:
                return True
    return False


def _endpoint(fn: ast.AsyncFunctionDef) -> bool:
    for d in fn.decorator_list:
        f = d.func if isinstance(d, ast.Call) else d
        if isinstance(f, ast.Attribute) and "router" in getattr(f.value, "id", ""):
            return True
    return False


def _pindai():
    """→ [(berkas, nama_fungsi, dep_pada_signature)] untuk endpoint penstempel."""
    hasil = []
    for p in sorted(ROUTES.glob("*.py")):
        pohon = ast.parse(p.read_text())
        for fn in ast.walk(pohon):
            if not isinstance(fn, ast.AsyncFunctionDef) or not _endpoint(fn):
                continue
            if _menstempel_dari_pemanggil(fn):
                hasil.append((p.name, fn.name, _dep_pada_signature(fn)))
    return hasil


class TestPenjagaAntiDrift:
    def test_pemindainya_sendiri_benar_benar_menemukan_sesuatu(self):
        """Kalau pemindainya tak menemukan apa pun — pola berubah, nama
        helper diganti — uji di bawah lulus tanpa memeriksa apa pun."""
        assert len(_pindai()) >= 15, _pindai()

    def test_setiap_endpoint_penstempel_memakai_gerbang(self):
        telanjang = [
            f"{berkas}:{fn}" for berkas, fn, dep in _pindai()
            if not (dep & GERBANG) and (berkas, fn) not in DIKECUALIKAN
        ]
        assert telanjang == [], (
            "endpoint berikut menstempel kode_satker dari pemanggil tetapi "
            "tak memakai require_writer_satker/require_admin_satker — akun "
            "pusat tanpa Satker Aktif akan menulis stempel \"\" yang tampil "
            f"di register SEMUA satker: {telanjang}")

    def test_daftar_pengecualian_tak_menyimpan_nama_basi(self):
        """Pengecualian yang endpoint-nya sudah tiada/berganti nama akan
        diam-diam melindungi endpoint LAIN bernama sama kelak."""
        # Sebagian pengecualian TIDAK terdeteksi pemindai (mis. stempelnya
        # bukan dari kode_satker_user) — yang penting berkas & fungsinya nyata.
        for berkas, fn in DIKECUALIKAN:
            sumber = ROUTES / berkas
            assert sumber.exists(), f"berkas pengecualian hilang: {berkas}"
            assert f"async def {fn}(" in sumber.read_text(), (
                f"fungsi pengecualian hilang/berganti nama: {berkas}:{fn}")


class TestGerbangnyaSendiri:
    def _jalan(self, coro):
        loop = asyncio.get_event_loop_policy().new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_pemanggil_tanpa_satker_ditolak_400(self):
        from auth_utils import require_writer_satker
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._jalan(require_writer_satker(
                {"username": "sa", "role": "admin", "kode_satker": ""}))
        assert e.value.status_code == 400
        assert "Satker Aktif" in str(e.value.detail)

    def test_pemanggil_bersatker_lolos(self):
        from auth_utils import require_writer_satker
        u = {"username": "op", "role": "operator", "kode_satker": "527001"}
        assert self._jalan(require_writer_satker(u)) is u

    def test_gerbang_admin_berperilaku_sama(self):
        from auth_utils import require_admin_satker
        from fastapi import HTTPException
        u = {"username": "adm", "role": "admin", "kode_satker": "527001"}
        assert self._jalan(require_admin_satker(u)) is u
        with pytest.raises(HTTPException):
            self._jalan(require_admin_satker(
                {"username": "sa", "role": "admin", "kode_satker": ""}))

    def test_satker_aktif_yang_TERSUNTIK_ikut_meloloskan(self):
        """Inilah jalan keluar yang ditunjuk pesan penolakan: super-admin
        pusat yang memilih Satker Aktif mendapat `kode_satker` tersuntik."""
        from auth_utils import require_writer_satker
        u = {"username": "sa", "role": "admin", "kode_satker": "527001",
             "_super_admin_asli": True, "_satker_aktif": "527001"}
        assert self._jalan(require_writer_satker(u) ) is u
