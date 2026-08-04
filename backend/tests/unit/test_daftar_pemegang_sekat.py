"""Uji PDF "Daftar Barang yang Digunakan" (Lampiran BAST Penggunaan).

Lampiran ini dibaca berdampingan dengan BAST induknya, jadi susunan tabelnya
harus SAMA: sekat pembagi per BIDANG kode barang berikut jumlah unit, barang
terurut kode lalu NUP terkecil. Kalau lampiran memakai urutan lain (dulu:
menurut nama barang), pembaca harus mencocokkan dua daftar berbeda urutan
untuk barang yang sama — kesalahan yang tidak menimbulkan error apa pun.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rp

SATKER = "527010"
USER = {"username": "arsiparis", "role": "admin", "kode_satker": SATKER}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    import routes.reports as rrep
    for mod in (rp, su, rrep):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "log_audit", _diam, raising=False)

    # Gerbang W9 memakai $regex+$options yang tidak didukung mongomock; yang
    # diuji di sini tata letak tabel, bukan gerbang itu (sudah ada ujinya
    # sendiri) — jadi dilewatkan apa adanya.
    async def _lewat(query=None):
        return dict(query or {})
    monkeypatch.setattr(su, "filter_aset_perhitungan", _lewat, raising=False)
    return fake


def _teks_pdf(resp):
    import io
    import pypdfium2 as pdfium
    buf = io.BytesIO()

    async def kumpul():
        async for potong in resp.body_iterator:
            buf.write(potong if isinstance(potong, bytes) else potong.encode())
    _jalan(kumpul())
    pdf = pdfium.PdfDocument(buf.getvalue())
    try:
        return "\n".join(h.get_textpage().get_text_range() for h in pdf)
    finally:
        pdf.close()


PEMEGANG = "Karina Lia Meirita Ulo"


def _aset(kode, nup, nama):
    return {"id": f"{kode}-{nup}", "asset_code": kode, "NUP": nup,
            "asset_name": nama, "brand": "-", "model": "-",
            "serial_number": "-", "condition": "Baik",
            "location": "Kemenko 3 Tower 2", "user": PEMEGANG,
            "pengguna_nip": "199005242025062002",
            "pengguna_jabatan": "Perekayasa Ahli Pertama",
            "activity_id": "keg-1",
            "kode_satker": SATKER, "status_inventarisasi": "ditemukan"}


async def _seed(dbx):
    # Aset hanya ikut perhitungan bila kegiatannya layak hitung (gerbang W9).
    await dbx.inventory_activities.insert_one({
        "id": "keg-1", "kode_satker": SATKER, "status_pengesahan": "disahkan",
        "tanggal_selesai": "2026-07-01"})
    await dbx.report_settings.insert_one({
        "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
        "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
        "alamat_instansi": "Gedung Kantor Otorita IKN, Nusantara"})
    await dbx.kodefikasi.insert_many([
        {"kode": "305", "uraian": "Alat Kantor dan Rumah Tangga"},
        {"kode": "306", "uraian": "Alat Studio, Komunikasi dan Pemancar"},
    ])
    # Sengaja dimasukkan dengan urutan acak (kamera NUP 1, VR, kamera NUP 2)
    await dbx.assets.insert_many([
        _aset("3060102128", "1", "Camera Digital"),
        _aset("3050105097", "1", "Realitas Virtual (Virtual Reality) Head set"),
        _aset("3060102128", "2", "Camera Digital"),
    ])


def test_lampiran_bersekat_bidang_dan_terurut_nup(dbx):
    async def skenario():
        await _seed(dbx)
        return await _unwrap(rp.daftar_pemegang_pdf)(
            nama=PEMEGANG, nip="199005242025062002", _user=USER)
    teks = _teks_pdf(_jalan(skenario()))
    assert "DAFTAR BARANG YANG DIGUNAKAN" in teks
    assert "BIDANG 305" in teks and "BIDANG 306" in teks
    assert "Alat Studio, Komunikasi dan Pemancar" in teks
    assert "1 unit" in teks and "2 unit" in teks          # jumlah per sekat
    assert teks.index("BIDANG 305") < teks.index("BIDANG 306")
    # Kelompok tidak saling menyisip: VR (305) selesai sebelum kamera (306)
    assert teks.index("Realitas Virtual") < teks.index("BIDANG 306")


def test_lampiran_tanpa_kodefikasi_tetap_bersekat(dbx):
    """Referensi kodefikasi belum lengkap → sekat cukup menyebut kodenya,
    tidak mengarang nama bidang dan tidak batal mengelompokkan."""
    async def skenario():
        await _seed(dbx)
        await dbx.kodefikasi.delete_many({})
        return await _unwrap(rp.daftar_pemegang_pdf)(
            nama=PEMEGANG, nip="199005242025062002", _user=USER)
    teks = _teks_pdf(_jalan(skenario()))
    assert "BIDANG 305" in teks and "BIDANG 306" in teks
    assert "Alat Studio" not in teks
