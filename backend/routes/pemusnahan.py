"""PEMUSNAHAN — Fase 6 tahap awal: register Berita Acara Pemusnahan.

PMK 83/PMK.06/2016 (pustaka §1 & §12): BA dicatat setelah persetujuan +
pelaksanaan; objek dibatasi aset rusak berat (kelayakan divalidasi per
aset). Tindak lanjut penghapusan lewat modul Penghapusan.
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
from shared_utils import kode_satker_user, scope_query_field_satker, blok_ttd_kpb_titik, delete_document_from_gridfs, get_document_from_gridfs
from pemusnahan_utils import (
    CARA_PEMUSNAHAN, kelayakan_musnah, rekap_pemusnahan,
    usulan_penghapusan_dari_ba, validate_pemusnahan,
)

pemusnahan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "condition": 1}


class PemusnahanIn(BaseModel):
    nomor_ba: str
    tanggal_ba: str
    cara: str
    nomor_persetujuan: str
    keterangan: str = ""
    asset_ids: list[str] = Field(min_length=1, max_length=100)


@pemusnahan_router.get("/pemusnahan")
async def list_pemusnahan(_user: dict = Depends(require_user)):
    """Register BA pemusnahan (terbaru dulu) + ringkasan + status usulan."""
    items = [r async for r in db.pemusnahan.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("tanggal_ba", -1).limit(500)]
    # Satu kueri: aset BA mana yang sudah punya usulan penghapusan aktif
    semua_id = [a.get("asset_id") for r in items for a in (r.get("aset") or [])]
    diusulkan = set()
    if semua_id:
        async for u in db.usulan_penghapusan.find(
                {"asset_id": {"$in": semua_id}, "status": {"$ne": "ditolak"}},
                {"_id": 0, "asset_id": 1}):
            diusulkan.add(u["asset_id"])
    for r in items:
        r["aset_diusulkan"] = sum(
            1 for a in (r.get("aset") or []) if a.get("asset_id") in diusulkan)
    return {"items": items, "ringkasan": rekap_pemusnahan(items),
            "label_cara": CARA_PEMUSNAHAN,
            "catatan": (
                "BA dicatat setelah persetujuan Pengelola/Pengguna Barang dan "
                "pelaksanaan pemusnahan (PMK 83/2016); tindak lanjut usulan "
                "penghapusan lewat modul Penghapusan.")}


@pemusnahan_router.get("/pemusnahan/export")
async def export_pemusnahan(_user: dict = Depends(require_user)):
    """Ekspor CSV register BA pemusnahan (pola #158)."""
    import csv as csv_module
    import io

    from pembukuan_utils import parse_harga

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["nomor_ba", "tanggal_ba", "cara", "nomor_persetujuan",
                "jumlah_aset", "nilai_perolehan", "keterangan",
                "jumlah_lampiran", "dibuat_oleh"])
    async for r in db.pemusnahan.find(scope_query_field_satker(_user), {"_id": 0}).sort("tanggal_ba", -1):
        aset = r.get("aset") or []
        w.writerow([
            r.get("nomor_ba"), r.get("tanggal_ba"),
            CARA_PEMUSNAHAN.get(r.get("cara"), r.get("cara")),
            r.get("nomor_persetujuan"), len(aset),
            int(sum(parse_harga(a.get("harga")) for a in aset)),
            r.get("keterangan"), len(r.get("lampiran") or []),
            r.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_pemusnahan.csv"'})


@pemusnahan_router.post("/pemusnahan")
async def buat_pemusnahan(payload: PemusnahanIn, user: dict = Depends(require_writer)):
    """Catat satu BA pemusnahan multi-aset (aset harus rusak berat)."""
    data = payload.model_dump()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    errors = validate_pemusnahan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):  # dedup, jaga urutan
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        layak, alasan = kelayakan_musnah(a)
        if not layak:
            raise HTTPException(status_code=400,
                                detail=f"{a.get('asset_name') or aid}: {alasan}")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "harga": a.get("purchase_price")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": kode_satker_user(user),
        "nomor_ba": data["nomor_ba"].strip(),
        "tanggal_ba": str(data["tanggal_ba"]).strip()[:10],
        "cara": data["cara"],
        "nomor_persetujuan": data["nomor_persetujuan"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "aset": aset_rows,
        "lampiran": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemusnahan.insert_one({**record})
    # Cek silang lintas register keluar (non-blocking, audit G5 #11).
    from shared_utils import proses_keluar_aktif
    peta = await proses_keluar_aktif([a.get("asset_id") for a in record.get("aset") or []])
    record["peringatan_proses"] = [
        f"{next((a.get('asset_name') for a in record['aset'] if a.get('asset_id') == aid), aid)}: "
        f"juga dalam {', '.join(x for x in labels if x != 'BA pemusnahan')}"
        for aid, labels in peta.items()
        if [x for x in labels if x != "BA pemusnahan"]][:10]
    return record


@pemusnahan_router.post("/pemusnahan/{ba_id}/usulkan-penghapusan")
async def usulkan_penghapusan_dari_ba(ba_id: str,
                                      user: dict = Depends(require_writer)):
    """Buat usulan penghapusan (register Penghapusan) untuk aset BA ini.

    Tindak lanjut PMK 83/2016: barang yang telah dimusnahkan diusulkan
    hapus dari DBKP. Aset yang sudah punya usulan aktif dilewati (bukan
    galat) supaya tombol aman diklik ulang.
    """
    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0})
    if not ba:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    hasil = []
    dibuat = 0
    for a in ba.get("aset") or []:
        aid = a.get("asset_id")
        aktif = await db.usulan_penghapusan.find_one(
            {"asset_id": aid, "status": {"$ne": "ditolak"}},
            {"_id": 0, "id": 1, "status": 1})
        if aktif:
            hasil.append({"asset_id": aid, "asset_name": a.get("asset_name"),
                          "dibuat": False,
                          "alasan": f"Sudah ada usulan aktif ({aktif.get('status')})"})
            continue
        now = datetime.now(timezone.utc).isoformat()
        # Record ber-TAUT sumber (Pemusnahan → Penghapusan) — helper murni teruji.
        record = usulan_penghapusan_dari_ba(ba, a, now, user.get("username"), str(uuid.uuid4()))
        await db.usulan_penghapusan.insert_one({**record})
        dibuat += 1
        hasil.append({"asset_id": aid, "asset_name": a.get("asset_name"),
                      "dibuat": True, "alasan": ""})
    return {"total": len(hasil), "dibuat": dibuat,
            "terlewati": len(hasil) - dibuat, "hasil": hasil}


