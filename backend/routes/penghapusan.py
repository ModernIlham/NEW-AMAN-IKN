"""PENGHAPUSAN — Fase 6: kandidat usul hapus + tiket usulan berstatus.

PMK 83/PMK.06/2016 (pustaka §1 & §7): jaring kandidat per jalur —
Tidak Ditemukan → penelusuran + telaah TGR; Rusak Berat → pemusnahan/
pemindahtanganan. Tiket usulan: diusulkan → diproses → SK terbit/ditolak
(transisi tervalidasi, riwayat tercatat, arsip nomor SK).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import delete_document_from_gridfs, get_document_from_gridfs, log_audit
from penghapusan_utils import (
    JALUR_KANDIDAT, STATUS_USULAN, build_asset_penghapusan_projection,
    jalur_kandidat, rekap_kandidat, validate_transisi,
)

penghapusan_router = APIRouter()


class UsulanIn(BaseModel):
    asset_id: str = Field(min_length=1)
    keterangan: str = ""


class TransisiIn(BaseModel):
    status: str
    nomor_sk: str = ""
    tanggal_sk: str = ""
    catatan: str = ""

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "condition": 1, "inventory_status": 1,
         "location": 1, "uraian_tidak_ditemukan": 1}
_MAKS_BARIS = 500


@penghapusan_router.get("/penghapusan/kandidat")
async def kandidat_penghapusan(_user: dict = Depends(require_user)):
    """Kandidat usul hapus per jalur + status usulan aktifnya (bila ada)."""
    assets = [a async for a in db.assets.find(
        {"$or": [{"inventory_status": "Tidak Ditemukan"},
                 {"condition": "Rusak Berat"}]}, _PROJ)]
    hasil = rekap_kandidat(assets)
    # Lekatkan status usulan aktif per aset agar UI tahu mana yang sudah diusulkan
    usulan_aktif = {}
    async for u in db.usulan_penghapusan.find(
            {"status": {"$ne": "ditolak"}},
            {"_id": 0, "asset_id": 1, "status": 1, "id": 1}):
        usulan_aktif[u["asset_id"]] = {"id": u["id"], "status": u["status"]}
    for b in hasil["jalur"].values():
        for r in b["rows"]:
            r["usulan"] = usulan_aktif.get(r["id"])
        b["dipangkas"] = len(b["rows"]) > _MAKS_BARIS
        b["rows"] = b["rows"][:_MAKS_BARIS]
    hasil["label_status"] = STATUS_USULAN
    hasil["catatan"] = (
        "Kandidat dijaring otomatis dari hasil inventarisasi (kondisi + "
        "status). Penghapusan formal tetap melalui usulan, persetujuan, dan "
        "SK sesuai PMK 83/2016 — nilai tersaji adalah nilai perolehan."
    )
    return hasil


@penghapusan_router.get("/penghapusan/usulan")
async def list_usulan(
    status: str = Query("", description="Saring satu status"),
    _user: dict = Depends(require_user),
):
    """Daftar tiket usulan penghapusan, terbaru dulu."""
    query = {}
    if status:
        if status not in STATUS_USULAN:
            valid = ", ".join(STATUS_USULAN)
            raise HTTPException(status_code=400,
                                detail=f"Status tidak dikenal (pilihan: {valid})")
        query["status"] = status
    items = [u async for u in db.usulan_penghapusan.find(query, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    return {"items": items, "jumlah": len(items), "label_status": STATUS_USULAN,
            "label_jalur": {k: v[0] for k, v in JALUR_KANDIDAT.items()}}


@penghapusan_router.get("/penghapusan/usulan/export")
async def export_usulan_penghapusan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh tiket usulan penghapusan (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["jalur", "kode_aset", "nup", "nama_aset", "status",
                "nomor_sk", "tanggal_sk", "tanggal_usulan", "keterangan",
                "jumlah_lampiran", "dibuat_oleh"])
    async for u in db.usulan_penghapusan.find({}, {"_id": 0}).sort("created_at", -1):
        w.writerow([
            JALUR_KANDIDAT.get(u.get("jalur"), (u.get("jalur"),))[0],
            u.get("asset_code"), u.get("NUP"), u.get("asset_name"),
            STATUS_USULAN.get(u.get("status"), u.get("status")),
            u.get("nomor_sk"), u.get("tanggal_sk"),
            str(u.get("created_at") or "")[:10], u.get("keterangan"),
            len(u.get("lampiran") or []), u.get("created_by"),
        ])
    return HttpResponse(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="register_usulan_penghapusan.csv"'})


@penghapusan_router.post("/penghapusan/usulan")
async def buat_usulan(payload: UsulanIn, user: dict = Depends(require_user)):
    """Buat tiket usulan penghapusan untuk satu aset kandidat."""
    asset = await db.assets.find_one({"id": payload.asset_id}, _PROJ)
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    jalur = jalur_kandidat(asset)
    if not jalur:
        raise HTTPException(
            status_code=400,
            detail="Aset bukan kandidat penghapusan (bukan Rusak Berat / Tidak Ditemukan)")
    aktif = await db.usulan_penghapusan.find_one(
        {"asset_id": payload.asset_id, "status": {"$ne": "ditolak"}}, {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(status_code=409,
                            detail="Aset ini sudah punya usulan penghapusan aktif")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "jalur": jalur,
        "status": "diusulkan",
        "nomor_sk": "",
        "tanggal_sk": "",
        "keterangan": str(payload.keterangan or "").strip(),
        "lampiran": [],
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.usulan_penghapusan.insert_one({**record})
    # Cek silang lintas register keluar (non-blocking, audit G5 #11).
    from shared_utils import proses_keluar_aktif
    lain = (await proses_keluar_aktif([asset["id"]])).get(asset["id"], [])
    lain = [x for x in lain if x != "usulan penghapusan"]
    record["peringatan_proses"] = (
        [f"Aset ini juga sedang dalam {', '.join(lain)} — periksa agar tidak dobel jalur keluar"]
        if lain else [])
    return record


async def _proyeksi_master_penghapusan(usulan: dict, oleh: str) -> bool:
    """Proyeksikan master aset saat SK penghapusan terbit (Prinsip 3 Bab 5).

    Best-effort & idempoten: SK sudah tercatat di register `usulan_penghapusan`
    (jurnal), jadi kegagalan/no-op proyeksi TIDAK menggagalkan transisi. Filter
    `dihapus != true` membuat pemanggilan ulang aman; `$inc version` mem-bust
    cache media/ETag dan memicu OCC 409 pada form edit yang masih terbuka atas
    aset itu (memang seharusnya konflik — asetnya baru saja dihapus). Tidak
    menyentuh field yang dibaca laporan → tanpa regresi laporan.
    """
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_penghapusan_projection(usulan, now)
    updated = await db.assets.find_one_and_update(
        {"id": usulan.get("asset_id"), "dihapus": {"$ne": True}},
        {"$set": proj, "$inc": {"version": 1}},
        projection={"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1,
                    "asset_name": 1, "NUP": 1},
        return_document=True,
    )
    if not updated:
        # Aset sudah dihapus/diproyeksikan atau tak ada lagi — SK tetap sah.
        return False
    await log_audit(
        "penghapusan", updated.get("activity_id", ""), updated.get("id", ""),
        updated.get("asset_code", ""), updated.get("asset_name", ""),
        username=oleh,
        detail=f"Aset dihapus dari master via SK penghapusan {proj['penghapusan']['nomor_sk']}".strip(),
        nup=updated.get("NUP", ""),
    )
    return True


@penghapusan_router.post("/penghapusan/usulan/{usulan_id}/status")
async def transisi_usulan(usulan_id: str, payload: TransisiIn,
                          admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (khusus admin — gerbang persetujuan)."""
    u = await db.usulan_penghapusan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    errors = validate_transisi(u["status"], payload.status, payload.nomor_sk)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": payload.status,
        "updated_at": now,
    }
    if payload.status == "sk_terbit":
        update["nomor_sk"] = payload.nomor_sk.strip()
        update["tanggal_sk"] = str(payload.tanggal_sk or "").strip()[:10]
    res = await db.usulan_penghapusan.find_one_and_update(
        # Status diikutkan di filter: dua admin yang berlomba tidak bisa
        # menerapkan transisi ganda dari status yang sama
        {"id": usulan_id, "status": u["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status usulan berubah oleh proses lain — muat ulang")
    # Proyeksi master (Prinsip 3): saat SK terbit, tandai aset `dihapus` di
    # db.assets + audit. Setelah transisi CAS sukses agar tak double-proyeksi.
    if payload.status == "sk_terbit":
        res["proyeksi_master"] = await _proyeksi_master_penghapusan(
            res, admin.get("username") or "system")
    return res


# Arsip lampiran per tiket (SK penghapusan + dokumen pendukung —
# PMK 83/2016). Pola sama dengan lampiran pemanfaatan/pemusnahan
# (#131/#132).
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


@penghapusan_router.post("/penghapusan/usulan/{usulan_id}/lampiran")
async def unggah_lampiran_usulan(usulan_id: str, file: UploadFile = File(...),
                                 user: dict = Depends(require_user)):
    """Unggah scan SK/dokumen pendukung (PDF/gambar, maks 10MB, 10 berkas)."""
    u = await db.usulan_penghapusan.find_one(
        {"id": usulan_id}, {"_id": 0, "id": 1, "lampiran": 1})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    if len(u.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per usulan")
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
                  "kind": "penghapusan", "usulan_id": usulan_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.usulan_penghapusan.find_one_and_update(
        {"id": usulan_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@penghapusan_router.get("/penghapusan/usulan/{usulan_id}/lampiran/{file_id}")
async def unduh_lampiran_usulan(usulan_id: str, file_id: str, request: Request,
                                _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran usulan (menerima header ATAU ?token)."""
    u = await db.usulan_penghapusan.find_one(
        {"id": usulan_id, "lampiran.file_id": file_id}, {"_id": 0, "lampiran.$": 1})
    if not u or not u.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = u["lampiran"][0]
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


@penghapusan_router.delete("/penghapusan/usulan/{usulan_id}/lampiran/{file_id}")
async def hapus_lampiran_usulan(usulan_id: str, file_id: str,
                                _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.usulan_penghapusan.update_one(
        {"id": usulan_id},
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@penghapusan_router.delete("/penghapusan/usulan/{usulan_id}")
async def hapus_usulan(usulan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (status diusulkan) + berkas lampirannya."""
    u = await db.usulan_penghapusan.find_one(
        {"id": usulan_id, "status": "diusulkan"}, {"_id": 0, "lampiran": 1})
    res = await db.usulan_penghapusan.delete_one(
        {"id": usulan_id, "status": "diusulkan"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    for lamp in (u or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": usulan_id}
