"""Unit kerja LUAR — pohon Eselon/Tingkat I–V milik satu satker luar.

Rencana: `docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md` (PGW-05; kontrak 6.2,
aturan penampungan 3.3 butir 3). Cermin `routes/unit_kerja.py`:
- aturan pohon dari `organisasi_utils`, derivasi dari
  `unit_kerja_utils.unit_dari_pegawai`, `akar` dari
  `satker_luar.eselon_satker`;
- setiap operasi WAJIB ber-`satker_luar_id`, dan induk sebuah unit selalu
  berada di satker yang sama — unit senama di satker atau instansi lain tidak
  tersentuh;
- ganti nama merambat ke `pegawai_luar` SAJA, dalam satker itu — tidak
  pernah ke `assets` maupun ke Master Pegawai internal;
- satker-wadah "Masyarakat (Perorangan)" menolak semua operasi unit;
- tanpa `cocokkan-lingkup` (lingkup kegiatan hanya memakai unit internal).

Direktori bersama (K2/K2a): tanpa `kode_satker`, semua admin boleh
menambah/mengubah dengan audit ketat; hapus permanen hanya super-admin (3.4).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_super_admin, require_user
from db import db
from shared_utils import kode_satker_user, log_audit
import organisasi_utils as org
from unit_kerja_utils import unit_dari_pegawai

unit_kerja_luar_router = APIRouter()

_PROJ = {"_id": 0}


class UnitLuarIn(BaseModel):
    satker_luar_id: str = ""
    nama_unit: str
    eselon: str
    parent_id: Optional[str] = ""


class UnitLuarUbah(BaseModel):
    """Sama dengan `UnitUbah` internal: None = biarkan, "" pada parent_id =
    jadikan puncak. `satker_luar_id` tidak bisa diganti lewat sini."""
    nama_unit: Optional[str] = None
    eselon: Optional[str] = None
    parent_id: Optional[str] = None


class BangunLuarIn(BaseModel):
    satker_luar_id: str = ""


def _kini() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(aksi: str, record_id: str, user: dict, detail: str):
    await log_audit(aksi, "", record_id, username=user.get("username", "system"),
                    detail=detail, kode_satker=kode_satker_user(user), strict=True)


async def _satker(satker_luar_id: str) -> dict:
    """Satker luar yang boleh ber-unit; wadah perorangan ditolak."""
    if not satker_luar_id:
        raise HTTPException(status_code=400, detail="Pilih satker dulu")
    s = await db.satker_luar.find_one({"id": satker_luar_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Satker luar tidak ditemukan")
    if s.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            "Wadah perorangan tidak memiliki struktur unit"))
    return s


def _akar(satker: dict) -> int:
    return org.level_akar(satker.get("eselon_satker"))


async def _induk(parent_id: str, satker_luar_id: str):
    if not parent_id:
        return None
    induk = await db.unit_kerja_luar.find_one({"id": parent_id}, _PROJ)
    if not induk:
        raise HTTPException(status_code=400, detail="Induk tidak ditemukan")
    if induk.get("satker_luar_id") != satker_luar_id:
        # Aturan penampungan 3: induk sebuah unit selalu di satker yang sama.
        raise HTTPException(status_code=400, detail=(
            "Induk harus berada di satker yang sama"))
    return induk


@unit_kerja_luar_router.get("/unit-kerja-luar")
async def daftar_unit_kerja_luar(satker_luar_id: str = "",
                                 _user: dict = Depends(require_user)):
    satker = await _satker(satker_luar_id)
    items = await db.unit_kerja_luar.find(
        {"satker_luar_id": satker_luar_id}, _PROJ).to_list(5000)
    items.sort(key=lambda u: (str(u.get("eselon")), str(u.get("nama_unit", "")).lower()))
    akar = _akar(satker)
    return {"items": items, "jumlah": len(items), "level_akar": akar,
            "level": org.daftar_level(akar)}


@unit_kerja_luar_router.post("/unit-kerja-luar")
async def buat_unit_kerja_luar(payload: UnitLuarIn, user: dict = Depends(require_admin)):
    satker = await _satker(str(payload.satker_luar_id or "").strip())
    doc = {"nama_unit": str(payload.nama_unit or "").strip(),
           "eselon": str(payload.eselon or "").strip(),
           "parent_id": str(payload.parent_id or "").strip()}
    induk = await _induk(doc["parent_id"], satker["id"])
    ok, pesan = org.validasi_unit(doc, induk, akar=_akar(satker))
    if not ok:
        raise HTTPException(status_code=400, detail=pesan)
    dup = await db.unit_kerja_luar.find_one(
        {"satker_luar_id": satker["id"], "nama_unit": doc["nama_unit"],
         "eselon": doc["eselon"], "parent_id": doc["parent_id"] or None}, _PROJ)
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Unit {doc['nama_unit']} sudah terdaftar")
    now = _kini()
    doc.update({"id": str(uuid.uuid4()), "parent_id": doc["parent_id"] or None,
                "satker_luar_id": satker["id"], "created_at": now, "updated_at": now})
    await db.unit_kerja_luar.insert_one(dict(doc))
    await _audit("luar_unit_tambah", doc["id"], user,
                 f"Tambah unit {doc['eselon']}: {doc['nama_unit']} "
                 f"({satker.get('nama_satker', '')})")
    return {"ok": True, "id": doc["id"]}


async def _rambatkan_nama(satker_luar_id, fe_lama, fe_baru, level_lama, level_baru):
    """Ikutkan orang luar SATKER INI saat nama/jalur unitnya berubah. Dicari
    lewat jalur lama lengkap, persis seperti internal — tetapi hanya ke
    `pegawai_luar`, tidak pernah ke `assets` atau `pegawai`."""
    saring = org.filter_jalur(fe_lama, level_lama)
    if not saring:
        return {"pegawai": 0}
    setel, hapus = org.perubahan_jalur(fe_lama, fe_baru, max(level_lama, level_baru))
    if not setel and not hapus:
        return {"pegawai": 0}
    ubah = {}
    if setel:
        ubah["$set"] = dict(setel)
    if hapus:
        ubah["$unset"] = {k: "" for k in hapus}
    hasil = await db.pegawai_luar.update_many(
        {**saring, "satker_luar_id": satker_luar_id}, ubah)
    return {"pegawai": getattr(hasil, "modified_count", 0) or 0}


@unit_kerja_luar_router.put("/unit-kerja-luar/{unit_id}")
async def ubah_unit_kerja_luar(unit_id: str, payload: UnitLuarUbah,
                               user: dict = Depends(require_admin)):
    u = await db.unit_kerja_luar.find_one({"id": unit_id}, _PROJ)
    if not u:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    satker = await _satker(u.get("satker_luar_id", ""))
    baru = dict(u)
    if payload.nama_unit is not None:
        baru["nama_unit"] = str(payload.nama_unit or "").strip()
    if payload.eselon is not None:
        baru["eselon"] = str(payload.eselon or "").strip()
    if payload.parent_id is not None:
        baru["parent_id"] = str(payload.parent_id or "").strip() or None
    induk = await _induk(baru.get("parent_id") or "", satker["id"])
    semua = await db.unit_kerja_luar.find(
        {"satker_luar_id": satker["id"]},
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1, "parent_id": 1}).to_list(5000)
    ok, pesan = org.validasi_perubahan(u, baru, induk, semua, akar=_akar(satker))
    if not ok:
        raise HTTPException(status_code=400, detail=pesan)
    kembar = await db.unit_kerja_luar.find_one(
        {"id": {"$ne": unit_id}, "satker_luar_id": satker["id"],
         "nama_unit": baru["nama_unit"], "eselon": baru["eselon"],
         "parent_id": baru.get("parent_id")}, _PROJ)
    if kembar:
        raise HTTPException(status_code=400, detail=(
            f"Unit {baru['nama_unit']} sudah terdaftar di induk itu"))
    peta_unit = {x["id"]: x for x in semua}
    peta_parent = {x["id"]: x.get("parent_id") for x in semua}
    fe_lama = org.field_eselon(unit_id, peta_unit, peta_parent)
    peta_unit_baru = dict(peta_unit, **{unit_id: baru})
    peta_parent_baru = dict(peta_parent, **{unit_id: baru.get("parent_id")})
    fe_baru = org.field_eselon(unit_id, peta_unit_baru, peta_parent_baru)
    lv_lama = int(str(u.get("eselon") or "1"))
    lv_baru = int(str(baru.get("eselon") or "1"))
    await db.unit_kerja_luar.update_one({"id": unit_id}, {"$set": {
        "nama_unit": baru["nama_unit"], "eselon": baru["eselon"],
        "parent_id": baru.get("parent_id"), "updated_at": _kini()}})
    rambat = await _rambatkan_nama(satker["id"], fe_lama, fe_baru, lv_lama, lv_baru)
    await _audit("luar_unit_ubah", unit_id, user,
                 f"Ubah unit {lv_lama}→{lv_baru}: {u.get('nama_unit')} → "
                 f"{baru['nama_unit']}; orang {rambat['pegawai']}")
    return {"ok": True, "id": unit_id,
            "jalur": org.jalur_nama(unit_id, peta_unit_baru, peta_parent_baru),
            "ikut_diperbarui": rambat}


@unit_kerja_luar_router.delete("/unit-kerja-luar/{unit_id}")
async def hapus_unit_kerja_luar(unit_id: str, user: dict = Depends(require_super_admin)):
    """Hapus permanen (super-admin, 3.4). Ditolak bila masih punya anak atau
    masih dipakai orang di satker ini."""
    u = await db.unit_kerja_luar.find_one({"id": unit_id}, _PROJ)
    if not u:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    satker_id = u.get("satker_luar_id", "")
    anak = await db.unit_kerja_luar.count_documents(
        {"satker_luar_id": satker_id, "parent_id": unit_id})
    if anak:
        raise HTTPException(status_code=409, detail=(
            f"Unit masih punya {anak} sub-unit — hapus/pindahkan dulu"))
    nama, es = str(u.get("nama_unit") or ""), str(u.get("eselon") or "1")
    dipakai = await db.pegawai_luar.count_documents(
        {"satker_luar_id": satker_id, f"eselon{es}": nama})
    if dipakai:
        raise HTTPException(status_code=409, detail=(
            f"Unit dipakai {dipakai} orang — perbarui unit orangnya dulu"))
    await db.unit_kerja_luar.delete_one({"id": unit_id})
    await _audit("luar_unit_hapus", unit_id, user, f"Hapus unit {es}: {nama}")
    return {"ok": True, "id": unit_id}


@unit_kerja_luar_router.post("/unit-kerja-luar/bangun-dari-pegawai")
async def bangun_unit_luar_dari_pegawai(payload: BangunLuarIn,
                                        user: dict = Depends(require_admin)):
    """Bangun/lengkapi pohon unit satu satker luar dari jalur eselon1–5
    orangnya (idempoten — hanya menambah yang belum ada)."""
    satker = await _satker(str(payload.satker_luar_id or "").strip())
    orang = await db.pegawai_luar.find(
        {"satker_luar_id": satker["id"]},
        {"_id": 0, "eselon1": 1, "eselon2": 1, "eselon3": 1,
         "eselon4": 1, "eselon5": 1}).to_list(20000)
    kandidat = unit_dari_pegawai(orang, akar=_akar(satker))
    ada = await db.unit_kerja_luar.find(
        {"satker_luar_id": satker["id"]},
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1}).to_list(5000)
    peta = {(str(u["eselon"]), u["nama_unit"]): u["id"] for u in ada}
    now, dibuat = _kini(), 0
    for k in sorted(kandidat, key=lambda x: x["eselon"]):
        kunci = (k["eselon"], k["nama_unit"])
        if kunci in peta:
            continue
        parent_id = None
        if k["induk_nama"]:
            parent_id = peta.get((str(int(k["eselon"]) - 1), k["induk_nama"]))
            if not parent_id:
                continue
        doc = {"id": str(uuid.uuid4()), "nama_unit": k["nama_unit"],
               "eselon": k["eselon"], "parent_id": parent_id,
               "satker_luar_id": satker["id"], "sumber": "derivasi pegawai",
               "created_at": now, "updated_at": now}
        await db.unit_kerja_luar.insert_one(dict(doc))
        peta[kunci] = doc["id"]
        dibuat += 1
    await _audit("luar_unit_bangun", satker["id"], user,
                 f"Bangun unit dari orang ({satker.get('nama_satker', '')}): "
                 f"{dibuat} unit baru")
    return {"ok": True, "dibuat": dibuat, "total_kandidat": len(kandidat)}
