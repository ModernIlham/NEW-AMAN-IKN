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


# Hash bcrypt "boneka" untuk MENYETARAKAN WAKTU RESPONS login saat username
# TIDAK ditemukan. Tanpa ini, permintaan dengan username tak-ada kembali jauh
# lebih cepat (tak menjalankan bcrypt) daripada username ada → penyerang bisa
# membedakan akun yang ADA vs TIDAK hanya dari waktu respons (enumerasi user).
# Dihitung sekali saat impor; cost factor sama dengan hash_password (gensalt
# default) agar durasinya setara.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"aman-timing-equalizer", bcrypt.gensalt())


def verify_password_dummy(plain_password: str) -> bool:
    """Jalankan bcrypt terhadap hash boneka lalu buang hasilnya — dipakai pada
    jalur login ketika user TIDAK ditemukan, agar waktu respons setara dengan
    kasus user ada (anti-enumerasi via timing). SELALU mengembalikan False."""
    try:
        bcrypt.checkpw(str(plain_password or "").encode("utf-8"), _DUMMY_PASSWORD_HASH)
    except Exception:
        pass
    return False

def create_token(user_id: str, username: str, sesi_epoch: int = 0) -> str:
    # `sesi_epoch` (AUTH-C): dinaikkan tiap reset/ubah password → token dengan
    # epoch lama otomatis dicabut di _decode_bearer. Login membaca nilai terbaru
    # dari dokumen user; default 0 untuk pemanggil lama/bootstrap.
    payload = {
        "user_id": user_id,
        "username": username,
        "sesi_epoch": int(sesi_epoch or 0),
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


def create_media_token(user_id: str, username: str, sesi_epoch: int = 0) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "scope": "media",
        "sesi_epoch": int(sesi_epoch or 0),  # ikut dicabut saat reset password (AUTH-C)
        "exp": datetime.now(timezone.utc).timestamp() + (MEDIA_TOKEN_EXPIRATION_DAYS * 86400),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# Token BERKAS EKSPOR (scope="docfile", umur 7 hari): DITANAM ke tautan
# doc-file di dalam CSV/XLSX hasil ekspor, karena berkas itu dibuka belakangan
# dari spreadsheet (tak ada header Authorization di sana).
#
# Sengaja BUKAN token media (REVIEW-9 R10): token media berumur 30 hari DAN
# diterima ~30 endpoint (assets, bast, pengesahan, ttd, persediaan, jobs, …),
# jadi menanamnya ke berkas yang rutin dikirim ke KPKNL/auditor sama dengan
# membagikan kredensial baca umum atas nama pengekspor. Token ini dipersempit
# ke SATU rute (doc-file) dan diperpendek jadi 7 hari; pencabutan tetap ikut
# `sesi_epoch` (reset password mencabutnya).
DOCFILE_TOKEN_EXPIRATION_DAYS = 7


def create_docfile_token(user_id: str, username: str, sesi_epoch: int = 0) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "scope": "docfile",
        "sesi_epoch": int(sesi_epoch or 0),
        "exp": datetime.now(timezone.utc).timestamp() + (DOCFILE_TOKEN_EXPIRATION_DAYS * 86400),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_user_docfile(
    authorization: str = Header(default="", alias="Authorization"),
    token: str = Query(default=""),
) -> dict:
    """Gate rute doc-file: Bearer biasa, token media, ATAU token scope
    "docfile" yang ditanam di tautan ekspor. Guard satker tetap ditegakkan
    pemanggil lewat `pastikan_akses_aset`."""
    if authorization and authorization.startswith("Bearer "):
        return await _decode_bearer(authorization, allow_media_scope=True)
    if not token:
        raise HTTPException(status_code=401, detail="Autentikasi diperlukan")
    return await _decode_bearer(f"Bearer {token}", allow_media_scope=True,
                                allow_docfile_scope=True)


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
    Bearer; ?token= bertipe sign tetap DICOBA bila Bearer gagal — tamu yang
    membawa token sesi BASI di localStorage (interceptor global memasangnya
    otomatis) tidak boleh terkunci padahal link e-sign-nya valid."""
    bearer_err = None
    if authorization and authorization.startswith("Bearer "):
        try:
            return await _decode_bearer(authorization)
        except HTTPException as e:
            bearer_err = e
    try:
        tok = await require_sign_token(token)
    except HTTPException:
        raise bearer_err or HTTPException(status_code=401,
                                          detail="Autentikasi diperlukan")
    return {"guest": True, "sign": tok, "username": "tamu-ttd", "role": "tamu"}


# --- Token PETA KOLABORATIF (link publik peta) -----------------------------
# Mirror token e-sign, tipe "peta". BEDA penting: masa tayang NYATA disimpan di
# DB (peta_shares.berlaku_sampai) — token diberi exp longgar (plafon) agar link
# yang sudah tersebar tetap berlaku saat masa tayang DIPERPANJANG (cukup ubah
# field DB, tanpa mint ulang). Kedaluwarsa/pembatalan ditegakkan di route.
MAP_TOKEN_EXPIRATION_DAYS = 400


def create_map_token(share_id: str, jti: str) -> str:
    payload = {
        "typ": "peta", "share": share_id, "jti": jti,
        "exp": datetime.now(timezone.utc).timestamp() + MAP_TOKEN_EXPIRATION_DAYS * 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_map_token(token: str = Query(default="")) -> dict:
    """Validasi token peta kolaboratif (link publik). Kembalikan {share, jti}.
    Tidak lookup user (pengunjung tamu). Masa tayang & pembatalan dicek route."""
    if not token:
        raise HTTPException(status_code=401, detail="Token peta wajib")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Link peta kedaluwarsa")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Link peta tidak valid")
    if payload.get("typ") != "peta":
        raise HTTPException(status_code=401, detail="Token bukan untuk peta")
    return {"share": payload.get("share"), "jti": payload.get("jti")}


async def require_user_or_map_token(
    authorization: str = Header(default="", alias="Authorization"),
    token: str = Query(default=""),
) -> dict:
    """Gate peta kolaboratif: user login (Bearer) MAUPUN pengunjung tamu
    (?token= tipe peta). Bearer diprioritaskan; token sesi BASI yang terpasang
    otomatis tak boleh mengunci tamu berlink valid (sama pola e-sign)."""
    bearer_err = None
    if authorization and authorization.startswith("Bearer "):
        try:
            return await _decode_bearer(authorization)
        except HTTPException as e:
            bearer_err = e
    try:
        tok = await require_map_token(token)
    except HTTPException:
        raise bearer_err or HTTPException(status_code=401,
                                          detail="Autentikasi diperlukan")
    return {"guest": True, "peta": tok, "username": "tamu-peta", "role": "tamu"}


# Kunci EFEMERAL yang HANYA sah diset di dalam request (oleh
# _terapkan_satker_aktif) — bukan dari dokumen user di DB.
_KUNCI_EFEMERAL = ("_super_admin_asli", "_satker_aktif", "_kode_satker_asli")


def _buang_efemeral(user: dict) -> dict:
    """Buang kunci efemeral dari dokumen user yang baru dibaca dari DB, supaya
    `_super_admin_asli` dsb. tak bisa diselundupkan lewat data tersimpan."""
    for k in _KUNCI_EFEMERAL:
        user.pop(k, None)
    return user


async def _decode_bearer(authorization: str, allow_media_scope: bool = False,
                         allow_docfile_scope: bool = False) -> dict:
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
    # Token "docfile" ditanam di tautan CSV/XLSX yang beredar luas — hanya sah
    # untuk rute doc-file, tidak untuk endpoint lain (REVIEW-9 R10).
    if payload.get("scope") == "docfile" and not allow_docfile_scope:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Hash bcrypt disimpan di field `password` — WAJIB dikecualikan agar tak
    # bocor ke klien lewat dokumen user yang dikembalikan require_user/admin.
    # (`password_hash` disertakan utk keamanan bila ada data lama.)
    user = await db.users.find_one({"id": payload.get("user_id")}, {"_id": 0, "password": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Field EFEMERAL "Satker Aktif" hanya boleh diset DALAM request oleh
    # `_terapkan_satker_aktif` — jangan pernah dipercaya dari dokumen DB
    # (backdoor via restore backup pihak luar; temuan tinjauan).
    _buang_efemeral(user)
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun Anda telah dinonaktifkan. Hubungi administrator.")
    # Revokasi sesi (AUTH-C): token membawa `sesi_epoch`. Bila lebih kecil dari
    # epoch user (dinaikkan tiap reset/ubah password), token itu sudah DICABUT →
    # tolak. Token lama TANPA klaim dianggap epoch 0 (kompatibel mundur): user
    # yang belum pernah reset (epoch 0) tetap diterima; yang sudah reset (≥1)
    # otomatis menolak semua token lama.
    try:
        user_epoch = int(user.get("sesi_epoch") or 0)
    except (TypeError, ValueError):
        user_epoch = 0  # nilai rusak (mis. dari restore lama) → jangan 500
    try:
        tok_epoch = int(payload.get("sesi_epoch") or 0)
    except (TypeError, ValueError):
        tok_epoch = 0
    if tok_epoch < user_epoch:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir — silakan masuk kembali")
    return user


async def get_current_user(authorization: str):
    """Legacy positional helper. Prefer `require_user` for new code."""
    return await _decode_bearer(authorization)


async def _satker_terdaftar(kode: str) -> bool:
    """True bila `kode` terdaftar di Master Satker. Diekstrak agar mudah
    di-mock pada pengujian (koleksi Motor sulit di-monkeypatch langsung)."""
    return bool(await db.satker.find_one({"kode_satker": kode}, {"_id": 1}))


async def _terapkan_satker_aktif(user: dict, x_satker_aktif: str) -> dict:
    """Terapkan "Satker Aktif" (act-as-satker) untuk SUPER-ADMIN.

    Bila pemanggil super-admin PUSAT (kode_satker kosong) mengirim header
    `X-Satker-Aktif: <kode>` yang VALID (terdaftar di Master Satker), kita
    suntikkan kode itu ke dokumen user untuk request ini. Dampaknya:
    `kode_satker_user` mengembalikan kode itu → SELURUH mesin isolasi yang ada
    (`scope_query_field_satker`, `scope_query_aset`, `pastikan_akses_*`, dan
    stempel `kode_satker` saat INSERT) otomatis berperilaku sebagai satker
    tersebut — TANPA menyentuh satu pun callsite. Identitas otoritas tetap
    super-admin lewat `_super_admin_asli` (lihat is_super_admin).

    KEAMANAN: header ini DIABAIKAN untuk user yang sudah terikat satker — ia
    tak boleh berpura-pura jadi satker lain. Kode yang tak terdaftar juga
    diabaikan (jatuh ke perilaku lintas-satker biasa), bukan ditolak, agar
    header basi tak mengunci aplikasi.
    """
    kode = str(x_satker_aktif or "").strip()
    # Hanya super-admin PUSAT (belum tersuntik) yang boleh act-as.
    asli_super = (user.get("role") == "admin"
                  and not str(user.get("kode_satker") or "").strip())
    if not kode or not asli_super:
        return user
    if not await _satker_terdaftar(kode):
        return user
    user["_super_admin_asli"] = True   # otoritas TETAP super-admin
    user["_kode_satker_asli"] = ""
    user["_satker_aktif"] = kode
    user["kode_satker"] = kode         # scoping & stempel ikut satker ini
    return user


async def require_user(
    authorization: str = Header(default="", alias="Authorization"),
    x_satker_aktif: str = Header(default="", alias="X-Satker-Aktif"),
) -> dict:
    """FastAPI Depends-friendly auth gate.

    Usage:
        @router.get("/foo")
        async def foo(user: dict = Depends(require_user)): ...

    Returns the user document (without `password_hash`). Raises 401 / 403.
    Menerapkan "Satker Aktif" untuk super-admin (lihat _terapkan_satker_aktif).
    """
    user = await _decode_bearer(authorization)
    return await _terapkan_satker_aktif(user, x_satker_aktif)


async def require_admin(user: dict = Depends(require_user)) -> dict:
    """Layer on top of require_user that enforces role == 'admin'."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat melakukan aksi ini")
    return user


