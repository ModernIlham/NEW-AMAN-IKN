"""Asset CRUD, filter options, stats, analytics."""
import re
import uuid
import base64
import logging
import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import Response

from pymongo.errors import DuplicateKeyError

from db import db, fs_bucket
from asset_fields import SCALAR_FIELD_NAMES
from spasial_utils import terapkan_geo, sisip_geo_ke_update, entri_riwayat_lokasi
import spasial_penempatan as sp
from models import AssetCreate, AssetResponse
from auth_utils import (
    require_admin, require_super_admin, require_user,
    require_user_or_query_token, require_writer,
)
from shared_utils import (
    kunci_idem,
    invalidate_asset_cache, cache_get, cache_set,
    log_audit, compute_changes, create_thumbnail, create_gallery_thumbnail,
    store_photo_to_gridfs, get_photo_from_gridfs, delete_photo_from_gridfs,
    generate_photo_thumbnail,
    get_idempotent_response, store_idempotent_response, reserve_idempotency_key,
    ensure_activity_not_sealed,
    get_document_from_gridfs, delete_document_from_gridfs,
    kode_satker_user, pastikan_akses_aset, pastikan_akses_kegiatan_id,
    scope_query_aset, scope_query_field_satker,
)
from penggunaan_utils import info_psp_aset, peta_psp_dari_sk
from routes.websocket import notify_asset_change
from photo_rotate_utils import normalisasi_derajat, rotate_jpeg_bytes
from meili_utils import jadwalkan_sync, jadwalkan_hapus, cari_id_aset
from pencarian_utils import MIN_PANJANG, klausa_teks, pecah_kata, rx_awalan

logger = logging.getLogger(__name__)
assets_router = APIRouter()

# ============================================================================
# ASSET ROUTES
# ============================================================================


def _rx(term: str) -> dict:
    """Case-insensitive substring match treating user input as a LITERAL
    (re.escape). Prevents ReDoS + invalid-regex 500s from crafted input like
    "(a+)+$" or "[" while preserving plain substring search semantics."""
    return {"$regex": re.escape(term), "$options": "i"}


# Field yang ikut dicari saat pengguna mengetik di kotak pencarian aset.
# Selain field deskriptif, IDENTITAS yang paling sering diketik petugas WAJIB
# ada di sini — NUP, nomor kontrak/BAST/bukti perolehan, dan NIP pengguna
# dulu TIDAK dicari sama sekali, sehingga mengetiknya selalu nihil hasil.
FIELD_CARI_ASET = (
    "asset_code", "NUP", "asset_name", "serial_number", "location",
    "brand", "model", "category", "eselon1", "eselon2", "user",
    "pengguna_jabatan", "supplier", "perolehan_dari_nama",
    "condition", "status", "nomor_spm", "kode_register",
    "nomor_kontrak", "nomor_bast", "nomor_bukti_perolehan", "notes",
    # `year` bukan field registry tetapi ada pada dokumen lama & dipakai
    # laporan; petugas kerap mengetik tahun perolehan di kotak pencarian.
    "year",
)

# Field KODE/NOMOR yang boleh diketik dengan pemisah berbeda: kode barang
# tanpa titik ("3100102001"), kode sebagian ("310.01.02"), atau nama barang
# ber-desimal koma yang diketik pakai titik ("1.5" vs "1,5").
FIELD_KODE_ASET = (
    "asset_code", "NUP", "kode_register", "serial_number", "nomor_spm",
    "nomor_kontrak", "nomor_bast", "nomor_bukti_perolehan",
    "asset_name", "model", "location",
)

# Field yang nilainya BISA tersimpan sebagai angka (impor/sinkron lama).
# `$regex` tak pernah cocok ke nilai non-string, jadi aset ber-NUP numerik
# dulu mustahil ditemukan lewat pencarian.
FIELD_ANGKA_ASET = ("NUP", "year", "purchase_price")
# CATATAN PRIVASI: `pengguna_nip` SENGAJA tidak ikut pencarian teks bebas.
# NIP adalah data pribadi yang tidak diindeks ke mesin pencari eksternal
# (lihat test_meili_utils.test_proyeksi_aset_hanya_field_terindeks); bila ia
# dicari lewat Mongo saja, hasil pencarian akan berbeda tergantung Meili hidup
# atau mati — persis penyakit yang sedang diperbaiki. Pencarian per-NIP tetap
# tersedia lewat parameter filter khusus `pengguna_nip`.

# Panjang minimum kata angka sebelum dicocokkan sebagai AWALAN harga. Tanpa
# batas ini, mengetik "12" (maksudnya NUP) menyeret semua aset berharga
# 12.000, 120.000, 12.000.000 … — kebisingan yang membuat hasil terasa acak.
_MIN_DIGIT_AWALAN_HARGA = 4


def _klausa_harga(kata: str) -> list:
    """Klausa tambahan agar harga bisa dicari dengan mengetik angkanya.
    Format Indonesia (titik/koma pemisah ribuan) dinormalkan lebih dulu."""
    bersih = kata.replace(".", "").replace(",", "")
    try:
        angka = float(bersih)
    except ValueError:
        return []
    cabang = [{"purchase_price": angka}, {"purchase_price": bersih}]
    if len(bersih) >= _MIN_DIGIT_AWALAN_HARGA:
        cabang.append({"purchase_price": rx_awalan(bersih)})
    return cabang


# Panjang minimum kata kunci pencarian teks bebas — SATU sumber di
# pencarian_utils supaya ambangnya tak pernah berbeda antar modul. Regex infix
# tak bisa memakai index (COLLSCAN dalam lingkup satker), jadi kueri 1 huruf
# memindai hampir seluruh aset tanpa menyaring apa pun; di bawah ambang ini
# filter pencarian DIABAIKAN (daftar tampil apa adanya).
MIN_SEARCH_LEN = MIN_PANJANG


def _search_len_ok(search: str) -> bool:
    """True bila kata kunci pencarian layak dijalankan (≥ MIN_SEARCH_LEN setelah
    dipangkas). Kosong/whitespace/1-huruf → False (diperlakukan tanpa pencarian)."""
    return bool(pecah_kata(search))


async def _collect_asset_blob_ids(asset: dict) -> dict:
    """Gather GridFS blob ids referenced by an asset so they can be deleted
    alongside the doc (prevents orphaned blobs on delete). In this schema only
    full-size photos (photo_gridfs_ids) and the BAST file live in GridFS;
    checklist photos/PDFs are stored inline and vanish with the doc. Any
    checklist doc `gridfs_id` is collected defensively for forward-compat."""
    photo_ids = [g for g in (asset.get("photo_gridfs_ids") or []) if g]
    doc_ids = []
    bast_id = asset.get("bast_file_id") or ""
    if bast_id:
        doc_ids.append(bast_id)
    for item in (asset.get("document_checklist") or []):
        if not isinstance(item, dict):
            continue
        for d in (item.get("documents") or []):
            gid = d.get("gridfs_id") if isinstance(d, dict) else None
            if gid:
                doc_ids.append(gid)
    return {"photos": photo_ids, "documents": doc_ids}


# NOTE: Row locking & batch operations moved to routes/batch.py


def _build_cas_filter(asset_id: str, current_version: int) -> dict:
    """Build a resilient CAS (Compare-And-Swap) filter for the assets collection.

    Legacy assets (created before OCC was introduced, or restored from older
    backups) may be missing the `version` field entirely. In that case
    `existing.get("version", 1)` returns 1 (our default), but a plain query
    `{"version": 1}` will NOT match a document without the field.

    When current_version == 1 we therefore additionally accept docs where
    version is missing — this lets the very first write after an upgrade
    succeed and backfill the version field via `$inc`.
    """
    if current_version == 1:
        return {
            "id": asset_id,
            "$or": [
                {"version": 1},
                {"version": {"$exists": False}},
            ],
        }
    return {"id": asset_id, "version": current_version}


# OPTIMIZED: Lightweight list projection - excludes photos and document_checklist.
# Photos and document_checklist are fetched separately when editing an asset;
# this reduces response size by ~95% for assets with images. Shared by
# GET /assets and GET /assets/offline-snapshot so the offline cache stores
# EXACTLY the same (media-free) shape as the live list.
LIST_PROJECTION = {
    "_id": 0, "id": 1,
    # Semua field skalar aset dari registry (asset_fields.py) — termasuk
    # field berlebih/sengketa agar form edit offline melihat nilai aslinya.
    **{name: 1 for name in SCALAR_FIELD_NAMES},
    "bast_file_id": 1, "bast_filename": 1, "bast_snapshot": 1,
    "thumbnail": 1, "thumbnail_index": 1,
    # gallery_thumbnail (256px, ~11-20KB base64/baris) TIDAK ikut lagi: kartu
    # galeri memakai streaming ?w=256 yang ter-cache browser; payload list 50
    # baris hemat ~0,5-1MB dan sync snapshot 1000 baris hemat belasan MB.
    "created_at": 1, "updated_at": 1, "activity_id": 1,
    "version": 1,  # OCC: client needs this to send If-Match on subsequent writes
    "stiker_photo_index": 1,
    # Sinkronisasi SIMAN V2: status cocok/selisih + rincian selisih + referensi
    # (nilai penyusutan/buku dsb.) — ringkas, dipakai penanda di halaman aset.
    "siman": 1,
    # Jejak BAST serah terima terakhir (badge riwayat handover per aset).
    "bast_terakhir": 1,
    # GridFS-first (dokumen ter-migrasi punya photos=[] tapi gridfs terisi);
    # fallback ke inline untuk dokumen legacy.
    "photo_count": {"$cond": [
        {"$gt": [{"$size": {"$ifNull": ["$photo_gridfs_ids", []]}}, 0]},
        {"$size": {"$ifNull": ["$photo_gridfs_ids", []]}},
        {"$size": {"$ifNull": ["$photos", []]}},
    ]},
    # Computed doc checklist summary (avoids sending full checklist data)
    "doc_total": {"$size": {"$ifNull": ["$document_checklist", []]}},
    "doc_checked": {"$size": {"$filter": {
        "input": {"$ifNull": ["$document_checklist", []]},
        "cond": {"$eq": ["$$this.checked", True]}
    }}},
    "doc_summary": {"$map": {
        "input": {"$ifNull": ["$document_checklist", []]},
        "as": "doc",
        "in": {
            "name": "$$doc.name",
            "checked": "$$doc.checked",
            "has_photos": {"$gt": [{"$size": {"$ifNull": ["$$doc.photos", []]}}, 0]},
            "has_documents": {"$gt": [{"$size": {"$ifNull": ["$$doc.documents", []]}}, 0]},
            "photo_count": {"$size": {"$ifNull": ["$$doc.photos", []]}},
            "doc_count": {"$size": {"$ifNull": ["$$doc.documents", []]}}
        }
    }}
    # EXCLUDED: "photos", "document_checklist" - fetched via GET /assets/{id}
}


async def lengkapi_psp(assets, user):
    """Tempelkan keterangan `psp` per aset — SATU query untuk seluruh halaman.

    Dua sumber digabung oleh `info_psp_aset` (register SK PSP menang atas
    referensi SIMAN). `siman` sudah ikut LIST_PROJECTION, jadi yang perlu
    diambil dari DB hanyalah SK register yang mencakup id di halaman ini —
    bukan N query, dan bukan seluruh register.

    Query di-scope satker via `scope_query_field_satker`: SK milik satker lain
    tak boleh menerangi aset siapa pun, sekalipun id-nya kebetulan tercantum.
    """
    ids = [str(a.get("id")) for a in (assets or []) if a.get("id")]
    if not ids:
        return assets
    sk = await db.psp.find(
        scope_query_field_satker(user, {"aset.asset_id": {"$in": ids}}),
        {"_id": 0, "nomor_sk": 1, "tanggal_sk": 1, "jenis": 1,
         "status_pengajuan": 1, "aset.asset_id": 1},
    ).to_list(length=None)
    peta = peta_psp_dari_sk(sk)
    for a in assets:
        info = info_psp_aset(a, peta)
        if info:
            a["psp"] = info
    return assets


def build_asset_search_query(
    search: str = "",
    category: str = "",
    activity_id: str = "",
    condition: str = "",
    status: str = "",
    location: str = "",
    eselon1_filter: str = "",
    eselon2_filter: str = "",
    stiker_status: str = "",
    inventory_status: str = "",
    price_min: float = None,
    price_max: float = None,
    nomor_spm: str = "",
    perolehan_dari: str = "",
    user_filter: str = "",
    pengguna_nip: str = "",
    beli_dari: str = "",
    beli_sampai: str = "",
    ids: list = None,
) -> dict:
    """Query pencarian + filter aset — SATU builder untuk GET /assets dan
    ekspor geo (KML/KMZ/SHP) supaya filter tidak pernah drift antar-endpoint."""
    query = {}

    # Filter by activity_id if provided
    if activity_id:
        query["activity_id"] = activity_id

    # Batasi ke daftar id tertentu (mis. aset yang DIPILIH di peta) — irisan
    # dengan filter lain, sehingga ekspor terseleksi = filter ∩ pilihan.
    if ids:
        query["id"] = {"$in": list(ids)}

    # Pencarian teks bebas MULTI-KATA: setiap kata wajib ada, boleh di field
    # yang berbeda-beda (lihat pencarian_utils). Diabaikan bila kata kunci
    # < MIN_SEARCH_LEN (cegah COLLSCAN 1-huruf).
    query.update(klausa_teks(
        search, FIELD_CARI_ASET, tambahan=_klausa_harga,
        fields_kode=FIELD_KODE_ASET, fields_angka=FIELD_ANGKA_ASET))

    # Basic category filter
    if category:
        query["category"] = category
    
    # Advanced filters
    if condition:
        query["condition"] = condition
    
    if status:
        query["status"] = status
    
    if location:
        query["location"] = _rx(location)

    if eselon1_filter:
        query["eselon1"] = _rx(eselon1_filter)

    if eselon2_filter:
        query["eselon2"] = _rx(eselon2_filter)

    if stiker_status:
        query["stiker_status"] = stiker_status

    if inventory_status:
        query["inventory_status"] = inventory_status

    if nomor_spm:
        query["nomor_spm"] = _rx(nomor_spm)

    if perolehan_dari:
        query["supplier"] = _rx(perolehan_dari)

    # Filter khusus pemegang aset (registry: `user` = nama pengguna,
    # `pengguna_nip` = NIP/NIK). Terpisah dari kotak pencarian bebas agar bisa
    # dikombinasikan dengan filter lain dan agar NIP (yang tidak masuk daftar
    # $or pencarian) tetap bisa dicari presisi. Keduanya contains, literal-safe.
    if user_filter:
        query["user"] = _rx(user_filter)

    if pengguna_nip:
        query["pengguna_nip"] = _rx(pengguna_nip)

    # Price range filter
    if price_min is not None or price_max is not None:
        price_query = {}
        if price_min is not None:
            price_query["$gte"] = price_min
        if price_max is not None:
            price_query["$lte"] = price_max
        if price_query:
            # Handle both numeric and string prices (including empty strings)
            # Use $convert with onError to handle empty strings and invalid values
            price_convert = {
                "$convert": {
                    "input": "$purchase_price",
                    "to": "double",
                    "onError": 0,
                    "onNull": 0
                }
            }
            query["$expr"] = {
                "$and": [
                    {"$gte": [price_convert, price_min or 0]},
                    {"$lte": [price_convert, price_max or 999999999999]}
                ]
            }

    # Rentang TANGGAL BELI (purchase_date, string YYYY-MM-DD — perbandingan
    # leksikal aman untuk prefiks tanggal). Aset tanpa tanggal beli otomatis
    # keluar dari hasil saat rentang diisi (tak punya tanggal beli untuk
    # dibandingkan). Kedua batas divalidasi simetris; nilai tak valid
    # diabaikan diam-diam (frontend selalu mengirim YYYY-MM-DD dari
    # <input type=date>).
    if beli_dari or beli_sampai:
        rng = {}
        cf = str(beli_dari or "").strip()[:10]
        ct = str(beli_sampai or "").strip()[:10]
        if cf:
            try:
                datetime.strptime(cf, "%Y-%m-%d")
                rng["$gte"] = cf
            except (ValueError, OverflowError):
                pass
        if ct:
            try:
                datetime.strptime(ct, "%Y-%m-%d")
                rng["$lte"] = ct  # tanggal beli tanpa jam → batas atas inklusif
            except (ValueError, OverflowError):
                pass
        if rng:
            query["purchase_date"] = rng

    return query


