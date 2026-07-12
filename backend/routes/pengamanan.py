"""PENGAMANAN — Fase 3 tahap awal: dasbor tertib administrasi + sengketa.

Proyeksi baca dari data inventarisasi (tanpa koleksi baru). Arsip dokumen
kepemilikan (sertifikat/BPKB) & jadwal pemeliharaan menyusul sesuai
masterplan Fase 3 (pustaka §2.1 & §4).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from auth_utils import require_user
from db import db
from pengamanan_utils import (
    JENIS_KEKURANGAN, kekurangan_aset, rekap_kesehatan,
)

pengamanan_router = APIRouter()

# Proyeksi hemat: foto cukup 1 elemen pertama untuk uji keberadaan.
_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "kode_register": 1, "location": 1, "user": 1, "bast_file_id": 1,
         "inventory_status": 1, "nomor_perkara": 1, "pihak_bersengketa": 1,
         "keterangan_sengketa": 1, "activity_id": 1,
         "photos": {"$slice": 1}, "photo_gridfs_ids": {"$slice": 1}}


@pengamanan_router.get("/pengamanan/ringkasan")
async def ringkasan_pengamanan(_user: dict = Depends(require_user)):
    """Kesehatan data seluruh aset + daftar pantau sengketa."""
    assets = [a async for a in db.assets.find({}, _PROJ)]
    per, lengkap, sengketa = rekap_kesehatan(assets)
    return {
        "total_aset": len(assets),
        "lengkap": lengkap,
        "kekurangan": per,
        "label_kekurangan": JENIS_KEKURANGAN,
        "sengketa": sengketa,
        "jumlah_sengketa": len(sengketa),
    }


@pengamanan_router.get("/pengamanan/aset-kurang")
async def aset_kurang(
    jenis: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Daftar aset dengan kekurangan tertentu (foto/register/lokasi/pengguna/bast)."""
    if jenis not in JENIS_KEKURANGAN:
        valid = ", ".join(JENIS_KEKURANGAN)
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal (pilihan: {valid})")
    rows = []
    async for a in db.assets.find({}, _PROJ):
        if jenis in kekurangan_aset(a):
            rows.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "location": a.get("location"),
                "activity_id": a.get("activity_id"),
            })
    rows.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total,
            "page": page, "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),
            "label": JENIS_KEKURANGAN[jenis]}
