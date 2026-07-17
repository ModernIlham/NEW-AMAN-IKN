"""SINKRONISASI SIMAN V2 — impor manual ekspor "Master Aset" sebagai kanal
pembaruan berkala (pengganti API yang belum tersedia untuk satker).

Alur: unggah XLSX hasil ekspor SIMAN V2 → tiap baris dicocokkan ke aset
AMAN (Kode Register dulu, lalu Kode Barang+NUP) → perbedaan field kunci
tercatat pada subdoc `siman` aset (tanda di halaman aset) → pengguna
meninjau lalu "terapkan nilai SIMAN" per aset (SIMAN = data valid).
Riwayat impor tersimpan di register `siman_imports`.

Logika banding murni di siman_utils.py (teruji unit).
"""
import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from report_filters import active_asset_filter
from shared_utils import limiter, log_audit
from siman_utils import (
    FIELD_TERAPKAN, banding_aset, kunci_aset, nilai_terapkan, parse_baris,
    petakan_header, referensi_siman, ringkas_import,
)

siman_router = APIRouter()

_PROJ_ASET = {
    "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
    "category": 1, "brand": 1, "model": 1, "condition": 1, "status": 1,
    "purchase_price": 1, "purchase_date": 1, "user": 1, "kode_register": 1,
    "activity_id": 1, "siman": 1,
}
_MAKS_CONTOH = 200  # batas daftar contoh yang disimpan di register impor


class TerapkanIn(BaseModel):
    fields: Optional[List[str]] = None  # None = terapkan semua selisih


