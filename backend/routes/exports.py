"""
Export routes (CSV, PDF, XLSX), document file serving, bulk delete.
Extracted from assets.py for clean separation of concerns.
"""
import io
import asyncio
import os
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends
from auth_utils import require_user
from fastapi.responses import StreamingResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import xlsxwriter
from PIL import Image as PILImage

from asset_fields import SCALAR_FIELD_NAMES
from db import db
from shared_utils import limiter, invalidate_asset_cache, log_audit, get_photo_from_gridfs

logger = logging.getLogger(__name__)
exports_router = APIRouter()

def _safe_price_float(val) -> float:
    """purchase_price berupa string bebas — nilai tak numerik dihitung 0
    (selaras $convert onError:0 pada agregasi ringkasan), bukan error 500."""
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0


# Default nilai kolom CSV saat field tidak ada di dokumen (dokumen lama).
_CSV_ROW_DEFAULTS = {
    "stiker_status": "Belum Terpasang",
    "inventory_status": "Belum Diinventarisasi",
}

# Header sheet "Data Aset" pada ekspor XLSX. Kolom skalar memakai label dari
# registry (asset_fields.py); test registry menagih bila ada field baru yang
# belum punya kolom di sini.
ASSET_SHEET_HEADERS = ['Foto', 'Foto Stiker', 'Kode Aset', 'NUP', 'Nama Aset', 'Kategori', 'Brand', 'Model',
                       'Kode Register', 'Serial Number', 'Tgl Beli', 'Harga', 'Lokasi', 'Eselon I', 'Eselon II',
                       'Pengguna', 'Melekat Ke', 'Jabatan Pengguna', 'NIP/NIK Pegawai', 'Jenis Operasional', 'Nomor BAST',
                       'Kondisi', 'Status', 'Stiker Status', 'Ukuran Stiker',
                       'Nomor SPM', 'Perolehan Dari',
                       'Nomor Kontrak', 'Bukti Perolehan', 'Supplier', 'Catatan',
                       'Status Inventarisasi', 'Klasifikasi', 'Sub Klasifikasi', 'Uraian Tidak Ditemukan', 'Tindak Lanjut',
                       'Latitude', 'Longitude', 'Kronologis',
                       'Keterangan Berlebih', 'Asal Usul Berlebih', 'Nomor Perkara', 'Pihak Bersengketa', 'Keterangan Sengketa',
                       'Jumlah Foto', 'Tanggal Input']


def _xlsx_image_buffer(img_data: str, max_px: int, quality: int = 70) -> io.BytesIO:
    """Fast image prep for embedding photos in XLSX exports.

    Decodes base64, uses PIL ``draft()`` for a cheap partial JPEG decode,
    flattens any alpha channel onto white, downsizes with a fast BILINEAR
    filter and re-encodes as JPEG. Replaces the previous lossless-PNG path
    (~375 ms/asset) with a ~31 ms/asset path so large exports finish well
    inside the nginx 120 s timeout.
    """
    raw = img_data.split(",", 1)[1] if "," in img_data else img_data
    img = PILImage.open(io.BytesIO(base64.b64decode(raw)))
    # Cheap partial decode for JPEG sources (no-op for PNG).
    img.draft("RGB", (max_px, max_px))
    # Flatten transparency onto white because JPEG has no alpha channel.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        background = PILImage.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((max_px, max_px), PILImage.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=False)
    buf.seek(0)
    return buf


# ============================================================================

def format_document_checklist_for_csv(checklist: list, asset_id: str, base_url: str = "") -> dict:
    """Format document_checklist for CSV export - returns dict with separate fields"""
    result = {
        "kelengkapan_items": "",
        "kelengkapan_foto_links": "",
        "kelengkapan_pdf_links": ""
    }
    
    if not checklist:
        return result
    
    items = []
    foto_links = []
    pdf_links = []
    
    for idx, item in enumerate(checklist):
        name = item.get('name', '')
        checked = "✓" if item.get('checked') else "✗"
        notes = item.get('notes', '')
        photos = item.get('photos', [])
        documents = item.get('documents', [])
        
        # Item info
        item_str = f"{name}:{checked}"
        if notes:
            item_str += f"({notes})"
        items.append(item_str)
        
        # Photo links
        if photos and base_url:
            for pi in range(len(photos)):
                foto_links.append(f"{base_url}/api/assets/{asset_id}/doc-file/{idx}/photo/{pi}")
        
        # Document links
        if documents and base_url:
            for di in range(len(documents)):
                doc_name = documents[di].get('name', f'doc_{di}.pdf')
                pdf_links.append(f"{doc_name}={base_url}/api/assets/{asset_id}/doc-file/{idx}/document/{di}")
    
    result["kelengkapan_items"] = " | ".join(items)
    result["kelengkapan_foto_links"] = " | ".join(foto_links)
    result["kelengkapan_pdf_links"] = " | ".join(pdf_links)
    
    return result

def format_document_checklist_for_xlsx(checklist: list, asset_id: str, base_url: str = "") -> list:
    """Format document_checklist for XLSX export - returns list of dicts for separate sheet"""
    rows = []
    
    if not checklist:
        return rows
    
    for idx, item in enumerate(checklist):
        name = item.get('name', '')
        checked = item.get('checked', False)
        notes = item.get('notes', '')
        photos = item.get('photos', [])
        documents = item.get('documents', [])
        
        row = {
            "asset_id": asset_id,
            "item_name": name,
            "status": "✓ Ada" if checked else "✗ Tidak Ada",
            "catatan": notes,
            "jumlah_foto": len(photos),
            "jumlah_dokumen": len(documents),
            "foto_links": [],
            "dokumen_links": []
        }
        
        if photos and base_url:
            row["foto_links"] = [f"{base_url}/api/assets/{asset_id}/doc-file/{idx}/photo/{pi}" for pi in range(len(photos))]
        
        if documents and base_url:
            row["dokumen_links"] = [f"{base_url}/api/assets/{asset_id}/doc-file/{idx}/document/{di}" for di in range(len(documents))]
        
        rows.append(row)
    
    return rows

