"""Penukaran tautan pendek: kode → tujuan.

Halaman `/s/{kode}` di frontend memanggil endpoint ini lalu mengalihkan.
Dibuat sebagai penukaran (bukan 301 dari nginx) supaya fitur ini hidup lewat
pipeline deploy biasa — konfigurasi nginx di VPS tidak perlu disentuh, dan
tak ada mode gagal senyap "tautan pendek 404 karena nginx belum diperbarui".

Endpoint ini SENGAJA publik: yang membuka tautan e-sign adalah tamu tanpa
akun. Karena itu ia ber-batas laju ketat — kode 10 karakter base62 sudah
mustahil ditebak satu per satu, dan batas laju menutup upaya penyapuan
terdistribusi supaya tak ada yang bisa memanen tautan tanda tangan.
"""
from fastapi import APIRouter, HTTPException, Request

from shared_utils import limiter
from tautan_pendek_utils import resolve_tautan

tautan_pendek_router = APIRouter()


@tautan_pendek_router.get("/s/{kode}")
@limiter.limit("60/minute")
async def tukar_tautan_pendek(kode: str, request: Request):
    """Kembalikan tujuan tautan pendek. 404 bila tak dikenal, sudah dicabut,
    atau kedaluwarsa — pesannya SAMA untuk ketiganya supaya tak jadi oracle
    yang memberi tahu penebak bahwa suatu kode 'pernah ada'."""
    tujuan = await resolve_tautan(kode)
    if not tujuan:
        raise HTTPException(
            status_code=404,
            detail="Tautan tidak dikenal atau sudah tidak berlaku")
    return {"tujuan": tujuan}
