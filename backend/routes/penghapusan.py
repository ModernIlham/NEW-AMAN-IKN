"""PENGHAPUSAN — Fase 6 tahap awal: kandidat usul hapus dari inventarisasi.

PMK 83/PMK.06/2016 (pustaka §1 & §7): jaring kandidat per jalur —
Tidak Ditemukan → penelusuran + telaah TGR; Rusak Berat → pemusnahan/
pemindahtanganan. Tiket usulan formal + arsip SK menyusul.
"""
from fastapi import APIRouter, Depends

from auth_utils import require_user
from db import db
from penghapusan_utils import rekap_kandidat

penghapusan_router = APIRouter()

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "condition": 1, "inventory_status": 1,
         "location": 1, "uraian_tidak_ditemukan": 1}
_MAKS_BARIS = 500


@penghapusan_router.get("/penghapusan/kandidat")
async def kandidat_penghapusan(_user: dict = Depends(require_user)):
    """Kandidat usul hapus per jalur + ringkasan nilai."""
    assets = [a async for a in db.assets.find(
        {"$or": [{"inventory_status": "Tidak Ditemukan"},
                 {"condition": "Rusak Berat"}]}, _PROJ)]
    hasil = rekap_kandidat(assets)
    for b in hasil["jalur"].values():
        b["dipangkas"] = len(b["rows"]) > _MAKS_BARIS
        b["rows"] = b["rows"][:_MAKS_BARIS]
    hasil["catatan"] = (
        "Kandidat dijaring otomatis dari hasil inventarisasi (kondisi + "
        "status). Penghapusan formal tetap melalui usulan, persetujuan, dan "
        "SK sesuai PMK 83/2016 — nilai tersaji adalah nilai perolehan."
    )
    return hasil
