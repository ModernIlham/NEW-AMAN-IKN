"""
Authentication utility functions.
JWT config, password hashing, token creation, and user verification.
"""
import os
import jwt
import bcrypt
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Header, Depends, Query
from db import db

logger = logging.getLogger(__name__)

# Fail-fast: JWT_SECRET MUST be provided by the environment. There is NO usable
# hardcoded fallback — a predictable secret would let anyone forge admin tokens.
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET wajib diset")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_token(user_id: str, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc).timestamp() + (JWT_EXPIRATION_HOURS * 3600)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# Token KHUSUS MEDIA (scope="media", umur 30 hari): dipakai hanya untuk URL
# streaming foto/dokumen (?token=...) supaya URL media STABIL antar login —
# tanpa ini, rotasi token sesi (24 jam) mengganti semua URL <img> dan mem-bust
# seluruh cache foto browser setiap hari. Token ini DITOLAK oleh require_user
# (tak bisa dipakai memanggil API tulis/baca biasa); validitasnya tetap dicek
# ke db.users (akun nonaktif = ditolak) di _decode_bearer.
MEDIA_TOKEN_EXPIRATION_DAYS = 30


def create_media_token(user_id: str, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "scope": "media",
        "exp": datetime.now(timezone.utc).timestamp() + (MEDIA_TOKEN_EXPIRATION_DAYS * 86400),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# Token TANDA TANGAN (typ="sign", umur 14 hari): dipakai link e-sign yang
# dibagikan ke penanda tangan TAMU (tanpa akun). Membawa id permintaan +
# id penanda tangan + jti (sekali pakai, ditandai di record). DITOLAK untuk
# API biasa (tidak punya user_id → _decode_bearer gagal find user).
SIGN_TOKEN_EXPIRATION_DAYS = 14


def create_sign_token(sr_id: str, signer_id: str, jti: str) -> str:
    payload = {
        "typ": "sign", "sr": sr_id, "signer": signer_id, "jti": jti,
        "exp": datetime.now(timezone.utc).timestamp() + SIGN_TOKEN_EXPIRATION_DAYS * 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_sign_token(token: str = Query(default="")) -> dict:
    """Validasi token e-sign (link publik). Kembalikan {sr, signer, jti}.
    Tidak melakukan lookup user (penanda tangan tamu)."""
    if not token:
        raise HTTPException(status_code=401, detail="Token tanda tangan wajib")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Link tanda tangan kedaluwarsa")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Link tanda tangan tidak valid")
    if payload.get("typ") != "sign":
        raise HTTPException(status_code=401, detail="Token bukan untuk tanda tangan")
    return {"sr": payload.get("sr"), "signer": payload.get("signer"),
            "jti": payload.get("jti")}


async def require_user_or_sign_token(
    authorization: str = Header(default="", alias="Authorization"),
    token: str = Query(default=""),
) -> dict:
    """Gate untuk endpoint yang dipakai BAIK oleh user login MAUPUN penanda
    tangan tamu (halaman link e-sign) — mis. olah foto TTD. Prioritas header
    Bearer; fallback ?token= bertipe sign."""
    if authorization and authorization.startswith("Bearer "):
        return await _decode_bearer(authorization)
    tok = await require_sign_token(token)
    return {"guest": True, "sign": tok, "username": "tamu-ttd", "role": "tamu"}


async def _decode_bearer(authorization: str, allow_media_scope: bool = False) -> dict:
    """Decode an Authorization header value and return the user document.

    Raises HTTPException(401) on any failure. Shared by the legacy positional
    helper `get_current_user(...)` and the new FastAPI Depends-friendly
    `require_user(authorization: str = Header(...))`.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Token ber-scope "media" hanya sah untuk endpoint media/laporan
    # (require_user_or_query_token) — tolak untuk API biasa.
    if payload.get("scope") == "media" and not allow_media_scope:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload.get("user_id")}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun Anda telah dinonaktifkan. Hubungi administrator.")
    return user


async def get_current_user(authorization: str):
    """Legacy positional helper. Prefer `require_user` for new code."""
    return await _decode_bearer(authorization)


async def require_user(authorization: str = Header(default="", alias="Authorization")) -> dict:
    """FastAPI Depends-friendly auth gate.

    Usage:
        @router.get("/foo")
        async def foo(user: dict = Depends(require_user)): ...

    Returns the user document (without `password_hash`). Raises 401 / 403.
    """
    return await _decode_bearer(authorization)


async def require_admin(user: dict = Depends(require_user)) -> dict:
    """Layer on top of require_user that enforces role == 'admin'."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat melakukan aksi ini")
    return user


async def require_user_or_query_token(
    authorization: str = Header(default="", alias="Authorization"),
    token: str = Query(default=""),
) -> dict:
    """Auth gate that accepts EITHER an `Authorization: Bearer <jwt>` header OR
    a `?token=<jwt>` query param (validated against the SAME JWT secret).

    Needed for endpoints consumed by plain `<img src="...">` tags and
    `window.open(...)`, neither of which can attach an Authorization header:
    media streaming (photos / checklist files / BAST / pengesahan dokumen) and
    the HTML/PDF report previews the frontend opens in a new tab.

    SECURITY TRADEOFF: a JWT placed in the URL is captured by web-server and
    proxy access logs. This is accepted as strictly better than the previous
    posture (fully anonymous media/report reads); the token carries the normal
    24h TTL. A short-lived, media-scoped token is a future improvement.
    """
    if authorization and authorization.startswith("Bearer "):
        return await _decode_bearer(authorization, allow_media_scope=True)
    if token:
        return await _decode_bearer(f"Bearer {token}", allow_media_scope=True)
    raise HTTPException(status_code=401, detail="Autentikasi diperlukan")

