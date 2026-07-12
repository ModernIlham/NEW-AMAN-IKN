"""PENGAMANAN — Fase 3: dasbor tertib administrasi + register kasus.

Dasbor = proyeksi baca dari data inventarisasi (tanpa koleksi baru).
Register BMN bermasalah/sengketa (pustaka §11) memakai koleksi sendiri;
arsip dokumen kepemilikan (sertifikat/BPKB) menyusul.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pengamanan_utils import (
    JENIS_KEKURANGAN, KATEGORI_KASUS, STATUS_KASUS, TRANSISI_KASUS,
    kekurangan_aset, rekap_kasus, rekap_kesehatan, validate_kasus,
    validate_transisi_kasus,
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


class KasusIn(BaseModel):
    asset_id: str = Field(min_length=1)
    kategori: str
    uraian: str = Field(min_length=1)
    pihak_lawan: str = Field(min_length=1)
    nomor_perkara: str = ""
    pendamping: str = ""      # mis. JPN Kejari / Biro Hukum


class TransisiKasusIn(BaseModel):
    status: str
    catatan: str = ""


@pengamanan_router.get("/pengamanan/kasus")
async def list_kasus(_user: dict = Depends(require_user)):
    """Register BMN bermasalah/sengketa (terbaru dulu) + ringkasan."""
    items = [k async for k in db.pengamanan_kasus.find({}, {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_kasus(items),
            "label_kategori": KATEGORI_KASUS,
            "label_status": STATUS_KASUS,
            "transisi": {k: sorted(v) for k, v in TRANSISI_KASUS.items()},
            "catatan": (
                "Register pendamping penanganan BMN bermasalah (pustaka §11) "
                "— bahan laporan wasdal/CaLBMN; bukan kanal resmi, tidak "
                "berkekuatan hukum, dan bukan pemblokiran sertipikat.")}


@pengamanan_router.post("/pengamanan/kasus")
async def buka_kasus(payload: KasusIn, user: dict = Depends(require_user)):
    """Buka kasus baru untuk satu aset (satu kasus aktif per aset)."""
    data = payload.model_dump()
    errors = validate_kasus(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "location": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    aktif = await db.pengamanan_kasus.find_one(
        {"asset_id": asset["id"], "status": {"$ne": "selesai"}},
        {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(
            status_code=409,
            detail="Aset ini sudah punya kasus aktif — selesaikan dulu")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "lokasi": asset.get("location"),
        "kategori": data["kategori"],
        "status": "identifikasi",
        "uraian": data["uraian"].strip(),
        "pihak_lawan": data["pihak_lawan"].strip(),
        "nomor_perkara": str(data.get("nomor_perkara") or "").strip(),
        "pendamping": str(data.get("pendamping") or "").strip(),
        "riwayat": [{"status": "identifikasi", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengamanan_kasus.insert_one({**record})
    return record


@pengamanan_router.post("/pengamanan/kasus/{kasus_id}/status")
async def transisi_kasus(kasus_id: str, payload: TransisiKasusIn,
                         user: dict = Depends(require_user)):
    """Pindahkan status kasus (anti-race pada status lama)."""
    kasus = await db.pengamanan_kasus.find_one({"id": kasus_id}, {"_id": 0})
    if not kasus:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    ke = payload.status
    errors = validate_transisi_kasus(kasus, ke)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    entri = {"status": ke, "tanggal": now, "oleh": user.get("username"),
             "catatan": str(payload.catatan or "").strip()}
    res = await db.pengamanan_kasus.find_one_and_update(
        {"id": kasus_id, "status": kasus["status"]},
        {"$set": {"status": ke, "updated_at": now}, "$push": {"riwayat": entri}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Status kasus berubah di perangkat lain — muat ulang")
    res["status"] = ke
    return res


@pengamanan_router.delete("/pengamanan/kasus/{kasus_id}")
async def hapus_kasus(kasus_id: str, _admin: dict = Depends(require_admin)):
    """Hapus satu kasus dari register (admin)."""
    res = await db.pengamanan_kasus.delete_one({"id": kasus_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    return {"ok": True}
