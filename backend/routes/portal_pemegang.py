"""Portal pemegang tahap pertama: penugasan akses dan laporan observasi.

Tidak ada handler yang menulis master aset, BAST, jurnal, TGR, atau SK.
Idempotensi disimpan bersama perubahan dokumen sehingga kegagalan respons
tidak dapat menggandakan aksi. Bukti asli berada pada laporan yang sama.
"""
import asyncio
import base64
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymongo.errors import DuplicateKeyError, PyMongoError

from auth_utils import require_admin, require_user, require_writer
from db import db
from portal_auth import (pegawai_layak_portal, require_portal_session,
                         require_portal_write)
from portal_pemegang_utils import (
    STATUS_LAPORAN, alias_identitas_aset, bukti_metadata, ikatan_sumber,
    sidik_data, teks, tindak_lanjut_laporan, validasi_bukti, waktu_pengambilan,
)
from shared_utils import kode_satker_user, log_audit

portal_pemegang_router = APIRouter(prefix="/portal-pemegang")
_PROJ_ASSET = {"_id": 0, **{k: 1 for k in (
    "id", "activity_id", "asset_name", "asset_code", "NUP", "kode_register",
    "user", "pengguna_nip", "bast_terakhir", "location", "condition",
    "inventory_status", "dihapus", "category", "amanah_bast")}}
_PROJ_LAPORAN = {"_id": 0, "bukti.data_base64": 0,
                 "_idem_buat": 0, "_operasi": 0, "_identitas_pelapor": 0}
_ASET_RINGKAS = ("asset_id", "asset_name", "asset_code", "NUP", "location", "condition")
_LEASE_LAPORAN = timedelta(minutes=2)
_PROJ_LAPORAN_TERAKHIR = {"_id": 0, **{k: 1 for k in (
    "id", "penugasan_id", "pegawai_id", "status", "jenis", "kondisi",
    "status_operasional", "lokasi_laporan", "catatan", "created_at",
    "diambil_pada", "tinjauan", "perlu_tindak_lanjut", "laporan_sebelumnya_id")}}


class _Masukan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PenugasanIn(_Masukan):
    pegawai_id: str = Field(min_length=1, max_length=100)
    asset_id: str = Field(min_length=1, max_length=100)
    dasar_penugasan: str = Field(min_length=10, max_length=1500)
    catatan: str = Field(default="", max_length=3000)


class CabutIn(_Masukan):
    version: int = Field(ge=1)
    catatan: str = Field(min_length=5, max_length=3000)


class KonfirmasiIn(_Masukan):
    version: int = Field(ge=1)
    keputusan: Literal["terima", "sanggah"]
    catatan: str = Field(default="", max_length=3000)


class GpsBuktiIn(_Masukan):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)


class PengambilanBuktiIn(_Masukan):
    waktu: str = Field(min_length=1, max_length=50)
    gps: GpsBuktiIn | None = None


class BuktiIn(_Masukan):
    nama: str = Field(min_length=1, max_length=160)
    mime: Literal["image/jpeg", "image/png", "image/webp"]
    data_base64: str = Field(min_length=1, max_length=4 * 1024 * 1024)
    pengambilan: PengambilanBuktiIn | None = None


class LaporanIn(_Masukan):
    penugasan_id: str = Field(min_length=1, max_length=100)
    penugasan_version: int = Field(ge=1)
    jenis: Literal["berkala", "kerusakan", "kehilangan", "perbaikan", "pengembalian"]
    kondisi: Literal["Baik", "Rusak Ringan", "Rusak Berat", "Tidak diketahui"]
    status_operasional: Literal["digunakan", "tidak_digunakan", "diperbaiki", "tidak_diketahui"]
    lokasi_laporan: str = Field(default="", max_length=1000)
    catatan: str = Field(default="", max_length=5000)
    diambil_pada: str | None = Field(default=None, max_length=50)
    bukti: list[BuktiIn] = Field(default_factory=list, max_length=3)
    laporan_sebelumnya_id: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def validasi_catatan(self):
        # Hanya pemeriksaan berkala normal yang tidak memerlukan uraian.
        # Tidak mengisi narasi otomatis atau menambah field payload: sidik
        # retry laporan lama harus tetap sama, termasuk antrean luring.
        normal = (self.jenis == "berkala" and self.kondisi == "Baik"
                  and self.status_operasional in ("digunakan", "tidak_digunakan")
                  and not self.laporan_sebelumnya_id)
        if not normal and len(self.catatan) < 5:
            raise ValueError("Tuliskan hasil pemeriksaan, kronologi, atau alasan minimal 5 karakter untuk laporan ini")
        return self


class TinjauIn(_Masukan):
    version: int = Field(ge=1)
    keputusan: Literal["terverifikasi", "perlu_perbaikan", "ditolak"]
    catatan: str = Field(min_length=5, max_length=5000)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _satker_staff(user):
    kode = kode_satker_user(user)
    if not kode:
        raise HTTPException(409, "Pilih satu Satker Aktif untuk mengelola portal pemegang")
    return kode


