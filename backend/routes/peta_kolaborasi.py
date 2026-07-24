"""Peta Kolaboratif — berbagi peta aset kegiatan via link publik.

Operator/admin membagikan peta 1 kegiatan lewat link ber-token dengan MASA
TAYANG. Selama aktif, siapa pun yang punya link dapat: melihat titik aset,
berkomentar di tiap titik, dan menambah titik + komentar sendiri (kolaboratif;
tamu cukup mengisi nama). Masa tayang dapat DIPERPANJANG. Setelah kedaluwarsa,
link hanya bisa dibuka oleh operator/admin satker + kegiatan terkait (untuk
melihat/mengarsipkan & memperpanjang).

Desain token: masa tayang NYATA di DB (`peta_shares.berlaku_sampai`), token
diberi exp longgar (plafon) — perpanjang cukup ubah field DB tanpa mematikan
link yang sudah tersebar. Pembatalan = `status="batal"`. Isolasi M-SCOPE:
share distempel `kode_satker` kegiatan; hanya satker itu (super-admin lolos)
yang boleh mengelola & membuka pasca-kedaluwarsa.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from auth_utils import (
    require_user, require_writer, create_map_token, require_map_token,
    require_user_or_map_token, MAP_TOKEN_EXPIRATION_DAYS,
)
from db import db
from shared_utils import (
    limiter, log_audit, scope_query_field_satker, pastikan_akses_dok_satker,
)

peta_kolaborasi_router = APIRouter()

_PROJ = {"_id": 0}
_DEFAULT_JAM = 72          # masa tayang default 3 hari
DEFAULT_MAKS_TITIK = 120
DEFAULT_MAKS_TEKS = 1000


def _basis_url_publik() -> str:
    """URL publik aplikasi (untuk membangun link) — APP_PUBLIC_URL, lalu origin
    non-localhost pertama dari ALLOWED_ORIGINS/CORS_ORIGINS. '' = link relatif."""
    u = str(os.environ.get("APP_PUBLIC_URL", "")).strip().rstrip("/")
    if u:
        return u
    for var in ("ALLOWED_ORIGINS", "CORS_ORIGINS"):
        for o in str(os.environ.get(var, "")).split(","):
            o = o.strip().rstrip("/")
            if o and "localhost" not in o and "127.0.0.1" not in o:
                return o
    return ""


def _link_peta(share_id: str, token: str) -> str:
    return f"{_basis_url_publik()}/peta/kolaborasi/{share_id}?token={token}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_coord(v) -> Optional[float]:
    """Koordinat aset tersimpan STRING (bisa desimal koma) — kembalikan float
    berhingga atau None."""
    if v is None:
        return None
    try:
        import math
        f = float(str(v).strip().replace(",", "."))
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def _hitung_berlaku(durasi_jam, berlaku_sampai_str, base: datetime) -> str:
    """Tentukan ISO masa tayang: berlaku_sampai eksplisit > durasi_jam > default.
    Dijepit ke plafon token (MAP_TOKEN_EXPIRATION_DAYS) & minimal 1 jam."""
    maks = base + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)
    dt = None
    if berlaku_sampai_str:
        try:
            dt = datetime.fromisoformat(str(berlaku_sampai_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            dt = None
    if dt is None and durasi_jam is not None:
        try:
            jam = max(1, min(int(durasi_jam), MAP_TOKEN_EXPIRATION_DAYS * 24))
            dt = base + timedelta(hours=jam)
        except (ValueError, TypeError):
            dt = None
    if dt is None:
        dt = base + timedelta(hours=_DEFAULT_JAM)
    if dt > maks:
        dt = maks
    if dt <= base:
        dt = base + timedelta(hours=1)
    return dt.isoformat()


def _kedaluwarsa(share: dict) -> bool:
    bs = str(share.get("berlaku_sampai") or "")
    return bool(bs) and bs < _now().isoformat()


def _operator_satker(share: dict, ctx: dict) -> bool:
    """True bila konteks = user login operator/admin satker kegiatan share
    (super-admin kode_satker kosong lolos). Tamu & viewer → False."""
    if ctx.get("guest"):
        return False
    role = ctx.get("role") or "operator"
    if role == "user":
        role = "operator"
    if role == "viewer":
        return False
    uk = str(ctx.get("kode_satker") or "").strip()
    sk = str(share.get("kode_satker") or "").strip()
    return not (uk and sk and uk != sk)


def _akses_peta(share: dict, ctx: dict, punya_link: bool):
    """(boleh_lihat, boleh_kontribusi, alasan). `punya_link` = permintaan
    membawa token peta VALID untuk share ini (pemegang link publik)."""
    if share.get("status") == "batal":
        return False, False, "Link peta telah dibatalkan pembagi."
    op = _operator_satker(share, ctx)
    if not _kedaluwarsa(share):
        # Masa tayang aktif: pemegang link (tamu/user) ATAU operator/admin
        # satker (buka dari aplikasi) → lihat + kontribusi.
        if punya_link or op:
            return True, True, ""
        return False, False, "Link peta tidak valid untuk sesi ini."
    # Kedaluwarsa: hanya operator/admin satker terkait (arsip; kontribusi butuh
    # perpanjang). Pemegang link biasa & satker lain ditolak.
    if op:
        return True, False, ""
    return (False, False,
            "Masa tayang peta telah berakhir. Hanya operator/admin satker "
            "terkait yang dapat membukanya — silakan minta diperpanjang.")


async def _punya_link(share: dict, request: Request) -> bool:
    """Verifikasi permintaan membawa ?token= peta VALID untuk share ini (tipe
    peta, share cocok, jti cocok = belum di-rotasi/dibatalkan)."""
    tok = request.query_params.get("token") or ""
    if not tok:
        return False
    try:
        t = await require_map_token(token=tok)
    except HTTPException:
        return False
    return (t.get("share") == share.get("id")
            and str(t.get("jti") or "") == str(share.get("jti") or ""))


async def _muat_share(share_id: str) -> dict:
    sh = await db.peta_shares.find_one({"id": share_id}, _PROJ)
    if not sh:
        raise HTTPException(status_code=404, detail="Peta bagikan tidak ditemukan")
    return sh


def _verifikasi_token_share(share: dict, ctx: dict):
    """Untuk pengunjung tamu: token HARUS untuk share ini & jti cocok (deteksi
    link lama yang dibatalkan/di-rotasi)."""
    if not ctx.get("guest"):
        return
    tok = ctx.get("peta") or {}
    if tok.get("share") != share.get("id"):
        raise HTTPException(status_code=401, detail="Token tidak cocok peta ini")
    if str(tok.get("jti") or "") != str(share.get("jti") or ""):
        raise HTTPException(status_code=401,
                            detail="Link ini sudah tidak berlaku (diterbitkan ulang/dibatalkan)")


def _pengontribusi(ctx: dict, oleh_input: str):
    """Identitas kontributor: user login pakai namanya; tamu isi nama sendiri."""
    if ctx.get("guest"):
        nama = str(oleh_input or "").strip()[:60] or "Tamu"
        return nama, "tamu", ""
    nama = str(ctx.get("name") or ctx.get("username") or "Pengguna").strip()[:60]
    return nama, "pengguna", str(ctx.get("id") or "")


# ── Model input ────────────────────────────────────────────────────────────
class ShareIn(BaseModel):
    activity_id: str
    judul: Optional[str] = ""
    durasi_jam: Optional[int] = None
    berlaku_sampai: Optional[str] = None
    izinkan_titik_publik: bool = True
    izinkan_komentar_publik: bool = True


class PerpanjangIn(BaseModel):
    durasi_jam: Optional[int] = None
    berlaku_sampai: Optional[str] = None
    izinkan_titik_publik: Optional[bool] = None
    izinkan_komentar_publik: Optional[bool] = None


class TitikIn(BaseModel):
    lat: float
    lng: float
    nama_titik: str
    keterangan: Optional[str] = ""
    oleh: Optional[str] = ""


class KomentarIn(BaseModel):
    target_jenis: str          # "aset" | "titik"
    target_id: str
    teks: str
    oleh: Optional[str] = ""


def _share_keluar(sh: dict) -> dict:
    """Bentuk aman untuk daftar/detail pengelola — tanpa jti (rahasia token)."""
    d = {k: v for k, v in sh.items() if k != "jti"}
    d["kedaluwarsa"] = _kedaluwarsa(sh)
    d["link"] = None  # link berisi token; hanya dikembalikan saat create/lihat-token
    return d


# ── Endpoint PENGELOLA (operator/admin, ter-scope satker) ──────────────────
@peta_kolaborasi_router.post("/peta/share")
async def buat_share(payload: ShareIn, user: dict = Depends(require_writer)):
    """Buat link peta kolaboratif untuk sebuah kegiatan (operator/admin)."""
    act = await db.inventory_activities.find_one(
        {"id": payload.activity_id}, {"_id": 0, "id": 1, "kode_satker": 1,
                                      "nama": 1, "nama_kegiatan": 1, "judul": 1})
    if not act:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    await pastikan_akses_dok_satker(user, act)  # 403 bila satker lain
    base = _now()
    jti = uuid.uuid4().hex
    share_id = str(uuid.uuid4())
    berlaku = _hitung_berlaku(payload.durasi_jam, payload.berlaku_sampai, base)
    nama_keg = (act.get("nama") or act.get("nama_kegiatan")
                or act.get("judul") or "")
    doc = {
        "id": share_id,
        "activity_id": payload.activity_id,
        "kode_satker": str(act.get("kode_satker") or ""),
        "nama_kegiatan": str(nama_keg),
        "judul": str(payload.judul or "").strip()[:140],
        "jti": jti,
        "berlaku_sampai": berlaku,
        "izinkan_titik_publik": bool(payload.izinkan_titik_publik),
        "izinkan_komentar_publik": bool(payload.izinkan_komentar_publik),
        "status": "aktif",
        "created_by": user.get("username", "system"),
        "created_at": base.isoformat(),
        "updated_at": base.isoformat(),
    }
    await db.peta_shares.insert_one(dict(doc))
    token = create_map_token(share_id, jti)
    await log_audit("buat_share_peta", payload.activity_id, share_id,
                    username=user.get("username", "system"),
                    detail=f"Bagikan peta kolaboratif (s.d. {berlaku[:16]})",
                    kode_satker=doc["kode_satker"])
    out = _share_keluar(doc)
    out["link"] = _link_peta(share_id, token)
    out["token"] = token
    return out


@peta_kolaborasi_router.get("/peta/share")
async def daftar_share(activity_id: str = Query(...),
                       user: dict = Depends(require_writer)):
    """Daftar link peta untuk sebuah kegiatan (ter-scope satker). Menyertakan
    link ber-token agar pengelola bisa menyalin/membagikan ulang."""
    q = scope_query_field_satker(user, {"activity_id": activity_id})
    items = await db.peta_shares.find(q, _PROJ).sort("created_at", -1).to_list(200)
    hasil = []
    for sh in items:
        d = _share_keluar(sh)
        if sh.get("status") != "batal":
            d["link"] = _link_peta(sh["id"], create_map_token(sh["id"], sh.get("jti", "")))
        # jumlah kontribusi (info ringkas)
        d["jumlah_kontribusi"] = await db.peta_kolaborasi.count_documents(
            {"share_id": sh["id"], "dihapus": {"$ne": True}})
        hasil.append(d)
    return {"items": hasil, "jumlah": len(hasil)}


@peta_kolaborasi_router.put("/peta/share/{share_id}/perpanjang")
async def perpanjang_share(share_id: str, payload: PerpanjangIn,
                           user: dict = Depends(require_writer)):
    """Perpanjang masa tayang (dari SEKARANG) + opsi izin — link lama tetap
    berlaku (jti tidak dirotasi)."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    now = _now()
    berlaku = _hitung_berlaku(payload.durasi_jam, payload.berlaku_sampai, now)
    setf = {"berlaku_sampai": berlaku, "status": "aktif",
            "updated_at": now.isoformat()}
    if payload.izinkan_titik_publik is not None:
        setf["izinkan_titik_publik"] = bool(payload.izinkan_titik_publik)
    if payload.izinkan_komentar_publik is not None:
        setf["izinkan_komentar_publik"] = bool(payload.izinkan_komentar_publik)
    await db.peta_shares.update_one({"id": share_id}, {"$set": setf})
    await log_audit("perpanjang_share_peta", sh.get("activity_id", ""), share_id,
                    username=user.get("username", "system"),
                    detail=f"Perpanjang masa tayang peta s.d. {berlaku[:16]}",
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True, "berlaku_sampai": berlaku}


