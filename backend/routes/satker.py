"""Master Satker — satker sebagai ENTITAS KELAS SATU (Mandat-2, M-SATKER).

Sebelumnya identitas satker hanya field flat pada kegiatan (kode_satker,
nama_satker, …) dan kop laporan sepenuhnya GLOBAL (`report_settings`), sehingga
aplikasi multi-satker ber-database bersama memakai satu kop untuk semua.
Koleksi `satker` menampung profil + KOP PER-SATKER; resolusi nilai laporan:

    kegiatan (paling spesifik) → master satker → report_settings global

Master diregistrasi otomatis dari kegiatan (sinkron) dan dirawat admin.
Koleksi ini KONFIGURASI: masuk RESET_KEEP (selamat reset), tetap ikut backup.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import log_audit

satker_router = APIRouter()

_PROJ = {"_id": 0}

# Field kop yang boleh dioverride per satker (subset report_settings + identitas)
FIELD_KOP_SATKER = (
    "nama_satker", "nama_unit_organisasi", "nama_sub_unit", "alamat",
    "tempat_laporan", "tembusan_laporan", "telepon", "email",
)


class SatkerIn(BaseModel):
    kode_satker: str
    nama_satker: str
    nama_unit_organisasi: str = ""
    nama_sub_unit: str = ""
    alamat: str = ""
    tempat_laporan: str = ""
    tembusan_laporan: str = ""
    telepon: str = ""
    email: str = ""
    eselon1: Optional[List[str]] = None
    aktif: bool = True


def _valid_kode(kode: str) -> str:
    k = str(kode or "").strip()
    if not k or len(k) > 30 or not re.fullmatch(r"[\w.\-]+", k):
        raise HTTPException(status_code=400,
                            detail="Kode satker wajib (huruf/angka/titik/strip, maks 30)")
    return k


@satker_router.get("/satker")
async def daftar_satker(_user: dict = Depends(require_user)):
    """Master satker + jumlah kegiatan per satker (agar terlihat mana yang
    dipakai). Termasuk satker yang BELUM terdaftar di master tetapi muncul di
    kegiatan (status 'belum terdaftar') — kandidat sinkron 1-klik."""
    master = {m["kode_satker"]: m async for m in db.satker.find({}, _PROJ)}
    pakai = {}
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"}, "n": {"$sum": 1}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        pakai[g["_id"]] = g
    items = []
    for kode, m in master.items():
        items.append({**m, "jumlah_kegiatan": pakai.get(kode, {}).get("n", 0),
                      "terdaftar": True})
    for kode, g in pakai.items():
        if kode not in master:
            items.append({"kode_satker": kode, "nama_satker": g.get("nama") or "",
                          "eselon1": g.get("eselon1") or [], "aktif": True,
                          "jumlah_kegiatan": g.get("n", 0), "terdaftar": False})
    items.sort(key=lambda x: str(x.get("kode_satker")))
    return {"items": items, "jumlah": len(items),
            "field_kop": list(FIELD_KOP_SATKER)}


@satker_router.get("/satker/{kode}")
async def detail_satker(kode: str, _user: dict = Depends(require_user)):
    doc = await db.satker.find_one({"kode_satker": kode}, _PROJ)
    if not doc:
        raise HTTPException(status_code=404, detail="Satker belum terdaftar di master")
    return doc


@satker_router.put("/satker/{kode}")
async def simpan_satker(kode: str, payload: SatkerIn,
                        admin: dict = Depends(require_admin)):
    """Daftarkan/perbarui profil & kop satu satker (admin). Upsert by kode —
    kode pada path menang atas body (path = identitas)."""
    k = _valid_kode(kode)
    if not str(payload.nama_satker or "").strip():
        raise HTTPException(status_code=400, detail="Nama satker wajib diisi")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "kode_satker": k,
        "nama_satker": payload.nama_satker.strip(),
        "eselon1": [str(e).strip() for e in (payload.eselon1 or []) if str(e).strip()],
        "aktif": bool(payload.aktif),
        "updated_at": now, "updated_by": admin.get("username", "system"),
    }
    for f in FIELD_KOP_SATKER:
        if f in ("nama_satker",):
            continue
        doc[f] = str(getattr(payload, f, "") or "").strip()
    await db.satker.update_one(
        {"kode_satker": k},
        {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True)
    await log_audit("simpan_satker", "", k, username=admin.get("username", "system"),
                    detail=f"Master satker {k} — {doc['nama_satker']}")
    return {"ok": True, "kode_satker": k}


@satker_router.delete("/satker/{kode}")
async def hapus_satker(kode: str, admin: dict = Depends(require_admin)):
    """Hapus satker dari master — DITOLAK bila masih dipakai kegiatan
    (hapus/madah kegiatannya dulu; master bukan tempat menghilangkan jejak)."""
    n = await db.inventory_activities.count_documents({"kode_satker": kode})
    if n:
        raise HTTPException(status_code=409,
                            detail=f"Satker dipakai {n} kegiatan — tidak dapat dihapus")
    res = await db.satker.delete_one({"kode_satker": kode})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Satker tidak ditemukan")
    await log_audit("hapus_satker", "", kode,
                    username=admin.get("username", "system"),
                    detail=f"Hapus master satker {kode}")
    return {"ok": True}


@satker_router.post("/satker/sinkron")
async def sinkron_satker(admin: dict = Depends(require_admin)):
    """Registrasi otomatis: setiap satker yang muncul di kegiatan tetapi belum
    ada di master → didaftarkan (kode+nama+eselon1). Idempoten; profil kop
    yang sudah diisi admin TIDAK ditimpa."""
    now = datetime.now(timezone.utc).isoformat()
    baru = 0
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"},
                    "alamat": {"$first": "$alamat_satker"}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        ada = await db.satker.find_one({"kode_satker": g["_id"]}, {"_id": 1})
        if ada:
            continue
        await db.satker.insert_one({
            "id": str(uuid.uuid4()), "kode_satker": g["_id"],
            "nama_satker": str(g.get("nama") or "").strip(),
            "nama_unit_organisasi": "", "nama_sub_unit": "",
            "alamat": str(g.get("alamat") or "").strip(),
            "tempat_laporan": "", "tembusan_laporan": "",
            "telepon": "", "email": "",
            "eselon1": g.get("eselon1") or [], "aktif": True,
            "created_at": now, "updated_at": now,
            "updated_by": admin.get("username", "system"),
        })
        baru += 1
    await log_audit("sinkron_satker", "", "master",
                    username=admin.get("username", "system"),
                    detail=f"Sinkron master satker: {baru} satker baru terdaftar")
    return {"ok": True, "baru": baru}