def is_super_admin(user: dict) -> bool:
    """SUPER-ADMIN = admin PUSAT lintas-satker: role 'admin' DAN `kode_satker`
    KOSONG. Bedanya dengan admin biasa:
      - Admin satker (role 'admin' + kode_satker terisi): mengelola HANYA
        satkernya (data ter-isolasi M-SCOPE).
      - Super-admin (role 'admin' + kode_satker ''): lintas-satker, memegang
        operasi SELURUH-DB (backup / restore / reset sistem).
    Model ini (lihat users.py) sengaja memakai kode_satker kosong sebagai
    penanda super-admin, bukan role kelima.

    SATKER AKTIF (act-as): saat super-admin memilih "Satker Aktif", kita
    menyuntikkan kode itu ke `user["kode_satker"]` supaya SELURUH scoping &
    stempel berperilaku sebagai satker tersebut. Namun OTORITAS-nya tetap
    super-admin — jadi bila penanda `_super_admin_asli` ada, itulah yang
    dipakai (mencegah super-admin terkunci dari backup/restore/kelola satker
    hanya karena sedang bertindak sebagai satu satker)."""
    if "_super_admin_asli" in user:
        return bool(user["_super_admin_asli"])
    return (user.get("role") == "admin"
            and not str(user.get("kode_satker") or "").strip())


