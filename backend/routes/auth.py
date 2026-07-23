"""Authentication routes: register, login, OTP, heartbeat."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Header

from db import db
from models import UserCreate, UserLogin, UserResponse, TokenResponse, OTPRequest, OTPVerify
from auth_utils import hash_password, verify_password, verify_password_dummy, create_token, create_media_token, get_current_user
import hmac

from shared_utils import limiter, generate_otp, send_otp_email, store_otp, get_otp, delete_otp, catat_gagal_otp, RESEND_API_KEY, SENDER_EMAIL

logger = logging.getLogger(__name__)
auth_router = APIRouter()


def _debug_otp_allowed() -> bool:
    """Whether the OTP may be echoed back in the API response.

    ONLY when ALLOW_DEBUG_OTP is explicitly truthy AND we are not running in
    production. Otherwise the OTP is never returned to the client (a returned
    OTP fully defeats email-based verification for anyone who can hit the API).
    """
    allow = os.environ.get("ALLOW_DEBUG_OTP", "").strip().lower() in ("1", "true", "yes", "on")
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "").strip().lower()
    is_prod = env in ("production", "prod")
    return allow and not is_prod

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
    email_sent, email_alasan = await send_otp_email(email, otp, data.name)
    
    # Only expose the OTP when email delivery is unavailable AND debug echo is
    # explicitly enabled for a non-production environment.
    show_debug_otp = (not RESEND_API_KEY or not email_sent) and _debug_otp_allowed()

    return {
        "message": "Kode OTP telah dikirim ke email" if email_sent else f"Email gagal terkirim: {email_alasan}",
        "email": email,
        "otp_sent": email_sent,
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
    
    email_sent, email_alasan = await send_otp_email(email, otp, stored["user_data"].get("name", ""))
    show_debug_otp = (not RESEND_API_KEY or not email_sent) and _debug_otp_allowed()

    return {
        "message": "Kode OTP baru telah dikirim" if email_sent else f"Email gagal terkirim: {email_alasan}",
        "email": email,
        "otp_sent": email_sent,
        "debug_otp": otp if show_debug_otp else None
    }

@auth_router.get("/auth/email-status")
async def email_status():
    """Status konfigurasi layanan email — diagnosa cepat "OTP tidak terkirim".
    Publik-aman: hanya mengungkap ADA/TIDAKNYA konfigurasi + alamat pengirim
    (bukan nilai kunci) — sama seperti yang terlihat di email mana pun."""
    sandbox = SENDER_EMAIL.strip().lower().endswith("@resend.dev")
    return {
        "terkonfigurasi": bool(RESEND_API_KEY),
        "sender_email": SENDER_EMAIL,
        "mode_uji_resend": sandbox,
        "catatan": (
            "" if RESEND_API_KEY and not sandbox else
            ("Layanan email BELUM dikonfigurasi (RESEND_API_KEY kosong)."
             if not RESEND_API_KEY else
             "SENDER_EMAIL masih alamat uji Resend (@resend.dev) — hanya bisa "
             "mengirim ke email pemilik akun Resend; setel domain terverifikasi "
             "agar OTP sampai ke semua pendaftar.")),
    }


@auth_router.post("/auth/request-reset-otp")
@limiter.limit("3/minute")
async def request_reset_otp(request: Request, data: OTPVerify):
    """Lupa password: kirim OTP reset ke email akun (audit G6 #1 — jalan
    buntu login). Respons SELALU generik agar keberadaan akun tidak bocor;
    OTP disimpan di namespace terpisah ("reset:") agar tak bentrok dengan
    registrasi pending."""
    email = data.email.strip().lower()
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Format email tidak valid")

    pesan_generik = ("Bila email terdaftar, kode OTP reset password telah "
                     "dikirim — periksa kotak masuk/spam.")
    user = await db.users.find_one({"username": email}, {"_id": 0, "id": 1, "name": 1})
    if not user:
        return {"message": pesan_generik, "otp_sent": True, "debug_otp": None}

    otp = generate_otp()
    await store_otp(f"reset:{email}", otp, {"email": email, "user_id": user["id"]})
    email_sent, _email_alasan = await send_otp_email(email, otp, user.get("name") or "")
    show_debug_otp = (not RESEND_API_KEY or not email_sent) and _debug_otp_allowed()
    return {"message": pesan_generik, "otp_sent": True,
            "debug_otp": otp if show_debug_otp else None}


@auth_router.post("/auth/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, data: dict):
    """Lupa password langkah 2: verifikasi OTP reset + setel password baru."""
    email = str(data.get("email") or "").strip().lower()
    otp = str(data.get("otp") or "").strip()
    baru = str(data.get("new_password") or "")
    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email & kode OTP wajib diisi")
    if len(baru) < 8:
        raise HTTPException(status_code=400, detail="Password baru minimal 8 karakter")

    stored = await get_otp(f"reset:{email}")
    if not stored:
        raise HTTPException(status_code=400,
                            detail="OTP tidak ditemukan atau kadaluarsa — minta OTP baru")
    # Banding konstan-waktu + kunci brute-force (invalidasi OTP setelah N gagal).
    # Bandingkan sebagai bytes agar input non-ASCII tak memicu TypeError → 500.
    if not hmac.compare_digest(str(stored.get("otp") or "").encode("utf-8"),
                               str(otp).encode("utf-8")):
        terkunci = await catat_gagal_otp(f"reset:{email}")
        raise HTTPException(
            status_code=400,
            detail=("Terlalu banyak percobaan salah — OTP dinonaktifkan, minta OTP baru"
                    if terkunci else "Kode OTP salah"))

    from auth_utils import hash_password
    # Naikkan sesi_epoch (AUTH-C): seluruh token lama (akses & media) langsung
    # gugur setelah reset password — perangkat yang mungkin dikuasai penyerang
    # kehilangan akses.
    res = await db.users.update_one(
        {"username": email},
        {"$set": {"password": hash_password(baru)}, "$inc": {"sesi_epoch": 1}})
    await delete_otp(f"reset:{email}")
    if res.matched_count == 0:
        raise HTTPException(status_code=400, detail="Akun tidak ditemukan")
    return {"message": "Password berhasil direset — silakan masuk dengan password baru"}


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

    # Banding konstan-waktu + kunci brute-force (invalidasi OTP setelah N gagal).
    # Bandingkan sebagai bytes agar input non-ASCII tak memicu TypeError → 500.
    if not hmac.compare_digest(str(stored.get("otp") or "").encode("utf-8"),
                               str(otp).encode("utf-8")):
        terkunci = await catat_gagal_otp(email)
        raise HTTPException(
            status_code=400,
            detail=("Terlalu banyak percobaan salah — OTP dinonaktifkan, minta OTP baru"
                    if terkunci else "Kode OTP salah"))

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

# Kunci brute-force login: setelah MAKS_GAGAL_LOGIN gagal beruntun, akun
# dikunci sementara KUNCI_MENIT menit (auto-buka). Pelengkap rate-limit per-IP
# (10/menit) untuk menahan credential-stuffing terdistribusi. Kunci auto-expire
# agar tak jadi DoS permanen; penghitung di-reset saat login sukses.
MAKS_GAGAL_LOGIN = 10
KUNCI_MENIT = 15


@auth_router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin):
    """Login user and return JWT token"""
    user = await db.users.find_one({"username": credentials.username}, {"_id": 0})
    if not user:
        # User tak ada: tetap jalankan bcrypt (hash boneka) agar waktu respons
        # setara kasus user ada — tanpa ini timing membocorkan username valid.
        verify_password_dummy(credentials.password)
        raise HTTPException(status_code=401, detail="Username atau password salah")

    # Akun terkunci sementara karena terlalu banyak percobaan gagal?
    terkunci_hingga = user.get("login_terkunci_hingga")
    if terkunci_hingga:
        try:
            dt = datetime.fromisoformat(terkunci_hingga)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            sekarang = datetime.now(timezone.utc)
            if dt > sekarang:
                sisa = int((dt - sekarang).total_seconds() // 60) + 1
                raise HTTPException(
                    status_code=429,
                    detail=(f"Akun terkunci sementara karena terlalu banyak percobaan "
                            f"gagal. Coba lagi dalam ~{sisa} menit."))
        except (ValueError, OverflowError):
            pass  # nilai rusak → abaikan kunci, jangan sampai 500

    if not verify_password(credentials.password, user["password"]):
        # Naikkan penghitung gagal; kunci akun bila melewati ambang.
        gagal = int(user.get("login_gagal") or 0) + 1
        set_fields = {"login_gagal": gagal}
        if gagal >= MAKS_GAGAL_LOGIN:
            set_fields["login_terkunci_hingga"] = (
                datetime.now(timezone.utc) + timedelta(minutes=KUNCI_MENIT)).isoformat()
            set_fields["login_gagal"] = 0  # reset setelah dikunci
        await db.users.update_one({"id": user["id"]}, {"$set": set_fields})
        raise HTTPException(status_code=401, detail="Username atau password salah")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun Anda telah dinonaktifkan. Hubungi administrator.")

    # Sertakan sesi_epoch user pada token (AUTH-C): reset/ubah password akan
    # menaikkan epoch → token yang diterbitkan kini otomatis gugur.
    sesi_epoch = int(user.get("sesi_epoch") or 0)
    token = create_token(user["id"], user["username"], sesi_epoch)

    # Login sukses: perbarui last_active + reset penghitung/kunci gagal.
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_active": datetime.now(timezone.utc).isoformat(), "login_gagal": 0},
         "$unset": {"login_terkunci_hingga": ""}})
    
    # Normalize legacy role: "user" -> "operator"
    user_role = user.get("role", "operator")
    if user_role == "user":
        user_role = "operator"
    
    return TokenResponse(
        access_token=token,
        media_token=create_media_token(user["id"], user["username"], sesi_epoch),
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


