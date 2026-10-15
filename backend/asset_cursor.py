"""Opt-in sequential asset cursor; page-number API remains compatible.

Mutable dataset, no immutable snapshot guarantee. Cursor is scoped to principal,
filters, order, page size and installation dataset epoch, expires in 30 minutes.
Only canonical created_at string/null is supported; other legacy BSON types
require the page API instead of being silently omitted.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from bson import json_util
from fastapi import HTTPException

from auth_utils import JWT_SECRET

KINDS = {"newest", "oldest"}
MAX_CURSOR_BYTES = 2048


def fingerprint(user, query, sort_by, page_size, generation):
    context = {"user": str(user.get("id") or user.get("username") or ""),
               "role": user.get("role"), "satker": user.get("kode_satker", ""),
               "query": query, "sort": sort_by, "page_size": page_size,
               "generation": generation, "version": 1}
    canonical = json_util.dumps(context, sort_keys=True, json_options=json_util.CANONICAL_JSON_OPTIONS)
    return hashlib.sha256(canonical.encode()).hexdigest()


def encode_cursor(context, last, page):
    return jwt.encode({"purpose": "asset-list-cursor", "version": 1, "context": context,
        "created_at": last.get("created_at"), "id": last["id"], "page": page,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}, JWT_SECRET, algorithm="HS256",
        headers={"typ": "AMAN-ASSET-CURSOR"})


def decode_cursor(token, context):
    if not isinstance(token, str) or len(token.encode()) > MAX_CURSOR_BYTES:
        raise HTTPException(400, "Cursor daftar tidak valid atau terlalu panjang")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(409, "Cursor daftar kedaluwarsa. Mulai dari halaman pertama.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Cursor daftar tidak valid")
    if payload.get("purpose") != "asset-list-cursor" or payload.get("version") != 1:
        raise HTTPException(400, "Jenis cursor daftar tidak valid")
    if payload.get("context") != context:
        raise HTTPException(409, "Konteks daftar berubah. Mulai dari halaman pertama.")
    identifier, value, page = payload.get("id"), payload.get("created_at"), payload.get("page")
    if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 200
            or not (value is None or isinstance(value, str) and len(value) <= 128)
            or not isinstance(page, int) or isinstance(page, bool) or not 2 <= page <= 10000000):
        raise HTTPException(400, "Posisi cursor daftar tidak valid")
    return payload


def after_cursor(position, sort_by):
    identifier, value = position["id"], position["created_at"]
    same = {"created_at": value, "id": {"$gt": identifier}}
    if value is None:
        return {"$or": [same, {"created_at": {"$type": "string"}}]} if sort_by == "oldest" else same
    if sort_by == "oldest":
        return {"$or": [{"created_at": {"$gt": value}}, same]}
    return {"$or": [{"created_at": {"$lt": value}}, same, {"created_at": None}]}


async def ensure_cursor_domain(collection, query):
    unsupported = {"$expr": {"$not": [{"$in": [{"$type": "$created_at"}, ["string", "null", "missing"]]}]}}
    if await collection.find_one({"$and": [query, unsupported]}, {"_id": 1}):
        raise HTTPException(400, "Urutan waktu data lama tidak mendukung cursor. Gunakan pagination halaman.")
