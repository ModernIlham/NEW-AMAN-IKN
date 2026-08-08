"""Perakitan dokumen ber-TTD pindah ke thread — TL-3 (sisa temuan S7).

`_bangun_pdf_ber_ttd` dulu menjalankan SELURUH pypdf + ReportLab di event
loop, dan 4 `await` di tengah badannya (blob GridFS per penanda, status
kepegawaian per NIP, link verifikasi pendek) membuatnya tak bisa sekadar
dibungkus `to_thread`. Kini fungsi async hanya MENGUMPULKAN data, lalu
perakitan murni-CPU-nya (`_rakit_pdf_ber_ttd`) berjalan lewat
`asyncio.to_thread` — BUKAN `_PDFIUM_EXEC`, karena perakitan tak menyentuh
pypdfium2 dan mengantre di belakang render pratinjau tak ada gunanya.

Bahaya restrukturisasi ini bukan kinerja melainkan PARITAS: prefetch yang
salah kawat (blob tertukar, status NIP hilang) menghasilkan dokumen resmi
yang salah tanpa galat apa pun. Uji perilaku di bawah membaca PDF yang jadi.
"""
import asyncio
import io
import threading

import pytest

import routes.ttd as rt


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _pdf(halaman=2) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(halaman):
        c.drawString(72, 720, f"Naskah halaman {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (120, 40), (10, 10, 120, 255)).save(buf, format="PNG")
    return buf.getvalue()


NIP_ASN = "197001011990031001"


def _sr():
    return {
        "kode_satker": "111111",
        "signers": [
            # Posisi pilihan di halaman 1 (fraksi kiri-atas).
            {"nama": "Sari", "signature_file_id": "sig-1",
             "signed_at": "2026-08-08T10:00:00",
             "posisi_ttd": {"halaman": 1, "x": 0.1, "y": 0.2, "lebar": 0.25}},
            # Slot otomatis di halaman terakhir, ber-NIP.
            {"nama": "Budi", "signature_file_id": "sig-2",
             "signed_at": "2026-08-08T11:00:00", "nip": NIP_ASN,
             "jabatan": "Kepala Sub Bagian"},
        ],
    }


@pytest.fixture()
def sadapan(monkeypatch):
    """Sumber data async dipalsukan; catatan panggilan dikembalikan."""
    catatan = {"gridfs": [], "status_nip": [], "verif": 0}

    async def _blob(fid):
        catatan["gridfs"].append(fid)
        return _png()

    async def _status(nip):
        catatan["status_nip"].append(nip)
        return "PNS"

    async def _verif(sr_id, kode_satker="", oleh=""):
        catatan["verif"] += 1
        return f"https://aman.uji/v/{sr_id[:8]}"

    monkeypatch.setattr(rt, "get_document_from_gridfs", _blob)
    monkeypatch.setattr(rt, "_link_verifikasi_pendek", _verif)
    import shared_utils
    monkeypatch.setattr(shared_utils, "status_kepegawaian_by_nip", _status)
    return catatan


def _teks(data: bytes):
    pdfium = pytest.importorskip("pypdfium2")
    dok = pdfium.PdfDocument(io.BytesIO(data))
    return [p.get_textpage().get_text_range() for p in dok]


class TestParitasPerilaku:
    def test_dokumen_utuh_dan_kedua_gaya_ttd_terpasang(self, sadapan):
        from pypdf import PdfReader
        out = _jalan(rt._bangun_pdf_ber_ttd(_sr(), "sr-uji-1", _pdf()))
        data = out.getvalue()
        halaman = _teks(data)
        assert len(halaman) == 2
        # Naskah asli tak hilang.
        assert "Naskah halaman 1" in halaman[0]
        # Slot otomatis di halaman terakhir: stempel + nama + NIP (status PNS
        # dari prefetch → baris NIP tetap dicetak) + QR verifikasi otomatis.
        assert "Ditandatangani secara elektronik" in halaman[1]
        assert "Budi" in halaman[1]
        assert NIP_ASN in halaman[1]
        assert "Verifikasi:" in halaman[1]
        # Gambar ttd benar-benar tertanam: posisi-pilihan di hal 1, slot
        # otomatis di hal 2 — prefetch blob yang salah kawat mematikan ini.
        reader = PdfReader(io.BytesIO(data))
        assert len(reader.pages[0].images) >= 1
        assert len(reader.pages[1].images) >= 1
        assert set(sadapan["gridfs"]) == {"sig-1", "sig-2"}
        assert sadapan["status_nip"] == [NIP_ASN]

    def test_pratinjau_tanpa_qr(self, sadapan):
        out = _jalan(rt._bangun_pdf_ber_ttd(_sr(), "sr-uji-2", _pdf(),
                                            sertakan_qr=False))
        halaman = _teks(out.getvalue())
        assert "Ditandatangani secara elektronik" in halaman[1]
        assert all("Verifikasi:" not in h for h in halaman)

    def test_status_non_asn_menyembunyikan_baris_nip(self, sadapan,
                                                     monkeypatch):
        # Aturan privasi mengalir lewat prefetch status_nip — mutasi yang
        # memutus kawatnya (status selalu kosong) membuat NIP Non-ASN ikut
        # tercetak di dokumen resmi.
        import shared_utils

        async def _non_asn(nip):
            # Token persis yang dikenali label_nomor_identitas: "non_asn".
            return "non_asn"
        monkeypatch.setattr(shared_utils, "status_kepegawaian_by_nip",
                            _non_asn)
        halaman = _teks(_jalan(
            rt._bangun_pdf_ber_ttd(_sr(), "sr-uji-3", _pdf())).getvalue())
        assert "Budi" in halaman[1]
        assert NIP_ASN not in halaman[1]

    def test_blob_hilang_tidak_meledak(self, sadapan, monkeypatch):
        async def _kosong(fid):
            return None
        monkeypatch.setattr(rt, "get_document_from_gridfs", _kosong)
        halaman = _teks(_jalan(
            rt._bangun_pdf_ber_ttd(_sr(), "sr-uji-4", _pdf())).getvalue())
        # Slot otomatis tetap mencetak nama tanpa gambar; dokumen tetap utuh.
        assert len(halaman) == 2
        assert "Budi" in halaman[1]


class TestDiThread:
    def test_perakitan_tidak_di_thread_utama(self, sadapan, monkeypatch):
        """Mutasi inti TL-3: kembali memanggil `_rakit_pdf_ber_ttd` telanjang
        di coroutine → perakitan kembali membekukan event loop. Selain uji
        ini, penjaga AST SINKRON di test_cpu_sinkron_di_thread.py menangkap
        bentuk sumbernya."""
        jejak = {}
        asli = rt._rakit_pdf_ber_ttd

        def _catat(*a, **kw):
            jejak["utama"] = (threading.current_thread()
                              is threading.main_thread())
            return asli(*a, **kw)

        monkeypatch.setattr(rt, "_rakit_pdf_ber_ttd", _catat)
        _jalan(rt._bangun_pdf_ber_ttd(_sr(), "sr-uji-5", _pdf()))
        assert jejak["utama"] is False

    def test_rakit_tetap_sinkron(self):
        import inspect
        assert not inspect.iscoroutinefunction(rt._rakit_pdf_ber_ttd)
        assert inspect.iscoroutinefunction(rt._bangun_pdf_ber_ttd)
