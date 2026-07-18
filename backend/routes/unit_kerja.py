"""Master Unit Kerja berjenjang (Eselon I–V) — adopsi KERJA-BARENG.

Menyediakan struktur organisasi hierarkis utk pilihan bertingkat di form
pegawai & rekap laporan BMN per unit resmi. Semua user melihat; admin
mengelola. Ter-scope satker (pola master lain). Endpoint bangun-dari-pegawai
menderivasi master otomatis dari eselon1–5 data pegawai yang sudah ada/impor.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import kode_satker_user, log_audit, scope_query_field_satker
from unit_kerja_utils import unit_dari_pegawai, validate_unit

unit_kerja_router = APIRouter()

_PROJ = {"_id": 0}


class UnitIn(BaseModel):
    nama_unit: str
    eselon: str
    parent_id: Optional[str] = ""


@unit_kerja_router.get("/unit-kerja")
async def daftar_unit_kerja(_user: dict = Depends(require_user)):
    """Seluruh unit kerja satker (terurut eselon lalu nama)."""
    items = await db.unit_kerja.find(
        scope_query_field_satker(_user), _PROJ).to_list(5000)
    items.sort(key=lambda u: (str(u.get("eselon")), str(u.get("nama_unit", "")).lower()))
    return {"items": items, "jumlah": len(items)}


@unit_kerja_router.post("/unit-kerja")
async def buat_unit_kerja(payload: UnitIn, user: dict = Depends(require_admin)):
    """Tambah unit (admin). Eselon >1 wajib induk eselon tepat di atasnya."""
    doc = {"nama_unit": str(payload.nama_unit or "").strip(),
           "eselon": str(payload.eselon or "").strip(),
           "parent_id": str(payload.parent_id or "").strip()}
    induk = None
    if doc["parent_id"]:
        induk = await db.unit_kerja.find_one({"id": doc["parent_id"]}, _PROJ)
        if not induk:
            raise HTTPException(status_code=400, detail="Induk tidak ditemukan")
        if doc["eselon"].isdigit() and \
                str(induk.get("eselon")) != str(int(doc["eselon"]) - 1):
            raise HTTPException(
                status_code=400,
                detail=f"Induk unit Eselon {doc['eselon']} harus Eselon "
                       f"{int(doc['eselon']) - 1}")
    errors = validate_unit(doc, punya_induk=bool(induk))
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    kode = kode_satker_user(user)
    dup = await db.unit_kerja.find_one(
        {"nama_unit": doc["nama_unit"], "eselon": doc["eselon"],
         "parent_id": doc["parent_id"] or None,
         "kode_satker": {"$in": [kode, "", None]}}, _PROJ)
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Unit {doc['nama_unit']} sudah terdaftar")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "parent_id": doc["parent_id"] or None,
                "kode_satker": kode, "created_at": now, "updated_at": now})
    await db.unit_kerja.insert_one(dict(doc))
    await log_audit("buat_unit_kerja", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah unit Eselon {doc['eselon']}: {doc['nama_unit']}")
    return {"ok": True, "id": doc["id"]}


@unit_kerja_router.delete("/unit-kerja/{unit_id}")
async def hapus_unit_kerja(unit_id: str, user: dict = Depends(require_admin)):
    """Hapus unit (admin). Ditolak bila masih punya anak atau dipakai pegawai."""
    u = await db.unit_kerja.find_one({"id": unit_id}, _PROJ)
    if not u:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(user, u)
    anak = await db.unit_kerja.count_documents({"parent_id": unit_id})
    if anak:
        raise HTTPException(status_code=409, detail=(
            f"Unit masih punya {anak} sub-unit — hapus/pindahkan dulu"))
    nama = str(u.get("nama_unit") or "")
    es = str(u.get("eselon") or "1")
    dipakai = await db.pegawai.count_documents({f"eselon{es}": nama})
    if dipakai:
        raise HTTPException(status_code=409, detail=(
            f"Unit dipakai {dipakai} pegawai — perbarui unit pegawai dulu"))
    await db.unit_kerja.delete_one({"id": unit_id})
    await log_audit("hapus_unit_kerja", "", unit_id,
                    username=user.get("username", "system"),
                    detail=f"Hapus unit Eselon {es}: {nama}")
    return {"ok": True, "id": unit_id}


@unit_kerja_router.post("/unit-kerja/bangun-dari-pegawai")
async def bangun_dari_pegawai(user: dict = Depends(require_admin)):
    """Bangun/lengkapi master unit OTOMATIS dari jalur eselon1–5 seluruh
    pegawai satker (idempoten — hanya menambah yang belum ada). Berguna
    pasca impor massal: master langsung terisi tanpa entri manual."""
    kode = kode_satker_user(user)
    pegawai = await db.pegawai.find(
        scope_query_field_satker(user),
        {"_id": 0, "eselon1": 1, "eselon2": 1, "eselon3": 1,
         "eselon4": 1, "eselon5": 1}).to_list(20000)
    kandidat = unit_dari_pegawai(pegawai)
    ada = await db.unit_kerja.find(
        scope_query_field_satker(user),
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1, "parent_id": 1}
    ).to_list(5000)
    # peta (eselon, nama) → id utk resolusi induk; nama unik per level cukup
    # praktis utk data organisasi nyata.
    peta = {(str(u["eselon"]), u["nama_unit"]): u["id"] for u in ada}
    now = datetime.now(timezone.utc).isoformat()
    dibuat = 0
    # urut per eselon agar induk selalu dibuat lebih dulu
    for k in sorted(kandidat, key=lambda x: x["eselon"]):
        kunci = (k["eselon"], k["nama_unit"])
        if kunci in peta:
            continue
        parent_id = None
        if k["induk_nama"]:
            parent_id = peta.get((str(int(k["eselon"]) - 1), k["induk_nama"]))
            if not parent_id:
                continue  # induk tak dikenal — jalur tak utuh, lewati
        doc = {"id": str(uuid.uuid4()), "nama_unit": k["nama_unit"],
               "eselon": k["eselon"], "parent_id": parent_id,
               "kode_satker": kode, "sumber": "derivasi pegawai",
               "created_at": now, "updated_at": now}
        await db.unit_kerja.insert_one(dict(doc))
        peta[kunci] = doc["id"]
        dibuat += 1
    await log_audit("bangun_unit_kerja", "", "derivasi",
                    username=user.get("username", "system"),
                    detail=f"Bangun master unit dari pegawai: {dibuat} unit baru")
    return {"ok": True, "dibuat": dibuat, "total_kandidat": len(kandidat)}
