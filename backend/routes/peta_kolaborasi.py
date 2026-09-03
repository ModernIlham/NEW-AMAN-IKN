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
import base64
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from auth_utils import (
    require_user, require_writer, create_map_token, require_map_token,
    require_user_or_map_token, MAP_TOKEN_EXPIRATION_DAYS,
)
from db import db
from shared_utils import (
    limiter, log_audit, scope_query_field_satker, pastikan_akses_dok_satker,
    get_photo_from_gridfs, generate_photo_thumbnail,
)

peta_kolaborasi_router = APIRouter()

_PROJ = {"_id": 0}
_DEFAULT_JAM = 72          # masa tayang default 3 hari
UMUR_ARSIP_HARI = 30       # link mati > sebulan tak lagi didaftar (lihat _share_usang)
DEFAULT_MAKS_TITIK = 120
DEFAULT_MAKS_TEKS = 1000
MAKS_TITIK_ASET_PUBLIK = 5000   # plafon titik aset yang dikirim ke peta publik
MAKS_KONTRIB_SHARE = 3000       # plafon kontribusi (titik+komentar) per share

# ── Impor usulan kolaborasi ke peta ASLI ───────────────────────────────────
#
# Kontribusi tamu adalah USULAN, bukan data resmi. Pengelola satker meninjau
# lalu menyetujui/menolak — satu per satu atau sekaligus ("yakin semua").
#
# Titik yang disetujui menjadi ASET nyata dengan KODE BARANG PLACEHOLDER
# (KODE_BARANG_USULAN) + NUP otomatis. Kode itu memang bukan kodefikasi BMN
# yang sah: ia penanda "barang ini datang dari lapangan, kodenya belum
# ditetapkan". Kategorinya memakai kategori DUMMY, dan `report_filters
# .tanpa_dummy_filter` mengecualikan kategori dummy dari laporan resmi —
# jadi usulan yang baru masuk TIDAK ikut menghitung neraca sampai petugas
# melengkapi kode barang & kategori sebenarnya. Itu disengaja.
KODE_BARANG_USULAN = "0000000000"
MAKS_SETUJUI_SEKALIGUS = 300    # plafon satu batch "setujui semua"

STATUS_USULAN = ("terbuka", "disetujui", "ditolak")


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


async def _link_peta_pendek(share_id: str, token: str, kode_satker: str = "",
                            oleh: str = "") -> str:
    """Tautan berbagi peta versi PENDEK — sama pertimbangannya dengan tautan
    e-sign: token berada di query string, jadi memendekkannya membuat pesan
    yang beredar (WA/email) tak lagi membawa token itu. Gagal memendekkan
    jatuh ke tautan panjang; berbagi peta tak boleh batal karenanya."""
    panjang = _link_peta(share_id, token)
    try:
        from tautan_pendek_utils import buat_tautan_pendek, url_pendek
        kode = await buat_tautan_pendek(
            panjang, jenis="peta", ref=str(share_id), kode_satker=kode_satker,
            dibuat_oleh=oleh, pakai_ulang=True)
        return url_pendek(kode) if kode else panjang
    except Exception:
        return panjang


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_coord(v) -> Optional[float]:
    """Koordinat aset tersimpan STRING (bisa desimal koma) — kembalikan float
    berhingga atau None."""
    from spasial_utils import parse_koordinat
    return parse_koordinat(v)


def _hitung_berlaku(durasi_jam, berlaku_sampai_str, base: datetime,
                    plafon_base: Optional[datetime] = None) -> str:
    """Tentukan ISO masa tayang (UTC): berlaku_sampai eksplisit > durasi_jam >
    default. Dijepit ke plafon token (MAP_TOKEN_EXPIRATION_DAYS sejak
    `plafon_base` bila diberi — mis. created_at, agar token yang SUDAH tersebar
    tak kedaluwarsa lebih dulu dari masa tayang — atau sejak `base`) & minimal
    1 jam. SELALU dinormalkan ke UTC agar perbandingan kedaluwarsa konsisten
    (offset non-UTC pada input tak menyesatkan)."""
    maks = (plafon_base or base) + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)
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
    return dt.astimezone(timezone.utc).isoformat()


