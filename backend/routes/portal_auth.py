"""Masuk tanpa registrasi untuk BMN Saya, dan pengesahan akses oleh admin."""
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from slowapi.util import get_remote_address

from auth_utils import require_admin
from db import db
import portal_auth as pa
from shared_utils import kode_satker_user, limiter, log_audit

logger = logging.getLogger(__name__)
portal_auth_router = APIRouter(prefix="/portal-pemegang")


class MintaLink(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class MasukPortal(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class AksesPortalIn(BaseModel):
    pegawai_id: str = Field(min_length=1, max_length=100)
    aktif: bool
    catatan: str = Field(min_length=5, max_length=1000)
    version: int = Field(ge=0)
    email: str = Field(default="", max_length=254)
    konfirmasi_email: bool = False


def _privat(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def _cookie(response, nama, secret, max_age):
    response.set_cookie(nama, secret, max_age=max_age, path=pa.PORTAL_PATH,
                        secure=True, httponly=True, samesite="strict")


def _hapus_cookie(response, nama):
    response.delete_cookie(nama, path=pa.PORTAL_PATH, secure=True,
                           httponly=True, samesite="strict")


async def _kirim_tertunda(email, challenge, origin):
    try:
        await pa.siapkan_link_portal(email, challenge, origin=origin)
    except Exception:
        # Background task tidak mengubah respons generik atau membocorkan
        # konfigurasi, alamat, maupun secret melalui exception provider.
        logger.warning("Permintaan tautan portal tidak dapat diproses")


@portal_auth_router.post("/auth/minta-link")
@limiter.limit("10/minute", key_func=get_remote_address)
async def minta_link(request: Request, payload: MintaLink, response: Response,
                     background_tasks: BackgroundTasks):
    pa.pastikan_origin_portal(request)
    _privat(response)
    email = pa.email_normal(payload.email)
    challenge = request.cookies.get(pa.CHALLENGE_COOKIE, "")
    if not pa._RAHASIA.fullmatch(challenge):
        challenge = pa.rahasia_baru()
    _cookie(response, pa.CHALLENGE_COOKIE, challenge, int(pa.LINK_TTL.total_seconds()))
    if pa.email_sah(email):
        # Semua alamat mendapat respons yang sama sebelum lookup/kirim email.
        background_tasks.add_task(_kirim_tertunda, email, challenge, request.headers["origin"])
    return {"message": pa.PESAN_LINK}


@portal_auth_router.post("/auth/masuk")
@limiter.limit("15/minute", key_func=get_remote_address)
async def masuk_portal(request: Request, payload: MasukPortal, response: Response):
    pa.pastikan_origin_portal(request)
    _privat(response)
    challenge = request.cookies.get(pa.CHALLENGE_COOKIE, "")
    if not pa._RAHASIA.fullmatch(challenge):
        raise HTTPException(401, "Buka tautan pada peramban tempat meminta akses, "
                            "atau minta tautan baru di peramban ini.")
    if not pa._RAHASIA.fullmatch(payload.token):
        raise HTTPException(401, "Tautan masuk tidak berlaku. Minta tautan baru.")
    now = pa.sekarang()
    query = {"_id": pa.hash_rahasia(payload.token), "status": "menunggu",
             "challenge_hash": pa.hash_rahasia(challenge), "expires_at": {"$gt": now}}
    token = await db.portal_pemegang_tokens.find_one(query)
    valid = await pa.akses_pegawai_sah(token["pegawai_id"]) if token else None
    if not valid:
        raise HTTPException(401, "Tautan tidak berlaku atau peramban berbeda. "
                            "Minta tautan baru di peramban ini.")
    peg, akses = valid
    if (token.get("epoch") != akses.get("epoch")
            or token.get("identitas_hash") != akses.get("identitas_hash")
            or token.get("kode_satker") != peg.get("kode_satker")):
        raise HTTPException(401, "Tautan telah dicabut. Hubungi pengelola BMN.")
    # Filter pada operasi atomik menutup replay/race sesudah pemeriksaan awal.
    consumed = await db.portal_pemegang_tokens.find_one_and_update(
        query, {"$set": {"status": "dipakai", "used_at": now}},
        return_document=ReturnDocument.AFTER)
    if not consumed:
        raise HTTPException(401, "Tautan sudah dipakai atau kedaluwarsa. Minta tautan baru.")
    raw, csrf = pa.rahasia_baru(), pa.rahasia_baru()
    akhir = now + pa.SESSION_ABSOLUTE
    sesi = {"_id": pa.hash_rahasia(raw), "id": str(uuid.uuid4()),
            "pegawai_id": peg["id"], "kode_satker": peg["kode_satker"],
            "epoch": akses["epoch"], "identitas_hash": akses["identitas_hash"],
            "csrf_token": csrf, "created_at": now, "last_seen_at": now,
            "idle_expires_at": now + pa.SESSION_IDLE, "expires_at": akhir}
    await db.portal_pemegang_sesi.insert_one(sesi)
    # Jika admin mencabut/mengubah identitas di antara consume dan insert,
    # jangan mengembalikan cookie yang tampak sukses. Guard juga selalu cek ulang.
    terbaru = await pa.akses_pegawai_sah(peg["id"])
    if not terbaru or terbaru[1].get("epoch") != akses.get("epoch"):
        await db.portal_pemegang_sesi.delete_one({"_id": sesi["_id"]})
        raise HTTPException(401, "Akses portal berubah. Hubungi pengelola BMN.")
    lama = request.cookies.get(pa.SESSION_COOKIE, "")
    if pa._RAHASIA.fullmatch(lama):
        await db.portal_pemegang_sesi.delete_one({"_id": pa.hash_rahasia(lama)})
    _cookie(response, pa.SESSION_COOKIE, raw, int(pa.SESSION_ABSOLUTE.total_seconds()))
    _hapus_cookie(response, pa.CHALLENGE_COOKIE)
    return {"pegawai": {"id": peg["id"], "nama": peg.get("nama") or "",
                        "kode_satker": peg["kode_satker"]},
            "session_id": sesi["id"], "csrf_token": csrf, "expires_at": akhir.isoformat(),
            "idle_expires_at": sesi["idle_expires_at"].isoformat()}


@portal_auth_router.get("/sesi")
async def sesi_portal(response: Response, sesi: dict = Depends(pa.require_portal_session)):
    _privat(response)
    return {k: sesi[k] for k in ("pegawai", "session_id", "csrf_token", "expires_at", "idle_expires_at")}


@portal_auth_router.post("/auth/keluar")
async def keluar_portal(request: Request, response: Response,
                        sesi: dict = Depends(pa.require_portal_write)):
    await db.portal_pemegang_sesi.delete_one({"id": sesi["session_id"]})
    _hapus_cookie(response, pa.SESSION_COOKIE)
    _hapus_cookie(response, pa.CHALLENGE_COOKIE)
    _privat(response)
    return {"ok": True}


async def _pegawai_admin(pegawai_id, admin):
    kode = kode_satker_user(admin)
    if not kode:
        raise HTTPException(403, "Pilih Satker Aktif sebelum mengelola akses portal")
    peg = await db.pegawai.find_one({"id": pegawai_id, "kode_satker": kode}, {"_id": 0})
    if not peg:
        raise HTTPException(404, "Pegawai tidak ditemukan di satker aktif")
    return peg


def _akses_publik(akses):
    a = akses or {}
    fields = ("aktif", "email_verified", "verified_at", "verified_by", "catatan",
              "alasan_pencabutan", "dicabut_pada", "kode_satker", "version")
    result = {**{k: a[k] for k in fields if k in a},
              "aktif": a.get("aktif") is True, "version": int(a.get("version") or 0)}
    for field in ("verified_at", "dicabut_pada"):
        value = pa.waktu_utc(result.get(field))
        if value:
            result[field] = value.isoformat()
    return result


@portal_auth_router.get("/admin/akses")
async def baca_akses_portal(response: Response, pegawai_id: str,
                            admin: dict = Depends(require_admin)):
    peg = await _pegawai_admin(pegawai_id, admin)
    akses = await db.portal_pemegang_akses.find_one({"id": pegawai_id})
    _privat(response)
    return {"pegawai_id": pegawai_id, "email": pa.email_normal(peg.get("email")),
            "nama": peg.get("nama") or "", "kode_satker": peg["kode_satker"],
            "layak": pa.pegawai_layak_portal(peg), "akses": _akses_publik(akses),
            "version": int((akses or {}).get("version") or 0)}


@portal_auth_router.post("/admin/akses")
async def ubah_akses_portal(request: Request, payload: AksesPortalIn, response: Response,
                            admin: dict = Depends(require_admin)):
    pa.pastikan_origin_portal(request)
    peg = await _pegawai_admin(payload.pegawai_id, admin)
    _privat(response)
    raw_key = request.headers.get("Idempotency-Key", "").strip()
    if not raw_key or len(raw_key) > 200:
        raise HTTPException(400, "Idempotency-Key wajib diisi (maksimal 200 karakter)")
    try:
        versi_header = int(request.headers.get("If-Match", "").strip('"'))
    except ValueError:
        raise HTTPException(428, "If-Match wajib memuat versi akses yang dibaca")
    if versi_header != payload.version:
        raise HTTPException(409, "Versi akses berbeda. Muat ulang data pegawai.")
    sid = str(admin.get("id") or admin.get("username") or "")
    key = "portal-akses:" + pa.hash_rahasia(f"{sid}:{raw_key}")
    isi = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True).encode()).hexdigest()
    lama_idem = await db.idempotency_keys.find_one({"key": key})
    if lama_idem:
        if lama_idem.get("payload_hash") != isi:
            raise HTTPException(409, "Idempotency-Key sudah dipakai untuk permintaan berbeda")
        if lama_idem.get("response") is not None:
            return lama_idem["response"]
        raise HTTPException(409, "Permintaan sedang diproses. Muat ulang sebelum mencoba lagi.")
    if payload.aktif:
        if (not payload.konfirmasi_email
                or pa.email_normal(payload.email) != pa.email_normal(peg.get("email"))):
            raise HTTPException(400, "Konfirmasikan bahwa email yang tampil milik pegawai ini")
        tunggal = await pa.pegawai_email_tunggal(peg.get("email"))
        if not pa.pegawai_layak_portal(peg) or not tunggal or tunggal.get("id") != peg["id"]:
            raise HTTPException(409, "Pegawai belum memenuhi syarat atau email dipakai beberapa pegawai")
    akses = await db.portal_pemegang_akses.find_one({"id": peg["id"]})
    if int((akses or {}).get("version") or 0) != payload.version:
        raise HTTPException(409, "Akses telah berubah. Muat ulang data pegawai.")
    try:
        await db.idempotency_keys.insert_one({"key": key, "payload_hash": isi,
                                              "created_at": pa.sekarang()})
    except DuplicateKeyError:
        raise HTTPException(409, "Permintaan sedang diproses. Coba lagi.")
    now = pa.sekarang()
    nilai = {"id": peg["id"], "kode_satker": peg["kode_satker"],
             "aktif": payload.aktif, "email_verified": pa.email_normal(peg.get("email")),
             "identitas_hash": pa.identitas_portal_hash(peg),
             "epoch": int((akses or {}).get("epoch") or 0) + 1,
             "version": payload.version + 1, "catatan": payload.catatan.strip(),
             "verified_at": now, "verified_by": sid,
             "alasan_pencabutan": "" if payload.aktif else payload.catatan.strip()}
    try:
        if akses:
            result = await db.portal_pemegang_akses.update_one(
                {"id": peg["id"], "version": payload.version}, {"$set": nilai})
            if not result.matched_count:
                raise HTTPException(409, "Akses telah berubah. Muat ulang data pegawai.")
        else:
            try:
                await db.portal_pemegang_akses.insert_one({"_id": peg["id"], **nilai})
            except DuplicateKeyError:
                raise HTTPException(409, "Akses telah berubah. Muat ulang data pegawai.")
    except HTTPException:
        await db.idempotency_keys.delete_one({"key": key, "payload_hash": isi})
        raise
    # Epoch sudah menggugurkan sesi sebelum pembersihan ini berjalan.
    await db.portal_pemegang_tokens.delete_many({"pegawai_id": peg["id"]})
    await db.portal_pemegang_sesi.delete_many({"pegawai_id": peg["id"]})
    await log_audit("portal_akses_ubah", "", peg["id"], username=sid,
                    kode_satker=peg["kode_satker"],
                    detail=("Akses portal diaktifkan; kepemilikan email dikonfirmasi admin"
                            if payload.aktif else "Akses portal dicabut oleh admin"))
    hasil = {"ok": True, "pegawai_id": peg["id"], "akses": _akses_publik(nilai),
             "version": nilai["version"]}
    await db.idempotency_keys.update_one({"key": key}, {"$set": {"response": hasil}})
    return hasil
