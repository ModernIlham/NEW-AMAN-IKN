"""
Batch operations & row locking routes.
Extracted from assets.py for clean separation of concerns.
Provides: lock/unlock/heartbeat, batch-update, groups, all-ids
"""
import io
import re
import uuid
import base64
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import (APIRouter, HTTPException, Query, Request, Header,
                     Depends)
from pydantic import BaseModel
from pymongo import UpdateOne, ReturnDocument
from pymongo.errors import DuplicateKeyError

from asset_fields import BATCHABLE_FIELD_NAMES
from meili_utils import jadwalkan_sync_id
from spasial_utils import sisip_geo_ke_update
from auth_utils import require_user, require_writer
from db import db
from shared_utils import (
    invalidate_asset_cache, log_audit,
    create_thumbnail, create_gallery_thumbnail,
    store_photo_to_gridfs, delete_photo_from_gridfs, generate_photo_thumbnail,
    SEALED_DETAIL,
)
from routes.websocket import notify_asset_change
from routes.media import auto_compress_image

logger = logging.getLogger(__name__)
batch_router = APIRouter()

# --- Row Locking for Concurrent Editing (Persistent via MongoDB) ---
# 60s: the 15s frontend heartbeat tolerates 3 missed beats, and a crashed
# client frees the row in <=1 minute (was 5 minutes).
LOCK_TTL_SECONDS = 60

class LockRequest(BaseModel):
    asset_id: str

@batch_router.post("/assets/lock")
async def lock_asset(data: LockRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None), _user: dict = Depends(require_writer)):
    """Lock an asset row for editing. Atomic lock acquisition via find_one_and_update + insert fallback.
    Race-free: guaranteed only one user can hold the lock at any time."""
    asset_id = data.asset_id
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
    session_id = x_session_id or "unknown-session"

    # activity_id disalin ke dokumen lock supaya polling GET /assets/locks bisa
    # membaca row_locks langsung per kegiatan — tidak lagi mengambil puluhan
    # ribu id aset dari db.assets pada SETIAP poll.
    asset_doc = await db.assets.find_one({"id": asset_id}, {"_id": 0, "activity_id": 1})
    lock_doc = {
        "asset_id": asset_id,
        "activity_id": (asset_doc or {}).get("activity_id", "") or "",
        "user_id": x_user_id or "unknown",
        "user_name": x_user_name or "Unknown",
        "session_id": session_id,
        "locked_at": now.isoformat(),
        "expires_at": expires_at,
    }

    # STEP 1: Try to acquire the lock atomically IF it's expired OR held by same session.
    # This single DB call prevents the read-then-write race condition.
    result = await db.row_locks.find_one_and_update(
        {
            "asset_id": asset_id,
            "$or": [
                {"expires_at": {"$lte": now}},      # expired lock — steal it
                {"session_id": session_id},          # our own session — renew it
            ],
        },
        {"$set": lock_doc},
        return_document=ReturnDocument.AFTER,
    )
    if result is not None:
        return {"locked": True}

    # STEP 2: No existing lock found (or existing one belongs to another active user).
    # Try to insert fresh lock — unique index on asset_id ensures atomicity.
    try:
        await db.row_locks.insert_one(lock_doc)
        return {"locked": True}
    except DuplicateKeyError:
        # Another user got the lock first (or still active). Return who holds it.
        existing = await db.row_locks.find_one({"asset_id": asset_id})
        if not existing:
            # Rare race: lock expired between steps — retry once
            try:
                await db.row_locks.insert_one(lock_doc)
                return {"locked": True}
            except DuplicateKeyError:
                existing = await db.row_locks.find_one({"asset_id": asset_id})
        return {
            "locked": False,
            "locked_by": (existing or {}).get("user_name", "Unknown"),
            "locked_by_id": (existing or {}).get("user_id", ""),
        }

@batch_router.post("/assets/heartbeat")
async def heartbeat_lock(data: LockRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None), _user: dict = Depends(require_writer)):
    """Renew lock TTL (heartbeat). Call every ~15s while editing."""
    asset_id = data.asset_id
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
    session_id = x_session_id or "unknown-session"

    result = await db.row_locks.update_one(
        {"asset_id": asset_id, "session_id": session_id},
        {"$set": {"expires_at": expires_at}}
    )
    return {"renewed": result.modified_count > 0}

