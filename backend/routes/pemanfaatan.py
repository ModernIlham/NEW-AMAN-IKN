"""PEMANFAATAN — Fase 5 tahap awal: register perjanjian pemanfaatan BMN.

PMK 115/PMK.06/2020 (pustaka §6): register + arsip, bukan sistem uang —
persetujuan selalu di Pengelola Barang; PNBP disetor mitra langsung ke
Kas Negara. Status turunan menandai dokumen kurang / jatuh tempo ≤60
hari / berakhir. Kontribusi tahunan tercatat per tahun (NTPN) dengan
pengingat tunggakan; lampiran scan dokumen menyusul.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import delete_document_from_gridfs, get_document_from_gridfs
from pemanfaatan_utils import (
    BENTUK_PEMANFAATAN, LABEL_STATUS_PERJANJIAN, dokumen_kurang,
    peringatan_kontribusi, rekap_pemanfaatan, status_perjanjian,
    validate_kontribusi, validate_pemanfaatan,
)

pemanfaatan_router = APIRouter()

_PROJ = {"_id": 0}


class PemanfaatanIn(BaseModel):
    asset_id: str = ""            # opsional: tautan objek BMN
    bentuk: str
    mitra: str = Field(min_length=1)
    jenis_mitra: str = ""         # BUMN/BUMD/PT/koperasi/perorangan/Pemda...
    mulai: str
    berakhir: str
    nilai: float = 0              # nilai sewa total / kontribusi (informasi)
    nomor_persetujuan: str = ""   # persetujuan Pengelola Barang
    nomor_perjanjian: str = ""
    ntpn: str = ""                # bukti setor PNBP (wajib utk sewa aktif)
    kontribusi_tahunan: float = 0  # kewajiban PNBP per tahun (0 = tidak ada)
    keterangan: str = ""


class KontribusiIn(BaseModel):
    tahun: str = Field(min_length=4, max_length=4)
    ntpn: str = Field(min_length=1)
    tanggal: str = ""             # tanggal setor (default hari ini)
    jumlah: float = 0             # 0 = pakai nilai kontribusi_tahunan


@pemanfaatan_router.get("/pemanfaatan/bentuk")
async def daftar_bentuk(_user: dict = Depends(require_user)):
    """Daftar bentuk pemanfaatan + jangka maksimal untuk form."""
    return {"items": [
        {"key": k, "label": v[0], "maks_tahun": v[1], "dapat_perpanjang": v[2]}
        for k, v in BENTUK_PEMANFAATAN.items()
    ]}


@pemanfaatan_router.get("/pemanfaatan")
async def list_pemanfaatan(_user: dict = Depends(require_user)):
    """Register perjanjian + status turunan + ringkasan."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [p async for p in db.pemanfaatan.find({}, _PROJ)
             .sort("berakhir", 1).limit(500)]
    for p in items:
        p["status"] = status_perjanjian(p, today_iso)
        p["kekurangan"] = dokumen_kurang(p)
        p["peringatan_kontribusi"] = peringatan_kontribusi(p, today_iso)
    ringkasan = rekap_pemanfaatan(items, today_iso)
    return {"items": items, "ringkasan": ringkasan,
            "label_status": LABEL_STATUS_PERJANJIAN,
            "label_bentuk": {k: v[0] for k, v in BENTUK_PEMANFAATAN.items()},
            "catatan": (
                "Register penatausahaan — persetujuan di Pengelola Barang; "
                "PNBP disetor mitra langsung ke Kas Negara (PMK 115/2020). "
                "Status Aktif menuntut nomor persetujuan + perjanjian "
                "(sewa: + NTPN).")}


