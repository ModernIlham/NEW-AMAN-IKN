"""PENGGUNAAN — Fase 3 tahap awal: rekap aset per pemegang lintas kegiatan.

Membaca data yang SUDAH dicatat modul inventarisasi (user, pengguna_nip,
pengguna_melekat_ke, pengguna_jabatan, bast_file_id) — tidak ada koleksi
baru; ini proyeksi baca. Daftar aset per pemegang dapat diunduh sebagai
PDF lampiran BAST. PSP/alih status/BMN idle menyusul sesuai masterplan
Fase 3 (PMK 40/2024 & 120/2024 — pustaka §1).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from penggunaan_utils import (
    STATUS_IDLE, indikasi_idle, kunci_pemegang, rekap_idle, rekap_pemegang,
    validate_transisi_idle,
)

penggunaan_router = APIRouter()

_PROJ = {"_id": 0, "user": 1, "pengguna_nip": 1, "pengguna_melekat_ke": 1,
         "pengguna_jabatan": 1, "bast_file_id": 1, "activity_id": 1}


@penggunaan_router.get("/penggunaan/pemegang")
async def daftar_pemegang(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Rekap pemegang: jumlah aset, kelengkapan BAST, jumlah kegiatan."""
    assets = [a async for a in db.assets.find(
        {"user": {"$exists": True, "$nin": ["", None]}}, _PROJ)]
    rows = rekap_pemegang(assets)
    if search.strip():
        s = search.strip().lower()
        rows = [r for r in rows if s in r["nama"].lower() or s in (r["nip"] or "")
                or s in (r["jabatan"] or "").lower()]
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "items": rows[start:start + page_size],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "total_pemegang": total,
        "total_lengkap": sum(1 for r in rows if r["lengkap"]),
    }


@penggunaan_router.get("/penggunaan/pemegang/aset")
async def aset_pemegang(
    nama: str = Query(..., min_length=1),
    nip: str = "",
    _user: dict = Depends(require_user),
):
    """Daftar aset yang dipegang satu orang (identitas nama+NIP)."""
    key = (" ".join(nama.split()).lower(), nip.strip())
    proj = {**_PROJ, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "location": 1, "condition": 1, "inventory_status": 1}
    out = []
    async for a in db.assets.find(
            {"user": {"$exists": True, "$nin": ["", None]}}, proj):
        if kunci_pemegang(a) == key:
            out.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "location": a.get("location"),
                "condition": a.get("condition"),
                "inventory_status": a.get("inventory_status"),
                "activity_id": a.get("activity_id"),
                "ada_bast": bool(str(a.get("bast_file_id") or "").strip()),
            })
    out.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return {"items": out, "total": len(out)}


class TiketIdleIn(BaseModel):
    asset_id: str = Field(min_length=1)
    keterangan: str = ""


class TransisiIdleIn(BaseModel):
    status: str
    nomor_usulan: str = ""       # surat usulan penyerahan ke Pengelola
    nomor_bast_serah: str = ""   # BAST penyerahan
    catatan: str = ""


_PROJ_IDLE = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "status": 1, "user": 1, "inventory_status": 1, "location": 1}


