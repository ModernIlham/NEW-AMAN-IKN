"""PENGADAAN — Fase 4 tahap awal: register perolehan per dokumen.

Perpres 16/2018 jo. 46/2025 (pustaka §10): satu entri per BAST/kontrak,
checklist kelengkapan dokumen sumber, daftar barang dengan tautan ke aset
master (cegah entri ganda) + penanda ekstrakomptabel PMK 181. Pencatatan
resmi tetap di SAKTI; kanal pengadaan tetap SiRUP/SPSE/e-Katalog — AMAN
alat bantu tertib dokumen satker. Pra-isi draft aset baru menyusul.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    dokumen_kurang_perolehan, is_ekstrakomptabel, nilai_perolehan,
    rekap_perolehan, validate_perolehan,
)

pengadaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


class BarangIn(BaseModel):
    uraian: str = Field(min_length=1)
    kode: str = ""                     # kode barang (opsional, utk ambang)
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)
    asset_id: str = ""                 # tautan ke aset master (opsional)


class PerolehanIn(BaseModel):
    jenis: str
    pihak: str = Field(min_length=1)   # penyedia / pemberi hibah / pengirim
    nomor_kontrak: str = ""
    nomor_bast: str = Field(min_length=1)
    tanggal_bast: str = Field(min_length=10, max_length=10)
    keterangan: str = ""
    barang: list[BarangIn] = Field(min_length=1, max_length=100)


class DokumenIn(BaseModel):
    dokumen: dict[str, bool]


class TautkanIn(BaseModel):
    index: int = Field(ge=0)
    asset_id: str = ""                 # kosong = lepaskan tautan


def _enrich(p: dict) -> dict:
    p["dokumen_kurang"] = dokumen_kurang_perolehan(p)
    p["nilai"] = nilai_perolehan(p)
    for b in p.get("barang") or []:
        b["ekstrakomptabel"] = is_ekstrakomptabel(b)
    return p


@pengadaan_router.get("/pengadaan")
async def list_pengadaan(_user: dict = Depends(require_user)):
    """Register perolehan (BAST terbaru dulu) + ringkasan + label."""
    items = [_enrich(p) async for p in db.pengadaan.find({}, {"_id": 0})
             .sort("tanggal_bast", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_perolehan(items),
            "label_jenis": {k: v[0] for k, v in JENIS_PEROLEHAN.items()},
            "kode_jenis": {k: v[1] for k, v in JENIS_PEROLEHAN.items()},
            "label_dokumen": LABEL_DOKUMEN_SUMBER,
            "dokumen_wajib": {k: list(v) for k, v in DOKUMEN_PEROLEHAN.items()},
            "catatan": (
                "Register pendamping tertib dokumen: pencatatan BMN resmi di "
                "SAKTI (BAST = pemicu, tanpa menunggu SP2D); kanal pengadaan "
                "resmi SiRUP/SPSE/e-Katalog. Penanda ekstrakomptabel memakai "
                "ambang PMK 181/2016 (peralatan-mesin Rp1 jt, gedung Rp25 jt).")}


@pengadaan_router.post("/pengadaan")
async def buat_perolehan(payload: PerolehanIn, user: dict = Depends(require_user)):
    """Catat perolehan baru (barang boleh ditautkan ke aset master)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_perolehan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    barang_rows = []
    for b in data["barang"]:
        row = {"uraian": b["uraian"].strip(),
               "kode": str(b.get("kode") or "").strip(),
               "jumlah": float(b["jumlah"]),
               "harga_satuan": float(b["harga_satuan"]),
               "asset_id": "", "asset_code": "", "NUP": "", "asset_name": ""}
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
            if not a:
                raise HTTPException(status_code=404,
                                    detail=f"Aset {aid} tidak ditemukan")
            row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                        "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
        barang_rows.append(row)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "jenis": data["jenis"],
        "pihak": data["pihak"].strip(),
        "nomor_kontrak": str(data.get("nomor_kontrak") or "").strip(),
        "nomor_bast": data["nomor_bast"].strip(),
        "tanggal_bast": data["tanggal_bast"].strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        # Checklist mulai kosong; BAST & kontrak otomatis tercentang bila
        # nomornya sudah diisi saat pencatatan.
        "dokumen": {"bast": True,
                    **({"kontrak": True} if str(data.get("nomor_kontrak") or "").strip() else {})},
        "barang": barang_rows,
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengadaan.insert_one({**record})
    return _enrich(record)


@pengadaan_router.put("/pengadaan/{perolehan_id}/dokumen")
async def perbarui_dokumen(perolehan_id: str, payload: DokumenIn,
                           _user: dict = Depends(require_user)):
    """Perbarui checklist dokumen sumber (kunci di luar daftar diabaikan)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    wajib = set(DOKUMEN_PEROLEHAN.get(p.get("jenis"), ()))
    dokumen = {**(p.get("dokumen") or {}),
               **{k: bool(v) for k, v in payload.dokumen.items() if k in wajib}}
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"dokumen": dokumen, "updated_at": now}})
    p["dokumen"] = dokumen
    return _enrich(p)


@pengadaan_router.post("/pengadaan/{perolehan_id}/tautkan")
async def tautkan_barang(perolehan_id: str, payload: TautkanIn,
                         _user: dict = Depends(require_user)):
    """Tautkan/lepaskan baris barang ke aset master (cegah entri ganda)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    barang = p.get("barang") or []
    if payload.index >= len(barang):
        raise HTTPException(status_code=400, detail="Baris barang tidak ada")
    row = barang[payload.index]
    aid = str(payload.asset_id or "").strip()
    if aid:
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                    "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    else:
        row.update({"asset_id": "", "asset_code": "", "NUP": "",
                    "asset_name": ""})
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"barang": barang, "updated_at": now}})
    p["barang"] = barang
    return _enrich(p)


@pengadaan_router.delete("/pengadaan/{perolehan_id}")
async def hapus_perolehan(perolehan_id: str,
                          _admin: dict = Depends(require_admin)):
    """Hapus register perolehan salah input (admin)."""
    res = await db.pengadaan.delete_one({"id": perolehan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    return {"ok": True, "id": perolehan_id}
