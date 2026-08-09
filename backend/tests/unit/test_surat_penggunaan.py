"""Dokumen resmi register penggunaan (ASET-DOK-2):

  1. Surat Usulan Penyerahan BMN Idle — hanya tiket klarifikasi/usul_serah
     yang ikut (tiket diserahkan tidak); `ids` menyaring.
  2. Surat Permohonan proses penggunaan per tiket — daftar aset + identitas
     tercetak, nomor dibooking SEKALI lalu disimpan di tiket.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rpg

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
    for mod in (rpg, su):
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


def test_surat_idle_hanya_status_pra_serah(dbx):
    async def skenario():
        for dok in (
            {"id": "id-1", "asset_id": "a1", "asset_code": "3050104001",
             "NUP": "1", "asset_name": "PC Menganggur", "alasan": "Nonaktif",
             "status": "klarifikasi"},
            {"id": "id-2", "asset_id": "a2", "asset_code": "3100102001",
             "NUP": "2", "asset_name": "Meja Tanpa Pengguna",
             "alasan": "Tanpa pengguna", "status": "usul_serah"},
            {"id": "id-3", "asset_id": "a3", "asset_code": "3050201001",
             "NUP": "3", "asset_name": "Lemari Sudah Serah",
             "alasan": "Nonaktif", "status": "diserahkan"},
        ):
            await dbx.bmn_idle.insert_one(
                {**dok, "kode_satker": "", "created_at": "2026-08-01"})
        await dbx.assets.insert_one({"id": "a1", "purchase_price": "9000000"})
        await dbx.assets.insert_one({"id": "a2", "purchase_price": "3000000"})
        return await _teks(await _unwrap(rpg.surat_usulan_idle)(
            ids="", booking=0, _user=USER))
    teks = _jalan(skenario())
    assert "PC Menganggur" in teks and "Meja Tanpa Pengguna" in teks
    assert "Lemari Sudah Serah" not in teks   # sudah diserahkan — tak ikut
    assert "12.000.000" in teks               # total dari master aset


def test_surat_proses_membooking_nomor_sekali(dbx, monkeypatch):
    panggilan = []

    async def _booking(*a, **k):
        panggilan.append(1)
        return "SP-003/VIII/2026", "sid-9"

    import routes.persuratan as rsu
    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _booking)

    async def skenario():
        await dbx.penggunaan_proses.insert_one({
            "id": "pr-1", "kode_satker": "",
            "jenis_proses": "penggunaan_sementara", "arah": "keluar",
            "pihak_asal": "Satker Kita", "pihak_tujuan": "Kementerian X",
            "aset": [{"asset_id": "a1", "asset_code": "3050104001",
                      "NUP": "1", "asset_name": "Genset Portabel"}],
            "status": "draf", "tanggal_mulai": "2026-09-01",
            "tanggal_berakhir": "2026-12-01", "keterangan": "dukungan acara",
            "created_at": "2026-08-01"})
        await dbx.assets.insert_one({"id": "a1", "purchase_price": "45000000"})
        t1 = await _teks(await _unwrap(rpg.surat_permohonan_proses)(
            "pr-1", _user=USER))
        t2 = await _teks(await _unwrap(rpg.surat_permohonan_proses)(
            "pr-1", _user=USER))
        tiket = await dbx.penggunaan_proses.find_one({"id": "pr-1"})
        return t1, t2, tiket

    t1, t2, tiket = _jalan(skenario())
    assert "Genset Portabel" in t1
    assert "Kementerian X" in t1
    assert "45.000.000" in t1
    assert "SP-003/VIII/2026" in t1 and "SP-003/VIII/2026" in t2
    assert tiket["nomor_surat_permohonan"] == "SP-003/VIII/2026"
    assert len(panggilan) == 1