def _aktor(user, portal=False):
    if portal:
        return f"pegawai:{user['kode_satker']}:{user['pegawai_id']}"
    return f"staff:{_satker_staff(user)}:{user.get('id') or user.get('username')}"


def _operasi(request, user, route, payload, portal=False):
    key = teks(request.headers.get("Idempotency-Key"))
    if not key or len(key) > 200:
        raise HTTPException(428, "Idempotency-Key wajib diisi (maksimal 200 karakter)")
    match = teks(request.headers.get("If-Match")).strip('"')
    if not match.isdigit():
        raise HTTPException(428, "If-Match wajib memuat versi yang dibaca")
    expected = int(match)
    operation = sidik_data([_aktor(user, portal), route, key])
    body = payload.model_dump()
    # Metadata baru opsional tidak mengubah sidik retry laporan/antrean lama.
    for b in body.get("bukti", []):
        if b.get("pengambilan") is None:
            b.pop("pengambilan", None)
    digest = sidik_data({"payload": body, "version": expected})
    return operation, digest, expected


def _cek_version(expected, version):
    if expected != version:
        raise HTTPException(409, "Versi berubah — muat ulang sebelum melanjutkan")


def _replay(doc, operation, digest, create=False):
    ops = [doc.get("_idem_buat") or {}] if create else doc.get("_operasi") or []
    for op in ops:
        if op.get("id") == operation:
            if op.get("sidik") != digest:
                raise HTTPException(409, "Idempotency-Key sudah dipakai dengan isi berbeda")
            return op["hasil"]
    return None


def _catat_operasi(operation, digest, hasil):
    return {"id": operation, "sidik": digest, "hasil": hasil}


def _ringkas_penugasan(p, asset=None, internal=False):
    keys = ("id", "version", "status", "asset_id", "asset_name", "asset_code",
            "NUP", "location", "condition", "dasar_penugasan", "catatan",
            "created_at", "updated_at", "konfirmasi", "pencabutan", "penerimaan_otomatis")
    out = {k: p[k] for k in keys if k in p}
    if p.get("sumber_bast"):
        out["sumber_bast"] = {k: p["sumber_bast"].get(k, "") for k in
                              ("id", "nomor", "tanggal", "jenis", "jangka_sampai")}
    if asset:
        out.update({k: asset.get(k, "") for k in
                    ("asset_name", "asset_code", "NUP", "location", "condition", "kode_register")})
    if internal:
        out.update({k: p.get(k, "") for k in
                    ("pegawai_id", "pegawai_nama", "kode_satker", "created_by")})
    return out


def _ringkas_laporan(doc):
    out = {k: v for k, v in doc.items() if not k.startswith("_")}
    out["bukti"] = bukti_metadata(doc.get("bukti"))
    return out


async def _audit(action, doc, user, detail):
    await log_audit(action, "", asset_id=doc.get("asset_id", ""),
                    username=user.get("username") or f"pemegang:{user.get('pegawai_id', '')}",
                    detail=detail, kode_satker=doc.get("kode_satker", ""))


async def _aset_dalam_satker(asset_id, kode):
    asset = await db.assets.find_one({"id": asset_id}, _PROJ_ASSET)
    if not asset or asset.get("dihapus") is True or "dummy" in teks(asset.get("category")).lower():
        raise HTTPException(409, "Aset tidak lagi tersedia untuk portal")
    activity = await db.inventory_activities.find_one(
        {"id": asset.get("activity_id")}, {"_id": 0, "kode_satker": 1})
    if not kode or teks((activity or {}).get("kode_satker")) != kode:
        raise HTTPException(409, "Cakupan satker aset berubah atau belum lengkap")
    return asset


async def _validitas_penugasan(p):
    try:
        await periksa_penugasan_aktif(p, harus_diterima=True)
        return True, ""
    except HTTPException as exc:
        return False, str(exc.detail)


async def periksa_penugasan_aktif(penugasan, principal=None, harus_diterima=False, sumber_cache=None):
    """Guard dapat dipakai integrasi lain; tak pernah memperbarui master.

Selalu baca kembali pegawai, record aset pilihan, dan kegiatan induknya.
Riwayat portal tidak dapat menjadi pengganti penugasan yang sudah berubah.
"""
    p = penugasan
    if not p or p.get("status") == "dicabut":
        raise HTTPException(403, "Akses penugasan sudah dicabut atau tidak tersedia")
    if principal and (p.get("pegawai_id") != principal.get("pegawai_id")
                      or p.get("kode_satker") != principal.get("kode_satker")):
        raise HTTPException(404, "Penugasan tidak ditemukan")
    peg = await db.pegawai.find_one({"id": p["pegawai_id"]}, {"_id": 0})
    if (not peg or not pegawai_layak_portal(peg)
            or teks(peg.get("kode_satker")) != p["kode_satker"]):
        raise HTTPException(403, "Pegawai tidak lagi memenuhi syarat akses portal")
    asset = await _aset_dalam_satker(p["asset_id"], p["kode_satker"])
    # Baca status terkini, bukan snapshot sebelum transfer/cabut berjalan.
    current = await db.portal_penugasan.find_one({"id": p["id"]}, {"status": 1})
    if not current or current.get("status") == "dicabut":
        raise HTTPException(403, "Akses penugasan telah dicabut")
    if p.get("sumber_bast"):
        from portal_bast import periksa_sumber_bast
        await periksa_sumber_bast(db, p, asset, cache=sumber_cache)
    elif asset.get("amanah_bast"):
        raise HTTPException(403, "Amanah kini mengikuti BAST; pemetaan akses lama tidak berlaku")
    if ikatan_sumber(asset, p["kode_satker"]) != p.get("ikatan_sumber"):
        raise HTTPException(409, "Data penugasan aset berubah — minta petugas meninjau akses")
    if harus_diterima and p.get("status") != "diterima":
        raise HTTPException(409, "Konfirmasikan penerimaan penugasan sebelum mengirim laporan")
    return asset


