"""PELAPORAN — periode pelaporan ber-kunci (pustaka §2.3).

Register periode (Semester I/II/Tahunan per tahun) berstatus terbuka →
terkunci. Saat terkunci, PDF LBKP & CaLBMN periode itu diberi penanda
FINAL. Kunci dapat dibuka kembali oleh admin dengan alasan (riwayat
tercatat) — jejak tidak pernah dihapus.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pelaporan_utils import (
    STATUS_PERIODE, info_tenggat_periode, kunci_unik_periode,
    label_periode_pelaporan, rekap_periode, validate_buka_periode,
    validate_kunci_periode, validate_periode, validate_tenggat,
)

pelaporan_router = APIRouter()


class PeriodeIn(BaseModel):
    tahun: int = Field(ge=2000, le=2100)
    semester: int | None = None       # 1 | 2 | None (tahunan)
    catatan: str = ""


class BukaKunciIn(BaseModel):
    alasan: str = Field(min_length=1)


class TenggatIn(BaseModel):
    tenggat: str = ""                 # YYYY-MM-DD; kosong = hapus tenggat


@pelaporan_router.get("/pelaporan/periode")
async def daftar_periode(_user: dict = Depends(require_user)):
    """Register periode pelaporan (terbaru dulu) + tenggat aktif + rekap."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [p async for p in db.periode_pelaporan.find({}, {"_id": 0})
             .sort([("tahun", -1), ("semester", -1)]).limit(200)]
    lewat = 0
    for p in items:
        p["info_tenggat"] = info_tenggat_periode(p, today_iso)
        if p["info_tenggat"]["lewat"]:
            lewat += 1
    ringkasan = rekap_periode(items)
    ringkasan["lewat_tenggat"] = lewat
    return {"items": items, "ringkasan": ringkasan,
            "label_status": STATUS_PERIODE,
            "catatan": (
                "Periode terkunci menandai laporan periode itu FINAL — PDF "
                "LBKP & CaLBMN diberi penanda; membuka kembali kunci wajib "
                "beralasan dan tercatat pada riwayat. Tenggat penyampaian "
                "dapat diatur per periode mengikuti surat DJKN/K/L.")}


