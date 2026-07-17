"""PENGGUNAAN — Fase 3 tahap awal: rekap aset per pemegang lintas kegiatan.

Rekap per pemegang membaca data yang SUDAH dicatat modul inventarisasi
(user, pengguna_nip, pengguna_melekat_ke, pengguna_jabatan, bast_file_id)
— proyeksi baca, dapat diunduh sebagai PDF lampiran BAST. Register PSP
(SK + BAST), proses alih status/alih fungsi, dan BMN idle (klarifikasi →
usul serah) tersedia di modul ini (PMK 40/2024 & 120/2024 — pustaka §1);
transisi terminalnya memproyeksikan status ke master aset.
"""
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_user_or_query_token
from db import db, fs_bucket
from shared_utils import blok_ttd_kpb_titik, delete_document_from_gridfs, get_document_from_gridfs, log_audit
from penggunaan_utils import (
    ARAH_PROSES, JENIS_PROSES_PENGGUNAAN, JENIS_PSP, STATUS_IDLE,
    STATUS_PENGAJUAN_PSP, STATUS_PROSES, TRANSISI_PROSES, baris_csv_idle,
    baris_csv_proses, baris_csv_psp,
    build_asset_alih_keluar_projection, build_asset_idle_serah_projection,
    indikasi_idle,
    info_proses_sementara, kunci_pemegang, rekap_idle, rekap_pemegang,
    rekap_proses_penggunaan, rekap_psp, status_pengajuan_psp,
    validate_proses_penggunaan, validate_psp, validate_transisi_idle,
    validate_transisi_pengajuan_psp, validate_transisi_proses,
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
    halaman = rows[start:start + page_size]
    # Perkaya dgn Master Pegawai via NIP (temuan #36) — additif, hanya halaman ini.
    nips = {r.get("nip") for r in halaman if str(r.get("nip") or "").strip()}
    if nips:
        peg_map = {}
        async for pgw in db.pegawai.find(
                {"nip": {"$in": list(nips)}},
                {"_id": 0, "nip": 1, "nama": 1, "unit_kerja": 1, "status": 1}):
            peg_map[pgw["nip"]] = pgw
        for r in halaman:
            m = peg_map.get(str(r.get("nip") or "").strip())
            r["pegawai_master_nama"] = (m or {}).get("nama", "")
            r["pegawai_master_unit"] = (m or {}).get("unit_kerja", "")
            r["pegawai_terdaftar"] = bool(m)
    return {
        "items": halaman,
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
            "location": 1, "condition": 1, "inventory_status": 1,
            "bast_terakhir": 1}
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
                "bast_terakhir": a.get("bast_terakhir") or None,
            })
    out.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return {"items": out, "total": len(out)}


class PspIn(BaseModel):
    nomor_sk: str = ""             # wajib kecuali draf usulan
    tanggal_sk: str = ""           # wajib kecuali draf usulan
    jenis: str
    penetap: str = ""              # Pengelola Barang / Pengguna Barang (delegasi)
    keterangan: str = ""
    sebagai_draf: bool = False     # True = usulan PSP sebelum SK terbit
    asset_ids: list[str] = Field(min_length=1, max_length=200)


class TransisiPengajuanIn(BaseModel):
    status: str
    nomor_sk: str = ""             # wajib saat "ditetapkan"
    tanggal_sk: str = ""
    catatan: str = ""              # wajib saat ditolak/dikembalikan


@penggunaan_router.get("/penggunaan/psp")
async def daftar_psp(_user: dict = Depends(require_user)):
    """Register SK penetapan penggunaan + rekap + cakupan aset."""
    items = [s async for s in db.psp.find({}, {"_id": 0})
             .sort("tanggal_sk", -1).limit(500)]
    for s in items:
        # Normalisasi record lama tanpa field status (= SK sudah terbit)
        s["status_pengajuan"] = status_pengajuan_psp(s)
    total_aset = await db.assets.count_documents({})
    ringkasan = rekap_psp(items)
    ringkasan["total_aset"] = total_aset
    return {"items": items, "ringkasan": ringkasan,
            "label_jenis": JENIS_PSP,
            "label_status_pengajuan": STATUS_PENGAJUAN_PSP,
            "catatan": (
                "Register penatausahaan SK penggunaan (PMK 40/2024): PSP "
                "ditetapkan Pengelola Barang atau Pengguna Barang untuk BMN "
                "tertentu (delegasi). AMAN mencatat cakupan SK per aset — "
                "dokumen resmi tetap SK yang diterbitkan pejabat berwenang.")}