@batch_router.post("/assets/unlock")
async def unlock_asset(data: LockRequest, request: Request, x_user_id: str = Header(None), x_session_id: str = Header(None), _user: dict = Depends(require_writer)):
    """Release the lock on an asset row."""
    asset_id = data.asset_id
    session_id = x_session_id or "unknown-session"
    await db.row_locks.delete_one({"asset_id": asset_id, "session_id": session_id})
    return {"unlocked": True}

@batch_router.get("/assets/locks")
async def get_all_locks(request: Request, activity_id: str = "", _user: dict = Depends(require_user)):
    """Get currently active (non-expired) locks. Optional activity_id filter for efficient per-activity polling.
    Also filters out expired locks defensively even if TTL index hasn't purged yet."""
    now = datetime.now(timezone.utc)
    locks = {}
    query = {"expires_at": {"$gt": now}}
    if activity_id:
        # activity_id tersimpan di dokumen lock (didenormalisasi saat akuisisi)
        # → cukup baca row_locks langsung, tanpa mengambil id aset dari db.assets
        # di tiap poll. $exists:false = kompatibilitas lock lama sesaat setelah
        # deploy (lock kedaluwarsa sendiri dalam hitungan menit).
        query["$or"] = [{"activity_id": activity_id}, {"activity_id": {"$exists": False}}]
    cursor = db.row_locks.find(query, {"_id": 0, "asset_id": 1, "user_name": 1, "user_id": 1, "session_id": 1})
    async for doc in cursor:
        locks[doc["asset_id"]] = {
            "user_name": doc["user_name"],
            "user_id": doc["user_id"],
            "session_id": doc.get("session_id", ""),
        }
    return {"locks": locks}

# --- Batch Update ---
class BatchUpdateRequest(BaseModel):
    asset_ids: List[str]
    updates: dict  # Fields to update: category, location, condition, inventory_status, stiker_status, stiker_ukuran, eselon1, eselon2

# Diturunkan dari registry (asset_fields.py, flag `batchable`) supaya selalu
# selaras dengan field yang bisa diedit di form aset dan tidak drift lagi.
BATCH_ALLOWED_FIELDS = set(BATCHABLE_FIELD_NAMES)

# Fields that need special handling (not simple $set)
BATCH_SPECIAL_FIELDS = {"batch_photo", "batch_photos", "document_checklist_items"}