@peta_kolaborasi_router.post("/peta/share/{share_id}/batal")
async def batal_share(share_id: str, user: dict = Depends(require_writer)):
    """Batalkan link (link mati untuk publik; operator/admin masih bisa lihat
    arsip kontribusi lewat aplikasi)."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    await db.peta_shares.update_one(
        {"id": share_id}, {"$set": {"status": "batal", "updated_at": _now().isoformat()}})
    await log_audit("batal_share_peta", sh.get("activity_id", ""), share_id,
                    username=user.get("username", "system"),
                    detail="Batalkan link peta kolaboratif",
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True}


@peta_kolaborasi_router.delete("/peta/kolaborasi/{share_id}/kontribusi/{kontrib_id}")
async def hapus_kontribusi(share_id: str, kontrib_id: str,
                           user: dict = Depends(require_writer)):
    """Moderasi: operator/admin satker terkait menghapus (soft) titik/komentar."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    res = await db.peta_kolaborasi.update_one(
        {"id": kontrib_id, "share_id": share_id},
        {"$set": {"dihapus": True, "dihapus_oleh": user.get("username", "system"),
                  "dihapus_pada": _now().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kontribusi tidak ditemukan")
    return {"ok": True}


# ── Endpoint PUBLIK / HIBRIDA (tamu via token ATAU user login) ─────────────
async def _titik_aset(share: dict) -> list:
    """Titik aset kegiatan (koordinat valid) — HANYA field aman untuk publik."""
    cur = db.assets.find(
        {"activity_id": share.get("activity_id"), "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "category": 1, "inventory_status": 1,
         "koordinat_latitude": 1, "koordinat_longitude": 1})
    out = []
    async for a in cur:
        lat = _parse_coord(a.get("koordinat_latitude"))
        lng = _parse_coord(a.get("koordinat_longitude"))
        if lat is None or lng is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        out.append({"id": a["id"], "lat": lat, "lng": lng,
                    "kode": a.get("asset_code") or "", "nup": a.get("NUP") or "",
                    "nama": a.get("asset_name") or "",
                    "kategori": a.get("category") or "",
                    "status": a.get("inventory_status") or ""})
    return out


@peta_kolaborasi_router.get("/peta/kolaborasi/{share_id}")
async def lihat_peta(share_id: str, request: Request,
                     ctx: dict = Depends(require_user_or_map_token)):
    """Data peta kolaboratif: titik aset + titik & komentar kolaboratif.
    Tamu (token) saat aktif; user login satker terkait juga pasca-kedaluwarsa."""
    sh = await _muat_share(share_id)
    _verifikasi_token_share(sh, ctx)
    punya_link = await _punya_link(sh, request)
    boleh_lihat, boleh_kontribusi, alasan = _akses_peta(sh, ctx, punya_link)
    if not boleh_lihat:
        raise HTTPException(status_code=403, detail=alasan)
    kontrib = await db.peta_kolaborasi.find(
        {"share_id": share_id, "dihapus": {"$ne": True}},
        {"_id": 0, "ip": 0, "oleh_user_id": 0}).sort("created_at", 1).to_list(5000)
    titik_kolaborasi = [k for k in kontrib if k.get("jenis") == "titik"]
    komentar = [k for k in kontrib if k.get("jenis") == "komentar"]
    return {
        "id": share_id,
        "judul": sh.get("judul") or "",
        "nama_kegiatan": sh.get("nama_kegiatan") or "",
        "berlaku_sampai": sh.get("berlaku_sampai") or "",
        "kedaluwarsa": _kedaluwarsa(sh),
        "boleh_kontribusi": boleh_kontribusi,
        "izinkan_titik_publik": bool(sh.get("izinkan_titik_publik", True)),
        "izinkan_komentar_publik": bool(sh.get("izinkan_komentar_publik", True)),
        "tamu": bool(ctx.get("guest")),
        "titik_aset": await _titik_aset(sh),
        "titik_kolaborasi": titik_kolaborasi,
        "komentar": komentar,
    }


async def _guard_kontribusi(sh: dict, ctx: dict, request: Request,
                            izin_field: str, aksi: str):
    """Validasi umum saat menulis (titik/komentar): akses + izin publik."""
    _verifikasi_token_share(sh, ctx)
    punya_link = await _punya_link(sh, request)
    _, boleh_kontribusi, alasan = _akses_peta(sh, ctx, punya_link)
    if not boleh_kontribusi:
        raise HTTPException(status_code=403,
                            detail=alasan or "Masa tayang berakhir — perpanjang untuk berkontribusi lagi.")
    # Tamu tunduk pada izin publik; user login selalu boleh.
    if ctx.get("guest") and not bool(sh.get(izin_field, True)):
        raise HTTPException(status_code=403,
                            detail=f"Pembagi menonaktifkan {aksi} publik untuk peta ini.")


@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/titik")
@limiter.limit("30/minute")
async def tambah_titik(share_id: str, payload: TitikIn, request: Request,
                       ctx: dict = Depends(require_user_or_map_token)):
    """Tambah titik kolaboratif (anotasi — BUKAN aset resmi)."""
    sh = await _muat_share(share_id)
    await _guard_kontribusi(sh, ctx, request, "izinkan_titik_publik", "penambahan titik")
    import math
    if not (math.isfinite(payload.lat) and math.isfinite(payload.lng)
            and -90 <= payload.lat <= 90 and -180 <= payload.lng <= 180):
        raise HTTPException(status_code=400, detail="Koordinat tidak valid")
    nama_titik = str(payload.nama_titik or "").strip()[:DEFAULT_MAKS_TITIK]
    if not nama_titik:
        raise HTTPException(status_code=400, detail="Nama titik wajib diisi")
    oleh, tipe, uid = _pengontribusi(ctx, payload.oleh)
    now = _now().isoformat()
    doc = {
        "id": str(uuid.uuid4()), "share_id": share_id, "jenis": "titik",
        "lat": float(payload.lat), "lng": float(payload.lng),
        "nama_titik": nama_titik,
        "keterangan": str(payload.keterangan or "").strip()[:DEFAULT_MAKS_TEKS],
        "oleh": oleh, "oleh_tipe": tipe, "oleh_user_id": uid,
        "ip": (request.client.host if request.client else ""),
        "created_at": now, "dihapus": False,
    }
    await db.peta_kolaborasi.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k not in ("ip", "oleh_user_id")}


@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/komentar")
@limiter.limit("40/minute")
async def tambah_komentar(share_id: str, payload: KomentarIn, request: Request,
                          ctx: dict = Depends(require_user_or_map_token)):
    """Tambah komentar pada titik aset atau titik kolaboratif."""
    sh = await _muat_share(share_id)
    await _guard_kontribusi(sh, ctx, request, "izinkan_komentar_publik", "komentar")
    if payload.target_jenis not in ("aset", "titik"):
        raise HTTPException(status_code=400, detail="target_jenis tidak dikenal")
    teks = str(payload.teks or "").strip()[:DEFAULT_MAKS_TEKS]
    if not teks:
        raise HTTPException(status_code=400, detail="Komentar tidak boleh kosong")
    tid = str(payload.target_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="Target komentar wajib")
    oleh, tipe, uid = _pengontribusi(ctx, payload.oleh)
    now = _now().isoformat()
    doc = {
        "id": str(uuid.uuid4()), "share_id": share_id, "jenis": "komentar",
        "target_jenis": payload.target_jenis, "target_id": tid, "teks": teks,
        "oleh": oleh, "oleh_tipe": tipe, "oleh_user_id": uid,
        "ip": (request.client.host if request.client else ""),
        "created_at": now, "dihapus": False,
    }
    await db.peta_kolaborasi.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k not in ("ip", "oleh_user_id")}
