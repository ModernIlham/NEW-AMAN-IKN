"""Master Referensi Ruangan — fondasi KIR/DBR & lokasi terstruktur (PMK 181/2016).

User login melihat daftar ruangan SATKERNYA; admin satker mengelola miliknya.
Tiap ruangan dapat menunjuk Penanggung Jawab Ruangan (dari registry pejabat).

ISOLASI SATKER (REVIEW-9 R9). Ruangan itu fisik dan melekat pada gedung satker,
jadi ia BUKAN referensi universal seperti kodefikasi/akun BAS: dokumen baru
distempel `kode_satker`, daftar di-scope, dan ubah/hapus di-guard. Keunikan
`kode_ruangan` pun berlaku PER SATKER — dua satker boleh sama-sama punya
"R-101"; memakai indeks/cek unik global akan menolak satker kedua sekaligus
membocorkan eksistensi kode milik satker lain.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user, require_admin_satker
from db import db
from shared_utils import (kode_satker_user, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)
from ruangan_utils import validate_ruangan

ruangan_router = APIRouter()

_PROJ = {"_id": 0}


class RuanganIn(BaseModel):
    kode_ruangan: str
    nama_ruangan: str
    gedung: Optional[str] = ""
    lantai: Optional[str] = ""
    penanggung_jawab_id: Optional[str] = ""
    penanggung_jawab_nama: Optional[str] = ""
    unit_kerja: Optional[str] = ""
    keterangan: Optional[str] = ""
    aktif: Optional[bool] = True


def _bersih(p: RuanganIn) -> dict:
    return {
        "kode_ruangan": str(p.kode_ruangan or "").strip(),
        "nama_ruangan": str(p.nama_ruangan or "").strip(),
        "gedung": str(p.gedung or "").strip(),
        "lantai": str(p.lantai or "").strip(),
        "penanggung_jawab_id": str(p.penanggung_jawab_id or "").strip(),
        "penanggung_jawab_nama": str(p.penanggung_jawab_nama or "").strip(),
        "unit_kerja": str(p.unit_kerja or "").strip(),
        "keterangan": str(p.keterangan or "").strip(),
        "aktif": bool(p.aktif) if p.aktif is not None else True,
    }


@ruangan_router.get("/ruangan")
async def list_ruangan(_user: dict = Depends(require_user)):
    """Daftar ruangan satker user (+ era lama tanpa stempel), urut kode."""
    items = await (db.ruangan.find(scope_query_field_satker(_user), _PROJ)
                   .sort("kode_ruangan", 1).to_list(5000))
    return {"items": items, "jumlah": len(items)}


@ruangan_router.post("/ruangan")
async def buat_ruangan(payload: RuanganIn, user: dict = Depends(require_admin_satker)):
    """Tambah ruangan (admin). Kode ruangan harus unik."""
    doc = _bersih(payload)
    errors = validate_ruangan(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    # Keunikan PER SATKER (bukan global) — lihat catatan modul.
    if await db.ruangan.find_one(
            scope_query_field_satker(user, {"kode_ruangan": doc["kode_ruangan"]}),
            {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Kode ruangan {doc['kode_ruangan']} sudah ada")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "created_at": now, "updated_at": now,
                "kode_satker": kode_satker_user(user)})
    await db.ruangan.insert_one(dict(doc))
    await log_audit("buat_ruangan", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah ruangan {doc['kode_ruangan']} — {doc['nama_ruangan']}")
    return {"ok": True, "id": doc["id"]}


@ruangan_router.put("/ruangan/{ruangan_id}")
async def ubah_ruangan(ruangan_id: str, payload: RuanganIn,
                       user: dict = Depends(require_admin)):
    """Ubah ruangan (admin). Kode ruangan tetap unik."""
    doc = _bersih(payload)
    errors = validate_ruangan(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    lama = await db.ruangan.find_one(
        {"id": ruangan_id}, {"_id": 0, "id": 1, "kode_satker": 1})
    if not lama:
        raise HTTPException(status_code=404, detail="Ruangan tidak ditemukan")
    await pastikan_akses_dok_satker(user, lama)  # isolasi satker (REVIEW-9 R9)
    bentrok = await db.ruangan.find_one(
        scope_query_field_satker(user, {"kode_ruangan": doc["kode_ruangan"],
                                        "id": {"$ne": ruangan_id}}), {"_id": 1})
    if bentrok:
        raise HTTPException(status_code=400, detail=f"Kode ruangan {doc['kode_ruangan']} sudah dipakai ruangan lain")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.ruangan.update_one({"id": ruangan_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ruangan tidak ditemukan")
    await log_audit("ubah_ruangan", "", ruangan_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah ruangan {doc['kode_ruangan']}")
    return {"ok": True, "id": ruangan_id}


@ruangan_router.delete("/ruangan/{ruangan_id}")
async def hapus_ruangan(ruangan_id: str, user: dict = Depends(require_admin)):
    """Hapus ruangan (admin)."""
    r = await db.ruangan.find_one(
        {"id": ruangan_id},
        {"_id": 0, "kode_ruangan": 1, "nama_ruangan": 1, "kode_satker": 1})
    if r:
        await pastikan_akses_dok_satker(user, r)  # isolasi satker (REVIEW-9 R9)
        import re as _re
        label = [x for x in (
            f"{r.get('kode_ruangan','')} — {r.get('nama_ruangan','')}".strip(" —"),
            str(r.get("kode_ruangan") or "").strip(),
            str(r.get("nama_ruangan") or "").strip()) if x]
        if label:
            # Scope aset ke satker user juga — tanpa itu ruangan satker A tak
            # bisa dihapus hanya karena satker B punya aset ber-lokasi bernama
            # sama (dan jumlahnya membocorkan volume aset satker lain).
            from shared_utils import scope_query_aset
            dipakai = await db.assets.count_documents(await scope_query_aset(user, {
                "dihapus": {"$ne": True},
                "$or": [{"location": {"$regex": f"^{_re.escape(v)}$", "$options": "i"}}
                        for v in label]}))
            if dipakai:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ruangan {r.get('kode_ruangan')} masih dipakai sebagai "
                           f"lokasi {dipakai} aset — pindahkan aset atau nonaktifkan "
                           f"ruangan, jangan dihapus (temuan #34).")
    res = await db.ruangan.delete_one({"id": ruangan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ruangan tidak ditemukan")
    await log_audit("hapus_ruangan", "", ruangan_id,
                    username=user.get("username", "system"), detail="Hapus ruangan")
    return {"ok": True, "id": ruangan_id}
