"""
Authentication utility functions.
JWT config, password hashing, token creation, and user verification.
"""
import os
import jwt
import bcrypt
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Header, Depends
from db import db

logger = logging.getLogger(__name__)

# Fail-fast in production: missing JWT_SECRET → log a loud warning. We keep a
# weak default ONLY for local development; deployment .env MUST set this.
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    JWT_SECRET = 'inventory_secret_key_2024_DEV_ONLY_DO_NOT_USE_IN_PROD'
    logger.warning(
        "JWT_SECRET env var missing — using insecure dev fallback. "
        "Set a strong secret in production .env immediately."
    )
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


async def _decode_bearer(authorization: str) -> dict:
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