@pemanfaatan_router.post("/pemanfaatan")
async def buat_pemanfaatan(payload: PemanfaatanIn, user: dict = Depends(require_user)):
    """Catat satu perjanjian pemanfaatan."""
    data = payload.model_dump()
    errors = validate_pemanfaatan(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    objek = None
    if data.get("asset_id"):
        objek = await db.assets.find_one(
            {"id": data["asset_id"]},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
        if not objek:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": objek["id"] if objek else "",
        "asset_code": objek.get("asset_code") if objek else "",
        "NUP": objek.get("NUP") if objek else "",
        "asset_name": objek.get("asset_name") if objek else "",
        "bentuk": data["bentuk"],
        "mitra": data["mitra"].strip(),
        "jenis_mitra": str(data.get("jenis_mitra") or "").strip(),
        "mulai": str(data["mulai"]).strip()[:10],
        "berakhir": str(data["berakhir"]).strip()[:10],
        "nilai": float(data.get("nilai") or 0),
        "nomor_persetujuan": str(data.get("nomor_persetujuan") or "").strip(),
        "nomor_perjanjian": str(data.get("nomor_perjanjian") or "").strip(),
        "ntpn": str(data.get("ntpn") or "").strip(),
        "kontribusi_tahunan": float(data.get("kontribusi_tahunan") or 0),
        "kontribusi": [],
        "lampiran": [],
        "keterangan": str(data.get("keterangan") or "").strip(),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemanfaatan.insert_one({**record})
    return record


@pemanfaatan_router.put("/pemanfaatan/{register_id}")
async def ubah_pemanfaatan(register_id: str, payload: PemanfaatanIn,
                           user: dict = Depends(require_user)):
    """Perbarui perjanjian (melengkapi dokumen/nilai)."""
    data = payload.model_dump()
    errors = validate_pemanfaatan(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    update = {k: (str(v).strip() if isinstance(v, str) else v)
              for k, v in data.items() if k != "asset_id"}
    update["mulai"] = update["mulai"][:10]
    update["berakhir"] = update["berakhir"][:10]
    update["nilai"] = float(data.get("nilai") or 0)
    update["kontribusi_tahunan"] = float(data.get("kontribusi_tahunan") or 0)
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pemanfaatan.find_one_and_update(
        {"id": register_id}, {"$set": update},
        projection=_PROJ, return_document=True)
    if not res:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    return res


@pemanfaatan_router.post("/pemanfaatan/{register_id}/kontribusi")
async def catat_kontribusi(register_id: str, payload: KontribusiIn,
                           user: dict = Depends(require_user)):
    """Catat pembayaran kontribusi tahunan satu tahun (NTPN wajib)."""
    p = await db.pemanfaatan.find_one({"id": register_id}, _PROJ)
    if not p:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    today_iso = datetime.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_kontribusi(data, p, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    entri = {
        "tahun": data["tahun"].strip(),
        "ntpn": data["ntpn"].strip(),
        "tanggal": (str(data.get("tanggal") or "").strip()[:10] or today_iso),
        "jumlah": float(data.get("jumlah") or 0)
                  or float(p.get("kontribusi_tahunan") or 0),
        "oleh": user.get("username"),
    }
    res = await db.pemanfaatan.find_one_and_update(
        {"id": register_id},
        {"$push": {"kontribusi": entri},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        projection=_PROJ, return_document=True)
    res["peringatan_kontribusi"] = peringatan_kontribusi(res, today_iso)
    return res


# Arsip lampiran per perjanjian (pustaka §6: dokumen persetujuan/
# perjanjian/bukti setor tercecer = temuan auditor). Pola sama dengan
# unggah BAST aset: GridFS + validasi tipe/ukuran.
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


@pemanfaatan_router.post("/pemanfaatan/{register_id}/lampiran")
async def unggah_lampiran(register_id: str, file: UploadFile = File(...),
                          user: dict = Depends(require_user)):
    """Unggah scan dokumen perjanjian (PDF/gambar, maks 10MB, 10 berkas)."""
    p = await db.pemanfaatan.find_one(
        {"id": register_id}, {"_id": 0, "id": 1, "lampiran": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    if len(p.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per perjanjian")
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
                  "kind": "pemanfaatan", "register_id": register_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pemanfaatan.find_one_and_update(
        {"id": register_id},
        {"$push": {"lampiran": entri},
         "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@pemanfaatan_router.get("/pemanfaatan/{register_id}/lampiran/{file_id}")
async def unduh_lampiran(register_id: str, file_id: str, request: Request,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran (dipakai window.open → menerima header ATAU ?token)."""
    p = await db.pemanfaatan.find_one(
        {"id": register_id, "lampiran.file_id": file_id},
        {"_id": 0, "lampiran.$": 1})
    if not p or not p.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = p["lampiran"][0]
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


@pemanfaatan_router.delete("/pemanfaatan/{register_id}/lampiran/{file_id}")
async def hapus_lampiran(register_id: str, file_id: str,
                         _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pemanfaatan.update_one(
        {"id": register_id},
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pemanfaatan_router.delete("/pemanfaatan/{register_id}")
async def hapus_pemanfaatan(register_id: str, _admin: dict = Depends(require_admin)):
    """Hapus register salah input (khusus admin) + berkas lampirannya."""
    p = await db.pemanfaatan.find_one({"id": register_id},
                                      {"_id": 0, "lampiran": 1})
    res = await db.pemanfaatan.delete_one({"id": register_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    for lamp in (p or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": register_id}
