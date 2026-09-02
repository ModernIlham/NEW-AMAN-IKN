"""Authentication routes: register, login, OTP, heartbeat."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Header
from pymongo.errors import DuplicateKeyError

from db import db
from models import UserCreate, UserLogin, UserResponse, TokenResponse, OTPRequest, OTPVerify
from preferensi_kamera import normalkan as normalkan_preferensi_kamera
from auth_utils import hash_password, verify_password, verify_password_dummy, create_token, create_media_token, get_current_user
from bootstrap_state import (COLLECTION_NAME as BOOTSTRAP_STATE_COLLECTION,
                             STATE_ID as BOOTSTRAP_STATE_ID)
import hmac

from shared_utils import limiter, generate_otp, send_otp_email, store_otp, get_otp, delete_otp, catat_gagal_otp, RESEND_API_KEY, SENDER_EMAIL

logger = logging.getLogger(__name__)
auth_router = APIRouter()


BOOTSTRAP_TOKEN_ENV = "ADMIN_BOOTSTRAP_TOKEN"
MIN_BOOTSTRAP_TOKEN_LENGTH = 32


async def _pastikan_admin_aktif_tersedia() -> None:
    """Tolak pendaftaran publik bila belum ada admin yang dapat mengaktifkan.

    Sebelumnya siapa pun yang paling cepat mendaftar pada database kosong
    otomatis menjadi admin pusat. Selain eskalasi hak publik, pola
    ``count_documents({}) == 0`` juga rentan balapan: dua request dapat sama-
    sama membaca nol sebelum salah satunya menulis.

    Instalasi kosong sekarang harus dipasang lewat ``/auth/bootstrap``.
    ``is_active != False`` mempertahankan kompatibilitas admin lama yang belum
    memiliki field tersebut.
    """
    admin = await db.users.find_one(
        {"role": "admin", "$or": [
            {"is_active": True},
            {"is_active": {"$exists": False}},
        ]},
        {"_id": 1},
    )
    if not admin:
        raise HTTPException(
            status_code=503,
            detail=("Administrator awal belum dipasang. Hubungi pengelola "
                    "server untuk menjalankan bootstrap admin yang aman."),
        )


def _validasi_token_bootstrap(token: str) -> None:
    """Validasi secret bootstrap tanpa nilai bawaan dan secara konstan-waktu."""
    expected = str(os.environ.get(BOOTSTRAP_TOKEN_ENV) or "").strip()
    if len(expected) < MIN_BOOTSTRAP_TOKEN_LENGTH:
        logger.error(
            "%s belum diset atau kurang dari %d karakter; bootstrap ditutup",
            BOOTSTRAP_TOKEN_ENV, MIN_BOOTSTRAP_TOKEN_LENGTH,
        )
        raise HTTPException(
            status_code=503,
            detail="Bootstrap admin belum dikonfigurasi oleh pengelola server.",
        )
    supplied = str(token or "").strip()
    if not supplied or not hmac.compare_digest(
            supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403,
                            detail="Kredensial bootstrap tidak valid")


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


@auth_router.post("/auth/bootstrap")
@limiter.limit("3/minute")
async def bootstrap_admin(
    request: Request,
    user_data: UserCreate,
    x_admin_bootstrap_token: str = Header(
        default="", alias="X-Admin-Bootstrap-Token"),
):
    """Pasang SATU admin pusat awal memakai secret server sekali pakai.

    Endpoint hanya berguna pada database pengguna yang benar-benar kosong.
    Dokumen status ber-``_id`` konstan memanfaatkan indeks unik bawaan MongoDB
    sebagai CAS: dua request bersamaan tidak mungkin sama-sama menjadi admin
    awal, tanpa bergantung pada transaksi/replica set. Status berada di
    koleksi terpisah agar bootstrap tidak terbuka lagi bila users dihapus.
    """
    _validasi_token_bootstrap(x_admin_bootstrap_token)

    if await db.users.find_one({}, {"_id": 1}):
        # Backfill fail-closed untuk instalasi lama. Update ini idempoten dan
        # memastikan penghapusan akun di masa depan tidak membuka bootstrap.
        await db[BOOTSTRAP_STATE_COLLECTION].update_one(
            {"_id": BOOTSTRAP_STATE_ID},
            {"$setOnInsert": {
                "status": "closed",
                "reason": "existing_users",
                "closed_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        raise HTTPException(status_code=409,
                            detail="Bootstrap admin sudah ditutup")

    from auth_utils import periksa_kekuatan_password
    galat_pw = periksa_kekuatan_password(user_data.password)
    if galat_pw:
        raise HTTPException(status_code=400, detail=galat_pw)

    username = str(user_data.username or "").strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Email wajib diisi")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    claim_id = str(uuid.uuid4())
    try:
        await db[BOOTSTRAP_STATE_COLLECTION].insert_one({
            "_id": BOOTSTRAP_STATE_ID,
            "status": "claimed",
            "claim_id": claim_id,
            "claimed_at": now,
        })
    except DuplicateKeyError:
        raise HTTPException(status_code=409,
                            detail="Bootstrap admin sudah ditutup")

    user_doc = {
        "id": user_id,
        "username": username,
        "password": hash_password(user_data.password),
        "name": str(user_data.name or username).strip(),
        "role": "admin",
        "is_active": True,
        "bootstrap_admin": True,
        "created_at": now,
    }
    try:
        await db.users.insert_one(user_doc)
    except DuplicateKeyError:
        # Lepaskan hanya claim milik request ini. Bila user ternyata sudah
        # tersimpan tetapi respons Mongo tidak pasti, pemeriksaan users di
        # request berikutnya tetap menutup bootstrap secara fail-closed.
        await db[BOOTSTRAP_STATE_COLLECTION].delete_one({
            "_id": BOOTSTRAP_STATE_ID,
            "status": "claimed",
            "claim_id": claim_id,
        })
        raise HTTPException(status_code=409,
                            detail="Bootstrap admin sudah ditutup")

    await db[BOOTSTRAP_STATE_COLLECTION].update_one(
        {"_id": BOOTSTRAP_STATE_ID, "claim_id": claim_id},
        {"$set": {"status": "closed", "reason": "bootstrap_completed",
                  "closed_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"claim_id": "", "claimed_at": ""}},
    )

    token = create_token(user_id, username)
    logger.warning("Bootstrap admin awal berhasil dipasang: %s", username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": username,
            "name": user_doc["name"],
            "role": "admin",
            "is_active": True,
            "created_at": now,
        },
        "pending_approval": False,
        "message": ("Administrator awal berhasil dipasang. Hapus "
                    "ADMIN_BOOTSTRAP_TOKEN dari environment server lalu "
                    "restart backend."),
    }

@auth_router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate):
    """
    Register a new user (legacy endpoint - kept for backward compat).
    Semua pengguna dari jalur publik dibuat viewer nonaktif dan harus
    diaktifkan admin. Admin awal hanya dapat dibuat lewat /auth/bootstrap.
    """
    await _pastikan_admin_aktif_tersedia()
    username = str(user_data.username or "").strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Email wajib diisi")
    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah digunakan")

    from auth_utils import periksa_kekuatan_password
    galat_pw = periksa_kekuatan_password(user_data.password)
    if galat_pw:
        raise HTTPException(status_code=400, detail=galat_pw)

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "id": user_id,
        "username": username,
        "password": hash_password(user_data.password),
        "name": user_data.name or username,
        "role": "viewer",
        "is_active": False,
        "created_at": now
    }

    await db.users.insert_one(user_doc)

    # Regular user: pending admin approval, NO token issued.
    logger.info(f"New user registered (pending admin approval): {username}")
    return {
        "access_token": None,
        "user": {
            "id": user_id,
            "username": username,
            "name": user_doc["name"],
            "role": "viewer",
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
    await _pastikan_admin_aktif_tersedia()
    email = data.email.strip().lower()
    
    # Basic email validation
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Format email tidak valid")
    
    # Check if email already registered
    existing = await db.users.find_one({"username": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    
    # Syarat kata sandi ditegakkan di server (auth_utils), bukan hanya di layar.
    from auth_utils import periksa_kekuatan_password
    _galat_pw = periksa_kekuatan_password(data.password)
    if _galat_pw:
        raise HTTPException(status_code=400, detail=_galat_pw)
    
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
    email_sent, _email_alasan = await send_otp_email(
        email, otp, user.get("name") or "", jenis="otp_reset")
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
    # Syarat SAMA dengan pendaftaran (auth_utils) — dulu jalur ini hanya
    # menuntut 8 karakter sehingga akun bisa berakhir dengan kata sandi yang
    # justru akan ditolak saat mendaftar.
    from auth_utils import periksa_kekuatan_password
    _galat_baru = periksa_kekuatan_password(baru)
    if _galat_baru:
        raise HTTPException(status_code=400, detail=_galat_baru)

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
    # kehilangan akses. Baca epoch lalu $set (bukan $inc) agar nilai rusak
    # (mis. string dari restore lama) dinormalkan ke int — $inc pada tipe
    # non-numerik akan melempar WriteError (500) dan password gagal berubah.
    u = await db.users.find_one({"username": email}, {"_id": 0, "sesi_epoch": 1})
    try:
        epoch_baru = int((u or {}).get("sesi_epoch") or 0) + 1
    except (TypeError, ValueError):
        epoch_baru = 1
    res = await db.users.update_one(
        {"username": email},
        {"$set": {"password": hash_password(baru), "sesi_epoch": epoch_baru}})
    await delete_otp(f"reset:{email}")
    if res.matched_count == 0:
        raise HTTPException(status_code=400, detail="Akun tidak ditemukan")
    return {"message": "Password berhasil direset — silakan masuk dengan password baru"}


@auth_router.post("/auth/verify-otp")
@limiter.limit("5/minute")
async def verify_otp(request: Request, data: OTPVerify):
    """
    Verify OTP and complete user registration.
    Semua pengguna hasil OTP dibuat viewer nonaktif. Instalasi kosong wajib
    memasang admin awal lewat /auth/bootstrap terlebih dahulu.
    """
    await _pastikan_admin_aktif_tersedia()
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

    user_doc = {
        "id": user_id,
        "username": email,
        "password": hash_password(user_data["password"]),
        "name": user_data["name"],
        "role": "viewer",
        "is_active": False,
        "email_verified": True,
        "created_at": now
    }

    await db.users.insert_one(user_doc)

    # Clear OTP from store
    await delete_otp(email)

    # Regular user: pending admin approval, NO token issued.
    logger.info(f"New user registered via OTP (pending admin approval): {email}")
    return {
        "access_token": None,
        "user": {
            "id": user_id,
            "username": email,
            "name": user_doc["name"],
            "role": "viewer",
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
    username_input = str(credentials.username or "").strip()
    user = await db.users.find_one({"username": username_input}, {"_id": 0})
    username_normalized = username_input.lower()
    if not user and username_normalized != username_input:
        # Akun baru selalu disimpan lowercase. Lookup mentah tetap didahulukan
        # agar akun legacy bercasing campuran tidak kehilangan akses.
        user = await db.users.find_one(
            {"username": username_normalized}, {"_id": 0})
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
    # menaikkan epoch → token yang diterbitkan kini otomatis gugur. Guard nilai
    # rusak (samakan dengan _decode_bearer) agar user dengan epoch korup tak
    # justru 500 saat login (tak bisa dapat sesi baru).
    try:
        sesi_epoch = int(user.get("sesi_epoch") or 0)
    except (TypeError, ValueError):
        sesi_epoch = 0
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

# ── PREFERENSI KAMERA (melekat pada AKUN, bukan perangkat) ─────────────────
# Dipisah dari UserResponse: ini setelan alat kerja, bukan identitas — dan
# dibaca/ditulis jauh lebih sering daripada profil.

@auth_router.get("/auth/preferensi-kamera")
async def get_preferensi_kamera(authorization: str = Header(None)):
    """Setelan kamera milik akun ini (orientasi stempel, resolusi, kualitas).

    Selalu mengembalikan nilai yang SAH — akun yang belum pernah menyetel
    menerima bawaan, jadi layar tak perlu menangani keadaan 'belum ada'.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    user = await get_current_user(authorization)
    return normalkan_preferensi_kamera(user.get("preferensi_kamera"))


@auth_router.put("/auth/preferensi-kamera")
async def set_preferensi_kamera(payload: dict, authorization: str = Header(None)):
    """Simpan setelan kamera akun ini. Nilai dinormalkan DI SERVER agar isi
    basis data tetap masuk akal walau permintaannya datang dari klien lama."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    user = await get_current_user(authorization)
    bersih = normalkan_preferensi_kamera(payload)
    await db.users.update_one({"id": user["id"]}, {"$set": {"preferensi_kamera": bersih}})
    return bersih


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