# NOTE (auth posture): this stays a PUBLIC stream — the CSV/XLSX exports embed
# doc-file links meant to be opened later from a spreadsheet (no auth header/
# token available there). We DO harden it: the served Content-Type is derived
# from the file KIND (never the attacker-controllable stored data-URL MIME),
# and X-Content-Type-Options: nosniff blocks browser MIME-sniffing.
_DOCFILE_NOSNIFF = {"X-Content-Type-Options": "nosniff"}


@exports_router.get("/assets/{asset_id}/doc-file/{item_idx}/{file_type}/{file_idx}")
async def get_asset_doc_file(asset_id: str, item_idx: int, file_type: str, file_idx: int):
    """Get a specific file (photo or document) from document_checklist"""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    checklist = asset.get('document_checklist', [])
    if item_idx >= len(checklist):
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")

    item = checklist[item_idx]

    if file_type == "photo":
        photos = item.get('photos', [])
        if file_idx >= len(photos):
            raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
        photo_data = photos[file_idx]

        # Ignore any stored data-URL MIME — photos are always served as JPEG.
        encoded = photo_data.split("base64,", 1)[1] if "base64," in photo_data else photo_data
        image_bytes = base64.b64decode(encoded)
        return StreamingResponse(
            io.BytesIO(image_bytes),
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f"inline; filename=foto_{item_idx}_{file_idx}.jpg",
                **_DOCFILE_NOSNIFF,
            },
        )

    elif file_type == "document":
        documents = item.get('documents', [])
        if file_idx >= len(documents):
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
        doc = documents[file_idx]
        doc_data = doc.get('data', '')
        doc_name = doc.get('name', f'document_{file_idx}.pdf')

        # Documents are always PDFs — serve as application/pdf regardless of the
        # stored data-URL MIME. `attachment` (not inline) is safer for docs.
        encoded = doc_data.split("base64,", 1)[1] if "base64," in doc_data else doc_data
        doc_bytes = base64.b64decode(encoded)
        return StreamingResponse(
            io.BytesIO(doc_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{doc_name}"',
                **_DOCFILE_NOSNIFF,
            },
        )

    raise HTTPException(status_code=400, detail="Tipe file tidak valid")

@exports_router.delete("/assets/bulk-delete/{activity_id}")
@limiter.limit("3/minute")
async def bulk_delete_assets(request: Request, activity_id: str, _user: dict = Depends(require_user)):
    """Delete all assets for a specific activity"""
    activity = await db.inventory_activities.find_one({"id": activity_id})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan inventarisasi tidak ditemukan")
    if activity.get("status_pengesahan") == "disahkan":
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    count = await db.assets.count_documents({"activity_id": activity_id})
    if count == 0:
        return {"message": "Tidak ada aset untuk dihapus", "deleted": 0}
    
    result = await db.assets.delete_many({"activity_id": activity_id})
    
    logger.info(f"Bulk deleted {result.deleted_count} assets for activity {activity_id}")
    invalidate_asset_cache()
    audit_user = request.headers.get("X-Audit-User", "unknown")
    await log_audit("bulk_delete", activity_id, "", "", "", audit_user, detail=f"Hapus massal {result.deleted_count} aset")
    
    return {
        "message": f"Berhasil menghapus {result.deleted_count} aset dari kegiatan ini",
        "deleted": result.deleted_count
    }

@exports_router.get("/export/csv")
@limiter.limit("5/minute")
async def export_csv(request: Request, activity_id: Optional[str] = None, base_url: str = "",
                     _user: dict = Depends(require_user)):
    """Export assets to CSV format - streaming for large datasets with document checklist"""
    query = {"activity_id": activity_id} if activity_id else {}
    total = await db.assets.count_documents(query)
    if total == 0:
        raise HTTPException(status_code=404, detail="Tidak ada data untuk diexport")
    
    async def generate_csv():
        # Fetch activity data if activity_id provided
        act_data = None
        if activity_id:
            act_data = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
        
        # Activity header info
        if act_data:
            yield f"# Kegiatan: {act_data.get('nama_kegiatan','')}\n"
            yield f"# Nomor Surat: {act_data.get('nomor_surat','')}\n"
            yield f"# Kode Satker: {act_data.get('kode_satker','')} - {act_data.get('nama_satker','')}\n"
            yield f"# Periode: {act_data.get('tanggal_mulai','')} s/d {act_data.get('tanggal_selesai','')}\n"
            yield f"# Penanggung Jawab: {act_data.get('penanggung_jawab','')}\n"
            eselon_list = act_data.get('eselon1', [])
            for es in eselon_list:
                nama_es1 = es.get('nama', '') if isinstance(es, dict) else str(es)
                eselon2_list = es.get('eselon2', []) if isinstance(es, dict) else []
                yield f"# Eselon I: {nama_es1} | Eselon II: {', '.join(eselon2_list)}\n"
            yield "#\n"
        
        # Kolom skalar diambil dari registry (asset_fields.py) supaya field
        # baru otomatis ikut ter-ekspor; sisanya kolom turunan/kelengkapan.
        yield ",".join([*SCALAR_FIELD_NAMES, "jumlah_foto", "tanggal_input",
                        "kelengkapan_items", "link_foto_kelengkapan", "link_pdf_kelengkapan"]) + "\n"
        
        projection = {"_id": 0, "photo": 0, "photos": 0, "thumbnail": 0, "photo_thumbnails": 0}
        cursor = db.assets.find(query, projection).batch_size(500)
        
        async for asset in cursor:
            # Format document checklist into separate columns
            doc_data = format_document_checklist_for_csv(
                asset.get('document_checklist', []),
                asset.get('id', ''),
                base_url
            )
            
            # Photo count from photo_gridfs_ids or photos array
            photo_count = len(asset.get('photo_gridfs_ids', []))
            
            row = [
                *[asset.get(n, _CSV_ROW_DEFAULTS.get(n, '')) for n in SCALAR_FIELD_NAMES],
                str(photo_count),
                asset.get('created_at', ''),
                doc_data.get('kelengkapan_items', ''),
                doc_data.get('kelengkapan_foto_links', ''),
                doc_data.get('kelengkapan_pdf_links', '')
            ]
            yield ','.join([f'"{str(item).replace(chr(34), chr(39))}"' for item in row]) + '\n'
    
    logger.info(f"📤 Streaming CSV export ({total} assets, activity_id={activity_id})")
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"}
    )

