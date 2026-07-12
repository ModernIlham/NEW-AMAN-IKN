"""PENGAMANAN — Fase 3: dasbor tertib administrasi + register kasus + arsip.

Dasbor = proyeksi baca dari data inventarisasi (tanpa koleksi baru).
Register BMN bermasalah/sengketa dan arsip dokumen kepemilikan
(sertipikat/BPKB/IMB-PBG, pustaka §11) memakai koleksi sendiri.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import delete_document_from_gridfs, get_document_from_gridfs
from pengamanan_utils import (
    JENIS_DOKUMEN, JENIS_KEKURANGAN, KATEGORI_KASUS, LOKASI_SIMPAN,
    STATUS_KASUS, TRANSISI_KASUS, kekurangan_aset, rekap_dokumen,
    rekap_kasus, rekap_kesehatan, validate_dokumen, validate_kasus,
    validate_transisi_kasus,
)

pengamanan_router = APIRouter()

# Proyeksi hemat: foto cukup 1 elemen pertama untuk uji keberadaan.
_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "kode_register": 1, "location": 1, "user": 1, "bast_file_id": 1,
         "inventory_status": 1, "nomor_perkara": 1, "pihak_bersengketa": 1,
         "keterangan_sengketa": 1, "activity_id": 1,
         "photos": {"$slice": 1}, "photo_gridfs_ids": {"$slice": 1}}


@pengamanan_router.get("/pengamanan/ringkasan")
async def ringkasan_pengamanan(_user: dict = Depends(require_user)):
    """Kesehatan data seluruh aset + daftar pantau sengketa."""
    assets = [a async for a in db.assets.find({}, _PROJ)]
    per, lengkap, sengketa = rekap_kesehatan(assets)
    return {
        "total_aset": len(assets),
        "lengkap": lengkap,
        "kekurangan": per,
        "label_kekurangan": JENIS_KEKURANGAN,
        "sengketa": sengketa,
        "jumlah_sengketa": len(sengketa),
    }


@pengamanan_router.get("/pengamanan/aset-kurang")
async def aset_kurang(
    jenis: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Daftar aset dengan kekurangan tertentu (foto/register/lokasi/pengguna/bast)."""
    if jenis not in JENIS_KEKURANGAN:
        valid = ", ".join(JENIS_KEKURANGAN)
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal (pilihan: {valid})")
    rows = []
    async for a in db.assets.find({}, _PROJ):
        if jenis in kekurangan_aset(a):
            rows.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "location": a.get("location"),
                "activity_id": a.get("activity_id"),
            })
    rows.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total,
            "page": page, "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),
            "label": JENIS_KEKURANGAN[jenis]}


class KasusIn(BaseModel):
    asset_id: str = Field(min_length=1)
    kategori: str
    uraian: str = Field(min_length=1)
    pihak_lawan: str = Field(min_length=1)
    nomor_perkara: str = ""
    pendamping: str = ""      # mis. JPN Kejari / Biro Hukum


class TransisiKasusIn(BaseModel):
    status: str
    catatan: str = ""