async def _penugasan_holder(pid, principal, harus_diterima=False):
    p = await db.portal_penugasan.find_one({
        "id": pid, "pegawai_id": principal["pegawai_id"],
        "kode_satker": principal["kode_satker"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Penugasan tidak ditemukan")
    asset = await periksa_penugasan_aktif(p, principal, harus_diterima)
    return p, asset


async def _laporan_terakhir_penugasan(items, kode):
    """Satu proyeksi metadata per penugasan, bukan laporan pemegang terdahulu.

    Batas batch mencegah kueri $in besar; isi foto/token tidak dibaca untuk
    kartu monitoring. Status laporan tetap observasi, bukan kondisi induk.
    """
    result = {}
    ids = [p["id"] for p in items]
    pemegang = {p["id"]: p.get("pegawai_id") for p in items}
    for start in range(0, len(ids), 200):
        pipeline = [
            {"$match": {"kode_satker": kode, "penugasan_id": {"$in": ids[start:start + 200]},
                        "$or": [{"penugasan_id": pid, "pegawai_id": pemegang[pid]}
                                for pid in ids[start:start + 200]]}},
            {"$project": _PROJ_LAPORAN_TERAKHIR},
            {"$sort": {"created_at": -1, "id": -1}},
            {"$group": {"_id": "$penugasan_id", "laporan": {"$first": "$$ROOT"}}},
        ]
        async for row in db.portal_laporan.aggregate(pipeline, maxTimeMS=10000):
            laporan = row["laporan"]
            # Data arsip tidak boleh melekat ke pemegang lain karena ID salah.
            if laporan.get("pegawai_id") == pemegang.get(row["_id"]):
                result[row["_id"]] = laporan
    return result


@portal_pemegang_router.get("/admin/monitoring")
async def monitoring_admin(pegawai_id: str = "", user: dict = Depends(require_user)):
    """Ringkasan status tercatat, bukan hitungan izin akses/BAST sah saat ini.

    Satker aktif wajib. Hitungan meliputi seluruh halaman dan tidak mengikuti
    pencarian/status daftar laporan; lingkup pegawai tetap mengikuti pilihan.
    Pemeriksaan hak terkini tetap dilakukan di daftar/detail dan setiap tulis.
    """
    q = {"kode_satker": _satker_staff(user)}
    if pegawai_id:
        q["pegawai_id"] = pegawai_id
    pipeline = [{"$match": q}, {"$group": {"_id": "$status", "jumlah": {"$sum": 1}}}]
    assignments, reports, holders = await asyncio.gather(
        db.portal_penugasan.aggregate(pipeline, maxTimeMS=10000).to_list(None),
        db.portal_laporan.aggregate(pipeline, maxTimeMS=10000).to_list(None),
        db.portal_penugasan.aggregate([
            {"$match": {**q, "pegawai_id": {"$nin": [None, ""]},
                        **({"pegawai_id": pegawai_id} if pegawai_id else {})}},
            {"$group": {"_id": "$pegawai_id"}}, {"$count": "jumlah"},
        ], maxTimeMS=10000).to_list(1),
    )
    a = {r["_id"]: r["jumlah"] for r in assignments}
    r = {row["_id"]: row["jumlah"] for row in reports}
    return {
        "penugasan": {"total": sum(a.values()), **{k: a.get(k, 0) for k in
                       ("diterima", "menunggu_konfirmasi", "disanggah", "dicabut")}},
        "laporan": {"total": sum(r.values()),
                    "menunggu_tinjauan": r.get("diajukan", 0) + r.get("menunggu_verifikasi", 0),
                    **{k: r.get(k, 0) for k in ("perlu_perbaikan", "terverifikasi", "ditolak")}},
        "pemegang": holders[0]["jumlah"] if holders else 0,
    }


@portal_pemegang_router.get("/admin/penugasan")
async def daftar_penugasan_admin(pegawai_id: str = "", user: dict = Depends(require_user)):
    q = {"kode_satker": _satker_staff(user)}
    if pegawai_id:
        q["pegawai_id"] = pegawai_id
    items, sumber_cache = [], {}
    async for p in db.portal_penugasan.find(q, {"_id": 0}).sort("created_at", -1):
        try:
            asset = await periksa_penugasan_aktif(p, sumber_cache=sumber_cache)
            valid, alasan = True, ""
        except HTTPException as exc:
            asset, valid, alasan = None, False, exc.detail
        items.append({**_ringkas_penugasan(p, asset, True),
                      "akses_valid": valid, "alasan_akses": alasan})
    latest = await _laporan_terakhir_penugasan(items, q["kode_satker"])
    for item in items:
        item["laporan_terakhir"] = latest.get(item["id"])
    return {"items": items, "total": len(items)}


def _periksa_aset_manual(asset, peg, kode):
    """Aturan yang sama untuk saran pilihan dan penyimpanan pengecualian.

    Pemetaan portal bukan cara memindahkan pemegang resmi. Nama lama hanya
    diperiksa jika nomor identitas belum ada; nomor tetap lebih otoritatif.
    """
    if asset.get("amanah_bast"):
        raise HTTPException(409, "Amanah barang ini mengikuti BAST; gunakan sinkronisasi atau revisi BAST")
    nomor = teks(asset.get("pengguna_nip"))
    nama = " ".join(teks(asset.get("user")).split()).casefold()
    if ((nomor and nomor != teks(peg.get("nip")))
            or (not nomor and nama and nama != " ".join(teks(peg.get("nama")).split()).casefold())):
        raise HTTPException(409, "Pemegang pada master aset berbeda; selesaikan penugasan resmi dahulu")
    try:
        return alias_identitas_aset(asset, kode)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@portal_pemegang_router.get("/admin/kandidat-aset")
async def kandidat_aset_admin(pegawai_id: str = Query(..., min_length=1, max_length=100),
                             search: str = Query("", max_length=120),
                             page: int = Query(1, ge=1),
                             page_size: int = Query(20, ge=1, le=100),
                             semua_satker: bool = False,
                             user: dict = Depends(require_admin)):
    """Saran read-only, bukan pemberian akses; create memeriksa ulang semuanya.

    Default tepat nomor identitas pegawai, bukan substring/nama. Pengecualian
    semua_satker tetap SATU satker aktif. Total mencakup hasil yang ditolak
    agar sebabnya terlihat; pilihan tidak diam-diam melewati halaman.
    """
    kode = _satker_staff(user)
    peg = await db.pegawai.find_one({"id": pegawai_id, "kode_satker": kode}, {"_id": 0})
    if not peg:
        raise HTTPException(404, "Pegawai tidak ditemukan dalam satker aktif")
    if not pegawai_layak_portal(peg):
        raise HTTPException(409, "Pegawai belum memenuhi syarat portal; periksa status dan email di Master Pegawai")
    empty = {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}
    nomor = teks(peg.get("nip"))
    if not semua_satker and not nomor:
        return {**empty, "message": "NIP/NIK pegawai belum diisi. Lengkapi identitas atau periksa pengecualian dalam satker aktif."}
    activities = {a["id"]: a.get("name", "") async for a in db.inventory_activities.find(
        {"kode_satker": kode}, {"_id": 0, "id": 1, "name": 1})}
    if not activities:
        return empty
    q = {"activity_id": {"$in": list(activities)}, "dihapus": {"$ne": True},
         "category": {"$not": re.compile("dummy", re.IGNORECASE)}}
    if not semua_satker:
        q["pengguna_nip"] = {"$regex": r"^\s*" + re.escape(nomor) + r"\s*$"}
    if search.strip():
        q["$or"] = [{k: {"$regex": re.escape(search.strip()), "$options": "i"}}
                    for k in ("asset_name", "asset_code", "NUP", "location", "user")]
    total, rows = await asyncio.gather(
        db.assets.count_documents(q, maxTimeMS=10000),
        db.assets.find(q, _PROJ_ASSET).max_time_ms(10000).sort([("asset_name", 1), ("id", 1)])
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size),
    )
    items, aliases_all = [], set()
    for asset in rows:
        aliases, alasan = [], ""
        try:
            aliases = _periksa_aset_manual(asset, peg, kode)
        except HTTPException as exc:
            alasan = str(exc.detail)
        aliases_all.update(aliases)
        items.append({**{k: asset.get(k, "") for k in (
            "id", "asset_name", "asset_code", "NUP", "activity_id", "location", "user", "condition")},
            "activity_name": activities.get(asset.get("activity_id"), ""),
            "kunci_fisik": aliases, "boleh_dipilih": not alasan, "alasan": alasan})
    occupied = set()
    if aliases_all:
        async for p in db.portal_penugasan.find(
                {"kode_satker": kode, "slot_aktif": {"$in": list(aliases_all)}},
                {"_id": 0, "slot_aktif": 1}):
            occupied.update(p.get("slot_aktif") or [])
    for item in items:
        if item["boleh_dipilih"] and occupied.intersection(item["kunci_fisik"]):
            item.update(boleh_dipilih=False, alasan="Barang fisik ini sudah memiliki penugasan portal; tinjau penugasan yang tercatat dahulu")
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size)}


