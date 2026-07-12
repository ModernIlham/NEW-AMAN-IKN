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
    BENTUK_PEMANFAATAN, DASAR_FASILITAS, LABEL_STATUS_PERJANJIAN,
    dokumen_kurang, peringatan_kontribusi, rekap_pemanfaatan,
    status_perjanjian, validate_fasilitas, validate_kontribusi,
    validate_pemanfaatan,
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
    # Fasilitas transaksi PMK 18/2024 / PMK 139/2022 (pendamping, opsional)
    dasar_fasilitas: str = "tanpa_fasilitas"
    nomor_penetapan_fasilitas: str = ""
    pelaksana_fasilitas: str = ""  # BUMN penugasan (mis. PT PII utk IKN)
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


@pemanfaatan_router.get("/pemanfaatan/export")
async def export_pemanfaatan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh register perjanjian pemanfaatan.

    Kolom register + status turunan + rekap kontribusi tercatat +
    jumlah lampiran — bahan olah lanjut/lampiran laporan (pola export
    persediaan; semua data nyata dari register).
    """
    import csv as csv_module
    import io

    today_iso = datetime.now(timezone.utc).date().isoformat()
    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["bentuk", "mitra", "jenis_mitra", "kode_aset", "nup",
                "nama_aset", "mulai", "berakhir", "status", "nilai",
                "kontribusi_tahunan", "kontribusi_tercatat_jumlah",
                "kontribusi_tercatat_total", "nomor_persetujuan",
                "nomor_perjanjian", "ntpn", "dasar_fasilitas",
                "nomor_penetapan_fasilitas", "jumlah_lampiran",
                "jumlah_lampiran_wasdal", "keterangan", "dibuat_oleh"])
    async for p in db.pemanfaatan.find({}, {"_id": 0}).sort("berakhir", 1):
        kontribusi = p.get("kontribusi") or []
        status = status_perjanjian(p, today_iso)
        w.writerow([
            BENTUK_PEMANFAATAN.get(p.get("bentuk"), (p.get("bentuk"),))[0],
            p.get("mitra"), p.get("jenis_mitra"),
            p.get("asset_code"), p.get("NUP"), p.get("asset_name"),
            p.get("mulai"), p.get("berakhir"),
            LABEL_STATUS_PERJANJIAN.get(status, status),
            p.get("nilai", 0), p.get("kontribusi_tahunan", 0),
            len(kontribusi),
            sum(float(k.get("jumlah") or 0) for k in kontribusi),
            p.get("nomor_persetujuan"), p.get("nomor_perjanjian"),
            p.get("ntpn"),
            DASAR_FASILITAS.get(p.get("dasar_fasilitas") or "tanpa_fasilitas",
                                p.get("dasar_fasilitas")),
            p.get("nomor_penetapan_fasilitas"),
            len(p.get("lampiran") or []),
            len(p.get("lampiran_wasdal") or []),
            p.get("keterangan"), p.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_pemanfaatan.csv"'})


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
            "label_dasar_fasilitas": DASAR_FASILITAS,
            "catatan": (
                "Register penatausahaan — persetujuan di Pengelola Barang; "
                "PNBP disetor mitra langsung ke Kas Negara (PMK 115/2020). "
                "Status Aktif menuntut nomor persetujuan + perjanjian "
                "(sewa: + NTPN).")}


@pemanfaatan_router.post("/pemanfaatan")
async def buat_pemanfaatan(payload: PemanfaatanIn, user: dict = Depends(require_user)):
    """Catat satu perjanjian pemanfaatan."""
    data = payload.model_dump()
    errors = validate_pemanfaatan(data) + validate_fasilitas(data)
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
        "dasar_fasilitas": str(data.get("dasar_fasilitas") or "tanpa_fasilitas").strip(),
        "nomor_penetapan_fasilitas": str(data.get("nomor_penetapan_fasilitas") or "").strip(),
        "pelaksana_fasilitas": str(data.get("pelaksana_fasilitas") or "").strip(),
        "kontribusi": [],
        "lampiran": [],
        "lampiran_wasdal": [],
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
    errors = validate_pemanfaatan(data) + validate_fasilitas(data)
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


async def _terima_lampiran(register_id: str, file: UploadFile, user: dict,
                           field: str, kind: str) -> dict:
    """Validasi + simpan satu lampiran GridFS lalu $push ke array `field`."""
    p = await db.pemanfaatan.find_one(
        {"id": register_id}, {"_id": 0, "id": 1, field: 1})
    if not p:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    if len(p.get(field) or []) >= _MAX_LAMPIRAN:
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
                  "kind": kind, "register_id": register_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pemanfaatan.find_one_and_update(
        {"id": register_id},
        {"$push": {field: entri},
         "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, field: 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    return {"message": "Lampiran terunggah", field: res.get(field) or []}


async def _stream_lampiran(register_id: str, file_id: str, request: Request,
                           field: str) -> Response:
    """Stream satu lampiran dari array `field` (ETag + 304)."""
    p = await db.pemanfaatan.find_one(
        {"id": register_id, f"{field}.file_id": file_id},
        {"_id": 0, f"{field}.$": 1})
    if not p or not p.get(field):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = p[field][0]
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


async def _buang_lampiran(register_id: str, file_id: str, field: str) -> dict:
    """$pull satu entri dari array `field` + hapus berkas GridFS-nya."""
    res = await db.pemanfaatan.update_one(
        {"id": register_id},
        {"$pull": {field: {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pemanfaatan_router.post("/pemanfaatan/{register_id}/lampiran")
async def unggah_lampiran(register_id: str, file: UploadFile = File(...),
                          user: dict = Depends(require_user)):
    """Unggah scan dokumen perjanjian (PDF/gambar, maks 10MB, 10 berkas)."""
    return await _terima_lampiran(register_id, file, user,
                                  "lampiran", "pemanfaatan")


@pemanfaatan_router.get("/pemanfaatan/{register_id}/lampiran/{file_id}")
async def unduh_lampiran(register_id: str, file_id: str, request: Request,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran (dipakai window.open → menerima header ATAU ?token)."""
    return await _stream_lampiran(register_id, file_id, request, "lampiran")


