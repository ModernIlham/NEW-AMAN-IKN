"""Satu gerbang Tinify: anggaran 500, lintas-worker, tanpa I/O sinkron.

`used` adalah batas atas konservatif, BUKAN sekadar jumlah foto. JPEG→WebP
memakai 2 operasi; WebP→WebP cukup /shrink (1). Anggaran dicatat SEBELUM
panggilan berbayar. Jika proses mati/unduhan terputus, anggarannya tetap
terpakai: respons terlambat tidak boleh membuka peluang melewati batas 500.

Counter resmi dibaca sebelum operasi, lalu direkonsiliasi dengan $max; ia
tidak pernah menurunkan anggaran ambigu. Lease hanya membatasi konkurensi,
bukan sumber keamanan kuota. Expiry/crash tidak menghapus biaya yang dicatat.
API key sebaiknya khusus instalasi ini: pemakaian eksternal bersamaan tidak
dapat direservasi oleh database lokal.
"""
import asyncio
import io
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from PIL import Image
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from db import db

logger = logging.getLogger(__name__)
BATAS = 500
TOTAL_DETIK = 40
LEASE_DETIK = 90
JEDA_STATUS = 300
MAKS_BITA = 25 * 1024 * 1024
API = "https://api.tinify.com"


@dataclass(frozen=True)
class HasilTinify:
    data: bytes | None = None
    status: str = "sementara"
    retry_at: datetime | None = None


def _now():
    return datetime.now(timezone.utc)


def _utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _bulan(now):
    return now.strftime("%Y-%m")


def _bulan_depan(now):
    return (now.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)


def _key():
    return os.environ.get("TINIFY_API_KEY", "").strip()


def _angka(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError, OverflowError):
        return BATAS  # data penghitung rusak → tidak memberi kuota gratis


def _gambar(data):
    if not data or len(data) > MAKS_BITA:
        return None
    try:
        with Image.open(io.BytesIO(data)) as img:
            jenis = (img.format or "").upper()
            if jenis not in {"JPEG", "PNG", "WEBP", "AVIF"} or img.width * img.height > 40_000_000:
                return None
            img.verify()
            return jenis
    except Exception:
        return None


def _url_hasil(value):
    """Jangan pernah mengirim Basic Auth ke URL dari respons yang tak dipercaya."""
    try:
        u = urlsplit(value or "")
        if (u.scheme == "https" and u.hostname == "api.tinify.com"
                and u.port in (None, 443) and not u.username and not u.password
                and not u.query and not u.fragment
                and re.fullmatch(r"/output/[A-Za-z0-9_-]+", u.path)):
            return value
    except (ValueError, TypeError):
        pass
    return None


def _client(key):
    return httpx.AsyncClient(
        auth=httpx.BasicAuth("api", key), follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
        timeout=httpx.Timeout(15.0, connect=5.0, pool=3.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        # Jangan memakai proxy lingkungan tak sengaja untuk foto/kredensial.
        trust_env=False)


async def _http(client, method, url, *, limit=65536, **kwargs):
    async with client.stream(method, url, **kwargs) as response:
        data = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=65536):
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Respons Tinify melebihi batas")
        return response.status_code, response.headers, bytes(data)


def _count(headers, month):
    """Respons bulan lama tidak boleh mengisi dokumen bulan baru (atau balik)."""
    try:
        if headers.get("date") and _bulan(parsedate_to_datetime(headers["date"]).astimezone(timezone.utc)) != month:
            return None
        raw = headers.get("compression-count")
        if raw is None or not str(raw).isdigit():
            return None
        return int(raw)
    except (TypeError, ValueError, OverflowError):
        return None


def _gagal(code, count, now):
    if count is not None and count >= BATAS:
        return HasilTinify(status="kuota", retry_at=_bulan_depan(now))
    if code in (401, 402, 403):
        return HasilTinify(status="tidak_tersedia", retry_at=now + timedelta(minutes=15))
    if code in (400, 413, 415, 422):
        return HasilTinify(status="input_rusak")
    return HasilTinify(status="sementara", retry_at=now + timedelta(minutes=5))


async def _dokumen(month):
    """Migrasi non-destruktif: jumlahkan dokumen lama, termasuk duplikatnya."""
    coll = db.tinify_budget
    ident = f"tinify:{month}"
    doc = await coll.find_one({"_id": ident})
    if doc:
        return doc
    legacy = await db.compression_quotas.find(
        {"service": "tinify", "month": month}, {"used": 1}).to_list(length=1000)
    used = min(BATAS, sum(_angka(x.get("used", 0)) for x in legacy))
    try:
        await coll.update_one({"_id": ident}, {"$setOnInsert": {
            "month": month, "used": used,
            "status": "sementara", "initialized": False}}, upsert=True)
    except DuplicateKeyError:
        pass  # worker lain lebih dulu membuat _id deterministik yang sama
    return await coll.find_one({"_id": ident})