async def require_super_admin(user: dict = Depends(require_user)) -> dict:
    """Gate SUPER-ADMIN pusat (lintas-satker) untuk operasi seluruh-DB yang
    menyentuh SEMUA satker (backup / restore / reset). Admin yang terikat satu
    satker ditolak 403 — mereka tak boleh mengunduh/menimpa/menghapus data
    satker lain."""
    if not is_super_admin(user):
        raise HTTPException(
            status_code=403,
            detail=("Khusus super-admin pusat (admin lintas-satker). Admin satker "
                    "tidak dapat mengakses backup/restore/reset seluruh sistem."))
    return user


def pastikan_kelola_akun(admin: dict, target: dict) -> None:
    """403 bila admin SATKER mengelola akun di luar satkernya.

    `require_admin` hanya memeriksa role, sehingga admin satker A lolos ke
    seluruh endpoint /users — tanpa guard ini ia dapat mereset password,
    menghapus, atau mengubah role akun satker B (pengambilalihan lintas
    satker). Super-admin (kode_satker kosong) tetap lintas-satker.

    Aturan (urut):
      1. Super-admin pusat → boleh atas semua akun.
      2. Target super-admin (role admin + TANPA ikatan satker) → SELALU 403.
         Berbeda dari dokumen, di mana kode_satker kosong berarti "era lama,
         terbuka": pada AKUN, kosong + role admin berarti akun PUSAT — justru
         yang paling harus dilindungi (termasuk akun bootstrap pertama).
      3. Target BELUM terikat satker (pendaftaran baru, non-admin) → boleh.
         Registrasi mandiri selalu menghasilkan akun nonaktif tanpa ikatan,
         jadi admin satker tetap dapat mengaktifkan lalu mengikatnya ke
         satkernya sendiri. Akun ini belum memegang data satker mana pun.
      4. Selain itu, ikatan satker harus cocok PERSIS.

    KEAMANAN (temuan tinjauan): `target` selalu dokumen DB MENTAH. Bila dokumen
    itu menyelundupkan `_super_admin_asli` (mis. hasil restore backup pihak
    luar), tanpa dibersihkan ia bisa membalik hasil `is_super_admin(target)` di
    bawah — melewati proteksi "akun pusat hanya dikelola super-admin". Buang
    field efemeral dari target lebih dulu. `admin` (pemanggil) JANGAN dibuang:
    penandanya SAH bila sedang act-as (sudah discrub di _decode_bearer).
    """
    if target:
        _buang_efemeral(target)
    if is_super_admin(admin):
        return
    kode = str((admin or {}).get("kode_satker") or "").strip()
    milik = str((target or {}).get("kode_satker") or "").strip()
    if not kode:
        raise HTTPException(
            status_code=403, detail="Akun Anda tidak terikat satker mana pun")
    if is_super_admin(target or {}):
        raise HTTPException(
            status_code=403,
            detail="Akun super-admin pusat hanya dapat dikelola super-admin")
    if milik and milik != kode:
        raise HTTPException(
            status_code=403,
            detail=("Akun ini milik satker " + milik + " — akun Anda terikat "
                    "satker " + kode))