@pemanfaatan_router.delete("/pemanfaatan/{register_id}/lampiran/{file_id}")
async def hapus_lampiran(register_id: str, file_id: str,
                         _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    return await _buang_lampiran(register_id, file_id, "lampiran")


# Lampiran wasdal per perjanjian (pustaka §8: pemanfaatan adalah salah satu
# dari 5 objek pemantauan KPB — laporan monitoring/BA peninjauan lapangan
# diarsipkan TERPISAH dari dokumen perjanjian agar jejak wasdal jelas).

@pemanfaatan_router.post("/pemanfaatan/{register_id}/wasdal")
async def unggah_lampiran_wasdal(register_id: str, file: UploadFile = File(...),
                                 user: dict = Depends(require_user)):
    """Unggah laporan wasdal/BA peninjauan per perjanjian (PDF/gambar)."""
    return await _terima_lampiran(register_id, file, user,
                                  "lampiran_wasdal", "pemanfaatan_wasdal")


@pemanfaatan_router.get("/pemanfaatan/{register_id}/wasdal/{file_id}")
async def unduh_lampiran_wasdal(register_id: str, file_id: str, request: Request,
                                _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran wasdal (window.open → header ATAU ?token)."""
    return await _stream_lampiran(register_id, file_id, request,
                                  "lampiran_wasdal")


@pemanfaatan_router.delete("/pemanfaatan/{register_id}/wasdal/{file_id}")
async def hapus_lampiran_wasdal(register_id: str, file_id: str,
                                _admin: dict = Depends(require_admin)):
    """Hapus lampiran wasdal salah unggah (khusus admin)."""
    return await _buang_lampiran(register_id, file_id, "lampiran_wasdal")


@pemanfaatan_router.delete("/pemanfaatan/{register_id}")
async def hapus_pemanfaatan(register_id: str, _admin: dict = Depends(require_admin)):
    """Hapus register salah input (khusus admin) + berkas lampirannya."""
    p = await db.pemanfaatan.find_one(
        {"id": register_id}, {"_id": 0, "lampiran": 1, "lampiran_wasdal": 1})
    res = await db.pemanfaatan.delete_one({"id": register_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Register tidak ditemukan")
    semua = ((p or {}).get("lampiran") or []) + ((p or {}).get("lampiran_wasdal") or [])
    for lamp in semua:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": register_id}