@assets_router.get("/assets")
async def get_assets(
    search: str = "",
    category: str = "",
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 50,
    activity_id: str = "",
    # Advanced filters
    condition: str = "",
    status: str = "",
    location: str = "",
    eselon1_filter: str = "",
    eselon2_filter: str = "",
    stiker_status: str = "",
    inventory_status: str = "",
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
    """Get paginated assets with advanced filters - optimized for millions of records"""
    # PENCARIAN TEKS BEBAS via Meilisearch (bila aktif): resolve kata kunci →
    # daftar id kandidat ter-scope, lalu batasi kueri Mongo ke id itu. SEMUA
    # filter lanjutan/sort/paginasi/isolasi tetap dijalankan Mongo (otoritatif).
    # `meili_ids is None` → Meili nonaktif/gagal → pakai regex Mongo 16-field lama.
    meili_ids = await cari_id_aset(_user, activity_id, search) if _search_len_ok(search) else None
    # Hasil KOSONG dari Meili TIDAK dipercaya sebagai "memang tidak ada":
    # indeks bisa tertinggal (dokumen gagal sinkron saat Meili mati) dan
    # pencocokan berbasis kata di Meili tak mengenal kode yang diketik tanpa
    # pemisah. Nihil → jatuh ke regex Mongo yang otoritatif; biaya pindai
    # hanya muncul pada pencarian yang memang tak berhasil.
    if meili_ids is not None and not meili_ids:
        meili_ids = None
    query = build_asset_search_query(
        search=("" if meili_ids is not None else search),
        category=category, activity_id=activity_id,
        condition=condition, status=status, location=location,
        eselon1_filter=eselon1_filter, eselon2_filter=eselon2_filter,
        stiker_status=stiker_status, inventory_status=inventory_status,
        price_min=price_min, price_max=price_max, nomor_spm=nomor_spm,
        perolehan_dari=perolehan_dari, user_filter=user_filter, pengguna_nip=pengguna_nip,
        beli_dari=beli_dari, beli_sampai=beli_sampai,
    )
    if meili_ids is not None:
        # Daftar kosong = tak ada kecocokan → hasil nihil (bukan "semua").
        query["id"] = {"$in": meili_ids}
    # ISOLASI SATKER (M-SCOPE): activity_id spesifik → wajib milik satker
    # user; tanpa activity_id → batasi ke seluruh kegiatan satkernya.
    await pastikan_akses_kegiatan_id(_user, activity_id)
    query = await scope_query_aset(_user, query)

    # Extended sort options
    # Tiebreaker `id` di setiap opsi: sort Mongo tidak stabil antar-query
    # skip/limit, tanpa kunci unik halaman bisa tumpang-tindih/terlewat
    # (nilai created_at/nama yang sama) — penting utk klien yang menjahit
    # beberapa halaman (mis. Peta Aset).
    sort_options = {
        "newest": [("created_at", -1), ("id", 1)],
        "oldest": [("created_at", 1), ("id", 1)],
        "name_asc": [("asset_name", 1), ("id", 1)],
        "name_desc": [("asset_name", -1), ("id", 1)],
        "price_asc": [("purchase_price", 1), ("id", 1)],
        "price_desc": [("purchase_price", -1), ("id", 1)],
        "category_asc": [("category", 1), ("id", 1)],
        "category_desc": [("category", -1), ("id", 1)],
        "location_asc": [("location", 1), ("id", 1)],
        "eselon1_asc": [("eselon1", 1), ("id", 1)],
        "condition_asc": [("condition", 1), ("id", 1)],
        "status_asc": [("status", 1), ("id", 1)]
    }
    sort = sort_options.get(sort_by, [("created_at", -1)])
    
    # Lightweight shared list projection (see LIST_PROJECTION above)
    projection = LIST_PROJECTION

    # Clamp page_size - allow up to 500 for power users
    page_size = min(max(page_size, 10), 500)
    skip = (max(page, 1) - 1) * page_size
    
    # Run count and fetch in parallel using aggregation for computed fields
    pipeline = [
        {"$match": query},
        {"$sort": dict(sort)},
        {"$skip": skip},
        {"$limit": page_size},
        {"$project": projection}
    ]
    total, assets = await asyncio.gather(
        db.assets.count_documents(query),
        db.assets.aggregate(pipeline).to_list(page_size)
    )
    await lengkapi_psp(assets, _user)

    total_pages = max(1, (total + page_size - 1) // page_size)
    
    return {
        "items": assets,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@assets_router.get("/assets/offline-snapshot")
async def get_assets_offline_snapshot(
    activity_id: str,
    since: str = "",
    skip: int = 0,
    cursor: str = "",
    limit: int = 1000,
    _user: dict = Depends(require_user),
):
    """Delta feed for the client-side offline read cache (inventory mode).

    Returns list-projection assets (LIST_PROJECTION — NO photos / full
    document_checklist) for ONE activity, paged via KEYSET cursor (`cursor` =
    `id` of the previous page's last row) so 10k assets stream in chunks of
    <= 1000 without the O(skip) rescan that `$skip` pays each page (a full sync
    was O(n²)). Legacy `skip` param still honoured for not-yet-deployed clients.
    With `since` (ISO timestamp from a previous
    response's `server_time`) only assets changed after that moment are
    returned — creates/PUT/PATCH/batch all stamp `updated_at`.

    Tombstones: there is no dedicated deletions log, but every single-asset
    DELETE writes an audit entry (action='delete' with asset_id), so those are
    returned as `deleted_ids`. Bulk deletes (action='bulk_delete') carry no
    per-asset ids — when one happened after `since` we set
    `requires_full_refresh` and the client re-syncs from scratch (a full
    refresh reconciles deletes by definition).

    Auth: gated by require_user like other protected endpoints, and strictly
    scoped by activity_id (400 without it) so a snapshot can never leak
    assets from another activity.
    """
    if not activity_id:
        raise HTTPException(status_code=400, detail="activity_id wajib diisi")
    await pastikan_akses_kegiatan_id(_user, activity_id)

    limit = min(max(limit, 1), 1000)
    skip = max(skip, 0)
    cursor = str(cursor or "").strip()

    # Capture server_time BEFORE querying: anything written while we stream
    # pages is (re-)fetched by the next delta — upserts are idempotent.
    server_time = datetime.now(timezone.utc).isoformat()

    base_query = {"activity_id": activity_id}
    if since:
        # Legacy docs created before updated_at stamping existed only have
        # created_at — cover both so a fresh row is never missed.
        base_query["$or"] = [
            {"updated_at": {"$gt": since}},
            {"updated_at": {"$exists": False}, "created_at": {"$gt": since}},
        ]

    # Urutan total pada `id` (UUID unik & selalu ada — indeks (activity_id,id)).
    # KEYSET: cursor = id item terakhir → next page = {id > cursor}, seek
    # O(log n) bukan $skip O(skip). id dipilih (bukan created_at) karena unik &
    # non-null DIJAMIN oleh indeks unik + tiap jalur tulis; created_at bisa
    # hilang di sebagian dok sehingga predikat $lt akan MENJATUHKAN baris
    # (kehilangan data senyap di cache offline). Klien order-agnostik (upsert
    # per id) → urutan id tak memengaruhi kebenaran. `skip` lama tetap konsisten
    # karena sort-nya sama.
    match = dict(base_query)
    if cursor:
        keyset = {"id": {"$gt": cursor}}
        match = {"$and": [base_query, keyset]} if "$or" in match else {**match, **keyset}

    pipeline = [{"$match": match}, {"$sort": {"id": 1}}]
    if not cursor and skip:
        pipeline.append({"$skip": skip})
    pipeline += [{"$limit": limit}, {"$project": LIST_PROJECTION}]

    total, assets = await asyncio.gather(
        db.assets.count_documents(base_query),
        db.assets.aggregate(pipeline).to_list(limit),
    )
    # Snapshot luring memakai bentuk yang SAMA dengan daftar daring — termasuk
    # `psp`. Tanpa ini penanda ber-PSP lenyap begitu petugas kehilangan sinyal,
    # dan itu terbaca sebagai bug, bukan sebagai "sedang luring".
    await lengkapi_psp(assets, _user)
    # Kursor halaman berikut = id item terakhir bila halaman PENUH (mungkin masih
    # ada); halaman tak-penuh → "" (penanda selesai, kembar dgn items<limit).
    next_cursor = assets[-1]["id"] if len(assets) == limit and assets else ""

    # Tombstones only make sense for a delta, and only need to be sent once
    # per sync run (first page = tanpa cursor & skip==0).
    deleted_ids = []
    requires_full_refresh = False
    if since and not cursor and skip == 0:
        tomb_query = {"action": "delete", "activity_id": activity_id, "timestamp": {"$gt": since}}
        tombstones = await db.audit_logs.find(tomb_query, {"_id": 0, "asset_id": 1}).to_list(10000)
        deleted_ids = [t["asset_id"] for t in tombstones if t.get("asset_id")]
        bulk = await db.audit_logs.count_documents(
            {"action": "bulk_delete", "activity_id": activity_id, "timestamp": {"$gt": since}}
        )
        requires_full_refresh = bulk > 0

    return {
        "items": assets,
        "total": total,
        "skip": skip,
        "limit": limit,
        "next_cursor": next_cursor,
        "server_time": server_time,
        "deleted_ids": deleted_ids,
        "requires_full_refresh": requires_full_refresh,
    }


@assets_router.get("/assets/filter-options")
async def get_filter_options(activity_id: str = "", _user: dict = Depends(require_user)):
    """Get distinct values for filter dropdowns (cached 3 min per activity)"""
    # Cache key MEMBAWA kode satker user — tanpa ini, cache "__all__" yang
    # diisi user lintas-satker bocor ke user satker lain (M-SCOPE).
    await pastikan_akses_kegiatan_id(_user, activity_id)
    cache_key = f"{kode_satker_user(_user)}|{activity_id or '__all__'}"
    _cached = await cache_get("filter_opts", cache_key)
    if _cached is not None:
        return _cached

    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    query = await scope_query_aset(_user, query)

    # Get distinct values for each filterable field
    locations, eselon1s, eselon2s, conditions, statuses, stiker_statuses, inventory_statuses = await asyncio.gather(
        db.assets.distinct("location", query),
        db.assets.distinct("eselon1", query),
        db.assets.distinct("eselon2", query),
        db.assets.distinct("condition", query),
        db.assets.distinct("status", query),
        db.assets.distinct("stiker_status", query),
        db.assets.distinct("inventory_status", query)
    )
    
    # Filter out None/empty values and sort
    clean_sort = lambda lst: sorted([x for x in lst if x and str(x).strip()])
    
    result = {
        "locations": clean_sort(locations),
        "eselon1s": clean_sort(eselon1s),
        "eselon2s": clean_sort(eselon2s),
        "conditions": clean_sort(conditions),
        "statuses": clean_sort(statuses),
        "stiker_statuses": clean_sort(stiker_statuses),
        "inventory_statuses": clean_sort(inventory_statuses)
    }
    await cache_set("filter_opts", cache_key, result)
    return result

@assets_router.get("/assets/stats")
async def get_assets_stats(search: str = "", category: str = "", activity_id: str = "",
                           _user: dict = Depends(require_user)):
    """Get aggregate stats (cached 1 min per unique query)"""
    await pastikan_akses_kegiatan_id(_user, activity_id)
    cache_key = f"{kode_satker_user(_user)}|{activity_id}|{search}|{category}"
    _cached = await cache_get("stats", cache_key)
    if _cached is not None:
        return _cached

    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    query = await scope_query_aset(_user, query)
    # Pencarian teks bebas via Meilisearch bila aktif (konsisten dgn GET /assets
    # sehingga total statistik = total daftar). Fallback → regex 5-field lama.
    meili_ids = await cari_id_aset(_user, activity_id, search) if _search_len_ok(search) else None
    if meili_ids is not None:
        query["id"] = {"$in": meili_ids}
    elif _search_len_ok(search):
        rx = _rx(search)
        query["$or"] = [
            {"asset_code": rx},
            {"asset_name": rx},
            {"serial_number": rx},
            {"location": rx},
            {"brand": rx},
        ]
    if category:
        query["category"] = category
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "total_assets": {"$sum": 1},
            "total_value": {"$sum": {
                "$convert": {
                    "input": "$purchase_price",
                    "to": "double",
                    "onError": 0,
                    "onNull": 0
                }
            }},
            "active_count": {"$sum": {"$cond": [{"$eq": ["$status", "Aktif"]}, 1, 0]}},
            "maintenance_count": {"$sum": {"$cond": [{"$eq": ["$status", "Maintenance"]}, 1, 0]}}
        }}
    ]
    
    result = await db.assets.aggregate(pipeline).to_list(1)
    if result:
        r = result[0]
        stats = {
            "total_assets": r["total_assets"],
            "total_value": r["total_value"],
            "active_count": r["active_count"],
            "maintenance_count": r["maintenance_count"]
        }
    else:
        stats = {"total_assets": 0, "total_value": 0, "active_count": 0, "maintenance_count": 0}
    await cache_set("stats", cache_key, stats)
    return stats

