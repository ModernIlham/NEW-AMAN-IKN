"""Registri LAPISAN CITRA EKSISTING peta — lihat `peta_lapisan_utils.py`.

SENGAJA BERSAMA untuk dibaca. Citra adalah rekaman GEOGRAFIS kawasan: satu
foto udara kawasan yang sama benar bagi semua satker yang asetnya ada di sana,
sama sifatnya dengan peta dasar OSM. Karena itu daftar lapisan aktif TIDAK
di-scope satker. (Uji pemilik "bila dua satker mengisi berbeda, apakah
keduanya benar?" — keduanya merekam wilayah/tanggal berbeda, dan keduanya
justru berguna bagi satker lain yang asetnya ada di wilayah itu.)

PENULISAN tetap dijaga ketat: lapisan distempel `kode_satker` pembuatnya dan
hanya boleh diubah/dihapus admin satker itu atau super-admin. Lebih ketat dari
`pastikan_akses_dok_satker` (yang membuka dokumen tanpa kode untuk semua): di
sini lapisan buatan super-admin (kode kosong) tidak boleh diubah admin satker,
karena lapisan itu tampil di peta SEMUA satker.

Backend tidak pernah melayani ubin. Ubin adalah berkas statis yang disajikan
nginx (lihat docs/LAPISAN-CITRA-EKSISTING.md) — uvicorn hanya satu proses.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from peta_lapisan_utils import bentuk_publik, normalisasi_lapisan
from shared_utils import kode_satker_user, log_audit

peta_lapisan_router = APIRouter()

BATAS_DAFTAR = 200


class BatasIn(BaseModel):
    barat: Optional[float] = None
    selatan: Optional[float] = None
    timur: Optional[float] = None
    utara: Optional[float] = None


class LapisanIn(BaseModel):
    nama: str = ""
    sumber: Optional[str] = ""
    tanggal_rekam: str = ""
    url_template: str = ""
    batas: BatasIn = BatasIn()
    zoom_min: Optional[int] = None
    zoom_maks: Optional[int] = None
    opasitas: Optional[float] = None
    aktif: Optional[bool] = True
    keterangan: Optional[str] = ""
    version: Optional[int] = None   # OCC: wajib saat mengubah


def _bersih(payload: LapisanIn) -> dict:
    dok, galat = normalisasi_lapisan(payload.model_dump())
    if galat:
        raise HTTPException(status_code=400, detail="; ".join(galat))
    return dok


def _boleh_ubah(user: dict, dok: dict) -> bool:
    kode = kode_satker_user(user)
    return not kode or str(dok.get("kode_satker") or "").strip() == kode


def _pastikan_boleh_ubah(user: dict, dok: dict) -> None:
    if not _boleh_ubah(user, dok):
        pemilik = str(dok.get("kode_satker") or "").strip() or "pusat"
        raise HTTPException(
            status_code=403,
            detail=f"Lapisan ini dikelola satker {pemilik} — hanya admin satker "
                   f"tersebut atau super-admin yang dapat mengubahnya")


async def _bentrok_url(url: str, kecuali_id: str = "") -> bool:
    q = {"url_template": url}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    return bool(await db.peta_lapisan.find_one(q, {"_id": 1}))


@peta_lapisan_router.get("/peta-lapisan")
async def daftar_lapisan(user: dict = Depends(require_user)):
    """Lapisan citra eksisting. Pengguna biasa: hanya yang aktif. Admin: semua,
    plus siapa pengelolanya dan apakah ia boleh mengubahnya."""
    admin = user.get("role") == "admin"
    q = {} if admin else {"aktif": True}
    items = await (db.peta_lapisan.find(q, {"_id": 0})
                   .sort([("tanggal_rekam", -1), ("nama", 1)])
                   .to_list(BATAS_DAFTAR))
    hasil = []
    for dok in items:
        item = bentuk_publik(dok)
        if admin:
            item["kode_satker"] = str(dok.get("kode_satker") or "")
            item["bisa_ubah"] = _boleh_ubah(user, dok)
            item["diubah_oleh"] = dok.get("diubah_oleh") or dok.get("dibuat_oleh") or ""
            item["updated_at"] = dok.get("updated_at") or ""
        hasil.append(item)
    return {"items": hasil, "jumlah": len(hasil)}


@peta_lapisan_router.post("/peta-lapisan")
async def buat_lapisan(payload: LapisanIn, user: dict = Depends(require_admin)):
    dok = _bersih(payload)
    # Alamat ubin yang sama = lapisan yang sama. Sekaligus penjaga kirim ganda
    # (ketuk Simpan dua kali / antrean mengulang) tanpa kunci idempotensi.
    if await _bentrok_url(dok["url_template"]):
        raise HTTPException(status_code=409,
                            detail="Alamat ubin ini sudah terdaftar sebagai lapisan lain")
    now = datetime.now(timezone.utc).isoformat()
    dok.update({"id": str(uuid.uuid4()), "version": 1, "created_at": now,
                "updated_at": now, "kode_satker": kode_satker_user(user),
                "dibuat_oleh": user.get("username", "")})
    await db.peta_lapisan.insert_one(dict(dok))
    await log_audit("buat_peta_lapisan", "", dok["id"],
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Tambah lapisan citra {dok['nama']} ({dok['tanggal_rekam']})")
    return bentuk_publik(dok)


@peta_lapisan_router.put("/peta-lapisan/{lapisan_id}")
async def ubah_lapisan(lapisan_id: str, payload: LapisanIn,
                       user: dict = Depends(require_admin)):
    if payload.version is None:
        raise HTTPException(status_code=428, detail="Versi lapisan wajib dikirim saat mengubah")
    dok = _bersih(payload)
    lama = await db.peta_lapisan.find_one({"id": lapisan_id}, {"_id": 0})
    if not lama:
        raise HTTPException(status_code=404, detail="Lapisan tidak ditemukan")
    _pastikan_boleh_ubah(user, lama)
    if await _bentrok_url(dok["url_template"], kecuali_id=lapisan_id):
        raise HTTPException(status_code=409,
                            detail="Alamat ubin ini sudah terdaftar sebagai lapisan lain")
    dok.update({"updated_at": datetime.now(timezone.utc).isoformat(),
                "diubah_oleh": user.get("username", "")})
    res = await db.peta_lapisan.update_one(
        {"id": lapisan_id, "version": payload.version},
        {"$set": dok, "$inc": {"version": 1}})
    if res.matched_count == 0:
        raise HTTPException(status_code=409,
                            detail="Lapisan sudah diubah orang lain — muat ulang lalu coba lagi")
    await log_audit("ubah_peta_lapisan", "", lapisan_id,
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Ubah lapisan citra {dok['nama']}"
                           + ("" if dok["aktif"] else " (nonaktif)"))
    baru = await db.peta_lapisan.find_one({"id": lapisan_id}, {"_id": 0})
    return bentuk_publik(baru or {**lama, **dok})


@peta_lapisan_router.delete("/peta-lapisan/{lapisan_id}")
async def hapus_lapisan(lapisan_id: str, user: dict = Depends(require_admin)):
    """Hapus dari registri. Berkas ubin di server TIDAK disentuh."""
    lama = await db.peta_lapisan.find_one({"id": lapisan_id}, {"_id": 0})
    if not lama:
        raise HTTPException(status_code=404, detail="Lapisan tidak ditemukan")
    _pastikan_boleh_ubah(user, lama)
    await db.peta_lapisan.delete_one({"id": lapisan_id})
    await log_audit("hapus_peta_lapisan", "", lapisan_id,
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Hapus lapisan citra {lama.get('nama', '')}")
    return {"ok": True, "id": lapisan_id}