@siman_router.post("/siman/import")
@limiter.limit("3/minute")
async def import_siman(request: Request, file: UploadFile = File(...),
                       tandai_tidak_ditemukan: bool = False,
                       user: dict = Depends(require_admin)):
    """Impor ekspor SIMAN V2 (XLSX "Master Aset") dan tandai selisih per aset.

    `tandai_tidak_ditemukan=true` juga menandai aset AMAN yang TIDAK ada di
    file (pakai hanya bila file memuat SELURUH aset satker — ekspor penuh,
    bukan potongan).
    """
    nama_file = file.filename or ""
    if not nama_file.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File harus Excel (.xlsx) hasil ekspor SIMAN V2")

    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(await file.read()),
                                    read_only=True, data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="File Excel tidak dapat dibaca")

    # Sheet "Master Aset" bila ada; selain itu sheet pertama.
    ws = wb["Master Aset"] if "Master Aset" in wb.sheetnames else wb[wb.sheetnames[0]]
    # Ekspor SIMAN kerap menulis metadata dimensi yang salah — tanpa reset,
    # mode read_only hanya melihat baris pertama (terbukti pada file asli).
    ws.reset_dimensions()

    # Cari baris header (baris pertama yang memuat kolom kode barang + NUP).
    peta_header, baris_data, ditemukan = None, [], False
    for row in ws.iter_rows(values_only=True):
        if not ditemukan:
            peta, hilang = petakan_header(row)
            if not hilang:
                peta_header, ditemukan = peta, True
            continue
        b = parse_baris(row, peta_header)
        if b:
            baris_data.append(b)
    wb.close()
    if not ditemukan:
        raise HTTPException(status_code=400, detail=(
            "Header tidak dikenali — pastikan file adalah ekspor SIMAN V2 "
            "dengan kolom 'Kode Barang' dan 'NUP'"))
    if not baris_data:
        raise HTTPException(status_code=400, detail="Tidak ada baris aset pada file")

    # Peta pencocokan: kode register (paling stabil) & kode+NUP.
    per_register, per_kunci, duplikat_kunci = {}, {}, 0
    for b in baris_data:
        if b["kode_register"]:
            per_register.setdefault(b["kode_register"], b)
        k = kunci_aset(b["kode_barang"], b["nup"])
        if k in per_kunci:
            duplikat_kunci += 1
        else:
            per_kunci[k] = b

    assets = await db.assets.find(active_asset_filter(), _PROJ_ASET).to_list(500000)

    now = datetime.now(timezone.utc).isoformat()
    import_id = str(uuid.uuid4())
    hasil, terpakai = [], set()
    for a in assets:
        reg = str(a.get("kode_register") or "").strip()
        b = per_register.get(reg) if reg else None
        if b is None:
            b = per_kunci.get(kunci_aset(a.get("asset_code"), a.get("NUP")))
        if b is None:
            continue
        terpakai.add(id(b))
        selisih = banding_aset(a, b)
        # Sinyal reklasifikasi (riset G7 §5): kode_register cocok tetapi
        # kodefikasi/NUP beda → aset direklasifikasi di SIMAN, bukan sekadar
        # selisih field — UI menampilkannya berbeda.
        from mutasi_bmn_utils import deteksi_reklasifikasi_siman
        reklas = deteksi_reklasifikasi_siman(a, b)
        hasil.append({"aset": a, "baris": b, "selisih": selisih,
                      "reklasifikasi": reklas})

    aset_cocok_id = {r["aset"]["id"] for r in hasil}
    aman_tanpa_siman = [a for a in assets if a["id"] not in aset_cocok_id]
    siman_tanpa_aset = [b for b in baris_data if id(b) not in terpakai]

    # Tulis subdoc `siman` per aset yang cocok (bulk, $inc version).
    from pymongo import UpdateOne
    ops = []
    register_diadopsi = 0
    for r in hasil:
        subdoc = {
            "status": "selisih" if r["selisih"] else "cocok",
            "selisih": r["selisih"],
            "reklasifikasi": r.get("reklasifikasi") or {},
            "referensi": referensi_siman(r["baris"]),
            "kode_register": r["baris"]["kode_register"],
            "import_id": import_id,
            "diperiksa_pada": now,
        }
        set_doc = {"siman": subdoc, "updated_at": now}
        # Adopsi ID register SIMAN bila AMAN belum punya — memperkuat
        # pencocokan impor berikutnya (tahan reklasifikasi kode barang).
        if r["baris"]["kode_register"] and not str(r["aset"].get("kode_register") or "").strip():
            set_doc["kode_register"] = r["baris"]["kode_register"]
            register_diadopsi += 1
        ops.append(UpdateOne({"id": r["aset"]["id"]},
                             {"$set": set_doc, "$inc": {"version": 1}}))
    if tandai_tidak_ditemukan:
        for a in aman_tanpa_siman:
            ops.append(UpdateOne(
                {"id": a["id"]},
                {"$set": {"siman": {"status": "tidak_di_siman", "selisih": [],
                                    "import_id": import_id,
                                    "diperiksa_pada": now},
                          "updated_at": now},
                 "$inc": {"version": 1}}))
    if ops:
        await db.assets.bulk_write(ops, ordered=False)

    ringkasan = ringkas_import(
        [{"selisih": r["selisih"]} for r in hasil], siman_tanpa_aset, aman_tanpa_siman)
    register = {
        "id": import_id,
        "filename": nama_file,
        "waktu": now,
        "oleh": user.get("username", "system"),
        "total_baris": len(baris_data),
        "duplikat_kunci": duplikat_kunci,
        "register_diadopsi": register_diadopsi,
        "tandai_tidak_ditemukan": bool(tandai_tidak_ditemukan),
        "ringkasan": ringkasan,
        "satker": sorted({b["nama_satker"] for b in baris_data if b.get("nama_satker")})[:10],
        # Contoh (dibatasi) untuk ditinjau di UI — bukan data lengkap.
        "contoh_siman_tanpa_aset": [
            {"kode_barang": b["kode_barang"], "nup": b["nup"],
             "nama_barang": b["nama_barang"], "nilai_perolehan": b["nilai_perolehan"]}
            for b in siman_tanpa_aset[:_MAKS_CONTOH]],
        "contoh_aman_tanpa_siman": [
            {"id": a["id"], "asset_code": a.get("asset_code"), "NUP": a.get("NUP"),
             "asset_name": a.get("asset_name")}
            for a in aman_tanpa_siman[:_MAKS_CONTOH]],
    }
    await db.siman_imports.insert_one({**register})
    await log_audit("import_siman", "", username=user.get("username", "system"),
                    detail=(f"Impor SIMAN V2 '{nama_file}': {len(baris_data)} baris, "
                            f"{ringkasan['cocok']} cocok, {ringkasan['selisih']} selisih, "
                            f"{ringkasan['siman_tanpa_aset']} belum tercatat di AMAN"))
    return register


@siman_router.get("/siman/ringkasan")
async def ringkasan_siman(_user: dict = Depends(require_user)):
    """Status sinkronisasi terkini + riwayat impor (untuk panel UI)."""
    selisih = await db.assets.count_documents(
        active_asset_filter({"siman.status": "selisih"}))
    cocok = await db.assets.count_documents(
        active_asset_filter({"siman.status": "cocok"}))
    tidak_di_siman = await db.assets.count_documents(
        active_asset_filter({"siman.status": "tidak_di_siman"}))
    belum_dicek = await db.assets.count_documents(
        active_asset_filter({"siman": {"$exists": False}}))
    riwayat = await db.siman_imports.find(
        {}, {"_id": 0, "contoh_siman_tanpa_aset": 0, "contoh_aman_tanpa_siman": 0},
    ).sort("waktu", -1).limit(10).to_list(10)
    return {
        "selisih": selisih, "cocok": cocok,
        "tidak_di_siman": tidak_di_siman, "belum_dicek": belum_dicek,
        "riwayat": riwayat,
        "import_terakhir": riwayat[0] if riwayat else None,
    }