@exports_router.get("/export/pdf")
@limiter.limit("3/minute")
async def export_pdf(request: Request, activity_id: Optional[str] = None,
                     _user: dict = Depends(require_user)):
    """Export assets to professional PDF report with HD photos"""
    query = {"activity_id": activity_id} if activity_id else {}
    total = await db.assets.count_documents(query)
    if total == 0:
        raise HTTPException(status_code=404, detail="Tidak ada data untuk diexport")
    
    # Get stats via aggregation
    match_stage = {"$match": query} if activity_id else {"$match": {}}
    stats_pipeline = [match_stage, {"$group": {
        "_id": None,
        "total_value": {"$sum": {"$convert": {"input": "$purchase_price", "to": "double", "onError": 0, "onNull": 0}}},
        "active": {"$sum": {"$cond": [{"$eq": ["$status", "Aktif"]}, 1, 0]}},
        "maintenance": {"$sum": {"$cond": [{"$eq": ["$status", "Maintenance"]}, 1, 0]}},
        "idle": {"$sum": {"$cond": [{"$eq": ["$status", "Idle"]}, 1, 0]}},
        "nonaktif": {"$sum": {"$cond": [{"$eq": ["$status", "Nonaktif"]}, 1, 0]}}
    }}]
    stats_result = await db.assets.aggregate(stats_pipeline).to_list(1)
    sr = stats_result[0] if stats_result else {}
    total_value = sr.get("total_value", 0)
    
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import PageBreak, KeepTogether
    
    buffer = io.BytesIO()
    
    # Page number callback
    def add_page_number(cvs, doc_obj):
        page_num = cvs.getPageNumber()
        text = f"Halaman {page_num}"
        cvs.saveState()
        cvs.setFont('Helvetica', 7)
        cvs.setFillColor(colors.HexColor('#94a3b8'))
        cvs.drawRightString(doc_obj.pagesize[0] - 15*mm, 10*mm, text)
        cvs.restoreState()
    
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('PDFTitle', parent=styles['Heading1'],
        fontSize=22, textColor=colors.HexColor('#0f172a'),
        spaceAfter=4, alignment=1, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('PDFSubtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#64748b'),
        spaceAfter=16, alignment=1)
    stat_style = ParagraphStyle('PDFStat', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#334155'))
    cell_style = ParagraphStyle('PDFCell', parent=styles['Normal'],
        fontSize=7, leading=9, textColor=colors.HexColor('#1e293b'))
    cell_small = ParagraphStyle('PDFCellSmall', parent=styles['Normal'],
        fontSize=6, leading=8, textColor=colors.HexColor('#64748b'))
    
    # === HEADER ===
    elements.append(Paragraph("LAPORAN INVENTARIS ASET", title_style))
    now_str = datetime.now(timezone(timedelta(hours=7))).strftime("%d %B %Y, %H:%M WIB")
    elements.append(Paragraph(f"Dicetak pada: {now_str}", subtitle_style))
    
    # === SUMMARY BOX ===
    summary_data = [[
        Paragraph(f"<b>Total Aset</b><br/>{total:,}", stat_style),
        Paragraph(f"<b>Total Nilai</b><br/>Rp {total_value:,.0f}", stat_style),
        Paragraph(f"<b>Aktif</b><br/>{sr.get('active', 0):,}", stat_style),
        Paragraph(f"<b>Maintenance</b><br/>{sr.get('maintenance', 0):,}", stat_style),
        Paragraph(f"<b>Idle</b><br/>{sr.get('idle', 0):,}", stat_style),
        Paragraph(f"<b>Nonaktif</b><br/>{sr.get('nonaktif', 0):,}", stat_style),
    ]]
    summary_table = Table(summary_data, colWidths=[44*mm]*6)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))
    
    # === DATA TABLE ===
    header_row = [
        Paragraph('<b>Foto</b>', cell_style),
        Paragraph('<b>Kode Aset</b>', cell_style),
        Paragraph('<b>Nama Aset</b>', cell_style),
        Paragraph('<b>Kategori</b>', cell_style),
        Paragraph('<b>Brand / Model</b>', cell_style),
        Paragraph('<b>Lokasi</b>', cell_style),
        Paragraph('<b>Kondisi</b>', cell_style),
        Paragraph('<b>Status</b>', cell_style),
        Paragraph('<b>Stiker</b>', cell_style),
        Paragraph('<b>Harga Beli</b>', cell_style),
    ]
    table_data = [header_row]
    
    # Use thumbnail for fast PDF generation - skip loading full photos array
    projection = {"_id": 0, "asset_code": 1, "asset_name": 1, "category": 1,
                  "brand": 1, "model": 1, "location": 1, "eselon1": 1, "eselon2": 1,
                  "condition": 1, "status": 1, "purchase_price": 1,
                  "thumbnail": 1, "photo_thumbnails": 1, "thumbnail_index": 1,
                  "stiker_status": 1, "stiker_ukuran": 1}
    cursor = db.assets.find(query, projection).batch_size(200)
    
    async for asset in cursor:
        photo_element = ''
        # Use thumbnail for fast PDF - try photo_thumbnails first, then thumbnail field
        img_data = None
        thumbnails = asset.get('photo_thumbnails', [])
        tidx = asset.get('thumbnail_index', 0) or 0
        if thumbnails and tidx < len(thumbnails):
            img_data = thumbnails[tidx]
        elif thumbnails:
            img_data = thumbnails[0]
        if not img_data:
            img_data = asset.get('thumbnail')
        if img_data:
            try:
                if "base64," in img_data:
                    encoded = img_data.split("base64,", 1)[1]
                else:
                    encoded = img_data
                image_bytes = base64.b64decode(encoded)
                img = PILImage.open(io.BytesIO(image_bytes))
                # Small thumbnail for PDF table: 80x80 max for speed
                img.thumbnail((80, 80), PILImage.LANCZOS)
                img_buf = io.BytesIO()
                img.save(img_buf, format="JPEG", quality=60)
                img_buf.seek(0)
                photo_element = RLImage(img_buf, width=18*mm, height=18*mm)
            except Exception:
                photo_element = ''
        
        brand_model = asset.get('brand', '')
        if asset.get('model'):
            brand_model += f"<br/>{asset.get('model', '')}" if brand_model else asset.get('model', '')
        
        # Color-coded condition
        cond = asset.get('condition', '')
        cond_color = '#16a34a' if cond == 'Baik' else '#d97706' if cond == 'Rusak Ringan' else '#dc2626'
        
        # Color-coded status
        stat = asset.get('status', '')
        if stat == 'Aktif':
            stat_color = '#16a34a'
        elif stat == 'Idle':
            stat_color = '#0284c7'  # sky-600 — distinguishes idle (paused) from maintenance
        elif stat == 'Maintenance':
            stat_color = '#d97706'
        else:
            stat_color = '#dc2626'
        
        cond_style = ParagraphStyle('CondStyle', parent=cell_style, textColor=colors.HexColor(cond_color))
        stat_style_row = ParagraphStyle('StatStyle', parent=cell_style, textColor=colors.HexColor(stat_color))
        
        table_data.append([
            photo_element,
            Paragraph(asset.get('asset_code', ''), cell_style),
            Paragraph(asset.get('asset_name', ''), cell_style),
            Paragraph(asset.get('category', ''), cell_small),
            Paragraph(brand_model, cell_small),
            Paragraph(asset.get('location', ''), cell_small),
            Paragraph(f"<b>{cond}</b>", cond_style),
            Paragraph(f"<b>{stat}</b>", stat_style_row),
            Paragraph(f"{asset.get('stiker_status', 'Belum Terpasang')}" + (f"<br/>({asset.get('stiker_ukuran', '')})" if asset.get('stiker_ukuran') else ""), cell_small),
            Paragraph(f"Rp {_safe_price_float(asset.get('purchase_price')):,.0f}", cell_style),
        ])
    
    col_widths = [22*mm, 26*mm, 42*mm, 25*mm, 30*mm, 30*mm, 18*mm, 16*mm, 22*mm, 28*mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header - professional dark blue
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        # Body
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        # Borders - lighter, cleaner
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#1e40af')),
        # Alternating rows - subtle
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    
    elements.append(table)
    
    # Footer note
    elements.append(Spacer(1, 12))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#94a3b8'), alignment=1)
    elements.append(Paragraph(f"Dokumen ini digenerate otomatis oleh Sistem Inventaris Aset | Total {total} aset", footer_style))
    
    # Dokumen kecil mendapat footer "Halaman N dari M" via overlay di bawah;
    # menulis nomor halaman ganda di titik yang sama membuat teks bertumpuk.
    if total <= 500:
        doc.build(elements)
    else:
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

    # Add total pages to each page (skip for large docs to save memory/time)
    buffer.seek(0)
    
    if total <= 500:
        from reportlab.pdfgen import canvas as pdf_canvas
        from PyPDF2 import PdfReader, PdfWriter
        try:
            reader = PdfReader(buffer)
            total_pages = len(reader.pages)
            writer = PdfWriter()
            
            for page_idx, page in enumerate(reader.pages):
                overlay_buf = io.BytesIO()
                overlay_canvas = pdf_canvas.Canvas(overlay_buf, pagesize=landscape(A4))
                overlay_canvas.setFont('Helvetica', 7)
                overlay_canvas.setFillColor(colors.HexColor('#94a3b8'))
                text = f"Halaman {page_idx + 1} dari {total_pages}"
                overlay_canvas.drawRightString(landscape(A4)[0] - 15*mm, 10*mm, text)
                overlay_canvas.save()
                overlay_buf.seek(0)
                
                overlay_reader = PdfReader(overlay_buf)
                page.merge_page(overlay_reader.pages[0])
                writer.add_page(page)
            
            final_buffer = io.BytesIO()
            writer.write(final_buffer)
            final_buffer.seek(0)
        except Exception:
            buffer.seek(0)
            final_buffer = buffer
    else:
        final_buffer = buffer
    
    logger.info(f"Exported {total} assets to PDF")
    
    return StreamingResponse(
        final_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=laporan_inventaris.pdf"}
    )

@exports_router.get("/export/xlsx")
@limiter.limit("3/minute")
async def export_xlsx(request: Request, activity_id: Optional[str] = None, base_url: str = "",
                      _user: dict = Depends(require_user)):
    """Export assets to Excel format with thumbnails and document checklist - optimized for large datasets"""
    query = {"activity_id": activity_id} if activity_id else {}
    total = await db.assets.count_documents(query)
    if total == 0:
        raise HTTPException(status_code=404, detail="Tidak ada data untuk diexport")
    
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {'in_memory': True, 'constant_memory': False})
    
    # === SHEET 1: Data Aset ===
    worksheet = workbook.add_worksheet('Data Aset')
    
    header_format = workbook.add_format({
        'bold': True, 'bg_color': '#3b82f6', 'font_color': 'white',
        'align': 'center', 'valign': 'vcenter', 'border': 1
    })
    cell_format = workbook.add_format({
        'align': 'left', 'valign': 'vcenter', 'border': 1, 'text_wrap': True
    })
    link_format = workbook.add_format({
        'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_color': 'blue', 'underline': 1
    })
    
    headers = ASSET_SHEET_HEADERS

    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    worksheet.set_column(0, 0, 20)  # Foto
    worksheet.set_column(1, 1, 20)  # Foto Stiker
    worksheet.set_column(2, 2, 15)  # Kode Aset
    worksheet.set_column(3, 3, 8)   # NUP
    worksheet.set_column(4, 4, 25)  # Nama Aset
    worksheet.set_column(5, 43, 14)
    worksheet.set_column(44, 44, 12) # Jumlah Foto
    worksheet.set_column(45, 45, 18) # Tanggal Input
    
    # === SHEET 2: Kelengkapan Dokumen ===
    doc_sheet = workbook.add_worksheet('Kelengkapan Dokumen')
    # Headers with separate columns for each photo link (max 3) and 1 PDF
    doc_headers = ['Kode Aset', 'NUP', 'Nama Aset', 'Item Kelengkapan', 'Catatan', 
                   'Foto 1', 'Foto 2', 'Foto 3', 'PDF']
    
    for col, header in enumerate(doc_headers):
        doc_sheet.write(0, col, header, header_format)
    
    doc_sheet.set_column(0, 0, 15)
    doc_sheet.set_column(1, 1, 8)
    doc_sheet.set_column(2, 2, 25)
    doc_sheet.set_column(3, 3, 30)
    doc_sheet.set_column(4, 4, 25)
    doc_sheet.set_column(5, 7, 15)  # Foto 1-3 columns - thumbnail + link
    doc_sheet.set_column(8, 8, 25)  # PDF column
    
    doc_thumbnail_format = workbook.add_format({
        'align': 'center', 'valign': 'vcenter', 'border': 1
    })
    
    # Stream data
    projection = {"_id": 0}
    cursor = db.assets.find(query, projection).batch_size(200)
    row = 1
    doc_row = 1
    
    async for asset in cursor:
        worksheet.set_row(row, 120)
        asset_code = asset.get('asset_code', '')
        asset_nup = asset.get('NUP', '')
        asset_name = asset.get('asset_name', '')
        asset_id = asset.get('id', '')
        
        # HD Photo - use selected cover photo at higher resolution.
        # URUTAN: inline full-res → GridFS full-res → cover 'photo' →
        # thumbnail 100px paling akhir. Dokumen ter-migrasi selalu punya
        # thumbnail, jadi bila thumbnail dicoba lebih dulu, fallback GridFS
        # tak pernah jalan dan kolom "HD Photo" berisi gambar 100px buram.
        photos_list = asset.get('photos', [])
        tidx = asset.get('thumbnail_index', 0) or 0
        img_data = None
        if photos_list and tidx < len(photos_list) and photos_list[tidx]:
            img_data = photos_list[tidx]
        gids = [g for g in (asset.get('photo_gridfs_ids') or []) if g]
        if not img_data and gids:
            # Blob sampul GridFS (indeks di-clamp) → data-URI agar jalur embed
            # inline di bawah tetap bekerja tanpa perubahan.
            try:
                gidx = max(0, min(int(tidx), len(gids) - 1))
                raw = await get_photo_from_gridfs(gids[gidx])
                if raw:
                    img_data = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
            except Exception as e:
                logger.error(f"GridFS cover fetch failed for {asset_id}: {e}")
        if not img_data:
            img_data = asset.get('photo') or asset.get('thumbnail')
        if img_data:
            try:
                thumb_buffer = _xlsx_image_buffer(img_data, 640, quality=70)
                worksheet.insert_image(row, 0, 'image.jpg', {
                    'image_data': thumb_buffer, 'x_scale': 0.22, 'y_scale': 0.22,
                    'x_offset': 4, 'y_offset': 4
                })
            except Exception as e:
                logger.error(f"Error adding image: {e}")
                worksheet.write(row, 0, '', cell_format)
        else:
            worksheet.write(row, 0, '', cell_format)

        # Stiker Photo - use selected stiker photo at best quality
        stiker_idx = asset.get('stiker_photo_index')
        stiker_data = None
        if stiker_idx is not None and photos_list and stiker_idx < len(photos_list):
            stiker_data = photos_list[stiker_idx]
        elif stiker_idx is not None and not photos_list and gids:
            # Fallback GridFS: foto stiker pada indeks yang sama (di-clamp);
            # dilewati bila stiker_photo_index tidak diset (None).
            try:
                sidx = max(0, min(int(stiker_idx), len(gids) - 1))
                raw = await get_photo_from_gridfs(gids[sidx])
                if raw:
                    stiker_data = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
            except Exception as e:
                logger.error(f"GridFS stiker fetch failed for {asset_id}: {e}")
        if stiker_data:
            try:
                stiker_buffer = _xlsx_image_buffer(stiker_data, 900, quality=75)
                worksheet.insert_image(row, 1, 'stiker.jpg', {
                    'image_data': stiker_buffer, 'x_scale': 0.24, 'y_scale': 0.24,
                    'x_offset': 4, 'y_offset': 4
                })
            except Exception as e:
                logger.error(f"Error adding stiker image: {e}")
                worksheet.write(row, 1, '', cell_format)
        else:
            worksheet.write(row, 1, '', cell_format)
        
        worksheet.write(row, 2, asset_code, cell_format)
        worksheet.write(row, 3, asset_nup, cell_format)
        worksheet.write(row, 4, asset_name, cell_format)
        worksheet.write(row, 5, asset.get('category', ''), cell_format)
        worksheet.write(row, 6, asset.get('brand', ''), cell_format)
        worksheet.write(row, 7, asset.get('model', ''), cell_format)
        worksheet.write(row, 8, asset.get('kode_register', ''), cell_format)
        worksheet.write(row, 9, asset.get('serial_number', ''), cell_format)
        worksheet.write(row, 10, asset.get('purchase_date', ''), cell_format)
        worksheet.write(row, 11, str(asset.get('purchase_price', '')), cell_format)
        worksheet.write(row, 12, asset.get('location', ''), cell_format)
        worksheet.write(row, 13, asset.get('eselon1', ''), cell_format)
        worksheet.write(row, 14, asset.get('eselon2', ''), cell_format)
        worksheet.write(row, 15, asset.get('user', ''), cell_format)
        worksheet.write(row, 16, asset.get('pengguna_melekat_ke', ''), cell_format)
        worksheet.write(row, 17, asset.get('pengguna_jabatan', ''), cell_format)
        worksheet.write(row, 18, asset.get('pengguna_nip', ''), cell_format)
        worksheet.write(row, 19, asset.get('operasional_jenis', ''), cell_format)
        worksheet.write(row, 20, asset.get('nomor_bast', ''), cell_format)
        worksheet.write(row, 21, asset.get('condition', ''), cell_format)
        worksheet.write(row, 22, asset.get('status', ''), cell_format)
        worksheet.write(row, 23, asset.get('stiker_status', 'Belum Terpasang'), cell_format)
        worksheet.write(row, 24, asset.get('stiker_ukuran', ''), cell_format)
        worksheet.write(row, 25, asset.get('nomor_spm', ''), cell_format)
        worksheet.write(row, 26, asset.get('perolehan_dari_nama', ''), cell_format)
        worksheet.write(row, 27, asset.get('nomor_kontrak', ''), cell_format)
        worksheet.write(row, 28, asset.get('nomor_bukti_perolehan', ''), cell_format)
        worksheet.write(row, 29, asset.get('supplier', ''), cell_format)
        worksheet.write(row, 30, asset.get('notes', ''), cell_format)
        worksheet.write(row, 31, asset.get('inventory_status', 'Belum Diinventarisasi'), cell_format)
        worksheet.write(row, 32, asset.get('klasifikasi_tidak_ditemukan', ''), cell_format)
        worksheet.write(row, 33, asset.get('sub_klasifikasi', ''), cell_format)
        worksheet.write(row, 34, asset.get('uraian_tidak_ditemukan', ''), cell_format)
        worksheet.write(row, 35, asset.get('tindak_lanjut', ''), cell_format)
        worksheet.write(row, 36, asset.get('koordinat_latitude', ''), cell_format)
        worksheet.write(row, 37, asset.get('koordinat_longitude', ''), cell_format)
        worksheet.write(row, 38, asset.get('kronologis', ''), cell_format)
        worksheet.write(row, 39, asset.get('keterangan_berlebih', ''), cell_format)
        worksheet.write(row, 40, asset.get('asal_usul_berlebih', ''), cell_format)
        worksheet.write(row, 41, asset.get('nomor_perkara', ''), cell_format)
        worksheet.write(row, 42, asset.get('pihak_bersengketa', ''), cell_format)
        worksheet.write(row, 43, asset.get('keterangan_sengketa', ''), cell_format)

        # Jumlah Foto
        photo_count = len(asset.get('photo_gridfs_ids', []) or asset.get('photos', []))
        worksheet.write(row, 44, photo_count, cell_format)
        # Tanggal Input
        worksheet.write(row, 45, asset.get('created_at', ''), cell_format)
        
        # Write document checklist to separate sheet - ONLY items with checked=True (✓ Ada)
        checklist = asset.get('document_checklist', [])
        for idx, item in enumerate(checklist):
            checked = item.get('checked', False)
            
            # Skip items that are NOT available (✗ Tidak Ada)
            if not checked:
                continue
            
            item_name = item.get('name', '')
            notes = item.get('notes', '')
            photos = item.get('photos', [])
            documents = item.get('documents', [])
            
            # Set row height for thumbnails if there are photos
            if photos:
                doc_sheet.set_row(doc_row, 80)  # Height for thumbnail
            
            doc_sheet.write(doc_row, 0, asset_code, cell_format)
            doc_sheet.write(doc_row, 1, asset_nup, cell_format)
            doc_sheet.write(doc_row, 2, asset_name, cell_format)
            doc_sheet.write(doc_row, 3, item_name, cell_format)
            doc_sheet.write(doc_row, 4, notes, cell_format)
            
            # Photo columns (Foto 1, Foto 2, Foto 3) - with thumbnails and clickable links
            for pi in range(3):  # Max 3 photos
                col_idx = 5 + pi  # Columns 5, 6, 7
                if pi < len(photos) and photos[pi] and base_url:
                    photo_url = f"{base_url}/api/assets/{asset_id}/doc-file/{idx}/photo/{pi}"
                    
                    # Try to embed thumbnail image
                    try:
                        thumb_buf = _xlsx_image_buffer(photos[pi], 110, quality=60)
                        
                        # Insert thumbnail image with hyperlink
                        doc_sheet.insert_image(doc_row, col_idx, 'thumb.jpg', {
                            'image_data': thumb_buf, 
                            'x_scale': 0.7, 
                            'y_scale': 0.7,
                            'x_offset': 2, 
                            'y_offset': 2,
                            'url': photo_url  # Clickable link on the image
                        })
                    except Exception as e:
                        # Fallback: just write clickable link text
                        logger.warning(f"Could not embed photo thumbnail: {e}")
                        doc_sheet.write_url(doc_row, col_idx, photo_url, link_format, f"Foto {pi+1}")
                else:
                    doc_sheet.write(doc_row, col_idx, "", doc_thumbnail_format)
            
            # PDF column (only 1 PDF max)
            if documents and len(documents) > 0 and documents[0] and base_url:
                doc_obj = documents[0]
                doc_name = doc_obj.get('name', 'PDF') if isinstance(doc_obj, dict) else 'PDF'
                pdf_url = f"{base_url}/api/assets/{asset_id}/doc-file/{idx}/document/0"
                doc_sheet.write_url(doc_row, 8, pdf_url, link_format, doc_name)
            else:
                doc_sheet.write(doc_row, 8, "", cell_format)
            
            doc_row += 1
        
        row += 1
        # Yield to the event loop periodically so large exports don't
        # starve other tasks (WS heartbeats, etc.).
        if row % 50 == 0:
            await asyncio.sleep(0)
    
    # === SHEET 3: Data Kegiatan ===
    if activity_id:
        act_data = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
        if act_data:
            act_sheet = workbook.add_worksheet('Data Kegiatan')
            label_fmt = workbook.add_format({'bold': True, 'bg_color': '#10b981', 'font_color': 'white', 'border': 1, 'align': 'left', 'valign': 'vcenter'})
            val_fmt = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
            section_fmt = workbook.add_format({'bold': True, 'bg_color': '#059669', 'font_color': 'white', 'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 11})
            act_sheet.set_column(0, 0, 28)
            act_sheet.set_column(1, 1, 55)
            
            ar = 0
            # Section: Informasi Kegiatan
            act_sheet.merge_range(ar, 0, ar, 1, 'INFORMASI KEGIATAN', section_fmt)
            ar += 1
            info_rows = [
                ("Nama Kegiatan", act_data.get('nama_kegiatan', '')),
                ("Nomor Surat", act_data.get('nomor_surat', '')),
                ("Deskripsi", act_data.get('deskripsi', '')),
                ("Tanggal Mulai", act_data.get('tanggal_mulai', '')),
                ("Tanggal Selesai", act_data.get('tanggal_selesai', '')),
            ]
            for lbl, val in info_rows:
                act_sheet.write(ar, 0, lbl, label_fmt)
                act_sheet.write(ar, 1, val, val_fmt)
                ar += 1
            
            # Section: Satuan Kerja
            ar += 1
            act_sheet.merge_range(ar, 0, ar, 1, 'SATUAN KERJA', section_fmt)
            ar += 1
            satker_rows = [
                ("Kode Satker", act_data.get('kode_satker', '')),
                ("Nama Satker", act_data.get('nama_satker', '')),
                ("Alamat Satker", act_data.get('alamat_satker', '')),
                ("Nama Kasatker", act_data.get('kasatker_nama', '')),
                ("NIP Kasatker", act_data.get('kasatker_nip', '')),
                ("Jabatan Kasatker", act_data.get('kasatker_jabatan', '')),
            ]
            for lbl, val in satker_rows:
                act_sheet.write(ar, 0, lbl, label_fmt)
                act_sheet.write(ar, 1, val, val_fmt)
                ar += 1
            
            # Eselon data
            eselon_list = act_data.get('eselon1', [])
            for es in eselon_list:
                nama_es1 = es.get('nama', '') if isinstance(es, dict) else str(es)
                eselon2_items = es.get('eselon2', []) if isinstance(es, dict) else []
                act_sheet.write(ar, 0, "Eselon I", label_fmt)
                act_sheet.write(ar, 1, nama_es1, val_fmt)
                ar += 1
                for e2 in eselon2_items:
                    act_sheet.write(ar, 0, "  - Eselon II", label_fmt)
                    act_sheet.write(ar, 1, e2, val_fmt)
                    ar += 1
            
            # Section: Penanggung Jawab
            ar += 1
            act_sheet.merge_range(ar, 0, ar, 1, 'PENANGGUNG JAWAB', section_fmt)
            ar += 1
            pj_rows = [
                ("Nama", act_data.get('penanggung_jawab', '')),
                ("Jabatan", act_data.get('penanggung_jawab_jabatan', '')),
                ("NIP", act_data.get('penanggung_jawab_nip', '')),
            ]
            for lbl, val in pj_rows:
                act_sheet.write(ar, 0, lbl, label_fmt)
                act_sheet.write(ar, 1, val, val_fmt)
                ar += 1
            
            # Section: Berita Acara
            ar += 1
            act_sheet.merge_range(ar, 0, ar, 1, 'BERITA ACARA', section_fmt)
            ar += 1
            ba_rows = [
                ("Nomor Berita Acara", act_data.get('nomor_berita_acara', '')),
                ("Tanggal Berita Acara", act_data.get('tanggal_berita_acara', '')),
                ("Kesimpulan", act_data.get('kesimpulan', '')),
            ]
            for lbl, val in ba_rows:
                act_sheet.write(ar, 0, lbl, label_fmt)
                act_sheet.write(ar, 1, val, val_fmt)
                ar += 1
            
            # === SHEET 4: Tim Inventarisasi (detailed) ===
            tim_sheet = workbook.add_worksheet('Tim Inventarisasi')
            tim_header_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#7c3aed', 'font_color': 'white',
                'align': 'center', 'valign': 'vcenter', 'border': 1
            })
            tim_section_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#6d28d9', 'font_color': 'white',
                'border': 1, 'align': 'left', 'font_size': 11
            })
            tim_cell_fmt = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
            tim_ketua_fmt = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter', 'bold': True, 'bg_color': '#fef3c7'})
            
            tim_sheet.set_column(0, 0, 5)   # No
            tim_sheet.set_column(1, 1, 30)  # Nama
            tim_sheet.set_column(2, 2, 25)  # Jabatan
            tim_sheet.set_column(3, 3, 22)  # NIP
            tim_sheet.set_column(4, 4, 20)  # Unit/Asal
            tim_sheet.set_column(5, 5, 14)  # Peran
            
            tr = 0
            
            def write_tim_section(sheet, start_row, title, members, fields, has_ketua=False, has_dari_pihak=False, has_dari_satker=False):
                """Write a team section with header + members"""
                r = start_row
                sheet.merge_range(r, 0, r, 5, title, tim_section_fmt)
                r += 1

                # Column headers — kolom ke-5 menyesuaikan jenis tim
                col5 = 'Unit'
                if has_dari_pihak:
                    col5 = 'Dari Pihak'
                elif has_dari_satker:
                    col5 = 'Dari Satker'
                headers_tim = ['No', 'Nama', 'Jabatan', 'NIP/NIK', col5, 'Peran']
                for c, h in enumerate(headers_tim):
                    sheet.write(r, c, h, tim_header_fmt)
                r += 1

                if not members:
                    sheet.merge_range(r, 0, r, 5, '(tidak ada data)', tim_cell_fmt)
                    return r + 1

                for idx, m in enumerate(members):
                    if not isinstance(m, dict):
                        continue
                    is_ketua = m.get('is_ketua', False)
                    fmt = tim_ketua_fmt if is_ketua else tim_cell_fmt
                    sheet.write(r, 0, idx + 1, fmt)
                    sheet.write(r, 1, m.get('nama', ''), fmt)
                    sheet.write(r, 2, m.get('jabatan', ''), fmt)
                    sheet.write(r, 3, m.get('nip', ''), fmt)
                    if has_dari_pihak:
                        sheet.write(r, 4, m.get('dari_pihak', ''), fmt)
                    elif has_dari_satker:
                        sheet.write(r, 4, m.get('dari_satker', ''), fmt)
                    else:
                        sheet.write(r, 4, m.get('unit', ''), fmt)
                    peran = 'Ketua' if is_ketua else 'Anggota'
                    sheet.write(r, 5, peran, fmt)
                    r += 1
                return r + 1  # extra spacing
            
            # Tim Inti (Internal)
            tr = write_tim_section(tim_sheet, tr, 'TIM INTI (INTERNAL)', act_data.get('tim_inti', []), 
                                   ['nama', 'jabatan', 'nip', 'unit'], has_ketua=True)
            # Tim Pembantu (Internal)
            tr = write_tim_section(tim_sheet, tr, 'TIM PEMBANTU (INTERNAL)', act_data.get('tim_pembantu', []),
                                   ['nama', 'jabatan', 'nip', 'unit'], has_ketua=True)
            # Tim Peneliti (External)
            tr = write_tim_section(tim_sheet, tr, 'TIM PENELITI (EKSTERNAL)', act_data.get('tim_peneliti', []),
                                   ['nama', 'jabatan', 'nip', 'dari_satker'], has_dari_satker=True)
            # Tim Pendukung (External)
            tr = write_tim_section(tim_sheet, tr, 'TIM PENDUKUNG (EKSTERNAL)', act_data.get('tim_pendukung', []),
                                   ['nama', 'jabatan', 'nip', 'dari_pihak'], has_dari_pihak=True)
    
    workbook.close()
    buffer.seek(0)
    
    logger.info(f"📤 Exported {total} assets to Excel (activity_id={activity_id})")
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=inventory.xlsx"}
    )

