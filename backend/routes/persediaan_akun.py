"""Referensi Akun Persediaan (sub-kelompok → akun neraca 1171xx) — kelola satker.

Evaluasi #3: laporan Posisi Persediaan memetakan sub-kelompok (5 digit) →
akun neraca via default 117111 + override `db.persediaan_akun`. Modul ini
menyediakan endpoint mengelola override tersebut (admin) + katalog akun 1171xx
sebagai pilihan. Semua user login dapat melihat.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from persediaan_akun_utils import (
    AKUN_PERSEDIAAN_DEFAULT, AKUN_PERSEDIAAN_UTAMA, validate_akun_persediaan,
)

persediaan_akun_router = APIRouter()


class PersediaanAkunIn(BaseModel):
    sub_kelompok: str
    akun: str
    uraian: str = ""


def _validate_sub_kelompok(sub: str):
    """5 digit angka diawali '1' (domain persediaan). Kembalikan (sub_bersih, error)."""
    s = str(sub or "").strip()
    if not (s.isdigit() and len(s) == 5 and s.startswith("1")):
        return s, "Sub-kelompok harus 5 digit angka diawali '1' (persediaan), mis. 10101"
    return s, ""


@persediaan_akun_router.get("/persediaan-akun")
async def list_persediaan_akun(_user: dict = Depends(require_user)):
    """Katalog akun 1171xx + daftar override sub-kelompok satker (default 117111)."""
    overrides = []
    async for m in db.persediaan_akun.find({}, {"_id": 0}):
        overrides.append({
            "sub_kelompok": m.get("sub_kelompok", ""),
            "akun": m.get("akun", ""),
            "uraian": m.get("uraian", "") or AKUN_PERSEDIAAN_DEFAULT.get(m.get("akun", ""), ""),
        })
    overrides.sort(key=lambda x: x["sub_kelompok"])
    katalog = [{"akun": k, "uraian": v} for k, v in AKUN_PERSEDIAAN_DEFAULT.items()]
    return {
        "katalog": katalog,
        "overrides": overrides,
        "default_akun": AKUN_PERSEDIAAN_UTAMA,
        "default_uraian": AKUN_PERSEDIAAN_DEFAULT.get(AKUN_PERSEDIAAN_UTAMA, ""),
        "jumlah_override": len(overrides),
    }


@persediaan_akun_router.post("/persediaan-akun")
async def upsert_persediaan_akun(payload: PersediaanAkunIn,
                                 _admin: dict = Depends(require_admin)):
    """Tambah/ubah pemetaan sub-kelompok → akun neraca (admin; menimpa default)."""
    sub, err_sub = _validate_sub_kelompok(payload.sub_kelompok)
    if err_sub:
        raise HTTPException(status_code=400, detail=err_sub)
    akun = str(payload.akun or "").strip()
    errors = validate_akun_persediaan(akun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    uraian = str(payload.uraian or "").strip() or AKUN_PERSEDIAAN_DEFAULT.get(akun, "")
    now = datetime.now(timezone.utc).isoformat()
    await db.persediaan_akun.update_one(
        {"sub_kelompok": sub},
        {"$set": {"sub_kelompok": sub, "akun": akun, "uraian": uraian, "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True, "sub_kelompok": sub, "akun": akun}


@persediaan_akun_router.delete("/persediaan-akun/{sub_kelompok}")
async def hapus_persediaan_akun(sub_kelompok: str,
                                _admin: dict = Depends(require_admin)):
    """Hapus override (kembali ke default 117111)."""
    res = await db.persediaan_akun.delete_one({"sub_kelompok": str(sub_kelompok).strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Override sub-kelompok tidak ditemukan")
    return {"ok": True, "sub_kelompok": str(sub_kelompok).strip()}
