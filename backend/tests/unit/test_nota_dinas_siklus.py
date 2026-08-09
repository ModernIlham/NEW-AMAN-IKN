"""Nota Dinas Usulan register siklus (ASET-DOK-1) — dokumen resmi yang dulu
tidak ada (register hanya CSV + nomor teks bebas):

  1. Pemindahtanganan: nota per USULAN — daftar barang tercetak, nomor
     dibooking SEKALI lalu disimpan di register (unduh ulang tak memboroskan
     deret nomor).
  2. Penghapusan: nota gabungan tiket berstatus `diusulkan` — tiket selesai
     tidak ikut; `ids` menyaring dan bukan pintu belakang.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.pemindahtanganan as rpt
import routes.penghapusan as rph

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


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rpt, rph, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


async def _teks(resp):
    pdfium = pytest.importorskip("pypdfium2")
    data = b"".join([b async for b in resp.body_iterator])
    assert data[:5] == b"%PDF-"
    from io import BytesIO
    doc = pdfium.PdfDocument(BytesIO(data))
    return "\n".join(p.get_textpage().get_text_range() for p in doc)


def test_nota_pt_memuat_daftar_dan_membooking_nomor_sekali(dbx, monkeypatch):
    panggilan = []

    async def _booking(*a, **k):
        panggilan.append(1)
        return "ND-007/VIII/2026", "sid-1"

    import routes.persuratan as rsu
    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _booking)

    async def skenario():
        await dbx.pemindahtanganan.insert_one({
            "id": "pt-1", "kode_satker": "", "bentuk": "hibah",
            "pihak": "Pemda Sepaku", "keterangan": "hibah sosial",
            "jenis_bmn": "selain_tanah_bangunan", "nilai_wajar": 0,
            "tb_terkecuali": False, "status": "diusulkan",
            "aset": [
                {"asset_id": "a1", "asset_code": "3050104001", "NUP": "1",
                 "asset_name": "PC Unit Kantor", "harga": "9000000",
                 "kondisi": "Rusak Ringan"},
                {"asset_id": "a2", "asset_code": "3020104002", "NUP": "4",
                 "asset_name": "Sepeda Motor Dinas", "harga": "21000000",
                 "kondisi": "Baik"},
            ],
            "created_at": "2026-08-01T00:00:00+00:00"})
        t1 = await _teks(await _unwrap(rpt.nota_dinas_pt)("pt-1", _user=USER))
        u = await dbx.pemindahtanganan.find_one({"id": "pt-1"})
        # Unduh kedua — nomor dari register, booking TIDAK dipanggil lagi.
        t2 = await _teks(await _unwrap(rpt.nota_dinas_pt)("pt-1", _user=USER))
        return t1, t2, u

    t1, t2, u = _jalan(skenario())
    assert "PC Unit Kantor" in t1 and "Sepeda Motor Dinas" in t1
    assert "Pemda Sepaku" in t1
    assert "ND-007/VIII/2026" in t1
    assert "30.000.000" in t1          # total nilai perolehan
    assert u["nomor_nota"] == "ND-007/VIII/2026"
    assert "ND-007/VIII/2026" in t2
    assert len(panggilan) == 1


async def _seed_penghapusan(dbx):
    for dok in (
        {"id": "uh-1", "asset_id": "a1", "asset_code": "3050104001",
         "NUP": "1", "asset_name": "PC Unit Rusak", "jalur": "rusak_berat",
         "status": "diusulkan"},
        {"id": "uh-2", "asset_id": "a2", "asset_code": "3100102001",
         "NUP": "2", "asset_name": "Proyektor Hilang",
         "jalur": "tidak_ditemukan", "status": "diusulkan"},
        {"id": "uh-3", "asset_id": "a3", "asset_code": "3050201001",
         "NUP": "3", "asset_name": "Printer Sudah SK",
         "jalur": "rusak_berat", "status": "sk_terbit"},
    ):
        await dbx.usulan_penghapusan.insert_one(
            {**dok, "kode_satker": "", "created_at": "2026-08-01"})
    await dbx.assets.insert_one({"id": "a1", "purchase_price": "9000000"})
    await dbx.assets.insert_one({"id": "a2", "purchase_price": "5000000"})


def test_nota_penghapusan_hanya_status_diusulkan(dbx):
    async def skenario():
        await _seed_penghapusan(dbx)
        return await _teks(await _unwrap(rph.nota_dinas_penghapusan)(
            ids="", booking=0, _user=USER))
    teks = _jalan(skenario())
    assert "PC Unit Rusak" in teks and "Proyektor Hilang" in teks
    assert "Printer Sudah SK" not in teks     # bukan diusulkan — tak ikut
    assert "14.000.000" in teks               # total dari master aset


def test_nota_penghapusan_ids_menyaring_dan_bukan_pintu_belakang(dbx):
    async def skenario():
        await _seed_penghapusan(dbx)
        return await _teks(await _unwrap(rph.nota_dinas_penghapusan)(
            ids="uh-1,uh-3", booking=0, _user=USER))
    teks = _jalan(skenario())
    assert "PC Unit Rusak" in teks
    assert "Proyektor Hilang" not in teks     # tak dipilih
    assert "Printer Sudah SK" not in teks     # id status lain diabaikan
    assert "DIPILIH" in teks
