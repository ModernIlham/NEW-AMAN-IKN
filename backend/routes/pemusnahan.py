"""PEMUSNAHAN — Fase 6 tahap awal: register Berita Acara Pemusnahan.

PMK 83/PMK.06/2016 (pustaka §1 & §11): BA dicatat setelah persetujuan +
pelaksanaan; objek dibatasi aset rusak berat (kelayakan divalidasi per
aset). Tindak lanjut penghapusan lewat modul Penghapusan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemusnahan_utils import (
    CARA_PEMUSNAHAN, kelayakan_musnah, rekap_pemusnahan, validate_pemusnahan,
)

pemusnahan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "condition": 1}


class PemusnahanIn(BaseModel):
    nomor_ba: str
    tanggal_ba: str
    cara: str
    nomor_persetujuan: str
    keterangan: str = ""
    asset_ids: list[str] = Field(min_length=1, max_length=100)


@pemusnahan_router.get("/pemusnahan")
async def list_pemusnahan(_user: dict = Depends(require_user)):
    """Register BA pemusnahan (terbaru dulu) + ringkasan."""
    items = [r async for r in db.pemusnahan.find({}, {"_id": 0})
             .sort("tanggal_ba", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_pemusnahan(items),
            "label_cara": CARA_PEMUSNAHAN,
            "catatan": (
                "BA dicatat setelah persetujuan Pengelola/Pengguna Barang dan "
                "pelaksanaan pemusnahan (PMK 83/2016); tindak lanjut usulan "
                "penghapusan lewat modul Penghapusan.")}


@pemusnahan_router.post("/pemusnahan")
async def buat_pemusnahan(payload: PemusnahanIn, user: dict = Depends(require_user)):
    """Catat satu BA pemusnahan multi-aset (aset harus rusak berat)."""
    data = payload.model_dump()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    errors = validate_pemusnahan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):  # dedup, jaga urutan
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        layak, alasan = kelayakan_musnah(a)
        if not layak:
            raise HTTPException(status_code=400,
                                detail=f"{a.get('asset_name') or aid}: {alasan}")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "harga": a.get("purchase_price")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "nomor_ba": data["nomor_ba"].strip(),
        "tanggal_ba": str(data["tanggal_ba"]).strip()[:10],
        "cara": data["cara"],
        "nomor_persetujuan": data["nomor_persetujuan"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "aset": aset_rows,
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemusnahan.insert_one({**record})
    return record


@pemusnahan_router.delete("/pemusnahan/{ba_id}")
async def hapus_pemusnahan(ba_id: str, _admin: dict = Depends(require_admin)):
    """Hapus BA salah input (khusus admin)."""
    res = await db.pemusnahan.delete_one({"id": ba_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    return {"ok": True, "id": ba_id}
