"""Register TGR aset hilang — ASET-TGR (PP 38/2016; PMK 83/PMK.06/2016).

Tiket per aset "Tidak Ditemukan": penelusuran → telaah TPKN → keputusan
(TGR ditetapkan / bebas TGR) → lunas. Gerbang pasangannya ada di
routes/penghapusan.py: SK penghapusan jalur tidak_ditemukan DITOLAK selama
belum ada tiket TGR berkeputusan untuk aset itu — SK aset hilang tidak
boleh terbit tanpa bukti proses TGR terekam.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_writer
from db import db
from penghapusan_utils import jalur_kandidat
from shared_utils import (kode_satker_user, log_audit,
                          pastikan_akses_dok_satker,
                          scope_query_field_satker)
from tgr_utils import (STATUS_TGR, STATUS_TGR_BERKEPUTUSAN, TRANSISI_TGR,
                       validate_tiket_tgr_baru, validate_transisi_tgr)

tgr_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "inventory_status": 1,
              "uraian_tidak_ditemukan": 1, "condition": 1, "activity_id": 1}


class TiketTgrIn(BaseModel):
    asset_id: str = Field(min_length=1)
    penanggung_jawab: str = ""
    nip_penanggung_jawab: str = ""
    kronologi: str = ""


class TransisiTgrIn(BaseModel):
    status: str
    nomor_dokumen: str = ""
    tanggal_dokumen: str = ""
    nilai_ganti_rugi: float = 0
    catatan: str = ""


@tgr_router.post("/tgr")
async def buka_tiket_tgr(payload: TiketTgrIn,
                         user: dict = Depends(require_writer)):
    """Buka tiket TGR untuk satu aset hilang (jalur Tidak Ditemukan)."""
    from shared_utils import pastikan_akses_aset
    asset = await db.assets.find_one({"id": payload.asset_id}, _PROJ_ASET)
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, asset)
    if jalur_kandidat(asset) != "tidak_ditemukan":
        raise HTTPException(
            status_code=400,
            detail="TGR hanya untuk aset berstatus Tidak Ditemukan — "
                   "aset ini bukan kandidat aset hilang")
    errors = validate_tiket_tgr_baru(payload.kronologi,
                                     payload.penanggung_jawab)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aktif = await db.tgr_register.find_one(
        {"asset_id": payload.asset_id, "status": {"$ne": "dibatalkan"}},
        {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(status_code=409,
                            detail="Aset ini sudah punya tiket TGR aktif")
    now = datetime.now(timezone.utc).isoformat()
    from shared_utils import kode_satker_efektif_dari_aset
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": await kode_satker_efektif_dari_aset(
            user, [asset["id"]]),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "penanggung_jawab": payload.penanggung_jawab.strip(),
        "nip_penanggung_jawab": payload.nip_penanggung_jawab.strip(),
        "kronologi": payload.kronologi.strip(),
        "status": "penelusuran",
        "nomor_dokumen": "",
        "tanggal_dokumen": "",
        "nilai_ganti_rugi": 0,
        "riwayat": [{"status": "penelusuran", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.tgr_register.insert_one({**record})
    await log_audit("tgr_buka", "", record["id"],
                    username=user.get("username", "system"),
                    detail=(f"TGR {asset.get('asset_code')}/{asset.get('NUP')} "
                            f"{asset.get('asset_name')}"))
    return record


@tgr_router.get("/tgr")
async def daftar_tgr(_user: dict = Depends(require_user)):
    q = scope_query_field_satker(_user)
    items = await (db.tgr_register.find(q, {"_id": 0})
                   .sort("created_at", -1).to_list(500))
    berjalan = sum(1 for it in items
                   if it.get("status") in ("penelusuran", "telaah"))
    return {"items": items, "label_status": STATUS_TGR,
            "transisi": {k: sorted(v) for k, v in TRANSISI_TGR.items()},
            "ringkasan": {"total": len(items), "berjalan": berjalan}}


@tgr_router.post("/tgr/{tiket_id}/status")
async def transisi_tgr(tiket_id: str, payload: TransisiTgrIn,
                       admin: dict = Depends(require_admin)):
    """Pindahkan status tiket TGR (admin — keputusan berdampak SK
    penghapusan; dokumen wajib divalidasi tgr_utils)."""
    t = await db.tgr_register.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket TGR tidak ditemukan")
    await pastikan_akses_dok_satker(admin, t)
    errors = validate_transisi_tgr(t["status"], payload.status,
                                   payload.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "updated_at": now}
    if payload.status in ("tgr_ditetapkan", "bebas_tgr", "lunas"):
        update["nomor_dokumen"] = payload.nomor_dokumen.strip()
        update["tanggal_dokumen"] = str(payload.tanggal_dokumen or "").strip()[:10]
    if payload.status == "tgr_ditetapkan":
        update["nilai_ganti_rugi"] = float(payload.nilai_ganti_rugi or 0)
    res = await db.tgr_register.find_one_and_update(
        # Anti-balapan: status lama diikutkan di filter.
        {"id": tiket_id, "status": t["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        return_document=True)
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Status tiket berubah oleh proses lain — muat ulang")
    res.pop("_id", None)
    await log_audit("tgr_transisi", "", tiket_id,
                    username=admin.get("username", "system"),
                    detail=(f"{STATUS_TGR.get(t['status'], t['status'])} → "
                            f"{STATUS_TGR.get(payload.status, payload.status)}"
                            + (f" ({payload.nomor_dokumen})"
                               if payload.nomor_dokumen else "")))
    return res


@tgr_router.get("/tgr/export")
async def export_tgr(_user: dict = Depends(require_user)):
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["kode_barang", "nup", "nama_aset", "penanggung_jawab",
                "nip", "status", "nomor_dokumen", "tanggal_dokumen",
                "nilai_ganti_rugi", "kronologi", "tanggal_buka",
                "dibuat_oleh"])
    async for t in db.tgr_register.find(
            scope_query_field_satker(_user), {"_id": 0}).sort("created_at", -1):
        w.writerow([
            t.get("asset_code"), t.get("NUP"), t.get("asset_name"),
            t.get("penanggung_jawab"), t.get("nip_penanggung_jawab"),
            STATUS_TGR.get(t.get("status"), t.get("status")),
            t.get("nomor_dokumen"), t.get("tanggal_dokumen"),
            int(t.get("nilai_ganti_rugi") or 0), t.get("kronologi"),
            str(t.get("created_at") or "")[:10], t.get("created_by"),
        ])
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_tgr.csv"'})


@tgr_router.delete("/tgr/{tiket_id}")
async def hapus_tiket_tgr(tiket_id: str, admin: dict = Depends(require_admin)):
    """Hapus tiket — hanya status penelusuran (belum ada telaah/keputusan)."""
    t = await db.tgr_register.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket TGR tidak ditemukan")
    await pastikan_akses_dok_satker(admin, t)
    if t.get("status") != "penelusuran":
        raise HTTPException(
            status_code=400,
            detail="Hanya tiket berstatus Penelusuran yang boleh dihapus — "
                   "tiket ber-telaah/keputusan adalah arsip proses")
    await db.tgr_register.delete_one({"id": tiket_id})
    await log_audit("tgr_hapus", "", tiket_id,
                    username=admin.get("username", "system"),
                    detail=f"{t.get('asset_code')}/{t.get('NUP')}")
    return {"message": "Tiket TGR dihapus"}


async def tgr_berkeputusan_untuk(asset_id: str) -> bool:
    """Dipakai gerbang SK penghapusan: adakah tiket TGR aset ini yang sudah
    berkeputusan (ditetapkan/bebas/lunas)?"""
    t = await db.tgr_register.find_one(
        {"asset_id": asset_id,
         "status": {"$in": sorted(STATUS_TGR_BERKEPUTUSAN)}},
        {"_id": 0, "id": 1})
    return bool(t)
