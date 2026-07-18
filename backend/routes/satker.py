"""Master Satker — satker sebagai ENTITAS KELAS SATU (Mandat-2, M-SATKER).

Sebelumnya identitas satker hanya field flat pada kegiatan (kode_satker,
nama_satker, …) dan kop laporan sepenuhnya GLOBAL (`report_settings`), sehingga
aplikasi multi-satker ber-database bersama memakai satu kop untuk semua.
Koleksi `satker` menampung profil + KOP PER-SATKER; resolusi nilai laporan:

    kegiatan (paling spesifik) → master satker → report_settings global

Master diregistrasi otomatis dari kegiatan (sinkron) dan dirawat admin.
Koleksi ini KONFIGURASI: masuk RESET_KEEP (selamat reset), tetap ikut backup.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import log_audit

satker_router = APIRouter()

_PROJ = {"_id": 0}

# Field kop yang boleh dioverride per satker (subset report_settings + identitas)
FIELD_KOP_SATKER = (
    "nama_satker", "nama_unit_organisasi", "nama_sub_unit", "alamat",
    "tempat_laporan", "tembusan_laporan", "telepon", "email",
    "kode_satker_lengkap",
)


class SatkerIn(BaseModel):
    kode_satker: str
    nama_satker: str
    nama_unit_organisasi: str = ""
    nama_sub_unit: str = ""
    alamat: str = ""
    tempat_laporan: str = ""
    tembusan_laporan: str = ""
    telepon: str = ""
    email: str = ""
    # Kode satker LENGKAP registrasi BMN (±20 digit, mis.
    # 126011600691778000KP) — dipakai a.l. baris kedua header stiker.
    kode_satker_lengkap: str = ""
    eselon1: Optional[List[str]] = None
    aktif: bool = True


def _valid_kode(kode: str) -> str:
    k = str(kode or "").strip()
    if not k or len(k) > 30 or not re.fullmatch(r"[\w.\-]+", k):
        raise HTTPException(status_code=400,
                            detail="Kode satker wajib (huruf/angka/titik/strip, maks 30)")
    return k


@satker_router.get("/satker")
async def daftar_satker(_user: dict = Depends(require_user)):
    """Master satker + jumlah kegiatan per satker (agar terlihat mana yang
    dipakai). Termasuk satker yang BELUM terdaftar di master tetapi muncul di
    kegiatan (status 'belum terdaftar') — kandidat sinkron 1-klik."""
    master = {m["kode_satker"]: m async for m in db.satker.find({}, _PROJ)}
    pakai = {}
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"}, "n": {"$sum": 1}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        pakai[g["_id"]] = g
    items = []
    for kode, m in master.items():
        items.append({**m, "jumlah_kegiatan": pakai.get(kode, {}).get("n", 0),
                      "terdaftar": True})
    for kode, g in pakai.items():
        if kode not in master:
            items.append({"kode_satker": kode, "nama_satker": g.get("nama") or "",
                          "eselon1": g.get("eselon1") or [], "aktif": True,
                          "jumlah_kegiatan": g.get("n", 0), "terdaftar": False})
    items.sort(key=lambda x: str(x.get("kode_satker")))
    return {"items": items, "jumlah": len(items),
            "field_kop": list(FIELD_KOP_SATKER)}


@satker_router.get("/satker/{kode}")
async def detail_satker(kode: str, _user: dict = Depends(require_user)):
    doc = await db.satker.find_one({"kode_satker": kode}, _PROJ)
    if not doc:
        raise HTTPException(status_code=404, detail="Satker belum terdaftar di master")
    return doc


@satker_router.put("/satker/{kode}")
async def simpan_satker(kode: str, payload: SatkerIn,
                        admin: dict = Depends(require_admin)):
    """Daftarkan/perbarui profil & kop satu satker (admin). Upsert by kode —
    kode pada path menang atas body (path = identitas)."""
    k = _valid_kode(kode)
    if not str(payload.nama_satker or "").strip():
        raise HTTPException(status_code=400, detail="Nama satker wajib diisi")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "kode_satker": k,
        "nama_satker": payload.nama_satker.strip(),
        "eselon1": [str(e).strip() for e in (payload.eselon1 or []) if str(e).strip()],
        "aktif": bool(payload.aktif),
        "updated_at": now, "updated_by": admin.get("username", "system"),
    }
    for f in FIELD_KOP_SATKER:
        if f in ("nama_satker",):
            continue
        doc[f] = str(getattr(payload, f, "") or "").strip()
    await db.satker.update_one(
        {"kode_satker": k},
        {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True)
    await log_audit("simpan_satker", "", k, username=admin.get("username", "system"),
                    detail=f"Master satker {k} — {doc['nama_satker']}")
    return {"ok": True, "kode_satker": k}


@satker_router.delete("/satker/{kode}")
async def hapus_satker(kode: str, admin: dict = Depends(require_admin)):
    """Hapus satker dari master — DITOLAK bila masih dipakai kegiatan
    (hapus/madah kegiatannya dulu; master bukan tempat menghilangkan jejak)."""
    n = await db.inventory_activities.count_documents({"kode_satker": kode})
    if n:
        raise HTTPException(status_code=409,
                            detail=f"Satker dipakai {n} kegiatan — tidak dapat dihapus")
    res = await db.satker.delete_one({"kode_satker": kode})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Satker tidak ditemukan")
    await log_audit("hapus_satker", "", kode,
                    username=admin.get("username", "system"),
                    detail=f"Hapus master satker {kode}")
    return {"ok": True}


@satker_router.post("/satker/sinkron")
async def sinkron_satker(admin: dict = Depends(require_admin)):
    """Registrasi otomatis: setiap satker yang muncul di kegiatan tetapi belum
    ada di master → didaftarkan (kode+nama+eselon1). Idempoten; profil kop
    yang sudah diisi admin TIDAK ditimpa."""
    now = datetime.now(timezone.utc).isoformat()
    baru = 0
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"},
                    "alamat": {"$first": "$alamat_satker"}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        ada = await db.satker.find_one({"kode_satker": g["_id"]}, {"_id": 1})
        if ada:
            continue
        await db.satker.insert_one({
            "id": str(uuid.uuid4()), "kode_satker": g["_id"],
            "nama_satker": str(g.get("nama") or "").strip(),
            "nama_unit_organisasi": "", "nama_sub_unit": "",
            "alamat": str(g.get("alamat") or "").strip(),
            "tempat_laporan": "", "tembusan_laporan": "",
            "telepon": "", "email": "",
            "eselon1": g.get("eselon1") or [], "aktif": True,
            "created_at": now, "updated_at": now,
            "updated_by": admin.get("username", "system"),
        })
        baru += 1
    await log_audit("sinkron_satker", "", "master",
                    username=admin.get("username", "system"),
                    detail=f"Sinkron master satker: {baru} satker baru terdaftar")
    return {"ok": True, "baru": baru}


@satker_router.post("/satker/backfill")
async def backfill_kode_satker(payload: dict = None,
                               admin: dict = Depends(require_admin)):
    """BACKFILL kode_satker untuk DATA LAMA (sekali jalan, idempoten — hanya
    dokumen yang kode_satker-nya kosong/hilang yang diisi):

    1. Register ber-relasi aset (asset_id / asset_ids / aset[]): kode
       diturunkan dari aset → kegiatan → kode_satker.
    2. Sisanya (persediaan, pengadaan, penganggaran, usulan RKBMN,
       pengamanan, insidentil, dst.) TANPA relasi kegiatan: diisi
       `kode_satker_sisa` bila diberikan (use-case: satker tunggal lama
       mengklaim seluruh data historisnya sebelum satker kedua bergabung).

    Kembalikan laporan jumlah terisi per koleksi."""
    payload = payload or {}
    kode_sisa = str(payload.get("kode_satker_sisa") or "").strip()
    if kode_sisa:
        ada = await db.satker.find_one({"kode_satker": kode_sisa}, {"_id": 1})
        if not ada:
            raise HTTPException(
                status_code=400,
                detail=f"Satker {kode_sisa} belum terdaftar di master")

    # Peta aset → kode satker (via kegiatan) — sekali bangun.
    act_satker = {}
    async for a in db.inventory_activities.find(
            {"kode_satker": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "kode_satker": 1}):
        act_satker[a["id"]] = a["kode_satker"]
    aset_satker = {}
    async for a in db.assets.find(
            {}, {"_id": 0, "id": 1, "activity_id": 1}):
        k = act_satker.get(a.get("activity_id"))
        if k:
            aset_satker[a["id"]] = k

    def _kode_dari_dok(d):
        aid = d.get("asset_id")
        if aid and aset_satker.get(aid):
            return aset_satker[aid]
        for lid in (d.get("asset_ids") or []):
            if aset_satker.get(lid):
                return aset_satker[lid]
        for ar in (d.get("aset") or []):
            k = aset_satker.get((ar or {}).get("asset_id"))
            if k:
                return k
        return ""

    KOSONG = {"$in": ["", None]}
    _q_kosong = {"$or": [{"kode_satker": KOSONG},
                         {"kode_satker": {"$exists": False}}]}
    # Klaim-sisa TIDAK boleh menyentuh kode_satker == "" — string kosong
    # adalah stempel sengaja "lintas-satker" oleh super-admin; hanya dokumen
    # yang benar-benar belum pernah distempel (None / field absen) yang sah
    # diklaim massal.
    _q_belum_distempel = {"$or": [{"kode_satker": None},
                                  {"kode_satker": {"$exists": False}}]}
    laporan = {}

    # 1) Koleksi ber-relasi aset.
    RELASI = ("psp", "bmn_idle", "penggunaan_proses", "usulan_penghapusan",
              "pemusnahan", "pemindahtanganan", "pemanfaatan", "penertiban",
              "bast_serah_terima")
    for nama in RELASI:
        coll = db[nama]
        terisi = 0
        async for d in coll.find(_q_kosong, {"_id": 0, "id": 1, "asset_id": 1,
                                             "asset_ids": 1, "aset.asset_id": 1}):
            k = _kode_dari_dok(d)
            if k and d.get("id"):
                await coll.update_one({"id": d["id"]},
                                      {"$set": {"kode_satker": k}})
                terisi += 1
        laporan[nama] = terisi

    # 2) Sisanya diisi kode_satker_sisa bila diberikan.
    if kode_sisa:
        SISA = ("persediaan", "pengadaan", "penganggaran", "perencanaan_usulan",
                "pemantauan_insidentil", "pengamanan_kasus",
                "pengamanan_dokumen", "pengamanan_polis") + RELASI
        for nama in SISA:
            res = await db[nama].update_many(
                _q_belum_distempel, {"$set": {"kode_satker": kode_sisa}})
            laporan[nama] = laporan.get(nama, 0) + res.modified_count

    total = sum(laporan.values())
    await log_audit("backfill_kode_satker", "", "backfill",
                    username=admin.get("username", "system"),
                    detail=(f"Backfill kode_satker: {total} dokumen"
                            + (f" (sisa → {kode_sisa})" if kode_sisa else "")))
    return {"ok": True, "total": total, "per_koleksi": laporan,
            "kode_satker_sisa": kode_sisa}
