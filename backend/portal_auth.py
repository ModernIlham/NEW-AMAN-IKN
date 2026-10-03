"""Identitas dan sesi khusus pemegang BMN; tidak menerima JWT akun staf.

Token email dan sesi disimpan sebagai hash. Hak portal selalu dibaca kembali
dari persetujuan akses serta Master Pegawai, termasuk sesudah impor/restore.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from db import db

logger = logging.getLogger(__name__)
PORTAL_PATH = "/api/portal-pemegang"
SESSION_COOKIE = "aman_portal_sesi"
CHALLENGE_COOKIE = "aman_portal_tantangan"
LINK_TTL = timedelta(minutes=15)
SESSION_IDLE = timedelta(minutes=30)
SESSION_ABSOLUTE = timedelta(hours=8)
PESAN_LINK = ("Jika email sesuai Master Pegawai dan akses telah diaktifkan, "
              "tautan masuk akan dikirim. Periksa kotak masuk atau spam.")
STATUS_PORTAL = frozenset({"aktif", "cuti", "tugas_belajar"})
FIELD_IDENTITAS_PORTAL = (
    "id", "nama", "nip", "email", "kode_satker", "status",
    "status_kepegawaian", "kewarganegaraan", "jenis_identitas_wna",
    "nomor_identitas_wna", "tanggal_lahir", "tgl_mulai_kontrak",
    "tgl_selesai_kontrak", "portal_identitas_epoch",
)
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_RAHASIA = re.compile(r"^[A-Za-z0-9_-]{43}$")


def sekarang():
    return datetime.now(timezone.utc)


def waktu_utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def email_normal(nilai):
    # Jangan menghapus titik/plus alias: itu bukan aturan universal email.
    return str(nilai or "").strip().lower()


def email_sah(nilai):
    return len(nilai) <= 254 and bool(_EMAIL.fullmatch(nilai))


def hash_rahasia(nilai):
    return hashlib.sha256(str(nilai).encode("utf-8")).hexdigest()


def rahasia_baru():
    return secrets.token_urlsafe(32)


def identitas_portal_hash(pegawai):
    data = {k: str((pegawai or {}).get(k) or "").strip()
            for k in FIELD_IDENTITAS_PORTAL}
    data["email"] = email_normal(data["email"])
    return hash_rahasia(json.dumps(data, sort_keys=True, ensure_ascii=False))


def identitas_portal_berubah(sebelum, sesudah):
    return identitas_portal_hash(sebelum) != identitas_portal_hash(sesudah)


def pegawai_layak_portal(pegawai):
    p = pegawai or {}
    if (not str(p.get("id") or "").strip()
            or not str(p.get("kode_satker") or "").strip()
            or p.get("status") not in STATUS_PORTAL
            or not email_sah(email_normal(p.get("email")))):
        return False
    if p.get("status_kepegawaian") == "non_asn":
        hari_ini = sekarang().astimezone(timezone(timedelta(hours=8))).date()
        for field, mulai in (("tgl_mulai_kontrak", True), ("tgl_selesai_kontrak", False)):
            nilai = str(p.get(field) or "").strip()
            if not nilai:
                continue
            try:
                tanggal = datetime.strptime(nilai, "%Y-%m-%d").date()
            except (ValueError, OverflowError):
                return False
            if (mulai and tanggal > hari_ini) or (not mulai and tanggal < hari_ini):
                return False
    return True


def origin_portal():
    """Allowlist konfigurasi; tidak mempercayai Host/X-Forwarded-Host klien."""
    sumber = os.environ.get("ALLOWED_ORIGINS") or os.environ.get("CORS_ORIGINS") or ""
    nilai = [os.environ.get("APP_PUBLIC_URL", ""), *sumber.split(",")]
    if not any(str(v).strip() for v in nilai):
        nilai = ["https://amanikn-inventarisasi.com",
                 "https://www.amanikn-inventarisasi.com", "http://localhost:3000"]
    hasil = set()
    for v in nilai:
        u = urlsplit(str(v).strip())
        if (u.scheme in {"http", "https"} and u.netloc and not u.username
                and not u.password and u.hostname != "*"):
            hasil.add(f"{u.scheme}://{u.netloc}")
    return hasil


def basis_url_portal(origin=None):
    configured = str(os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
    asal = origin_portal()
    if origin is not None:
        # Origin frontend sudah diperiksa allowlist; jaga host cookie challenge
        # (www/apex bisa berbeda). Jangan menebak host dari header proxy/Host.
        return origin if origin in asal and origin.startswith("https://") else ""
    if configured:
        u = urlsplit(configured)
        if f"{u.scheme}://{u.netloc}" in asal and u.scheme == "https":
            return f"{u.scheme}://{u.netloc}"
        return ""
    return next(iter(sorted(o for o in asal if o.startswith("https://"))), "")


def pastikan_origin_portal(request: Request):
    if request.headers.get("origin", "") not in origin_portal():
        raise HTTPException(403, "Asal permintaan portal tidak diizinkan")


async def pegawai_email_tunggal(email, database=None):
    basis = database if database is not None else db
    # Master lama belum memiliki email_normal. Pencocokan utuh tetap membaca
    # duplikat lintas satker, termasuk pegawai nonaktif (tanpa union identitas).
    q = {"email": {"$regex": r"^\s*" + re.escape(email_normal(email)) + r"\s*$",
                   "$options": "i"}}
    rows = await basis.pegawai.find(q, {"_id": 0}).limit(2).to_list(2)
    return rows[0] if len(rows) == 1 else None


async def akses_pegawai_sah(pegawai_id, database=None):
    basis = database if database is not None else db
    pegawai = await basis.pegawai.find_one({"id": pegawai_id}, {"_id": 0})
    akses = await basis.portal_pemegang_akses.find_one({"id": pegawai_id}, {"_id": 0})
    if (not pegawai_layak_portal(pegawai) or not akses or akses.get("aktif") is not True
            or akses.get("kode_satker") != pegawai.get("kode_satker")
            or akses.get("email_verified") != email_normal(pegawai.get("email"))
            or akses.get("identitas_hash") != identitas_portal_hash(pegawai)):
        return None
    tunggal = await pegawai_email_tunggal(akses["email_verified"], basis)
    if not tunggal or tunggal.get("id") != pegawai_id:
        return None
    return pegawai, akses


async def cabut_akses_portal_pegawai(pegawai_ids, alasan, database=None):
    """Cabut sebelum master berubah; kegagalan storage tidak dilewati."""
    basis = database if database is not None else db
    ids = list({str(v) for v in pegawai_ids if v})
    if not ids:
        return
    await basis.portal_pemegang_akses.update_many(
        {"id": {"$in": ids}}, {"$set": {"aktif": False, "dicabut_pada": sekarang(),
            "alasan_pencabutan": str(alasan)[:300]}, "$inc": {"epoch": 1, "version": 1}})
    await basis.portal_pemegang_tokens.delete_many({"pegawai_id": {"$in": ids}})
    await basis.portal_pemegang_sesi.delete_many({"pegawai_id": {"$in": ids}})


async def cabut_semua_portal_akses(alasan, database=None):
    """Fail-closed sesudah restore/reset; aman dipanggil ulang."""
    basis = database if database is not None else db
    await basis.portal_pemegang_akses.update_many(
        {}, {"$set": {"aktif": False, "dicabut_pada": sekarang(),
                     "alasan_pencabutan": str(alasan)[:300]},
             "$inc": {"epoch": 1, "version": 1}})
    await basis.portal_pemegang_tokens.delete_many({})
    await basis.portal_pemegang_sesi.delete_many({})


async def cabut_email_bentrok(email, database=None):
    basis = database if database is not None else db
    e = email_normal(email)
    if not e:
        return
    rows = await basis.pegawai.find(
        {"email": {"$regex": r"^\s*" + re.escape(e) + r"\s*$", "$options": "i"}},
        {"id": 1}).to_list(None)
    if len(rows) > 1:
        await cabut_akses_portal_pegawai(
            [p["id"] for p in rows], "Email dipakai beberapa pegawai; verifikasi ulang", basis)


async def cabut_email_bentrok_banyak(emails, database=None):
    """Satu scan proyeksi email untuk impor; hindari lookup per baris."""
    basis = database if database is not None else db
    sasaran = {email_normal(e) for e in emails if email_normal(e)}
    if not sasaran:
        return
    per_email = {}
    async for peg in basis.pegawai.find({}, {"_id": 0, "id": 1, "email": 1}):
        email = email_normal(peg.get("email"))
        if email in sasaran and peg.get("id"):
            per_email.setdefault(email, []).append(peg["id"])
    ids = [pid for values in per_email.values() if len(values) > 1 for pid in values]
    await cabut_akses_portal_pegawai(ids, "Email impor dipakai beberapa pegawai; verifikasi ulang", basis)


async def batas_kirim_portal(email, database=None):
    """Batas tambahan per-email + global di Mongo bersama, fail-closed.

    IP ditangani limiter existing pada route. Counter tidak menyimpan email.
    Batas global menahan biaya email; batas per-email menahan banjir kotak masuk.
    """
    basis = database if database is not None else db
    now = sekarang()
    epoch = int(now.timestamp())
    batas = [(f"email:{hash_rahasia(email_normal(email))}", 60, 1),
             (f"email:{hash_rahasia(email_normal(email))}", 3600, 5),
             ("global", 3600, 100), ("global", 86400, 500)]
    for nama, detik, maksimum in batas:
        key = f"{nama}:{detik}:{epoch // detik}"
        rec = await basis.portal_pemegang_batas.find_one_and_update(
            {"_id": key}, {"$inc": {"jumlah": 1}, "$setOnInsert": {
                "expires_at": now + timedelta(seconds=detik * 2)}},
            upsert=True, return_document=ReturnDocument.AFTER)
        if rec["jumlah"] > maksimum:
            return False
    return True


async def kirim_email_portal(email, nama, link):
    """Transport Resend existing, tanpa mencatat token/email/galat provider."""
    from portal_email import isi_email_portal
    import shared_utils as su

    if not su.RESEND_API_KEY:
        return False
    params = {"from": su.SENDER_EMAIL, "to": [email],
              "subject": "Tautan masuk BMN Saya — AMAN",
              **isi_email_portal(nama, link, int(LINK_TTL.total_seconds() // 60))}
    try:
        await asyncio.wait_for(asyncio.to_thread(su.resend.Emails.send, params), timeout=12)
        await su.catat_email_terkirim("portal_pemegang")
        return True
    except Exception as exc:
        # Galat SDK dapat memuat badan permintaan dan kredensial: jangan log.
        lingkup = su._deteksi_kuota_email(str(exc))
        if lingkup:
            await su.catat_kuota_email_tercapai(lingkup, "Pengiriman tautan portal ditolak karena kuota")
        logger.warning("Pengiriman tautan portal gagal")
        return False


async def siapkan_link_portal(email, challenge, database=None, origin=None):
    """Dijalankan setelah respons generik, tanpa memasukkan secret ke antrean DB."""
    basis = database if database is not None else db
    if not await batas_kirim_portal(email, basis):
        return
    peg = await pegawai_email_tunggal(email, basis)
    valid = await akses_pegawai_sah(peg["id"], basis) if peg else None
    basis_url = basis_url_portal(origin)
    if not valid or not basis_url:
        return
    peg, akses = valid
    token = rahasia_baru()
    token_hash = hash_rahasia(token)
    await basis.portal_pemegang_tokens.insert_one({
        "_id": token_hash, "pegawai_id": peg["id"], "kode_satker": peg["kode_satker"],
        "challenge_hash": hash_rahasia(challenge), "epoch": akses["epoch"],
        "identitas_hash": akses["identitas_hash"], "status": "menunggu",
        "created_at": sekarang(), "expires_at": sekarang() + LINK_TTL,
    })
    ok = await kirim_email_portal(email_normal(peg["email"]), peg.get("nama") or "",
                                 f"{basis_url}/bmn-saya#token={token}")
    if not ok:
        await basis.portal_pemegang_tokens.delete_one({"_id": token_hash})


async def require_portal_session(request: Request):
    raw = request.cookies.get(SESSION_COOKIE, "")
    if not _RAHASIA.fullmatch(raw):
        raise HTTPException(401, "Sesi portal berakhir. Minta tautan masuk kembali.")
    now = sekarang()
    sesi = await db.portal_pemegang_sesi.find_one({
        "_id": hash_rahasia(raw), "expires_at": {"$gt": now},
        "idle_expires_at": {"$gt": now}, "dicabut": {"$ne": True}})
    valid = await akses_pegawai_sah(sesi["pegawai_id"]) if sesi else None
    if not valid:
        raise HTTPException(401, "Sesi portal berakhir atau akses perlu diverifikasi ulang.")
    peg, akses = valid
    if (sesi.get("epoch") != akses.get("epoch")
            or sesi.get("identitas_hash") != akses.get("identitas_hash")
            or sesi.get("kode_satker") != peg.get("kode_satker")):
        raise HTTPException(401, "Akses portal telah dicabut. Hubungi pengelola BMN.")
    akhir = waktu_utc(sesi["expires_at"])
    idle = min(akhir, now + SESSION_IDLE)
    # Tidak menghidupkan kembali sesi yang sudah dihapus/dicabut saat lookup.
    hasil = await db.portal_pemegang_sesi.update_one(
        {"_id": sesi["_id"], "dicabut": {"$ne": True}, "idle_expires_at": {"$gt": now}},
        {"$max": {"idle_expires_at": idle}, "$set": {"last_seen_at": now}})
    if not hasil.matched_count:
        raise HTTPException(401, "Sesi portal telah berakhir")
    return {"pegawai_id": peg["id"], "kode_satker": peg["kode_satker"],
            "session_id": sesi["id"], "csrf_token": sesi["csrf_token"],
            "pegawai": {"id": peg["id"], "nama": peg.get("nama") or "",
                         "kode_satker": peg["kode_satker"]},
            "expires_at": akhir.isoformat(), "idle_expires_at": idle.isoformat()}


async def require_portal_write(request: Request):
    pastikan_origin_portal(request)
    sesi = await require_portal_session(request)
    csrf = request.headers.get("X-Portal-CSRF", "")
    if not hmac.compare_digest(csrf.encode(), sesi["csrf_token"].encode()):
        raise HTTPException(403, "Verifikasi permintaan portal gagal. Muat ulang halaman.")
    return sesi