@siman_router.get("/siman/import/{import_id}")
async def detail_import_siman(import_id: str, _user: dict = Depends(require_user)):
    """Detail satu impor termasuk daftar contoh yang tidak cocok."""
    reg = await db.siman_imports.find_one({"id": import_id}, {"_id": 0})
    if not reg:
        raise HTTPException(status_code=404, detail="Riwayat impor tidak ditemukan")
    return reg


@siman_router.get("/siman/selisih")
async def daftar_selisih_siman(page: int = 1, page_size: int = 50,
                               _user: dict = Depends(require_user)):
    """Aset yang datanya berbeda dengan SIMAN (untuk tabel tinjau & terapkan)."""
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    q = active_asset_filter({"siman.status": "selisih"})
    total = await db.assets.count_documents(q)
    items = await (db.assets.find(q, _PROJ_ASET)
                   .sort([("asset_code", 1), ("NUP", 1)])
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size))}


@siman_router.post("/siman/terapkan/{asset_id}")
async def terapkan_siman(asset_id: str, payload: TerapkanIn,
                         user: dict = Depends(require_user)):
    """Terapkan nilai SIMAN ke aset AMAN (menyingkronkan kembali).

    Default seluruh selisih; `fields` membatasi field tertentu. Nilai SIMAN
    menang (data valid). Ber-audit + $inc version (OCC).
    """
    a = await db.assets.find_one({"id": asset_id, "dihapus": {"$ne": True}},
                                 {"_id": 0, "id": 1, "NUP": 1, "asset_code": 1,
                                  "asset_name": 1, "activity_id": 1, "siman": 1,
                                  "version": 1})
    if not a:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    sub = a.get("siman") or {}
    selisih = sub.get("selisih") or []
    if not selisih:
        raise HTTPException(status_code=400, detail="Tidak ada selisih SIMAN pada aset ini")

    pilih = set(payload.fields) if payload.fields else None
    terapkan = [s for s in selisih
                if s.get("field") in FIELD_TERAPKAN
                and (pilih is None or s.get("field") in pilih)]
    if not terapkan:
        raise HTTPException(status_code=400, detail="Tidak ada field terpilih yang bisa diterapkan")

    set_fields, changes = {}, []
    for s in terapkan:
        set_fields[s["field"]] = nilai_terapkan(s)
        changes.append({"field": s["field"], "from": s.get("aman", ""),
                        "to": nilai_terapkan(s)})

    # Reklasifikasi kode barang: jaga keunikan kode+NUP antar aset hidup.
    kode_baru = set_fields.get("asset_code")
    if kode_baru:
        bentrok = await db.assets.count_documents({
            "asset_code": kode_baru, "NUP": a.get("NUP"),
            "id": {"$ne": asset_id}, "dihapus": {"$ne": True}})
        if bentrok:
            raise HTTPException(status_code=409, detail=(
                f"Kode {kode_baru} NUP {a.get('NUP')} sudah dipakai aset lain — "
                "periksa duplikat sebelum menerapkan reklasifikasi"))

    sisa = [s for s in selisih if s not in terapkan]
    sub.update({"selisih": sisa, "status": "selisih" if sisa else "cocok",
                "disinkron_pada": datetime.now(timezone.utc).isoformat()})
    now = datetime.now(timezone.utc).isoformat()
    res = await db.assets.find_one_and_update(
        {"id": asset_id, "dihapus": {"$ne": True}},
        {"$set": {**set_fields, "siman": sub, "updated_at": now},
         "$inc": {"version": 1}},
        projection={"_id": 0, "version": 1})
    if res is None:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    await log_audit("sinkron_siman", a.get("activity_id", ""), asset_id,
                    asset_code=a.get("asset_code", ""),
                    asset_name=a.get("asset_name", ""),
                    nup=str(a.get("NUP") or ""),
                    username=user.get("username", "system"),
                    changes=changes,
                    detail=f"Terapkan nilai SIMAN V2 ({len(terapkan)} field)")
    return {"ok": True, "diterapkan": [s["field"] for s in terapkan],
            "sisa_selisih": len(sisa), "version": (res or {}).get("version")}
