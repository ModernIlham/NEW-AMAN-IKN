"""REFERENSI AKUN BAS — Kodefikasi Segmen Akun (SATU master, tidak dipecah).

Permintaan pemilik: referensi akun jangan dibagi dua (akun neraca aset vs
akun persediaan) — jadikan SATU "Kodefikasi Segmen Akun BAS" seperti
referensi resmi SAKTI/SPAN. Master ini memuat SELURUH akun 6 digit (8
segmen: aset s.d. non-anggaran) hasil parse dokumen resmi "REFERENSI AKUN"
(cetak 24-12-2025) + pengayaan akun belanja↔BMN dari kertas kerja satker
(gol BMN, kapitalisasi, kategori neraca).

Pemetaan turunan (golongan aset → akun di `akun_bas`, sub-kelompok
persediaan → akun di `persediaan_akun`) TETAP ada sebagai aturan pakai —
kini tampil satu pintu di halaman Referensi Akun BAS dan tervalidasi lunak
ke master ini (pola §5A Prinsip 2, non-blocking).

Seed idempoten: koleksi kosong → dimuat otomatis dari
`data/referensi_akun_bas.json` saat akses pertama; admin dapat memuat
ulang kapan pun (upsert, entri manual satker tak hilang).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from referensi_akun_utils import (KELOMPOK_LABEL, baris_csv_referensi,
                                  jalur_digit)
from shared_utils import log_audit

referensi_akun_router = APIRouter()

_PROJ = {"_id": 0}
_SEED_PATH = Path(__file__).parent.parent / "data" / "referensi_akun_bas.json"

# Versi isi seed — dinaikkan saat data seed diperkaya (mis. +penjelasan resmi
# KEP-211/PB/2018, +hierarki nama tiap level digit) agar auto-seed MENIMPA
# ulang koleksi yang sudah terisi di produksi tanpa perlu admin menekan
# "Muat Referensi Resmi" manual.
SEED_VERSION = 3

SEGMEN_LABEL = {
    "1": "Aset", "2": "Kewajiban", "3": "Ekuitas", "4": "Pendapatan",
    "5": "Belanja", "6": "Transfer", "7": "Pembiayaan", "8": "Non-Anggaran",
}


class AkunIn(BaseModel):
    kode: str
    nama: str
    uraian_bmn: Optional[str] = ""
    kapitalisasi: Optional[str] = ""
    kategori_neraca: Optional[str] = ""


def _valid_kode(kode: str) -> str:
    k = str(kode or "").strip()
    if not re.match(r"^\d{6}$", k):
        raise HTTPException(status_code=400,
                            detail="Kode akun harus 6 digit angka (segmen akun BAS)")
    return k


async def _perlu_seed(hanya_bila_kosong: bool) -> bool:
    """True bila seed perlu dijalankan: dipaksa, koleksi kosong, atau versi
    seed tersimpan tertinggal (data seed sudah diperkaya)."""
    if not hanya_bila_kosong:
        return True
    if await db.referensi_akun.count_documents({}) == 0:
        return True
    meta = await db.referensi_akun_meta.find_one(
        {"key": "seed"}, {"_id": 0, "version": 1})
    return int((meta or {}).get("version") or 0) < SEED_VERSION


async def _seed(hanya_bila_kosong: bool) -> dict:
    """Muat referensi resmi dari file seed (upsert idempoten). Menyertakan
    penjelasan resmi per akun (kolom Penjelasan KEP-211/PB/2018)."""
    if not await _perlu_seed(hanya_bila_kosong):
        return {"dimuat": 0, "dilewati": True}
    try:
        data = json.loads(_SEED_PATH.read_text())
    except (OSError, ValueError):
        raise HTTPException(status_code=500,
                            detail="File seed referensi akun tidak dapat dibaca")
    from pymongo import UpdateOne
    now = datetime.now(timezone.utc).isoformat()
    ops = []
    for a in data.get("akun", []):
        kode = str(a.get("kode") or "").strip()
        if not re.match(r"^\d{6}$", kode):
            continue
        doc = {"kode": kode, "nama": str(a.get("nama") or "").strip(),
               "segmen": SEGMEN_LABEL.get(kode[0], kode[0]),
               "sumber": "resmi", "updated_at": now}
        for f in ("uraian_bmn", "kapitalisasi", "kategori_neraca",
                  "penjelasan", "penjelasan_warisan"):
            if a.get(f):
                doc[f] = a[f]
        ops.append(UpdateOne({"kode": kode}, {"$set": doc}, upsert=True))
    if ops:
        await db.referensi_akun.bulk_write(ops, ordered=False)
    # Hierarki nama tiap level digit (1-5) — dipakai endpoint struktur/{kode}
    # utk menampilkan makna digit 1 s.d. 6 sebuah akun.
    ops_h = [UpdateOne({"kode": k},
                       {"$set": {"kode": k, "uraian": u, "updated_at": now}},
                       upsert=True)
             for k, u in (data.get("hierarki") or {}).items()
             if re.match(r"^\d{1,5}$", str(k)) and str(u or "").strip()]
    if ops_h:
        await db.referensi_akun_hierarki.bulk_write(ops_h, ordered=False)
    await db.referensi_akun_meta.update_one(
        {"key": "seed"},
        {"$set": {"key": "seed", "version": SEED_VERSION, "updated_at": now}},
        upsert=True)
    return {"dimuat": len(ops), "hierarki": len(ops_h),
            "sumber": data.get("sumber", ""), "dilewati": False}


@referensi_akun_router.get("/referensi-akun")
async def daftar_referensi_akun(search: str = "", segmen: str = "",
                                page: int = 1, page_size: int = 50,
                                _user: dict = Depends(require_user)):
    """Master Kodefikasi Segmen Akun BAS (auto-seed saat pertama kosong)."""
    await _seed(hanya_bila_kosong=True)
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    q = {}
    if str(segmen).strip() in SEGMEN_LABEL:
        q["kode"] = {"$regex": f"^{segmen.strip()}"}
    if search.strip():
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        q["$or"] = [{"kode": rx}, {"nama": rx}]
    total = await db.referensi_akun.count_documents(q)
    items = await (db.referensi_akun.find(q, _PROJ).sort("kode", 1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    per_segmen = {}
    async for g in db.referensi_akun.aggregate([
            {"$group": {"_id": {"$substrCP": ["$kode", 0, 1]},
                        "n": {"$sum": 1}}}]):
        per_segmen[g["_id"]] = g["n"]
    # Nama hierarki (level 1-5) utk prefiks kode di halaman ini — dipakai UI
    # menggambar HEADER BERTINGKAT langsung di tabel (permintaan pemilik:
    # makna digit tampil di luar, membagi baris seperti lampiran resmi).
    prefiks = sorted({str(a.get("kode") or "")[:n]
                      for a in items for n in range(1, 6)
                      if a.get("kode")})
    hierarki = {}
    if prefiks:
        async for h in db.referensi_akun_hierarki.find(
                {"kode": {"$in": prefiks}},
                {"_id": 0, "kode": 1, "uraian": 1}):
            hierarki[h["kode"]] = h["uraian"]
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "per_segmen": per_segmen, "label_segmen": SEGMEN_LABEL,
            "label_kelompok": KELOMPOK_LABEL, "hierarki": hierarki}


@referensi_akun_router.get("/referensi-akun/export")
async def export_referensi_akun(search: str = "", segmen: str = "",
                                _user: dict = Depends(require_user)):
    """Ekspor CSV master Kodefikasi Segmen Akun + kolom hierarki digit
    (akun/segmen · kelompok · jenis) — mengikuti filter cari & segmen yang
    sedang aktif di halaman (tanpa paginasi; pola export register)."""
    import csv as csv_module
    import io

    from fastapi import Response

    await _seed(hanya_bila_kosong=True)
    q = {}
    if str(segmen).strip() in SEGMEN_LABEL:
        q["kode"] = {"$regex": f"^{segmen.strip()}"}
    if search.strip():
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        q["$or"] = [{"kode": rx}, {"nama": rx}]
    items = [a async for a in db.referensi_akun.find(q, _PROJ).sort("kode", 1)]
    # Nama Jenis (3 digit) dari hierarki resmi — satu query utk semua prefiks.
    prefiks3 = sorted({str(a.get("kode") or "")[:3] for a in items
                       if a.get("kode")})
    hier = {}
    if prefiks3:
        async for h in db.referensi_akun_hierarki.find(
                {"kode": {"$in": prefiks3}}, {"_id": 0, "kode": 1, "uraian": 1}):
            hier[h["kode"]] = h["uraian"]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_referensi(items, SEGMEN_LABEL, hierarki=hier):
        w.writerow(row)
    return Response(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="referensi_akun_bas.csv"'})


@referensi_akun_router.get("/referensi-akun/struktur/{kode}")
async def struktur_akun(kode: str, _user: dict = Depends(require_user)):
    """Makna TIAP POLA DIGIT sebuah kode akun (permintaan pemilik): digit 1
    = akun/segmen, 2 digit = kelompok, 3 digit = jenis, dst. hingga akun
    rincian 6 digit — uraian resmi dari hierarki KEP-211/PB/2018."""
    kode = _valid_kode(kode)
    await _seed(hanya_bila_kosong=True)
    prefiks = [kode[:n] for n in range(1, 6)]
    hier = {}
    async for h in db.referensi_akun_hierarki.find(
            {"kode": {"$in": prefiks}}, {"_id": 0, "kode": 1, "uraian": 1}):
        hier[h["kode"]] = h["uraian"]
    sendiri = await db.referensi_akun.find_one(
        {"kode": kode}, {"_id": 0, "nama": 1})
    return {"kode": kode,
            "jalur": jalur_digit(kode, hier, (sendiri or {}).get("nama", "")),
            "sumber": "KEP-211/PB/2018 — hierarki level digit"}


@referensi_akun_router.get("/referensi-akun/periksa")
async def periksa_akun(kode: str = "", _user: dict = Depends(require_user)):
    """Lookup batch nama akun utk validasi lunak pemetaan: ?kode=a,b,c →
    {kode: nama | null}. Non-blocking — pemetaan dengan kode di luar master
    hanya DITANDAI, tidak ditolak."""
    await _seed(hanya_bila_kosong=True)
    daftar = [k.strip() for k in str(kode or "").split(",") if k.strip()][:100]
    hasil = {k: None for k in daftar}
    if daftar:
        async for a in db.referensi_akun.find(
                {"kode": {"$in": daftar}}, {"_id": 0, "kode": 1, "nama": 1}):
            hasil[a["kode"]] = a["nama"]
    return {"akun": hasil}


@referensi_akun_router.post("/referensi-akun/seed")
async def muat_ulang_seed(user: dict = Depends(require_admin)):
    """Muat ulang referensi resmi (admin; upsert — entri manual tak hilang)."""
    hasil = await _seed(hanya_bila_kosong=False)
    await log_audit("referensi_akun", "", username=user.get("username", "system"),
                    detail=f"Muat referensi akun BAS resmi: {hasil['dimuat']} akun")
    return hasil


@referensi_akun_router.post("/referensi-akun")
async def upsert_akun(payload: AkunIn, user: dict = Depends(require_admin)):
    """Tambah/ubah satu akun (admin — entri manual satker, sumber 'satker')."""
    kode = _valid_kode(payload.kode)
    nama = str(payload.nama or "").strip()
    if not nama:
        raise HTTPException(status_code=400, detail="Nama akun wajib diisi")
    now = datetime.now(timezone.utc).isoformat()
    doc = {"kode": kode, "nama": nama,
           "segmen": SEGMEN_LABEL.get(kode[0], kode[0]),
           "sumber": "satker", "updated_at": now}
    for f in ("uraian_bmn", "kapitalisasi", "kategori_neraca"):
        v = str(getattr(payload, f) or "").strip()
        if v:
            doc[f] = v
    await db.referensi_akun.update_one({"kode": kode}, {"$set": doc}, upsert=True)
    await log_audit("referensi_akun", "", username=user.get("username", "system"),
                    detail=f"Upsert akun {kode} — {nama}")
    return doc


@referensi_akun_router.delete("/referensi-akun/{kode}")
async def hapus_akun(kode: str, user: dict = Depends(require_admin)):
    """Hapus satu akun dari master (admin). Ditolak bila dipakai pemetaan."""
    kode = _valid_kode(kode)
    dipakai = []
    if await db.akun_bas.find_one({"akun": kode}, _PROJ):
        dipakai.append("pemetaan akun aset per golongan")
    if await db.persediaan_akun.find_one({"akun": kode}, _PROJ):
        dipakai.append("pemetaan akun persediaan")
    if dipakai:
        raise HTTPException(status_code=409, detail=(
            f"Akun {kode} masih dipakai {' dan '.join(dipakai)} — "
            "ubah pemetaannya dulu"))
    res = await db.referensi_akun.delete_one({"kode": kode})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    await log_audit("referensi_akun", "", username=user.get("username", "system"),
                    detail=f"Hapus akun {kode}")
    return {"ok": True, "kode": kode}