@portal_pemegang_router.post("/admin/penugasan")
async def buat_penugasan(data: PenugasanIn, request: Request,
                        user: dict = Depends(require_admin)):
    kode = _satker_staff(user)
    op, digest, version = _operasi(request, user, "buat_penugasan", data)
    _cek_version(version, 0)
    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aman:portal:penugasan:{op}"))
    existing = await db.portal_penugasan.find_one({"id": pid}, {"_id": 0})
    if existing:
        return _replay(existing, op, digest, True)
    peg = await db.pegawai.find_one({"id": data.pegawai_id}, {"_id": 0})
    if not peg or teks(peg.get("kode_satker")) != kode:
        raise HTTPException(404, "Pegawai tidak ditemukan dalam satker aktif")
    if not pegawai_layak_portal(peg):
        raise HTTPException(409, "Pegawai tidak memenuhi syarat portal")
    asset = await _aset_dalam_satker(data.asset_id, kode)
    aliases = _periksa_aset_manual(asset, peg, kode)
    # Startup AMAN mencatat kegagalan indeks dan terus hidup. Gerbang domain
    # harus menolak pemetaan bila indeks penjaga duplikasi tidak tersedia.
    try:
        await db.portal_penugasan.create_index(
            [("slot_aktif", 1)], name="portal_penugasan_slot_aktif", unique=True,
            partialFilterExpression={"slot_aktif": {"$exists": True}})
    except PyMongoError:
        raise HTTPException(503, "Indeks penugasan portal belum siap; hubungi administrator")
    if await db.portal_penugasan.find_one({"slot_aktif": {"$in": aliases}}, {"id": 1}):
        raise HTTPException(409, "Barang fisik ini sudah memiliki penugasan portal; cabut akses lama dahulu")
    now = _now()
    doc = {
        "_id": pid, "id": pid, "version": 1, "status": "menunggu_konfirmasi",
        "pegawai_id": peg["id"], "pegawai_nama": teks(peg.get("nama")),
        "kode_satker": kode, "asset_id": asset["id"],
        **{k: asset.get(k, "") for k in ("asset_name", "asset_code", "NUP", "location", "condition")},
        "ikatan_sumber": ikatan_sumber(asset, kode), "slot_aktif": aliases,
        "dasar_penugasan": data.dasar_penugasan, "catatan": data.catatan,
        "created_at": now, "updated_at": now,
        "created_by": user.get("username", ""),
        "riwayat": [{"status": "menunggu_konfirmasi", "tanggal": now,
                     "oleh": user.get("username", ""), "catatan": data.catatan}],
    }
    result = {"message": "Akses dicatat berdasarkan penugasan yang sudah sah", "item": _ringkas_penugasan(doc, internal=True)}
    doc["_idem_buat"] = _catat_operasi(op, digest, result)
    try:
        await db.portal_penugasan.insert_one(dict(doc))
    except DuplicateKeyError:
        existing = await db.portal_penugasan.find_one({"id": pid}, {"_id": 0})
        if existing:
            return _replay(existing, op, digest, True)
        raise HTTPException(409, "Barang fisik ini sudah memiliki penugasan portal")
    await _audit("portal_penugasan_buat", doc, user, "Pemetaan akses portal berdasarkan dokumen penugasan")
    return result


