"""Render pratinjau halaman PDF di executor pdfium tunggal — temuan S7.

`_render_halaman_png` dulu sinkron di event loop: ±100–130 ms per halaman
(yang mahal bukan pdfium 11 ms, melainkan encode PNG Pillow 87 ms), dan
`AturPosisiTtd` memicu satu render per ganti halaman. Terukur: 6 pratinjau
bersamaan membuat permintaan lain menunggu median 223 ms / maks 446 ms;
dengan executor, median 0,29 ms / maks 2,4 ms. Perbaikan ini membeli
KETERSEDIAAN, bukan kecepatan.

Kenapa executor 1-thread dan BUKAN `asyncio.to_thread` telanjang (usul
laporan asli): pypdfium2 TIDAK aman-thread — 6 render dari 6 thread
meng-SIGSEGV proses 5/5 percobaan. `to_thread` telanjang menukar "lambat"
dengan "mati"; dengan `--workers 2`, satu worker segfault = separuh
kapasitas hilang sampai supervisor restart. Uji inti di bawah membunuh
persis mutasi itu tanpa segfault dan tanpa timing rapuh: yang diukur
identitas thread dan kedalaman paralel, bukan durasi.
"""
import asyncio
import io
import threading
import time

import pytest
from fastapi import HTTPException
from PIL import Image

import routes.ttd as rt


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _pdf_tiga_halaman() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(3):
        c.drawString(72, 720, f"Halaman {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


async def _kuras(resp) -> bytes:
    return b"".join([b async for b in resp.body_iterator])


class TestSerialisasi:
    def test_render_tidak_di_event_loop_dan_terserialisasi(self, monkeypatch):
        """Uji INTI — dua mutasi mati sekaligus: (1) executor dicabut →
        render kembali ke thread utama; (2) max_workers dinaikkan / usul
        `to_thread` telanjang diterapkan → kedalaman paralel > 1, persis
        kondisi yang meng-SIGSEGV pdfium di produksi."""
        keadaan = {"depth": 0, "maks": 0, "thread_utama": False}
        kunci = threading.Lock()

        def palsu(data, no):
            with kunci:
                keadaan["depth"] += 1
                keadaan["maks"] = max(keadaan["maks"], keadaan["depth"])
                if threading.current_thread() is threading.main_thread():
                    keadaan["thread_utama"] = True
            time.sleep(0.02)
            with kunci:
                keadaan["depth"] -= 1
            return b"\x89PNG\r\n\x1a\n", 3

        monkeypatch.setattr(rt, "_render_halaman_bytes", palsu)

        async def _lima():
            await asyncio.gather(
                *(rt._render_halaman_png(b"x", i) for i in range(5)))
        _jalan(_lima())
        assert keadaan["thread_utama"] is False
        assert keadaan["maks"] == 1


class TestKontrakRespons:
    def test_kontrak_respons_halaman(self):
        # Render NYATA. Kontrak HTTP tidak boleh berubah: Cache-Control
        # hilang = tiap ganti halaman memukul server lagi dan menabrak plafon
        # 60/menit; clamp lebar 1100 bergeser = regresi SENYAP (posisi
        # tersimpan sebagai fraksi, jadi salahnya cuma tampak sebagai
        # ketajaman/berat unduhan yang berubah).
        r = _jalan(rt._render_halaman_png(_pdf_tiga_halaman(), 2))
        assert r.media_type == "image/png"
        assert r.headers["X-Jumlah-Halaman"] == "3"
        assert r.headers["Cache-Control"] == "private, max-age=600"
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        badan = _jalan(_kuras(r))
        assert badan.startswith(b"\x89PNG\r\n\x1a\n")
        assert Image.open(io.BytesIO(badan)).size[0] == 1100

    def test_pdf_rusak_jadi_422_bukan_500(self):
        # Galat harus tetap menembus batas thread sebagai HTTPException 422.
        with pytest.raises(HTTPException) as e:
            _jalan(rt._render_halaman_png(b"bukan pdf", 1))
        assert e.value.status_code == 422

    def test_nomor_halaman_dijepit(self):
        pdf = _pdf_tiga_halaman()
        r = _jalan(rt._render_halaman_png(pdf, 99))
        assert r.headers["X-Jumlah-Halaman"] == "3"
        r0 = _jalan(rt._render_halaman_png(pdf, 0))
        assert r0.headers["X-Jumlah-Halaman"] == "3"


class TestBentukSumber:
    def test_parser_murni_tetap_sinkron_dan_executor_tunggal(self):
        import inspect
        assert not inspect.iscoroutinefunction(rt._render_halaman_bytes)
        assert rt._PDFIUM_EXEC._max_workers == 1

    def test_compress_level_encode_png_dipertahankan(self):
        """Pin setelan TERUKUR, bukan selera: pada halaman naskah 1100px,
        compress_level=3 meng-encode 103 → 64 ms sekaligus 652 → 516 KB
        dibanding bawaan (6). Waktu encode langsung membatasi laju SEMUA
        pratinjau karena executornya tunggal. Mengembalikannya ke bawaan
        (menghapus kwarg) memperlambat tanpa memperkecil apa pun; menurunkan
        ke 0 meledakkan ukuran (terukur 5 MB per halaman)."""
        import inspect
        src = inspect.getsource(rt._render_halaman_bytes)
        assert 'format="PNG", compress_level=3' in src
