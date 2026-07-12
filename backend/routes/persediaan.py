"""Master PERSEDIAAN — langkah 1 modul Inventarisasi Persediaan (§7.4).

Master barang persediaan satker (aset lancar, kodefikasi berawalan '1'):
CRUD + paging/pencarian. Stok & layer FIFO (`batches`) dikelola transaksi
persediaan pada iterasi berikutnya — di sini barang lahir dengan stok 0
dan daftar layer kosong; hapus hanya boleh saat stok masih 0.

Regulasi: docs/PUSTAKA-REGULASI-BMN.md §3 (perpetual + FIFO per layer,
kode golongan '1', batas kritis & kedaluwarsa untuk peringatan/nota dinas).
Referensi teknis: modul persediaan KERJA-BARENG (dipelajari menyeluruh).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from persediaan_fields import EDITABLE_FIELD_NAMES
from persediaan_utils import (
    KODE_PENUH_LEN, KODE_PREFIX_LEN, SATUAN_BAKU, next_kode_penuh, next_nup,
    status_stok, validate_kode_persediaan,
)

persediaan_router = APIRouter()


class PersediaanCreate(BaseModel):
    kode_barang: str = Field(min_length=1, max_length=KODE_PENUH_LEN)
    nup: str = ""                     # kosong → otomatis
    nama_barang: str = Field(min_length=1, max_length=300)
    merk: str = ""
    tipe: str = ""
    satuan: str = "Buah"
    lokasi: str = ""
    batas_kritis: int = Field(0, ge=0)
    expired_default: str = ""         # YYYY-MM-DD; kedaluwarsa bawaan batch
    tahun_anggaran: str = ""
    keterangan: str = ""


class PersediaanUpdate(BaseModel):
    nama_barang: Optional[str] = Field(None, min_length=1, max_length=300)
    merk: Optional[str] = None
    tipe: Optional[str] = None
    satuan: Optional[str] = None
    lokasi: Optional[str] = None
    batas_kritis: Optional[int] = Field(None, ge=0)
    expired_default: Optional[str] = None
    tahun_anggaran: Optional[str] = None
    keterangan: Optional[str] = None


def _doc(item: dict) -> dict:
    stok = int(item.get("stok", 0) or 0)
    return {
        **{k: item.get(k) for k in (
            "id", "kode_barang", "nup", "nama_barang", "merk", "tipe", "satuan",
            "lokasi", "batas_kritis", "expired_default", "tahun_anggaran",
            "keterangan", "stok", "version", "created_at", "updated_at")},
        "status_stok": status_stok(stok, item.get("batas_kritis")),
    }


@persediaan_router.get("/persediaan/satuan-baku")
async def list_satuan(_user: dict = Depends(require_user)):
    """Daftar satuan baku untuk dropdown (referensi, bukan pembatasan keras)."""
    return list(SATUAN_BAKU)


@persediaan_router.get("/persediaan")
async def list_persediaan(
    search: str = "",
    status: str = Query("", pattern="^(|aman|kritis|habis)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Daftar master persediaan: cari kode/nama/merk, filter status stok."""
    query = {}
    if search:
        s = search.strip()
        query["$or"] = [
            {"kode_barang": {"$regex": f"^{s}" if s.isdigit() else s, "$options": "i"}},
            {"nama_barang": {"$regex": s, "$options": "i"}},
            {"merk": {"$regex": s, "$options": "i"}},
        ]
    # Filter status stok dihitung DI QUERY (bukan pasca-paging) agar total &
    # halaman benar: habis = stok<=0; kritis = 0<stok<=batas (batas>0).
    if status == "habis":
        query["stok"] = {"$lte": 0}
    elif status == "kritis":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$gt": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
            {"$lte": ["$stok", "$batas_kritis"]},
        ]}
    elif status == "aman":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$or": [
                {"$lte": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
                {"$gt": ["$stok", "$batas_kritis"]},
            ]},
        ]}
    total = await db.persediaan.count_documents(query)
    cursor = (db.persediaan.find(query, {"_id": 0, "batches": 0})
              .sort([("nama_barang", 1), ("kode_barang", 1)])
              .skip((page - 1) * page_size).limit(page_size))
    items = [_doc(x) async for x in cursor]
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@persediaan_router.get("/persediaan/{item_id}")
async def get_persediaan(item_id: str, _user: dict = Depends(require_user)):
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    out = _doc(item)
    out["batches"] = item.get("batches") or []  # detail menampilkan layer FIFO
    return out


