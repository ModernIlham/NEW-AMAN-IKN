"""Pemantauan kuota email Resend — indikator penggunaan harian & bulanan.

Semua email keluar aplikasi menempuh Resend (OTP registrasi, OTP lupa password,
link tanda tangan elektronik, dst.) dan dicatat di choke point pengiriman
(`shared_utils.catat_email_terkirim`). Modul ini MENYAJIKAN rekap itu +
mengelola BATAS (limit) yang dapat diubah admin bila Resend mengubah
ketentuannya — sehingga penggunaan tetap terpantau meski limit berubah.

Batas plan gratis Resend saat ini: 100 email/hari & 3000 email/bulan.
Penghitungan pakai kalender UTC, selaras reset kuota harian Resend.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth_utils import require_admin, require_super_admin
from db import db
from shared_utils import (
    RESEND_API_KEY, SENDER_EMAIL, RESEND_LIMIT_HARIAN_DEFAULT,
    RESEND_LIMIT_BULANAN_DEFAULT, _periode_email,
)

email_monitor_router = APIRouter()

# Label ramah untuk tiap jenis email (kunci teknis → tampilan Indonesia).
LABEL_JENIS = {
    "otp_registrasi": "OTP Registrasi",
    "otp_reset": "OTP Lupa Password",
    "esign": "Link Tanda Tangan (e-sign)",
    "lainnya": "Lainnya",
}


class LimitIn(BaseModel):
    limit_harian: int
    limit_bulanan: int


async def _config() -> dict:
    doc = await db.email_usage.find_one(
        {"lingkup": "config", "periode": "config"}, {"_id": 0}) or {}
    return doc


def _int(v, default):
    try:
        n = int(v)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _bagian(doc: dict, limit: int) -> dict:
    """Bentuk ringkasan satu lingkup (harian/bulanan) untuk indikator."""
    total = int((doc or {}).get("total") or 0)
    per_jenis = (doc or {}).get("per_jenis") or {}
    sisa = max(0, limit - total)
    persen = round(min(100.0, (total / limit * 100.0)) if limit else 0.0, 1)
    status = "aman"
    if limit and total >= limit:
        status = "penuh"
    elif limit and total >= 0.8 * limit:
        status = "hampir"
    rincian = sorted(
        ({"jenis": k, "label": LABEL_JENIS.get(k, k), "jumlah": int(v)}
         for k, v in per_jenis.items() if int(v or 0) > 0),
        key=lambda x: -x["jumlah"])
    return {"terpakai": total, "limit": limit, "sisa": sisa,
            "persen": persen, "status": status, "rincian": rincian}


@email_monitor_router.get("/email/usage")
async def email_usage(_user: dict = Depends(require_admin)):
    """Rekap penggunaan email Resend hari ini & bulan ini + batas & riwayat."""
    hari, bulan = _periode_email()
    cfg = await _config()
    limit_h = _int(cfg.get("limit_harian"), RESEND_LIMIT_HARIAN_DEFAULT)
    limit_b = _int(cfg.get("limit_bulanan"), RESEND_LIMIT_BULANAN_DEFAULT)

    doc_h = await db.email_usage.find_one(
        {"lingkup": "harian", "periode": hari}, {"_id": 0}) or {}
    doc_b = await db.email_usage.find_one(
        {"lingkup": "bulanan", "periode": bulan}, {"_id": 0}) or {}

    # Riwayat 14 hari terakhir (untuk grafik ringkas) — urut naik.
    riwayat_docs = await db.email_usage.find(
        {"lingkup": "harian"}, {"_id": 0, "periode": 1, "total": 1}
    ).sort("periode", -1).to_list(14)
    riwayat = [{"tanggal": d["periode"], "total": int(d.get("total") or 0)}
               for d in reversed(riwayat_docs)]

    # Sinyal OTOMATIS: Resend menolak karena kuota — tampil hanya bila masih
    # dalam periode berjalan (harian=hari ini, bulanan=bulan ini).
    kt = cfg.get("kuota_tercapai") or {}
    tercapai = {}
    for lingkup, periode_now in (("harian", hari), ("bulanan", bulan)):
        info = kt.get(lingkup)
        if not info:
            continue
        pada = str(info.get("pada") or "")
        cocok = (pada[:10] == hari) if lingkup == "harian" else (pada[:7] == bulan)
        if cocok:
            tercapai[lingkup] = {"pada": pada, "pesan": info.get("pesan", "")}

    return {
        "resend_terkonfigurasi": bool(RESEND_API_KEY),
        "pengirim": SENDER_EMAIL,
        "periode": {"hari": hari, "bulan": bulan, "zona": "UTC"},
        "harian": _bagian(doc_h, limit_h),
        "bulanan": _bagian(doc_b, limit_b),
        "riwayat_harian": riwayat,
        "kuota_tercapai": tercapai,
        "limit_default": {"harian": RESEND_LIMIT_HARIAN_DEFAULT,
                          "bulanan": RESEND_LIMIT_BULANAN_DEFAULT},
    }


@email_monitor_router.put("/email/limit")
async def set_email_limit(payload: LimitIn,
                          _user: dict = Depends(require_super_admin)):
    """Ubah batas kuota email (super-admin) — dipakai bila Resend mengubah
    ketentuan limit di kemudian hari, tanpa perlu deploy ulang."""
    lh = max(1, min(1_000_000, int(payload.limit_harian)))
    lb = max(1, min(50_000_000, int(payload.limit_bulanan)))
    await db.email_usage.update_one(
        {"lingkup": "config", "periode": "config"},
        {"$set": {"limit_harian": lh, "limit_bulanan": lb,
                  "updated_at": datetime.now(timezone.utc)}},
        upsert=True)
    return {"ok": True, "limit_harian": lh, "limit_bulanan": lb}
