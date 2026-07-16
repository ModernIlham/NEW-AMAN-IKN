"""Master Pegawai — data kepegawaian menyeluruh satker (adopsi SIMAN-G).

BERBEDA dari Referensi Pejabat (khusus pejabat penatausahaan/penanda tangan):
master ini menampung SELURUH pegawai + unit kerjanya, sebagai rujukan lintas
modul. Semua user login dapat melihat; admin mengelola (CRUD). NIP unik bila
diisi. Pola sama dengan referensi pejabat/ruangan.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import log_audit
from pejabat_utils import STATUS_KEPEGAWAIAN
from pegawai_utils import (
    JENIS_JABATAN, JENIS_KELAMIN, STATUS_PEGAWAI,
    kelompok_unit_kerja, validate_pegawai,
)

pegawai_router = APIRouter()

_PROJ = {"_id": 0}


class PegawaiIn(BaseModel):
    nama: str
    nip: Optional[str] = ""
    gelar_depan: Optional[str] = ""
    gelar_belakang: Optional[str] = ""
    jenis_kelamin: Optional[str] = ""
    tempat_lahir: Optional[str] = ""
    tanggal_lahir: Optional[str] = ""
    status_kepegawaian: Optional[str] = ""
    pangkat_golongan: Optional[str] = ""
    jabatan: Optional[str] = ""
    jenis_jabatan: Optional[str] = ""
    eselon: Optional[str] = ""
    unit_kerja: Optional[str] = ""
    unit_organisasi: Optional[str] = ""
    npwp: Optional[str] = ""
    pendidikan_terakhir: Optional[str] = ""
    no_hp: Optional[str] = ""
    email: Optional[str] = ""
    alamat: Optional[str] = ""
    tmt_jabatan: Optional[str] = ""
    status: Optional[str] = "aktif"
    keterangan: Optional[str] = ""


def _bersih(p: PegawaiIn) -> dict:
    return {
        "nama": str(p.nama or "").strip(),
        "nip": str(p.nip or "").strip(),
        "gelar_depan": str(p.gelar_depan or "").strip(),
        "gelar_belakang": str(p.gelar_belakang or "").strip(),
        "jenis_kelamin": str(p.jenis_kelamin or "").strip().upper(),
        "tempat_lahir": str(p.tempat_lahir or "").strip(),
        "tanggal_lahir": str(p.tanggal_lahir or "").strip()[:10],
        "status_kepegawaian": str(p.status_kepegawaian or "").strip(),
        "pangkat_golongan": str(p.pangkat_golongan or "").strip(),
        "jabatan": str(p.jabatan or "").strip(),
        "jenis_jabatan": str(p.jenis_jabatan or "").strip(),
        "eselon": str(p.eselon or "").strip(),
        "unit_kerja": str(p.unit_kerja or "").strip(),
        "unit_organisasi": str(p.unit_organisasi or "").strip(),
        "npwp": str(p.npwp or "").strip(),
        "pendidikan_terakhir": str(p.pendidikan_terakhir or "").strip(),
        "no_hp": str(p.no_hp or "").strip(),
        "email": str(p.email or "").strip(),
        "alamat": str(p.alamat or "").strip(),
        "tmt_jabatan": str(p.tmt_jabatan or "").strip()[:10],
        "status": str(p.status or "aktif").strip() or "aktif",
        "keterangan": str(p.keterangan or "").strip(),
    }


async def _nip_bentrok(nip: str, kecuali_id: str = "") -> bool:
    """True bila NIP sudah dipakai pegawai lain (NIP kosong tak pernah bentrok)."""
    if not nip:
        return False
    q = {"nip": nip}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    return await db.pegawai.find_one(q, _PROJ) is not None


@pegawai_router.get("/pegawai/referensi")
async def referensi_pegawai(_user: dict = Depends(require_user)):
    """Referensi pilihan (untuk dropdown UI)."""
    return {
        "jenis_kelamin": [{"kode": k, "uraian": v} for k, v in JENIS_KELAMIN.items()],
        "status_kepegawaian": [{"kode": k, "uraian": v} for k, v in STATUS_KEPEGAWAIAN.items()],
        "jenis_jabatan": [{"kode": k, "uraian": v} for k, v in JENIS_JABATAN.items()],
        "status": [{"kode": k, "uraian": v} for k, v in STATUS_PEGAWAI.items()],
    }


@pegawai_router.get("/pegawai/rekap-unit")
async def rekap_unit_pegawai(_user: dict = Depends(require_user)):
    """Rekap jumlah pegawai per unit kerja (untuk ringkasan)."""
    semua = await db.pegawai.find({}, _PROJ).to_list(10000)
    kelompok = kelompok_unit_kerja(semua)
    return {
        "unit": [{"unit_kerja": g["unit_kerja"], "jumlah": g["jumlah"]} for g in kelompok],
        "jumlah_pegawai": len(semua),
        "jumlah_unit": len(kelompok),
    }


@pegawai_router.get("/pegawai")
async def list_pegawai(_user: dict = Depends(require_user)):
    """Daftar seluruh pegawai (terurut nama)."""
    items = await db.pegawai.find({}, _PROJ).sort("nama", 1).to_list(10000)
    return {"items": items, "jumlah": len(items)}


@pegawai_router.post("/pegawai")
async def buat_pegawai(payload: PegawaiIn, user: dict = Depends(require_admin)):
    """Tambah pegawai (admin)."""
    doc = _bersih(payload)
    errors = validate_pegawai(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if await _nip_bentrok(doc["nip"]):
        raise HTTPException(status_code=400, detail=f"NIP {doc['nip']} sudah terdaftar")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "created_at": now, "updated_at": now})
    await db.pegawai.insert_one(dict(doc))
    await log_audit("buat_pegawai", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah pegawai {doc['nama']}")
    return {"ok": True, "id": doc["id"]}


@pegawai_router.put("/pegawai/{pegawai_id}")
async def ubah_pegawai(pegawai_id: str, payload: PegawaiIn,
                       user: dict = Depends(require_admin)):
    """Ubah pegawai (admin)."""
    doc = _bersih(payload)
    errors = validate_pegawai(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if await _nip_bentrok(doc["nip"], kecuali_id=pegawai_id):
        raise HTTPException(status_code=400, detail=f"NIP {doc['nip']} sudah terdaftar")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pegawai.update_one({"id": pegawai_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")
    await log_audit("ubah_pegawai", "", pegawai_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah pegawai {doc['nama']}")
    return {"ok": True, "id": pegawai_id}


@pegawai_router.delete("/pegawai/{pegawai_id}")
async def hapus_pegawai(pegawai_id: str, user: dict = Depends(require_admin)):
    """Hapus pegawai (admin). Ditolak bila NIP-nya masih dipakai aset (temuan #34)."""
    peg = await db.pegawai.find_one({"id": pegawai_id}, {"_id": 0, "nip": 1, "nama": 1})
    if peg and str(peg.get("nip") or "").strip():
        dipakai = await db.assets.count_documents(
            {"pengguna_nip": str(peg["nip"]).strip(), "dihapus": {"$ne": True}})
        if dipakai:
            raise HTTPException(
                status_code=409,
                detail=f"Pegawai {peg.get('nama')} (NIP {peg['nip']}) masih tercatat "
                       f"sebagai pengguna pada {dipakai} aset — pindahkan aset atau "
                       f"ubah status pegawai menjadi nonaktif, jangan dihapus.")
    res = await db.pegawai.delete_one({"id": pegawai_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")
    await log_audit("hapus_pegawai", "", pegawai_id,
                    username=user.get("username", "system"),
                    detail="Hapus pegawai")
    return {"ok": True, "id": pegawai_id}
