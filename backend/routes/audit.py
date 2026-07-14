"""
Audit log routes.
Extracted from assets.py for clean separation of concerns.
Provides: GET /audit-logs
"""
import logging
from fastapi import APIRouter, Depends
from db import db
from auth_utils import require_user
from penghapusan_utils import normalisasi_jejak_terhapus, rekap_jejak_terhapus
from integritas_utils import FIELD_IDENTITAS, identitas_drift
from kodefikasi_utils import (
    derive_level, level_terdaftar_terdalam, normalize_kode,
)
from report_filters import active_asset_filter

logger = logging.getLogger(__name__)
audit_router = APIRouter()


@audit_router.get("/audit-logs")
async def get_audit_logs(activity_id: str = "", asset_id: str = "", page: int = 1, page_size: int = 50,
                         _user: dict = Depends(require_user)):
    """Get audit logs with optional filtering"""
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if asset_id:
        query["asset_id"] = asset_id

    # Clamp pagination so a caller can't request an unbounded page and dump the
    # entire audit trail (or drive huge memory use) in one request.
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(page_size).to_list(page_size)

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }


@audit_router.get("/audit-logs/aset-terhapus")
async def get_jejak_aset_terhapus(activity_id: str = "", page: int = 1,
                                  page_size: int = 50,
                                  _user: dict = Depends(require_user)):
    """Jejak Aset Terhapus — arsip read-only dari audit log.

    Aset yang dihapus permanen tetap tertelusur (kode/NUP/nama/nilai/oleh/
    waktu) tanpa mengubah mekanisme penghapusan. Nilai perolehan diambil
    dari perubahan yang direkam saat penghapusan.
    """
    query = {"action": {"$in": ["delete", "bulk_delete"]}}
    if activity_id:
        query["activity_id"] = activity_id
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort(
        "timestamp", -1).skip(skip).limit(page_size).to_list(page_size)
    rows = normalisasi_jejak_terhapus(logs)
    return {
        "items": rows,
        "ringkasan": rekap_jejak_terhapus(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "catatan": (
            "Arsip jejak penghapusan aset (read-only) dari log audit. "
            "Penghapusan permanen tetap tercatat di sini untuk penelusuran; "
            "nilai perolehan direkam saat aset dihapus."),
    }


@audit_router.get("/integritas/identitas-penghapusan")
async def integritas_identitas_penghapusan(_user: dict = Depends(require_user)):
    """§5A Prinsip 1 (READ-ONLY): deteksi snapshot identitas aset yang BASI pada
    register `usulan_penghapusan`.

    Register hilir membekukan `asset_code`/`NUP`/`asset_name` saat usulan dibuat;
    bila master aset kelak diedit, snapshot itu jadi usang. Endpoint ini
    membandingkan tiap snapshot dengan master aset TERKINI (via `asset_id`) dan
    melaporkan yang **basi** (`snapshot_basi`) atau yang master-nya sudah
    **hilang** (`aset_master_hilang`). Tidak mengubah data apa pun — langkah awal
    penyegaran snapshot (penulisan menyusul sebagai langkah terpisah).
    """
    proj_snap = {"_id": 0, "id": 1, "asset_id": 1, "status": 1,
                 "asset_code": 1, "NUP": 1, "asset_name": 1}
    proj_master = {"_id": 0, "asset_code": 1, "NUP": 1, "asset_name": 1}
    items = []
    n_basi = n_hilang = 0
    async for u in db.usulan_penghapusan.find({}, proj_snap):
        aid = u.get("asset_id")
        master = await db.assets.find_one({"id": aid}, proj_master) if aid else None
        snap = {f: u.get(f) for f in FIELD_IDENTITAS}
        if not master:
            n_hilang += 1
            items.append({"usulan_id": u.get("id"), "asset_id": aid,
                          "status": u.get("status"),
                          "masalah": "aset_master_hilang", "snapshot": snap})
            continue
        drift = identitas_drift(u, master)
        if drift:
            n_basi += 1
            items.append({"usulan_id": u.get("id"), "asset_id": aid,
                          "status": u.get("status"),
                          "masalah": "snapshot_basi", "drift": drift})
    return {
        "jumlah": len(items),
        "snapshot_basi": n_basi,
        "aset_master_hilang": n_hilang,
        "items": items,
        "catatan": (
            "Deteksi read-only snapshot identitas aset basi di register usulan "
            "penghapusan (§5A Prinsip 1). Belum menyegarkan otomatis — hanya "
            "melaporkan agar bisa ditindaklanjuti."),
    }


@audit_router.get("/integritas/kodefikasi-aset")
async def integritas_kodefikasi_aset(_user: dict = Depends(require_user)):
    """§5A Prinsip 2 (READ-ONLY): kodefikasi sebagai FK tervalidasi.

    Kode barang aset diturunkan dari prefix, tetapi TAK divalidasi sebagai FK ke
    referensi `kodefikasi`. Endpoint ini mengagregasi `asset_code` DISTINCT (aset
    aktif) dan melaporkan yang prefix golongan/level-nya **tak terdaftar** di
    `db.kodefikasi` — sebagai **peringatan** (non-blocking), tanpa menolak/ubah
    data lama. Ambang: `kode_spesifik_tak_terdaftar` (hanya induk terdaftar),
    `golongan_tak_terdaftar` (level 1 pun tak ada), `panjang_kode_tak_valid`.
    """
    terdaftar = set()
    async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if k.get("kode"):
            terdaftar.add(str(k["kode"]))

    items = []
    n_golongan = n_spesifik = n_invalid = 0
    async for grp in db.assets.aggregate([
        {"$match": active_asset_filter()},
        {"$group": {"_id": "$asset_code", "jumlah_aset": {"$sum": 1}}},
    ]):
        kode = normalize_kode(grp.get("_id"))
        jml = grp.get("jumlah_aset", 0)
        level_kode = derive_level(kode)
        if not level_kode:
            n_invalid += 1
            items.append({"asset_code": grp.get("_id"), "jumlah_aset": jml,
                          "masalah": "panjang_kode_tak_valid"})
            continue
        dalam = level_terdaftar_terdalam(kode, terdaftar)
        if dalam >= level_kode:
            continue  # kode terdaftar sampai level-nya → konsisten
        masalah = "golongan_tak_terdaftar" if dalam == 0 else "kode_spesifik_tak_terdaftar"
        if dalam == 0:
            n_golongan += 1
        else:
            n_spesifik += 1
        items.append({"asset_code": grp.get("_id"), "jumlah_aset": jml,
                      "level_kode": level_kode, "level_terdaftar": dalam,
                      "masalah": masalah})

    items.sort(key=lambda x: (-x.get("jumlah_aset", 0), str(x.get("asset_code") or "")))
    return {
        "jumlah_kode": len(items),
        "golongan_tak_terdaftar": n_golongan,
        "kode_spesifik_tak_terdaftar": n_spesifik,
        "panjang_kode_tak_valid": n_invalid,
        "items": items,
        "catatan": (
            "Peringatan read-only (§5A Prinsip 2): kode aset yang prefix "
            "kodefikasi-nya belum terdaftar di referensi. Non-blocking — tak "
            "menolak data lama; lengkapi referensi kodefikasi untuk menutup."),
    }