@persediaan_router.post("/persediaan")
async def create_persediaan(data: PersediaanCreate, _user: dict = Depends(require_user)):
    kode = str(data.kode_barang or "").strip()
    ok, err = validate_kode_persediaan(kode)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # Kode 10 digit → lengkapi 6 digit nomor urut otomatis (increment
    # dari kode terbesar se-prefix; numerik karena panjang seragam).
    if len(kode) == KODE_PREFIX_LEN:
        max_doc = await db.persediaan.find_one(
            {"kode_barang": {"$regex": f"^{kode}"}},
            {"_id": 0, "kode_barang": 1}, sort=[("kode_barang", -1)])
        try:
            kode = next_kode_penuh(kode, (max_doc or {}).get("kode_barang"))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    # NUP otomatis bila kosong: increment NUP terbesar pada kode sama.
    nup = str(data.nup or "").strip()
    if not nup:
        max_nup_doc = await db.persediaan.find_one(
            {"kode_barang": kode}, {"_id": 0, "nup": 1},
            sort=[("nup_num", -1)])
        nup = next_nup((max_nup_doc or {}).get("nup"))
    if await db.persediaan.find_one({"kode_barang": kode, "nup": nup}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"Kode {kode} NUP {nup} sudah terdaftar")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "kode_barang": kode,
        "nup": nup,
        "nup_num": int(nup) if nup.isdigit() else 0,
        "nama_barang": data.nama_barang.strip(),
        "merk": data.merk.strip(),
        "tipe": data.tipe.strip(),
        "satuan": (data.satuan or "Buah").strip() or "Buah",
        "lokasi": data.lokasi.strip(),
        "batas_kritis": int(data.batas_kritis or 0),
        "expired_default": data.expired_default.strip(),
        "tahun_anggaran": data.tahun_anggaran.strip(),
        "keterangan": data.keterangan.strip(),
        "stok": 0,          # stok lahir 0 — bertambah lewat transaksi masuk
        "batches": [],      # layer FIFO {batch_id, tanggal, qty, harga, expired, ref}
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.persediaan.insert_one({**doc})
    return _doc(doc)


@persediaan_router.put("/persediaan/{item_id}")
async def update_persediaan(
    item_id: str,
    data: PersediaanUpdate,
    if_match: str = Header("", alias="If-Match"),
    _user: dict = Depends(require_user),
):
    """Ubah field non-identitas master (OCC: wajib If-Match versi terkini)."""
    # Whitelist dari registry (persediaan_fields) — field identitas/terkelola
    # sistem tak akan pernah lolos meski model berubah; test registry menjaga.
    updates = {}
    for k, v in data.model_dump(exclude_none=True).items():
        if k not in EDITABLE_FIELD_NAMES:
            continue
        updates[k] = v.strip() if isinstance(v, str) else v
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah")
    if not if_match.strip().isdigit():
        raise HTTPException(status_code=428, detail="Header If-Match (versi) wajib disertakan")

    version = int(if_match.strip())
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.persediaan.find_one_and_update(
        {"id": item_id, "version": version},
        {"$set": updates, "$inc": {"version": 1}},
        projection={"_id": 0},
        return_document=True,
    )
    if res is None:
        exists = await db.persediaan.find_one({"id": item_id}, {"_id": 1})
        if not exists:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        raise HTTPException(status_code=409, detail="Versi berubah — muat ulang data lalu simpan lagi")
    return _doc(res)


@persediaan_router.delete("/persediaan/{item_id}")
async def delete_persediaan(item_id: str, _admin: dict = Depends(require_admin)):
    """Hapus master — hanya bila stok 0 & tanpa layer (jejak transaksi aman)."""
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0, "stok": 1, "batches": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    if int(item.get("stok", 0) or 0) > 0 or (item.get("batches") or []):
        raise HTTPException(status_code=409,
                            detail="Barang masih punya stok/layer — keluarkan stoknya dulu lewat transaksi")
    await db.persediaan.delete_one({"id": item_id})
    return {"message": "Barang persediaan dihapus"}
