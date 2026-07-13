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
    info_tenggat_tahapan, rekap_anggaran, rekap_kalender, sanding_per_akun,
    sanding_per_triwulan, validate_tahapan_kalender,
    validate_transisi_anggaran, validate_usulan_anggaran,
)
from perencanaan_utils import snapshot_rkbmn

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
    rkbmn_id: str = ""                 # FK usulan RKBMN Perencanaan (#257)
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
            "per_triwulan": sanding_per_triwulan(items),
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


class TahapanKalenderIn(BaseModel):
    nama: str = Field(min_length=1)
    tanggal: str = Field(min_length=10, max_length=10)
    tahun_anggaran: str = Field(min_length=4, max_length=4)
    keterangan: str = ""


@penganggaran_router.get("/penganggaran/kalender")
async def list_kalender_penganggaran(_user: dict = Depends(require_user)):
    """Kalender tahapan (tenggat terdekat dulu) + pengingat sisa hari."""
    items = [t async for t in db.penganggaran_kalender.find({}, {"_id": 0})
             .sort("tanggal", 1).limit(200)]
    today_iso = datetime.now(timezone.utc).date().isoformat()
    for t in items:
        t["info_tenggat"] = info_tenggat_tahapan(t, today_iso)
    return {"items": items, "ringkasan": rekap_kalender(items, today_iso),
            "catatan": (
                "Tanggal tenggat konfigurabel — tenggat internal tiap K/L "
                "berbeda (surat edaran masing-masing); isi berdasar kalender "
                "penganggaran resmi unit Anda (pustaka §9.4).")}


@penganggaran_router.post("/penganggaran/kalender")
async def buat_tahapan_kalender(payload: TahapanKalenderIn,
                                admin: dict = Depends(require_admin)):
    """Daftarkan satu tahapan kalender penganggaran (admin)."""
    data = payload.model_dump()
    errors = validate_tahapan_kalender(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "nama": data["nama"].strip(),
        "tanggal": data["tanggal"].strip()[:10],
        "tahun_anggaran": data["tahun_anggaran"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "created_by": admin.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.penganggaran_kalender.insert_one({**record})
    record["info_tenggat"] = info_tenggat_tahapan(
        record, datetime.now(timezone.utc).date().isoformat())
    return record


@penganggaran_router.delete("/penganggaran/kalender/{tahapan_id}")
async def hapus_tahapan_kalender(tahapan_id: str,
                                 _admin: dict = Depends(require_admin)):
    """Hapus satu tahapan kalender (admin)."""
    res = await db.penganggaran_kalender.delete_one({"id": tahapan_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Tahapan tidak ditemukan")
    return {"ok": True}


async def _ambil_snapshot_rkbmn(rkbmn_id: str) -> dict:
    """Cari usulan RKBMN Perencanaan (bila id diisi) → snapshot FK; 404 bila
    hilang (tiru `_ambil_snapshot_penganggaran` #199)."""
    rid = str(rkbmn_id or "").strip()
    if not rid:
        return snapshot_rkbmn(None)
    u = await db.perencanaan_usulan.find_one(
        {"id": rid},
        {"_id": 0, "id": 1, "uraian": 1, "tahun_rkbmn": 1, "jenis": 1,
         "unit_pengusul": 1})
    if not u:
        raise HTTPException(status_code=404,
                            detail="Usulan RKBMN Perencanaan tidak ditemukan")
    return snapshot_rkbmn(u)


@penganggaran_router.post("/penganggaran")
async def buat_usulan_anggaran(payload: UsulanAnggaranIn,
                               user: dict = Depends(require_user)):
    """Buat usulan penganggaran (opsional tertaut aset + FK usulan RKBMN)."""
    data = payload.model_dump()
    errors = validate_usulan_anggaran(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    # FK ke simpul Perencanaan (§5A gap #4): bekukan snapshot RKBMN sumber.
    snap_rkbmn = await _ambil_snapshot_rkbmn(data.get("rkbmn_id"))
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
        **snap_rkbmn,
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
