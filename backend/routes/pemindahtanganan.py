"""PEMINDAHTANGANAN — Fase 6 tahap awal: register usulan berstatus.

PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 (pustaka §7): usulan multi-aset →
disetujui → dilaksanakan → selesai (SK Penghapusan). Dokumen wajib per
tahap mengunci transisi; peringatan tenggat lelang 6 bulan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemindahtanganan_utils import (
    BENTUK_PEMINDAHTANGANAN, DOKUMEN_PELAKSANAAN, STATUS_USULAN_PT,
    peringatan_pt, rekap_pt, validate_transisi_pt, validate_usulan_pt,
)

pemindahtanganan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "condition": 1}


class UsulanPtIn(BaseModel):
    bentuk: str
    pihak: str = Field(min_length=1)   # penerima hibah / pembeli / mitra / BUMN
    keterangan: str = ""
    asset_ids: list[str] = Field(min_length=1, max_length=100)


class TransisiPtIn(BaseModel):
    status: str
    nomor_persetujuan: str = ""
    tanggal_persetujuan: str = ""
    nomor_dokumen: str = ""            # risalah lelang / BAST / naskah hibah / PP
    ntpn: str = ""                     # bukti setor PNBP (penjualan)
    nomor_sk_penghapusan: str = ""
    catatan: str = ""


@pemindahtanganan_router.get("/pemindahtanganan")
async def list_pemindahtanganan(_user: dict = Depends(require_user)):
    """Register usulan (terbaru dulu) + ringkasan + peringatan tenggat."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [u async for u in db.pemindahtanganan.find({}, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    for u in items:
        u["peringatan"] = peringatan_pt(u, today_iso)
    return {"items": items, "ringkasan": rekap_pt(items),
            "label_status": STATUS_USULAN_PT,
            "label_bentuk": BENTUK_PEMINDAHTANGANAN,
            "label_dokumen": DOKUMEN_PELAKSANAAN,
            "catatan": (
                "Register penatausahaan: persetujuan bertingkat nilai (Pengguna "
                "delegasi PMK 4/2015 / KPKNL / Kanwil / DJKN / Presiden / DPR); "
                "hasil penjualan disetor seluruhnya ke Kas Negara; selesai = SK "
                "Penghapusan terbit (PMK 83/2016).")}


@pemindahtanganan_router.post("/pemindahtanganan")
async def buat_usulan_pt(payload: UsulanPtIn, user: dict = Depends(require_user)):
    """Buat usulan pemindahtanganan multi-aset (snapshot identitas)."""
    data = payload.model_dump()
    errors = validate_usulan_pt(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "harga": a.get("purchase_price"),
                          "kondisi": a.get("condition")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "bentuk": data["bentuk"],
        "pihak": data["pihak"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "status": "diusulkan",
        "nomor_persetujuan": "",
        "tanggal_persetujuan": "",
        "nomor_dokumen": "",
        "ntpn": "",
        "nomor_sk_penghapusan": "",
        "aset": aset_rows,
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemindahtanganan.insert_one({**record})
    return record


@pemindahtanganan_router.post("/pemindahtanganan/{usulan_id}/status")
async def transisi_pt(usulan_id: str, payload: TransisiPtIn,
                      admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (admin — gerbang persetujuan berdokumen)."""
    u = await db.pemindahtanganan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    data = payload.model_dump()
    errors = validate_transisi_pt(u, payload.status, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "updated_at": now}
    if payload.status == "disetujui":
        update["nomor_persetujuan"] = payload.nomor_persetujuan.strip()
        update["tanggal_persetujuan"] = (str(payload.tanggal_persetujuan or "").strip()[:10]
                                         or now[:10])
    if payload.status == "dilaksanakan":
        update["nomor_dokumen"] = payload.nomor_dokumen.strip()
        if payload.ntpn:
            update["ntpn"] = payload.ntpn.strip()
    if payload.status == "selesai":
        update["nomor_sk_penghapusan"] = payload.nomor_sk_penghapusan.strip()
    res = await db.pemindahtanganan.find_one_and_update(
        # Anti-balapan: status lama diikutkan di filter
        {"id": usulan_id, "status": u["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status usulan berubah oleh proses lain — muat ulang")
    return res


@pemindahtanganan_router.delete("/pemindahtanganan/{usulan_id}")
async def hapus_usulan_pt(usulan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus usulan salah input (hanya status diusulkan)."""
    res = await db.pemindahtanganan.delete_one(
        {"id": usulan_id, "status": "diusulkan"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    return {"ok": True, "id": usulan_id}
