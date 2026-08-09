"""Nota Dinas persediaan ber-pilihan — permintaan pemilik (2026-08-09):
tidak semua barang habis/kritis harus diusulkan pengadaan ulang, jadi
`GET /persediaan/nota-dinas` menerima `ids` (dipisah koma) dan hanya
mencetak barang TERPILIH. Dua sifat yang dijaga:

  1. Filter benar-benar menyaring ISI PDF — barang yang tidak dipilih
     tidak tercantum (dibaca dari teks PDF-nya, bukan dari niat kode).
  2. `ids` bukan pintu belakang: id yang tidak ada di daftar peringatan
     (mis. barang berstok aman) diabaikan, tidak ikut dicetak.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps

USER = {"username": "op1", "role": "operator", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rps, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


async def _seed(dbx):
    # Dua kandidat nota (habis + kritis) dan satu barang beraman-stok yang
    # TIDAK boleh bisa diseludupkan lewat ids.
    for dok in (
        {"id": "hab-1", "kode_barang": "K001", "nup": "1",
         "nama_barang": "Kertas HVS A4", "satuan": "Rim",
         "stok": 0, "batas_kritis": 5, "batches": []},
        {"id": "kri-1", "kode_barang": "K002", "nup": "1",
         "nama_barang": "Tinta Printer Hitam", "satuan": "Botol",
         "stok": 2, "batas_kritis": 5, "batches": []},
        {"id": "amn-1", "kode_barang": "K003", "nup": "1",
         "nama_barang": "Map Folder Plastik", "satuan": "Buah",
         "stok": 100, "batas_kritis": 5, "batches": []},
    ):
        await dbx.persediaan.insert_one({**dok, "kode_satker": ""})


async def _teks_nota(ids=""):
    pdfium = pytest.importorskip("pypdfium2")
    resp = await _unwrap(rps.nota_dinas_persediaan)(
        jenis="kritis", horizon_hari=30, ids=ids, _user=USER)
    data = b"".join([b async for b in resp.body_iterator])
    assert data[:5] == b"%PDF-"
    from io import BytesIO
    doc = pdfium.PdfDocument(BytesIO(data))
    return "\n".join(p.get_textpage().get_text_range() for p in doc)


def test_tanpa_ids_semua_kandidat_tercetak(dbx):
    async def skenario():
        await _seed(dbx)
        return await _teks_nota("")
    teks = _jalan(skenario())
    assert "Kertas HVS A4" in teks
    assert "Tinta Printer Hitam" in teks
    assert "Map Folder Plastik" not in teks   # stok aman — bukan kandidat


def test_ids_menyaring_hanya_barang_terpilih(dbx):
    async def skenario():
        await _seed(dbx)
        return await _teks_nota("hab-1")
    teks = _jalan(skenario())
    assert "Kertas HVS A4" in teks
    assert "Tinta Printer Hitam" not in teks
    # Dokumen jujur bahwa ini hasil seleksi, bukan daftar lengkap.
    assert "DIPILIH" in teks


def test_ids_bukan_pintu_belakang_barang_aman(dbx):
    async def skenario():
        await _seed(dbx)
        return await _teks_nota("kri-1,amn-1")
    teks = _jalan(skenario())
    assert "Tinta Printer Hitam" in teks
    assert "Map Folder Plastik" not in teks   # id aman diabaikan, tak disisipkan
