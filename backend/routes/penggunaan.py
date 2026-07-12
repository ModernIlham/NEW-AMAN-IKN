"""PENGGUNAAN — Fase 3 tahap awal: rekap aset per pemegang lintas kegiatan.

Membaca data yang SUDAH dicatat modul inventarisasi (user, pengguna_nip,
pengguna_melekat_ke, pengguna_jabatan, bast_file_id) — tidak ada koleksi
baru; ini proyeksi baca. PSP/alih status/BMN idle menyusul sesuai
masterplan Fase 3 (PMK 40/2024 & 120/2024 — pustaka §1).
"""
from fastapi import APIRouter, Depends, Query

from auth_utils import require_user
from db import db
from penggunaan_utils import kunci_pemegang, rekap_pemegang

penggunaan_router = APIRouter()

_PROJ = {"_id": 0, "user": 1, "pengguna_nip": 1, "pengguna_melekat_ke": 1,
         "pengguna_jabatan": 1, "bast_file_id": 1, "activity_id": 1}


@penggunaan_router.get("/penggunaan/pemegang")
async def daftar_pemegang(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Rekap pemegang: jumlah aset, kelengkapan BAST, jumlah kegiatan."""
    assets = [a async for a in db.assets.find(
        {"user": {"$exists": True, "$nin": ["", None]}}, _PROJ)]
    rows = rekap_pemegang(assets)
    if search.strip():
        s = search.strip().lower()
        rows = [r for r in rows if s in r["nama"].lower() or s in (r["nip"] or "")
                or s in (r["jabatan"] or "").lower()]
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "items": rows[start:start + page_size],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "total_pemegang": total,
        "total_lengkap": sum(1 for r in rows if r["lengkap"]),
    }


@penggunaan_router.get("/penggunaan/pemegang/aset")
async def aset_pemegang(
    nama: str = Query(..., min_length=1),
    nip: str = "",
    _user: dict = Depends(require_user),
):
    """Daftar aset yang dipegang satu orang (identitas nama+NIP)."""
    key = (" ".join(nama.split()).lower(), nip.strip())
    proj = {**_PROJ, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "location": 1, "condition": 1, "inventory_status": 1}
    out = []
    async for a in db.assets.find(
            {"user": {"$exists": True, "$nin": ["", None]}}, proj):
        if kunci_pemegang(a) == key:
            out.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "location": a.get("location"),
                "condition": a.get("condition"),
                "inventory_status": a.get("inventory_status"),
                "activity_id": a.get("activity_id"),
                "ada_bast": bool(str(a.get("bast_file_id") or "").strip()),
            })
    out.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return {"items": out, "total": len(out)}