@batch_router.put("/assets/batch-update")
async def batch_update_assets(data: BatchUpdateRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None), _user: dict = Depends(require_writer)):
    """Batch update multiple assets with the same field values."""
    if not data.asset_ids:
        raise HTTPException(status_code=400, detail="Tidak ada aset yang dipilih")
    if not data.updates:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan yang dikirim")

    # ISOLASI SATKER (M-SCOPE): seluruh aset terpilih harus milik kegiatan
    # satker user — satu saja milik satker lain → 403 (tolak seluruh batch).
    from shared_utils import kode_satker_user, pastikan_akses_kegiatan_id
    if kode_satker_user(_user):
        for _aid in await db.assets.distinct("activity_id", {"id": {"$in": data.asset_ids}}):
            await pastikan_akses_kegiatan_id(_user, _aid)

    # Filter only allowed fields
    clean_updates = {k: v for k, v in data.updates.items() if k in BATCH_ALLOWED_FIELDS and v is not None}

    # Handle __clear__ sentinel: convert to empty string for DB
    for k, v in list(clean_updates.items()):
        if v == "__clear__":
            clean_updates[k] = ""

    # Setelan opt-in "wajib pegawai terdaftar" berlaku juga utk ubah massal
    # (temuan #29 — dulu hanya create/PUT/PATCH tunggal yang menegakkan).
    if clean_updates.get("pengguna_nip"):
        from shared_utils import enforce_pegawai_terdaftar
        await enforce_pegawai_terdaftar(clean_updates["pengguna_nip"])

    # Handle batch photo(s): terima `batch_photo` (tunggal, kompat lama) ATAU
    # `batch_photos` (banyak) → gabung jadi satu daftar data-URL, batasi 6 foto.
    batch_photo = data.updates.get("batch_photo")
    batch_photos_in = data.updates.get("batch_photos")
    photo_list = []
    if isinstance(batch_photo, str) and batch_photo.startswith("data:"):
        photo_list.append(batch_photo)
    if isinstance(batch_photos_in, list):
        photo_list += [p for p in batch_photos_in if isinstance(p, str) and p.startswith("data:")]
    photo_list = photo_list[:6]  # tak mungkin > 6 foto per aset
    has_photo = len(photo_list) > 0

    # Handle clear photos (remove all photos from selected assets)
    should_clear_photos = data.updates.get("clear_photos") is True

    # Handle clear document checklist
    should_clear_doc_checklist = data.updates.get("clear_document_checklist") is True

    # Handle document checklist items
    doc_checklist_items = data.updates.get("document_checklist_items")
    has_doc_checklist = doc_checklist_items and isinstance(doc_checklist_items, list) and len(doc_checklist_items) > 0

    if not clean_updates and not has_photo and not has_doc_checklist and not should_clear_photos and not should_clear_doc_checklist:
        raise HTTPException(status_code=400, detail="Tidak ada field valid untuk diupdate")

    # Kegiatan yang sudah disahkan terkunci: kumpulkan activity_id target
    # (distinct — batch hampir selalu 1 kegiatan) lalu satu lookup ber-indeks.
    target_activity_ids = [
        aid for aid in await db.assets.distinct("activity_id", {"id": {"$in": data.asset_ids}}) if aid
    ]
    if target_activity_ids:
        sealed = await db.inventory_activities.find_one(
            {"id": {"$in": target_activity_ids}, "status_pengesahan": "disahkan"},
            {"_id": 0, "id": 1},
        )
        if sealed:
            raise HTTPException(status_code=423, detail=SEALED_DETAIL)

    # Skip lock check for large batches (own batch action) — only check for small batches
    session_id = x_session_id or "unknown-session"
    if len(data.asset_ids) <= 50:
        locked_assets = []
        cursor = db.row_locks.find({"asset_id": {"$in": data.asset_ids}, "session_id": {"$ne": session_id}}, {"_id": 0, "asset_id": 1, "user_name": 1})
        async for lock in cursor:
            locked_assets.append(f"{lock['asset_id']} (oleh {lock['user_name']})")
        if locked_assets:
            raise HTTPException(status_code=409, detail=f"Aset terkunci: {', '.join(locked_assets[:5])}")

    now_str = datetime.now(timezone.utc).isoformat()
    clean_updates["updated_at"] = now_str
    updated_count = len(data.asset_ids)

    # SPASIAL: ubah-massal memakai SATU update_many, sehingga `geo` tak bisa
    # dihitung per-aset. Aturannya:
    #   - KEDUA sumbu diisi  -> semua aset memang dipindah ke titik yang sama,
    #                           `geo` boleh dihitung sekali lalu dipakai bersama;
    #   - hanya SATU sumbu   -> nilai benar berbeda tiap aset dan tak dapat
    #                           dihitung di sini, jadi `geo` DIBUANG. Lebih baik
    #                           aset keluar dari indeks daripada memegang posisi
    #                           yang salah diam-diam.
    _geo_unset = sisip_geo_ke_update({}, clean_updates)

    # Jurnal Buku Barang 204/205 untuk ubah massal nilai perolehan: harga
    # LAMA tiap aset dipotret SEBELUM update_many (sesudahnya selisihnya
    # hilang). Jurnalnya ditulis setelah update sukses — best-effort.
    harga_sebelum = []
    if "purchase_price" in clean_updates:
        harga_sebelum = [a async for a in db.assets.find(
            {"id": {"$in": data.asset_ids}},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1,
             "purchase_price": 1})]

    # 1. Simple field updates — single update_many (fast)
    if len(clean_updates) > 1:
        # $inc version pada SEMUA tulisan ubah-massal (temuan audit G3): tanpa
        # ini penjaga OCC/If-Match buta terhadap perubahan massal — klien yang
        # membawa If-Match versi lama masih lolos CAS lalu menimpa hasil ubah
        # massal tanpa satu pun 409. Konsisten dengan jalur tulis tunggal di
        # assets.py yang selalu menaikkan version.
        _ops = {"$set": clean_updates, "$inc": {"version": 1}}
        if _geo_unset:
            _ops["$unset"] = _geo_unset
        await db.assets.update_many({"id": {"$in": data.asset_ids}}, _ops)
        if harga_sebelum:
            from shared_utils import catat_jurnal_edit_harga
            for _a in harga_sebelum:
                await catat_jurnal_edit_harga(
                    _a, clean_updates["purchase_price"],
                    x_user_name or _user.get("username"), sumber="batch")

    # 2. Foto massal — kompres SEKALI per foto, lalu distribusikan ke semua aset
    #    (hormati batas 6 foto/aset). `photo_list` gabungan batch_photo + batch_photos.
    if has_photo:
        prepared = []  # [{data, thumb}] per foto, sudah dikompres sekali
        for p in photo_list:
            compressed_photo, compress_method, orig_size, comp_size = await auto_compress_image(p)
            if compress_method != "none":
                logger.info(f"Batch photo compressed via {compress_method}: {orig_size/1024:.0f}KB → {comp_size/1024:.0f}KB ({(1-comp_size/orig_size)*100:.0f}% reduction)")
            # Pillow SINKRON → thread (temuan C26). `auto_compress_image` tepat di
            # atas sudah memakai to_thread, jadi blokirnya selama ini
            # terpotong-potong — tetapi tetap ada. Diukur pada JPEG 1600×1200:
            # create_thumbnail ±37 ms, create_gallery_thumbnail ±36 ms; delapan
            # foto ±0,3 dtk di mesin uji. Yang dibeli adalah jitter yang hilang
            # dan keseragaman dengan assets.py:1199 — bukan penyelamatan darurat.
            thumb = await asyncio.to_thread(generate_photo_thumbnail, compressed_photo)
            prepared.append({"data": compressed_photo, "thumb": thumb or ""})

        # Cover (thumbnail/gallery) dari foto PERTAMA — dipakai bila aset semula 0 foto.
        cover_thumbnail = await asyncio.to_thread(create_thumbnail, prepared[0]["data"])
        cover_gallery = await asyncio.to_thread(create_gallery_thumbnail, prepared[0]["data"])
        MAX_PHOTOS = 6
        CHUNK = 50

        async def update_photo_chunk(chunk_ids):
            # SATU query $in per chunk (bukan find_one serial per aset — N+1).
            by_id = {}
            async for doc in db.assets.find(
                {"id": {"$in": chunk_ids}},
                {"_id": 0, "id": 1, "photos": 1, "photo_gridfs_ids": 1, "photo_thumbnails": 1},
            ):
                by_id[doc["id"]] = doc
            ops = []
            for aid in chunk_ids:
                asset = by_id.get(aid) or {}
                # PARITAS INDEKS: array gridfs TIDAK difilter — padding "" milik
                # dokumen legacy harus dipertahankan (meng-collapse-nya menggeser
                # indeks → streaming/keep[] menunjuk foto yang salah → kehilangan).
                gridfs_ids = list(asset.get("photo_gridfs_ids") or [])
                current_photos = asset.get("photos", []) or []
                thumbs = list(asset.get("photo_thumbnails") or [])
                current_count = len([g for g in gridfs_ids if g]) or len(current_photos)
                # Hormati batas 6 foto/aset: hanya tambah sisa slot yang tersedia.
                to_add = prepared[: max(0, MAX_PHOTOS - current_count)]
                if not to_add:
                    continue  # aset sudah penuh
                n_slots = max(len(gridfs_ids), len(current_photos))
                # Samakan panjang semua array ke n_slots sebelum append
                gridfs_ids += [""] * (n_slots - len(gridfs_ids))
                thumbs += [""] * (n_slots - len(thumbs))
                # Setiap foto → satu blob GridFS PER ASET (blob dimiliki eksklusif
                # oleh asetnya karena delete-asset menghapus blobnya).
                new_gids, new_thumbs, new_inline = [], [], []
                for ph in to_add:
                    try:
                        gid = await store_photo_to_gridfs(ph["data"])
                    except Exception as e:
                        logger.warning(f"Batch photo: GridFS store failed for {aid}: {e}")
                        continue
                    new_gids.append(gid)
                    new_thumbs.append(ph["thumb"])
                    new_inline.append(ph["data"])
                if not new_gids:
                    continue
                update_fields = {
                    "photo_gridfs_ids": gridfs_ids + new_gids,
                    "photo_thumbnails": thumbs + new_thumbs,
                    "updated_at": now_str,
                }
                # Dokumen legacy yang MASIH menyimpan inline: jaga photos paralel
                # (padding "" bila lebih pendek). Dokumen bersih: photos tetap [].
                if current_photos:
                    update_fields["photos"] = current_photos + [""] * (n_slots - len(current_photos)) + new_inline
                if current_count == 0:
                    update_fields["thumbnail"] = cover_thumbnail
                    update_fields["gallery_thumbnail"] = cover_gallery
                ops.append(UpdateOne({"id": aid}, {"$set": update_fields, "$inc": {"version": 1}}))
            if ops:
                await db.assets.bulk_write(ops, ordered=False)

        chunks = [data.asset_ids[i:i+CHUNK] for i in range(0, len(data.asset_ids), CHUNK)]
        for chunk in chunks:
            await update_photo_chunk(chunk)

    # 3. Document checklist — process in parallel chunks
    if has_doc_checklist:
        CHUNK = 50

        async def update_doc_chunk(chunk_ids):
            # SATU query $in per chunk (bukan find_one serial per aset — N+1).
            by_id = {}
            async for doc in db.assets.find({"id": {"$in": chunk_ids}}, {"_id": 0, "id": 1, "document_checklist": 1}):
                by_id[doc["id"]] = doc
            ops = []
            for aid in chunk_ids:
                asset = by_id.get(aid)
                existing = asset.get("document_checklist", []) if asset else []
                existing_names = {item.get("name", ""): idx for idx, item in enumerate(existing)}

                updated_checklist = list(existing)
                for new_item in doc_checklist_items:
                    item_name = new_item.get("name", "")
                    item_checked = new_item.get("checked", False)
                    item_photos = new_item.get("photos", [])
                    item_documents = new_item.get("documents", [])

                    if item_name in existing_names:
                        idx = existing_names[item_name]
                        updated_checklist[idx]["checked"] = item_checked
                        if item_photos:
                            cur_photos = updated_checklist[idx].get("photos", [])
                            updated_checklist[idx]["photos"] = (cur_photos + item_photos)[:3]
                        if item_documents:
                            cur_docs = updated_checklist[idx].get("documents", [])
                            updated_checklist[idx]["documents"] = (cur_docs + item_documents)[:1]
                    else:
                        updated_checklist.append({
                            "name": item_name, "checked": item_checked, "notes": "",
                            "photos": item_photos[:3], "documents": item_documents[:1],
                        })
                ops.append(UpdateOne({"id": aid}, {"$set": {"document_checklist": updated_checklist, "updated_at": now_str}, "$inc": {"version": 1}}))
            if ops:
                await db.assets.bulk_write(ops, ordered=False)

        chunks = [data.asset_ids[i:i+CHUNK] for i in range(0, len(data.asset_ids), CHUNK)]
        for chunk in chunks:
            await update_doc_chunk(chunk)

    # 4. Clear all photos from selected assets — termasuk blob GridFS (dulu
    # hanya inline yang dikosongkan sehingga blob & photo_count menggantung).
    # URUTAN PENTING: kumpulkan id blob → perbarui dokumen DULU → baru hapus
    # blob. Bila crash setelah update, sisa blob hanya jadi orphan (bocor,
    # aman); urutan sebaliknya bisa meninggalkan dokumen yang merujuk blob
    # mati = kehilangan foto.
    if should_clear_photos:
        gids_to_delete = []
        async for doc in db.assets.find(
            {"id": {"$in": data.asset_ids}, "photo_gridfs_ids": {"$exists": True, "$ne": []}},
            {"_id": 0, "photo_gridfs_ids": 1},
        ):
            gids_to_delete.extend(g for g in (doc.get("photo_gridfs_ids") or []) if g)
        # HANYA aset yang benar-benar punya foto. Menyentuh yang lain menaikkan
        # `version` tanpa perubahan apa pun — dan karena URL media memakai
        # `?v=<version>` sebagai cache-buster, itu MEMBATALKAN cache foto di
        # SELURUH perangkat lapangan untuk aset yang fotonya tak berubah
        # sedikit pun. Di jaringan yang buruk, ongkosnya nyata.
        await db.assets.update_many(
            {"id": {"$in": data.asset_ids},
             # `.0 $exists` dipakai alih-alih `$nin: [None, []]`: yang terakhir
             # ditafsirkan BERBEDA oleh mongomock dan MongoDB asli, sehingga uji
             # bisa hijau sementara produksi berperilaku lain. Predikat ini
             # tunggal artinya di keduanya — "array berisi minimal satu elemen".
             "$or": [{"photo_gridfs_ids.0": {"$exists": True}},
                     {"photos.0": {"$exists": True}},
                     {"thumbnail": {"$nin": [None, ""]}}]},
            {"$set": {"photos": [], "photo": None, "photo_gridfs_ids": [], "photo_thumbnails": [],
                      "thumbnail": None, "gallery_thumbnail": None, "updated_at": now_str},
             "$inc": {"version": 1}}
        )
        for gid in gids_to_delete:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass  # best-effort; orphan dibersihkan rutin GridFS

    # 5. Clear all document checklist from selected assets
    if should_clear_doc_checklist:
        # Alasan yang sama: jangan menaikkan version aset yang checklist-nya
        # memang sudah kosong.
        await db.assets.update_many(
            {"id": {"$in": data.asset_ids},
             "document_checklist.0": {"$exists": True}},
            {"$set": {"document_checklist": [], "updated_at": now_str}, "$inc": {"version": 1}}
        )

    # 6. Audit log — batch insert (limit to 20 entries max for large batches)
    field_names_list = list(clean_updates.keys() - {"updated_at"})
    if has_photo:
        field_names_list.append("foto")
    if has_doc_checklist:
        field_names_list.append("kelengkapan_dokumen")
    if should_clear_photos:
        field_names_list.append("hapus_semua_foto")
    if should_clear_doc_checklist:
        field_names_list.append("hapus_semua_dokumen")
    field_names = ", ".join(field_names_list)

    # Single summary audit log entry (instead of one per asset)
    try:
        sample_asset = await db.assets.find_one({"id": data.asset_ids[0]}, {"_id": 0, "asset_code": 1, "asset_name": 1, "activity_id": 1})
        if sample_asset:
            changes = [{"field": k, "from": "(batch)", "to": str(v)[:100]} for k, v in clean_updates.items() if k != "updated_at"]
            await log_audit(
                "batch_update", sample_asset.get("activity_id", ""), data.asset_ids[0],
                sample_asset.get("asset_code", ""), sample_asset.get("asset_name", ""),
                x_user_name or "system", changes,
                f"Batch update {field_names} untuk {updated_count} aset"
            )
    except Exception as e:
        logger.warning(f"Audit log batch error: {e}")

    invalidate_asset_cache()

    # INDEKS PENCARIAN: ubah massal memakai update_many/bulk_write sehingga
    # hook sinkron per-dokumen (jalur tunggal) TIDAK pernah jalan. Tanpa baris
    # ini indeks memegang nilai LAMA — barang yang baru diisi lokasinya secara
    # massal tak ketemu saat dicari, padahal datanya ada.
    jadwalkan_sync_id("assets", data.asset_ids)

    # Broadcast WebSocket notification. notify_asset_change's signature is
    # (activity_id, event_type, asset_data, user_name, user_id=None) and it
    # broadcasts per-activity. The previous call passed a single dict, which
    # raised TypeError (swallowed below) so batch updates never reached other
    # viewers. Broadcast to the affected assets' activity instead.
    try:
        bcast_asset = await db.assets.find_one(
            {"id": data.asset_ids[0]}, {"_id": 0, "activity_id": 1}
        ) if data.asset_ids else None
        await notify_asset_change(
            (bcast_asset or {}).get("activity_id", ""),
            "batch_update",
            {"count": updated_count, "fields": field_names_list},
            x_user_name or "system",
        )
    except Exception:
        pass

    result = {
        "updated": updated_count,
        "total": len(data.asset_ids),
        "fields": field_names_list
    }

    # Add compression info if photo was compressed
    if has_photo and compress_method != "none":
        result["photo_compression"] = {
            "method": compress_method,
            "original_kb": round(orig_size / 1024, 1),
            "compressed_kb": round(comp_size / 1024, 1),
            "reduction_pct": round((1 - comp_size / orig_size) * 100) if orig_size > 0 else 0,
        }

    return result



