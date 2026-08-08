"""Persediaan pada berkas rekonsiliasi SAKTI — temuan C3 tinjauan 2026-08.

`generate_rekonsiliasi_xlsx` memanggil `db.persediaan.find({}, ...)` dengan
filter KOSONG, padahal aset EMPAT BARIS DI ATASNYA sudah di-scope. Berkas
rekonsiliasi resmi satker itu karenanya menjumlahkan persediaan SELURUH satker:
nilainya lebih saji dan tidak akan pernah tie-out dengan SAKTI satker itu —
sekaligus data persediaan satker lain terbaca oleh yang tak berhak, dan
endpoint ini menerima token kueri (`require_user_or_query_token`).

Yang menegaskan ini bug, bukan pilihan desain: TIGA kueri persediaan lain di
berkas yang sama dan di `lbp.py` semuanya memakai `scope_query_field_satker`.

Uji ini mengurung dua lapis:
  1. perilaku filternya — dua satker, masing-masing hanya melihat miliknya;
  2. sapuan sumber — TIDAK BOLEH ADA lagi `db.persediaan.find` berfilter
     kosong di mana pun di backend. Lapis kedua yang menjaga pintu berikutnya.
"""
import asyncio
import pathlib
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

from shared_utils import scope_query_field_satker

USER_A = {"username": "a", "role": "admin", "kode_satker": "527010"}
USER_B = {"username": "b", "role": "admin", "kode_satker": "999999"}
SUPER = {"username": "s", "role": "super_admin", "kode_satker": ""}

BACKEND = pathlib.Path(__file__).resolve().parents[2]


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def dbx():
    fake = AsyncMongoMockClient()["uji"]

    async def _seed():
        await fake.persediaan.insert_many([
            {"id": "p1", "kode_satker": "527010", "nama_barang": "Kertas A4",
             "batches": [{"qty": 10, "harga": 50_000}]},
            {"id": "p2", "kode_satker": "527010", "nama_barang": "Tinta",
             "batches": [{"qty": 5, "harga": 100_000}]},
            {"id": "p3", "kode_satker": "999999", "nama_barang": "Map Snelhecter",
             "batches": [{"qty": 200, "harga": 3_000}]},
        ])
    _jalan(_seed())
    return fake


def _ambil(dbx, user):
    async def _q():
        return [d async for d in dbx.persediaan.find(
            scope_query_field_satker(user), {"_id": 0, "id": 1})]
    return {d["id"] for d in _jalan(_q())}


def test_satker_A_tidak_melihat_persediaan_satker_B(dbx):
    assert _ambil(dbx, USER_A) == {"p1", "p2"}


def test_satker_B_tidak_melihat_persediaan_satker_A(dbx):
    assert _ambil(dbx, USER_B) == {"p3"}


def test_super_admin_tetap_lintas_satker(dbx):
    # Scope BUKAN penjara: super-admin memang berwenang lintas satker, dan
    # perbaikan C3 tidak boleh diam-diam mencabut kewenangan itu.
    assert _ambil(dbx, SUPER) == {"p1", "p2", "p3"}


def test_kueri_rekonsiliasi_memakai_scope():
    """Titik yang persis diperbaiki — dibaca dari sumbernya."""
    src = (BACKEND / "routes" / "reports.py").read_text(encoding="utf-8")
    i = src.index("async def generate_rekonsiliasi_xlsx")
    badan = src[i:i + 6000]
    j = badan.index("db.persediaan.find(")
    potongan = badan[j:j + 200]
    assert "scope_query_field_satker(_user)" in potongan, potongan


def test_NOL_kueri_persediaan_berfilter_kosong_di_seluruh_backend():
    """Sapuan kelas — penjaga sesungguhnya.

    Memperbaiki satu baris hanya menutup satu pintu. Yang membuat C3 bertahan
    lama adalah ia terlihat persis seperti tetangganya yang benar. Aturan
    "persediaan tidak pernah dibaca tanpa filter" bisa diperiksa mesin, jadi
    diperiksa mesin.
    """
    pola = re.compile(r"db\.persediaan\.(find|aggregate|count_documents)\(\s*\{\s*\}")
    pelanggar = []
    for p in BACKEND.rglob("*.py"):
        if "tests" in p.parts or "venv" in p.parts:
            continue
        teks = p.read_text(encoding="utf-8", errors="ignore")
        for m in pola.finditer(teks):
            baris = teks[:m.start()].count("\n") + 1
            pelanggar.append(f"{p.relative_to(BACKEND)}:{baris}")
    assert pelanggar == [], f"persediaan dibaca tanpa filter satker: {pelanggar}"