async def _klaim(doc, token):
    now = _now()
    return await db.tinify_budget.find_one_and_update(
        {"_id": doc["_id"], "$or": [
            {"lease_until": {"$exists": False}}, {"lease_until": {"$lte": now}}]},
        {"$set": {"lease": token, "lease_until": now + timedelta(seconds=LEASE_DETIK)}},
        return_document=ReturnDocument.AFTER)


async def _counter(doc, headers):
    count = _count(headers, doc["month"])
    if count is not None:
        await db.tinify_budget.update_one({"_id": doc["_id"]}, {
            "$max": {"used": count, "provider_used": count}})
    return count


async def _status(doc, token, result):
    # Respons worker dengan lease lama tak menimpa status worker baru.
    await db.tinify_budget.update_one({"_id": doc["_id"], "lease": token}, {
        "$set": {"status": result.status, "retry_at": result.retry_at,
                  "checked_at": _now()}})


async def _probe(client, doc):
    # Cara validate resmi SDK: POST /shrink TANPA foto → 400, tanpa kompresi.
    code, headers, _ = await _http(client, "POST", API + "/shrink", content=b"")
    count = await _counter(doc, headers)
    if code == 400 and count is not None:
        await db.tinify_budget.update_one({"_id": doc["_id"]}, {
            "$set": {"initialized": True}})
        return (HasilTinify(status="kuota", retry_at=_bulan_depan(_now()))
                if count >= BATAS else HasilTinify(status="ok")), count
    result = _gagal(code, count, _now())
    if result.status == "input_rusak":
        result = HasilTinify(status="sementara", retry_at=_now() + timedelta(minutes=5))
    return result, count