@portal_pemegang_router.post("/admin/penugasan/{pid}/cabut")
async def cabut_penugasan(pid: str, data: CabutIn, request: Request,
                         user: dict = Depends(require_admin)):
    kode = _satker_staff(user)
    op, digest, version = _operasi(request, user, f"cabut:{pid}", data)
    _cek_version(version, data.version)
    p = await db.portal_penugasan.find_one({"id": pid, "kode_satker": kode}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Penugasan tidak ditemukan")
    replay = _replay(p, op, digest)
    if replay:
        return replay
    _cek_version(version, p["version"])
    if p["status"] == "dicabut":
        raise HTTPException(409, "Akses sudah dicabut")
    now = _now()
    pencabutan = {"catatan": data.catatan, "tanggal": now, "oleh": user.get("username", "")}
    result = {"message": "Akses portal dicabut; tanggung jawab resmi aset tetap mengikuti dokumen penugasan",
              "item": _ringkas_penugasan({**p, "status": "dicabut", "version": version + 1,
                                           "updated_at": now, "pencabutan": pencabutan}, internal=True)}
    res = await db.portal_penugasan.update_one(
        {"id": pid, "version": version,
         "$or": [{"laporan_aktif": {"$exists": False}},
                 {"laporan_aktif.expires_at": {"$lte": datetime.now(timezone.utc)}}]},
        {"$set": {"status": "dicabut", "updated_at": now, "pencabutan": pencabutan},
         "$unset": {"slot_aktif": "", "laporan_aktif": ""}, "$inc": {"version": 1},
         "$push": {"_operasi": _catat_operasi(op, digest, result),
                   "riwayat": {"status": "dicabut", **pencabutan}}})
    if not res.modified_count:
        raise HTTPException(409, "Penugasan berubah atau laporan sedang disimpan — muat ulang")
    await _audit("portal_penugasan_cabut", p, user, data.catatan)
    return result


@portal_pemegang_router.get("/aset")
async def aset_saya(principal: dict = Depends(require_portal_session)):
    items, sumber_cache = [], {}
    q = {"pegawai_id": principal["pegawai_id"], "kode_satker": principal["kode_satker"],
         "status": {"$ne": "dicabut"}}
    async for p in db.portal_penugasan.find(q, {"_id": 0}).sort("created_at", -1):
        try:
            asset = await periksa_penugasan_aktif(p, principal, sumber_cache=sumber_cache)
        except HTTPException:
            continue
        items.append(_ringkas_penugasan(p, asset))
    return {"items": items, "total": len(items)}


@portal_pemegang_router.post("/penugasan/{pid}/konfirmasi")
async def konfirmasi_penugasan(pid: str, data: KonfirmasiIn, request: Request,
                              principal: dict = Depends(require_portal_write)):
    op, digest, version = _operasi(request, principal, f"konfirmasi:{pid}", data, True)
    _cek_version(version, data.version)
    p, asset = await _penugasan_holder(pid, principal)
    replay = _replay(p, op, digest)
    if replay:
        return replay
    _cek_version(version, p["version"])
    if p["status"] != "menunggu_konfirmasi":
        raise HTTPException(409, "Penugasan sudah dikonfirmasi; hubungi petugas untuk perubahan")
    if data.keputusan == "sanggah" and len(data.catatan) < 5:
        raise HTTPException(422, "Sertakan alasan sanggahan minimal lima karakter")
    status = "diterima" if data.keputusan == "terima" else "disanggah"
    now = _now()
    konfirmasi = {"keputusan": data.keputusan, "catatan": data.catatan, "tanggal": now}
    result = {"message": "Konfirmasi penugasan tersimpan", "item": _ringkas_penugasan(
        {**p, "status": status, "version": version + 1, "updated_at": now, "konfirmasi": konfirmasi}, asset)}
    res = await db.portal_penugasan.update_one(
        {"id": pid, "version": version, "status": "menunggu_konfirmasi"},
        {"$set": {"status": status, "updated_at": now, "konfirmasi": konfirmasi},
         "$inc": {"version": 1},
         "$push": {"_operasi": _catat_operasi(op, digest, result),
                   "riwayat": {"status": status, "tanggal": now,
                               "oleh": f"pegawai:{principal['pegawai_id']}", "catatan": data.catatan}}})
    if not res.modified_count:
        raise HTTPException(409, "Penugasan berubah — muat ulang")
    await _audit("portal_penugasan_konfirmasi", p, principal, status)
    return result


@portal_pemegang_router.get("/laporan")
async def laporan_saya(principal: dict = Depends(require_portal_session)):
    valid, sumber_cache = [], {}
    async for p in db.portal_penugasan.find({"pegawai_id": principal["pegawai_id"],
            "kode_satker": principal["kode_satker"], "status": "diterima"}, {"_id": 0}):
        try:
            await periksa_penugasan_aktif(p, principal, True, sumber_cache=sumber_cache)
            valid.append(p["id"])
        except HTTPException:
            continue
    q = {"pegawai_id": principal["pegawai_id"], "kode_satker": principal["kode_satker"],
         "penugasan_id": {"$in": valid}}
    items = [_ringkas_laporan(r) async for r in
             db.portal_laporan.find(q, _PROJ_LAPORAN).sort("created_at", -1)]
    return {"items": items, "total": len(items)}


@portal_pemegang_router.post("/laporan")
async def kirim_laporan(data: LaporanIn, request: Request,
                       principal: dict = Depends(require_portal_write)):
    op, digest, version = _operasi(request, principal, "kirim_laporan", data, True)
    _cek_version(version, data.penugasan_version)
    p, asset = await _penugasan_holder(data.penugasan_id, principal, True)
    _cek_version(version, p["version"])
    rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aman:portal:laporan:{op}"))
    existing = await db.portal_laporan.find_one({"id": rid}, {"_id": 0})
    if existing:
        return _replay(existing, op, digest, True)
    if data.laporan_sebelumnya_id:
        prev = await db.portal_laporan.find_one({"id": data.laporan_sebelumnya_id,
            "penugasan_id": p["id"], "pegawai_id": principal["pegawai_id"],
            "kode_satker": principal["kode_satker"]}, {"_id": 0, "status": 1})
        if not prev or prev.get("status") != "perlu_perbaikan":
            raise HTTPException(409, "Klarifikasi harus merujuk laporan sendiri yang perlu perbaikan")
    try:
        bukti = await asyncio.to_thread(validasi_bukti, [b.model_dump() for b in data.bukti])
        diambil = waktu_pengambilan(data.diambil_pada)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    # Lease singkat tidak menjebak akses setelah proses mati. Retry identik
    # dapat melanjutkan; proses lain/cabut dapat merebut setelah dua menit.
    # Laporan tetap observasi historis bila sumber berubah saat penyimpanan;
    # semua pembacaan pemegang memeriksa kembali ikatan, tinjauan menandainya.
    saat_klaim = datetime.now(timezone.utc)
    claim = await db.portal_penugasan.update_one(
        {"id": p["id"], "version": version, "status": "diterima",
         "$or": [{"laporan_aktif": {"$exists": False}},
                 {"laporan_aktif.expires_at": {"$lte": saat_klaim}},
                 {"laporan_aktif.id": rid, "laporan_aktif.sidik": digest}]},
        {"$set": {"laporan_aktif": {"id": rid, "sidik": digest,
                                    "expires_at": saat_klaim + _LEASE_LAPORAN}}})
    if not claim.matched_count:
        raise HTTPException(409, "Penugasan berubah atau laporan lain sedang disimpan")
    try:
        await periksa_penugasan_aktif(p, principal, True)
        masih_diklaim = await db.portal_penugasan.find_one({
            "id": p["id"], "version": version, "status": "diterima",
            "laporan_aktif.id": rid, "laporan_aktif.sidik": digest,
            "laporan_aktif.expires_at": {"$gt": datetime.now(timezone.utc)}}, {"id": 1})
        if not masih_diklaim:
            raise HTTPException(409, "Waktu simpan berakhir atau penugasan berubah — muat ulang")
        pelapor = await db.pegawai.find_one({"id": principal["pegawai_id"]},
                                           {"_id": 0, "email": 1, "nip": 1})
        identitas_pelapor = {
            k: sidik_data(teks((pelapor or {}).get(k)).casefold())
            for k in ("email", "nip") if teks((pelapor or {}).get(k))}
        now = _now()
        doc = {"_id": rid, "id": rid, "version": 1, "status": "diajukan",
               "penugasan_id": p["id"], "penugasan_version": version,
               "pegawai_id": principal["pegawai_id"], "pegawai_nama": p["pegawai_nama"],
               "_identitas_pelapor": identitas_pelapor,
               "kode_satker": p["kode_satker"],
               **{k: p.get(k, "") for k in _ASET_RINGKAS},
               **{k: v for k, v in data.model_dump().items()
                  if k not in ("bukti", "penugasan_version", "penugasan_id", "diambil_pada")},
               "asset_name": asset.get("asset_name", ""),
               "snapshot_aset": {k: asset.get(k, "") for k in
                                 ("asset_name", "asset_code", "NUP", "location", "condition", "inventory_status")},
               "diambil_pada": diambil, "created_at": now, "updated_at": now,
               "bukti": [{**b, "diterima_pada": now} for b in bukti],
               "perlu_tindak_lanjut": tindak_lanjut_laporan(data.jenis, data.kondisi),
               "tinjauan": []}
        doc["sidik_laporan_asli"] = sidik_data({k: v for k, v in doc.items()
                                              if k not in ("_id", "version", "status", "updated_at", "tinjauan")})
        result = {"message": "Laporan tersimpan dan menunggu peninjauan petugas", "item": _ringkas_laporan(doc)}
        doc["_idem_buat"] = _catat_operasi(op, digest, result)
        try:
            await db.portal_laporan.insert_one(dict(doc))
        except DuplicateKeyError:
            existing = await db.portal_laporan.find_one({"id": rid}, {"_id": 0})
            if existing:
                return _replay(existing, op, digest, True)
            raise
    finally:
        await db.portal_penugasan.update_one(
            {"id": p["id"], "laporan_aktif.id": rid, "laporan_aktif.sidik": digest},
            {"$unset": {"laporan_aktif": ""}})
    await _audit("portal_laporan_kirim", doc, principal, f"Laporan {data.jenis}; belum mengubah master BMN")
    return result


@portal_pemegang_router.get("/admin/laporan")
async def daftar_laporan_admin(status: str = "", page: int = Query(1, ge=1),
                              page_size: int = Query(30, ge=1, le=100),
                              user: dict = Depends(require_user), pegawai_id: str = "",
                              search: str = ""):
    q = {"kode_satker": _satker_staff(user)}
    if pegawai_id:
        q["pegawai_id"] = pegawai_id
    search = search.strip()
    if len(search) > 120:
        raise HTTPException(422, "Pencarian laporan maksimal 120 karakter")
    if search:
        q["$or"] = [{k: {"$regex": re.escape(search), "$options": "i"}} for k in
                    ("asset_name", "asset_code", "NUP", "pegawai_nama", "lokasi_laporan")]
    if status:
        if status not in STATUS_LAPORAN:
            raise HTTPException(422, "Status laporan tidak dikenal")
        q["status"] = status
    total = await db.portal_laporan.count_documents(q)
    rows = db.portal_laporan.find(q, _PROJ_LAPORAN).sort([
        ("created_at", -1), ("id", -1)]).skip((page - 1) * page_size).limit(page_size)
    items = []
    async for r in rows:
        p = await db.portal_penugasan.find_one({"id": r["penugasan_id"],
                                               "kode_satker": q["kode_satker"]}, {"_id": 0})
        valid, alasan = await _validitas_penugasan(p)
        items.append({**_ringkas_laporan(r), "penugasan_valid": valid,
                      "alasan_penugasan": alasan})
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def _bukan_peninjau_sendiri(report, user):
    pid = report["pegawai_id"]
    if teks(user.get("pegawai_id")) == pid:
        raise HTTPException(403, "Pemegang tidak boleh meninjau laporannya sendiri")
    peg = await db.pegawai.find_one({"id": pid}, {"_id": 0, "email": 1, "nip": 1})
    # Akun AMAN memakai alamat email sebagai username; dokumen user lama
    # tidak selalu memiliki field email tersendiri.
    emails = {teks(user.get(k)).casefold() for k in ("email", "username") if teks(user.get(k))}
    frozen = report.get("_identitas_pelapor") or {}
    if (teks((peg or {}).get("email")).casefold() in emails
            or frozen.get("email") in {sidik_data(e) for e in emails}):
        raise HTTPException(403, "Pemegang tidak boleh meninjau laporannya sendiri")
    nip = teks(user.get("nip"))
    if nip and (nip == teks((peg or {}).get("nip"))
                or frozen.get("nip") == sidik_data(nip.casefold())):
        raise HTTPException(403, "Pemegang tidak boleh meninjau laporannya sendiri")


@portal_pemegang_router.post("/admin/laporan/{rid}/tinjau")
async def tinjau_laporan(rid: str, data: TinjauIn, request: Request,
                        user: dict = Depends(require_writer)):
    kode = _satker_staff(user)
    op, digest, version = _operasi(request, user, f"tinjau:{rid}", data)
    _cek_version(version, data.version)
    r = await db.portal_laporan.find_one({"id": rid, "kode_satker": kode}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Laporan tidak ditemukan")
    await _bukan_peninjau_sendiri(r, user)
    p = await db.portal_penugasan.find_one({"id": r["penugasan_id"], "kode_satker": kode}, {"_id": 0})
    valid, alasan = await _validitas_penugasan(p)
    replay = _replay(r, op, digest)
    if replay:
        return replay
    _cek_version(version, r["version"])
    if r["status"] != "diajukan":
        raise HTTPException(409, "Laporan sudah ditinjau; klarifikasi dicatat sebagai laporan baru")
    now = _now()
    tinjauan = {"keputusan": data.keputusan, "catatan": data.catatan,
                "tanggal": now, "oleh": user.get("username", ""),
                "penugasan_valid": valid, "alasan_penugasan": alasan}
    result = {"message": "Peninjauan laporan tersimpan; master BMN tetap mengikuti proses resmi",
              "item": _ringkas_laporan({**r, "version": version + 1,
                        "status": data.keputusan, "updated_at": now,
                        "tinjauan": [*(r.get("tinjauan") or []), tinjauan]})}
    res = await db.portal_laporan.update_one(
        {"id": rid, "kode_satker": kode, "version": version, "status": "diajukan"},
        {"$set": {"status": data.keputusan, "updated_at": now}, "$inc": {"version": 1},
         "$push": {"tinjauan": tinjauan, "_operasi": _catat_operasi(op, digest, result)}})
    if not res.modified_count:
        raise HTTPException(409, "Laporan berubah — muat ulang")
    await _audit("portal_laporan_tinjau", r, user, f"{data.keputusan}: {data.catatan}")
    return result


def _respons_bukti(report, index):
    items = report.get("bukti") or []
    if index < 0 or index >= len(items):
        raise HTTPException(404, "Bukti tidak ditemukan")
    b = items[index]
    return Response(base64.b64decode(b["data_base64"]), media_type=b["mime"], headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline", "Referrer-Policy": "no-referrer"})


@portal_pemegang_router.get("/laporan/{rid}/bukti/{index}")
async def bukti_saya(rid: str, index: int,
                    principal: dict = Depends(require_portal_session)):
    r = await db.portal_laporan.find_one({"id": rid, "pegawai_id": principal["pegawai_id"],
        "kode_satker": principal["kode_satker"]}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Laporan tidak ditemukan")
    await _penugasan_holder(r["penugasan_id"], principal, True)
    return _respons_bukti(r, index)


@portal_pemegang_router.get("/admin/laporan/{rid}/bukti/{index}")
async def bukti_admin(rid: str, index: int, user: dict = Depends(require_user)):
    kode = _satker_staff(user)
    r = await db.portal_laporan.find_one({"id": rid, "kode_satker": kode}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Laporan tidak ditemukan")
    # Bukti historis tetap dimiliki satker pembuat laporan, termasuk sesudah
    # penugasan dicabut, master berpindah satker, atau SK menghapus aset.
    return _respons_bukti(r, index)