@batch_router.get("/assets/groups")
async def get_asset_groups(activity_id: str = "", request: Request = None, _user: dict = Depends(require_user)):
    """Group assets by same asset_code, asset_name, purchase_date, brand/model, price.
    Returns groups with count >= 2, including detailed member info."""
    from shared_utils import scope_query_aset
    match = {}
    if activity_id:
        match["activity_id"] = activity_id
    # Isolasi satker (REVIEW-9 R8): agregasi kelompok aset SEBELUMNYA lintas
    # SELURUH satker — membocorkan detail anggota (lokasi/pemegang/kondisi).
    match = await scope_query_aset(_user, match)

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {
                "asset_code": {"$ifNull": ["$asset_code", ""]},
                "asset_name": {"$ifNull": ["$asset_name", ""]},
                "purchase_date": {"$ifNull": ["$purchase_date", ""]},
                "brand": {"$ifNull": ["$brand", ""]},
                "model": {"$ifNull": ["$model", ""]},
                "purchase_price": {"$ifNull": ["$purchase_price", 0]}
            },
            "count": {"$sum": 1},
            "asset_ids": {"$push": "$id"},
            "NUPs": {"$push": "$NUP"},
            "members": {"$push": {
                "id": "$id",
                "NUP": "$NUP",
                "location": "$location",
                "eselon1": "$eselon1",
                "eselon2": "$eselon2",
                "user": "$user",
                "condition": "$condition",
                "inventory_status": "$inventory_status",
                "stiker_status": "$stiker_status",
                "nomor_spm": "$nomor_spm",
                "serial_number": "$serial_number",
                "kode_register": "$kode_register",
                "supplier": "$supplier",
                "perolehan_dari_nama": "$perolehan_dari_nama",
                "purchase_date": "$purchase_date",
                "purchase_price": "$purchase_price",
                "category": "$category",
            }}
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
        {"$project": {
            "_id": 0,
            "asset_code": "$_id.asset_code",
            "asset_name": "$_id.asset_name",
            "purchase_date": "$_id.purchase_date",
            "brand": "$_id.brand",
            "model": "$_id.model",
            "purchase_price": "$_id.purchase_price",
            "count": 1,
            "asset_ids": 1,
            "NUPs": 1,
            "members": 1
        }}
    ]
    
    groups = []
    async for doc in db.assets.aggregate(pipeline):
        groups.append(doc)
    
    return {"groups": groups, "total_groups": len(groups)}


