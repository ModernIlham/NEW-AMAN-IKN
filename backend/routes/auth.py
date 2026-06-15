"""Authentication routes: register, login, OTP, heartbeat."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Header

from db import db
from models import UserCreate, UserLogin, UserResponse, TokenResponse, OTPRequest, OTPVerify
from auth_utils import hash_password, verify_password, create_token, get_current_user
from shared_utils import limiter, generate_otp, send_otp_email, store_otp, get_otp, delete_otp, RESEND_API_KEY

logger = logging.getLogger(__name__)
auth_router = APIRouter()

@auth_router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate):
    """
    Register a new user (legacy endpoint - kept for backward compat).
    NEW BEHAVIOR: new users are created INACTIVE (is_active=False) and must be
    activated by admin before they can log in. First user (bootstrap admin)
    is auto-activated.
    """
    existing = await db.users.find_one({"username": user_data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah digunakan")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # First user gets admin role + active (bootstrap), subsequent get viewer + inactive
    user_count = await db.users.count_documents({})
    is_first_user = (user_count == 0)
    role = "admin" if is_first_user else "viewer"
    is_active = True if is_first_user else False

    user_doc = {
        "id": user_id,
        "username": user_data.username,
        "password": hash_password(user_data.password),
        "name": user_data.name or user_data.username,
        "role": role,
        "is_active": is_active,
        "created_at": now
    }

    await db.users.insert_one(user_doc)

    # First admin: auto-login with token.
    if is_first_user:
        token = create_token(user_id, user_data.username)
        logger.info(f"Bootstrap admin registered and auto-activated: {user_data.username}")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": user_data.username,
                "name": user_doc["name"],
                "role": role,
                "is_active": True,
                "created_at": now,
            },
            "pending_approval": False,
            "message": "Akun admin berhasil dibuat",
        }

    # Regular user: pending admin approval, NO token issued.
    logger.info(f"New user registered (pending admin approval): {user_data.username}")
    return {
        "access_token": None,
        "user": {
            "id": user_id,
            "username": user_data.username,
            "name": user_doc["name"],
            "role": role,
            "is_active": False,
            "created_at": now,
        },
        "pending_approval": True,
        "message": "Pendaftaran berhasil. Akun Anda menunggu aktivasi dari administrator sebelum dapat digunakan untuk login.",
    }

# ============================================================================
# OTP-BASED USER REGISTRATION (for admin-created users)
# ============================================================================

@auth_router.post("/auth/request-otp")
@limiter.limit("3/minute")
async def request_otp(request: Request, data: OTPRequest):
    """
    Request OTP for new user registration.
    Admin creates user with email, OTP is sent to that email.
    User must verify OTP to complete registration.
    """
    email = data.email.strip().lower()
    
    # Basic email validation
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Format email tidak valid")
    
    # Check if email already registered
    existing = await db.users.find_one({"username": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    
    # Check if password is valid
    if not data.password or len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")
    
    # Generate OTP
    otp = generate_otp()
    
    # Store in MongoDB for multi-replica support
    await store_otp(email, otp, {
        "email": email,
        "password": data.password,
        "name": data.name or email.split("@")[0]
    })
    
    # Send OTP email
    email_sent = await send_otp_email(email, otp, data.name)
    
    # Show debug OTP if email not configured OR if sending failed
    show_debug_otp = not RESEND_API_KEY or not email_sent
    
    return {
        "message": "Kode OTP telah dikirim ke email" if email_sent else "Email gagal terkirim. Gunakan kode OTP di bawah.",
        "email": email,
        "otp_sent": email_sent,
        # Show OTP for admin when email fails or not configured
        "debug_otp": otp if show_debug_otp else None
    }

@auth_router.post("/auth/resend-otp")
@limiter.limit("3/minute")
async def resend_otp(request: Request, data: OTPVerify):
    """
    Resend OTP for pending registration. Only requires email.
    Preserves existing user data, just regenerates OTP code.
    """
    email = data.email.strip().lower()
    
    stored = await get_otp(email)
    if not stored:
        raise HTTPException(status_code=400, detail="Tidak ada registrasi pending untuk email ini. Silakan daftar ulang.")
    
    # Regenerate OTP but keep existing user_data
    otp = generate_otp()
    await store_otp(email, otp, stored["user_data"])
    
    email_sent = await send_otp_email(email, otp, stored["user_data"].get("name", ""))
    show_debug_otp = not RESEND_API_KEY or not email_sent
    
    return {
        "message": "Kode OTP baru telah dikirim" if email_sent else "Email gagal terkirim. Gunakan kode OTP di bawah.",
        "email": email,
        "otp_sent": email_sent,
        "debug_otp": otp if show_debug_otp else None
    }

@auth_router.post("/auth/verify-otp")
@limiter.limit("5/minute")
async def verify_otp(request: Request, data: OTPVerify):
    """
    Verify OTP and complete user registration.
    NEW BEHAVIOR: new users are created INACTIVE (is_active=False) and must be
    activated by admin before they can log in. First user (bootstrap admin)
    is auto-activated.
    """
    email = data.email.strip().lower()
    otp = data.otp.strip()

    # Check if OTP exists
    stored = await get_otp(email)
    if not stored:
        raise HTTPException(status_code=400, detail="OTP tidak ditemukan atau sudah kadaluarsa. Minta OTP baru.")

    # Check if OTP matches
    if stored["otp"] != otp:
        raise HTTPException(status_code=400, detail="Kode OTP salah")

    # Get user data
    user_data = stored["user_data"]

    # Double-check email not registered
    existing = await db.users.find_one({"username": email})
    if existing:
        await delete_otp(email)
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # First user gets admin + active (bootstrap), subsequent get viewer + inactive
    user_count = await db.users.count_documents({})
    is_first_user = (user_count == 0)
    role = "admin" if is_first_user else "viewer"
    is_active = True if is_first_user else False

    user_doc = {
        "id": user_id,
        "username": email,
        "password": hash_password(user_data["password"]),
        "name": user_data["name"],
        "role": role,
        "is_active": is_active,
        "email_verified": True,
        "created_at": now
    }

    await db.users.insert_one(user_doc)

    # Clear OTP from store
    await delete_otp(email)

    # First admin: issue token & auto-login
    if is_first_user:
        token = create_token(user_id, email)
        logger.info(f"Bootstrap admin registered via OTP and auto-activated: {email}")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": email,
                "name": user_doc["name"],
                "role": role,
                "is_active": True,
                "created_at": now,
            },
            "pending_approval": False,
            "message": "Akun admin berhasil dibuat",
        }

    # Regular user: pending admin approval, NO token issued.
    logger.info(f"New user registered via OTP (pending admin approval): {email}")
    return {
        "access_token": None,
        "user": {
            "id": user_id,
            "username": email,
            "name": user_doc["name"],
            "role": role,
            "is_active": False,
            "created_at": now,
        },
        "pending_approval": True,
        "message": "Pendaftaran berhasil. Email Anda telah terverifikasi, namun akun menunggu aktivasi dari administrator sebelum dapat digunakan untuk login.",
    }

@auth_router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin):
    """Login user and return JWT token"""
    user = await db.users.find_one({"username": credentials.username}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    
    if not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun Anda telah dinonaktifkan. Hubungi administrator.")
    
    token = create_token(user["id"], user["username"])

    # Update last_active on login
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})
    
    # Normalize legacy role: "user" -> "operator"
    user_role = user.get("role", "operator")
    if user_role == "user":
        user_role = "operator"
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            name=user["name"],
            role=user_role,
            is_active=user.get("is_active", True),
            created_at=user["created_at"]
        )
    )

@auth_router.get("/auth/me", response_model=UserResponse)
async def get_me(authorization: str = Header(None)):
    """Get current user profile"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    user = await get_current_user(authorization)
    user_role = user.get("role", "operator")
    if user_role == "user":
        user_role = "operator"
    return UserResponse(
        id=user["id"],
        username=user["username"],
        name=user["name"],
        role=user_role,
        is_active=user.get("is_active", True),
        created_at=user["created_at"]
    )

@auth_router.post("/auth/heartbeat")
async def heartbeat(authorization: str = Header(None)):
    """Update user's last_active timestamp for online/offline tracking"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    user = await get_current_user(authorization)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}