@pengamanan_router.get("/pengamanan/kasus")
async def list_kasus(_user: dict = Depends(require_user)):
    """Register BMN bermasalah/sengketa (terbaru dulu) + ringkasan."""
    items = [k async for k in db.pengamanan_kasus.find({}, {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_kasus(items),
            "label_kategori": KATEGORI_KASUS,
            "label_status": STATUS_KASUS,
            "transisi": {k: sorted(v) for k, v in TRANSISI_KASUS.items()},
            "catatan": (
                "Register pendamping penanganan BMN bermasalah (pustaka §11) "
                "— bahan laporan wasdal/CaLBMN; bukan kanal resmi, tidak "
                "berkekuatan hukum, dan bukan pemblokiran sertipikat.")}


@pengamanan_router.post("/pengamanan/kasus")
async def buka_kasus(payload: KasusIn, user: dict = Depends(require_user)):
    """Buka kasus baru untuk satu aset (satu kasus aktif per aset)."""
    data = payload.model_dump()
    errors = validate_kasus(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "location": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    aktif = await db.pengamanan_kasus.find_one(
        {"asset_id": asset["id"], "status": {"$ne": "selesai"}},
        {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(
            status_code=409,
            detail="Aset ini sudah punya kasus aktif — selesaikan dulu")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "lokasi": asset.get("location"),
        "kategori": data["kategori"],
        "status": "identifikasi",
        "uraian": data["uraian"].strip(),
        "pihak_lawan": data["pihak_lawan"].strip(),
        "nomor_perkara": str(data.get("nomor_perkara") or "").strip(),
        "pendamping": str(data.get("pendamping") or "").strip(),
        "riwayat": [{"status": "identifikasi", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengamanan_kasus.insert_one({**record})
    return record


@pengamanan_router.post("/pengamanan/kasus/{kasus_id}/status")
async def transisi_kasus(kasus_id: str, payload: TransisiKasusIn,
                         user: dict = Depends(require_user)):
    """Pindahkan status kasus (anti-race pada status lama)."""
    kasus = await db.pengamanan_kasus.find_one({"id": kasus_id}, {"_id": 0})
    if not kasus:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    ke = payload.status
    errors = validate_transisi_kasus(kasus, ke)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    entri = {"status": ke, "tanggal": now, "oleh": user.get("username"),
             "catatan": str(payload.catatan or "").strip()}
    res = await db.pengamanan_kasus.find_one_and_update(
        {"id": kasus_id, "status": kasus["status"]},
        {"$set": {"status": ke, "updated_at": now}, "$push": {"riwayat": entri}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Status kasus berubah di perangkat lain — muat ulang")
    res["status"] = ke
    return res


@pengamanan_router.delete("/pengamanan/kasus/{kasus_id}")
async def hapus_kasus(kasus_id: str, _admin: dict = Depends(require_admin)):
    """Hapus satu kasus dari register (admin)."""
    res = await db.pengamanan_kasus.delete_one({"id": kasus_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    return {"ok": True}


class DokumenIn(BaseModel):
    asset_id: str = Field(min_length=1)
    jenis: str
    nomor: str = Field(min_length=1)
    atas_nama: str = ""            # mis. Pemerintah RI c.q. K/L
    lokasi_simpan: str
    berlaku_sampai: str = ""       # opsional (STNK/pajak) YYYY-MM-DD
    keterangan: str = ""


@pengamanan_router.get("/pengamanan/dokumen")
async def list_dokumen(asset_id: str = "", _user: dict = Depends(require_user)):
    """Arsip dokumen kepemilikan (terbaru dulu) + ringkasan per jenis."""
    query = {"asset_id": asset_id} if asset_id else {}
    items = [d async for d in db.pengamanan_dokumen.find(query, {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    today_iso = datetime.now(timezone.utc).date().isoformat()
    return {"items": items, "ringkasan": rekap_dokumen(items, today_iso),
            "label_jenis": JENIS_DOKUMEN, "label_lokasi": LOKASI_SIMPAN,
            "catatan": (
                "Arsip pendamping (pustaka §11.3) — penyimpanan dokumen yang "
                "sah tetap mengikuti PP 27/2014 Ps. 43 + PMK 218/2015 "
                "(tanah/bangunan di Pengelola Barang, lainnya di Pengguna "
                "Barang); AMAN hanya mencatat salinan/scan.")}


@pengamanan_router.post("/pengamanan/dokumen")
async def catat_dokumen(payload: DokumenIn, user: dict = Depends(require_user)):
    """Catat satu dokumen kepemilikan untuk satu aset."""
    data = payload.model_dump()
    errors = validate_dokumen(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "jenis": data["jenis"],
        "nomor": data["nomor"].strip(),
        "atas_nama": str(data.get("atas_nama") or "").strip(),
        "lokasi_simpan": data["lokasi_simpan"],
        "berlaku_sampai": str(data.get("berlaku_sampai") or "").strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        "lampiran": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengamanan_dokumen.insert_one({**record})
    return record


@pengamanan_router.delete("/pengamanan/dokumen/{dok_id}")
async def hapus_dokumen(dok_id: str, _admin: dict = Depends(require_admin)):
    """Hapus satu dokumen dari arsip + bersihkan lampirannya (admin)."""
    d = await db.pengamanan_dokumen.find_one({"id": dok_id}, {"_id": 0, "lampiran": 1})
    if not d:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    await db.pengamanan_dokumen.delete_one({"id": dok_id})
    for lamp in d.get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True}


# Lampiran scan dokumen — pola baku GridFS (#131-#156)
_LAMPIRAN_MEDIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
_MAX_LAMPIRAN_BYTES = 10 * 1024 * 1024
_MAX_LAMPIRAN = 10


def _lampiran_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _LAMPIRAN_MEDIA:
        if name.endswith(ext):
            return ext
    return ""


@pengamanan_router.post("/pengamanan/dokumen/{dok_id}/lampiran")
async def unggah_lampiran_dokumen(dok_id: str, file: UploadFile = File(...),
                                  user: dict = Depends(require_user)):
    """Unggah scan dokumen kepemilikan (PDF/gambar, maks 10MB, 10 berkas)."""
    d = await db.pengamanan_dokumen.find_one(
        {"id": dok_id}, {"_id": 0, "id": 1, "lampiran": 1})
    if not d:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    if len(d.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per dokumen")
    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    ext = _lampiran_ext(filename)
    if not ext:
        raise HTTPException(status_code=400,
                            detail="Lampiran harus PDF atau gambar (JPG/PNG/WEBP)")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > _MAX_LAMPIRAN_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran lampiran maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    from bson import ObjectId
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=filename,
        metadata={"content_type": _LAMPIRAN_MEDIA[ext], "size": len(file_bytes),
                  "kind": "dokumen_kepemilikan", "dok_id": dok_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pengamanan_dokumen.find_one_and_update(
        {"id": dok_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@pengamanan_router.get("/pengamanan/dokumen/{dok_id}/lampiran/{file_id}")
async def unduh_lampiran_dokumen(dok_id: str, file_id: str, request: Request,
                                 _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran dokumen (menerima header ATAU ?token)."""
    d = await db.pengamanan_dokumen.find_one(
        {"id": dok_id, "lampiran.file_id": file_id}, {"_id": 0, "lampiran.$": 1})
    if not d or not d.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = d["lampiran"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "dokumen"}"'})


@pengamanan_router.delete("/pengamanan/dokumen/{dok_id}/lampiran/{file_id}")
async def hapus_lampiran_dokumen(dok_id: str, file_id: str,
                                 _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pengamanan_dokumen.update_one(
        {"id": dok_id},
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}