@penggunaan_router.get("/penggunaan/idle")
async def daftar_idle(_user: dict = Depends(require_user)):
    """Kandidat BMN idle (PMK 120/2024) + tiket penanganan + ringkasan."""
    tiket = [t async for t in db.bmn_idle.find({}, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    tiket_aktif = {t["asset_id"]: t for t in tiket
                   if t.get("status") in ("klarifikasi", "usul_serah")}
    kandidat = []
    async for a in db.assets.find({}, _PROJ_IDLE):
        ya, alasan = indikasi_idle(a)
        if not ya:
            continue
        t = tiket_aktif.get(a["id"])
        kandidat.append({
            "asset_id": a["id"], "asset_code": a.get("asset_code"),
            "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
            "location": a.get("location"), "alasan": alasan,
            "tiket": ({"id": t["id"], "status": t["status"]} if t else None),
        })
    kandidat.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return {"kandidat": kandidat, "tiket": tiket,
            "ringkasan": rekap_idle(kandidat, tiket),
            "label_status": STATUS_IDLE,
            "catatan": (
                "PMK 120/2024: BMN yang tidak digunakan untuk tugas dan fungsi "
                "wajib diteliti (klarifikasi); bila benar idle, diserahkan "
                "kepada Pengelola Barang. Kandidat dihitung otomatis dari "
                "status Nonaktif / tanpa pengguna.")}


@penggunaan_router.post("/penggunaan/idle")
async def buat_tiket_idle(payload: TiketIdleIn, user: dict = Depends(require_user)):
    """Buka tiket klarifikasi idle untuk satu aset kandidat."""
    a = await db.assets.find_one({"id": payload.asset_id}, _PROJ_IDLE)
    if not a:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    ya, alasan = indikasi_idle(a)
    if not ya:
        raise HTTPException(status_code=400,
                            detail="Aset bukan kandidat idle (berstatus aktif dan berpengguna)")
    aktif = await db.bmn_idle.find_one(
        {"asset_id": payload.asset_id,
         "status": {"$in": ["klarifikasi", "usul_serah"]}}, {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(status_code=409,
                            detail="Aset ini sudah punya tiket idle aktif")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": a["id"],
        "asset_code": a.get("asset_code"),
        "NUP": a.get("NUP"),
        "asset_name": a.get("asset_name"),
        "alasan": alasan,
        "status": "klarifikasi",
        "nomor_usulan": "",
        "nomor_bast_serah": "",
        "keterangan": str(payload.keterangan or "").strip(),
        "riwayat": [{"status": "klarifikasi", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.bmn_idle.insert_one({**record})
    return record


@penggunaan_router.post("/penggunaan/idle/{tiket_id}/status")
async def transisi_idle(tiket_id: str, payload: TransisiIdleIn,
                        admin: dict = Depends(require_admin)):
    """Pindahkan status tiket idle (admin — dokumen wajib per tahap)."""
    t = await db.bmn_idle.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    errors = validate_transisi_idle(t.get("status"), payload.status,
                                    payload.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "updated_at": now}
    if payload.status == "usul_serah":
        update["nomor_usulan"] = payload.nomor_usulan.strip()
    if payload.status == "diserahkan":
        update["nomor_bast_serah"] = payload.nomor_bast_serah.strip()
    res = await db.bmn_idle.find_one_and_update(
        # Anti-balapan: status lama diikutkan di filter
        {"id": tiket_id, "status": t["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status tiket berubah oleh proses lain — muat ulang")
    return res


@penggunaan_router.delete("/penggunaan/idle/{tiket_id}")
async def hapus_tiket_idle(tiket_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (hanya status klarifikasi)."""
    res = await db.bmn_idle.delete_one(
        {"id": tiket_id, "status": "klarifikasi"})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Tiket tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    return {"ok": True, "id": tiket_id}


@penggunaan_router.get("/penggunaan/pemegang/daftar-pdf")
async def daftar_pemegang_pdf(
    nama: str = Query(..., min_length=1),
    nip: str = "",
    _user: dict = Depends(require_user),
):
    """Daftar Barang yang Digunakan per pemegang (PDF lampiran BAST).

    Dokumen pendamping tertib administrasi penggunaan (PMK 40/2024):
    identitas pemegang + tabel aset yang dipegangnya + tanda tangan
    pemegang dan KPB. Data murni dari modul inventarisasi.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    key = (" ".join(nama.split()).lower(), nip.strip())
    proj = {**_PROJ, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "location": 1, "condition": 1}
    rows = []
    jabatan = ""
    melekat = ""
    nama_tampil = ""
    async for a in db.assets.find(
            {"user": {"$exists": True, "$nin": ["", None]}}, proj):
        if kunci_pemegang(a) != key:
            continue
        rows.append(a)
        if not jabatan:
            jabatan = str(a.get("pengguna_jabatan") or "").strip()
        if not melekat:
            melekat = str(a.get("pengguna_melekat_ke") or "").strip()
        if not nama_tampil:
            nama_tampil = " ".join(str(a.get("user") or "").split())
    nama_tampil = nama_tampil or " ".join(nama.split())
    if not rows:
        raise HTTPException(status_code=404,
                            detail="Pemegang tidak ditemukan / tanpa aset")
    rows.sort(key=lambda a: (a.get("asset_name") or "", a.get("asset_code") or ""))
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("DAFTAR BARANG YANG DIGUNAKAN",
                                 subjudul="Lampiran BAST Penggunaan BMN (PMK 40/2024)"))
    identitas = f"Nama pemegang: <b>{nama_tampil}</b>"
    if nip.strip():
        identitas += f" · NIP/NIK: {nip.strip()}"
    if jabatan:
        identitas += f" · Jabatan: {jabatan}"
    if melekat:
        identitas += f" · Melekat ke: {melekat}"
    elements.append(Paragraph(identitas, st['Meta']))
    elements.append(Paragraph(
        f"Barang Milik Negara sejumlah {len(rows)} unit berikut berada dalam "
        f"penggunaan pemegang tersebut dan wajib dipelihara serta dikembalikan "
        f"dalam keadaan baik saat berakhirnya penggunaan.", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Lokasi", "Kondisi", "BAST"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, a in enumerate(rows, start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(a.get("asset_code") or "-", st['Cell']),
            Paragraph(str(a.get("NUP") or "-"), st['CellCenter']),
            Paragraph(a.get("asset_name") or "-", st['Cell']),
            Paragraph(a.get("location") or "-", st['Cell']),
            Paragraph(a.get("condition") or "-", st['CellCenter']),
            Paragraph("✓" if str(a.get("bast_file_id") or "").strip() else "—",
                      st['CellCenter']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([24, 96, 34, 140, 90, 60, 34], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Pemegang Barang,',
         'nama': nama_tampil,
         'after': [f"NIP. {nip.strip() or '....................'}"]},
        {'pre': [''], 'header': 'Mengetahui,', 'role': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or '...........................',
         'after': [f"NIP. {settings.get('kasatker_nip') or '....................'}"]},
    ], doc.width))
    footer = _page_footer_factory("Daftar Barang yang Digunakan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama_file = nama_tampil.replace(" ", "_").replace("/", "-")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="Daftar_Barang_{nama_file}.pdf"'})
