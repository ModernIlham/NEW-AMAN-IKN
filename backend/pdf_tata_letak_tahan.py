"""Penataan PDF ReportLab yang tahan sel tabel kelewat tinggi.

Masalah (tinjauan mutu Nov 2026): ReportLab menolak menata baris tabel yang
lebih tinggi dari satu halaman dan melempar ``LayoutError``. Satu aset dengan
nama ±2.500 karakter — atau data impor lama berisi teks panjang — cukup untuk
membuat Ekspor PDF aset dan Daftar Pemegang PDF SATU KEGIATAN gagal 500, dan
bagian DBHI di LHI ikut gagal disusun. Isian semacam itu sah tersimpan, jadi
laporan resmi tidak boleh ikut jatuh karenanya.

Pendekatan: ``BaseDocTemplate.build`` dibungkus sekali (``pasang()``).
  1. Bangun seperti biasa. Laporan normal tidak berubah SEDIKIT PUN — bahkan
     baris yang tak muat di sisa halaman tetap pindah utuh ke halaman berikut.
  2. HANYA bila gagal dengan ``LayoutError``, setiap tabel di cerita (termasuk
     yang bersarang di KeepTogether/sel tabel) diberi ``splitInRow=1`` lalu
     dibangun ulang dari salinan cerita yang segar: baris raksasa terbelah
     antarhalaman alih-alih menggagalkan seluruh dokumen.
  3. Bila tetap gagal (penyebab bukan tabel), galat asli diteruskan — server
     memetakannya ke 422 berpesan jelas (lihat ``server.py``).

``build`` ReportLab MENGHABISKAN list cerita yang diberikan (pop satu per
satu), karena itu salinan diambil SEBELUM percobaan pertama.
"""
from __future__ import annotations

import logging

from reportlab.platypus.doctemplate import BaseDocTemplate, LayoutError
from reportlab.platypus.tables import Table

logger = logging.getLogger(__name__)

_PENANDA = "_aman_tahan_sel_tinggi"
PESAN_422 = ("Laporan tidak dapat ditata: ada isian yang terlalu panjang untuk "
             "satu halaman PDF. Persingkat isian yang sangat panjang (mis. nama "
             "barang, lokasi, atau catatan) lalu coba lagi.")


def _tabel_dalam(flowables, _kedalaman: int = 0):
    """Semua ``Table`` di cerita, termasuk yang bersarang (batas kedalaman 6)."""
    if _kedalaman > 6 or not flowables:
        return
    for f in flowables:
        if isinstance(f, Table):
            yield f
            for baris in getattr(f, "_cellvalues", ()) or ():
                for sel in baris:
                    if isinstance(sel, (list, tuple)):
                        yield from _tabel_dalam(sel, _kedalaman + 1)
                    elif isinstance(sel, Table):
                        yield from _tabel_dalam([sel], _kedalaman + 1)
        for atribut in ("_content", "_flowables"):
            isi = getattr(f, atribut, None)
            if isinstance(isi, (list, tuple)):
                yield from _tabel_dalam(isi, _kedalaman + 1)


def _bungkus(build_asli):
    def build(self, flowables, *args, **kwargs):
        cadangan = list(flowables)
        tujuan = getattr(self, "filename", None)
        posisi = None
        if hasattr(tujuan, "tell") and hasattr(tujuan, "truncate"):
            try:
                posisi = tujuan.tell()
            except Exception:  # noqa: BLE001 — aliran tak bisa di-seek
                posisi = None
        try:
            return build_asli(self, flowables, *args, **kwargs)
        except LayoutError as galat:
            tabel = list(_tabel_dalam(cadangan))
            if not tabel:
                raise
            for t in tabel:
                t.splitInRow = 1
            logger.warning(
                "Tata letak PDF: sel tabel melebihi satu halaman — dibangun "
                "ulang dengan baris terbelah antarhalaman (%s)", str(galat)[:200])
            if posisi is not None:
                tujuan.seek(posisi)
                tujuan.truncate()
            return build_asli(self, list(cadangan), *args, **kwargs)

    setattr(build, _PENANDA, True)
    build.__wrapped__ = build_asli
    build.__doc__ = build_asli.__doc__
    return build


def pasang() -> None:
    """Pasang pembungkus sekali (idempoten)."""
    if getattr(BaseDocTemplate.build, _PENANDA, False):
        return
    BaseDocTemplate.build = _bungkus(BaseDocTemplate.build)


def terpasang() -> bool:
    return bool(getattr(BaseDocTemplate.build, _PENANDA, False))
