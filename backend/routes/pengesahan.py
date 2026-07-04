"""Pengesahan (finalization) workflow + nomor tiket kegiatan + kartu inventarisasi.

Alur:
  1. Setiap kegiatan mendapat `ticket_number` "INV-{tahun}-{seq:04d}" (berurutan
     per tahun, atomik via koleksi `counters` + findOneAndUpdate $inc upsert).
  2. Kegiatan hanya bisa disahkan bila SEMUA aset sudah diinventarisasi
     (inventory_status != "Belum Diinventarisasi") dan SEMUA aset punya foto,
     serta minimal 1 dokumen pengesahan (PDF bertanda tangan) sudah diunggah.
  3. Saat disahkan: kegiatan dikunci (status_pengesahan="disahkan") dan SATU
     record riwayat per aset ditulis ke koleksi `inventory_history` — dasar
     "Kartu Inventarisasi" lintas kegiatan per identitas aset.
"""
import io
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import Response
from pymongo import ReturnDocument

from db import db, fs_bucket
from auth_utils import require_admin
from shared_utils import log_audit, delete_document_from_gridfs, get_document_from_gridfs

logger = logging.getLogger(__name__)
pengesahan_router = APIRouter()

MAX_PENGESAHAN_PDF_BYTES = 20 * 1024 * 1024  # 20MB

# Same Cache-Control posture as asset media streaming (routes/assets.py)
MEDIA_CACHE_CONTROL = "private, max-age=86400"


# ============================================================================
# NOMOR TIKET KEGIATAN — INV-{tahun}-{seq:04d}
# ============================================================================

def _year_from_created_at(created_at: str) -> int:
    """Ambil tahun dari ISO timestamp created_at; fallback tahun berjalan."""
    try:
        return int(str(created_at)[:4])
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).year