@assets_router.get("/assets/analytics")
async def get_assets_analytics(activity_id: str = "", _user: dict = Depends(require_user)):
    """Get analytics data for charts (cached 2 min per activity)"""
    await pastikan_akses_kegiatan_id(_user, activity_id)
    cache_key = f"{kode_satker_user(_user)}|{activity_id or '_all'}"
    _cached = await cache_get("analytics", cache_key)
    if _cached is not None:
        return _cached

    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    query = await scope_query_aset(_user, query)

    price_convert = {"$convert": {"input": "$purchase_price", "to": "double", "onError": 0, "onNull": 0}}

    # SATU lintasan $facet: $match memilih set (via indeks activity_id) SEKALI,
    # lalu 5 grouping berjalan atas set yang sama — menggantikan 5 aggregation
    # terpisah yang masing-masing memindai ulang set yang sama. $limit tiap
    # cabang menyamai batas to_list(...) lama (keluaran identik).
    facet_res = await db.assets.aggregate([
        {"$match": query},
        {"$facet": {
            "by_category": [
                {"$group": {"_id": "$category", "count": {"$sum": 1}, "value": {"$sum": price_convert}}},
                {"$sort": {"count": -1}}, {"$limit": 15},
            ],
            "by_condition": [
                {"$group": {"_id": {"$ifNull": ["$condition", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 20},
            ],
            "by_status": [
                {"$group": {"_id": {"$ifNull": ["$status", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 20},
            ],
            "by_location": [
                {"$group": {"_id": {"$ifNull": ["$location", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 10},
            ],
            "by_eselon": [
                {"$group": {"_id": {"$ifNull": ["$eselon1", "Tidak Diketahui"]}, "count": {"$sum": 1}, "value": {"$sum": price_convert}}},
                {"$sort": {"value": -1}}, {"$limit": 10},
            ],
        }},
    ]).to_list(1)
    facets = facet_res[0] if facet_res else {}
    cat_res = facets.get("by_category", [])
    cond_res = facets.get("by_condition", [])
    stat_res = facets.get("by_status", [])
    loc_res = facets.get("by_location", [])
    eselon_res = facets.get("by_eselon", [])

    result = {
        "by_category": [{"name": r["_id"] or "Lainnya", "count": r["count"], "value": r["value"]} for r in cat_res],
        "by_condition": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in cond_res],
        "by_status": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in stat_res],
        "by_location": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in loc_res],
        "by_eselon": [{"name": r["_id"] or "Lainnya", "count": r["count"], "value": r["value"]} for r in eselon_res],
    }
    await cache_set("analytics", cache_key, result)
    return result


# Must be declared BEFORE /assets/{asset_id} or "next-nup" would be captured
# as an asset id by that route.
@assets_router.get("/assets/next-nup")
async def get_next_nup(activity_id: str = "", asset_code: str = "", category: str = "",
                       _user: dict = Depends(require_user)):
    """Next available numeric NUP for a category/asset_code within an activity.

    Uniqueness in this app is (asset_code, NUP) per activity_id, so the next
    number is computed over the same scope. NUP is stored as a string; values
    that aren't parseable as integers are ignored via $convert onError.
    """
    await pastikan_akses_kegiatan_id(_user, activity_id)
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    query = await scope_query_aset(_user, query)
    if asset_code:
        query["asset_code"] = asset_code
    elif category:
        query["category"] = category
    else:
        raise HTTPException(status_code=400, detail="asset_code atau category wajib diisi")

    res = await db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
            "input": "$NUP", "to": "int", "onError": None, "onNull": None
        }}}}}
    ]).to_list(1)

    max_nup = (res[0].get("max_nup") if res else None) or 0
    return {"next_nup": str(max_nup + 1), "max_nup": str(max_nup)}


# NOTE: Audit logs moved to routes/audit.py
# NOTE: Image compression moved to routes/media.py

async def process_photos_for_storage(photos: list) -> dict:
    """Store photos in GridFS and generate thumbnails. Atomic: rolls back on failure.
    Returns {gridfs_ids, thumbnails}."""
    gridfs_ids = []
    thumbnails = []
    try:
        for photo in photos:
            gid = await store_photo_to_gridfs(photo)
            gridfs_ids.append(gid)
            # Decode/resize/encode PIL bersifat CPU-bound — offload ke thread
            # (PIL melepas GIL) agar tak memblokir event loop (semua request).
            thumb = await asyncio.to_thread(generate_photo_thumbnail, photo, 100, 70)
            thumbnails.append(thumb or "")
    except Exception as e:
        # Rollback: clean up any already-stored GridFS blobs to prevent orphans
        logger.warning(f"Photo processing failed, rolling back {len(gridfs_ids)} blobs: {e}")
        for gid in gridfs_ids:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        raise
    return {"gridfs_ids": gridfs_ids, "thumbnails": thumbnails}


async def _enforce_pegawai_terdaftar(pengguna_nip, nip_lama=""):
    """Evaluasi #4 (OPT-IN) — delegasi ke penegakan bersama di shared_utils
    (temuan #29: jalur batch & impor juga harus menegakkan aturan yang sama).
    `nip_lama` membiarkan edit aset yang pemegangnya TIDAK berubah (termasuk
    aset almarhum yang sedang diproses pengembaliannya)."""
    from shared_utils import enforce_pegawai_terdaftar
    await enforce_pegawai_terdaftar(pengguna_nip, nip_lama)