def _kedaluwarsa(share: dict) -> bool:
    """True bila masa tayang lampau. Bandingkan sebagai datetime AWARE (bukan
    string leksikografis) agar offset zona waktu pada berlaku_sampai tak
    menyesatkan; jatuh ke perbandingan string hanya bila parse gagal."""
    bs = str(share.get("berlaku_sampai") or "")
    if not bs:
        return False
    try:
        dt = datetime.fromisoformat(bs.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= _now()
    except (ValueError, TypeError):
        return bs < _now().isoformat()


def _parse_iso(s) -> Optional[datetime]:
    """Parse ISO → datetime aware (UTC bila naif), atau None bila gagal."""
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def _mati_pada(share: dict) -> Optional[datetime]:
    """Kapan link BERHENTI berguna, atau None bila masih hidup.

    Dibatalkan → saat pembatalan (`updated_at`, sentuhan terakhir). Habis masa
    tayang → `berlaku_sampai`. Dua-duanya dipakai apa adanya: memakai
    `updated_at` untuk link kedaluwarsa akan salah (link yang dibuat 30 hari
    dengan sekali sentuh langsung dianggap tua begitu berakhir)."""
    if share.get("status") == "batal":
        return _parse_iso(share.get("updated_at")) or _parse_iso(share.get("created_at"))
    if _kedaluwarsa(share):
        return _parse_iso(share.get("berlaku_sampai"))
    return None


def _share_usang(share: dict, sekarang: Optional[datetime] = None) -> bool:
    """True bila link sudah MATI (dibatalkan / habis masa tayang, termasuk yang
    pernah diterbitkan ulang lalu mati lagi) DAN matinya lebih dari sebulan
    lalu. Dipakai untuk MENYINGKIRKAN arsip mati dari daftar kelola supaya
    daftar tak menumpuk — dokumen share, kontribusi, dan jejak auditnya TIDAK
    dihapus. Tanpa cap waktu yang bisa dibaca → jangan disingkirkan (lebih baik
    daftar sedikit panjang daripada link hilang tanpa alasan)."""
    mati = _mati_pada(share)
    if mati is None:
        return False
    return (sekarang or _now()) - mati > timedelta(days=UMUR_ARSIP_HARI)


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


def _stempel_asal(share: dict) -> dict:
    """Stempel satker + kegiatan pada dokumen kontribusi (lihat tambah_titik)."""
    return {"kode_satker": str((share or {}).get("kode_satker") or ""),
            "activity_id": str((share or {}).get("activity_id") or "")}


def _status_usulan(k: dict) -> str:
    """Status usulan sebuah kontribusi; kontribusi ERA-LAMA dianggap TERBUKA.

    Dokumen yang dibuat sebelum alur persetujuan ada tidak punya
    `status_usulan`. Menganggapnya 'disetujui' akan menyembunyikannya dari
    layar peninjauan selamanya — usulan lapangan yang sudah terlanjur masuk
    tak akan pernah bisa diimpor. Karena itu tak-ada = belum ditinjau.
    """
    s = str((k or {}).get("status_usulan") or "").strip()
    return s if s in STATUS_USULAN else "terbuka"


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
    #: Titik yang DIBAGIKAN. Kosong/None = seluruh aset kegiatan, sebagaimana
    #: perilaku sejak awal. Berisi = HANYA aset ini — dipakai saat operator
    #: membagikan peta dengan filter atau seleksi aktif.
    #:
    #: Disimpan sebagai daftar id, bukan sebagai salinan filternya. Filter
    #: adalah PERTANYAAN yang jawabannya berubah seiring data; tautan yang
    #: sudah tersebar ke pihak luar tak boleh diam-diam memuat aset yang
    #: belum ada saat ia dibagikan.
    asset_ids: Optional[List[str]] = None


class PerpanjangIn(BaseModel):
    durasi_jam: Optional[int] = None
    berlaku_sampai: Optional[str] = None
    izinkan_titik_publik: Optional[bool] = None
    izinkan_komentar_publik: Optional[bool] = None


class JudulIn(BaseModel):
    judul: Optional[str] = ""


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


class GeserIn(BaseModel):
    """Usul PEMINDAHAN posisi sebuah aset yang sudah ada di peta."""
    asset_id: str
    lat: float
    lng: float
    keterangan: Optional[str] = ""
    oleh: Optional[str] = ""


def _share_keluar(sh: dict) -> dict:
    """Bentuk aman untuk daftar/detail pengelola — tanpa jti (rahasia token).

    `asset_ids` ikut DIBUANG dan diganti ringkasannya. Daftar link memuat
    banyak entri sekaligus; membawa ribuan id di tiap entri membengkakkan
    jawaban tanpa satu pun layar membutuhkannya. Yang dibutuhkan hanyalah
    JUMLAHNYA — itulah pertanyaan yang benar-benar diajukan operator:
    "berapa titik yang saya bagikan lewat tautan ini?"
    """
    d = {k: v for k, v in sh.items() if k not in ("jti", "asset_ids")}
    d["kedaluwarsa"] = _kedaluwarsa(sh)
    ids = sh.get("asset_ids") or []
    d["lingkup"] = "terpilih" if ids else "semua"
    # None (bukan 0) untuk lingkup "semua": jumlahnya tidak tetap — ia
    # mengikuti isi kegiatan. Angka 0 akan terbaca "tak ada titik".
    d["jumlah_titik_dibagikan"] = len(ids) if ids else None
    d["link"] = None  # link berisi token; hanya dikembalikan saat create/lihat-token
    return d


async def _lingkup_aset(activity_id: str, asset_ids) -> list:
    """Daftar id aset yang benar-benar dibagikan; [] berarti SELURUH kegiatan.

    Dua hal ditegakkan di sini, dan keduanya harus di SERVER:

    1. **Kepemilikan.** Id yang dikirim layar tak boleh dipercaya begitu saja —
       tanpa pemeriksaan ini, seseorang dapat menyusun permintaan yang
       membagikan aset kegiatan LAIN lewat tautan publik. Hanya id yang benar
       terbukti milik kegiatan ini yang lolos.
    2. **Plafon.** Peta publik memang hanya mengirim `MAKS_TITIK_ASET_PUBLIK`
       titik. Menyimpan lebih dari itu akan membuat tautan menjanjikan sesuatu
       yang tak pernah ia tampilkan — jadi permintaannya ditolak dengan terang,
       bukan dipotong diam-diam.
    """
    if not asset_ids:
        return []
    bersih, terlihat = [], set()
    for x in asset_ids:
        v = str(x or "").strip()
        if v and v not in terlihat:
            terlihat.add(v)
            bersih.append(v)
    if not bersih:
        return []
    if len(bersih) > MAKS_TITIK_ASET_PUBLIK:
        raise HTTPException(
            status_code=400,
            detail=(f"Terlalu banyak titik untuk dibagikan "
                    f"({len(bersih)}; maks {MAKS_TITIK_ASET_PUBLIK}). "
                    "Persempit filter atau seleksi terlebih dahulu."))
    sah = set()
    async for a in db.assets.find(
            {"activity_id": activity_id, "id": {"$in": bersih},
             "dihapus": {"$ne": True}}, {"_id": 0, "id": 1}):
        sah.add(a.get("id"))
    hasil = [i for i in bersih if i in sah]
    if not hasil:
        raise HTTPException(
            status_code=400,
            detail=("Tak satu pun aset terpilih ditemukan di kegiatan ini. "
                    "Muat ulang peta lalu coba lagi."))
    return hasil


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
    lingkup_ids = await _lingkup_aset(payload.activity_id, payload.asset_ids)
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
        # [] = seluruh aset kegiatan (perilaku sejak awal, dan tetap HIDUP:
        # aset yang ditambahkan kemudian ikut tampil). Berisi = himpunan tetap
        # yang dipilih operator saat membagikan.
        "asset_ids": lingkup_ids,
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
    out["link"] = await _link_peta_pendek(
        share_id, token, kode_satker=doc["kode_satker"],
        oleh=user.get("username", ""))
    out["token"] = token
    return out


@peta_kolaborasi_router.get("/peta/share")
async def daftar_share(activity_id: str = Query(...),
                       user: dict = Depends(require_writer)):
    """Daftar link peta untuk sebuah kegiatan (ter-scope satker). Menyertakan
    link ber-token agar pengelola bisa menyalin/membagikan ulang.

    Link yang sudah MATI lebih dari sebulan (dibatalkan / habis masa tayang,
    termasuk yang pernah diterbitkan ulang) tidak ikut didaftar — jumlahnya
    dilaporkan lewat `diarsipkan` supaya daftar yang menyusut tidak terlihat
    seperti data hilang. Dokumen & kontribusinya tetap tersimpan."""
    q = scope_query_field_satker(user, {"activity_id": activity_id})
    items = await db.peta_shares.find(q, _PROJ).sort("created_at", -1).to_list(200)
    sekarang = _now()
    diarsipkan = 0
    hasil = []
    for sh in items:
        if _share_usang(sh, sekarang):
            diarsipkan += 1
            continue
        d = _share_keluar(sh)
        if sh.get("status") != "batal":
            d["link"] = await _link_peta_pendek(
                sh["id"], create_map_token(sh["id"], sh.get("jti", "")),
                kode_satker=str(sh.get("kode_satker") or ""))
        # jumlah kontribusi (info ringkas)
        d["jumlah_kontribusi"] = await db.peta_kolaborasi.count_documents(
            {"share_id": sh["id"], "dihapus": {"$ne": True}})
        hasil.append(d)
    return {"items": hasil, "jumlah": len(hasil), "diarsipkan": diarsipkan}


@peta_kolaborasi_router.put("/peta/share/{share_id}/judul")
async def ubah_judul_share(share_id: str, payload: JudulIn,
                           user: dict = Depends(require_writer)):
    """Ubah judul peta yang SUDAH diterbitkan. Judul dipakai di halaman publik
    dan pada teks ajakan saat dibagikan, jadi salah ketik harus bisa dikoreksi
    tanpa menerbitkan tautan baru — tautan yang sudah tersebar tetap hidup
    (jti tidak dirotasi)."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    judul = str(payload.judul or "").strip()[:140]
    await db.peta_shares.update_one(
        {"id": share_id},
        {"$set": {"judul": judul, "updated_at": _now().isoformat()}})
    await log_audit("ubah_judul_share_peta", sh.get("activity_id", ""), share_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah judul peta kolaboratif → {judul or '(kosong)'}",
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True, "judul": judul}


@peta_kolaborasi_router.put("/peta/share/{share_id}/perpanjang")
async def perpanjang_share(share_id: str, payload: PerpanjangIn,
                           user: dict = Depends(require_writer)):
    """Perpanjang masa tayang (dari SEKARANG) + opsi izin — link lama tetap
    berlaku (jti tidak dirotasi). Link yang sudah DIBATALKAN tidak bisa
    dihidupkan lewat sini (pembatalan bersifat permanen sebagai kill-switch);
    untuk mengaktifkan kembali gunakan 'terbitkan ulang' yang menerbitkan link
    BARU & mematikan link lama yang bocor."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    if sh.get("status") == "batal":
        raise HTTPException(
            status_code=409,
            detail="Link sudah dibatalkan. Terbitkan ulang untuk membuat "
                   "tautan baru (tautan lama tetap mati).")
    now = _now()
    # Plafon berlaku dipatok pada USIA TOKEN (created_at) agar link yang sudah
    # tersebar (exp = created_at + plafon) tak kedaluwarsa lebih dulu dari DB.
    plafon = _parse_iso(sh.get("created_at")) or now
    berlaku = _hitung_berlaku(payload.durasi_jam, payload.berlaku_sampai, now, plafon)
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


@peta_kolaborasi_router.post("/peta/share/{share_id}/terbitkan-ulang")
async def terbitkan_ulang_share(share_id: str, payload: PerpanjangIn,
                                user: dict = Depends(require_writer)):
    """Terbitkan ulang link: ROTASI jti + mint token BARU (kill-switch link
    bocor / hidupkan kembali link yang dibatalkan). Semua tautan lama LANGSUNG
    mati (jti tak cocok). Kontribusi yang sudah masuk tetap tersimpan (share_id
    sama)."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    now = _now()
    jti = uuid.uuid4().hex
    berlaku = _hitung_berlaku(payload.durasi_jam, payload.berlaku_sampai, now)
    setf = {"jti": jti, "berlaku_sampai": berlaku, "status": "aktif",
            "updated_at": now.isoformat()}
    if payload.izinkan_titik_publik is not None:
        setf["izinkan_titik_publik"] = bool(payload.izinkan_titik_publik)
    if payload.izinkan_komentar_publik is not None:
        setf["izinkan_komentar_publik"] = bool(payload.izinkan_komentar_publik)
    await db.peta_shares.update_one({"id": share_id}, {"$set": setf})
    token = create_map_token(share_id, jti)
    await log_audit("terbitkan_ulang_share_peta", sh.get("activity_id", ""), share_id,
                    username=user.get("username", "system"),
                    detail=f"Terbitkan ulang link peta (rotasi jti) s.d. {berlaku[:16]}",
                    kode_satker=str(sh.get("kode_satker") or ""))
    # jti dirotasi → tautan pendek lama menunjuk token mati; cabut dulu.
    from tautan_pendek_utils import cabut_tautan
    await cabut_tautan("peta", share_id)
    link = await _link_peta_pendek(share_id, token,
                                   kode_satker=str(sh.get("kode_satker") or ""),
                                   oleh=user.get("username", ""))
    return {"ok": True, "berlaku_sampai": berlaku,
            "link": link, "token": token}


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
#
# KONTRAK payload publik: SATU-SATUNYA kunci yang boleh keluar ke pemegang link.
# Ditulis sebagai konstanta agar dapat DIUJI, bukan sekadar dijanjikan komentar
# — sejak Fase 11 aplikasi menyimpan posisi perangkat yang dipegang perorangan,
# dan satu field tambahan yang lolos ke sini akan membocorkan keberadaan
# pemegangnya ke siapa pun yang punya tautan (DPIA §6).
KUNCI_PUBLIK_TITIK = frozenset({
    "id", "lat", "lng", "kode", "nup", "nama", "kategori", "status",
    "kondisi", "merk", "tipe", "lokasi", "jumlah_foto", "thumbnail_index",
})


def baris_titik_publik(a: dict, lat: float, lng: float) -> dict:
    """Satu titik aset untuk peta PUBLIK — dibangun kunci-per-kunci (allowlist).

    Disusun eksplisit, bukan `dict(a)` dikurangi field terlarang: daftar-larangan
    mensyaratkan seseorang mengingat untuk memperbaruinya setiap kali field baru
    lahir, dan justru field BARU-lah yang paling mungkin sensitif. Dengan
    allowlist, field yang tak dikenal otomatis tidak ikut keluar.
    """
    return {"id": a.get("id"), "lat": lat, "lng": lng,
            "kode": a.get("asset_code") or "", "nup": a.get("NUP") or "",
            "nama": a.get("asset_name") or "",
            "kategori": a.get("category") or "",
            "status": a.get("inventory_status") or "",
            "kondisi": a.get("condition") or "",
            "merk": a.get("brand") or "", "tipe": a.get("model") or "",
            "lokasi": a.get("location") or "",
            "jumlah_foto": int(a.get("jumlah_foto") or 0),
            "thumbnail_index": int(a.get("thumbnail_index") or 0)}


async def _titik_aset(share: dict) -> list:
    """Titik aset kegiatan (koordinat valid) — HANYA field DESKRIPTIF aman untuk
    publik (identitas + kategori/status + merk/tipe/lokasi/kondisi untuk verifikasi
    lapangan). SENGAJA TANPA: nilai/harga, foto, pengguna/NIP (PII), dokumen."""
    # jumlah_foto DIHITUNG (bukan field tersimpan): GridFS-first, fallback inline —
    # sama seperti daftar aset. $size dievaluasi di server; byte foto TIDAK ditarik.
    cocok = {"activity_id": share.get("activity_id"), "dihapus": {"$ne": True}}
    # Lingkup terbatas: tautan dibuat saat filter/seleksi aktif, jadi ia
    # membagikan HANYA titik yang saat itu terlihat operator. Tanpa penyaring
    # ini, tautan diam-diam memuat seluruh aset kegiatan — persis kebalikan
    # dari yang dimaksud saat membagikannya.
    lingkup = [str(i) for i in (share.get("asset_ids") or []) if i]
    if lingkup:
        cocok["id"] = {"$in": lingkup}
    pipeline = [
        {"$match": cocok},
        {"$limit": MAKS_TITIK_ASET_PUBLIK},
        {"$project": {
            "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "category": 1, "inventory_status": 1, "condition": 1,
            "brand": 1, "model": 1, "location": 1, "thumbnail_index": 1,
            "koordinat_latitude": 1, "koordinat_longitude": 1,
            "jumlah_foto": {"$let": {
                "vars": {"ng": {"$size": {"$ifNull": ["$photo_gridfs_ids", []]}}},
                "in": {"$cond": [{"$gt": ["$$ng", 0]}, "$$ng",
                                 {"$size": {"$ifNull": ["$photos", []]}}]},
            }},
        }},
    ]
    out = []
    async for a in db.assets.aggregate(pipeline):
        lat = _parse_coord(a.get("koordinat_latitude"))
        lng = _parse_coord(a.get("koordinat_longitude"))
        if lat is None or lng is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        out.append(baris_titik_publik(a, lat, lng))
    return out


@peta_kolaborasi_router.get("/peta/kolaborasi/{share_id}")
@limiter.limit("120/minute")
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
    # Usulan GESER yang masih menunggu — dipakai layar menggambar garis
    # putus-putus + marker transparan. Yang sudah disetujui/ditolak TIDAK ikut:
    # asetnya sudah pindah (atau usulannya gugur), jadi bayangannya harus
    # hilang. Kalau tidak, peta menyisakan garis ke posisi lama selamanya.
    usulan_geser = [k for k in kontrib
                    if k.get("jenis") == "geser" and _status_usulan(k) == "terbuka"]
    titik_aset = await _titik_aset(sh)
    return {
        "id": share_id,
        "judul": sh.get("judul") or "",
        "nama_kegiatan": sh.get("nama_kegiatan") or "",
        "berlaku_sampai": sh.get("berlaku_sampai") or "",
        "kedaluwarsa": _kedaluwarsa(sh),
        "boleh_kontribusi": boleh_kontribusi,
        # Operator/admin satker share → boleh MODERASI (hapus titik/komentar).
        # Sekadar penanda UI; penghapusan tetap ditegakkan require_writer + satker.
        "boleh_moderasi": _operator_satker(sh, ctx),
        "izinkan_titik_publik": bool(sh.get("izinkan_titik_publik", True)),
        "izinkan_komentar_publik": bool(sh.get("izinkan_komentar_publik", True)),
        # Keputusan SIAP-PAKAI untuk layar: dihitung dengan fungsi yang SAMA
        # dengan penjaga tulis, jadi tombol yang tampil = aksi yang benar-benar
        # diterima server. Layar tak boleh menyimpulkan izin sendiri.
        "boleh_tambah_titik": boleh_kontribusi and _izin_kontribusi(
            sh, ctx, punya_link, "izinkan_titik_publik"),
        "boleh_komentar": boleh_kontribusi and _izin_kontribusi(
            sh, ctx, punya_link, "izinkan_komentar_publik"),
        "tamu": bool(ctx.get("guest")),
        # Lingkup ikut dikirim supaya halaman publik dapat menyatakan bahwa
        # peta ini SEBAGIAN, bukan seluruh kegiatan. Tanpa itu pengunjung
        # menyimpulkan sendiri bahwa yang ia lihat adalah semuanya — dan pada
        # peta hasil filter, kesimpulan itu keliru.
        "lingkup": "terpilih" if (sh.get("asset_ids") or []) else "semua",
        "titik_aset": titik_aset,
        "jumlah_titik_aset": len(titik_aset),
        "titik_kolaborasi": titik_kolaborasi,
        "komentar": komentar,
        "usulan_geser": usulan_geser,
    }


@peta_kolaborasi_router.get("/peta/kolaborasi/{share_id}/aset/{asset_id}/foto/{indeks}")
@limiter.limit("240/minute")
async def foto_aset_peta(share_id: str, asset_id: str, indeks: int, request: Request,
                        thumb: int = 0,
                        ctx: dict = Depends(require_user_or_map_token)):
    """Sajikan foto aset kegiatan untuk peta publik (token peta / user).
    Diberi gerbang akses share yang SAMA + dipastikan aset milik kegiatan share.
    ?thumb=1 → thumbnail kecil; tanpa param → foto ASLI (untuk tampilan penuh)."""
    sh = await _muat_share(share_id)
    _verifikasi_token_share(sh, ctx)
    punya_link = await _punya_link(sh, request)
    boleh_lihat, _, alasan = _akses_peta(sh, ctx, punya_link)
    if not boleh_lihat:
        raise HTTPException(status_code=403, detail=alasan)
    if indeks < 0 or indeks > 200:
        raise HTTPException(status_code=400, detail="Indeks foto tidak valid")
    aset = await db.assets.find_one(
        {"id": asset_id, "activity_id": sh.get("activity_id"), "dihapus": {"$ne": True}},
        {"_id": 0, "photo_gridfs_ids": 1, "photos": 1, "photo_thumbnails": 1, "version": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    # Pakai helper media aset yang sudah teruji (deteksi tipe + header cache/ETag).
    from routes.assets import _tebak_media_type, _media_headers, _not_modified  # lazy: hindari siklus impor
    etag = (f'"peta-{asset_id}-p{indeks}{"-t" if thumb else ""}'
            f'-v{int(aset.get("version", 1) or 1)}"')
    nm = _not_modified(request, etag)
    if nm:
        return nm
    gridfs_ids = aset.get("photo_gridfs_ids", []) or []
    photos = aset.get("photos", []) or []
    if thumb:
        thumbnails = aset.get("photo_thumbnails", []) or []
        tb = thumbnails[indeks] if 0 <= indeks < len(thumbnails) else ""
        if not tb:
            if indeks < len(photos) and photos[indeks]:
                tb = await asyncio.to_thread(generate_photo_thumbnail, photos[indeks]) or ""
            elif indeks < len(gridfs_ids) and gridfs_ids[indeks]:
                pb = await get_photo_from_gridfs(gridfs_ids[indeks])
                if pb:
                    tb = await asyncio.to_thread(
                        generate_photo_thumbnail, base64.b64encode(pb).decode("utf-8")) or ""
        if tb:
            data = tb.split(",", 1)[1] if tb.startswith("data:") else tb
            try:
                _tb = base64.b64decode(data)
                # Deteksi tipe dari magic-byte: thumbnail kini WebP (lama bisa JPEG).
                return Response(content=_tb, media_type=_tebak_media_type(_tb),
                                headers=_media_headers(etag))
            except Exception:
                pass  # thumbnail rusak → jatuh ke foto penuh
    photo_bytes = None
    if indeks < len(gridfs_ids) and gridfs_ids[indeks]:
        photo_bytes = await get_photo_from_gridfs(gridfs_ids[indeks])
    if photo_bytes is None and indeks < len(photos):
        phb = photos[indeks] or ""
        data = phb.split(",", 1)[1] if phb.startswith("data:") else phb
        try:
            photo_bytes = base64.b64decode(data)
        except Exception:
            photo_bytes = None
    if photo_bytes is None:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    return Response(content=photo_bytes, media_type=_tebak_media_type(photo_bytes),
                    headers=_media_headers(etag))


def _izin_kontribusi(share: dict, ctx: dict, punya_link: bool,
                     izin_field: str) -> bool:
    """Apakah pengunjung ini boleh menulis kontribusi jenis `izin_field`?

    SATU-SATUNYA penentu izin per-link — dipakai baik oleh penjaga tulis maupun
    oleh payload yang menyalakan/mematikan tombol di layar, supaya UI tak pernah
    menawarkan aksi yang akan ditolak server (dan sebaliknya).

    Setelan per-link berlaku untuk SETIAP kunjungan LEWAT LINK — tamu maupun
    pengunjung yang kebetulan sedang login di aplikasi. Dulu setiap user login
    lolos begitu saja, sehingga link yang dibuat dengan komentar/titik DIMATIKAN
    tetap bisa dipakai berkontribusi; setelan tiap link jadi tak berarti.

    Yang lolos hanya operator/admin satker pemilik share yang membuka petanya
    DARI APLIKASI (tanpa token link): itu pengelolaan peta sendiri, bukan
    kontribusi publik.
    """
    if bool(share.get(izin_field, True)):
        return True
    return _operator_satker(share, ctx) and not punya_link


async def _guard_kontribusi(sh: dict, ctx: dict, request: Request,
                            izin_field: str, aksi: str):
    """Validasi umum saat menulis (titik/komentar): akses + izin publik + plafon."""
    _verifikasi_token_share(sh, ctx)
    punya_link = await _punya_link(sh, request)
    _, boleh_kontribusi, alasan = _akses_peta(sh, ctx, punya_link)
    if not boleh_kontribusi:
        raise HTTPException(status_code=403,
                            detail=alasan or "Masa tayang berakhir — perpanjang untuk berkontribusi lagi.")
    if not _izin_kontribusi(sh, ctx, punya_link, izin_field):
        raise HTTPException(status_code=403,
                            detail=f"Pembagi menonaktifkan {aksi} publik untuk peta ini.")
    # Plafon kontribusi per share — cegah pembengkakan tak terbatas & jaga
    # respons tetap terbatas.
    jml = await db.peta_kolaborasi.count_documents(
        {"share_id": sh["id"], "dihapus": {"$ne": True}})
    if jml >= MAKS_KONTRIB_SHARE:
        raise HTTPException(
            status_code=429,
            detail="Batas kontribusi peta ini telah tercapai. Hubungi pembagi.")


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
        # Stempel asal (M-SCOPE): kontribusi dulu hanya menyimpan `share_id`,
        # sehingga setiap kueri lintas-share TERPAKSA menjoin dokumen share
        # lebih dulu — satu kueri yang lupa menjoin langsung jadi kebocoran
        # lintas-satker. Distempel di sini supaya penyaringnya berdiri sendiri.
        **_stempel_asal(sh),
        "status_usulan": "terbuka",
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
        **_stempel_asal(sh),
        "status_usulan": "terbuka",
    }
    await db.peta_kolaborasi.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k not in ("ip", "oleh_user_id")}


# ══════════════════════════════════════════════════════════════════════════
# IMPOR USULAN KOLABORASI KE PETA ASLI
# ══════════════════════════════════════════════════════════════════════════
#
# Mandat pemilik: "hasil penambahan titik, dan juga komentarnya dapat
# ditambahkan import ke dalam peta aslinya satu persatu atau yakin semua
# import dari tamu kolaborasi massal langsung".
#
# Aturan main yang ditegakkan di sini:
#
# * MENYETUJUI = MENULIS DATA RESMI. Karena itu penjaganya `require_writer` +
#   `pastikan_akses_dok_satker` atas dokumen SHARE — pemegang tautan tamu tak
#   pernah bisa menyentuhnya, dan admin satker lain ditolak 403. Tamu hanya
#   boleh MENGUSULKAN (endpoint tambah_titik/tambah_komentar di atas).
#
# * SEKALI SETUJU = SATU ASET. Persetujuan memakai kunci idempotensi
#   deterministik dari id usulannya, jadi menekan "Setujui" dua kali (atau
#   "Setujui Semua" yang diulang karena jaringan putus) TIDAK melahirkan aset
#   kembar — `create_asset` mengembalikan aset yang sudah ada.
#
# * NUP DIALOKASIKAN DI SERVER, PER BATCH. Kalau klien yang menghitung, dua
#   penyetuju serentak (atau satu batch berisi 50 titik) akan memakai NUP yang
#   sama berulang. Penghitungnya di sini membaca NUP terbesar SEKALI lalu naik
#   sendiri, dan `create_asset` masih menegakkan keunikan (kode, NUP,
#   kegiatan) sebagai jaring terakhir.


class TinjauIn(BaseModel):
    alasan: Optional[str] = ""


class SetujuiSemuaIn(BaseModel):
    """Batas jenis usulan yang ikut disetujui ('' = titik & komentar)."""
    jenis: Optional[str] = ""


async def _pengelola_share(share_id: str, user: dict) -> dict:
    """Muat share + pastikan pemanggil BOLEH MENGELOLA-nya (403 bila bukan)."""
    sh = await _muat_share(share_id)
    await pastikan_akses_dok_satker(user, sh)
    return sh


def _usulan_keluar(k: dict) -> dict:
    """Bentuk usulan untuk layar peninjauan (tanpa IP & id user kontributor)."""
    d = {x: y for x, y in (k or {}).items()
         if x not in ("ip", "oleh_user_id", "_id")}
    d["status_usulan"] = _status_usulan(k)
    return d


@peta_kolaborasi_router.get("/peta/kolaborasi/{share_id}/usulan")
async def daftar_usulan(share_id: str, status: str = "terbuka",
                        user: dict = Depends(require_writer)):
    """Usulan kolaborasi untuk ditinjau pengelola satker.

    `status` = terbuka (bawaan) | disetujui | ditolak | semua.
    """
    sh = await _pengelola_share(share_id, user)
    semua = await db.peta_kolaborasi.find(
        {"share_id": share_id, "dihapus": {"$ne": True}},
        {"_id": 0, "ip": 0, "oleh_user_id": 0}).sort("created_at", 1).to_list(
            MAKS_KONTRIB_SHARE)
    # Penyaringan status dilakukan DI PYTHON, bukan di kueri: dokumen era-lama
    # tak punya field `status_usulan` sama sekali, dan {"status_usulan":
    # "terbuka"} tak akan pernah cocok dengannya — usulan lama akan hilang
    # diam-diam dari layar peninjauan.
    st = str(status or "terbuka").strip().lower()
    items = [_usulan_keluar(k) for k in semua
             if st == "semua" or _status_usulan(k) == st]
    rekap = {"terbuka": 0, "disetujui": 0, "ditolak": 0}
    for k in semua:
        rekap[_status_usulan(k)] = rekap.get(_status_usulan(k), 0) + 1
    return {
        "items": items,
        "jumlah": len(items),
        "rekap": rekap,
        "judul": sh.get("judul") or "",
        "nama_kegiatan": sh.get("nama_kegiatan") or "",
        "activity_id": sh.get("activity_id") or "",
    }


async def _kategori_usulan() -> str:
    """Label kategori untuk aset hasil usulan — kategori DUMMY bila tersedia.

    Sengaja SAMA dengan jalur "tambah aset di peta": barang yang belum
    diverifikasi petugas tak boleh langsung ikut menghitung laporan resmi
    (lihat `report_filters.tanpa_dummy_filter`). Bila master kategori belum
    punya entri dummy, dipakai label eksplisit yang tetap mengandung kata
    "Dummy" supaya penyaring laporan tetap mengenalinya.
    """
    kat = await db.categories.find_one(
        {"label": {"$regex": "dummy", "$options": "i"}}, {"_id": 0, "label": 1})
    return str((kat or {}).get("label") or "Dummy (Usulan Kolaborasi)")


async def _nup_awal_usulan(activity_id: str) -> int:
    """NUP terbesar yang sudah terpakai untuk KODE_BARANG_USULAN di kegiatan.

    Maksimumnya dihitung DI PYTHON, bukan lewat `$max` di server. NUP tersimpan
    sebagai STRING, jadi `$max` string akan menjawab "9" untuk himpunan
    {1..10} — batch berikutnya lalu mulai dari 10 dan langsung bentrok dengan
    NUP 10 yang sudah ada. Mengubahnya lewat `$convert` benar di MongoDB tapi
    tak tersedia di mongomock, sehingga perilakunya jadi tak teruji. Yang
    ditarik hanya satu field pendek, dan cakupannya sempit (satu kegiatan,
    satu kode barang).
    """
    nups = await db.assets.find(
        {"activity_id": activity_id, "asset_code": KODE_BARANG_USULAN},
        {"_id": 0, "NUP": 1}).to_list(MAKS_KONTRIB_SHARE)
    maks = 0
    for a in nups:
        try:
            maks = max(maks, int(str(a.get("NUP") or "0").strip() or 0))
        except (TypeError, ValueError):
            continue    # NUP non-numerik (data impor) diabaikan, bukan meledak
    return maks


class _PermintaanIdem:
    """Pengganti Request seadanya untuk memanggil `create_asset` dari dalam.

    `create_asset` hanya membaca satu hal dari Request: header
    Idempotency-Key. Memberinya kunci turunan id usulan membuat persetujuan
    ULANG mengembalikan aset yang SAMA alih-alih membuat kembarannya —
    penting karena "Setujui Semua" bisa diulang setelah jaringan putus.
    """

    def __init__(self, kunci: str):
        self.headers = {"Idempotency-Key": kunci}


async def _jadikan_aset(usulan: dict, share: dict, user: dict,
                        nup: int, kategori: str) -> str:
    """Buat aset dari satu usulan titik → id aset. Melempar HTTPException."""
    from models import AssetCreate
    from routes.assets import create_asset
    ket = str(usulan.get("keterangan") or "").strip()
    jejak = (f"Usulan peta kolaborasi oleh {usulan.get('oleh') or 'Tamu'} "
             f"({usulan.get('created_at', '')[:10]}).")
    payload = AssetCreate(
        asset_code=KODE_BARANG_USULAN,
        NUP=str(nup),
        asset_name=str(usulan.get("nama_titik") or "Titik usulan")[:200],
        category=kategori,
        condition="Baik",
        status="Aktif",
        inventory_status="Belum Diinventarisasi",
        koordinat_latitude=f"{float(usulan.get('lat') or 0):.7f}",
        koordinat_longitude=f"{float(usulan.get('lng') or 0):.7f}",
        notes=(f"{ket}\n{jejak}".strip() if ket else jejak),
        activity_id=str(share.get("activity_id") or ""),
    )
    hasil = await create_asset(
        payload, _PermintaanIdem(f"usulan-peta:{usulan.get('id')}"), _user=user)
    return str(getattr(hasil, "id", "") or "")


async def _salin_komentar_ke_aset(usulan: dict, share: dict, user: dict,
                                  asset_id: str) -> str:
    """Salin satu komentar usulan menjadi komentar pada aset peta ASLI."""
    now = _now().isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "asset_id": asset_id,
        "activity_id": str(share.get("activity_id") or ""),
        "kode_satker": str(share.get("kode_satker") or ""),
        "teks": str(usulan.get("teks") or "")[:DEFAULT_MAKS_TEKS],
        "oleh": str(usulan.get("oleh") or "Tamu"),
        "oleh_tipe": str(usulan.get("oleh_tipe") or "tamu"),
        "share_id": str(share.get("id") or ""),
        "usulan_id": str(usulan.get("id") or ""),
        "disetujui_oleh": user.get("username", "system"),
        "created_at": now,
        "dihapus": False,
    }
    # Idempoten: satu usulan komentar hanya boleh melahirkan SATU komentar aset
    # walau tombol setujui ditekan berulang.
    lama = await db.komentar_aset.find_one({"usulan_id": doc["usulan_id"]},
                                           {"_id": 0, "id": 1})
    if lama:
        return str(lama.get("id") or "")
    await db.komentar_aset.insert_one(dict(doc))
    return doc["id"]


async def _target_aset_komentar(usulan: dict) -> str:
    """Aset tujuan sebuah komentar usulan ('' bila belum bisa ditentukan).

    Komentar pada TITIK usulan menempel ke aset hasil titik itu — jadi ia baru
    bisa disalin setelah titiknya disetujui. Tanpa aturan ini komentar pada
    titik akan jadi yatim: menunjuk id yang tak pernah ada di peta asli.
    """
    if str(usulan.get("target_jenis") or "") == "aset":
        return str(usulan.get("target_id") or "")
    induk = await db.peta_kolaborasi.find_one(
        {"id": str(usulan.get("target_id") or "")},
        {"_id": 0, "aset_id": 1, "status_usulan": 1})
    return str((induk or {}).get("aset_id") or "")


async def _terapkan_geser(usulan: dict, share: dict, user: dict,
                          now: str) -> dict:
    """Setujui usulan geser → koordinat aset BENAR-BENAR berpindah.

    Posisi LAMA disimpan pada usulannya (`lat_asal`/`lng_asal`) dan
    `geser_dari` pada aset, jadi perpindahan ini bisa ditelusuri balik — bukan
    penimpaan senyap. `version` aset dinaikkan supaya klien ber-OCC tahu
    datanya berubah, dan `updated_at` disegarkan supaya jalur snapshot luring
    ikut menariknya.
    """
    from spasial_utils import operasi_geo_update
    aset = await db.assets.find_one(
        {"id": str(usulan.get("asset_id") or ""),
         "activity_id": str(share.get("activity_id") or "")},
        {"_id": 0})
    if not aset:
        return {"id": usulan["id"], "jenis": "geser", "dilewati": True,
                "alasan": ("Aset yang diusulkan pindah sudah tidak ada di "
                           "kegiatan ini.")}
    lat = f"{float(usulan.get('lat') or 0):.7f}"
    lng = f"{float(usulan.get('lng') or 0):.7f}"
    ubah = {
        "koordinat_latitude": lat, "koordinat_longitude": lng,
        "updated_at": now,
        # Jejak balik: dari mana ia dipindah, oleh usulan siapa.
        "geser_dari": {"lat": aset.get("koordinat_latitude") or "",
                       "lng": aset.get("koordinat_longitude") or "",
                       "usulan_id": usulan.get("id"),
                       "oleh": usulan.get("oleh") or "",
                       "disetujui_oleh": user.get("username", "system"),
                       "pada": now},
    }
    # `geo` (indeks 2dsphere) WAJIB ikut berpindah. Bila tidak, aset yang
    # posisinya dikoreksi tetap muncul di kueri area pada titik lamanya —
    # peta terlihat benar sementara pencarian spasial diam-diam salah.
    _geo = operasi_geo_update({"koordinat_latitude": lat,
                               "koordinat_longitude": lng})
    ubah.update(_geo["set"])
    operasi = {"$set": ubah, "$inc": {"version": 1}}
    if _geo["unset"]:
        operasi["$unset"] = _geo["unset"]
    await db.assets.update_one({"id": aset["id"]}, operasi)
    try:
        from meili_utils import jadwalkan_sync
        jadwalkan_sync("assets", {**aset, **ubah})
    except Exception:
        pass    # indeks pencarian bukan syarat perpindahan berhasil
    try:
        from shared_utils import invalidate_asset_cache
        invalidate_asset_cache()
    except Exception:
        pass
    await db.peta_kolaborasi.update_one(
        {"id": usulan["id"]},
        {"$set": {"status_usulan": "disetujui", "aset_id": aset["id"],
                  "ditinjau_oleh": user.get("username", "system"),
                  "ditinjau_pada": now, "alasan_tolak": ""}})
    return {"id": usulan["id"], "jenis": "geser", "aset_id": aset["id"],
            "lat": lat, "lng": lng}


async def _setujui_satu(usulan: dict, share: dict, user: dict,
                        nup: int, kategori: str) -> dict:
    """Setujui satu usulan → {id, jenis, aset_id, komentar_id} atau alasan."""
    now = _now().isoformat()
    jenis = str(usulan.get("jenis") or "")
    if jenis == "geser":
        hasil = await _terapkan_geser(usulan, share, user, now)
        return hasil
    if jenis == "titik":
        aset_id = await _jadikan_aset(usulan, share, user, nup, kategori)
        await db.peta_kolaborasi.update_one(
            {"id": usulan["id"]},
            {"$set": {"status_usulan": "disetujui", "aset_id": aset_id,
                      "ditinjau_oleh": user.get("username", "system"),
                      "ditinjau_pada": now, "alasan_tolak": ""}})
        return {"id": usulan["id"], "jenis": "titik", "aset_id": aset_id}
    aset_id = await _target_aset_komentar(usulan)
    if not aset_id:
        return {"id": usulan["id"], "jenis": "komentar", "dilewati": True,
                "alasan": ("Komentar menempel pada titik usulan yang belum "
                           "disetujui — setujui titiknya lebih dulu.")}
    kid = await _salin_komentar_ke_aset(usulan, share, user, aset_id)
    await db.peta_kolaborasi.update_one(
        {"id": usulan["id"]},
        {"$set": {"status_usulan": "disetujui", "komentar_aset_id": kid,
                  "aset_id": aset_id,
                  "ditinjau_oleh": user.get("username", "system"),
                  "ditinjau_pada": now, "alasan_tolak": ""}})
    return {"id": usulan["id"], "jenis": "komentar", "aset_id": aset_id,
            "komentar_id": kid}


@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/usulan/{usulan_id}/setujui")
@limiter.limit("60/minute")
async def setujui_usulan(share_id: str, usulan_id: str, request: Request,
                         user: dict = Depends(require_writer)):
    """Setujui SATU usulan → jadi aset (titik) / komentar aset (komentar)."""
    sh = await _pengelola_share(share_id, user)
    u = await db.peta_kolaborasi.find_one(
        {"id": usulan_id, "share_id": share_id, "dihapus": {"$ne": True}},
        {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    if _status_usulan(u) == "disetujui":
        # Bukan galat: pengelola lain mungkin sudah menyetujuinya lebih dulu.
        return {"ok": True, "sudah": True, "id": usulan_id,
                "aset_id": u.get("aset_id") or ""}
    kategori = await _kategori_usulan()
    nup = await _nup_awal_usulan(str(sh.get("activity_id") or "")) + 1
    hasil = await _setujui_satu(u, sh, user, nup, kategori)
    if hasil.get("dilewati"):
        raise HTTPException(status_code=409, detail=hasil["alasan"])
    await log_audit("setujui_usulan_peta", sh.get("activity_id", ""), usulan_id,
                    username=user.get("username", "system"),
                    detail=f"Usulan {hasil['jenis']} dari peta kolaborasi disetujui",
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True, **hasil}


@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/usulan/setujui-semua")
@limiter.limit("6/minute")
async def setujui_semua_usulan(share_id: str, payload: SetujuiSemuaIn,
                               request: Request,
                               user: dict = Depends(require_writer)):
    """"Yakin semua" — setujui seluruh usulan terbuka dalam satu jalan.

    TITIK diproses LEBIH DULU, baru komentar: komentar pada titik usulan baru
    punya aset tujuan setelah titiknya jadi aset. Urutan alami (`created_at`)
    BIASANYA sudah benar — orang tak bisa mengomentari titik yang belum ada —
    tetapi urutan itu bersandar pada perbandingan STRING waktu, yang meleset
    bila stempel waktunya bercampur format ('...Z' vs '+07:00') atau jam
    perangkat penyumbangnya meleset. Bila komentar sempat mendahului titiknya,
    komentar itu dilewati diam-diam padahal pemilik menekan "yakin semua".
    Pengurutan eksplisit di bawah membuat hasilnya tak bergantung pada itu.
    """
    sh = await _pengelola_share(share_id, user)
    semua = await db.peta_kolaborasi.find(
        {"share_id": share_id, "dihapus": {"$ne": True}},
        {"_id": 0}).sort("created_at", 1).to_list(MAKS_KONTRIB_SHARE)
    terbuka = [k for k in semua if _status_usulan(k) == "terbuka"]
    jenis_minta = str(payload.jenis or "").strip().lower()
    if jenis_minta in ("titik", "komentar"):
        terbuka = [k for k in terbuka if str(k.get("jenis") or "") == jenis_minta]
    if len(terbuka) > MAKS_SETUJUI_SEKALIGUS:
        raise HTTPException(
            status_code=413,
            detail=(f"Terlalu banyak usulan sekaligus ({len(terbuka)}). "
                    f"Setujui bertahap maksimal {MAKS_SETUJUI_SEKALIGUS} "
                    "per sekali jalan."))
    kategori = await _kategori_usulan()
    activity_id = str(sh.get("activity_id") or "")
    # Satu pembacaan NUP untuk SELURUH batch, lalu naik sendiri. Membaca ulang
    # per titik akan mengembalikan angka yang sama berkali-kali (aset yang baru
    # dibuat baru terlihat setelah insert-nya selesai) → NUP kembar.
    nup = await _nup_awal_usulan(activity_id)
    hasil, gagal, dilewati = [], [], []
    # Catatan jujur soal keunikan NUP: penghitung di atas menghemat kueri, TAPI
    # ia bukan yang menjamin tak ada NUP kembar. Dua batch yang berjalan
    # BERSAMAAN sama-sama membaca angka awal yang sama, dan penghitung lokal
    # tak bisa melihat batch tetangga. Yang benar-benar menjaga adalah
    # pemeriksaan keunikan (asset_code, NUP, activity_id) di `create_asset` —
    # yang kalah ditolak 400 dan muncul di daftar `gagal`, bukan menimpa data.
    for u in ([k for k in terbuka if str(k.get("jenis")) == "titik"]
              + [k for k in terbuka if str(k.get("jenis")) != "titik"]):
        try:
            if str(u.get("jenis")) == "titik":
                nup += 1
            r = await _setujui_satu(u, sh, user, nup, kategori)
            if r.get("dilewati"):
                dilewati.append(r)
                if str(u.get("jenis")) == "titik":
                    nup -= 1
            else:
                hasil.append(r)
        except HTTPException as e:
            gagal.append({"id": u.get("id"), "alasan": str(e.detail)})
            if str(u.get("jenis")) == "titik":
                nup -= 1
        except Exception as e:  # noqa: BLE001 — satu usulan rusak tak boleh
            gagal.append({"id": u.get("id"), "alasan": str(e)})  # menghentikan
            if str(u.get("jenis")) == "titik":                   # sisa batch
                nup -= 1
    await log_audit("setujui_semua_usulan_peta", activity_id, share_id,
                    username=user.get("username", "system"),
                    detail=(f"Impor massal usulan peta: {len(hasil)} disetujui, "
                            f"{len(dilewati)} dilewati, {len(gagal)} gagal"),
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True, "disetujui": len(hasil), "hasil": hasil,
            "dilewati": dilewati, "gagal": gagal}


@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/usulan/{usulan_id}/tolak")
@limiter.limit("60/minute")
async def tolak_usulan(share_id: str, usulan_id: str, payload: TinjauIn,
                       request: Request,
                       user: dict = Depends(require_writer)):
    """Tolak satu usulan — usulannya TETAP tersimpan (jejak), tidak dihapus."""
    sh = await _pengelola_share(share_id, user)
    res = await db.peta_kolaborasi.update_one(
        {"id": usulan_id, "share_id": share_id, "dihapus": {"$ne": True},
         "status_usulan": {"$ne": "disetujui"}},
        {"$set": {"status_usulan": "ditolak",
                  "alasan_tolak": str(payload.alasan or "").strip()[:DEFAULT_MAKS_TEKS],
                  "ditinjau_oleh": user.get("username", "system"),
                  "ditinjau_pada": _now().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Usulan tidak ditemukan / sudah disetujui")
    await log_audit("tolak_usulan_peta", sh.get("activity_id", ""), usulan_id,
                    username=user.get("username", "system"),
                    detail="Usulan peta kolaborasi ditolak",
                    kode_satker=str(sh.get("kode_satker") or ""))
    return {"ok": True, "id": usulan_id}


# ── Komentar pada peta ASLI (hasil impor) ─────────────────────────────────
#
# Mandat pemilik: "dengan icon komentar di marker yang dikomentari (berikan
# fitur hapus perkomentar di peta asli nantinya)".

@peta_kolaborasi_router.get("/aset/komentar")
async def daftar_komentar_aset(activity_id: str = Query(...),
                               _user: dict = Depends(require_user)):
    """Komentar hasil impor untuk peta ASLI satu kegiatan, dikelompokkan per aset."""
    from shared_utils import pastikan_akses_kegiatan_id
    await pastikan_akses_kegiatan_id(_user, activity_id)
    q = scope_query_field_satker(_user, {"activity_id": activity_id,
                                         "dihapus": {"$ne": True}})
    items = await db.komentar_aset.find(q, _PROJ).sort("created_at", 1).to_list(5000)
    per_aset = {}
    for k in items:
        per_aset.setdefault(str(k.get("asset_id") or ""), []).append(k)
    return {"items": items, "per_aset": per_aset, "jumlah": len(items)}


@peta_kolaborasi_router.delete("/aset/komentar/{komentar_id}")
async def hapus_komentar_aset(komentar_id: str,
                              user: dict = Depends(require_writer)):
    """Hapus SATU komentar di peta asli (soft delete — jejaknya tetap ada)."""
    k = await db.komentar_aset.find_one({"id": komentar_id}, _PROJ)
    if not k:
        raise HTTPException(status_code=404, detail="Komentar tidak ditemukan")
    await pastikan_akses_dok_satker(user, k)   # isolasi: satker pemilik saja
    await db.komentar_aset.update_one(
        {"id": komentar_id},
        {"$set": {"dihapus": True, "dihapus_oleh": user.get("username", "system"),
                  "dihapus_pada": _now().isoformat()}})
    await log_audit("hapus_komentar_aset", str(k.get("activity_id") or ""),
                    komentar_id, username=user.get("username", "system"),
                    detail="Komentar aset (hasil usulan kolaborasi) dihapus",
                    kode_satker=str(k.get("kode_satker") or ""))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# USULAN GESER — tamu memindahkan marker aset ASLI
# ══════════════════════════════════════════════════════════════════════════
#
# Mandat pemilik: "bebaskan tamu kolaborasi menggeser marker asli peta …
# berikan garis putus putus tempat marker asli peta dengan titik barunya nanti
# dengan tampilan marker yang transparan … dapat dilihat juga melalui peta asli
# perubahannya dan akan berubah ketika disetujui."
#
# KEPUTUSAN YANG DINYATAKAN TERUS TERANG: menggeser marker asli TIDAK langsung
# mengubah koordinat aset. Ia tersimpan sebagai USULAN, sama seperti titik dan
# komentar. Alasannya bukan kehati-hatian berlebihan: pemegang tautan peta
# kolaborasi adalah SIAPA SAJA yang menerima tautannya. Menulis langsung ke
# `assets` berarti siapa pun yang meneruskan tautan itu bisa memindahkan titik
# BMN resmi tanpa jejak persetujuan. Karena itu "geser titik asli" berarti
# MENGUSULKAN KOREKSI POSISI — dan posisinya benar-benar berubah saat pengelola
# menyetujuinya, persis bunyi mandatnya.
#
# Selama menunggu, usulan tampil sebagai marker TRANSPARAN di posisi baru yang
# tersambung GARIS PUTUS-PUTUS ke posisi asal — di peta kolaborasi maupun di
# peta asli.

@peta_kolaborasi_router.post("/peta/kolaborasi/{share_id}/geser")
@limiter.limit("30/minute")
async def usul_geser_titik(share_id: str, payload: GeserIn, request: Request,
                           ctx: dict = Depends(require_user_or_map_token)):
    """Usul pemindahan posisi satu aset (marker asli peta)."""
    sh = await _muat_share(share_id)
    # Izinnya menumpang saklar "titik publik": pemilik peta yang mematikan
    # kontribusi titik jelas juga tak ingin posisinya diutak-atik.
    await _guard_kontribusi(sh, ctx, request, "izinkan_titik_publik",
                            "usulan geser titik")
    import math
    if not (math.isfinite(payload.lat) and math.isfinite(payload.lng)
            and -90 <= payload.lat <= 90 and -180 <= payload.lng <= 180):
        raise HTTPException(status_code=400, detail="Koordinat tidak valid")
    aset = await db.assets.find_one(
        {"id": str(payload.asset_id or ""),
         "activity_id": str(sh.get("activity_id") or ""),
         "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_name": 1, "asset_code": 1, "NUP": 1,
         "koordinat_latitude": 1, "koordinat_longitude": 1})
    if not aset:
        # Aset di LUAR kegiatan share ini tak boleh bisa disentuh lewat tautan
        # peta mana pun — pesannya sengaja tak membedakan "tak ada" dari "bukan
        # milik peta ini" supaya tautan tak jadi alat penebak keberadaan aset.
        raise HTTPException(status_code=404,
                            detail="Aset tidak ditemukan pada peta ini")
    lat_asal = _parse_coord(aset.get("koordinat_latitude"))
    lng_asal = _parse_coord(aset.get("koordinat_longitude"))
    oleh, tipe, uid = _pengontribusi(ctx, payload.oleh)
    now = _now().isoformat()
    # Satu penyumbang, satu usulan geser per aset: usulan LAMA yang masih
    # terbuka digantikan, bukan menumpuk. Tanpa ini satu orang yang menyeret
    # marker lima kali meninggalkan lima garis putus-putus ke titik yang sama.
    await db.peta_kolaborasi.update_many(
        {"share_id": share_id, "jenis": "geser", "asset_id": aset["id"],
         "oleh": oleh, "dihapus": {"$ne": True},
         "status_usulan": {"$ne": "disetujui"}},
        {"$set": {"dihapus": True, "dihapus_pada": now,
                  "dihapus_oleh": "diganti-usulan-baru"}})
    doc = {
        "id": str(uuid.uuid4()), "share_id": share_id, "jenis": "geser",
        "asset_id": aset["id"],
        "nama_titik": str(aset.get("asset_name") or "Aset"),
        "kode": str(aset.get("asset_code") or ""),
        "nup": str(aset.get("NUP") or ""),
        "lat": float(payload.lat), "lng": float(payload.lng),
        "lat_asal": lat_asal, "lng_asal": lng_asal,
        "keterangan": str(payload.keterangan or "").strip()[:DEFAULT_MAKS_TEKS],
        "oleh": oleh, "oleh_tipe": tipe, "oleh_user_id": uid,
        "ip": (request.client.host if request.client else ""),
        "created_at": now, "dihapus": False,
        **_stempel_asal(sh),
        "status_usulan": "terbuka",
    }
    await db.peta_kolaborasi.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k not in ("ip", "oleh_user_id")}


@peta_kolaborasi_router.get("/aset/usulan-geser")
async def daftar_usulan_geser(activity_id: str = Query(...),
                              _user: dict = Depends(require_user)):
    """Usulan geser yang MASIH menunggu, untuk digambar di peta ASLI.

    Inilah yang membuat "dapat dilihat juga melalui peta asli" benar-benar
    terjadi: petugas melihat garis putus-putus + marker transparan tanpa harus
    membuka tautan peta kolaborasi.
    """
    from shared_utils import pastikan_akses_kegiatan_id
    await pastikan_akses_kegiatan_id(_user, activity_id)
    q = scope_query_field_satker(_user, {
        "activity_id": activity_id, "jenis": "geser",
        "dihapus": {"$ne": True}})
    semua = await db.peta_kolaborasi.find(
        q, {"_id": 0, "ip": 0, "oleh_user_id": 0}).sort("created_at", 1).to_list(2000)
    items = [k for k in semua if _status_usulan(k) == "terbuka"]
    per_aset = {}
    for k in items:
        per_aset.setdefault(str(k.get("asset_id") or ""), []).append(k)
    return {"items": items, "per_aset": per_aset, "jumlah": len(items)}
