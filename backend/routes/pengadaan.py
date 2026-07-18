"""PENGADAAN — Fase 4 tahap awal: register perolehan per dokumen.

Perpres 16/2018 jo. 46/2025 (pustaka §10): satu entri per BAST/kontrak,
checklist kelengkapan dokumen sumber, daftar barang dengan tautan ke aset
master (cegah entri ganda) + penanda ekstrakomptabel PMK 181. Pencatatan
resmi tetap di SAKTI; kanal pengadaan tetap SiRUP/SPSE/e-Katalog — AMAN
alat bantu tertib dokumen satker. Barang perolehan yang belum tertaut
dapat dibuatkan draft aset otomatis (buat-draft-aset, NUP berurut).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from db import db, fs_bucket
from shared_utils import delete_document_from_gridfs, get_document_from_gridfs, log_audit
from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    build_asset_perolehan_projection, dokumen_kurang_perolehan,
    is_ekstrakomptabel, nilai_perolehan, rekap_perolehan,
    snapshot_penganggaran, validate_perolehan,
)

pengadaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


class BarangIn(BaseModel):
    uraian: str = Field(min_length=1)
    kode: str = ""                     # kode barang (opsional, utk ambang)
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)
    asset_id: str = ""                 # tautan ke aset master (opsional)


class PerolehanIn(BaseModel):
    jenis: str
    pihak: str = Field(min_length=1)   # penyedia / pemberi hibah / pengirim
    nomor_kontrak: str = ""
    nomor_bast: str = Field(min_length=1)
    tanggal_bast: str = Field(min_length=10, max_length=10)
    keterangan: str = ""
    penganggaran_id: str = ""          # tautan usulan Penganggaran (opsional)
    barang: list[BarangIn] = Field(min_length=1, max_length=100)


class TautkanPenganggaranIn(BaseModel):
    penganggaran_id: str = ""          # kosong = lepaskan tautan


async def _ambil_snapshot_penganggaran(penganggaran_id: str) -> dict:
    """Cari usulan penganggaran (bila id diisi) → snapshot; 404 bila hilang."""
    pid = str(penganggaran_id or "").strip()
    if not pid:
        return snapshot_penganggaran(None)
    u = await db.penganggaran.find_one(
        {"id": pid},
        {"_id": 0, "id": 1, "uraian": 1, "nomor_dipa": 1, "tahun_anggaran": 1})
    if not u:
        raise HTTPException(status_code=404,
                            detail="Usulan penganggaran tidak ditemukan")
    return snapshot_penganggaran(u)


async def _proyeksi_perolehan_ke_aset(perolehan: dict) -> None:
    """Proyeksi BALIK dokumen sumber (§5A gap #6): stamp `perolehan_id` +
    snapshot ke tiap aset yang tertaut di baris barang. Best-effort — perolehan
    (jurnal) sudah tersimpan; kegagalan tak menggagalkan pencatatan. Tanpa
    `$inc version` (provenance) agar tak memicu OCC 409 palsu pada form aset.
    """
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_perolehan_projection(perolehan, now)
    for b in perolehan.get("barang") or []:
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            await db.assets.update_one({"id": aid}, {"$set": proj})


async def _lepas_perolehan_dari_aset(asset_id: str, perolehan_id: str) -> None:
    """Lepas back-link perolehan pada aset saat baris di-untautkan — HANYA bila
    `perolehan_id` cocok (jangan hapus tautan milik perolehan lain)."""
    aid = str(asset_id or "").strip()
    if not aid:
        return
    await db.assets.update_one(
        {"id": aid, "perolehan_id": perolehan_id},
        {"$set": {"perolehan_id": "", "perolehan": {}}})


class DokumenIn(BaseModel):
    dokumen: dict[str, bool]


class TautkanIn(BaseModel):
    index: int = Field(ge=0)
    asset_id: str = ""                 # kosong = lepaskan tautan


def _enrich(p: dict) -> dict:
    p["dokumen_kurang"] = dokumen_kurang_perolehan(p)
    p["nilai"] = nilai_perolehan(p)
    for b in p.get("barang") or []:
        b["ekstrakomptabel"] = is_ekstrakomptabel(b)
    return p


@pengadaan_router.get("/pengadaan")
async def list_pengadaan(_user: dict = Depends(require_user)):
    """Register perolehan (BAST terbaru dulu) + ringkasan + label."""
    items = [_enrich(p) async for p in db.pengadaan.find({}, {"_id": 0})
             .sort("tanggal_bast", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_perolehan(items),
            "label_jenis": {k: v[0] for k, v in JENIS_PEROLEHAN.items()},
            "kode_jenis": {k: v[1] for k, v in JENIS_PEROLEHAN.items()},
            "label_dokumen": LABEL_DOKUMEN_SUMBER,
            "dokumen_wajib": {k: list(v) for k, v in DOKUMEN_PEROLEHAN.items()},
            "catatan": (
                "Register pendamping tertib dokumen: pencatatan BMN resmi di "
                "SAKTI (BAST = pemicu, tanpa menunggu SP2D); kanal pengadaan "
                "resmi SiRUP/SPSE/e-Katalog. Penanda ekstrakomptabel memakai "
                "ambang PMK 181/2016 (peralatan-mesin Rp1 jt, gedung Rp25 jt).")}


@pengadaan_router.post("/pengadaan/{perolehan_id}/daftarkan-persediaan")
async def daftarkan_persediaan(perolehan_id: str, user: dict = Depends(require_writer)):
    """Barang perolehan ber-kode persediaan (awalan '1') → master persediaan
    + transaksi masuk berjurnal FIFO (audit G4 #6 — jalur BAST konsumsi).

    Master dicari per kode; bila belum ada dibuat otomatis (kode 10 digit
    dilengkapi nomor urut, NUP otomatis). Transaksi memakai jalur
    `transaksi_masuk` yang sudah atomik + berjurnal + ber-FK dokumen sumber.
    Baris yang sudah pernah didaftarkan (psd_item_id) dilewati.
    """
    from routes.persediaan import (PersediaanCreate, TransaksiMasukIn,
                                   create_persediaan, transaksi_masuk)

    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    barang = list(p.get("barang") or [])
    dibuat_master = masuk = dilewati_nonpsd = dilewati_terdaftar = 0
    gagal = []
    for row in barang:
        kode = str(row.get("kode") or "").strip()
        if not kode.startswith("1"):
            dilewati_nonpsd += 1
            continue
        if str(row.get("psd_item_id") or "").strip():
            dilewati_terdaftar += 1
            continue
        jumlah = max(1, int(float(row.get("jumlah") or 1)))
        it = await db.persediaan.find_one(
            {"kode_barang": kode}, {"_id": 0, "id": 1})
        if not it:
            try:
                it = await create_persediaan(PersediaanCreate(
                    kode_barang=kode,
                    nama_barang=str(row.get("uraian") or "Barang persediaan").strip()[:300],
                ), _user=user)
                dibuat_master += 1
            except HTTPException as e:
                gagal.append(f"{row.get('uraian')}: {e.detail}")
                continue
        try:
            await transaksi_masuk(it["id"], TransaksiMasukIn(
                jenis="pembelian", jumlah=jumlah,
                harga_satuan=float(row.get("harga_satuan") or 0),
                no_bukti=str(p.get("nomor_bast") or ""), jenis_dokumen="BAST",
                tgl_dokumen=str(p.get("tanggal_bast") or ""),
                no_kontrak=str(p.get("nomor_kontrak") or ""),
                penyedia=str(p.get("pihak") or ""), perolehan_id=perolehan_id,
                keterangan="Didaftarkan dari perolehan Pengadaan",
            ), user=user)
        except HTTPException as e:
            gagal.append(f"{row.get('uraian')}: {e.detail}")
            continue
        row["psd_item_id"] = it["id"]
        masuk += 1
    if masuk:
        await db.pengadaan.update_one(
            {"id": perolehan_id},
            {"$set": {"barang": barang,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_audit("pengadaan_daftarkan_persediaan", "", perolehan_id,
                    username=user.get("username", "system"),
                    detail=(f"BAST {p.get('nomor_bast') or perolehan_id[:8]}: "
                            f"{masuk} barang masuk persediaan "
                            f"({dibuat_master} master baru)"))
    return {"masuk": masuk, "dibuat_master": dibuat_master,
            "dilewati_bukan_persediaan": dilewati_nonpsd,
            "dilewati_sudah_terdaftar": dilewati_terdaftar,
            "gagal": gagal[:20]}


@pengadaan_router.get("/pengadaan/export")
async def export_pengadaan(_user: dict = Depends(require_user)):
    """Ekspor CSV register perolehan (pola #158)."""
    import csv as csv_module
    import io

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["jenis", "pihak", "nomor_kontrak", "nomor_bast", "tanggal_bast",
                "jumlah_barang", "nilai", "dokumen_kurang", "penganggaran",
                "nomor_dipa", "keterangan", "jumlah_lampiran", "dibuat_oleh"])
    async for p in db.pengadaan.find({}, {"_id": 0}).sort("tanggal_bast", -1):
        w.writerow([
            JENIS_PEROLEHAN.get(p.get("jenis"), (p.get("jenis"),))[0],
            p.get("pihak"), p.get("nomor_kontrak"), p.get("nomor_bast"),
            p.get("tanggal_bast"), len(p.get("barang") or []),
            int(nilai_perolehan(p)),
            "; ".join(dokumen_kurang_perolehan(p)),
            p.get("penganggaran_uraian"), p.get("penganggaran_nomor_dipa"),
            p.get("keterangan"), len(p.get("lampiran_berkas") or []),
            p.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_pengadaan.csv"'})


@pengadaan_router.post("/pengadaan")
async def buat_perolehan(payload: PerolehanIn, user: dict = Depends(require_writer)):
    """Catat perolehan baru (barang boleh ditautkan ke aset master)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_perolehan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    barang_rows = []
    for b in data["barang"]:
        row = {"uraian": b["uraian"].strip(),
               "kode": str(b.get("kode") or "").strip(),
               "jumlah": float(b["jumlah"]),
               "harga_satuan": float(b["harga_satuan"]),
               "asset_id": "", "asset_code": "", "NUP": "", "asset_name": ""}
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
            if not a:
                raise HTTPException(status_code=404,
                                    detail=f"Aset {aid} tidak ditemukan")
            row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                        "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
        barang_rows.append(row)
    snap = await _ambil_snapshot_penganggaran(data.get("penganggaran_id"))
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "jenis": data["jenis"],
        "pihak": data["pihak"].strip(),
        "nomor_kontrak": str(data.get("nomor_kontrak") or "").strip(),
        "nomor_bast": data["nomor_bast"].strip(),
        "tanggal_bast": data["tanggal_bast"].strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        **snap,
        # Checklist mulai kosong; BAST & kontrak otomatis tercentang bila
        # nomornya sudah diisi saat pencatatan.
        "dokumen": {"bast": True,
                    **({"kontrak": True} if str(data.get("nomor_kontrak") or "").strip() else {})},
        "barang": barang_rows,
        "lampiran_berkas": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengadaan.insert_one({**record})
    # Back-link dokumen sumber (§5A gap #6): stamp perolehan_id ke aset tertaut.
    await _proyeksi_perolehan_ke_aset(record)
    return _enrich(record)


@pengadaan_router.put("/pengadaan/{perolehan_id}/dokumen")
async def perbarui_dokumen(perolehan_id: str, payload: DokumenIn,
                           _user: dict = Depends(require_writer)):
    """Perbarui checklist dokumen sumber (kunci di luar daftar diabaikan)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    wajib = set(DOKUMEN_PEROLEHAN.get(p.get("jenis"), ()))
    dokumen = {**(p.get("dokumen") or {}),
               **{k: bool(v) for k, v in payload.dokumen.items() if k in wajib}}
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"dokumen": dokumen, "updated_at": now}})
    p["dokumen"] = dokumen
    return _enrich(p)


@pengadaan_router.post("/pengadaan/{perolehan_id}/tautkan")
async def tautkan_barang(perolehan_id: str, payload: TautkanIn,
                         _user: dict = Depends(require_writer)):
    """Tautkan/lepaskan baris barang ke aset master (cegah entri ganda)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    barang = p.get("barang") or []
    if payload.index >= len(barang):
        raise HTTPException(status_code=400, detail="Baris barang tidak ada")
    row = barang[payload.index]
    prev_aid = str(row.get("asset_id") or "").strip()   # aset lama (lepas back-link)
    aid = str(payload.asset_id or "").strip()
    if aid:
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                    "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    else:
        row.update({"asset_id": "", "asset_code": "", "NUP": "",
                    "asset_name": ""})
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"barang": barang, "updated_at": now}})
    # Back-link dokumen sumber (§5A gap #6): lepas dari aset lama bila berganti,
    # lalu stamp perolehan_id + snapshot ke aset baru.
    if prev_aid and prev_aid != aid:
        await _lepas_perolehan_dari_aset(prev_aid, perolehan_id)
    if aid:
        await db.assets.update_one(
            {"id": aid}, {"$set": build_asset_perolehan_projection(p, now)})
    p["barang"] = barang
    return _enrich(p)


class BuatDraftAsetIn(BaseModel):
    activity_id: str = Field(min_length=1)   # kegiatan tujuan (dipilih saat aksi)


@pengadaan_router.post("/pengadaan/{perolehan_id}/buat-draft-aset")
async def buat_draft_aset_dari_perolehan(perolehan_id: str,
                                         payload: BuatDraftAsetIn,
                                         user: dict = Depends(require_writer)):
    """Buat aset draft dari baris barang perolehan yang BELUM bertaut (evaluasi #5).

    Untuk tiap baris `barang[]` tanpa `asset_id`: buat aset draft di kegiatan
    inventarisasi terpilih lewat jalur create aset yang ada (`buat_aset_draft`
    — registry/keunikan/kunci-kegiatan/audit tetap berlaku), NUP dinomori
    otomatis per (kode, kegiatan), lalu tautkan balik `barang[].asset_id` +
    proyeksi dokumen sumber. Baris tanpa kode barang DILEWATI (isi kode dulu).
    Satu baris = satu aset draft (harga = harga satuan; jumlah BAST dicatat).
    """
    from models import AssetCreate
    from routes.assets import buat_aset_draft

    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    act = await db.inventory_activities.find_one(
        {"id": payload.activity_id}, {"_id": 0, "id": 1, "nama_kegiatan": 1})
    if not act:
        raise HTTPException(status_code=404,
                            detail="Kegiatan inventarisasi tidak ditemukan")
    kategori_by_kode = {
        c["kode_aset"]: c.get("label", "")
        async for c in db.categories.find({}, {"_id": 0, "kode_aset": 1, "label": 1})
        if c.get("kode_aset")}

    barang = p.get("barang") or []
    now = datetime.now(timezone.utc).isoformat()
    dibuat, dilewati_tertaut, dilewati_tanpa_kode = 0, 0, 0
    gagal = []
    next_nup = {}   # kode → NUP numerik terakhir dalam kegiatan tujuan

    async def _nup_berikut(kode: str) -> str:
        if kode not in next_nup:
            res = await db.assets.aggregate([
                {"$match": {"activity_id": payload.activity_id, "asset_code": kode}},
                {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
                    "input": "$NUP", "to": "int", "onError": None, "onNull": None}}}}},
            ]).to_list(1)
            next_nup[kode] = int((res[0].get("max_nup") if res else None) or 0)
        next_nup[kode] += 1
        return str(next_nup[kode])

    for row in barang:
        if str(row.get("asset_id") or "").strip():
            dilewati_tertaut += 1
            continue
        kode = str(row.get("kode") or "").strip()
        if not kode:
            dilewati_tanpa_kode += 1
            continue
        jumlah = float(row.get("jumlah") or 1)
        # BMN ber-jumlah N = N unit ber-NUP masing-masing (audit G4 #10):
        # pecah jadi N draft ber-NUP berurut bila jumlah bulat 2..50; di luar
        # itu (pecahan/ekstrem) tetap 1 draft + catatan jumlah.
        n_unit = int(jumlah) if jumlah == int(jumlah) and 2 <= jumlah <= 50 else 1
        catatan_jumlah = (f" — jumlah pada BAST: {jumlah:g} unit"
                          if jumlah != 1 and n_unit == 1 else "")
        gagal_baris = False
        for unit_ke in range(1, n_unit + 1):
            sub = (f" (unit {unit_ke}/{n_unit})" if n_unit > 1 else "")
            draft = AssetCreate(
                asset_code=kode,
                NUP=await _nup_berikut(kode),
                asset_name=str(row.get("uraian") or "").strip(),
                category=kategori_by_kode.get(kode, ""),
                purchase_date=str(p.get("tanggal_bast") or "").strip()[:10],
                purchase_price=str(int(round(float(row.get("harga_satuan") or 0)))),
                nomor_bast=str(p.get("nomor_bast") or "").strip(),
                nomor_kontrak=str(p.get("nomor_kontrak") or "").strip(),
                perolehan_dari_nama=str(p.get("pihak") or "").strip(),
                supplier=str(p.get("pihak") or "").strip(),
                notes=(f"Draft otomatis dari perolehan Pengadaan "
                       f"(BAST {p.get('nomor_bast')}){sub}{catatan_jumlah}"),
                activity_id=payload.activity_id,
            )
            try:
                doc = await buat_aset_draft(
                    draft, audit_user=user.get("name") or user.get("username") or "system")
            except HTTPException as e:
                gagal.append(f"{row.get('uraian')}{sub}: {e.detail}")
                gagal_baris = True
                break
            if unit_ke == 1:
                row.update({"asset_id": doc["id"], "asset_code": doc["asset_code"],
                            "NUP": doc["NUP"], "asset_name": doc["asset_name"]})
            # Back-link dokumen sumber (§5A gap #6) ke aset draft yang baru dibuat.
            await db.assets.update_one(
                {"id": doc["id"]}, {"$set": build_asset_perolehan_projection(p, now)})
            # Jurnal Buku Barang (G7): perolehan → kode 101/102/103/105.
            from shared_utils import catat_mutasi_bmn
            kode_trx = str(JENIS_PEROLEHAN.get(p.get("jenis"), ("", "101"))[1]).split("/")[0]
            await catat_mutasi_bmn({
                "asset_id": doc["id"], "kode_transaksi": kode_trx or "101",
                "kode_barang": doc["asset_code"], "nup": str(doc["NUP"]),
                "tanggal_buku": (str(p.get("tanggal_bast") or "").strip()[:10]
                                 or now[:10]),
                "jumlah": 1, "nilai": float(row.get("harga_satuan") or 0),
                "sumber_modul": "pengadaan", "ref_id": perolehan_id,
                "keterangan": f"Draft aset dari BAST {p.get('nomor_bast') or '-'}",
                "oleh": user.get("username", "system")})
            dibuat += 1
        if gagal_baris:
            continue

    if dibuat:
        await db.pengadaan.update_one(
            {"id": perolehan_id},
            {"$set": {"barang": barang,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
    p["barang"] = barang
    return {"dibuat": dibuat, "dilewati_tertaut": dilewati_tertaut,
            "dilewati_tanpa_kode": dilewati_tanpa_kode, "gagal": gagal[:20],
            "kegiatan": act.get("nama_kegiatan") or act.get("id"),
            "perolehan": _enrich(p)}


@pengadaan_router.post("/pengadaan/{perolehan_id}/penganggaran")
async def tautkan_penganggaran(perolehan_id: str,
                               payload: TautkanPenganggaranIn,
                               _user: dict = Depends(require_writer)):
    """Tautkan/lepaskan perolehan ke usulan Penganggaran (#117 ↔ #115)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    snap = await _ambil_snapshot_penganggaran(payload.penganggaran_id)
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id}, {"$set": {**snap, "updated_at": now}})
    p.update(snap)
    return _enrich(p)


# Lampiran berkas per perolehan (scan kontrak/BAPHP/BAST/kuitansi/SP2D
# — melengkapi checklist dokumen sumber). Pola sama dengan #131/#132/#134.
_LAMPIRAN_MEDIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
_MAX_LAMPIRAN_BYTES = 10 * 1024 * 1024
_MAX_LAMPIRAN = 10


def _lampiran_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _LAMPIRAN_MEDIA:
        if name.endswith(ext):
            return ext
    return ""


@pengadaan_router.post("/pengadaan/{perolehan_id}/lampiran")
async def unggah_lampiran_perolehan(perolehan_id: str,
                                    file: UploadFile = File(...),
                                    user: dict = Depends(require_writer)):
    """Unggah scan dokumen sumber (PDF/gambar, maks 10MB, 10 berkas)."""
    p = await db.pengadaan.find_one(
        {"id": perolehan_id}, {"_id": 0, "id": 1, "lampiran_berkas": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    if len(p.get("lampiran_berkas") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per perolehan")
    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    ext = _lampiran_ext(filename)
    if not ext:
        raise HTTPException(status_code=400,
                            detail="Lampiran harus PDF atau gambar (JPG/PNG/WEBP)")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > _MAX_LAMPIRAN_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran lampiran maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    from bson import ObjectId
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=filename,
        metadata={"content_type": _LAMPIRAN_MEDIA[ext], "size": len(file_bytes),
                  "kind": "pengadaan", "perolehan_id": perolehan_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pengadaan.find_one_and_update(
        {"id": perolehan_id},
        {"$push": {"lampiran_berkas": entri},
         "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran_berkas": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    return {"message": "Lampiran terunggah",
            "lampiran_berkas": res.get("lampiran_berkas") or []}


@pengadaan_router.get("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def unduh_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   request: Request,
                                   _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran perolehan (menerima header ATAU ?token)."""
    p = await db.pengadaan.find_one(
        {"id": perolehan_id, "lampiran_berkas.file_id": file_id},
        {"_id": 0, "lampiran_berkas.$": 1})
    if not p or not p.get("lampiran_berkas"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = p["lampiran_berkas"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "dokumen"}"'})


@pengadaan_router.delete("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def hapus_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$pull": {"lampiran_berkas": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pengadaan_router.delete("/pengadaan/{perolehan_id}")
async def hapus_perolehan(perolehan_id: str,
                          _admin: dict = Depends(require_admin)):
    """Hapus register perolehan salah input (admin) + berkas lampirannya.

    Back-link `perolehan_id`/snapshot di aset tertaut DILEPAS dulu (temuan
    review #11 — dulu menggantung menunjuk perolehan yang sudah tidak ada).
    """
    p = await db.pengadaan.find_one({"id": perolehan_id},
                                    {"_id": 0, "lampiran_berkas": 1, "barang": 1})
    res = await db.pengadaan.delete_one({"id": perolehan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    for b in (p or {}).get("barang") or []:
        if b.get("asset_id"):
            await _lepas_perolehan_dari_aset(b["asset_id"], perolehan_id)
    for lamp in (p or {}).get("lampiran_berkas") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": perolehan_id}