@pemusnahan_router.get("/pemusnahan/{ba_id}/ba-pdf")
async def ba_pemusnahan_pdf(ba_id: str, _user: dict = Depends(require_user)):
    """Berita Acara Pemusnahan siap tanda tangan (PMK 83/2016).

    Kop surat satker, narasi dasar persetujuan + cara pemusnahan, tabel
    aset multi-baris dengan nilai perolehan, blok tanda tangan pelaksana/
    saksi/KPB. Data murni dari register — tanpa isian dummy.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from pembukuan_utils import parse_harga
    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0})
    if not ba:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    aset = ba.get("aset") or []
    cara = CARA_PEMUSNAHAN.get(ba.get("cara"), ba.get("cara") or "-")

    def _rp(v):
        n = parse_harga(v)
        return f"Rp{n:,.0f}".replace(",", ".") if n else "-"

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("BERITA ACARA PEMUSNAHAN BARANG MILIK NEGARA",
                                 nomor=ba.get("nomor_ba") or "-"))
    elements.append(Paragraph(
        f"Pada tanggal {_fmt_tanggal_id(ba.get('tanggal_ba'))}, berdasarkan "
        f"persetujuan pemusnahan Nomor {ba.get('nomor_persetujuan') or '-'}, "
        f"telah dilaksanakan pemusnahan Barang Milik Negara dengan cara "
        f"<b>{_esc(cara.lower())}</b> terhadap {len(aset)} unit barang dalam kondisi "
        f"rusak berat yang tidak dapat digunakan, dimanfaatkan, maupun "
        f"dipindahtangankan (PMK 83/PMK.06/2016), dengan rincian sebagai berikut:",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    from xml.sax.saxutils import escape as _esc
    headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    total = 0.0
    for i, a in enumerate(aset, start=1):
        total += parse_harga(a.get("harga"))
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(_esc(a.get("asset_code") or "-"), st['Cell']),
            Paragraph(str(a.get("NUP") or "-"), st['CellCenter']),
            Paragraph(_esc(a.get("asset_name") or "-"), st['Cell']),
            Paragraph(_rp(a.get("harga")), st['CellRight']),
        ])
    table_data.append([
        Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph("<b>Jumlah</b>", st['Cell']),
        Paragraph(f"<b>{_rp(total)}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([28, 120, 45, 190, 90], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    if str(ba.get("keterangan") or "").strip():
        elements.append(Spacer(1, 3 * rl_mm))
        elements.append(Paragraph(f"Keterangan: {_esc(ba['keterangan'])}", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))
    elements.append(Paragraph(
        "Demikian Berita Acara Pemusnahan ini dibuat dengan sebenarnya untuk "
        "dipergunakan sebagaimana mestinya, sebagai dasar usulan penghapusan "
        "dari Daftar Barang Kuasa Pengguna.", st['Meta']))
    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Pelaksana,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Saksi,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        await blok_ttd_kpb_titik(settings, kode_satker=kode_satker_user(_user)),   # KPB dari registry pejabat (temuan #26)
    ], doc.width))
    footer = _page_footer_factory("Berita Acara Pemusnahan BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama_file = (ba.get("nomor_ba") or "BA").replace("/", "-").replace(" ", "_")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BA_Pemusnahan_{nama_file}.pdf"'})


# Lampiran bukti per BA (PMK 83/2016: foto pelaksanaan + scan BA
# bertanda tangan). Pola sama dengan lampiran pemanfaatan (#131).
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


@pemusnahan_router.post("/pemusnahan/{ba_id}/lampiran")
async def unggah_lampiran_ba(ba_id: str, file: UploadFile = File(...),
                             user: dict = Depends(require_writer)):
    """Unggah foto bukti/scan BA (PDF/gambar, maks 10MB, 10 berkas)."""
    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0, "id": 1, "lampiran": 1})
    if not ba:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    if len(ba.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per BA")
    filename = (file.filename or "bukti.jpg").strip() or "bukti.jpg"
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
                  "kind": "pemusnahan", "ba_id": ba_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pemusnahan.find_one_and_update(
        {"id": ba_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@pemusnahan_router.get("/pemusnahan/{ba_id}/lampiran/{file_id}")
async def unduh_lampiran_ba(ba_id: str, file_id: str, request: Request,
                            _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran BA (menerima header ATAU ?token untuk window.open)."""
    ba = await db.pemusnahan.find_one(
        {"id": ba_id, "lampiran.file_id": file_id}, {"_id": 0, "lampiran.$": 1})
    if not ba or not ba.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = ba["lampiran"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "bukti"}"'})


@pemusnahan_router.delete("/pemusnahan/{ba_id}/lampiran/{file_id}")
async def hapus_lampiran_ba(ba_id: str, file_id: str,
                            _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pemusnahan.update_one(
        {"id": ba_id},
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pemusnahan_router.delete("/pemusnahan/{ba_id}")
async def hapus_pemusnahan(ba_id: str, _admin: dict = Depends(require_admin)):
    """Hapus BA salah input (khusus admin) + berkas lampirannya."""
    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0, "lampiran": 1})
    res = await db.pemusnahan.delete_one({"id": ba_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    for lamp in (ba or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": ba_id}
