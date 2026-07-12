"""PENGANGGARAN — Fase 4 tahap awal: register usulan berstatus.

PMK 62/2023 + PMK 153/2021 (pustaka §9): jejak usulan dari kertas kerja
RKBMN menuju anggaran — diusulkan → disetujui telaah → masuk DIPA →
terealisasi. Nilai per tahap tercatat (usulan/disetujui/DIPA/realisasi);
kanal resmi tetap SIMAN V2 (RKBMN) & SAKTI (RKA/DIPA) — AMAN mencatat
jejak per usulan/aset, bukan memutus. Sanding rencana vs realisasi +
pengingat kalender menyusul sesuai masterplan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from penganggaran_utils import (
    AKUN_BAS, JENIS_ANGGARAN, STATUS_ANGGARAN,
    rekap_anggaran, sanding_per_akun, validate_transisi_anggaran,
    validate_usulan_anggaran,
)

penganggaran_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "condition": 1}


class UsulanAnggaranIn(BaseModel):
    jenis: str
    uraian: str = Field(min_length=1)
    tahun_anggaran: str = Field(min_length=4, max_length=4)
    nilai_usulan: float = Field(gt=0)
    akun: str = ""                     # pilihan BAS ringkas (53x/523)
    sumber: str = ""                   # mis. "Kertas kerja RKBMN 2027"
    keterangan: str = ""
    asset_ids: list[str] = Field(default_factory=list, max_length=100)


class TransisiAnggaranIn(BaseModel):
    status: str
    nomor_hasil_penelaahan: str = ""
    nilai_disetujui: float = 0
    nomor_dipa: str = ""
    nilai_dipa: float = 0
    nilai_realisasi: float = 0
    catatan: str = ""


@penganggaran_router.get("/penganggaran")
async def list_penganggaran(_user: dict = Depends(require_user)):
    """Register usulan (terbaru dulu) + ringkasan + label."""
    items = [u async for u in db.penganggaran.find({}, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_anggaran(items),
            "per_akun": sanding_per_akun(items),
            "label_status": STATUS_ANGGARAN,
            "label_jenis": {k: v[0] for k, v in JENIS_ANGGARAN.items()},
            "label_akun": AKUN_BAS,
            "catatan": (
                "Register pendamping: RKBMN resmi via SIMAN V2, RKA/DIPA via "
                "SAKTI, Renja via KRISNA. Status diisi berdasar dokumen resmi "
                "(RKBMN Hasil Penelaahan, DIPA petikan) dan tidak berkekuatan "
                "hukum.")}


@penganggaran_router.get("/penganggaran/export")
async def export_penganggaran(_user: dict = Depends(require_user)):
    """Ekspor CSV register usulan penganggaran (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["tahun_anggaran", "jenis", "akun", "uraian", "status",
                "nilai_usulan", "nilai_disetujui", "nilai_dipa",
                "nilai_realisasi", "nomor_dipa", "jumlah_aset", "sumber",
                "keterangan", "dibuat_oleh"])
    async for u in db.penganggaran.find({}, {"_id": 0}).sort("created_at", -1):
        akun = u.get("akun") or ""
        w.writerow([
            u.get("tahun_anggaran"),
            JENIS_ANGGARAN.get(u.get("jenis"), (u.get("jenis"),))[0],
            f"{akun} — {AKUN_BAS[akun]}" if akun in AKUN_BAS else akun,
            u.get("uraian"),
            STATUS_ANGGARAN.get(u.get("status"), u.get("status")),
            u.get("nilai_usulan"), u.get("nilai_disetujui"),
            u.get("nilai_dipa"), u.get("nilai_realisasi"),
            u.get("nomor_dipa"), len(u.get("aset") or []),
            u.get("sumber"), u.get("keterangan"), u.get("created_by"),
        ])
    return HttpResponse(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="register_penganggaran.csv"'})


@penganggaran_router.post("/penganggaran")
async def buat_usulan_anggaran(payload: UsulanAnggaranIn,
                               user: dict = Depends(require_user)):
    """Buat usulan penganggaran (opsional tertaut aset — snapshot identitas)."""
    data = payload.model_dump()
    errors = validate_usulan_anggaran(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data.get("asset_ids") or []):
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "kondisi": a.get("condition")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "jenis": data["jenis"],
        "uraian": data["uraian"].strip(),
        "tahun_anggaran": data["tahun_anggaran"].strip(),
        "nilai_usulan": float(data["nilai_usulan"]),
        "akun": str(data.get("akun") or "").strip(),
        "sumber": str(data.get("sumber") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "status": "diusulkan",
        "nomor_hasil_penelaahan": "",
        "nilai_disetujui": 0,
        "nomor_dipa": "",
        "nilai_dipa": 0,
        "nilai_realisasi": 0,
        "aset": aset_rows,
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.penganggaran.insert_one({**record})
    return record


@penganggaran_router.post("/penganggaran/{usulan_id}/status")
async def transisi_anggaran(usulan_id: str, payload: TransisiAnggaranIn,
                            admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (admin — nilai/dokumen wajib per tahap)."""
    u = await db.penganggaran.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    data = payload.model_dump()
    errors = validate_transisi_anggaran(u, payload.status, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "updated_at": now}
    if payload.status == "disetujui_telaah":
        update["nilai_disetujui"] = float(payload.nilai_disetujui)
        if payload.nomor_hasil_penelaahan:
            update["nomor_hasil_penelaahan"] = payload.nomor_hasil_penelaahan.strip()
    if payload.status == "masuk_dipa":
        update["nomor_dipa"] = payload.nomor_dipa.strip()
        update["nilai_dipa"] = float(payload.nilai_dipa)
    if payload.status == "terealisasi":
        update["nilai_realisasi"] = float(payload.nilai_realisasi)
    res = await db.penganggaran.find_one_and_update(
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


@penganggaran_router.delete("/penganggaran/{usulan_id}")
async def hapus_usulan_anggaran(usulan_id: str,
                                _admin: dict = Depends(require_admin)):
    """Hapus usulan salah input (hanya status diusulkan)."""
    res = await db.penganggaran.delete_one(
        {"id": usulan_id, "status": "diusulkan"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    return {"ok": True, "id": usulan_id}