@pelaporan_router.post("/pelaporan/periode")
async def buat_periode(payload: PeriodeIn, user: dict = Depends(require_admin)):
    """Daftarkan periode pelaporan baru (admin — seluruh siklus hidup periode
    kunci/buka/hapus/tenggat juga admin-only)."""
    data = payload.model_dump()
    errors = validate_periode(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    kunci = kunci_unik_periode(data["tahun"], data.get("semester"))
    if await db.periode_pelaporan.find_one({"kunci_unik": kunci}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Periode sudah terdaftar")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "kunci_unik": kunci,
        "tahun": data["tahun"],
        "semester": data.get("semester"),
        "label": label_periode_pelaporan(data["tahun"], data.get("semester")),
        "status": "terbuka",
        "tenggat": "",
        "tanggal_kunci": "",
        "dikunci_oleh": "",
        "catatan": str(data.get("catatan") or "").strip(),
        "riwayat": [{"aksi": "dibuat", "tanggal": now,
                     "oleh": user.get("username"), "alasan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.periode_pelaporan.insert_one({**record})
    return record


@pelaporan_router.post("/pelaporan/periode/{periode_id}/kunci")
async def kunci_periode(periode_id: str, admin: dict = Depends(require_admin)):
    """Kunci periode (admin) — laporan periode itu menjadi FINAL."""
    p = await db.periode_pelaporan.find_one({"id": periode_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Periode tidak ditemukan")
    errors = validate_kunci_periode(p)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    res = await db.periode_pelaporan.find_one_and_update(
        # Anti-balapan: hanya periode yang masih terbuka
        {"id": periode_id, "status": "terbuka"},
        {"$set": {"status": "terkunci", "tanggal_kunci": now,
                  "dikunci_oleh": admin.get("username"), "updated_at": now},
         "$push": {"riwayat": {"aksi": "dikunci", "tanggal": now,
                               "oleh": admin.get("username"), "alasan": ""}}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Periode berubah oleh proses lain — muat ulang")
    return res


@pelaporan_router.post("/pelaporan/periode/{periode_id}/buka")
async def buka_periode(periode_id: str, payload: BukaKunciIn,
                       admin: dict = Depends(require_admin)):
    """Buka kembali periode terkunci (admin, wajib beralasan)."""
    p = await db.periode_pelaporan.find_one({"id": periode_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Periode tidak ditemukan")
    data = payload.model_dump()
    errors = validate_buka_periode(p, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    res = await db.periode_pelaporan.find_one_and_update(
        {"id": periode_id, "status": "terkunci"},
        {"$set": {"status": "terbuka", "tanggal_kunci": "",
                  "dikunci_oleh": "", "updated_at": now},
         "$push": {"riwayat": {"aksi": "dibuka", "tanggal": now,
                               "oleh": admin.get("username"),
                               "alasan": data["alasan"].strip()}}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Periode berubah oleh proses lain — muat ulang")
    return res


@pelaporan_router.post("/pelaporan/periode/{periode_id}/tenggat")
async def atur_tenggat_periode(periode_id: str, payload: TenggatIn,
                               admin: dict = Depends(require_admin)):
    """Atur/hapus tenggat penyampaian periode terbuka (admin)."""
    p = await db.periode_pelaporan.find_one({"id": periode_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Periode tidak ditemukan")
    if p.get("status") != "terbuka":
        raise HTTPException(status_code=400,
                            detail="Tenggat hanya dapat diubah saat periode terbuka")
    data = payload.model_dump()
    errors = validate_tenggat(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    tenggat = str(data.get("tenggat") or "").strip()[:10]
    now = datetime.now(timezone.utc).isoformat()
    res = await db.periode_pelaporan.find_one_and_update(
        {"id": periode_id, "status": "terbuka"},
        {"$set": {"tenggat": tenggat, "updated_at": now},
         "$push": {"riwayat": {"aksi": "tenggat", "tanggal": now,
                               "oleh": admin.get("username"),
                               "alasan": tenggat or "(dihapus)"}}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Periode berubah oleh proses lain — muat ulang")
    res["info_tenggat"] = info_tenggat_periode(
        res, datetime.now(timezone.utc).date().isoformat())
    return res


@pelaporan_router.delete("/pelaporan/periode/{periode_id}")
async def hapus_periode(periode_id: str, _admin: dict = Depends(require_admin)):
    """Hapus periode salah input (hanya yang masih terbuka)."""
    res = await db.periode_pelaporan.delete_one(
        {"id": periode_id, "status": "terbuka"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Periode tidak ditemukan atau terkunci (buka dulu kuncinya)")
    return {"ok": True, "id": periode_id}


# ============================================================================
# ARSIP LAPORAN LINTAS KEGIATAN (Mandat-2, M-MODUL — butir terakhir Pelaporan)
# ============================================================================

@pelaporan_router.get("/pelaporan/arsip")
async def arsip_laporan(q: str = "", _user: dict = Depends(require_user)):
    """Arsip laporan LINTAS KEGIATAN & LINTAS PERIODE dalam satu daftar:

    1. Naskah keluar ber-jenis Laporan/Berita Acara dari Registrasi Persuratan
       (ber-NOMOR resmi + status booking/disahkan = riwayatnya).
    2. Kegiatan inventarisasi DISAHKAN (paket 13+ laporan finalnya).
    3. Periode pelaporan TERKUNCI (LBKP/CaLBMN berpenanda FINAL).

    Semuanya sumber data yang sudah ada — arsip ini menyatukannya (tidak
    membuat penomoran baru). Hasil terurut terbaru dulu.
    """
    s = str(q or "").strip().lower()
    items = []

    async for it in db.surat.find(
            {"jenis": "keluar", "jenis_naskah": {"$in": ["Laporan", "Berita Acara"]}},
            {"_id": 0, "id": 1, "nomor": 1, "perihal": 1, "jenis_naskah": 1,
             "status": 1, "tanggal_surat": 1, "modul": 1, "kegiatan_id": 1,
             "created_at": 1}).sort("created_at", -1).limit(500):
        items.append({
            "tipe": "surat", "id": it.get("id"),
            "judul": it.get("perihal") or "(tanpa perihal)",
            "nomor": it.get("nomor") or "", "status": it.get("status") or "",
            "sub": f"{it.get('jenis_naskah')} · modul {it.get('modul') or '-'}",
            "tanggal": it.get("tanggal_surat") or (it.get("created_at") or "")[:10],
            "kegiatan_id": it.get("kegiatan_id") or ""})

    async for a in db.inventory_activities.find(
            {"status_pengesahan": "disahkan"},
            {"_id": 0, "id": 1, "nama_kegiatan": 1, "ticket_number": 1,
             "nomor_surat": 1, "tanggal_pengesahan": 1, "nama_satker": 1,
             "kode_satker": 1}).sort("tanggal_pengesahan", -1).limit(300):
        items.append({
            "tipe": "kegiatan", "id": a.get("id"),
            "judul": a.get("nama_kegiatan") or a.get("ticket_number") or "(kegiatan)",
            "nomor": a.get("nomor_surat") or a.get("ticket_number") or "",
            "status": "disahkan",
            "sub": f"Paket laporan inventarisasi · {a.get('nama_satker') or '-'}",
            "tanggal": (a.get("tanggal_pengesahan") or "")[:10],
            "kegiatan_id": a.get("id")})

    async for p in db.periode_pelaporan.find(
            {"status": "terkunci"},
            {"_id": 0, "id": 1, "label": 1, "tahun": 1,
             "tanggal_kunci": 1}).sort("tanggal_kunci", -1).limit(100):
        items.append({
            "tipe": "periode", "id": p.get("id"),
            "judul": f"Periode {p.get('label') or p.get('tahun')}",
            "nomor": "", "status": "FINAL",
            "sub": "LBKP & CaLBMN periode ini berpenanda FINAL",
            "tanggal": (p.get("tanggal_kunci") or "")[:10],
            "kegiatan_id": ""})

    if s:
        items = [i for i in items if s in (i["judul"] + " " + i["nomor"] +
                                           " " + i["sub"]).lower()]
    items.sort(key=lambda x: x.get("tanggal") or "", reverse=True)
    ring = {"surat": 0, "kegiatan": 0, "periode": 0}
    for i in items:
        ring[i["tipe"]] = ring.get(i["tipe"], 0) + 1
    return {"items": items[:500], "ringkas": ring}
