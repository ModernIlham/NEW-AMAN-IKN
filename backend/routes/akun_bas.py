"""Referensi Akun Neraca (BAS) per golongan BMN — merged default + override satker.

Semua user login melihat pemetaan golongan → akun neraca; admin menimpa per
golongan dari Lampiran BAS (default riset ditandai perlu-verifikasi). Pola sama
dengan referensi masa manfaat (#107).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from akun_bas_utils import AKUN_NERACA_DEFAULT, validate_akun_bas

akun_bas_router = APIRouter()


class AkunBasIn(BaseModel):
    golongan: str
    akun: str
    uraian: str = ""


async def _peta_akun():
    """Peta golongan → {akun, uraian}: entri satker (DB) menimpa default riset."""
    peta = {g: dict(v) for g, v in AKUN_NERACA_DEFAULT.items()}
    entri = {}
    async for m in db.akun_bas.find({}, {"_id": 0}):
        peta[m["golongan"]] = {"akun": m.get("akun", ""), "uraian": m.get("uraian", "")}
        entri[m["golongan"]] = m
    return peta, entri


@akun_bas_router.get("/akun-bas")
async def list_akun_bas(_user: dict = Depends(require_user)):
    """Pemetaan golongan → akun neraca (default riset ditimpa entri satker)."""
    _, entri = await _peta_akun()
    items = []
    for g in sorted(AKUN_NERACA_DEFAULT):
        if g in entri:
            m = entri[g]
            items.append({"golongan": g, "akun": m.get("akun", ""),
                          "uraian": m.get("uraian", ""), "sumber": "input satker"})
        else:
            d = AKUN_NERACA_DEFAULT[g]
            items.append({"golongan": g, "akun": d["akun"], "uraian": d["uraian"],
                          "sumber": "default riset (verifikasi Lampiran BAS)"})
    return {"items": items, "jumlah": len(items)}


@akun_bas_router.post("/akun-bas")
async def upsert_akun_bas(payload: AkunBasIn, _admin: dict = Depends(require_admin)):
    """Tambah/ubah akun neraca satu golongan (admin; menimpa default)."""
    errors = validate_akun_bas(payload.golongan, payload.akun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    g = payload.golongan.strip()
    await db.akun_bas.update_one(
        {"golongan": g},
        {"$set": {"golongan": g, "akun": payload.akun.strip(),
                  "uraian": str(payload.uraian or "").strip(), "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True, "golongan": g, "akun": payload.akun.strip()}


@akun_bas_router.delete("/akun-bas/{golongan}")
async def hapus_akun_bas(golongan: str, _admin: dict = Depends(require_admin)):
    """Hapus entri satker (kembali ke default riset)."""
    res = await db.akun_bas.delete_one({"golongan": golongan.strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404,
                            detail="Entri satker tidak ditemukan (default riset tidak bisa dihapus)")
    return {"ok": True, "golongan": golongan.strip()}
