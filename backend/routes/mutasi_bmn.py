"""Pembukuan — Jurnal Mutasi BMN & Reklasifikasi (Gelombang 7, pustaka §2.6).

Koleksi `mutasi_bmn` append-only = "Buku Barang" AMAN: jurnal transaksi
ber-kode per aset (pola SIMAK/SAKTI). Endpoint reklasifikasi memutakhirkan
kode+NUP aset IN-PLACE (id internal & kode register SIMAN tidak berubah)
sambil merekam pasangan 304/107 dan riwayat pada dokumen aset.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from kodefikasi_utils import normalize_kode, validate_kode
from mutasi_bmn_utils import (
    KODE_TRANSAKSI_BMN, buat_pasangan_reklasifikasi, validate_entri_mutasi,
)
from shared_utils import log_audit

mutasi_bmn_router = APIRouter()

_PROJ = {"_id": 0}


class ReklasifikasiIn(BaseModel):
    asset_id: str
    kode_baru: str
    alasan: Optional[str] = ""
    tanggal_buku: Optional[str] = ""   # default hari ini


@mutasi_bmn_router.get("/pembukuan/mutasi")
async def daftar_mutasi(asset_id: str = "", kode_transaksi: str = "",
                        dari: str = "", sampai: str = "", page: int = 1,
                        page_size: int = 50,
                        _user: dict = Depends(require_user)):
    """Jurnal mutasi BMN (Buku Barang) — terbaru dulu, filter opsional."""
    page, page_size = max(1, page), min(max(1, page_size), 200)
    q = {}
    if asset_id.strip():
        q["asset_id"] = asset_id.strip()
    if kode_transaksi.strip():
        q["kode_transaksi"] = kode_transaksi.strip()
    if dari.strip() or sampai.strip():
        rentang = {}
        if dari.strip():
            rentang["$gte"] = dari.strip()[:10]
        if sampai.strip():
            rentang["$lte"] = sampai.strip()[:10]
        q["tanggal_buku"] = rentang
    total = await db.mutasi_bmn.count_documents(q)
    items = await (db.mutasi_bmn.find(q, _PROJ)
                   .sort([("tanggal_buku", -1), ("created_at", -1)])
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "label_kode": {k: v[0] for k, v in KODE_TRANSAKSI_BMN.items()}}


@mutasi_bmn_router.post("/pembukuan/mutasi/backfill")
async def backfill_saldo_awal(admin: dict = Depends(require_admin)):
    """Backfill sekali (idempoten): aset aktif TANPA entri jurnal apa pun
    diberi satu entri sintetis **100 Saldo Awal** (tanggal buku = tanggal
    perolehan, fallback created_at) — riset G7: aset tanpa jejak transaksi
    tetap harus punya titik awal di Buku Barang."""
    import uuid as _uuid

    from pembukuan_utils import parse_harga

    sudah = set()
    async for m in db.mutasi_bmn.find({}, {"_id": 0, "asset_id": 1}):
        sudah.add(m.get("asset_id"))
    dibuat = 0
    now = datetime.now(timezone.utc).isoformat()
    async for a in db.assets.find(
            {"dihapus": {"$ne": True}},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1,
             "purchase_price": 1, "purchase_date": 1, "created_at": 1}):
        if a["id"] in sudah:
            continue
        tgl = (str(a.get("purchase_date") or "").strip()[:10]
               or str(a.get("created_at") or now)[:10])
        if len(tgl) != 10 or tgl[4] != "-":
            tgl = now[:10]
        await db.mutasi_bmn.insert_one({
            "id": str(_uuid.uuid4()), "asset_id": a["id"],
            "kode_transaksi": "100",
            "kode_barang": str(a.get("asset_code") or ""),
            "nup": str(a.get("NUP") or ""),
            "tanggal_buku": tgl, "jumlah": 1,
            "nilai": parse_harga(a.get("purchase_price")),
            "sumber_modul": "backfill", "ref_id": "",
            "keterangan": "Saldo awal sintetis (backfill Buku Barang)",
            "oleh": admin.get("username", "system"),
            "created_at": now})
        dibuat += 1
    await log_audit("backfill_mutasi_bmn", "", username=admin.get("username", "system"),
                    detail=f"Backfill saldo awal Buku Barang: {dibuat} aset")
    return {"dibuat": dibuat, "sudah_berjurnal": len(sudah)}


async def _nup_berikut_kode(kode_baru: str) -> str:
    """NUP berikut pada kode tujuan (increment NUP numerik terbesar)."""
    res = await db.assets.aggregate([
        {"$match": {"asset_code": kode_baru, "dihapus": {"$ne": True}}},
        {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
            "input": "$NUP", "to": "int",
            "onError": None, "onNull": None}}}}},
    ]).to_list(1)
    return str(int((res[0].get("max_nup") if res else None) or 0) + 1)


@mutasi_bmn_router.post("/pembukuan/reklasifikasi")
async def reklasifikasi_aset(payload: ReklasifikasiIn,
                             user: dict = Depends(require_user)):
    """Reklasifikasi kodefikasi aset (SAKTI 304/107, riset §3):
    kode+NUP dimutakhirkan IN-PLACE (aset tidak dibuat ulang — nilai &
    tanggal perolehan, id internal, dan kode register SIMAN tetap), NUP baru
    berurut pada kode tujuan, riwayat tercatat pada aset + pasangan jurnal
    304/107 pada `mutasi_bmn` (periode sama, nilai bruto sama)."""
    kode_baru = normalize_kode(payload.kode_baru)
    ok, err = validate_kode(kode_baru)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    if len(kode_baru) != 10:
        raise HTTPException(status_code=400,
                            detail="Kode tujuan harus kode barang penuh 10 digit (sub-sub kelompok)")
    if kode_baru.startswith("1"):
        raise HTTPException(status_code=400, detail=(
            "Kode berawalan '1' = persediaan — reklasifikasi aset→persediaan "
            "tidak dilakukan di sini (rekam keluar aset + masuk persediaan)"))

    aset = await db.assets.find_one(
        {"id": payload.asset_id, "dihapus": {"$ne": True}}, _PROJ)
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if normalize_kode(aset.get("asset_code")) == kode_baru:
        raise HTTPException(status_code=400,
                            detail="Kode tujuan sama dengan kode sekarang")

    now = datetime.now(timezone.utc)
    tgl_buku = (str(payload.tanggal_buku or "").strip()[:10]
                or now.date().isoformat())
    nup_baru = await _nup_berikut_kode(kode_baru)
    oleh = user.get("username", "system")

    keluar, masuk = buat_pasangan_reklasifikasi(
        aset, kode_baru, nup_baru, tgl_buku, payload.alasan, oleh)
    for e in (keluar, masuk):
        errs = validate_entri_mutasi(e)
        if errs:
            raise HTTPException(status_code=400, detail="; ".join(errs))
        e.update({"id": str(uuid.uuid4()), "created_at": now.isoformat()})
    await db.mutasi_bmn.insert_one({**keluar})
    await db.mutasi_bmn.insert_one({**masuk})

    riwayat = {
        "kode_lama": aset.get("asset_code"), "nup_lama": aset.get("NUP"),
        "kode_baru": kode_baru, "nup_baru": nup_baru,
        "tanggal": tgl_buku, "alasan": str(payload.alasan or "").strip(),
        "oleh": oleh,
    }
    await db.assets.update_one(
        {"id": payload.asset_id},
        {"$set": {"asset_code": kode_baru, "NUP": nup_baru,
                  "updated_at": now.isoformat()},
         "$push": {"riwayat_reklasifikasi": riwayat},
         "$inc": {"version": 1}})
    await log_audit("reklasifikasi_aset", "", payload.asset_id,
                    username=oleh,
                    detail=(f"Reklasifikasi {riwayat['kode_lama']}/"
                            f"{riwayat['nup_lama']} → {kode_baru}/{nup_baru}"))
    return {"ok": True, "kode_baru": kode_baru, "nup_baru": nup_baru,
            "riwayat": riwayat}