async def require_writer(user: dict = Depends(require_user)) -> dict:
    """Gate endpoint TULIS: tolak role 'viewer' (read-only kini ditegakkan di
    SERVER, bukan hanya disembunyikan UI). Role legacy 'user' = operator;
    role tak dikenal diperlakukan sebagai operator (kompatibilitas akun lama
    tanpa field role)."""
    role = user.get("role") or "operator"
    if role == "user":  # legacy
        role = "operator"
    if role == "viewer":
        raise HTTPException(
            status_code=403,
            detail="Akun viewer hanya dapat membaca data — hubungi admin untuk akses tulis")
    return user


async def require_user_or_query_token(
    authorization: str = Header(default="", alias="Authorization"),
    token: str = Query(default=""),
    x_satker_aktif: str = Header(default="", alias="X-Satker-Aktif"),
    sa: str = Query(default=""),
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
    _kode_aktif = x_satker_aktif or sa
    if authorization and authorization.startswith("Bearer "):
        _u = await _decode_bearer(authorization, allow_media_scope=True)
        return await _terapkan_satker_aktif(_u, _kode_aktif)
    if token:
        _u = await _decode_bearer(f"Bearer {token}", allow_media_scope=True)
        return await _terapkan_satker_aktif(_u, _kode_aktif)
    raise HTTPException(status_code=401, detail="Autentikasi diperlukan")

