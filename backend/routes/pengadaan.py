"""PENGADAAN — Fase 4 tahap awal: register perolehan per dokumen.

Perpres 16/2018 jo. 46/2025 (pustaka §10): satu entri per BAST/kontrak,
checklist kelengkapan dokumen sumber, daftar barang dengan tautan ke aset
master (cegah entri ganda) + penanda ekstrakomptabel PMK 181. Pencatatan
resmi tetap di SAKTI; kanal pengadaan tetap SiRUP/SPSE/e-Katalog — AMAN
alat bantu tertib dokumen satker. Pra-isi draft aset baru menyusul.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import delete_document_from_gridfs, get_document_from_gridfs
from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    dokumen_kurang_perolehan, is_ekstrakomptabel, nilai_perolehan,
    rekap_perolehan, validate_perolehan,
)

pengadaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


class BarangIn(BaseModel):
    uraian: str = Field(min_length=1)
    kode: str = ""                     # kode barang (opsional, utk ambang)
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)
    asset_id: str = ""                 # tautan ke aset master (opsional)


class PerolehanIn(BaseModel):
    jenis: str
    pihak: str = Field(min_length=1)   # penyedia / pemberi hibah / pengirim
    nomor_kontrak: str = ""
    nomor_bast: str = Field(min_length=1)
    tanggal_bast: str = Field(min_length=10, max_length=10)
    keterangan: str = ""
    barang: list[BarangIn] = Field(min_length=1, max_length=100)


class DokumenIn(BaseModel):
    dokumen: dict[str, bool]


class TautkanIn(BaseModel):
    index: int = Field(ge=0)
    asset_id: str = ""                 # kosong = lepaskan tautan


def _enrich(p: dict) -> dict:
    p["dokumen_kurang"] = dokumen_kurang_perolehan(p)
    p["nilai"] = nilai_perolehan(p)
    for b in p.get("barang") or []:
        b["ekstrakomptabel"] = is_ekstrakomptabel(b)
    return p


@pengadaan_router.get("/pengadaan")
async def list_pengadaan(_user: dict = Depends(require_user)):
    """Register perolehan (BAST terbaru dulu) + ringkasan + label."""
    items = [_enrich(p) async for p in db.pengadaan.find({}, {"_id": 0})
             .sort("tanggal_bast", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_perolehan(items),
            "label_jenis": {k: v[0] for k, v in JENIS_PEROLEHAN.items()},
            "kode_jenis": {k: v[1] for k, v in JENIS_PEROLEHAN.items()},
            "label_dokumen": LABEL_DOKUMEN_SUMBER,
            "dokumen_wajib": {k: list(v) for k, v in DOKUMEN_PEROLEHAN.items()},
            "catatan": (
                "Register pendamping tertib dokumen: pencatatan BMN resmi di "
                "SAKTI (BAST = pemicu, tanpa menunggu SP2D); kanal pengadaan "
                "resmi SiRUP/SPSE/e-Katalog. Penanda ekstrakomptabel memakai "
                "ambang PMK 181/2016 (peralatan-mesin Rp1 jt, gedung Rp25 jt).")}


@pengadaan_router.get("/pengadaan/export")
async def export_pengadaan(_user: dict = Depends(require_user)):
    """Ekspor CSV register perolehan (pola #158)."""
    import csv as csv_module
    import io

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["jenis", "pihak", "nomor_kontrak", "nomor_bast", "tanggal_bast",
                "jumlah_barang", "nilai", "dokumen_kurang", "keterangan",
                "jumlah_lampiran", "dibuat_oleh"])
    async for p in db.pengadaan.find({}, {"_id": 0}).sort("tanggal_bast", -1):
        w.writerow([
            JENIS_PEROLEHAN.get(p.get("jenis"), (p.get("jenis"),))[0],
            p.get("pihak"), p.get("nomor_kontrak"), p.get("nomor_bast"),
            p.get("tanggal_bast"), len(p.get("barang") or []),
            int(nilai_perolehan(p)),
            "; ".join(dokumen_kurang_perolehan(p)),
            p.get("keterangan"), len(p.get("lampiran_berkas") or []),
            p.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_pengadaan.csv"'})


@pengadaan_router.post("/pengadaan")
async def buat_perolehan(payload: PerolehanIn, user: dict = Depends(require_user)):
    """Catat perolehan baru (barang boleh ditautkan ke aset master)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_perolehan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    barang_rows = []
    for b in data["barang"]:
        row = {"uraian": b["uraian"].strip(),
               "kode": str(b.get("kode") or "").strip(),
               "jumlah": float(b["jumlah"]),
               "harga_satuan": float(b["harga_satuan"]),
               "asset_id": "", "asset_code": "", "NUP": "", "asset_name": ""}
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
            if not a:
                raise HTTPException(status_code=404,
                                    detail=f"Aset {aid} tidak ditemukan")
            row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                        "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
        barang_rows.append(row)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "jenis": data["jenis"],
        "pihak": data["pihak"].strip(),
        "nomor_kontrak": str(data.get("nomor_kontrak") or "").strip(),
        "nomor_bast": data["nomor_bast"].strip(),
        "tanggal_bast": data["tanggal_bast"].strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        # Checklist mulai kosong; BAST & kontrak otomatis tercentang bila
        # nomornya sudah diisi saat pencatatan.
        "dokumen": {"bast": True,
                    **({"kontrak": True} if str(data.get("nomor_kontrak") or "").strip() else {})},
        "barang": barang_rows,
        "lampiran_berkas": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengadaan.insert_one({**record})
    return _enrich(record)


@pengadaan_router.put("/pengadaan/{perolehan_id}/dokumen")
async def perbarui_dokumen(perolehan_id: str, payload: DokumenIn,
                           _user: dict = Depends(require_user)):
    """Perbarui checklist dokumen sumber (kunci di luar daftar diabaikan)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    wajib = set(DOKUMEN_PEROLEHAN.get(p.get("jenis"), ()))
    dokumen = {**(p.get("dokumen") or {}),
               **{k: bool(v) for k, v in payload.dokumen.items() if k in wajib}}
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"dokumen": dokumen, "updated_at": now}})
    p["dokumen"] = dokumen
    return _enrich(p)


