"""Tanda Tangan Digital — spesimen TTD & pemrosesan foto (Mandat-2).

Slice 1: kelola SPESIMEN tanda tangan per pejabat/pegawai (gambar PNG
transparan dari kanvas goresan mulus ATAU foto kertas yang di-hapus
background-nya via Pillow), tersimpan di GridFS. Blok tanda tangan PDF
(reports.py `_signature_block`) otomatis menyematkan spesimen KPB. Slice 2
(menyusul): e-sign via link per dokumen (`signature_requests`).
"""
import base64
import io

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import (
    cek_magic_gambar, delete_document_from_gridfs, get_document_from_gridfs,
    log_audit,
)
from ttd_utils import foto_ke_png_transparan, png_transparan_valid

ttd_router = APIRouter()

_ENTITAS = {"pejabat": db.pejabat, "pegawai": db.pegawai}


class SpesimenIn(BaseModel):
    png_base64: str   # data-URL atau base64 murni PNG transparan


def _png_dari_base64(s: str) -> bytes:
    raw = str(s or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="PNG base64 tidak valid")
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=400, detail="Berkas bukan PNG")
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Gambar TTD maksimal 4MB")
    return data


@ttd_router.post("/ttd/olah-foto")
async def olah_foto(file: UploadFile = File(...),
                    _user: dict = Depends(require_user)):
    """Foto TTD di kertas → PNG TRANSPARAN (hapus background otomatis). Balikan
    pratinjau data-URL base64; klien menampilkan lalu menyimpannya sebagai
    spesimen bila puas."""
    nama = str(file.filename or "").lower()
    ext = next((e for e in (".jpg", ".jpeg", ".png", ".webp") if nama.endswith(e)), "")
    if not ext:
        raise HTTPException(status_code=400, detail="Foto harus JPG/PNG/WEBP")
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto maksimal 12MB")
    if not cek_magic_gambar(data, ext):
        raise HTTPException(status_code=400, detail="Isi berkas tidak cocok ekstensi")
    try:
        png = foto_ke_png_transparan(data)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Gagal memproses foto — coba foto lebih terang/kontras")
    if not png_transparan_valid(png):
        raise HTTPException(status_code=400,
                            detail="Tanda tangan tak terdeteksi — pastikan goresan gelap di kertas terang")
    return {"png_base64": "data:image/png;base64," + base64.b64encode(png).decode()}


@ttd_router.put("/ttd/spesimen/{entitas}/{eid}")
async def simpan_spesimen(entitas: str, eid: str, payload: SpesimenIn,
                          admin: dict = Depends(require_admin)):
    """Simpan spesimen TTD (PNG transparan) untuk pejabat/pegawai → GridFS +
    field `ttd_file_id`. Spesimen lama dihapus (cegah orphan)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1, "nama": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{entitas} tidak ditemukan")
    data = _png_dari_base64(payload.png_base64)
    if not png_transparan_valid(data):
        raise HTTPException(status_code=400, detail="PNG TTD tidak valid / kosong")

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"ttd_{entitas}_{eid}.png",
        metadata={"content_type": "image/png", "kind": "ttd_spesimen",
                  "entitas": entitas, "eid": eid})
    await grid_in.write(data)
    await grid_in.close()

    lama = str(doc.get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": str(file_id)}})
    if lama and lama != str(file_id):
        await delete_document_from_gridfs(lama)
    await log_audit("simpan_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Spesimen TTD {entitas} {doc.get('nama') or eid}")
    return {"ok": True, "ttd_file_id": str(file_id)}


@ttd_router.get("/ttd/spesimen/{entitas}/{eid}")
async def lihat_spesimen(entitas: str, eid: str,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream gambar spesimen TTD (pratinjau)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1})
    fid = str((doc or {}).get("ttd_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404, detail="Spesimen TTD belum ada")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas TTD tidak ditemukan")
    return StreamingResponse(
        io.BytesIO(data), media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="ttd.png"',
                 "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "private, max-age=3600"})


@ttd_router.delete("/ttd/spesimen/{entitas}/{eid}")
async def hapus_spesimen(entitas: str, eid: str,
                         admin: dict = Depends(require_admin)):
    """Hapus spesimen TTD (dokumen kembali ke tanda tangan basah)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1})
    fid = str((doc or {}).get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": ""}})
    if fid:
        await delete_document_from_gridfs(fid)
    await log_audit("hapus_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Hapus spesimen TTD {entitas}")
    return {"ok": True}
