"""Referensi Pejabat Penatausahaan BMN — registry + penanda tangan aktif.

PMK 181/PMK.06/2016. Menyediakan daftar pejabat (KPB, Petugas Penatausahaan/
Operator SIMAK-BMN, Pengurus Barang, PPK, dll.) beserta SK penunjukan & masa
berlaku, agar dokumen resmi (KIB/BAST/LBKP/penghapusan) memakai pejabat yang
benar & masih berlaku. Slice fondasi: CRUD + endpoint "aktif per peran".
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import log_audit
from pejabat_utils import (
    JENIS_PELAKSANA, PERAN_PEJABAT, PERAN_PEJABAT_META, STATUS_KEPEGAWAIAN,
    UNIT_AKUNTANSI, peran_penyerah_bast, pejabat_aktif_untuk_peran,
    validate_pejabat,
)

pejabat_router = APIRouter()

_PROJ = {"_id": 0}


class PejabatIn(BaseModel):
    nama: str
    nip: Optional[str] = ""
    jabatan: Optional[str] = ""
    pangkat_golongan: Optional[str] = ""
    status_kepegawaian: Optional[str] = ""
    unit_kerja: Optional[str] = ""
    no_hp: Optional[str] = ""
    email: Optional[str] = ""
    peran: List[str] = []
    # Rangkap jabatan struktural sementara: "" | "plt" | "plh" (Pelaksana
    # Tugas / Pelaksana Harian). Bila diisi, TTD dokumen memakai awalan
    # "Plt./Plh." di depan jabatan dengan nama & NIP pejabat pelaksana.
    jenis_pelaksana: Optional[str] = ""
    unit_akuntansi: Optional[str] = ""
    sk_nomor: Optional[str] = ""
    sk_tanggal: Optional[str] = ""
    berlaku_mulai: Optional[str] = ""
    berlaku_selesai: Optional[str] = ""
    aktif: Optional[bool] = True
    keterangan: Optional[str] = ""


def _bersih(p: PejabatIn) -> dict:
    return {
        "nama": str(p.nama or "").strip(),
        "nip": str(p.nip or "").strip(),
        "jabatan": str(p.jabatan or "").strip(),
        "pangkat_golongan": str(p.pangkat_golongan or "").strip(),
        "status_kepegawaian": str(p.status_kepegawaian or "").strip(),
        "unit_kerja": str(p.unit_kerja or "").strip(),
        "no_hp": str(p.no_hp or "").strip(),
        "email": str(p.email or "").strip(),
        "peran": [str(x).strip() for x in (p.peran or []) if str(x).strip()],
        "jenis_pelaksana": str(p.jenis_pelaksana or "").strip().lower(),
        "unit_akuntansi": str(p.unit_akuntansi or "").strip(),
        "sk_nomor": str(p.sk_nomor or "").strip(),
        "sk_tanggal": str(p.sk_tanggal or "").strip()[:10],
        "berlaku_mulai": str(p.berlaku_mulai or "").strip()[:10],
        "berlaku_selesai": str(p.berlaku_selesai or "").strip()[:10],
        "aktif": bool(p.aktif) if p.aktif is not None else True,
        "keterangan": str(p.keterangan or "").strip(),
    }


@pejabat_router.get("/pejabat/referensi")
async def referensi_pejabat(_user: dict = Depends(require_user)):
    """Referensi peran, status kepegawaian & unit akuntansi (untuk dropdown UI).

    Tiap peran disertai metadata (domain rezim bmn/bmd, peran pada BAST, dan
    keterangan berbasis regulasi) agar UI dapat menjelaskan perbedaan peran &
    menyaring penanda tangan BAST. `peran_penyerah_bast` = kode peran yang
    layak jadi 'yang menyerahkan' pada serah terima internal.
    """
    return {
        "peran": [{"kode": k, "uraian": v, **PERAN_PEJABAT_META.get(k, {})}
                  for k, v in PERAN_PEJABAT.items()],
        "peran_penyerah_bast": peran_penyerah_bast(),
        "status_kepegawaian": [{"kode": k, "uraian": v} for k, v in STATUS_KEPEGAWAIAN.items()],
        "jenis_pelaksana": [{"kode": k, "uraian": v} for k, v in JENIS_PELAKSANA.items()],
        "unit_akuntansi": [{"kode": k, **v} for k, v in UNIT_AKUNTANSI.items()],
    }


@pejabat_router.get("/pejabat")
async def list_pejabat(_user: dict = Depends(require_user)):
    """Daftar pejabat penatausahaan (semua)."""
    items = await db.pejabat.find({}, _PROJ).sort("nama", 1).to_list(2000)
    return {"items": items, "jumlah": len(items)}


@pejabat_router.get("/pejabat/aktif")
async def pejabat_aktif(
    peran: str = Query(..., description="kode peran, mis. kuasa_pengguna_barang"),
    per_tanggal: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Pejabat yang berlaku & memegang `peran` pada tanggal tertentu (SK terbaru)."""
    if peran not in PERAN_PEJABAT:
        raise HTTPException(status_code=400, detail=f"Peran tidak dikenal: {peran}")
    if not per_tanggal:
        per_tanggal = datetime.now(timezone.utc).date().isoformat()
    semua = await db.pejabat.find({}, _PROJ).to_list(2000)
    pj = pejabat_aktif_untuk_peran(semua, peran, per_tanggal)
    return {"peran": peran, "per_tanggal": per_tanggal, "pejabat": pj}


async def _nip_bentrok_pejabat(nip: str, kecuali_id: str = "") -> bool:
    """True bila NIP sudah dipakai pejabat LAIN di registry (dedup)."""
    nip = str(nip or "").strip()
    if not nip:
        return False
    q = {"nip": nip}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    return bool(await db.pejabat.find_one(q, {"_id": 1}))


@pejabat_router.post("/pejabat")
async def buat_pejabat(payload: PejabatIn, user: dict = Depends(require_admin)):
    """Tambah pejabat (admin)."""
    doc = _bersih(payload)
    errors = validate_pejabat(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if await _nip_bentrok_pejabat(doc["nip"]):
        raise HTTPException(status_code=409,
                            detail=f"NIP {doc['nip']} sudah terdaftar pada pejabat lain")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "created_at": now, "updated_at": now})
    await db.pejabat.insert_one(dict(doc))
    await log_audit("buat_pejabat", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah pejabat {doc['nama']}")
    return {"ok": True, "id": doc["id"]}


@pejabat_router.put("/pejabat/{pejabat_id}")
async def ubah_pejabat(pejabat_id: str, payload: PejabatIn,
                       user: dict = Depends(require_admin)):
    """Ubah pejabat (admin)."""
    doc = _bersih(payload)
    errors = validate_pejabat(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if await _nip_bentrok_pejabat(doc["nip"], kecuali_id=pejabat_id):
        raise HTTPException(status_code=409,
                            detail=f"NIP {doc['nip']} sudah terdaftar pada pejabat lain")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pejabat.update_one({"id": pejabat_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await log_audit("ubah_pejabat", "", pejabat_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah pejabat {doc['nama']}")
    return {"ok": True, "id": pejabat_id}


@pejabat_router.delete("/pejabat/{pejabat_id}")
async def hapus_pejabat(pejabat_id: str, user: dict = Depends(require_admin)):
    """Hapus pejabat (admin)."""
    res = await db.pejabat.delete_one({"id": pejabat_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await log_audit("hapus_pejabat", "", pejabat_id,
                    username=user.get("username", "system"),
                    detail="Hapus pejabat")
    return {"ok": True, "id": pejabat_id}