async def _jalankan(data, webp, cadangan, *, hanya_status=False):
    now = _now()
    if not _key():
        return HasilTinify(status="tidak_tersedia"), None
    jenis = None
    if not hanya_status:
        jenis = await asyncio.to_thread(_gambar, data)
        if jenis is None:
            return HasilTinify(status="input_rusak"), None
        # Jangan memulai operasi yang mungkin ditagih melintasi bulan UTC.
        if (_bulan_depan(now) - now).total_seconds() <= TOTAL_DETIK + 20:
            return HasilTinify(status="sementara", retry_at=_bulan_depan(now)), None
    doc = await _dokumen(_bulan(now))
    retry = _utc(doc.get("retry_at"))
    if retry and retry > now:
        return HasilTinify(status=doc.get("status", "sementara"), retry_at=retry), doc
    checked = _utc(doc.get("checked_at"))
    if hanya_status and checked and (now - checked).total_seconds() < JEDA_STATUS:
        return HasilTinify(status=doc.get("status", "sementara")), doc
    token = uuid.uuid4().hex
    locked = await _klaim(doc, token)
    if not locked:
        return HasilTinify(status="sementara", retry_at=now + timedelta(seconds=LEASE_DETIK)), doc
    doc = locked
    try:
        # Penahan dapat berubah di antara baca awal dan klaim lease.
        retry = _utc(doc.get("retry_at"))
        if retry and retry > _now():
            return HasilTinify(status=doc.get("status", "sementara"), retry_at=retry), doc
        async with _client(_key()) as client:
            result, _ = await _probe(client, doc)
            if result.status != "ok" or hanya_status:
                await _status(doc, token, result)
                return result, await db.tinify_budget.find_one({"_id": doc["_id"]})
            cost = 2 if webp and jenis != "WEBP" else 1
            now = _now()
            if _bulan(now) != doc["month"] or (_bulan_depan(now) - now).total_seconds() <= TOTAL_DETIK + 20:
                return HasilTinify(status="sementara", retry_at=_bulan_depan(now)), doc
            # Anggaran biaya penuh didahulukan, bahkan jika nanti /shrink
            # sukses tetapi unduh/convert terputus. Tidak ada refund ambigu.
            reserved = await db.tinify_budget.find_one_and_update(
                {"_id": doc["_id"], "lease": token, "lease_until": {"$gt": now},
                 "used": {"$lte": BATAS - cost - max(0, cadangan)}},
                {"$inc": {"used": cost}}, return_document=ReturnDocument.AFTER)
            if not reserved:
                fresh = await db.tinify_budget.find_one({"_id": doc["_id"]})
                held_until = _utc((fresh or {}).get("lease_until"))
                if not fresh or fresh.get("lease") != token or not held_until or held_until <= _now():
                    return HasilTinify(status="sementara", retry_at=_now() + timedelta(seconds=LEASE_DETIK)), fresh
                # Cadangan background bukan berarti kuota unggahan habis.
                cukup_tanpa_cadangan = BATAS - _angka(fresh.get("used")) >= cost
                retry = now + timedelta(minutes=15) if cadangan and cukup_tanpa_cadangan else _bulan_depan(now)
                return HasilTinify(status="kuota", retry_at=retry), fresh
            doc = reserved
            code, headers, _ = await _http(client, "POST", API + "/shrink", content=data)
            count = await _counter(doc, headers)
            if code != 201:
                result = _gagal(code, count, _now())
            else:
                url = _url_hasil(headers.get("location"))
                if not url:
                    raise ValueError("Lokasi hasil Tinify tidak sah")
                if cost == 2:
                    # Jangan meneruskan bagian berbayar setelah lease hilang.
                    held = await db.tinify_budget.find_one({
                        "_id": doc["_id"], "lease": token, "lease_until": {"$gt": _now()}})
                    if not held or _bulan(_now()) != doc["month"]:
                        result = HasilTinify(status="sementara", retry_at=_now() + timedelta(seconds=LEASE_DETIK))
                        await _status(doc, token, result)
                        return result, doc
                    if count is not None and count >= BATAS:
                        result = HasilTinify(status="kuota", retry_at=_bulan_depan(_now()))
                        await _status(doc, token, result)
                        return result, doc
                    code, headers, output = await _http(client, "POST", url, limit=MAKS_BITA,
                                                       json={"convert": {"type": "image/webp"}})
                else:
                    code, headers, output = await _http(client, "GET", url, limit=MAKS_BITA)
                count = await _counter(doc, headers)
                if code != 200:
                    result = _gagal(code, count, _now())
                else:
                    out_kind = await asyncio.to_thread(_gambar, output)
                    if not out_kind or (webp and out_kind != "WEBP"):
                        raise ValueError("Gambar hasil Tinify tidak sah")
                    result = HasilTinify(data=output, status="ok")
            # Galat gambar hanya mengenai input ini, bukan kesehatan layanan.
            await _status(doc, token, HasilTinify(status="ok") if result.status == "input_rusak" else result)
            return result, doc
    except asyncio.CancelledError:
        raise
    except Exception:
        # Tidak log pesan SDK, body, URL output, atau kunci API.
        result = HasilTinify(status="sementara", retry_at=_now() + timedelta(minutes=5))
        await _status(doc, token, result)
        return result, doc
    finally:
        await db.tinify_budget.update_one({"_id": doc["_id"], "lease": token}, {
            "$unset": {"lease": "", "lease_until": ""}})


async def _dibatasi(data=None, webp=False, cadangan=0, *, hanya_status=False):
    try:
        async with asyncio.timeout(TOTAL_DETIK):
            return await _jalankan(data, webp, int(cadangan), hanya_status=hanya_status)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("Tinify sementara tidak dapat dipastikan; anggaran tetap dijaga")
        return HasilTinify(status="sementara", retry_at=_now() + timedelta(minutes=5)), None


async def optimalkan(data: bytes, *, webp=False, cadangan=0) -> HasilTinify:
    result, _ = await _dibatasi(data, webp, cadangan)
    return result


async def status_kuota() -> dict:
    result, doc = await _dibatasi(hanya_status=True)
    # Dokumen anggaran dapat tercipta sebelum probe pertama berhasil. Nilai
    # awal 0 (atau counter legasi) bukan bukti provider memberi sisa 500.
    # Ini hanya proyeksi untuk pembaca; reservasi/angka konservatif di DB
    # tetap utuh, termasuk saat layanan yang pernah terverifikasi gagal lagi.
    terverifikasi = bool(doc and doc.get("initialized") is True
                         and doc.get("provider_used") is not None)
    used = _angka(doc.get("used", BATAS)) if terverifikasi else None
    return {"used": used, "remaining": max(0, BATAS - used) if used is not None else 0,
            "limit": BATAS, "month": _bulan(_now()),
            "tersedia": terverifikasi and result.status == "ok", "status": result.status,
            "retry_at": result.retry_at,
            "provider_used": doc.get("provider_used") if doc else None,
            "anggaran_konservatif": True}