@penggunaan_router.get("/penggunaan/psp/export")
async def export_psp(_user: dict = Depends(require_user)):
    """Ekspor CSV register SK PSP — flatten per aset (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    items = [s async for s in db.psp.find({}, {"_id": 0}).sort("tanggal_sk", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_psp(items):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_sk_psp.csv"'})


@penggunaan_router.post("/penggunaan/psp")
async def catat_psp(payload: PspIn, user: dict = Depends(require_user)):
    """Catat satu SK penetapan penggunaan multi-aset (snapshot identitas)."""
    from datetime import datetime as dt

    data = payload.model_dump()
    today_iso = dt.now(timezone.utc).date().isoformat()
    errors = validate_psp(data, today_iso, draf=bool(data.get("sebagai_draf")))
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):
        a = await db.assets.find_one({"id": aid}, _PROJ_IDLE)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    now = dt.now(timezone.utc).isoformat()
    status_awal = "draf" if data.get("sebagai_draf") else "ditetapkan"
    record = {
        "id": str(uuid.uuid4()),
        "nomor_sk": str(data.get("nomor_sk") or "").strip(),
        "tanggal_sk": str(data.get("tanggal_sk") or "").strip()[:10],
        "jenis": data["jenis"],
        "penetap": str(data.get("penetap") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "status_pengajuan": status_awal,
        "riwayat_pengajuan": [{"status": status_awal, "tanggal": now,
                               "oleh": user.get("username"), "catatan": ""}],
        "aset": aset_rows,
        "lampiran": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.psp.insert_one({**record})
    return record


@penggunaan_router.post("/penggunaan/psp/{sk_id}/status")
async def transisi_pengajuan_psp(sk_id: str, payload: TransisiPengajuanIn,
                                 admin: dict = Depends(require_admin)):
    """Pindahkan status pengajuan PSP (admin — SK wajib saat penetapan)."""
    from datetime import datetime as dt

    sk = await db.psp.find_one({"id": sk_id}, {"_id": 0})
    if not sk:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    today_iso = dt.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_transisi_pengajuan_psp(sk, payload.status, data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = dt.now(timezone.utc).isoformat()
    update = {"status_pengajuan": payload.status, "updated_at": now}
    if payload.status == "ditetapkan":
        update["nomor_sk"] = payload.nomor_sk.strip()
        update["tanggal_sk"] = payload.tanggal_sk.strip()[:10]
    res = await db.psp.find_one_and_update(
        # Anti-balapan: status lama diikutkan di filter (record lama tanpa
        # field status terminal "ditetapkan" — tak pernah sampai sini)
        {"id": sk_id, "status_pengajuan": sk.get("status_pengajuan")},
        {"$set": update,
         "$push": {"riwayat_pengajuan": {
             "status": payload.status, "tanggal": now,
             "oleh": admin.get("username"),
             "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status usulan berubah oleh proses lain — muat ulang")
    return res


@penggunaan_router.get("/penggunaan/psp/{sk_id}/bast-pdf")
async def bast_psp_pdf(sk_id: str, _user: dict = Depends(require_user)):
    """BAST penetapan status penggunaan siap tanda tangan (PMK 40/2024).

    Kop surat satker, narasi dasar SK penetapan, tabel aset multi-baris,
    blok tanda tangan pihak yang menyerahkan/menerima + KPB. Data murni
    dari register SK — tanpa isian dummy.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    sk = await db.psp.find_one({"id": sk_id}, {"_id": 0})
    if not sk:
        raise HTTPException(status_code=404, detail="SK tidak ditemukan")
    if status_pengajuan_psp(sk) != "ditetapkan":
        raise HTTPException(status_code=400,
                            detail="BAST hanya untuk usulan yang sudah ditetapkan (SK terbit)")
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    aset = sk.get("aset") or []
    jenis = JENIS_PSP.get(sk.get("jenis"), sk.get("jenis") or "-")

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        "BERITA ACARA SERAH TERIMA\nPENETAPAN STATUS PENGGUNAAN "
        "BARANG MILIK NEGARA"))
    penetap = str(sk.get("penetap") or "").strip()
    elements.append(Paragraph(
        f"Berdasarkan Surat Keputusan {jenis} Nomor "
        f"<b>{sk.get('nomor_sk') or '-'}</b> tanggal "
        f"{_fmt_tanggal_id(sk.get('tanggal_sk'))}"
        + (f" yang ditetapkan oleh {penetap}" if penetap else "")
        + f", pada hari ini telah dilakukan serah terima {len(aset)} unit "
        f"Barang Milik Negara untuk penyelenggaraan tugas dan fungsi "
        f"(PMK 40 Tahun 2024), dengan rincian sebagai berikut:",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Kode Barang", "NUP", "Nama Barang"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, a in enumerate(aset, start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(a.get("asset_code") or "-", st['Cell']),
            Paragraph(str(a.get("NUP") or "-"), st['CellCenter']),
            Paragraph(a.get("asset_name") or "-", st['Cell']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([28, 140, 55, 250], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)

    if str(sk.get("keterangan") or "").strip():
        elements.append(Spacer(1, 3 * rl_mm))
        elements.append(Paragraph(f"Keterangan: {sk['keterangan']}", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))
    elements.append(Paragraph(
        "Pihak yang menerima bertanggung jawab atas penggunaan, pengamanan, "
        "dan pemeliharaan barang tersebut sesuai ketentuan pengelolaan BMN. "
        "Demikian Berita Acara Serah Terima ini dibuat dengan sebenarnya "
        "untuk dipergunakan sebagaimana mestinya.", st['Meta']))
    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Pihak yang Menyerahkan,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Pihak yang Menerima,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
    ], doc.width))
    elements.append(Spacer(1, 10 * rl_mm))
    elements.extend(_signature_block([
        await blok_ttd_kpb_titik(settings),   # KPB dari registry pejabat (temuan #26)
    ], doc.width))
    footer = _page_footer_factory("BAST Penetapan Status Penggunaan BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama_file = (sk.get("nomor_sk") or "SK").replace("/", "-").replace(" ", "-")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BAST_PSP_{nama_file}.pdf"'})


@penggunaan_router.delete("/penggunaan/psp/{sk_id}")
async def hapus_psp(sk_id: str, _admin: dict = Depends(require_admin)):
    """Hapus catatan SK salah input (khusus admin) + berkas lampirannya."""
    sk = await db.psp.find_one({"id": sk_id}, {"_id": 0, "lampiran": 1})
    res = await db.psp.delete_one({"id": sk_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SK tidak ditemukan")
    for lamp in (sk or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": sk_id}


# Arsip lampiran per SK PSP (scan SK penetapan + dokumen pendukung —
# PMK 40/2024). Pola sama dengan lampiran pemanfaatan/pemusnahan/
# penghapusan/pengadaan (#131/#132/#134/#135).
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


@penggunaan_router.post("/penggunaan/psp/{sk_id}/lampiran")
async def unggah_lampiran_psp(sk_id: str, file: UploadFile = File(...),
                              user: dict = Depends(require_user)):
    """Unggah scan SK/dokumen pendukung (PDF/gambar, maks 10MB, 10 berkas)."""
    sk = await db.psp.find_one({"id": sk_id}, {"_id": 0, "id": 1, "lampiran": 1})
    if not sk:
        raise HTTPException(status_code=404, detail="SK tidak ditemukan")
    if len(sk.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per SK")
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
                  "kind": "psp", "sk_id": sk_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.psp.find_one_and_update(
        {"id": sk_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="SK tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@penggunaan_router.get("/penggunaan/psp/{sk_id}/lampiran/{file_id}")
async def unduh_lampiran_psp(sk_id: str, file_id: str, request: Request,
                             _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran SK PSP (menerima header ATAU ?token)."""
    sk = await db.psp.find_one(
        {"id": sk_id, "lampiran.file_id": file_id}, {"_id": 0, "lampiran.$": 1})
    if not sk or not sk.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = sk["lampiran"][0]
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


@penggunaan_router.delete("/penggunaan/psp/{sk_id}/lampiran/{file_id}")
async def hapus_lampiran_psp(sk_id: str, file_id: str,
                             _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.psp.update_one(
        {"id": sk_id},
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="SK tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


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


@penggunaan_router.get("/penggunaan/idle/export")
async def export_idle(_user: dict = Depends(require_user)):
    """Ekspor CSV register tiket penanganan BMN idle (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    tiket = [t async for t in db.bmn_idle.find({}, {"_id": 0})
             .sort("created_at", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_idle(tiket):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_tiket_bmn_idle.csv"'})


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


async def _proyeksi_terminal_ke_aset(proj: dict, asset_ids: list,
                                     oleh: str, aksi: str) -> int:
    """Stamp proyeksi terminal (dihapus=True + subdoc penghapusan) ke aset
    tertaut — pola penghapusan #234: hanya aset yang BELUM dihapus, `$inc
    version` (bust cache + OCC), audit per aset. Best-effort: tiket sudah
    tersimpan; kegagalan proyeksi tak menggagalkan transisi. Kembalikan
    jumlah aset terproyeksi."""
    n = 0
    for aid in asset_ids or []:
        aid = str(aid or "").strip()
        if not aid:
            continue
        updated = await db.assets.find_one_and_update(
            {"id": aid, "dihapus": {"$ne": True}},
            {"$set": proj, "$inc": {"version": 1}},
            projection={"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1,
                        "asset_name": 1, "NUP": 1},
            return_document=True,
        )
        if not updated:
            continue   # sudah dihapus/diproyeksikan atau master tak ada — transisi tetap sah
        await log_audit(
            aksi, updated.get("activity_id", ""), updated.get("id", ""),
            updated.get("asset_code", ""), updated.get("asset_name", ""),
            username=oleh,
            detail=f"Aset keluar pembukuan satker ({aksi}) — dokumen "
                   f"{(proj.get('penghapusan') or {}).get('nomor_sk') or '-'}",
            nup=updated.get("NUP", ""))
        n += 1
    return n


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
    # Terminal: aset diserahkan ke Pengelola → keluar pembukuan satker
    # (proyeksi master, temuan review #1 — pola penghapusan #234).
    proj = build_asset_idle_serah_projection(res, now)
    if proj:
        await _proyeksi_terminal_ke_aset(
            proj, [res.get("asset_id")], admin.get("username"), "idle_diserahkan")
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
        _page_footer_factory, _peta_subsub_kelompok, _sel_identitas_barang,
        _sel_uraian_barang, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    key = (" ".join(nama.split()).lower(), nip.strip())
    proj = {**_PROJ, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "brand": 1, "model": 1, "serial_number": 1,
            "location": 1, "condition": 1, "bast_file_id": 1}
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

    # Tabel ringkas (selaras BAST): kolom Identitas (Sub-sub Kelompok · kode ·
    # NUP) + Uraian (Nama · Merk/Tipe/Spesifikasi) gabungan agar teks panjang lega.
    subsub = await _peta_subsub_kelompok([a.get("asset_code") for a in rows])
    from kodefikasi_utils import normalize_kode as _norm
    headers = ["No", "Identitas Barang\n(Sub-sub Kelompok · Kode · NUP)",
               "Uraian Barang\n(Nama · Merk/Tipe/Spesifikasi)",
               "Lokasi", "Kondisi", "BAST"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, a in enumerate(rows, start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            _sel_identitas_barang(a, subsub.get(_norm(a.get("asset_code")), ""), st),
            _sel_uraian_barang(a, st),
            Paragraph(a.get("location") or "-", st['Cell']),
            Paragraph(a.get("condition") or "-", st['CellCenter']),
            Paragraph("✓" if str(a.get("bast_file_id") or "").strip() else "—",
                      st['CellCenter']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([20, 150, 185, 74, 52, 30], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Pemegang Barang,',
         'nama': nama_tampil,
         'after': [f"NIP. {nip.strip() or '....................'}"]},
        await blok_ttd_kpb_titik(settings),   # KPB dari registry pejabat (temuan #26)
    ], doc.width))
    footer = _page_footer_factory("Daftar Barang yang Digunakan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama_file = nama_tampil.replace(" ", "_").replace("/", "-")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="Daftar_Barang_{nama_file}.pdf"'})


class ProsesIn(BaseModel):
    jenis_proses: str
    arah: str
    pihak_asal: str = Field(min_length=1)
    pihak_tujuan: str = Field(min_length=1)
    asset_ids: list[str] = Field(min_length=1, max_length=100)
    nomor_permohonan: str = ""
    tanggal_permohonan: str = ""
    tanggal_mulai: str = ""            # wajib utk penggunaan sementara
    tanggal_berakhir: str = ""
    keterangan: str = ""


class TransisiProsesIn(BaseModel):
    status: str
    catatan: str = ""
    nomor_dokumen: str = ""            # dokumen tahap ini (persetujuan/BAST/SK)
    tanggal_dokumen: str = ""


# Peta status tujuan → field dokumen yang diisi saat transisi.
_DOK_PROSES = {
    "disetujui": ("nomor_persetujuan", "tanggal_persetujuan"),
    "ditolak": ("nomor_penolakan", "tanggal_penolakan"),
    "bast_selesai": ("nomor_bast", "tanggal_bast"),
    "dihapus_dibukukan": ("nomor_sk_penghapusan", "tanggal_sk_penghapusan"),
    "berjalan": ("nomor_perjanjian", "tanggal_perjanjian"),
}


@penggunaan_router.get("/penggunaan/proses")
async def list_proses(_user: dict = Depends(require_user)):
    """Tiket proses alih status & penggunaan sementara + ringkasan."""
    items = [t async for t in db.penggunaan_proses.find({}, {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    today_iso = datetime.now(timezone.utc).date().isoformat()
    for t in items:
        t["info"] = info_proses_sementara(t, today_iso)
    return {"items": items,
            "ringkasan": rekap_proses_penggunaan(items, today_iso),
            "label_jenis": JENIS_PROSES_PENGGUNAAN,
            "label_arah": ARAH_PROSES,
            "label_status": STATUS_PROSES,
            "transisi": {j: {k: sorted(v) for k, v in peta.items()}
                         for j, peta in TRANSISI_PROSES.items()},
            "catatan": (
                "Register proses pendamping (PMK 40/2024, pustaka §14 butir "
                "22) — pengajuan resmi via SIMAN/DJKN; tenggat BAST/"
                "penghapusan hanya pengingat internal; SK final dicatat di "
                "register SK PSP.")}


@penggunaan_router.get("/penggunaan/proses/export")
async def export_proses(_user: dict = Depends(require_user)):
    """Ekspor CSV register proses penggunaan — flatten per aset (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [t async for t in db.penggunaan_proses.find({}, {"_id": 0})
             .sort("updated_at", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_proses(items, today_iso):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_proses_penggunaan.csv"'})


@penggunaan_router.post("/penggunaan/proses")
async def buat_proses(payload: ProsesIn, user: dict = Depends(require_user)):
    """Buka tiket proses baru (status awal draf; aset multi ber-snapshot)."""
    data = payload.model_dump()
    errors = validate_proses_penggunaan(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):
        a = await db.assets.find_one(
            {"id": aid},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
        if not a:
            raise HTTPException(status_code=404,
                                detail=f"Aset {aid} tidak ditemukan")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "jenis_proses": data["jenis_proses"],
        "arah": data["arah"],
        "pihak_asal": data["pihak_asal"].strip(),
        "pihak_tujuan": data["pihak_tujuan"].strip(),
        "aset": aset_rows,
        "status": "draf",
        "nomor_permohonan": str(data.get("nomor_permohonan") or "").strip(),
        "tanggal_permohonan": str(data.get("tanggal_permohonan") or "").strip()[:10],
        "tanggal_mulai": str(data.get("tanggal_mulai") or "").strip()[:10],
        "tanggal_berakhir": str(data.get("tanggal_berakhir") or "").strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        "riwayat": [{"status": "draf", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.penggunaan_proses.insert_one({**record})
    return record


@penggunaan_router.post("/penggunaan/proses/{tiket_id}/status")
async def transisi_proses(tiket_id: str, payload: TransisiProsesIn,
                          user: dict = Depends(require_user)):
    """Pindahkan status tiket (anti-race; dokumen tahap ikut tercatat)."""
    t = await db.penggunaan_proses.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    ke = payload.status
    errors = validate_transisi_proses(t, ke)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": ke, "updated_at": now}
    if ke in _DOK_PROSES:
        f_nomor, f_tanggal = _DOK_PROSES[ke]
        if str(payload.nomor_dokumen or "").strip():
            set_fields[f_nomor] = payload.nomor_dokumen.strip()
        if str(payload.tanggal_dokumen or "").strip():
            set_fields[f_tanggal] = payload.tanggal_dokumen.strip()[:10]
    entri = {"status": ke, "tanggal": now, "oleh": user.get("username"),
             "catatan": str(payload.catatan or "").strip()}
    res = await db.penggunaan_proses.find_one_and_update(
        {"id": tiket_id, "status": t["status"]},
        {"$set": set_fields, "$push": {"riwayat": entri}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Status tiket berubah di perangkat lain — muat ulang")
    res.update(set_fields)
    # Terminal alih status ARAH KELUAR: aset beralih ke Pengguna Barang lain &
    # dibukukan di sana → keluar pembukuan satker (proyeksi master, temuan
    # review #1 — pola penghapusan #234). Arah masuk TIDAK diproyeksikan.
    proj = build_asset_alih_keluar_projection(res, now)
    if proj:
        await _proyeksi_terminal_ke_aset(
            proj, [r.get("asset_id") for r in (res.get("aset") or [])],
            user.get("username"), "alih_status_keluar")
    return res


@penggunaan_router.delete("/penggunaan/proses/{tiket_id}")
async def hapus_proses(tiket_id: str, _admin: dict = Depends(require_admin)):
    """Hapus satu tiket proses (admin)."""
    res = await db.penggunaan_proses.delete_one({"id": tiket_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    return {"ok": True}
