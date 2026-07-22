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
from shared_utils import (log_audit, kode_satker_user, scope_query_field_satker,
                          pastikan_akses_dok_satker)
from pejabat_utils import (
    JENIS_PELAKSANA, PERAN_PEJABAT, PERAN_PEJABAT_META, STATUS_KEPEGAWAIAN,
    UNIT_AKUNTANSI, peran_penyerah_bast, pejabat_aktif_untuk_peran,
    validate_pejabat,
)

pejabat_router = APIRouter()

_PROJ = {"_id": 0}


class PejabatIn(BaseModel):
    nama: str
    # Gelar akademik terpisah dari nama; ditampilkan pada TTD dokumen bila
    # `pakai_gelar` aktif (nama disimpan tanpa gelar).
    gelar_depan: Optional[str] = ""
    gelar_belakang: Optional[str] = ""
    pakai_gelar: Optional[bool] = False
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
    # Penghubung isolasi satker (M-SCOPE): dokumen resmi satker ini hanya boleh
    # ditandatangani pejabat satker ini (atau pejabat era-lama tanpa kode).
    kode_satker: Optional[str] = ""
    sk_nomor: Optional[str] = ""
    sk_tanggal: Optional[str] = ""
    berlaku_mulai: Optional[str] = ""
    berlaku_selesai: Optional[str] = ""
    aktif: Optional[bool] = True
    keterangan: Optional[str] = ""


def _bersih(p: PejabatIn) -> dict:
    return {
        "nama": str(p.nama or "").strip(),
        "gelar_depan": str(p.gelar_depan or "").strip(),
        "gelar_belakang": str(p.gelar_belakang or "").strip(),
        "pakai_gelar": bool(p.pakai_gelar) if p.pakai_gelar is not None else False,
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
        "kode_satker": str(p.kode_satker or "").strip(),
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
async def list_pejabat(user: dict = Depends(require_user)):
    """Daftar pejabat penatausahaan (ter-scope satker user + era-lama tanpa kode)."""
    q = scope_query_field_satker(user, {})
    items = await db.pejabat.find(q, _PROJ).sort("nama", 1).to_list(2000)
    return {"items": items, "jumlah": len(items)}


@pejabat_router.get("/pejabat/aktif")
async def pejabat_aktif(
    peran: str = Query(..., description="kode peran, mis. kuasa_pengguna_barang"),
    per_tanggal: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: dict = Depends(require_user),
):
    """Pejabat yang berlaku & memegang `peran` pada tanggal tertentu (SK terbaru),
    ter-scope satker user (+ pejabat era-lama tanpa kode)."""
    if peran not in PERAN_PEJABAT:
        raise HTTPException(status_code=400, detail=f"Peran tidak dikenal: {peran}")
    if not per_tanggal:
        per_tanggal = datetime.now(timezone.utc).date().isoformat()
    semua = await db.pejabat.find(scope_query_field_satker(user, {}), _PROJ).to_list(2000)
    pj = pejabat_aktif_untuk_peran(semua, peran, per_tanggal)
    return {"peran": peran, "per_tanggal": per_tanggal, "pejabat": pj}


async def _nip_bentrok_pejabat(nip: str, kecuali_id: str = "", kode: str = "") -> bool:
    """True bila NIP sudah dipakai pejabat LAIN DI SATKER SAMA (dedup per-satker;
    NIP boleh sama antar-satker). Pejabat era-lama tanpa kode ikut dicek."""
    nip = str(nip or "").strip()
    if not nip:
        return False
    q = {"nip": nip}
    if kode:
        q["kode_satker"] = {"$in": [kode, "", None]}
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
    # Admin terikat satker: dipaksa satkernya (isolasi M-SCOPE); super-admin
    # ("") boleh mengisi kode_satker eksplisit dari form.
    kode = kode_satker_user(user)
    doc["kode_satker"] = kode or doc.get("kode_satker", "")
    if await _nip_bentrok_pejabat(doc["nip"], kode=doc["kode_satker"]):
        raise HTTPException(status_code=409,
                            detail=f"NIP {doc['nip']} sudah terdaftar pada pejabat lain")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "created_at": now, "updated_at": now})
    await db.pejabat.insert_one(dict(doc))
    await log_audit("buat_pejabat", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah pejabat {doc['nama']}",
                    kode_satker=str(doc.get("kode_satker") or ""))
    return {"ok": True, "id": doc["id"]}


@pejabat_router.put("/pejabat/{pejabat_id}")
async def ubah_pejabat(pejabat_id: str, payload: PejabatIn,
                       user: dict = Depends(require_admin)):
    """Ubah pejabat (admin, ter-scope satker)."""
    existing = await db.pejabat.find_one({"id": pejabat_id}, _PROJ)
    if not existing:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await pastikan_akses_dok_satker(user, existing)  # 403 bila milik satker lain
    doc = _bersih(payload)
    errors = validate_pejabat(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    # Satker dipertahankan/dipaksa: admin terikat → satkernya; super-admin →
    # nilai form bila diisi, jika tidak pertahankan yang lama.
    kode = kode_satker_user(user)
    doc["kode_satker"] = kode or doc.get("kode_satker") or str(existing.get("kode_satker") or "")
    if await _nip_bentrok_pejabat(doc["nip"], kecuali_id=pejabat_id, kode=doc["kode_satker"]):
        raise HTTPException(status_code=409,
                            detail=f"NIP {doc['nip']} sudah terdaftar pada pejabat lain")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pejabat.update_one({"id": pejabat_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await log_audit("ubah_pejabat", "", pejabat_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah pejabat {doc['nama']}",
                    kode_satker=str(doc.get("kode_satker") or ""))
    return {"ok": True, "id": pejabat_id}


@pejabat_router.delete("/pejabat/{pejabat_id}")
async def hapus_pejabat(pejabat_id: str, user: dict = Depends(require_admin)):
    """Hapus pejabat (admin, ter-scope satker)."""
    existing = await db.pejabat.find_one({"id": pejabat_id}, _PROJ)
    if not existing:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await pastikan_akses_dok_satker(user, existing)  # 403 bila milik satker lain
    res = await db.pejabat.delete_one({"id": pejabat_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan")
    await log_audit("hapus_pejabat", "", pejabat_id,
                    username=user.get("username", "system"),
                    detail="Hapus pejabat")
    return {"ok": True, "id": pejabat_id}