async def buat_aset_draft(data: AssetCreate, audit_user: str = "system") -> dict:
    """Buat SATU aset draft TANPA foto — dipakai Pengadaan "buat draft aset dari
    perolehan" (evaluasi #5). JAGA SELARAS dengan create_asset: bentuk dokumen
    photoless di bawah harus identik dengan `asset_doc` pada create_asset.

    Melewati lapisan Idempotency-Key (pemanggil menangani pengulangan) tetapi
    TIDAK melewati: kunci kegiatan disahkan, validasi pegawai (opt-in),
    keunikan kode+NUP per kegiatan, registry field (model AssetCreate), audit,
    dan notifikasi realtime.
    """
    await ensure_activity_not_sealed(data.activity_id)
    await _enforce_pegawai_terdaftar(data.pengguna_nip)
    existing = await db.assets.find_one({
        "asset_code": data.asset_code, "NUP": data.NUP or "",
        "activity_id": data.activity_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Kombinasi Kode Barang '{data.asset_code}' dan NUP '{data.NUP}' sudah digunakan dalam kegiatan ini")
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    asset_doc = {
        "id": asset_id,
        **data.model_dump(),
        "photos": [],
        "photo_gridfs_ids": [],
        "photo_thumbnails": [],
        "photo": None,
        "thumbnail": None,
        "gallery_thumbnail": None,
        "thumbnail_index": 0,
        "document_checklist": [],
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }
    # SPASIAL: turunkan `geo` (GeoJSON Point) dari pasangan koordinat string
    # agar aset masuk indeks 2dsphere. Tanpa ini kueri peta per-area memindai
    # seluruh koleksi. Lihat spasial_utils.py.
    terapkan_geo(asset_doc)
    await db.assets.insert_one(asset_doc)
    invalidate_asset_cache()
    # Selaras create_asset (janji docstring): tanpa ini aset hasil Pengadaan
    # tak pernah masuk indeks pencarian sampai reindex manual.
    jadwalkan_sync("assets", asset_doc)
    await log_audit("create", data.activity_id, asset_id, data.asset_code,
                    data.asset_name, audit_user,
                    detail="Draft aset dibuat dari perolehan Pengadaan",
                    nup=data.NUP or "")
    await notify_asset_change(data.activity_id, "asset_created",
                              {"id": asset_id, "asset_code": data.asset_code,
                               "asset_name": data.asset_name}, audit_user)
    return asset_doc


@assets_router.post("/assets", response_model=AssetResponse)
async def create_asset(asset: AssetCreate, request: Request, _user: dict = Depends(require_writer)):
    """Create a new asset. Supports Idempotency-Key header to safely retry on network errors."""
    # Idempotency check: if same key was seen within the TTL window (24h), return cached response
    idem_key = kunci_idem(request.headers.get("Idempotency-Key", ""), _user)
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            logger.info(f"Idempotent replay for key {idem_key[:8]}...")
            return AssetResponse(**cached["response"])
        # DEDUP PERMANEN (temuan audit G3): cache respons di atas ber-TTL 24
        # jam, sedangkan antrean luring bisa jauh lebih tua. Dokumen aset
        # sendiri menyimpan idem_key sejak dibuat, jadi replay yang datang
        # SETELAH cache kedaluwarsa tetap terdeteksi di sini — dikembalikan
        # aset yang sudah ada, bukan menciptakan kembarannya.
        _sudah = await db.assets.find_one({"idem_key": idem_key}, {"_id": 0})
        if _sudah:
            logger.info(f"Idempotent replay (via asset doc) for key {idem_key[:8]}...")
            # _strip_media WAJIB di sini juga: tanpa itu balasan REPLAY membawa
            # base64 seluruh foto aset, sementara jalur sukses tepat di bawah
            # justru membuangnya. Replay lazim terjadi persis saat sinyal buruk —
            # keadaan yang paling tak sanggup menanggung respons multi-MB.
            return AssetResponse(**_strip_media(
                {k: v for k, v in _sudah.items() if k in AssetResponse.model_fields}))
        # Atomically claim the key so concurrent duplicates can't both run.
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return AssetResponse(**cached["response"])
        elif _idem == "pending":
            raise HTTPException(status_code=409, detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    # ISOLASI SATKER: aset hanya boleh dibuat pada kegiatan satker user.
    await pastikan_akses_kegiatan_id(_user, asset.activity_id)
    # Kegiatan yang sudah disahkan terkunci — tolak penambahan aset (423)
    await ensure_activity_not_sealed(asset.activity_id)
    await _enforce_pegawai_terdaftar(asset.pengguna_nip)

    # Check uniqueness: asset_code + NUP within same activity
    existing_query = {
        "asset_code": asset.asset_code,
        "NUP": asset.NUP or "",
        "activity_id": asset.activity_id
    }
    existing = await db.assets.find_one(existing_query)
    if existing:
        raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{asset.asset_code}' dan NUP '{asset.NUP}' sudah digunakan dalam kegiatan ini")
    
    # Check kode_register uniqueness within same activity (if provided)
    if asset.kode_register and asset.activity_id:
        kr_existing = await db.assets.find_one({
            "kode_register": asset.kode_register,
            "activity_id": asset.activity_id
        })
        if kr_existing:
            raise HTTPException(status_code=400, detail=f"Kode Register '{asset.kode_register}' sudah digunakan dalam kegiatan ini")
    
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Process photos: store in GridFS + generate thumbnails (atomic with rollback)
    photos = asset.photos or []
    if asset.photo and not photos:
        photos = [asset.photo]
    
    photo_gridfs_ids = []
    photo_thumbnails = []
    thumbnail = None
    gallery_thumbnail = None
    
    if photos:
        result = await process_photos_for_storage(photos)
        photo_gridfs_ids = result["gridfs_ids"]
        photo_thumbnails = result["thumbnails"]
        cover_idx = min(asset.thumbnail_index or 0, len(photos) - 1)
        thumbnail = await asyncio.to_thread(create_thumbnail, photos[cover_idx])
        gallery_thumbnail = await asyncio.to_thread(create_gallery_thumbnail, photos[cover_idx])

    asset_doc = {
        "id": asset_id,
        **asset.model_dump(),
        # SUMBER TUNGGAL foto = GridFS. Base64 inline TIDAK lagi dipersist
        # (dulu foto tersimpan 3×: photos[] + photo + GridFS → dokumen Mongo
        # membengkak mendekati batas 16MB dan tiap baca full-doc menarik
        # multi-MB). Semua jalur baca sudah GridFS-first dengan fallback inline
        # untuk dokumen legacy.
        "photos": [],
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_thumbnails": photo_thumbnails,
        "photo": None,
        "thumbnail": thumbnail,
        "gallery_thumbnail": gallery_thumbnail,
        "thumbnail_index": asset.thumbnail_index or 0,
        "document_checklist": [item.model_dump() for item in (asset.document_checklist or [])],
        "created_at": now,
        "updated_at": now,  # delta cursor for /assets/offline-snapshot
        "version": 1,  # OCC: initial version
        # PENANDA IDEMPOTENSI PERMANEN (temuan audit G3): kunci distempel ke
        # dokumen aset SENDIRI — dokumen tak kedaluwarsa, jadi dedup-nya juga
        # tidak. Diperiksa sebelum insert dan dijaga indeks unik parsial
        # idem_key_unik (indexes.py) + DuplicateKeyError sebagai jaring terakhir.
        **({"idem_key": idem_key} if idem_key else {}),
    }

    # SPASIAL: turunkan `geo` untuk indeks 2dsphere (lihat spasial_utils.py).
    terapkan_geo(asset_doc)

    # SPASIAL (integrasi inventarisasi → denah): aset baru ber-koordinat
    # langsung menempati node denah aktif pemuat titiknya — panel isi lokasi
    # dan angka "Tercatat" opname hidup dari pencatatan, tanpa langkah
    # penempatan terpisah. Lihat spasial_penempatan.py.
    lokasi_otomatis = await sp.penempatan_dari_inventarisasi(
        {}, asset_doc, _user.get("username", ""), now)
    if lokasi_otomatis:
        asset_doc["lokasi_spasial"] = lokasi_otomatis

    try:
        await db.assets.insert_one(asset_doc)
    except DuplicateKeyError:
        # Dua replay berpacu melewati pemeriksaan di atas — indeks unik parsial
        # idem_key_unik menghentikan yang kalah. Kembalikan aset yang menang:
        # bagi klien keduanya adalah SATU simpanan yang sama.
        for gid in photo_gridfs_ids:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        _menang = await db.assets.find_one({"idem_key": idem_key}, {"_id": 0}) if idem_key else None
        if _menang:
            return AssetResponse(**_strip_media(
                {k: v for k, v in _menang.items() if k in AssetResponse.model_fields}))
        raise HTTPException(status_code=409, detail="Aset dengan kunci idempotensi ini sudah tersimpan")
    except Exception as e:
        # Rollback GridFS photos on DB insert failure
        for gid in photo_gridfs_ids:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(
                status_code=413,
                detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto."
            )
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")
    
    logger.info(f"Asset created: {asset.asset_code}")
    # Riwayat penempatan ditulis SETELAH insert sukses — riwayat tak boleh
    # mendahului kenyataan (pola set_lokasi_aset). Replay DuplicateKeyError
    # sudah return lebih awal, jadi riwayat tak pernah dobel.
    if lokasi_otomatis:
        await sp.catat_penempatan(asset_doc, lokasi_otomatis,
                                  _user.get("username", ""), now)
    invalidate_asset_cache()
    # Sinkron indeks Meilisearch (best-effort, non-blocking; no-op bila nonaktif).
    jadwalkan_sync("assets", asset_doc)

    # Jurnal Buku Barang otomatis (M-MODUL): aset baru → entri perolehan.
    # Kode dari helper kode_jurnal_aset_baru: golongan 7 → 502 KDP,
    # asal beli/pengadaan → 101, selain itu 100. Best-effort — tidak
    # menggagalkan pencatatan asetnya.
    try:
        from mutasi_bmn_utils import kode_jurnal_aset_baru as _kj
        from pembukuan_utils import parse_harga as _ph
        from shared_utils import catat_mutasi_bmn as _cm
        _kode_trx = _kj(asset.asset_code,
                        getattr(asset, "perolehan_dari_nama", ""))
        _tgl = str(asset.purchase_date or "")[:10]
        if not (len(_tgl) == 10 and _tgl[4] == "-" and _tgl[7] == "-"):
            _tgl = str(now)[:10]
        await _cm({
            "asset_id": asset_id, "kode_transaksi": _kode_trx,
            "kode_barang": str(asset.asset_code or ""),
            "nup": str(asset.NUP or ""),
            "tanggal_buku": _tgl,
            "jumlah": 1, "nilai": _ph(asset.purchase_price),
            "sumber_modul": "aset", "ref_id": asset_id,
            "keterangan": "Pencatatan aset baru",
            "oleh": _user.get("username", "system")})
    except Exception:
        logger.warning("Jurnal otomatis aset baru gagal (non-fatal)", exc_info=True)

    # Audit actor comes from the authenticated JWT identity (can't be spoofed);
    # the X-Audit-User header is only a fallback hint.
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    await log_audit("create", asset.activity_id, asset_id, asset.asset_code, asset.asset_name, audit_user, detail="Aset baru ditambahkan", nup=asset.NUP or "")
    await notify_asset_change(asset.activity_id, "asset_created", {"id": asset_id, "asset_code": asset.asset_code, "asset_name": asset.asset_name}, audit_user, user_id=audit_user_id)

    # Respons TANPA media (lihat _strip_media): klien sudah punya fotonya —
    # jangan kirim balik base64 besar. Salinan dangkal agar asset_doc asli utuh.
    response = AssetResponse(**_strip_media({**asset_doc}))
    # Cache the response for idempotent retries
    if idem_key:
        await store_idempotent_response(idem_key, response.model_dump(mode="json"), 200)
    return response

def _strip_media(asset: dict) -> dict:
    """Ganti media base64 (foto + berkas checklist) dengan array kosong sambil
    menyisipkan photo_count/document_count. Dipakai GET ?exclude_media=true dan
    respons tulis (POST/PUT/PATCH) — klien sudah memegang medianya sendiri,
    mengirim balik ratusan KB base64 hanya membuang kuota & waktu."""
    real_photos = asset.get("photos", []) or []
    asset["photo_count"] = len(asset.get("photo_gridfs_ids") or []) or len(real_photos)
    asset["photos"] = []
    asset.pop("photo", None)
    if asset.get("document_checklist"):
        asset["document_checklist"] = [
            {**item, "photos": [], "documents": [], "photo_count": len(item.get("photos", []) or []), "document_count": len(item.get("documents", []) or [])}
            for item in asset["document_checklist"]
        ]
    return asset


@assets_router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str, exclude_media: bool = False, _user: dict = Depends(require_user)):
    """Get a single asset by ID. Use ?exclude_media=true for a lightweight response without base64 photos/documents."""
    if exclude_media:
        # Buang media DI SISI MONGO (bukan di Python setelah dokumen multi-MB
        # ditarik dari DB) — endpoint ini dipanggil pada SETIAP buka lightbox &
        # form edit. Bentuk hasil identik dengan _strip_media:
        # photos=[], photo dihapus, checklist: media dikosongkan + counts,
        # field lain (termasuk thumbnail/photo_thumbnails) tetap utuh.
        docs = await db.assets.aggregate([
            {"$match": {"id": asset_id}},
            {"$set": {
                "photo_count": {"$cond": [
                    {"$gt": [{"$size": {"$ifNull": ["$photo_gridfs_ids", []]}}, 0]},
                    {"$size": {"$ifNull": ["$photo_gridfs_ids", []]}},
                    {"$size": {"$ifNull": ["$photos", []]}},
                ]},
                "document_checklist": {"$map": {
                    "input": {"$ifNull": ["$document_checklist", []]},
                    "as": "item",
                    "in": {"$mergeObjects": ["$$item", {
                        "photos": [], "documents": [],
                        "photo_count": {"$size": {"$ifNull": ["$$item.photos", []]}},
                        "document_count": {"$size": {"$ifNull": ["$$item.documents", []]}},
                    }]},
                }},
            }},
            {"$set": {"photos": []}},
            {"$unset": ["_id", "photo"]},
        ]).to_list(1)
        if not docs:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        # Isolasi satker (REVIEW-9 R8): jalur ringan ini SEBELUMNYA langsung
        # return tanpa guard — IDOR baca metadata aset satker lain by id
        # (dipanggil pada SETIAP buka lightbox/form edit).
        await pastikan_akses_aset(_user, docs[0])
        await lengkapi_psp(docs, _user)
        return AssetResponse(**docs[0])
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    # Kontrak GET penuh = "beserta media". Dokumen bersih (GridFS-only,
    # photos=[]) dihidrasikan dari blob agar konsumen lama tetap bekerja.
    if not (asset.get("photos") or []) and (asset.get("photo_gridfs_ids") or []):
        # Baca semua blob foto PARALEL (I/O GridFS) alih-alih berurutan — detail
        # aset multi-foto tak lagi N round-trip serial. gather menjaga urutan.
        async def _hidrasi_foto(gid):
            if not gid:
                return ""
            try:
                raw = await get_photo_from_gridfs(gid)
                if raw:
                    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
            except Exception:
                pass
            return ""
        hydrated = list(await asyncio.gather(
            *[_hidrasi_foto(gid) for gid in asset["photo_gridfs_ids"]]))
        asset["photos"] = hydrated
        cover = asset.get("thumbnail_index") or 0
        if 0 <= cover < len(hydrated) and hydrated[cover]:
            asset["photo"] = hydrated[cover]
    await lengkapi_psp([asset], _user)
    return AssetResponse(**asset)


@assets_router.get("/assets/{asset_id}/media")
async def get_asset_media(asset_id: str, _user: dict = Depends(require_user)):
    """Return photo thumbnails + document_checklist media for the form.
    Full-size photos are in GridFS and accessed via /assets/{id}/photos/{index}."""
    asset = await db.assets.find_one({"id": asset_id}, {
        "_id": 0, "id": 1, "photos": 1, "photo_thumbnails": 1,
        "photo_gridfs_ids": 1, "document_checklist": 1, "activity_id": 1
    })
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    
    # Return thumbnails for display; if no thumbnails yet (legacy), generate on the fly
    photo_thumbnails = asset.get("photo_thumbnails", []) or []
    photo_gridfs_ids = asset.get("photo_gridfs_ids", []) or []
    photos = asset.get("photos", []) or []
    
    # Fallback for legacy assets without thumbnails: generate from full photos
    if photos and not photo_thumbnails:
        photo_thumbnails = await asyncio.to_thread(
            lambda pics: [generate_photo_thumbnail(p) or "" for p in pics], photos)
    
    checklist = asset.get("document_checklist", []) or []
    # For document checklist, also return thumbnails for photos
    checklist_media = []
    for item in checklist:
        item_photos = item.get("photos", []) or []
        item_photo_thumbs = item.get("photo_thumbnails", []) or []
        if item_photos and not item_photo_thumbs:
            item_photo_thumbs = await asyncio.to_thread(
                lambda pics: [generate_photo_thumbnail(p) or "" for p in pics], item_photos)
        checklist_media.append({
            "name": item.get("name", ""),
            "photo_thumbnails": item_photo_thumbs,
            "photo_count": len(item_photos),
            "documents": [{"name": d.get("name", "document.pdf")} for d in (item.get("documents", []) or [])],
            "document_count": len(item.get("documents", []) or [])
        })
    
    return {
        "photo_thumbnails": photo_thumbnails,
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_count": len(photos) if not photo_gridfs_ids else len(photo_gridfs_ids),
        "document_checklist_media": checklist_media
    }


@assets_router.get("/assets/{asset_id}/checklist-full")
async def get_asset_checklist_full(asset_id: str, _user: dict = Depends(require_user)):
    """Return checklist metadata + thumbnails ONLY. Photo full bytes and PDF
    bytes are streamed via dedicated endpoints (see below) — embedding them
    inline produced multi-MB JSON responses that timed out at the proxy / hung
    the browser when an asset had several large PDFs.

    Per item we return:
      - name / checked / notes
      - photo_thumbnails: array of small base64 thumbs (already cheap)
      - photo_count: total # of photos (for `photos.length` parity in the form
        state — the actual photo bytes are loaded by the <img> tag on demand)
      - documents: array of {name, idx} (NO data field)
    """
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1, "activity_id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    checklist = asset.get("document_checklist", []) or []
    normalized = []
    for item in checklist:
        item_photos = item.get("photos", []) or []
        item_thumbs = item.get("photo_thumbnails", []) or []
        # Generate thumbs on the fly for legacy items
        if item_photos and not item_thumbs:
            item_thumbs = await asyncio.to_thread(
                lambda pics: [generate_photo_thumbnail(p) or "" for p in pics], item_photos)
        # Trim to actual count — never return more thumbs than photos
        if len(item_thumbs) > len(item_photos):
            item_thumbs = item_thumbs[: len(item_photos)]
        normalized.append({
            "name": item.get("name", ""),
            "checked": bool(item.get("checked", False)),
            "notes": item.get("notes", ""),
            "photo_thumbnails": item_thumbs,
            "photo_count": len(item_photos),
            "documents": [
                {"name": d.get("name", "document.pdf"), "idx": idx}
                for idx, d in enumerate(item.get("documents", []) or [])
            ],
            "document_count": len(item.get("documents", []) or []),
        })
    return {"document_checklist": normalized}


# ============================================================================
# MEDIA STREAMING (photos / checklist photos / checklist PDFs)
#
# Auth posture: these are consumed by plain <img src="..."> tags and
# window.open(), neither of which can attach Authorization headers, so they
# accept EITHER the header OR a ?token=<jwt> query param via
# require_user_or_query_token. This closes the previous fully-anonymous read
# hole while keeping <img>/window.open working (see auth_utils for the URL-in-
# log tradeoff note). The frontend appends the token via lib/mediaUrl.js.
#
# Caching: responses are browser-cacheable. The frontend appends a
# ?v={asset.version} cache-buster to every media URL, so any edit (which
# bumps `version` via OCC) yields a brand-new URL and busts the cache. The
# version-based ETag additionally lets the browser revalidate cheaply (304)
# once max-age expires. X-Content-Type-Options: nosniff stops MIME sniffing.
# ============================================================================
MEDIA_CACHE_CONTROL = "private, max-age=86400"


# --- Varian PREVIEW foto (lebar dibatasi) untuk lightbox/galeri -------------
# Full-res (≤1920px, ~900KB) terlalu berat untuk dilihat cepat di jaringan
# lapangan. ?w=<lebar> menghasilkan JPEG yang diperkecil (~100-250KB) —
# di-resize SEKALI lalu di-cache di koleksi media_previews (ber-TTL), sehingga
# permintaan berikutnya (siapa pun penggunanya) langsung dari cache.
_PREVIEW_WIDTHS = {256, 640, 1280}  # 256 = kartu galeri, 1280 = lightbox
_PREVIEW_TTL_DAYS = 30
_preview_index_ready = False


async def _ensure_preview_index():
    global _preview_index_ready
    if _preview_index_ready:
        return
    _preview_index_ready = True
    try:
        await db.media_previews.create_index("created_at", expireAfterSeconds=_PREVIEW_TTL_DAYS * 86400)
    except Exception:  # index sudah ada / tak bisa dibuat — cache tetap berfungsi
        pass


def _resize_webp(photo_bytes: bytes, max_w: int, quality: int = 82) -> bytes:
    """Perkecil gambar ke lebar maks `max_w` (rasio dipertahankan) → **WebP**.
    Sumber bisa JPEG (foto lama) atau WebP (foto asli yang sudah dioptimalkan
    Tinify); keluaran selalu WebP — ~25-35% lebih kecil dari JPEG pada kualitas
    setara, sehingga preview galeri (w=256) & lightbox (w=1280) yang DITAMPILKAN
    ke browser lebih ringan. Kualitas mewarisi sumber (untuk foto asli:
    hasil optimasi Tinify). Sinkron & cepat; hasil di-cache oleh pemanggil.
    method=6 = kompresi terbaik."""
    import io
    from PIL import Image as PILImage
    img = PILImage.open(io.BytesIO(photo_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if w > max_w:
        img = img.resize((max_w, max(1, round(h * max_w / w))), PILImage.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()


def _media_headers(etag: str, extra: dict = None) -> dict:
    headers = {"Cache-Control": MEDIA_CACHE_CONTROL, "ETag": etag,
               "X-Content-Type-Options": "nosniff"}
    if extra:
        headers.update(extra)
    return headers


def _not_modified(request: Request, etag: str):
    """Return a 304 Response when the client already holds this exact version."""
    if request.headers.get("if-none-match", "").strip() == etag:
        return Response(status_code=304, headers=_media_headers(etag))
    return None


@assets_router.get("/assets/{asset_id}/checklist/{item_idx}/photos/{photo_idx}")
async def get_asset_checklist_photo(asset_id: str, item_idx: int, photo_idx: int, request: Request,
                                    _user: dict = Depends(require_user_or_query_token)):
    """Stream a single inline checklist photo by item & photo index."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1, "version": 1, "activity_id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    checklist = asset.get("document_checklist", []) or []
    if item_idx < 0 or item_idx >= len(checklist):
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")
    photos = (checklist[item_idx] or {}).get("photos", []) or []
    if photo_idx < 0 or photo_idx >= len(photos):
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    etag = f'"cl-{asset_id}-{item_idx}-p{photo_idx}-v{int(asset.get("version", 1) or 1)}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified
    photo_b64 = photos[photo_idx]
    if not isinstance(photo_b64, str):
        raise HTTPException(status_code=500, detail="Format foto tidak valid")
    if photo_b64.startswith("data:"):
        try:
            _, data = photo_b64.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=500, detail="Format foto tidak valid")
    else:
        data = photo_b64
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=500, detail="Foto rusak")
    return Response(content=raw, media_type="image/jpeg", headers=_media_headers(etag))


@assets_router.get("/assets/{asset_id}/checklist/{item_idx}/documents/{doc_idx}")
async def get_asset_checklist_document(asset_id: str, item_idx: int, doc_idx: int, request: Request,
                                       _user: dict = Depends(require_user_or_query_token)):
    """Stream a single inline checklist PDF by item & document index."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1, "version": 1, "activity_id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    checklist = asset.get("document_checklist", []) or []
    if item_idx < 0 or item_idx >= len(checklist):
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")
    docs = (checklist[item_idx] or {}).get("documents", []) or []
    if doc_idx < 0 or doc_idx >= len(docs):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    etag = f'"cl-{asset_id}-{item_idx}-d{doc_idx}-v{int(asset.get("version", 1) or 1)}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified
    doc = docs[doc_idx] or {}
    data_url = doc.get("data", "") or ""
    if not data_url:
        raise HTTPException(status_code=404, detail="Data dokumen kosong")
    if data_url.startswith("data:"):
        try:
            _, data = data_url.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=500, detail="Format dokumen tidak valid")
    else:
        data = data_url
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=500, detail="Dokumen rusak")
    name = doc.get("name", "document.pdf") or "document.pdf"
    return Response(
        content=raw,
        media_type="application/pdf",
        headers=_media_headers(etag, {"Content-Disposition": f'inline; filename="{name}"'}),
    )


def _tebak_media_type(b: bytes) -> str:
    """Content-type gambar dari magic-byte. Foto GridFS kini bisa JPEG ATAU
    WebP (konverter latar), jadi serve foto penuh harus content-type-aware."""
    if not b or len(b) < 12:
        return "image/jpeg"
    if b[:2] == b"\xff\xd8":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


@assets_router.get("/assets/{asset_id}/photos/{photo_index}")
async def get_asset_photo_full(asset_id: str, photo_index: int, request: Request, thumb: int = 0,
                               w: int = 0,
                               _user: dict = Depends(require_user_or_query_token)):
    """Stream a full-resolution photo from GridFS or fallback to inline base64.

    ?thumb=1 returns the small per-photo thumbnail instead: the one stored in
    `photo_thumbnails` at upload time, or (legacy assets without stored
    thumbnails) one generated on the fly — same fallback /media uses, cheap
    enough per request. The form's photo strip uses this so each thumbnail
    loads progressively via <img src> and gets cached by the browser.

    ?w=640|1280 returns a width-capped PREVIEW JPEG (progressive, q80) —
    resized once then cached in media_previews, so the lightbox loads a
    ~100-250KB image instead of the full ~900KB original.
    """
    asset = await db.assets.find_one({"id": asset_id}, {
        "_id": 0, "photo_gridfs_ids": 1, "photos": 1, "photo_thumbnails": 1,
        "version": 1, "activity_id": 1
    })
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)

    preview_w = w if (w in _PREVIEW_WIDTHS and not thumb) else 0
    # Penanda "webp" pada kunci preview: entri cache JPEG lama (kunci tanpa
    # penanda) tak lagi cocok → preview baru dibuat sebagai WebP seketika; entri
    # JPEG lama kedaluwarsa sendiri via TTL. Juga membuat cache browser refresh.
    etag = (f'"{asset_id}-p{photo_index}{"-t" if thumb else ""}'
            f'{f"-w{preview_w}webp" if preview_w else ""}-v{int(asset.get("version", 1) or 1)}"')
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified

    # Preview: sajikan dari cache bila sudah pernah di-resize (kunci = etag,
    # otomatis basi saat versi aset berubah; koleksi ber-TTL).
    if preview_w:
        await _ensure_preview_index()
        cached = await db.media_previews.find_one({"_id": etag})
        if cached and cached.get("data"):
            _cb = bytes(cached["data"])
            return Response(content=_cb, media_type=_tebak_media_type(_cb),
                            headers=_media_headers(etag))

    gridfs_ids = asset.get("photo_gridfs_ids", []) or []
    photos = asset.get("photos", []) or []

    if thumb:
        thumbnails = asset.get("photo_thumbnails", []) or []
        thumb_b64 = thumbnails[photo_index] if 0 <= photo_index < len(thumbnails) else ""
        if not thumb_b64:
            # Legacy asset without stored per-photo thumbnails: generate on the fly
            if photo_index < len(photos) and photos[photo_index]:
                thumb_b64 = await asyncio.to_thread(generate_photo_thumbnail, photos[photo_index]) or ""
            elif photo_index < len(gridfs_ids) and gridfs_ids[photo_index]:
                photo_bytes = await get_photo_from_gridfs(gridfs_ids[photo_index])
                if photo_bytes:
                    thumb_b64 = await asyncio.to_thread(generate_photo_thumbnail, base64.b64encode(photo_bytes).decode("utf-8")) or ""
        if thumb_b64:
            data = thumb_b64.split(",", 1)[1] if thumb_b64.startswith("data:") else thumb_b64
            try:
                _tb = base64.b64decode(data)
                # Deteksi tipe dari magic-byte: thumbnail kini WebP (yang lama
                # bisa JPEG) — nosniff mengharuskan Content-Type benar.
                return Response(content=_tb, media_type=_tebak_media_type(_tb),
                                headers=_media_headers(etag))
            except Exception:
                pass  # corrupt stored thumbnail — fall through to the full photo

    # Ambil byte foto penuh: GridFS dulu, lalu fallback inline base64
    photo_bytes = None
    if photo_index < len(gridfs_ids) and gridfs_ids[photo_index]:
        photo_bytes = await get_photo_from_gridfs(gridfs_ids[photo_index])
    if photo_bytes is None and photo_index < len(photos):
        photo_b64 = photos[photo_index]
        # Guard: elemen legacy bisa None / non-str (data rusak) — jangan sampai
        # `.startswith` melempar AttributeError (500); perlakukan sebagai tak ada
        # (jatuh ke 404 bersih di bawah). Konsisten dgn guard di endpoint checklist.
        if isinstance(photo_b64, str) and photo_b64:
            data = photo_b64.split(',', 1)[1] if photo_b64.startswith('data:') else photo_b64
            try:
                photo_bytes = base64.b64decode(data)
            except Exception:
                photo_bytes = None
    if photo_bytes is None:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")

    # Preview: resize→WebP sekali → cache → sajikan. Gagal / tak lebih kecil →
    # sajikan foto asli (content-type dideteksi).
    if preview_w:
        try:
            preview = _resize_webp(photo_bytes, preview_w)
            if len(preview) < len(photo_bytes):
                try:
                    await db.media_previews.update_one(
                        {"_id": etag},
                        {"$set": {"data": preview, "created_at": datetime.now(timezone.utc)}},
                        upsert=True,
                    )
                except Exception:
                    pass  # cache best-effort — respons tetap dilayani
                return Response(content=preview, media_type="image/webp",
                                headers=_media_headers(etag))
        except Exception:
            pass  # gambar tak valid / Pillow gagal — sajikan asli

    return Response(content=photo_bytes, media_type=_tebak_media_type(photo_bytes),
                    headers=_media_headers(etag))


@assets_router.post("/assets/{asset_id}/photos/{photo_index}/rotate")
async def rotate_asset_photo(asset_id: str, photo_index: int, request: Request,
                             _user: dict = Depends(require_writer)):
    """Putar foto ke-`photo_index` SECARA PERMANEN (default 90° searah jarum jam).

    Rotasi mengganti byte foto ASLI di GridFS + regen thumbnail per-foto dan
    (bila foto cover) thumbnail daftar/galeri, lalu menaikkan `version`. Akibatnya
    thumbnail, galeri, unduh, dan layar penuh SEMUA ikut berputar (permintaan
    "berubah total tanpa terkecuali") — bukan sekadar tampilan sesaat. Cache
    preview otomatis basi karena etag memuat versi.

    OCC via If-Match (opsional) + Idempotency-Key (opsional). Body opsional
    `{"degrees": 90}` (kelipatan 90; default & minimum efektif 90).
    """
    # --- Idempotency: putar ulang dgn kunci sama tak menggandakan rotasi ---
    idem_key = kunci_idem(request.headers.get("Idempotency-Key", ""), _user)
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            return cached["response"]
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return cached["response"]
        elif _idem == "pending":
            raise HTTPException(status_code=409, detail="Permintaan sedang diproses, coba lagi sebentar")

    try:
        body = await request.json()
    except Exception:
        body = {}
    degrees = normalisasi_derajat(body.get("degrees", 90)) if isinstance(body, dict) else 90
    if degrees == 0:
        degrees = 90  # tombol putar selalu memutar; 0 tak berarti

    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, existing)
    await ensure_activity_not_sealed(existing.get("activity_id"))

    # --- OCC (If-Match) ---
    if_match = request.headers.get("If-Match", "").strip().strip('"')
    current_version = int(existing.get("version", 1) or 1)
    if if_match:
        try:
            expected = int(if_match)
        except ValueError:
            expected = current_version
        if expected != current_version:
            raise HTTPException(status_code=409, detail={
                "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                "current_version": current_version, "your_version": expected,
            })

    gridfs_ids = list(existing.get("photo_gridfs_ids") or [])
    photos = list(existing.get("photos") or [])
    thumbnails = list(existing.get("photo_thumbnails") or [])
    n = max(len(gridfs_ids), len(photos))
    if photo_index < 0 or photo_index >= n:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")

    # Ambil byte foto asli: GridFS dulu, lalu fallback inline base64 (legacy)
    old_gid = gridfs_ids[photo_index] if photo_index < len(gridfs_ids) else None
    src_bytes = await get_photo_from_gridfs(old_gid) if old_gid else None
    if src_bytes is None and photo_index < len(photos) and photos[photo_index]:
        pb = photos[photo_index]
        try:
            src_bytes = base64.b64decode(pb.split(",", 1)[1] if pb.startswith("data:") else pb)
        except Exception:
            src_bytes = None
    if src_bytes is None:
        raise HTTPException(status_code=404, detail="Byte foto tidak ditemukan")

    # Putar (Pillow) → JPEG baru → data-URI untuk helper penyimpanan
    try:
        rotated = await asyncio.to_thread(rotate_jpeg_bytes, src_bytes, degrees)
    except Exception as e:
        logger.error(f"Rotate gagal aset {asset_id} idx {photo_index}: {e}")
        raise HTTPException(status_code=422, detail="Gagal memutar foto (berkas bukan gambar valid)")
    rotated_uri = "data:image/jpeg;base64," + base64.b64encode(rotated).decode("utf-8")

    set_fields = {}
    new_gid = None
    if old_gid or photo_index < len(gridfs_ids):
        new_gid = await store_photo_to_gridfs(rotated_uri)
        while len(gridfs_ids) <= photo_index:
            gridfs_ids.append("")
        gridfs_ids[photo_index] = new_gid
        set_fields["photo_gridfs_ids"] = gridfs_ids
    else:  # foto inline legacy — ganti di tempat
        while len(photos) <= photo_index:
            photos.append("")
        photos[photo_index] = rotated_uri
        set_fields["photos"] = photos

    # Regen thumbnail per-foto (strip form + placeholder lightbox)
    while len(thumbnails) <= photo_index:
        thumbnails.append("")
    thumbnails[photo_index] = await asyncio.to_thread(generate_photo_thumbnail, rotated_uri) or ""
    set_fields["photo_thumbnails"] = thumbnails

    # Foto cover → regen thumbnail daftar (data-URI) + gallery_thumbnail
    cover_idx = int(existing.get("thumbnail_index") or 0)
    if photo_index == cover_idx:
        set_fields["thumbnail"] = await asyncio.to_thread(create_thumbnail, rotated_uri)
        set_fields["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, rotated_uri)

    # Stempel updated_at WAJIB ikut (temuan audit G3): delta sinkron luring
    # memfilter pada updated_at, bukan version. Tanpa stempel ini rotasi tak
    # pernah sampai ke cache perangkat lapangan — HP surveyor terus menampilkan
    # foto dengan orientasi lama sambil memegang version yang sudah usang.
    set_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Tulis ber-OCC (CAS pada version) + $inc version → etag preview lama basi
    cas_filter = _build_cas_filter(asset_id, current_version)
    result = await db.assets.update_one(cas_filter, {"$set": set_fields, "$inc": {"version": 1}})
    if result.matched_count == 0:
        # Kalah balapan versi → buang blob baru agar tak jadi yatim
        if new_gid:
            try:
                await delete_photo_from_gridfs(new_gid)
            except Exception:
                pass
        latest = await db.assets.find_one({"id": asset_id}, {"_id": 0, "version": 1})
        raise HTTPException(status_code=409, detail={
            "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
            "current_version": int((latest or {}).get("version", current_version + 1) or current_version + 1),
        })

    # Sukses → hapus blob lama (byte pra-rotasi) agar GridFS tak menumpuk
    if old_gid and new_gid and old_gid != new_gid:
        try:
            await delete_photo_from_gridfs(old_gid)
        except Exception:
            pass

    invalidate_asset_cache()
    new_version = current_version + 1
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    try:
        await log_audit("update", existing.get("activity_id"), asset_id,
                        existing.get("asset_code"), existing.get("asset_name"), audit_user,
                        detail=f"Putar foto #{photo_index + 1} sebesar {degrees}°",
                        nup=existing.get("NUP") or "")
    except Exception:
        pass

    resp = {"id": asset_id, "version": new_version, "photo_index": photo_index,
            "degrees": degrees, "photo_count": len(gridfs_ids) or len(photos)}
    if idem_key:
        try:
            await store_idempotent_response(idem_key, resp, 200)
        except Exception:
            pass
    return resp


# ============================================================================
# DOKUMEN BAST (Berita Acara Serah Terima) — satu file per aset di GridFS.
# Posture sama dengan pengesahan-dokumen (routes/pengesahan.py): upload
# ter-gate auth (admin/user), GET publik + Cache-Control agar bisa dibuka
# via window.open() yang tidak dapat membawa Authorization header.
# ============================================================================
MAX_BAST_BYTES = 10 * 1024 * 1024  # 10MB
_BAST_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}


def _bast_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _BAST_MEDIA_TYPES:
        if name.endswith(ext):
            return ext
    return ""


@assets_router.post("/assets/{asset_id}/bast")
async def upload_asset_bast(
    asset_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_writer),
):
    """Unggah dokumen BAST (PDF/gambar, maks 10MB) — menggantikan yang lama."""
    existing = await db.assets.find_one(
        {"id": asset_id},
        {"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1, "asset_name": 1,
         "NUP": 1, "bast_file_id": 1},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, existing)
    # Kegiatan yang sudah disahkan terkunci — sama seperti mutasi aset lain
    await ensure_activity_not_sealed(existing.get("activity_id"))

    filename = (file.filename or "bast.pdf").strip() or "bast.pdf"
    ext = _bast_ext(filename)
    if not ext:
        raise HTTPException(status_code=400, detail="Dokumen BAST harus PDF atau gambar (JPG/PNG/WEBP)")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > MAX_BAST_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran dokumen BAST maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")
    # Untuk gambar: validasi ISI (magic byte) — konsisten dgn lampiran modul lain.
    if ext != ".pdf":
        from shared_utils import cek_magic_gambar
        if not cek_magic_gambar(file_bytes, ext):
            raise HTTPException(status_code=400, detail="Isi berkas tidak cocok tipe gambar")

    # Simpan ke GridFS (pola sama dengan pengesahan-dokumen)
    # GERBANG KOMPRESI — dokumen BAST aset (PDF hasil pindai atau foto).
    from gerbang_media import tulis_media
    file_id = None
    try:
        file_id, _meta = await tulis_media(
            file_bytes, nama=filename, content_type=_BAST_MEDIA_TYPES[ext],
            metadata={"kind": "bast", "asset_id": asset_id})
        filename = _meta["filename"]
    except Exception as e:
        logger.error(f"GridFS store BAST gagal: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan dokumen BAST")

    old_file_id = existing.get("bast_file_id") or ""
    # Sengaja TIDAK menaikkan `version` (OCC): unggah BAST terjadi saat form
    # edit masih terbuka — bump version akan membuat PATCH berikutnya 409.
    # Cache-busting GET memakai bast_file_id yang selalu baru per unggahan.
    # Snapshot kode+nama saat BAST dilampirkan → deteksi BAST usang bila
    # kode/nama berubah kemudian (reklasifikasi / ganti nama).
    from penggunaan_utils import snapshot_bast
    result = await db.assets.update_one(
        {"id": asset_id},
        {"$set": {
            "bast_file_id": str(file_id),
            "bast_filename": filename,
            "bast_snapshot": snapshot_bast(existing),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if old_file_id:
        await delete_document_from_gridfs(old_file_id)

    invalidate_asset_cache()
    # Prefer the authenticated JWT identity over the spoofable header hint.
    audit_user = user.get("name") or user.get("username") or request.headers.get("X-Audit-User", "unknown")
    await log_audit(
        "update", existing.get("activity_id", ""), asset_id,
        existing.get("asset_code", ""), existing.get("asset_name", ""),
        audit_user, detail=f"Dokumen BAST diunggah: {filename}", nup=existing.get("NUP", "") or "",
    )
    logger.info(f"BAST diunggah untuk aset {asset_id}: {filename}")
    return {
        "message": "Dokumen BAST berhasil diunggah",
        "bast_file_id": str(file_id),
        "bast_filename": filename,
    }


@assets_router.get("/assets/{asset_id}/bast")
async def get_asset_bast(asset_id: str, request: Request,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream dokumen BAST aset. Dikonsumsi window.open() (tidak bisa membawa
    Authorization header) → menerima header ATAU ?token=<jwt>. ETag berbasis
    bast_file_id (unik per unggahan) → cacheable."""
    asset = await db.assets.find_one(
        {"id": asset_id},
        {"_id": 0, "bast_file_id": 1, "bast_filename": 1, "activity_id": 1}
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    file_id = asset.get("bast_file_id") or ""
    if not file_id:
        raise HTTPException(status_code=404, detail="Aset belum memiliki dokumen BAST")

    etag = f'"bast-{file_id}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified

    file_bytes = await get_document_from_gridfs(file_id)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="File BAST tidak tersedia")
    name = asset.get("bast_filename", "bast.pdf") or "bast.pdf"
    media_type = _BAST_MEDIA_TYPES.get(_bast_ext(name), "application/octet-stream")
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers=_media_headers(etag, {"Content-Disposition": f'inline; filename="{name}"'}),
    )


@assets_router.put("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: str, asset: AssetCreate, request: Request,
                       _user: dict = Depends(require_writer)):
    """Update an existing asset. Supports OCC via If-Match header (expected version).
    Returns 409 Conflict if another user modified the asset in the meantime."""
    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Kegiatan yang sudah disahkan terkunci — cek activity asal DAN tujuan
    # (bila aset dipindah antar kegiatan lewat PUT).
    await pastikan_akses_aset(_user, existing)
    if asset.activity_id and asset.activity_id != existing.get("activity_id"):
        await pastikan_akses_kegiatan_id(_user, asset.activity_id)
    await ensure_activity_not_sealed(existing.get("activity_id"))
    if asset.activity_id and asset.activity_id != existing.get("activity_id"):
        await ensure_activity_not_sealed(asset.activity_id)
    await _enforce_pegawai_terdaftar(asset.pengguna_nip,
                                     existing.get("pengguna_nip"))

    # --- Optimistic Concurrency Control (OCC) ---
    # Client sends If-Match header with the version they loaded. If server has a
    # newer version, reject with 409 so client can show conflict-resolution UI.
    if_match = request.headers.get("If-Match", "").strip().strip('"')
    current_version = int(existing.get("version", 1))
    if if_match:
        try:
            expected = int(if_match)
        except ValueError:
            expected = current_version
        if expected != current_version:
            # Return minimal current state so client can show diff / refresh
            current_clean = {k: v for k, v in existing.items() if k != "_id"}
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": current_version,
                    "your_version": expected,
                    "current": {
                        "id": current_clean.get("id"),
                        "version": current_version,
                        "asset_code": current_clean.get("asset_code"),
                        "asset_name": current_clean.get("asset_name"),
                    },
                },
            )
    
    # Check uniqueness: asset_code + NUP within same activity (exclude self)
    if (asset.asset_code != existing.get("asset_code") or 
        (asset.NUP or "") != existing.get("NUP", "")):
        dup_query = {
            "asset_code": asset.asset_code,
            "NUP": asset.NUP or "",
            "activity_id": asset.activity_id,
            "id": {"$ne": asset_id}
        }
        dup = await db.assets.find_one(dup_query)
        if dup:
            raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{asset.asset_code}' dan NUP '{asset.NUP}' sudah digunakan dalam kegiatan ini")
    
    # Check kode_register uniqueness within same activity (exclude self)
    if asset.kode_register and asset.activity_id:
        kr_existing = await db.assets.find_one({
            "kode_register": asset.kode_register,
            "activity_id": asset.activity_id,
            "id": {"$ne": asset_id}
        })
        if kr_existing:
            raise HTTPException(status_code=400, detail=f"Kode Register '{asset.kode_register}' sudah digunakan dalam kegiatan ini")
    
    photos = asset.photos or []
    if asset.photo and not photos:
        photos = [asset.photo]

    # Generate thumbnail from selected cover photo + GridFS storage
    thumbnail = existing.get("thumbnail")
    gallery_thumbnail = existing.get("gallery_thumbnail")
    old_photos = existing.get("photos", [])

    photo_gridfs_ids = existing.get("photo_gridfs_ids", [])
    photo_thumbnails = existing.get("photo_thumbnails", [])
    old_gridfs_for_rollback = list(photo_gridfs_ids)  # pre-existing IDs (keep if new upload fails)

    # Jumlah foto lama yang SEBENARNYA (GridFS-first; dokumen ter-migrasi punya
    # photos=[] tapi gridfs_ids terisi).
    old_count = len([g for g in photo_gridfs_ids if g]) or len(old_photos)
    cover_idx = min(asset.thumbnail_index or 0, len(photos) - 1) if photos \
        else min(asset.thumbnail_index or 0, max(0, old_count - 1))

    if photos and (photos != old_photos or len(photos) != old_count or cover_idx != existing.get("thumbnail_index", 0)):
        thumbnail = await asyncio.to_thread(create_thumbnail, photos[cover_idx])
        gallery_thumbnail = await asyncio.to_thread(create_gallery_thumbnail, photos[cover_idx])
        # Store new photos in GridFS + generate per-photo thumbnails (atomic rollback on error)
        result = await process_photos_for_storage(photos)
        photo_gridfs_ids = result["gridfs_ids"]
        photo_thumbnails = result["thumbnails"]
    elif not photos and old_count == 0:
        thumbnail = None
        gallery_thumbnail = None
        photo_gridfs_ids = []
        photo_thumbnails = []
    # PENJAGA KEHILANGAN SENYAP: payload PUT tanpa foto sementara GridFS masih
    # berisi (klien yang memuat via exclude_media mengirim photos=[]) →
    # PERTAHANKAN foto GridFS yang ada. Penghapusan foto dilakukan lewat
    # PATCH photo_ops (keep[]), bukan PUT kosong.

    # Dokumen LEGACY MURNI (inline ada, blob GridFS belum ada) yang di-PUT
    # tanpa foto: photos=[] akan memusnahkan satu-satunya salinan byte —
    # pertahankan inline lama (dan cover-nya) sampai dokumen termigrasi.
    has_real_gids = any(g for g in photo_gridfs_ids)
    preserve_legacy_inline = (not photos) and (not has_real_gids) and len(old_photos) > 0

    update_data = {
        **asset.model_dump(),
        # Inline base64 tidak dipersist lagi — GridFS adalah sumber tunggal
        # (kecuali preservasi dokumen legacy murni di atas).
        "photos": old_photos if preserve_legacy_inline else [],
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_thumbnails": photo_thumbnails,
        "photo": existing.get("photo") if preserve_legacy_inline else None,
        "thumbnail": thumbnail,
        "gallery_thumbnail": gallery_thumbnail,
        "thumbnail_index": cover_idx,
        "document_checklist": [item.model_dump() for item in (asset.document_checklist or [])],
        "created_at": existing["created_at"],
        # Stamped on every write so the offline snapshot delta sync
        # (GET /assets/offline-snapshot?since=...) picks this change up.
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # SPASIAL: PUT full-replace juga menyentuh koordinat — hitung ulang `geo`
    # (celah lama: jalur ini tak pernah memanggilnya sehingga indeks 2dsphere
    # menyimpan titik basi) + penempatan otomatis inventarisasi (lihat PATCH
    # di bawah / spasial_penempatan.py).
    _geo_unset = sisip_geo_ke_update(existing, update_data)
    lokasi_otomatis = await sp.penempatan_dari_inventarisasi(
        existing, update_data, _user.get("username", ""),
        update_data["updated_at"])
    if lokasi_otomatis:
        update_data["lokasi_spasial"] = lokasi_otomatis

    try:
        # Atomic CAS update: only succeeds if version still matches.
        # Support legacy docs without version field: when current_version==1,
        # also match docs where version is missing ($exists=False).
        cas_filter = _build_cas_filter(asset_id, current_version)
        _ops = {"$set": update_data, "$inc": {"version": 1}}
        if _geo_unset:
            _ops["$unset"] = _geo_unset
        result = await db.assets.update_one(cas_filter, _ops)
        if result.matched_count == 0:
            # Someone else bumped version between our read and write — 409
            fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0, "version": 1, "asset_code": 1, "asset_name": 1})
            # Rollback GridFS uploads that were freshly created for this request
            if photo_gridfs_ids != old_gridfs_for_rollback:
                for gid in photo_gridfs_ids:
                    if gid and gid not in old_gridfs_for_rollback:
                        try:
                            await delete_photo_from_gridfs(gid)
                        except Exception:
                            pass
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain (race condition). Muat ulang dan coba lagi.",
                    "current_version": (fresh or {}).get("version", current_version + 1),
                    "your_version": current_version,
                    "current": fresh or {},
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        # Rollback new GridFS uploads on write error
        if photo_gridfs_ids != old_gridfs_for_rollback:
            for gid in photo_gridfs_ids:
                if gid and gid not in old_gridfs_for_rollback:
                    try:
                        await delete_photo_from_gridfs(gid)
                    except Exception:
                        pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(
                status_code=413,
                detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto."
            )
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")

    # After successful update: delete GridFS IDs that were replaced (old no-longer-referenced)
    if photo_gridfs_ids != old_gridfs_for_rollback:
        new_set = set(x for x in photo_gridfs_ids if x)
        for old_gid in old_gridfs_for_rollback:
            if old_gid and old_gid not in new_set:
                try:
                    await delete_photo_from_gridfs(old_gid)
                except Exception:
                    pass

    logger.info(f"Asset updated: {asset.asset_code}")
    # Riwayat penempatan otomatis SETELAH CAS sukses (pola set_lokasi_aset),
    # lewat helper best-effort yang sama dengan PATCH/POST.
    if lokasi_otomatis:
        await sp.catat_penempatan(
            {"id": asset_id, "activity_id": asset.activity_id,
             "asset_code": asset.asset_code, "asset_name": asset.asset_name},
            lokasi_otomatis, _user.get("username", ""),
            update_data["updated_at"])
    invalidate_asset_cache()
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    changes = compute_changes(existing, asset.model_dump())
    if changes:
        await log_audit("update", asset.activity_id, asset_id, asset.asset_code, asset.asset_name, audit_user, changes=changes, nup=asset.NUP or "")
    # Prinsip 1 Bab 5: identitas terbaca yang berubah lewat form ikut
    # disegarkan di register siklus — kalau tidak, Nota Dinas/BA/surat usulan
    # yang lahir dari register itu memuat kode/NUP/nama usang.
    _berubah = {c.get("field") for c in (changes or [])}
    _identitas_baru = {k: v for k, v in (
        ("asset_code", asset.asset_code), ("NUP", asset.NUP),
        ("asset_name", asset.asset_name)) if k in _berubah}
    if _identitas_baru:
        from snapshot_aset import segarkan_snapshot_aset
        await segarkan_snapshot_aset(db, asset_id, **_identitas_baru)
    # Jurnal Buku Barang 204/205 bila nilai perolehan berubah lewat edit —
    # jalur SIMAN/pemeliharaan/penilaian sudah berjurnal, edit manual dulu
    # SENYAP (temuan audit rantai nilai). Best-effort, tak menahan respons.
    from shared_utils import catat_jurnal_edit_harga
    await catat_jurnal_edit_harga(existing, asset.purchase_price, audit_user)
    # Respons TANPA media: klien sudah memegang foto/dokumennya sendiri —
    # mengirim balik base64 (bisa >1MB) di tiap simpan memboroskan kuota HP.
    updated_asset = _strip_media(await db.assets.find_one({"id": asset_id}, {"_id": 0}))
    # Sinkron indeks Meilisearch (best-effort; field skalar pencarian utuh di sini).
    jadwalkan_sync("assets", updated_asset)
    # Real-time notification
    await notify_asset_change(asset.activity_id, "asset_updated", {"id": asset_id, "asset_code": asset.asset_code, "asset_name": asset.asset_name}, audit_user, user_id=audit_user_id)
    return AssetResponse(**updated_asset)


# Fields that can be patched individually
# Semua field skalar registry + field media/posisi yang penanganannya khusus.
PATCHABLE_FIELDS = frozenset(SCALAR_FIELD_NAMES) | {
    "photos", "photo", "thumbnail_index", "document_checklist",
    "stiker_photo_index", "activity_id",
}

@assets_router.patch("/assets/{asset_id}")
async def patch_asset(asset_id: str, request: Request, _user: dict = Depends(require_writer)):
    """Partial update — only update the fields provided in the body.
    Supports OCC via If-Match header (expected version) and Idempotency-Key header."""
    # --- Idempotency: replay cached response if same key seen recently ---
    idem_key = kunci_idem(request.headers.get("Idempotency-Key", ""), _user)
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            logger.info(f"Idempotent PATCH replay for key {idem_key[:8]}...")
            return AssetResponse(**cached["response"])
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return AssetResponse(**cached["response"])
        elif _idem == "pending":
            raise HTTPException(status_code=409, detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    body = await request.json()
    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    await pastikan_akses_aset(_user, existing)
    # Kegiatan yang sudah disahkan terkunci — cek activity asal DAN tujuan
    await ensure_activity_not_sealed(existing.get("activity_id"))
    body_activity_id = body.get("activity_id")
    if body_activity_id and body_activity_id != existing.get("activity_id"):
        await pastikan_akses_kegiatan_id(_user, body_activity_id)
        await ensure_activity_not_sealed(body_activity_id)
    if "pengguna_nip" in body:
        await _enforce_pegawai_terdaftar(body.get("pengguna_nip"),
                                         existing.get("pengguna_nip"))

    # --- Optimistic Concurrency Control ---
    if_match = request.headers.get("If-Match", "").strip().strip('"')
    current_version = int(existing.get("version", 1))
    if if_match:
        try:
            expected = int(if_match)
        except ValueError:
            expected = current_version
        if expected != current_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": current_version,
                    "your_version": expected,
                    "current": {
                        "id": existing.get("id"),
                        "version": current_version,
                        "asset_code": existing.get("asset_code"),
                        "asset_name": existing.get("asset_name"),
                    },
                },
            )

    # Filter to patchable fields only
    update_data = {k: v for k, v in body.items() if k in PATCHABLE_FIELDS}
    has_photo_ops = "photo_ops" in body

    # Tolak operator NoSQL (mis. {"$ne": null}) agar tak menyusup ke query
    # cek-duplikat & $set.
    #
    # PERBAIKAN (REVIEW-9 R15): dulu SEMUA nilai list/dict ditolak, padahal
    # PATCHABLE_FIELDS memuat `photos` dan `document_checklist` yang memang
    # BERBENTUK LIST — akibatnya kedua field itu dinyatakan patchable tetapi
    # SELALU gagal 400, jadi edit kelengkapan dokumen lewat PATCH mustahil.
    # Kini list diizinkan HANYA untuk field yang memang berbentuk list, dengan
    # validasi isi; field skalar tetap menolak list/dict seperti semula.
    _FIELD_LIST = {"photos", "document_checklist"}

    def _bebas_operator(nilai, jalur: str):
        """Tolak kunci ber-awalan '$' atau bertitik di kedalaman berapa pun."""
        if isinstance(nilai, dict):
            for kk, vv in nilai.items():
                if not isinstance(kk, str) or kk.startswith("$") or "." in kk:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Nilai field '{jalur}' tidak valid")
                _bebas_operator(vv, jalur)
        elif isinstance(nilai, list):
            for vv in nilai:
                _bebas_operator(vv, jalur)

    for k, v in update_data.items():
        if k in _FIELD_LIST:
            if not isinstance(v, list):
                raise HTTPException(status_code=400,
                                    detail=f"Field '{k}' harus berupa daftar")
            _bebas_operator(v, k)
        elif isinstance(v, (dict, list)):
            raise HTTPException(status_code=400, detail=f"Nilai field '{k}' tidak valid")

    if not update_data and not has_photo_ops:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah")

    # Validate uniqueness: asset_code + NUP (only if either changed)
    new_code = update_data.get("asset_code", existing["asset_code"])
    new_nup = update_data.get("NUP", existing.get("NUP", ""))
    if new_code != existing.get("asset_code") or new_nup != existing.get("NUP", ""):
        activity_id = update_data.get("activity_id", existing.get("activity_id"))
        dup = await db.assets.find_one({
            "asset_code": new_code, "NUP": new_nup,
            "activity_id": activity_id, "id": {"$ne": asset_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{new_code}' dan NUP '{new_nup}' sudah digunakan dalam kegiatan ini")

    # Validate kode_register uniqueness (only if changed)
    if "kode_register" in update_data and update_data["kode_register"]:
        activity_id = update_data.get("activity_id", existing.get("activity_id"))
        kr_dup = await db.assets.find_one({
            "kode_register": update_data["kode_register"],
            "activity_id": activity_id, "id": {"$ne": asset_id}
        })
        if kr_dup:
            raise HTTPException(status_code=400, detail=f"Kode Register '{update_data['kode_register']}' sudah digunakan dalam kegiatan ini")

    # Track GridFS IDs that we create in this request for rollback on failure
    newly_uploaded_gridfs = []

    # Handle photo_ops: server-side photo manipulation without frontend needing full photos
    if has_photo_ops:
        ops = body["photo_ops"]
        # IKAT KEEP PADA VERSINYA (temuan audit G3). `keep` adalah indeks
        # POSISIONAL pada array foto TERKINI, padahal ia dihitung klien dari
        # array pada versi tertentu. Bila array sudah bergeser, keep yang sama
        # menunjuk foto yang BERBEDA — foto terhapus hidup lagi atau foto lain
        # terbuang, tanpa satu galat pun. If-Match header sudah menjaga bila
        # dikirim; `base_version` di badan photo_ops adalah jaring untuk jalur
        # tanpa header (antrean luring lama). Versi beda → 409.
        _po_base = ops.get("base_version")
        if not if_match and _po_base is not None:
            try:
                if int(_po_base) != current_version:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": ("Susunan foto aset telah berubah sejak "
                                        "perangkat Anda membacanya. Muat ulang "
                                        "lalu ulangi perubahan foto."),
                            "current_version": current_version,
                            "your_version": int(_po_base),
                        },
                    )
            except (TypeError, ValueError):
                pass  # base_version bukan angka → abaikan (kompat payload lama)
        # Dedup indeks keep (duplikat = satu blob dirujuk dua entri → penghapusan
        # salah satu ikut membunuh rujukan lainnya); None-guard thumbnail_index.
        keep_indices = list(dict.fromkeys(ops.get("keep", []) or []))
        new_photos_b64 = ops.get("add", []) or []
        new_thumb_idx = int(ops.get("thumbnail_index") or 0)

        old_photos = existing.get("photos", []) or []
        old_gridfs_ids = existing.get("photo_gridfs_ids", []) or []
        old_thumbnails = existing.get("photo_thumbnails", []) or []
        old_n = max(len(old_photos), len(old_gridfs_ids))

        # Susun array baru dari foto yang DIPERTAHANKAN + foto BARU.
        # Kanonis = GridFS: final_srcs hanya menyimpan b64 bila tersedia murah
        # (foto baru / inline legacy) untuk regenerasi cover tanpa fetch.
        final_srcs = []
        final_gridfs_ids = []
        final_thumbnails = []

        for idx in keep_indices:
            if not (0 <= idx < old_n):
                continue
            final_srcs.append(old_photos[idx] if idx < len(old_photos) else None)
            final_gridfs_ids.append(old_gridfs_ids[idx] if idx < len(old_gridfs_ids) else "")
            if idx < len(old_thumbnails) and old_thumbnails[idx]:
                final_thumbnails.append(old_thumbnails[idx])
            elif idx < len(old_photos) and old_photos[idx]:
                final_thumbnails.append(await asyncio.to_thread(generate_photo_thumbnail, old_photos[idx]) or "")
            else:
                final_thumbnails.append("")

        # Process new photos: store in GridFS + generate thumbnails (atomic rollback if one fails)
        try:
            # KRITIS (anti-kehilangan): foto KEPT dari dokumen legacy yang belum
            # punya blob (gid "") harus DIUNGGAH sekarang — karena photos inline
            # tidak dipersist lagi, tanpa unggahan ini byte foto lama lenyap
            # begitu pengguna mengedit aset legacy.
            for i, gid in enumerate(final_gridfs_ids):
                if not gid and final_srcs[i]:
                    new_gid = await store_photo_to_gridfs(final_srcs[i])
                    newly_uploaded_gridfs.append(new_gid)
                    final_gridfs_ids[i] = new_gid
            for photo_b64 in new_photos_b64:
                final_srcs.append(photo_b64)
                gid = await store_photo_to_gridfs(photo_b64)
                newly_uploaded_gridfs.append(gid)
                final_gridfs_ids.append(gid)
                thumb = await asyncio.to_thread(generate_photo_thumbnail, photo_b64)
                final_thumbnails.append(thumb or "")
        except Exception as e:
            # Rollback newly uploaded blobs
            for gid in newly_uploaded_gridfs:
                try:
                    await delete_photo_from_gridfs(gid)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan foto: {e}")

        # Delete removed photos from GridFS (only AFTER successful uploads, to allow rollback)
        removed_indices = set(range(len(old_gridfs_ids))) - set(keep_indices)

        n_final = len(final_gridfs_ids)
        cover_idx = min(new_thumb_idx, n_final - 1) if n_final else 0
        # Inline base64 tidak dipersist lagi — GridFS sumber tunggal.
        update_data["photos"] = []
        update_data["photo_gridfs_ids"] = final_gridfs_ids
        update_data["photo_thumbnails"] = final_thumbnails
        update_data["photo"] = None
        update_data["thumbnail_index"] = cover_idx
        if n_final:
            # Sumber bytes cover: b64 yang sudah di tangan (foto baru / inline
            # legacy); bila kept dari dokumen ter-migrasi, ambil dari GridFS.
            cover_b64 = final_srcs[cover_idx] if cover_idx < len(final_srcs) else None
            if not cover_b64 and cover_idx < len(final_gridfs_ids) and final_gridfs_ids[cover_idx]:
                try:
                    raw = await get_photo_from_gridfs(final_gridfs_ids[cover_idx])
                    if raw:
                        cover_b64 = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
                except Exception as e:
                    logger.warning(f"photo_ops cover regen: GridFS read failed for asset {asset_id}: {e}")
            if cover_b64:
                update_data["thumbnail"] = await asyncio.to_thread(create_thumbnail, cover_b64)
                update_data["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, cover_b64)
            elif cover_idx < len(final_thumbnails) and final_thumbnails[cover_idx]:
                # Fallback: full-res cover gagal diambil (mis. blob korup) tetapi
                # thumbnail per-foto cover TERSEDIA → regen composite dari situ
                # agar cover di mode DAFTAR (asset.thumbnail) tak pernah basi saat
                # cover diganti sambil menghapus foto. thumbnail_index +
                # photo_thumbnails sudah diperbarui; tanpa ini daftar tetap
                # menampilkan cover lama sampai cover diubah lagi (bug dilaporkan).
                update_data["thumbnail"] = await asyncio.to_thread(create_thumbnail, final_thumbnails[cover_idx])
                update_data["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, final_thumbnails[cover_idx])
            # keduanya kosong (benar-benar tak ada byte): biarkan thumbnail lama
        else:
            update_data["thumbnail"] = None
            update_data["gallery_thumbnail"] = None
        # Defer deletion of removed indices till after DB update succeeds
        update_data["__rollback_old_removed_gids__"] = [
            old_gridfs_ids[i] for i in removed_indices if 0 <= i < len(old_gridfs_ids) and old_gridfs_ids[i]
        ]

    # Handle legacy photos field (backward compat for full-photo PATCH)
    elif "photos" in update_data:
        photos = update_data["photos"] or []
        cover_idx = min(update_data.get("thumbnail_index", existing.get("thumbnail_index", 0)), len(photos) - 1) if photos else 0
        old_photos = existing.get("photos", [])
        old_gridfs = [g for g in (existing.get("photo_gridfs_ids", []) or []) if g]
        old_count = len(old_gridfs) or len(old_photos)
        if photos and (photos != old_photos or len(photos) != old_count or cover_idx != existing.get("thumbnail_index", 0)):
            update_data["thumbnail"] = await asyncio.to_thread(create_thumbnail, photos[cover_idx])
            update_data["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, photos[cover_idx])
            # Atomic rollback inside process_photos_for_storage
            result = await process_photos_for_storage(photos)
            newly_uploaded_gridfs.extend(result["gridfs_ids"])
            update_data["photo_gridfs_ids"] = result["gridfs_ids"]
            update_data["photo_thumbnails"] = result["thumbnails"]
            # Blob lama yang tergantikan dihapus SETELAH CAS sukses (dulu bocor
            # sebagai orphan di cabang ini).
            update_data["__rollback_old_removed_gids__"] = old_gridfs
        elif not photos and old_count == 0:
            update_data["thumbnail"] = None
            update_data["gallery_thumbnail"] = None
            update_data["photo_gridfs_ids"] = []
            update_data["photo_thumbnails"] = []
        elif not photos:
            # PENJAGA: PATCH photos=[] sementara GridFS masih berisi → JANGAN
            # hapus foto diam-diam; pertahankan (hapus foto = photo_ops keep[]).
            update_data.pop("photos", None)
        if "photos" in update_data:
            update_data["photos"] = []  # inline tidak dipersist lagi
        update_data["photo"] = None
        update_data["thumbnail_index"] = cover_idx

    # Handle cover-only change: user just picked a different thumbnail without
    # adding/removing any photo. Previously the backend stored the new index
    # but never regenerated `thumbnail` / `gallery_thumbnail` / `photo`, so
    # the list/gallery cover never updated — matching the user-reported bug
    # "thumbnails tidak berganti sesuai dengan cover yang dipilih".
    elif "thumbnail_index" in update_data:
        existing_photos = existing.get("photos", []) or []
        existing_gridfs = existing.get("photo_gridfs_ids", []) or []
        n_photos = max(len(existing_photos), len(existing_gridfs))
        if n_photos == 0:
            # No photos → thumbnail_index is meaningless, just clear
            update_data["thumbnail_index"] = 0
        else:
            new_idx = int(update_data.get("thumbnail_index", 0) or 0)
            new_idx = max(0, min(new_idx, n_photos - 1))
            update_data["thumbnail_index"] = new_idx
            # Prefer a full-res photo source if we still have one (legacy docs),
            # otherwise fall back to streaming the chosen GridFS blob and
            # re-rendering the composite thumbnails from its bytes.
            cover_b64 = None
            if new_idx < len(existing_photos) and existing_photos[new_idx]:
                cover_b64 = existing_photos[new_idx]
            elif new_idx < len(existing_gridfs) and existing_gridfs[new_idx]:
                try:
                    # `base64` dari impor tingkat modul — meng-import-nya di
                    # sini membuatnya LOKAL untuk seluruh patch_asset, sehingga
                    # pemakaian lebih awal (regen cover photo_ops di atas)
                    # meledak UnboundLocalError dan diam-diam tertelan except.
                    from bson import ObjectId
                    gid = existing_gridfs[new_idx]
                    stream = await fs_bucket.open_download_stream(ObjectId(gid) if ObjectId.is_valid(str(gid)) else gid)
                    raw = await stream.read()
                    cover_b64 = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
                except Exception as e:
                    logger.warning(f"thumbnail_index cover regen: GridFS read failed for asset {asset_id} idx {new_idx}: {e}")
            if cover_b64:
                update_data["thumbnail"] = await asyncio.to_thread(create_thumbnail, cover_b64)
                update_data["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, cover_b64)
                # JANGAN tulis update_data["photo"]: itu menyuntikkan kembali
                # base64 full-res ke dokumen yang sudah bersih (GridFS-only).

    # Handle document_checklist → normalize dicts. Frontend uses sentinels to
    # signal "preserve existing item at this index" without re-shipping the
    # base64 bytes; we resolve those sentinels against the existing doc here.
    if "document_checklist" in update_data:
        existing_checklist = existing.get("document_checklist", []) or []
        # Consume each existing item at most once, in order, so duplicate or
        # empty checklist-item names can't cross-wire / lose photos on edit.
        existing_by_name = {}
        for _it in existing_checklist:
            existing_by_name.setdefault((_it.get("name") or ""), deque()).append(_it)
        new_checklist = []
        for item in (update_data["document_checklist"] or []):
            name = item.get("name", "") or ""
            _q = existing_by_name.get(name)
            orig_item = _q.popleft() if _q else {}
            orig_photos = orig_item.get("photos", []) or []
            orig_docs = orig_item.get("documents", []) or []
            orig_thumbs = orig_item.get("photo_thumbnails", []) or []

            # Resolve photo sentinels: "__existing__:<idx>" → orig_photos[idx]
            resolved_photos = []
            resolved_thumbs = []
            for p in (item.get("photos", []) or []):
                if isinstance(p, str) and p.startswith("__existing__:"):
                    try:
                        idx = int(p.split(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    if 0 <= idx < len(orig_photos) and orig_photos[idx]:
                        resolved_photos.append(orig_photos[idx])
                        if idx < len(orig_thumbs):
                            resolved_thumbs.append(orig_thumbs[idx])
                else:
                    resolved_photos.append(p)
                    # Thumbnail will be regenerated below for new uploads
                    resolved_thumbs.append("")

            # Resolve doc sentinels: doc with data == "__existing__:<idx>"
            resolved_docs = []
            for d in (item.get("documents", []) or []):
                if not isinstance(d, dict):
                    continue
                data = d.get("data", "") or ""
                if isinstance(data, str) and data.startswith("__existing__:"):
                    try:
                        idx = int(data.split(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    if 0 <= idx < len(orig_docs):
                        resolved_docs.append(orig_docs[idx])
                else:
                    resolved_docs.append({"name": d.get("name", "document.pdf"), "data": data})

            # Regenerate any missing photo thumbnails for newly added photos
            final_thumbs = []
            for i, ph in enumerate(resolved_photos):
                t = resolved_thumbs[i] if i < len(resolved_thumbs) else ""
                if not t and ph:
                    t = await asyncio.to_thread(generate_photo_thumbnail, ph) or ""
                final_thumbs.append(t)

            new_checklist.append({
                "name": name,
                "checked": bool(item.get("checked", False)),
                "notes": item.get("notes", ""),
                "photos": resolved_photos,
                "photo_thumbnails": final_thumbs,
                "documents": resolved_docs,
            })
        update_data["document_checklist"] = new_checklist

    # Extract deferred rollback info before DB write
    deferred_delete_gids = update_data.pop("__rollback_old_removed_gids__", [])

    # Stamped on every write so the offline snapshot delta sync
    # (GET /assets/offline-snapshot?since=...) picks this change up.
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # SPASIAL: bila update menyentuh koordinat, hitung ulang `geo` dari gabungan
    # dokumen lama + perubahan (pengguna lazim memperbaiki SATU sumbu saja).
    # Mengembalikan bagian $unset agar `geo` ikut hilang saat koordinat dikosongkan.
    _geo_unset = sisip_geo_ke_update(existing, update_data)

    # SPASIAL (integrasi inventarisasi → denah): koordinat dari jalur
    # inventarisasi — kamera lapangan, antrean luring, lembar edit cepat,
    # geser marker peta, semuanya bermuara ke PATCH ini — menempatkan aset
    # yang BELUM ber-penempatan ke node denah aktif pemuat titiknya.
    # Digabung SEBELUM CAS agar atomik dengan tulisan utama; riwayat menyusul
    # setelah tulisan sukses. Lihat spasial_penempatan.py.
    lokasi_otomatis = await sp.penempatan_dari_inventarisasi(
        existing, update_data, _user.get("username", ""),
        update_data["updated_at"])
    if lokasi_otomatis:
        update_data["lokasi_spasial"] = lokasi_otomatis

    try:
        # Atomic CAS: only succeeds if version is still what client saw.
        # Support legacy docs without version field.
        cas_filter = _build_cas_filter(asset_id, current_version)
        _ops = {"$set": update_data, "$inc": {"version": 1}}
        if _geo_unset:
            _ops["$unset"] = _geo_unset
        result = await db.assets.update_one(
            cas_filter,
            _ops,
        )
        if result.matched_count == 0:
            # 409 — rollback newly uploaded GridFS blobs
            for gid in newly_uploaded_gridfs:
                try:
                    await delete_photo_from_gridfs(gid)
                except Exception:
                    pass
            fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0, "version": 1, "asset_code": 1, "asset_name": 1})
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": (fresh or {}).get("version", current_version + 1),
                    "your_version": current_version,
                    "current": fresh or {},
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        # Rollback newly uploaded blobs on DB error
        for gid in newly_uploaded_gridfs:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(status_code=413, detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto.")
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")

    # DB write succeeded — now safe to delete orphaned old GridFS blobs
    for gid in deferred_delete_gids:
        try:
            await delete_photo_from_gridfs(gid)
        except Exception:
            pass

    # Riwayat penempatan otomatis SETELAH CAS sukses — riwayat tak boleh
    # mendahului kenyataan (pola set_lokasi_aset). CAS yang kalah sudah
    # raise 409 di atas, jadi riwayat tak pernah menetes dari tulisan gagal.
    # Helper-nya best-effort: aset sudah tersimpan, jadi galat jejak tak
    # boleh membalas 500 atas tulisan yang berhasil.
    if lokasi_otomatis:
        await sp.catat_penempatan({**existing, "id": asset_id},
                                  lokasi_otomatis, _user.get("username", ""),
                                  update_data["updated_at"])

    logger.info(f"Asset patched: {asset_id} — fields: {list(update_data.keys())}")
    invalidate_asset_cache()
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    merged = {**existing, **update_data}
    changes = compute_changes(existing, merged)
    if changes:
        await log_audit(
            "update", merged.get("activity_id", ""), asset_id,
            merged.get("asset_code", ""), merged.get("asset_name", ""),
            audit_user, changes=changes, nup=merged.get("NUP", "")
        )
    # Jurnal 204/205 bila PATCH mengubah nilai perolehan (lihat PUT di atas).
    if "purchase_price" in update_data:
        from shared_utils import catat_jurnal_edit_harga
        await catat_jurnal_edit_harga(existing, update_data["purchase_price"],
                                      audit_user)
    # Respons TANPA media (lihat _strip_media) — juga memperkecil dokumen
    # idempotency yang disimpan di bawah.
    updated_asset = _strip_media(await db.assets.find_one({"id": asset_id}, {"_id": 0}))
    # Sinkron indeks Meilisearch (best-effort; no-op bila nonaktif).
    jadwalkan_sync("assets", updated_asset)
    await notify_asset_change(
        merged.get("activity_id", ""), "asset_updated",
        {"id": asset_id, "asset_code": merged.get("asset_code", ""), "asset_name": merged.get("asset_name", "")},
        audit_user, user_id=audit_user_id
    )
    response = AssetResponse(**updated_asset)
    if idem_key:
        await store_idempotent_response(idem_key, response.model_dump(mode="json"), 200)
    return response

@assets_router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, request: Request, _admin: dict = Depends(require_admin)):
    """Delete an asset (admin only)"""
    asset_doc = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset_doc:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_admin, asset_doc)

    # Kegiatan yang sudah disahkan terkunci — tolak penghapusan aset (423)
    await ensure_activity_not_sealed(asset_doc.get("activity_id"))

    result = await db.assets.delete_one({"id": asset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Clean up GridFS blobs the doc referenced so they don't leak as orphans.
    # Best-effort: a blob-delete failure must NOT block the (already-done) doc
    # delete — just log it.
    blob_ids = await _collect_asset_blob_ids(asset_doc)
    for gid in blob_ids["photos"]:
        try:
            await delete_photo_from_gridfs(gid)
        except Exception as e:
            logger.warning(f"delete_asset: gagal hapus foto GridFS {gid}: {e}")
    for gid in blob_ids["documents"]:
        try:
            await delete_document_from_gridfs(gid)
        except Exception as e:
            logger.warning(f"delete_asset: gagal hapus dokumen GridFS {gid}: {e}")

    # Lepas back-link register Pengadaan (best-effort): baris barang yang
    # menaut aset ini kini menunjuk aset yang sudah tak ada — register akan
    # mengklaim aset hantu dan tombol "tautkan" bertingkah aneh. Kosongkan
    # tautan + snapshotnya di SEMUA baris yang menyebut asset_id ini. Gagal di
    # sini tak boleh menahan penghapusan aset yang sudah terjadi.
    try:
        await db.pengadaan.update_many(
            {"barang.asset_id": asset_id},
            {"$set": {"barang.$[el].asset_id": "", "barang.$[el].asset_code": "",
                      "barang.$[el].NUP": "", "barang.$[el].asset_name": ""}},
            array_filters=[{"el.asset_id": asset_id}])
    except Exception as e:
        logger.warning(f"delete_asset: gagal lepas back-link pengadaan {asset_id}: {e}")

    logger.info(f"Asset deleted: {asset_id}")
    invalidate_asset_cache()
    # Cabut dari indeks Meilisearch (best-effort; no-op bila nonaktif).
    jadwalkan_hapus("assets", asset_id)
    audit_user = _admin.get("name") or _admin.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _admin.get("id") or request.headers.get("X-Audit-User-Id", "")
    # Nilai perolehan direkam di changes agar LBKP mutasi-kurang mendatang
    # bisa menghitung NILAI barang yang dihapus, bukan hanya jumlahnya.
    await log_audit(
        "delete", asset_doc.get("activity_id", ""), asset_id,
        asset_doc.get("asset_code", ""), asset_doc.get("asset_name", ""),
        audit_user, detail="Aset dihapus", nup=asset_doc.get("NUP", ""),
        changes=[{"field": "purchase_price",
                  "from": str(asset_doc.get("purchase_price", "") or ""),
                  "to": ""}],
    )
    # Real-time notification
    await notify_asset_change(asset_doc.get("activity_id", ""), "asset_deleted", {"id": asset_id, "asset_code": asset_doc.get("asset_code", "")}, audit_user, user_id=audit_user_id)
    
    return {"message": "Aset berhasil dihapus"}


@assets_router.post("/assets/migrate-gridfs")
async def migrate_photos_to_gridfs(_admin: dict = Depends(require_super_admin)):
    """Migrate existing inline base64 photos to GridFS + generate per-photo thumbnails.
    Safe to run multiple times — skips assets that already have gridfs_ids.

    KHUSUS SUPER-ADMIN (REVIEW-9 R15): operasi ini menyapu SELURUH koleksi
    assets tanpa filter satker dan MENULIS ULANG dokumen aset (foto → GridFS,
    thumbnail baru). Dengan `require_admin`, admin satker mana pun dapat
    memicu penulisan massal atas aset satker lain — migrasi seluruh-DB adalah
    wewenang pusat, sekelas backup/restore/reset.
    """
    cursor = db.assets.find(
        {"photos": {"$exists": True, "$ne": []}, "$or": [{"photo_gridfs_ids": {"$exists": False}}, {"photo_gridfs_ids": []}]},
        {"_id": 0, "id": 1, "photos": 1, "document_checklist": 1}
    )
    migrated = 0
    async for asset in cursor:
        try:
            photos = asset.get("photos", []) or []
            if not photos:
                continue
            result = await process_photos_for_storage(photos)
            update = {
                "photo_gridfs_ids": result["gridfs_ids"],
                "photo_thumbnails": result["thumbnails"],
            }
            # Also migrate document_checklist photos
            checklist = asset.get("document_checklist", []) or []
            updated_cl = []
            for item in checklist:
                item_photos = item.get("photos", []) or []
                if item_photos:
                    item_thumbs = await asyncio.to_thread(
                        lambda pics: [generate_photo_thumbnail(p) or "" for p in pics], item_photos)
                    updated_cl.append({**item, "photo_thumbnails": item_thumbs})
                else:
                    updated_cl.append(item)
            if any(it.get("photo_thumbnails") for it in updated_cl):
                update["document_checklist"] = updated_cl
            await db.assets.update_one({"id": asset["id"]}, {"$set": update})
            migrated += 1
        except Exception as e:
            logger.error(f"Migration error for asset {asset.get('id')}: {e}")

    # FASE 2 — pembersihan duplikasi: dokumen yang SUDAH punya blob GridFS
    # lengkap tak perlu lagi menyimpan base64 inline (photos/photo). Sebelum
    # $unset, setiap blob diverifikasi ADA & tidak kosong lewat metadata
    # fs.files (tanpa membaca seluruh byte) — jangan pernah membuang salinan
    # terakhir foto aset negara.
    cleaned = 0
    cursor2 = db.assets.find(
        {"photos": {"$exists": True, "$ne": []}, "photo_gridfs_ids": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "photos": 1, "photo_gridfs_ids": 1, "photo_thumbnails": 1},
    )
    async for asset in cursor2:
        try:
            gids = [g for g in (asset.get("photo_gridfs_ids") or []) if g]
            photos = asset.get("photos") or []
            thumbs = asset.get("photo_thumbnails") or []
            # Jumlah blob & thumbnail harus selaras dengan foto inline
            if len(gids) != len(photos) or len(thumbs) < len(gids):
                continue
            ok = True
            for gid in gids:
                try:
                    from bson import ObjectId
                    fdoc = await db.fs.files.find_one(
                        {"_id": ObjectId(gid) if ObjectId.is_valid(str(gid)) else gid},
                        {"length": 1},
                    )
                    if not fdoc or not fdoc.get("length"):
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
            if not ok:
                continue
            await db.assets.update_one({"id": asset["id"]}, {"$set": {"photos": []}, "$unset": {"photo": ""}})
            cleaned += 1
        except Exception as e:
            logger.error(f"Cleanup error for asset {asset.get('id')}: {e}")

    return {
        "migrated": migrated, "cleaned": cleaned,
        "message": f"Berhasil migrasi {migrated} aset ke GridFS; {cleaned} aset dibersihkan dari duplikasi inline",
    }

