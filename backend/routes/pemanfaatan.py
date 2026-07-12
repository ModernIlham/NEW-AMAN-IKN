"""PEMANFAATAN — Fase 5 tahap awal: register perjanjian pemanfaatan BMN.

PMK 115/PMK.06/2020 (pustaka §6): register + arsip, bukan sistem uang —
persetujuan selalu di Pengelola Barang; PNBP disetor mitra langsung ke
Kas Negara. Status turunan menandai dokumen kurang / jatuh tempo ≤60
hari / berakhir. Pengingat kontribusi tahunan & lampiran wasdal menyusul.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemanfaatan_utils import (
    BENTUK_PEMANFAATAN, LABEL_STATUS_PERJANJIAN, dokumen_kurang,
    rekap_pemanfaatan, status_perjanjian, validate_pemanfaatan,
)

pemanfaatan_router = APIRouter()

_PROJ = {"_id": 0}


class PemanfaatanIn(BaseModel):
    asset_id: str = ""            # opsional: tautan objek BMN
    bentuk: str
    mitra: str = Field(min_length=1)
    jenis_mitra: str = ""         # BUMN/BUMD/PT/koperasi/perorangan/Pemda...
    mulai: str
    berakhir: str
    nilai: float = 0              # nilai sewa total / kontribusi (informasi)
    nomor_persetujuan: str = ""   # persetujuan Pengelola Barang
    nomor_perjanjian: str = ""
    ntpn: str = ""                # bukti setor PNBP (wajib utk sewa aktif)
    keterangan: str = ""


@pemanfaatan_router.get("/pemanfaatan/bentuk")
async def daftar_bentuk(_user: dict = Depends(require_user)):
    """Daftar bentuk pemanfaatan + jangka maksimal untuk form."""
    return {"items": [
        {"key": k, "label": v[0], "maks_tahun": v[1], "dapat_perpanjang": v[2]}
        for k, v in BENTUK_PEMANFAATAN.items()
    ]}


@pemanfaatan_router.get("/pemanfaatan")
async def list_pemanfaatan(_user: dict = Depends(require_user)):
    """Register perjanjian + status turunan + ringkasan."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [p async for p in db.pemanfaatan.find({}, _PROJ)
             .sort("berakhir", 1).limit(500)]
    for p in items:
        p["status"] = status_perjanjian(p, today_iso)
        p["kekurangan"] = dokumen_kurang(p)
    ringkasan = rekap_pemanfaatan(items, today_iso)
    return {"items": items, "ringkasan": ringkasan,
            "label_status": LABEL_STATUS_PERJANJIAN,
            "label_bentuk": {k: v[0] for k, v in BENTUK_PEMANFAATAN.items()},
            "catatan": (
                "Register penatausahaan — persetujuan di Pengelola Barang; "
                "PNBP disetor mitra langsung ke Kas Negara (PMK 115/2020). "
                "Status Aktif menuntut nomor persetujuan + perjanjian "
                "(sewa: + NTPN).")}


@pemanfaatan_router.post("/pemanfaatan")
async def buat_pemanfaatan(payload: PemanfaatanIn, user: dict = Depends(require_user)):
    """Catat satu perjanjian pemanfaatan."""
    data = payload.model_dump()
    errors = validate_pemanfaatan(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    objek = None
    if data.get("asset_id"):
        objek = await db.assets.find_one(
            {"id": data["asset_id"]},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
        if not objek:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": objek["id"] if objek else "",
        "asset_code": objek.get("asset_code") if objek else "",
        "NUP": objek.get("NUP") if objek else "",
        "asset_name": objek.get("asset_name") if objek else "",
        "bentuk": data["bentuk"],
        "mitra": data["mitra"].strip(),
        "jenis_mitra": str(data.get("jenis_mitra") or "").strip(),
        "mulai": str(data["mulai"]).strip()[:10],
        "berakhir": str(data["berakhir"]).strip()[:10],
        "nilai": float(data.get("nilai") or 0),
        "nomor_persetujuan": str(data.get("nomor_persetujuan") or "").strip(),
        "nomor_perjanjian": str(data.get("nomor_perjanjian") or "").strip(),
        "ntpn": str(data.get("ntpn") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemanfaatan.insert_one({**record})
    return record


@pemanfaatan_router.put("/pemanfaatan/{register_id}")
async def ubah_pemanfaatan(register_id: str, payload: PemanfaatanIn,
                           user: dict = Depends(require_user)):
    """Perbarui perjanjian (melengkapi dokumen/nilai)."""
    data = payload.model_dump()
    errors = validate_pemanfaatan(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    update = {k: (str(v).strip() if isinstance(v, str) else v)
              for k, v in data.items() if k != "asset_id"}
    update["mulai"] = update["mulai"][:10]
    update["berakhir"] = update["berakhir"][:10]
    update["nilai"] = float(data.get("nilai") or 0)
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pemanfaatan.find_one_and_update(
        {"id": register_id}, {"$set": update},
        projection=_PROJ, return_document=True)
    if not res:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    return res


@pemanfaatan_router.delete("/pemanfaatan/{register_id}")
async def hapus_pemanfaatan(register_id: str, _admin: dict = Depends(require_admin)):
    """Hapus register salah input (khusus admin)."""
    res = await db.pemanfaatan.delete_one({"id": register_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    return {"ok": True, "id": register_id}
