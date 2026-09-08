"""Batas dibaca dari isi nyata, sebelum parser, job, atau penyedia berbayar."""
import asyncio
import inspect
import io
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from unggahan_utils import baca_unggahan_terbatas


class UnggahanTerukur:
    """Tidak mengalokasikan file besar; melarang read() tanpa batas."""

    def __init__(self, ukuran, potongan=1024 * 1024, filename="kategori.csv"):
        self.ukuran = ukuran
        self.potongan = potongan
        self.filename = filename
        self.size = 0  # Metadata sengaja salah: isi nyata tetap harus diperiksa.
        self.dibaca = 0
        self.permintaan = []

    async def read(self, ukuran=-1):
        assert 0 < ukuran <= 1024 * 1024
        self.permintaan.append(ukuran)
        jumlah = min(ukuran, self.potongan, self.ukuran - self.dibaca)
        self.dibaca += jumlah
        return b"x" * jumlah


@pytest.mark.asyncio
@pytest.mark.parametrize("ukuran", [0, 1, 63, 64])
async def test_batas_inklusif_dan_potongan_pendek(ukuran):
    unggahan = UnggahanTerukur(ukuran, potongan=7)
    assert await baca_unggahan_terbatas(unggahan, 64, "Terlalu besar") == b"x" * ukuran
    assert unggahan.dibaca == ukuran


@pytest.mark.asyncio
async def test_berhenti_tepat_satu_byte_setelah_batas():
    batas = 2 * 1024 * 1024
    unggahan = UnggahanTerukur(100 * batas)
    with pytest.raises(HTTPException) as galat:
        await baca_unggahan_terbatas(unggahan, batas, "Terlalu besar")
    assert galat.value.status_code == 400
    assert galat.value.detail == "Terlalu besar"
    assert unggahan.dibaca == batas + 1
    assert unggahan.permintaan == [1024 * 1024, 1024 * 1024, 1]


def permintaan():
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


@pytest.fixture
def kategori(monkeypatch):
    from routes import categories as modul
    monkeypatch.setattr(modul, "buat_job", AsyncMock(return_value="job-uji"))
    monkeypatch.setattr(modul, "update_job", AsyncMock())
    monkeypatch.setattr(modul, "_do_bulk_import", AsyncMock())
    return modul


@pytest.mark.asyncio
@pytest.mark.parametrize("kosong", [True, False])
async def test_kategori_ditolak_sebelum_job_dan_parser(kategori, monkeypatch, kosong):
    parser = Mock()
    monkeypatch.setattr(kategori, "_parse_baris_impor_kategori", parser)
    batas = kategori.MAKS_IMPOR_KATEGORI
    assert batas == 10 * 1024 * 1024
    unggahan = UnggahanTerukur(0 if kosong else batas * 3)
    with pytest.raises(HTTPException) as galat:
        await inspect.unwrap(kategori.import_categories_bulk)(permintaan(), unggahan, {})
    assert galat.value.status_code == 400
    assert ("kosong" if kosong else "maksimal 10 MB") in galat.value.detail
    assert unggahan.dibaca == (0 if kosong else batas + 1)
    kategori.buat_job.assert_not_awaited()
    kategori.update_job.assert_not_awaited()
    kategori._do_bulk_import.assert_not_called()
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_kategori_tepat_batas_tetap_diparse_dan_diproses(kategori, monkeypatch):
    isi = b"Kode Aset,Deskripsi Barang\n3010101001,Meja\n"
    # Batas kecil cukup untuk menguji endpoint dan parser asli tanpa file besar.
    monkeypatch.setattr(kategori, "MAKS_IMPOR_KATEGORI", len(isi))
    unggahan = UploadFile(filename="kategori.csv", file=io.BytesIO(isi))
    try:
        hasil = await inspect.unwrap(kategori.import_categories_bulk)(
            permintaan(), unggahan, {"username": "operator", "kode_satker": "SATKER-UJI"})
        await asyncio.gather(*kategori._IMPORT_TASKS)
    finally:
        await unggahan.close()
    assert hasil["job_id"] == "job-uji" and hasil["total"] == 1
    assert kategori.buat_job.await_args.kwargs["kode_satker"] == "SATKER-UJI"
    kategori.update_job.assert_awaited_once_with("job-uji", total=1, status="importing")
    kategori._do_bulk_import.assert_awaited_once_with(
        "job-uji", [{"kode aset": "3010101001", "deskripsi barang": "Meja"}])


@pytest.fixture
def kompresi(monkeypatch):
    from routes import pdf_compress as modul
    monkeypatch.setattr(modul, "compress_pdf_ilovepdf", AsyncMock(return_value=(None, None, "")))
    monkeypatch.setattr(modul.pcu, "kompres_pdf_lokal", Mock(return_value=None))
    return modul


@pytest.mark.asyncio
async def test_pdf_berlebih_tidak_dibaca_habis_atau_dikirim_ke_penyedia(kompresi):
    batas = kompresi.pcu.MAKS_UKURAN_PDF
    assert batas == 25 * 1024 * 1024
    unggahan = UnggahanTerukur(batas * 3, filename="dokumen.pdf")
    with pytest.raises(HTTPException) as galat:
        await inspect.unwrap(kompresi.compress_pdf)(permintaan(), unggahan, {})
    assert galat.value.status_code == 400
    assert galat.value.detail == "PDF melebihi 25MB"
    assert unggahan.dibaca == batas + 1
    kompresi.compress_pdf_ilovepdf.assert_not_awaited()
    kompresi.pcu.kompres_pdf_lokal.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("isi,pesan", [(b"", "Berkas kosong"), (b"bukan PDF", "Berkas bukan PDF yang valid")])
async def test_validasi_pdf_lama_tetap_berlaku(kompresi, isi, pesan):
    unggahan = UploadFile(filename="dokumen.pdf", file=io.BytesIO(isi))
    try:
        with pytest.raises(HTTPException) as galat:
            await inspect.unwrap(kompresi.compress_pdf)(permintaan(), unggahan, {})
    finally:
        await unggahan.close()
    assert galat.value.status_code == 400
    assert galat.value.detail == pesan
    kompresi.compress_pdf_ilovepdf.assert_not_awaited()
    kompresi.pcu.kompres_pdf_lokal.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_tepat_batas_diteruskan_utuh_dan_fallback_tetap_bekerja(kompresi, monkeypatch):
    isi = b"%PDF-1.4\nisi-sintetis"
    monkeypatch.setattr(kompresi.pcu, "MAKS_UKURAN_PDF", len(isi))
    unggahan = UploadFile(filename="dokumen.pdf", file=io.BytesIO(isi))
    try:
        respons = await inspect.unwrap(kompresi.compress_pdf)(permintaan(), unggahan, {})
    finally:
        await unggahan.close()
    kompresi.compress_pdf_ilovepdf.assert_awaited_once_with(isi, "dokumen.pdf")
    kompresi.pcu.kompres_pdf_lokal.assert_called_once_with(isi)
    assert b"".join([bagian async for bagian in respons.body_iterator]) == isi
    assert respons.headers["X-Original-Size"] == str(len(isi))
    assert respons.headers["X-Compression-Method"] == "none"
