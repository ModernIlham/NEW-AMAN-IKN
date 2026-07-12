"""PENGHAPUSAN — Fase 6: kandidat usul hapus + tiket usulan berstatus.

PMK 83/PMK.06/2016 (pustaka §1 & §7): jaring kandidat per jalur —
Tidak Ditemukan → penelusuran + telaah TGR; Rusak Berat → pemusnahan/
pemindahtanganan. Tiket usulan: diusulkan → diproses → SK terbit/ditolak
(transisi tervalidasi, riwayat tercatat, arsip nomor SK).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from penghapusan_utils import (
    JALUR_KANDIDAT, STATUS_USULAN, jalur_kandidat, rekap_kandidat,
    validate_transisi,
)

penghapusan_router = APIRouter()


class UsulanIn(BaseModel):
    asset_id: str = Field(min_length=1)
    keterangan: str = ""


class TransisiIn(BaseModel):
    status: str
    nomor_sk: str = ""
    tanggal_sk: str = ""
    catatan: str = ""

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "condition": 1, "inventory_status": 1,
         "location": 1, "uraian_tidak_ditemukan": 1}
_MAKS_BARIS = 500


@penghapusan_router.get("/penghapusan/kandidat")
async def kandidat_penghapusan(_user: dict = Depends(require_user)):
    """Kandidat usul hapus per jalur + status usulan aktifnya (bila ada)."""
    assets = [a async for a in db.assets.find(
        {"$or": [{"inventory_status": "Tidak Ditemukan"},
                 {"condition": "Rusak Berat"}]}, _PROJ)]
    hasil = rekap_kandidat(assets)
    # Lekatkan status usulan aktif per aset agar UI tahu mana yang sudah diusulkan
    usulan_aktif = {}
    async for u in db.usulan_penghapusan.find(
            {"status": {"$ne": "ditolak"}},
            {"_id": 0, "asset_id": 1, "status": 1, "id": 1}):
        usulan_aktif[u["asset_id"]] = {"id": u["id"], "status": u["status"]}
    for b in hasil["jalur"].values():
        for r in b["rows"]:
            r["usulan"] = usulan_aktif.get(r["id"])
        b["dipangkas"] = len(b["rows"]) > _MAKS_BARIS
        b["rows"] = b["rows"][:_MAKS_BARIS]
    hasil["label_status"] = STATUS_USULAN
    hasil["catatan"] = (
        "Kandidat dijaring otomatis dari hasil inventarisasi (kondisi + "
        "status). Penghapusan formal tetap melalui usulan, persetujuan, dan "
        "SK sesuai PMK 83/2016 — nilai tersaji adalah nilai perolehan."
    )
    return hasil


@penghapusan_router.get("/penghapusan/usulan")
async def list_usulan(
    status: str = Query("", description="Saring satu status"),
    _user: dict = Depends(require_user),
):
    """Daftar tiket usulan penghapusan, terbaru dulu."""
    query = {}
    if status:
        if status not in STATUS_USULAN:
            valid = ", ".join(STATUS_USULAN)
            raise HTTPException(status_code=400,
                                detail=f"Status tidak dikenal (pilihan: {valid})")
        query["status"] = status
    items = [u async for u in db.usulan_penghapusan.find(query, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    return {"items": items, "jumlah": len(items), "label_status": STATUS_USULAN,
            "label_jalur": {k: v[0] for k, v in JALUR_KANDIDAT.items()}}


@penghapusan_router.post("/penghapusan/usulan")
async def buat_usulan(payload: UsulanIn, user: dict = Depends(require_user)):
    """Buat tiket usulan penghapusan untuk satu aset kandidat."""
    asset = await db.assets.find_one({"id": payload.asset_id}, _PROJ)
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    jalur = jalur_kandidat(asset)
    if not jalur:
        raise HTTPException(
            status_code=400,
            detail="Aset bukan kandidat penghapusan (bukan Rusak Berat / Tidak Ditemukan)")
    aktif = await db.usulan_penghapusan.find_one(
        {"asset_id": payload.asset_id, "status": {"$ne": "ditolak"}}, {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(status_code=409,
                            detail="Aset ini sudah punya usulan penghapusan aktif")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "jalur": jalur,
        "status": "diusulkan",
        "nomor_sk": "",
        "tanggal_sk": "",
        "keterangan": str(payload.keterangan or "").strip(),
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.usulan_penghapusan.insert_one({**record})
    return record


@penghapusan_router.post("/penghapusan/usulan/{usulan_id}/status")
async def transisi_usulan(usulan_id: str, payload: TransisiIn,
                          admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (khusus admin — gerbang persetujuan)."""
    u = await db.usulan_penghapusan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    errors = validate_transisi(u["status"], payload.status, payload.nomor_sk)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": payload.status,
        "updated_at": now,
    }
    if payload.status == "sk_terbit":
        update["nomor_sk"] = payload.nomor_sk.strip()
        update["tanggal_sk"] = str(payload.tanggal_sk or "").strip()[:10]
    res = await db.usulan_penghapusan.find_one_and_update(
        # Status diikutkan di filter: dua admin yang berlomba tidak bisa
        # menerapkan transisi ganda dari status yang sama
        {"id": usulan_id, "status": u["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status usulan berubah oleh proses lain — muat ulang")
    return res


@penghapusan_router.delete("/penghapusan/usulan/{usulan_id}")
async def hapus_usulan(usulan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (hanya yang masih berstatus diusulkan)."""
    res = await db.usulan_penghapusan.delete_one(
        {"id": usulan_id, "status": "diusulkan"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    return {"ok": True, "id": usulan_id}