@pengadaan_router.post("/pengadaan/{perolehan_id}/tautkan")
async def tautkan_barang(perolehan_id: str, payload: TautkanIn,
                         _user: dict = Depends(require_user)):
    """Tautkan/lepaskan baris barang ke aset master (cegah entri ganda)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    barang = p.get("barang") or []
    if payload.index >= len(barang):
        raise HTTPException(status_code=400, detail="Baris barang tidak ada")
    row = barang[payload.index]
    aid = str(payload.asset_id or "").strip()
    if aid:
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                    "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    else:
        row.update({"asset_id": "", "asset_code": "", "NUP": "",
                    "asset_name": ""})
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"barang": barang, "updated_at": now}})
    p["barang"] = barang
    return _enrich(p)


# Lampiran berkas per perolehan (scan kontrak/BAPHP/BAST/kuitansi/SP2D
# — melengkapi checklist dokumen sumber). Pola sama dengan #131/#132/#134.
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


@pengadaan_router.post("/pengadaan/{perolehan_id}/lampiran")
async def unggah_lampiran_perolehan(perolehan_id: str,
                                    file: UploadFile = File(...),
                                    user: dict = Depends(require_user)):
    """Unggah scan dokumen sumber (PDF/gambar, maks 10MB, 10 berkas)."""
    p = await db.pengadaan.find_one(
        {"id": perolehan_id}, {"_id": 0, "id": 1, "lampiran_berkas": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    if len(p.get("lampiran_berkas") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per perolehan")
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
                  "kind": "pengadaan", "perolehan_id": perolehan_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pengadaan.find_one_and_update(
        {"id": perolehan_id},
        {"$push": {"lampiran_berkas": entri},
         "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran_berkas": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    return {"message": "Lampiran terunggah",
            "lampiran_berkas": res.get("lampiran_berkas") or []}


@pengadaan_router.get("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def unduh_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   request: Request,
                                   _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran perolehan (menerima header ATAU ?token)."""
    p = await db.pengadaan.find_one(
        {"id": perolehan_id, "lampiran_berkas.file_id": file_id},
        {"_id": 0, "lampiran_berkas.$": 1})
    if not p or not p.get("lampiran_berkas"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = p["lampiran_berkas"][0]
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


@pengadaan_router.delete("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def hapus_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$pull": {"lampiran_berkas": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pengadaan_router.delete("/pengadaan/{perolehan_id}")
async def hapus_perolehan(perolehan_id: str,
                          _admin: dict = Depends(require_admin)):
    """Hapus register perolehan salah input (admin) + berkas lampirannya."""
    p = await db.pengadaan.find_one({"id": perolehan_id},
                                    {"_id": 0, "lampiran_berkas": 1})
    res = await db.pengadaan.delete_one({"id": perolehan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    for lamp in (p or {}).get("lampiran_berkas") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": perolehan_id}