async def next_ticket_number(year: Optional[int] = None) -> str:
    """Nomor tiket berikutnya untuk `year` — atomik via counters findOneAndUpdate.

    Aman dipanggil bersamaan dari banyak worker: $inc pada dokumen counter
    adalah operasi atomik MongoDB, jadi dua pemanggil tidak pernah mendapat
    sequence yang sama.
    """
    year = year or datetime.now(timezone.utc).year
    counter = await db.counters.find_one_and_update(
        {"_id": f"inventory_activity_ticket_{year}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"INV-{year}-{int(counter['seq']):04d}"


async def ensure_ticket_number(activity: Optional[dict]) -> Optional[dict]:
    """Backfill malas: beri ticket_number pada kegiatan lama yang belum punya.

    Guard `{"ticket_number": {"$exists": False}}` membuat pemanggilan paralel
    aman — hanya satu penulis yang menang; yang kalah membaca ulang nilai
    yang sudah tersimpan (celah sequence yang terbuang tidak masalah).
    """
    if not activity or activity.get("ticket_number"):
        return activity
    aid = activity.get("id")
    if not aid:
        return activity
    ticket = await next_ticket_number(_year_from_created_at(activity.get("created_at")))
    result = await db.inventory_activities.update_one(
        {"id": aid, "ticket_number": {"$exists": False}},
        {"$set": {"ticket_number": ticket}},
    )
    if result.matched_count:
        activity["ticket_number"] = ticket
    else:
        fresh = await db.inventory_activities.find_one({"id": aid}, {"_id": 0, "ticket_number": 1})
        activity["ticket_number"] = (fresh or {}).get("ticket_number", "")
    return activity


async def backfill_ticket_numbers() -> int:
    """Backfill startup: kegiatan lama tanpa ticket_number diberi nomor
    berurutan (created_at menaik, agar kegiatan tertua bernomor terkecil).
    Idempotent & aman multi-worker (guard $exists:False per dokumen)."""
    count = 0
    cursor = db.inventory_activities.find(
        {"ticket_number": {"$exists": False}},
        {"_id": 0, "id": 1, "created_at": 1},
    ).sort("created_at", 1)
    async for act in cursor:
        await ensure_ticket_number(act)
        count += 1
    if count:
        logger.info(f"Ticket backfill: {count} kegiatan diberi nomor tiket")
    return count


# ============================================================================
# ELIGIBILITY (syarat pengesahan)
# ============================================================================

def _empty_field_filter(field: str) -> dict:
    """Filter: field kosong (\"\"), null, atau tidak ada sama sekali."""
    return {"$or": [{field: {"$in": ["", None]}}, {field: {"$exists": False}}]}


async def _pengesahan_counts(activity_id: str) -> dict:
    """Hitung syarat pengesahan — filter identik dengan /completion-status."""
    pending_filter = {
        "activity_id": activity_id,
        "$or": [
            {"inventory_status": {"$in": ["", "Belum Diinventarisasi", None]}},
            {"inventory_status": {"$exists": False}},
        ],
    }
    no_photo_filter = {
        "activity_id": activity_id,
        "$and": [
            {"$or": [{"photos": {"$exists": False}}, {"photos": {"$size": 0}}]},
            {"$or": [{"photo_gridfs_ids": {"$exists": False}}, {"photo_gridfs_ids": {"$size": 0}}]},
        ],
    }
    pending = await db.assets.count_documents(pending_filter)
    no_photo = await db.assets.count_documents(no_photo_filter)
    total = await db.assets.count_documents({"activity_id": activity_id})
    # Syarat data lengkap tambahan:
    #   - tidak boleh ada aset kategori "dummy" yang tersisa
    #   - semua aset punya kode_register, eselon (I atau II), lokasi, dan pengguna
    kategori_dummy = await db.assets.count_documents({
        "activity_id": activity_id,
        "category": {"$regex": "dummy", "$options": "i"},
    })
    tanpa_kode_register = await db.assets.count_documents({
        "activity_id": activity_id, **_empty_field_filter("kode_register"),
    })
    tanpa_eselon = await db.assets.count_documents({
        "activity_id": activity_id,
        "$and": [_empty_field_filter("eselon1"), _empty_field_filter("eselon2")],
    })
    tanpa_lokasi = await db.assets.count_documents({
        "activity_id": activity_id, **_empty_field_filter("location"),
    })
    tanpa_pengguna = await db.assets.count_documents({
        "activity_id": activity_id, **_empty_field_filter("user"),
    })
    counts = {
        "belum_diinventarisasi": pending,
        "tanpa_foto": no_photo,
        "kategori_dummy": kategori_dummy,
        "tanpa_kode_register": tanpa_kode_register,
        "tanpa_eselon": tanpa_eselon,
        "tanpa_lokasi": tanpa_lokasi,
        "tanpa_pengguna": tanpa_pengguna,
        "total": total,
    }
    counts["eligible"] = total > 0 and all(
        counts[k] == 0 for k in (
            "belum_diinventarisasi", "tanpa_foto", "kategori_dummy",
            "tanpa_kode_register", "tanpa_eselon", "tanpa_lokasi", "tanpa_pengguna",
        )
    )
    return counts


def _pengesahan_problems(counts: dict) -> list:
    """Daftar masalah (Indonesia) untuk counts yang belum nol — dipakai pesan 400."""
    labels = [
        ("belum_diinventarisasi", "aset belum diinventarisasi"),
        ("tanpa_foto", "aset tanpa foto"),
        ("kategori_dummy", "aset masih berkategori dummy"),
        ("tanpa_kode_register", "aset tanpa kode register"),
        ("tanpa_eselon", "aset tanpa Eselon I/II"),
        ("tanpa_lokasi", "aset tanpa lokasi"),
        ("tanpa_pengguna", "aset tanpa pengguna"),
    ]
    return [f"{counts[key]} {label}" for key, label in labels if counts.get(key)]


def _dokumen_meta(activity: dict) -> list:
    """Metadata dokumen pengesahan (tanpa gridfs_id internal)."""
    return [
        {
            "id": d.get("id", ""),
            "name": d.get("name", "dokumen.pdf"),
            "size": d.get("size", 0),
            "uploaded_at": d.get("uploaded_at", ""),
            "uploaded_by": d.get("uploaded_by", ""),
        }
        for d in (activity.get("pengesahan_dokumen") or [])
        if isinstance(d, dict)
    ]


@pengesahan_router.get("/inventory-activities/{activity_id}/pengesahan-status")
async def get_pengesahan_status(activity_id: str):
    """Status kelayakan pengesahan sebuah kegiatan (dipanggil saat dialog dibuka)."""
    activity = await db.inventory_activities.find_one(
        {"id": activity_id},
        {"_id": 0, "id": 1, "created_at": 1, "ticket_number": 1, "nama_kegiatan": 1,
         "status_pengesahan": 1, "disahkan_at": 1, "disahkan_by": 1, "pengesahan_dokumen": 1},
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    activity = await ensure_ticket_number(activity)
    counts = await _pengesahan_counts(activity_id)
    status = activity.get("status_pengesahan") or "draft"
    return {
        "activity_id": activity_id,
        "ticket_number": activity.get("ticket_number", ""),
        "status": status,
        "disahkan_at": activity.get("disahkan_at", ""),
        "disahkan_by": activity.get("disahkan_by", ""),
        "dokumen": _dokumen_meta(activity),
        **counts,
        # Sudah disahkan → tidak bisa disahkan ulang
        "eligible": counts["eligible"] and status != "disahkan",
    }


# ============================================================================
# DOKUMEN PENGESAHAN (PDF bertanda tangan — wajib sebelum sahkan)
# ============================================================================

@pengesahan_router.post("/inventory-activities/{activity_id}/pengesahan-dokumen")
async def upload_pengesahan_dokumen(
    activity_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
):
    """Unggah dokumen pengesahan (PDF, maks 20MB) — bisa lebih dari satu."""
    activity = await db.inventory_activities.find_one(
        {"id": activity_id}, {"_id": 0, "id": 1, "status_pengesahan": 1}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    if activity.get("status_pengesahan") == "disahkan":
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Dokumen pengesahan harus berformat PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(pdf_bytes) > MAX_PENGESAHAN_PDF_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran dokumen maksimal 20MB")
    if not pdf_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    # Simpan ke GridFS (pola sama dengan foto/dokumen kegiatan)
    from bson import ObjectId
    file_id = ObjectId()
    try:
        grid_in = fs_bucket.open_upload_stream_with_id(
            file_id,
            filename=filename,
            metadata={"content_type": "application/pdf", "size": len(pdf_bytes),
                      "kind": "pengesahan_dokumen", "activity_id": activity_id},
        )
        await grid_in.write(pdf_bytes)
        await grid_in.close()
    except Exception as e:
        logger.error(f"GridFS store pengesahan dokumen gagal: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan dokumen")

    doc_entry = {
        "id": str(uuid.uuid4()),
        "name": filename,
        "gridfs_id": str(file_id),
        "size": len(pdf_bytes),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": admin.get("name") or admin.get("username") or "admin",
    }
    # Guard status pada write juga — pengesahan yang menyelip antara read dan
    # write tidak boleh menambah dokumen ke kegiatan terkunci.
    result = await db.inventory_activities.update_one(
        {"id": activity_id, "status_pengesahan": {"$ne": "disahkan"}},
        {"$push": {"pengesahan_dokumen": doc_entry}},
    )
    if result.matched_count == 0:
        await delete_document_from_gridfs(doc_entry["gridfs_id"])
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    logger.info(f"Pengesahan dokumen diunggah untuk kegiatan {activity_id}: {filename}")
    return {
        "message": "Dokumen pengesahan berhasil diunggah",
        "dokumen": {k: v for k, v in doc_entry.items() if k != "gridfs_id"},
    }


@pengesahan_router.delete("/inventory-activities/{activity_id}/pengesahan-dokumen/{doc_id}")
async def delete_pengesahan_dokumen(
    activity_id: str,
    doc_id: str,
    _admin: dict = Depends(require_admin),
):
    """Hapus dokumen pengesahan — hanya selama kegiatan masih draft."""
    activity = await db.inventory_activities.find_one(
        {"id": activity_id}, {"_id": 0, "status_pengesahan": 1, "pengesahan_dokumen": 1}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    if activity.get("status_pengesahan") == "disahkan":
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    docs = activity.get("pengesahan_dokumen") or []
    target = next((d for d in docs if isinstance(d, dict) and d.get("id") == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    await db.inventory_activities.update_one(
        {"id": activity_id},
        {"$pull": {"pengesahan_dokumen": {"id": doc_id}}},
    )
    if target.get("gridfs_id"):
        await delete_document_from_gridfs(target["gridfs_id"])
    return {"message": "Dokumen pengesahan dihapus"}


@pengesahan_router.get("/inventory-activities/{activity_id}/pengesahan-dokumen/{doc_id}")
async def get_pengesahan_dokumen(activity_id: str, doc_id: str, request: Request):
    """Stream dokumen pengesahan (PDF). GET publik — dikonsumsi window.open()
    yang tidak bisa membawa Authorization header, mengikuti posture endpoint
    media lain di aplikasi ini. Cacheable di browser (dokumen immutable)."""
    activity = await db.inventory_activities.find_one(
        {"id": activity_id}, {"_id": 0, "pengesahan_dokumen": 1}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    docs = activity.get("pengesahan_dokumen") or []
    target = next((d for d in docs if isinstance(d, dict) and d.get("id") == doc_id), None)
    if not target or not target.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    etag = f'"pengesahan-{doc_id}"'
    if request.headers.get("if-none-match", "").strip() == etag:
        return Response(status_code=304, headers={"Cache-Control": MEDIA_CACHE_CONTROL, "ETag": etag})

    pdf_bytes = await get_document_from_gridfs(target["gridfs_id"])
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="File dokumen tidak tersedia")
    name = target.get("name", "dokumen.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Cache-Control": MEDIA_CACHE_CONTROL,
            "ETag": etag,
            "Content-Disposition": f'inline; filename="{name}"',
        },
    )


# ============================================================================
# SAHKAN — kunci kegiatan + tulis riwayat per aset
# ============================================================================

# Field yang disalin dari aset ke record riwayat (satu record per aset)
_HISTORY_ASSET_PROJECTION = {
    "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "kode_register": 1,
    "asset_name": 1, "inventory_status": 1, "condition": 1, "location": 1,
    "user": 1, "eselon1": 1,
}


@pengesahan_router.post("/inventory-activities/{activity_id}/sahkan")
async def sahkan_activity(activity_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Sahkan (finalisasi) kegiatan: validasi syarat → kunci → tulis riwayat."""
    activity = await db.inventory_activities.find_one(
        {"id": activity_id},
        {"_id": 0, "id": 1, "nama_kegiatan": 1, "created_at": 1, "ticket_number": 1,
         "status_pengesahan": 1, "pengesahan_dokumen": 1, "kode_satker": 1, "nama_satker": 1},
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    if activity.get("status_pengesahan") == "disahkan":
        raise HTTPException(status_code=400, detail="Kegiatan sudah disahkan sebelumnya")

    counts = await _pengesahan_counts(activity_id)
    if counts["total"] == 0:
        raise HTTPException(status_code=400, detail="Kegiatan belum memiliki aset — tidak ada yang bisa disahkan")
    if not counts["eligible"]:
        raise HTTPException(
            status_code=400,
            detail="Belum memenuhi syarat pengesahan: " + ", ".join(_pengesahan_problems(counts)),
        )
    if not (activity.get("pengesahan_dokumen") or []):
        raise HTTPException(status_code=400, detail="Unggah minimal 1 dokumen pengesahan (PDF bertanda tangan) terlebih dahulu")

    activity = await ensure_ticket_number(activity)
    ticket_number = activity.get("ticket_number", "")
    disahkan_at = datetime.now(timezone.utc).isoformat()
    disahkan_by = admin.get("name") or admin.get("username") or "admin"

    # Kunci secara atomik — guard $ne memastikan hanya satu request yang menang
    result = await db.inventory_activities.update_one(
        {"id": activity_id, "status_pengesahan": {"$ne": "disahkan"}},
        {"$set": {
            "status_pengesahan": "disahkan",
            "disahkan_at": disahkan_at,
            "disahkan_by": disahkan_by,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail="Kegiatan sudah disahkan sebelumnya")

    # Tulis SATU record riwayat per aset kegiatan ini. kode_satker/nama_satker
    # kegiatan ikut disalin agar Kartu Inventarisasi bisa memfilter riwayat
    # identitas aset yang sama per satuan kerja.
    activity_name = activity.get("nama_kegiatan", "")
    kode_satker = activity.get("kode_satker", "") or ""
    nama_satker = activity.get("nama_satker", "") or ""
    history_docs = []
    cursor = db.assets.find({"activity_id": activity_id}, _HISTORY_ASSET_PROJECTION)
    async for a in cursor:
        history_docs.append({
            "id": str(uuid.uuid4()),
            "activity_id": activity_id,
            "ticket_number": ticket_number,
            "activity_name": activity_name,
            "kode_satker": kode_satker,
            "nama_satker": nama_satker,
            "tanggal_pengesahan": disahkan_at,
            "asset_id": a.get("id", ""),
            "asset_code": a.get("asset_code", ""),
            "NUP": a.get("NUP", ""),
            "kode_register": a.get("kode_register", ""),
            "asset_name": a.get("asset_name", ""),
            "inventory_status": a.get("inventory_status", ""),
            "condition": a.get("condition", ""),
            "location": a.get("location", ""),
            "user": a.get("user", ""),
            "eselon1": a.get("eselon1", ""),
        })
    if history_docs:
        await db.inventory_history.insert_many(history_docs)

    audit_user = request.headers.get("X-Audit-User", disahkan_by)
    await log_audit(
        "sahkan", activity_id, "", "", "", audit_user,
        detail=f"Kegiatan disahkan (tiket {ticket_number}) — {len(history_docs)} riwayat aset dicatat",
    )
    logger.info(f"Kegiatan {activity_id} disahkan oleh {disahkan_by}: {len(history_docs)} riwayat ditulis")

    return {
        "message": f"Kegiatan berhasil disahkan (tiket {ticket_number})",
        "ticket_number": ticket_number,
        "disahkan_at": disahkan_at,
        "disahkan_by": disahkan_by,
        "history_count": len(history_docs),
    }


# ============================================================================
# KARTU INVENTARISASI — riwayat lintas kegiatan per identitas aset
# ============================================================================

@pengesahan_router.get("/assets/kartu-inventarisasi")
async def get_kartu_inventarisasi(kode_register: str = "", asset_code: str = "", NUP: str = "", kode_satker: str = ""):
    """Riwayat pengesahan sebuah aset lintas kegiatan.

    Identitas: prioritas kode_register; fallback (asset_code, NUP).
    kode_satker (opsional, dikirim frontend dari kegiatan aktif): riwayat
    dibatasi pada satuan kerja yang SAMA — identitas aset yang kebetulan sama
    di satker lain tidak ikut tampil. Record lama tanpa kode_satker (ditulis
    sebelum field ini ada) tetap disertakan; frontend menandainya sebagai legacy.
    NOTE: route ini dideklarasikan di router yang dimuat SEBELUM assets_router
    agar tidak tertangkap /assets/{asset_id}.
    """
    kode_register = (kode_register or "").strip()
    asset_code = (asset_code or "").strip()
    NUP = (NUP or "").strip()
    kode_satker = (kode_satker or "").strip()

    if kode_register:
        identity_query = {"kode_register": kode_register}
    elif asset_code:
        identity_query = {"asset_code": asset_code}
        if NUP:
            identity_query["NUP"] = NUP
    else:
        raise HTTPException(status_code=400, detail="Isi kode_register atau asset_code untuk mencari kartu inventarisasi")

    query = dict(identity_query)
    if kode_satker:
        query["$or"] = [
            {"kode_satker": kode_satker},
            # Legacy: record ditulis sebelum kode_satker dicatat — tetap tampil
            {"kode_satker": {"$in": ["", None]}},
            {"kode_satker": {"$exists": False}},
        ]

    history = await db.inventory_history.find(query, {"_id": 0}).sort(
        [("tanggal_pengesahan", -1), ("ticket_number", -1)]
    ).to_list(200)

    # Header identitas: aset terbaru dengan identitas yang sama (tanpa filter
    # satker — aset tidak menyimpan kode_satker); fallback ke record riwayat
    # teratas bila asetnya sudah tidak ada.
    asset = await db.assets.find_one(
        identity_query,
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "kode_register": 1,
         "asset_name": 1, "category": 1, "location": 1, "user": 1, "eselon1": 1},
        sort=[("created_at", -1)],
    )
    if not asset and history:
        h = history[0]
        asset = {
            "id": h.get("asset_id", ""),
            "asset_code": h.get("asset_code", ""),
            "NUP": h.get("NUP", ""),
            "kode_register": h.get("kode_register", ""),
            "asset_name": h.get("asset_name", ""),
            "location": h.get("location", ""),
            "user": h.get("user", ""),
            "eselon1": h.get("eselon1", ""),
        }

    return {
        "asset": asset,
        "history": history,
        "total": len(history),
        "query": {"kode_register": kode_register, "asset_code": asset_code, "NUP": NUP, "kode_satker": kode_satker},
    }
