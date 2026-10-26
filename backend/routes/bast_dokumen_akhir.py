"""Arsip tambahan BAST, bukan pengganti bukti penerapan atau PDF e-sign asli.

Semua versi dipertahankan, termasuk yang tidak sesuai. Pemeriksaan petugas
tidak memverifikasi sertifikat TTE/e-meterai dan tidak memfinalisasi BAST.
"""
import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth_utils import require_user_or_query_token, require_writer
from db import db
from portal_bast_validitas import sidik_isi_bast
from routes.bast import _header_otomasi_bast, _sidik_operasi_bast
from shared_utils import (cek_magic_gambar, delete_document_from_gridfs,
                          get_document_from_gridfs, log_audit,
                          pastikan_akses_dok_satker)

bast_dokumen_akhir_router = APIRouter()
MAKS_BERKAS = 20
MAKS_BYTE = 10 * 1024 * 1024
Jenis = Literal["scan_manual", "e_meterai", "dokumen_lengkap"]


class PemeriksaanAkhir(BaseModel):
    status: Literal["sesuai", "tidak_sesuai"]
    sudah_diperiksa: Literal[True]
    catatan: str = Field(min_length=5, max_length=1000)


async def _bast(bast_id, user):
    b = await db.bast_serah_terima.find_one({"id": bast_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "BAST tidak ditemukan")
    await pastikan_akses_dok_satker(user, b)
    return b


def _replay(b, operasi, sidik):
    for event in b.get("operasi_dokumen_akhir") or []:
        if event["kunci"] == operasi:
            if event["sidik"] != sidik:
                raise HTTPException(409, "Idempotency-Key sudah dipakai untuk tindakan berbeda")
            return event["hasil"]
    return None


def _siap(b, versi):
    if b.get("direvisi_oleh") or b.get("tt_dicabut"):
        raise HTTPException(409, "BAST telah direvisi atau TTD dicabut. Gunakan BAST pengganti yang aktif")
    if versi != int(b.get("dokumen_akhir_version") or 1):
        raise HTTPException(409, "Arsip BAST berubah. Muat ulang sebelum melanjutkan")


def _cas(b):
    # Lindungi snapshot isi, sumber bukti, status dan versi dalam SATU tulis.
    # Sertakan field opsional yang mungkin baru dibuat selama unggah/review.
    fields = set(b) | {"dokumen_akhir_version", "dokumen_akhir", "portal_otomasi",
                       "signature_request_id", "tt_dicabut", "direvisi_oleh", "bukti",
                       "foto_serah_terima", "foto_serah_terima_bersama"}
    return {k: {"$eq": b[k]} if k in b else {"$exists": False} for k in fields}


def _sumber(b):
    return {"bast_sidik": sidik_isi_bast(b),
            "signature_request_id": b.get("signature_request_id"),
            "bukti_file_id": (b.get("bukti") or {}).get("file_id")}


async def _simpan(b, dokumen, versi, operasi, sidik, hasil):
    changed = await db.bast_serah_terima.update_one(_cas(b), {
        "$set": {"dokumen_akhir": dokumen, "dokumen_akhir_version": versi + 1},
        "$push": {"operasi_dokumen_akhir": {"kunci": operasi, "sidik": sidik, "hasil": hasil}},
    })
    if changed.matched_count:
        return hasil
    latest = await db.bast_serah_terima.find_one({"id": b["id"]}) or {}
    replay = _replay(latest, operasi, sidik)
    if replay:
        return replay
    raise HTTPException(409, "BAST berubah selama proses. Muat ulang dan periksa arsip terlebih dahulu")


def _tipe(data, filename):
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext == ".pdf" and data.lstrip().startswith(b"%PDF-"):
        return "application/pdf"
    if ext in {".jpg", ".jpeg", ".png"} and cek_magic_gambar(data, ext):
        return "image/png" if ext == ".png" else "image/jpeg"
    raise HTTPException(400, "Isi berkas harus sesuai PDF/JPG/PNG, bukan hanya nama ekstensinya")


@bast_dokumen_akhir_router.post("/bast/{bast_id}/dokumen-akhir")
async def unggah_dokumen_akhir(bast_id: str, request: Request,
                              file: UploadFile = File(...), jenis: Jenis = Form(...),
                              catatan: str = Form(..., min_length=5, max_length=1000),
                              user: dict = Depends(require_writer)):
    b = await _bast(bast_id, user)
    versi, operasi = _header_otomasi_bast(request, user, bast_id, "dokumen-akhir")
    catatan = catatan.strip()
    if len(catatan) < 5:
        raise HTTPException(400, "Isi keterangan dokumen minimal 5 karakter")
    data = await file.read(MAKS_BYTE + 1)
    if not data or len(data) > MAKS_BYTE:
        raise HTTPException(400, "Berkas tidak boleh kosong dan maksimal 10 MB")
    # Nama hanya metadata; tidak pernah dipakai sebagai path filesystem.
    nama = str(file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    nama = "".join(c for c in nama if c.isprintable())[:180]
    tipe = _tipe(data, nama)
    digest = hashlib.sha256(data).hexdigest()
    sidik = _sidik_operasi_bast({"version": versi, "jenis": jenis,
                               "catatan": catatan, "filename": nama, "sha256": digest})
    replay = _replay(b, operasi, sidik)
    if replay:
        return replay
    _siap(b, versi)
    docs = b.get("dokumen_akhir") or []
    if len(docs) >= MAKS_BERKAS:
        raise HTTPException(400, "Maksimal 20 arsip dokumen akhir per BAST; arsip lama tetap dipertahankan")
    if any(d.get("sha256") == digest for d in docs):
        raise HTTPException(409, "Berkas identik sudah ada di arsip. Periksa dokumen yang sudah diunggah")
    from gerbang_media import tulis_media
    fid, _ = await tulis_media(data, nama=nama, content_type=tipe, kelas="mentah",
                               metadata={"arsip_bast_akhir": True, "sha256": digest})
    stored = await get_document_from_gridfs(fid)
    if not stored or hashlib.sha256(stored).hexdigest() != digest:
        await delete_document_from_gridfs(fid)
        raise HTTPException(503, "Integritas berkas tersimpan belum dapat dipastikan. Coba kembali")
    doc = {"id": str(uuid.uuid4()), "file_id": fid, "filename": nama,
           "content_type": tipe, "ukuran": len(data), "sha256": digest,
           "jenis": jenis, "catatan": catatan, "status": "menunggu",
           "sumber": _sumber(b), "oleh": user.get("username") or "system",
           "diunggah_pada": datetime.now(timezone.utc).isoformat()}
    hasil = {"ok": True, "dokumen_id": doc["id"], "version": versi + 1}
    try:
        result = await _simpan(b, [*docs, doc], versi, operasi, sidik, hasil)
    except HTTPException:
        # CAS gagal secara pasti: blob kalah tidak pernah menjadi rujukan.
        await delete_document_from_gridfs(fid)
        raise
    # Replay dua unggahan serentak: buang hanya blob percobaan yang kalah.
    if result["dokumen_id"] != doc["id"]:
        await delete_document_from_gridfs(fid)
        return result
    await log_audit("arsip_akhir_bast", "", username=doc["oleh"],
                    detail=f"Arsip tambahan BAST {b.get('nomor') or bast_id}: {doc['id']} ({jenis}); menunggu pemeriksaan")
    return result


@bast_dokumen_akhir_router.post("/bast/{bast_id}/dokumen-akhir/{dokumen_id}/periksa")
async def periksa_dokumen_akhir(bast_id: str, dokumen_id: str, payload: PemeriksaanAkhir,
                               request: Request, user: dict = Depends(require_writer)):
    b = await _bast(bast_id, user)
    versi, operasi = _header_otomasi_bast(request, user, bast_id, "periksa-dokumen-akhir")
    catatan = payload.catatan.strip()
    if len(catatan) < 5:
        raise HTTPException(400, "Catatan pemeriksaan minimal 5 karakter")
    sidik = _sidik_operasi_bast({"version": versi, "dokumen_id": dokumen_id,
                               **payload.model_dump(), "catatan": catatan})
    replay = _replay(b, operasi, sidik)
    if replay:
        return replay
    _siap(b, versi)
    docs = b.get("dokumen_akhir") or []
    doc = next((d for d in docs if d["id"] == dokumen_id), None)
    if not doc:
        raise HTTPException(404, "Dokumen tidak ditemukan dalam BAST ini")
    if doc["status"] != "menunggu":
        raise HTTPException(409, "Pemeriksaan sudah dicatat. Unggah versi baru bila perlu; arsip tidak ditimpa")
    if payload.status == "sesuai" and doc.get("sumber") != _sumber(b):
        raise HTTPException(409, "Sumber BAST berubah sejak unggahan; unggah dokumen yang sesuai sumber terbaru")
    data = await get_document_from_gridfs(doc["file_id"])
    if not data or hashlib.sha256(data).hexdigest() != doc["sha256"]:
        raise HTTPException(409, "Integritas arsip tidak sesuai. Pemeriksaan tidak dapat disahkan")
    checked = {**doc, "status": payload.status, "pemeriksaan": {
        "oleh": user.get("username") or "system", "catatan": catatan,
        "pada": datetime.now(timezone.utc).isoformat()}}
    hasil = {"ok": True, "dokumen_id": dokumen_id, "version": versi + 1}
    result = await _simpan(b, [checked if d["id"] == dokumen_id else d for d in docs],
                           versi, operasi, sidik, hasil)
    await log_audit("periksa_arsip_bast", "", username=checked["pemeriksaan"]["oleh"],
                    detail=f"Arsip BAST {b.get('nomor') or bast_id}: {dokumen_id}, {payload.status}; {catatan}")
    return result


@bast_dokumen_akhir_router.get("/bast/{bast_id}/dokumen-akhir/{dokumen_id}")
async def lihat_dokumen_akhir(bast_id: str, dokumen_id: str,
                             user: dict = Depends(require_user_or_query_token)):
    b = await _bast(bast_id, user)
    doc = next((d for d in b.get("dokumen_akhir") or [] if d["id"] == dokumen_id), None)
    if not doc:
        raise HTTPException(404, "Dokumen tidak ditemukan dalam BAST ini")
    data = await get_document_from_gridfs(doc["file_id"])
    if not data or hashlib.sha256(data).hexdigest() != doc["sha256"]:
        raise HTTPException(409, "Berkas tidak tersedia atau integritas arsip berubah")
    return StreamingResponse(io.BytesIO(data), media_type=doc["content_type"], headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc['filename'], safe='')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })
