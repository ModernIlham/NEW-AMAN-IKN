"""Nama barang/kegiatan bertanda `< >` tidak boleh hilang dari dokumen resmi.

ReportLab memperlakukan isi `Paragraph` sebagai markup mini. Teks pengguna yang
memuat tanda kurung siku — "PC <Dell>", "Kabel <3m>", "Monitor <24 inci>" —
dianggap TAG yang tidak dikenal lalu **dibuang diam-diam**: tak ada galat, tak
ada peringatan, hanya kata yang lenyap dari Berita Acara / SPTJM / Surat Koreksi
yang sudah ditandatangani Kuasa Pengguna Barang.

Uji ini merender dokumennya sungguhan lalu membaca teksnya kembali, karena
itulah satu-satunya cara membuktikan katanya benar-benar sampai ke kertas.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

_USER = {"username": "adm", "role": "admin", "kode_satker": ""}

# Nama yang memancing parser markup ReportLab dari tiga arah sekaligus.
NAMA_JEBAKAN = "PC <Dell> & Monitor 24<inci>"


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _isi(resp):
    if hasattr(resp, "body_iterator"):
        return b"".join([c async for c in resp.body_iterator])
    return resp.body


def _telanjangi(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


async def _siapkan(monkeypatch, klasifikasi):
    import routes.reports as R
    import shared_utils as su

    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(R, "db", fake, raising=False)
    monkeypatch.setattr(su, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(su, "pastikan_akses_kegiatan_id", _diam, raising=False)
    monkeypatch.setattr(R, "pastikan_akses_kegiatan_id", _diam, raising=False)

    await fake.inventory_activities.insert_one({
        "id": "k1", "nama_kegiatan": "Inventarisasi <Gedung A> & Halaman",
        "kode_satker": "123456"})
    await fake.assets.insert_one({
        "id": "a1", "activity_id": "k1", "asset_code": "3050104001", "NUP": "1",
        "asset_name": NAMA_JEBAKAN, "inventory_status": "Tidak Ditemukan",
        "klasifikasi_tidak_ditemukan": klasifikasi,
        "sub_klasifikasi": "Tidak Ditemukan Fisiknya",
        "uraian_tidak_ditemukan": "Hilang di ruang <server>",
        "tindak_lanjut": "Usul hapus <segera>",
        "condition": "Baik", "purchase_price": "1000",
        "purchase_date": "2020-01-01", "location": "Gudang A"})
    return fake


def _teks(data):
    pypdf = pytest.importorskip("pypdf")
    r = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(p.extract_text() for p in r.pages)


def _utuh(teks):
    """Seluruh kata dari nama jebakan harus muncul — termasuk yang di dalam < >."""
    return all(k in teks for k in ("PC", "Dell", "Monitor", "inci"))


class TestNamaBarangTidakHilang:
    def test_berita_acara(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, "Tidak Ditemukan Lainnya")
            t = _teks(await _isi(await _telanjangi(R.generate_berita_acara_pdf)(
                "k1", _user=_USER)))
            assert _utuh(t), "kata di dalam < > hilang dari Berita Acara"
        _jalan(skenario())

    def test_sptjm(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, "Tidak Ditemukan Lainnya")
            t = _teks(await _isi(await _telanjangi(R.generate_sptjm_pdf)(
                "k1", _user=_USER)))
            assert _utuh(t), "kata di dalam < > hilang dari SPTJM"
        _jalan(skenario())

    def test_surat_koreksi(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, "Kesalahan Pencatatan")
            t = _teks(await _isi(await _telanjangi(R.generate_surat_koreksi_pdf)(
                "k1", _user=_USER)))
            assert _utuh(t), "kata di dalam < > hilang dari Surat Koreksi"
            # Kolom teks bebas ikut selamat.
            assert "server" in t and "segera" in t
        _jalan(skenario())

    def test_nama_kegiatan_di_intro_berita_acara(self, monkeypatch):
        """Nama kegiatan masuk ke kalimat pembuka BA, bukan ke tabel."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, "Tidak Ditemukan Lainnya")
            t = _teks(await _isi(await _telanjangi(R.generate_berita_acara_pdf)(
                "k1", _user=_USER)))
            assert "Gedung A" in t, "nama kegiatan terpotong di kalimat pembuka"
        _jalan(skenario())