@batch_router.get("/assets/all-ids")
async def get_all_asset_ids(
    activity_id: str = "",
    search: str = "",
    category: str = "",
    condition: List[str] = Query(default=[]),
    status: List[str] = Query(default=[]),
    location: List[str] = Query(default=[]),
    eselon1_filter: List[str] = Query(default=[]),
    eselon2_filter: List[str] = Query(default=[]),
    stiker_status: List[str] = Query(default=[]),
    inventory_status: List[str] = Query(default=[]),
    price_min: float = None,
    price_max: float = None,
    nomor_spm: str = "",
    perolehan_dari: str = "",
    user_filter: str = "",
    pengguna_nip: str = "",
    beli_dari: str = "",
    beli_sampai: str = "",
    _user: dict = Depends(require_user),
):
    """Id seluruh aset yang cocok filter aktif — untuk "pilih semua halaman".

    Memakai build_asset_search_query yang SAMA dengan GET /assets. Sebelumnya
    endpoint ini menyusun query-nya sendiri dan sudah drift: `eselon1_filter`
    dicocokkan persis (di daftar: substring), pencarian teks hanya menyentuh 3
    field (di daftar: 16 field multi-kata), dan filter harga/tanggal/SPM/
    perolehan/pengguna TIDAK ADA sama sekali. Akibatnya "Pilih semua N aset"
    menandai himpunan yang BERBEDA dari yang sedang dilihat pengguna — lalu
    aksi massal (ubah/hapus/cetak) mengenai aset yang tak pernah tampil.
    """
    from routes.assets import build_asset_search_query
    query = build_asset_search_query(
        search=search, category=category, activity_id=activity_id,
        condition=condition, status=status, location=location,
        eselon1_filter=eselon1_filter, eselon2_filter=eselon2_filter,
        stiker_status=stiker_status, inventory_status=inventory_status,
        price_min=price_min, price_max=price_max, nomor_spm=nomor_spm,
        perolehan_dari=perolehan_dari, user_filter=user_filter,
        pengguna_nip=pengguna_nip, beli_dari=beli_dari,
        beli_sampai=beli_sampai)

    # Isolasi satker (REVIEW-9 R8): "pilih semua halaman" SEBELUMNYA
    # mengenumerasi id aset SELURUH satker.
    from shared_utils import scope_query_aset
    query = await scope_query_aset(_user, query)
    ids = []
    async for doc in db.assets.find(query, {"_id": 0, "id": 1}):
        ids.append(doc["id"])
    return {"ids": ids, "total": len(ids)}
