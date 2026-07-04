"""KTP-style asset card PDF generation routes."""
import io
import base64
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    Table,
    TableStyle,
    Frame,
    Image as RLImage,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from PIL import Image as PILImage
from PyPDF2 import PdfMerger

from db import db

logger = logging.getLogger(__name__)
cards_router = APIRouter()

# ============================================================================
# ASSET CARD ENDPOINT (for printing inventory card - KTP SIZE)
# ============================================================================

# KTP size: 85.6mm x 54mm (ID-1 format per ISO/IEC 7810)
KTP_WIDTH = 85.6 * mm
KTP_HEIGHT = 54 * mm


def build_qr_flowable(payload: str, size: float):
    """QR asli (bukan placeholder) memakai barcode bawaan reportlab.

    Payload format "#<kode register>" — QrScanButton di frontend mengenali
    prefix '#' dan memakai sisanya verbatim sebagai kode_register.
    Returns None bila pembuatan QR gagal (caller pakai fallback placeholder).
    """
    try:
        widget = qr.QrCodeWidget(payload, barLevel="M", barBorder=1)
        x0, y0, x1, y1 = widget.getBounds()
        w, h = (x1 - x0) or 1, (y1 - y0) or 1
        drawing = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        drawing.add(widget)
        return drawing
    except Exception as e:
        logger.warning(f"[cards] QR generation failed for payload '{payload}': {e}")
        return None

def create_ktp_card_elements(asset):
    """Create front and back card for KTP size (85.6mm x 54mm) - compact informative design"""
    
    elements = {'front': [], 'back': []}
    
    # Colors
    navy = colors.HexColor('#0f172a')
    blue = colors.HexColor('#2563eb')
    gray = colors.HexColor('#64748b')
    lightgray = colors.HexColor('#94a3b8')
    border = colors.HexColor('#e2e8f0')
    stripebg = colors.HexColor('#f8fafc')
    green = colors.HexColor('#16a34a')
    greenbg = colors.HexColor('#dcfce7')
    bluebg = colors.HexColor('#dbeafe')
    
    # Safe string helper
    def s(val, maxlen=50):
        if val is None or str(val).strip() in ('', 'None'):
            return '-'
        txt = str(val).strip()
        return txt[:maxlen-2] + '..' if len(txt) > maxlen else txt
    
    # Extract data
    code = s(asset.get('asset_code'), 15)
    nup = s(asset.get('NUP'), 5)
    name = s(asset.get('asset_name'), 45)
    cat = s(asset.get('category'), 15)
    sn = s(asset.get('serial_number'), 18)
    brand = s(asset.get('brand'), 12)
    mdl = s(asset.get('model'), 12)
    cond = s(asset.get('condition'), 8)
    stat = s(asset.get('status'), 8)
    eselon1 = s(asset.get('eselon1'), 20)
    eselon2 = s(asset.get('eselon2'), 20)
    loc = s(asset.get('location'), 20)
    usr = s(asset.get('user'), 35)
    pdate = s(asset.get('purchase_date'), 12)
    spm = s(asset.get('nomor_spm'), 20)
    kontrak = s(asset.get('nomor_kontrak'), 40)
    bukti = s(asset.get('nomor_bukti_perolehan'), 40)
    supplier = s(asset.get('supplier'), 25)
    kreg = s(asset.get('kode_register'), 32)
    
    price = asset.get('purchase_price', 0)
    try:
        price_str = f"Rp {float(price or 0):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        price_str = "-"
    
    ls = ParagraphStyle
    W = KTP_WIDTH - 2*mm  # Max usable width
    
    # ==================== FRONT CARD ====================
    # Layout: Header 5mm | Body 39mm | Footer 10mm = 54mm
    
    # --- HEADER (5mm) - Navy bar with title and NUP ---
    hdr = Table([[
        Paragraph("KARTU INVENTARIS", ls('_hdr', fontSize=7, textColor=colors.white, fontName='Helvetica-Bold')),
        Paragraph(f"NUP {nup}", ls('_nup', fontSize=6, textColor=colors.white, fontName='Courier-Bold', alignment=2))
    ]], colWidths=[W*0.7, W*0.3], rowHeights=[5*mm])
    hdr.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), navy),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (0,0), 2*mm),
        ('RIGHTPADDING', (1,0), (1,0), 2*mm),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements['front'].append(hdr)
    
    # --- BODY (39mm) - Photo left (17mm), Info right ---
    photo_w = 17*mm
    info_w = W - photo_w - 1*mm
    
    # Photo
    photo_el = Table([['FOTO']], colWidths=[15*mm], rowHeights=[20*mm])
    photo_el.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), stripebg),
        ('BOX', (0,0), (-1,-1), 0.3, border),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 5),
        ('TEXTCOLOR', (0,0), (-1,-1), lightgray),
    ]))
    
    photos_list = asset.get('photos', []) or []
    tidx = asset.get('thumbnail_index', 0) or 0
    img_src = photos_list[tidx] if photos_list and tidx < len(photos_list) else asset.get('photo')
    if img_src:
        try:
            enc = img_src.split("base64,", 1)[1] if "base64," in img_src else img_src
            ib = base64.b64decode(enc)
            im = PILImage.open(io.BytesIO(ib))
            if im.mode in ('RGBA', 'P'):
                bg_img = PILImage.new('RGB', im.size, (255, 255, 255))
                if im.mode == 'P':
                    im = im.convert('RGBA')
                bg_img.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
                im = bg_img
            im.thumbnail((150, 150), PILImage.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            photo_el = RLImage(buf, width=15*mm, height=20*mm)
        except Exception as e:
            logger.debug(f"[cards] Photo processing skipped for asset: {e}")
    
    # Info styles - compact
    code_style = ls('_code', fontSize=10, textColor=navy, fontName='Courier-Bold', leading=11)
    name_style = ls('_name', fontSize=5.5, textColor=navy, fontName='Helvetica-Bold', leading=6.5)
    lbl_style = ls('_lbl', fontSize=3.5, textColor=gray, fontName='Helvetica', leading=4)
    val_style = ls('_val', fontSize=4.5, textColor=navy, fontName='Helvetica-Bold', leading=5)
    
    # Specs grid - 2 columns, compact
    half_w = (info_w - 2*mm) / 2
    specs = Table([
        [Paragraph("KATEGORI", lbl_style), Paragraph("S/N", lbl_style)],
        [Paragraph(cat, val_style), Paragraph(sn, val_style)],
        [Paragraph("MEREK/MODEL", lbl_style), Paragraph("LOKASI", lbl_style)],
        [Paragraph(f"{brand}/{mdl}", val_style), Paragraph(loc, val_style)],
    ], colWidths=[half_w, half_w], rowHeights=[2.5*mm, 4*mm, 2.5*mm, 4*mm])
    specs.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    # Status badges - inline
    cond_color = green if cond.lower() == 'baik' else colors.HexColor('#ea580c')
    stat_color = blue if stat.lower() == 'aktif' else gray
    
    badges = Table([[
        Paragraph(cond.upper(), ls('_bc', fontSize=4, textColor=cond_color, fontName='Helvetica-Bold')),
        Paragraph(stat.upper(), ls('_bs', fontSize=4, textColor=stat_color, fontName='Helvetica-Bold')),
        Paragraph(price_str, ls('_pr', fontSize=4, textColor=gray, fontName='Helvetica-Bold', alignment=2))
    ]], colWidths=[12*mm, 12*mm, info_w - 26*mm], rowHeights=[4*mm])
    badges.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (0,0), greenbg if cond.lower() == 'baik' else colors.HexColor('#ffedd5')),
        ('BACKGROUND', (1,0), (1,0), bluebg if stat.lower() == 'aktif' else stripebg),
    ]))
    
    # Info column
    info = Table([
        [Paragraph(code, code_style)],
        [Paragraph(name, name_style)],
        [specs],
        [badges],
    ], colWidths=[info_w - 1*mm], rowHeights=[7*mm, 7*mm, 13*mm, 5*mm])
    info.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 0.5*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 1*mm),
    ]))
    
    # Combine photo + info
    body = Table([[photo_el, info]], colWidths=[photo_w, info_w], rowHeights=[34*mm])
    body.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 1*mm),
        ('LEFTPADDING', (0,0), (0,0), 1*mm),
    ]))
    elements['front'].append(body)
    
    # --- FOOTER (10mm) - QR + ID info ---
    ft_style = ls('_ft', fontSize=3.5, textColor=gray, fontName='Helvetica', leading=4)
    ft_code = ls('_ftc', fontSize=5, textColor=navy, fontName='Courier-Bold', leading=5.5)
    
    # QR asli berisi "#<kode register>" (fallback "#<kode>-<NUP>") — dipindai
    # QrScanButton untuk mencari aset via kode_register verbatim.
    raw_kreg = str(asset.get('kode_register') or '').strip()
    raw_code = str(asset.get('asset_code') or '').strip()
    raw_nup = str(asset.get('NUP') or '').strip()
    qr_payload = f"#{raw_kreg}" if raw_kreg else f"#{raw_code}-{raw_nup}"
    qr_el = build_qr_flowable(qr_payload, 8*mm) or Table([['QR']], colWidths=[8*mm], rowHeights=[8*mm])

    footer = Table([[
        qr_el,
        Table([
            [Paragraph(f"ID: {kreg if kreg != '-' else code}", ft_style)],
            [Paragraph(f"KODE: {code} | NUP: {nup}", ft_code)],
        ], colWidths=[W - 12*mm], rowHeights=[4*mm, 4.5*mm])
    ]], colWidths=[10*mm, W - 10*mm], rowHeights=[10*mm])
    footer.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), stripebg),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (0,0), 1*mm),
        ('BOX', (0,0), (0,0), 0.3, border),
        ('BACKGROUND', (0,0), (0,0), colors.white),
        ('LINEABOVE', (0,0), (-1,0), 0.3, border),
    ]))
    elements['front'].append(footer)
    
    # ==================== BACK CARD ====================
    # Layout: Header 4mm | Data 41mm | Footer 9mm = 54mm
    
    # --- HEADER (4mm) ---
    bhdr = Table([[
        Paragraph("DETAIL ADMINISTRATIF", ls('_bh', fontSize=5, textColor=colors.white, fontName='Helvetica-Bold'))
    ]], colWidths=[W], rowHeights=[4*mm])
    bhdr.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), navy),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 2*mm),
    ]))
    elements['back'].append(bhdr)
    
    # --- DATA ROWS (41mm) - 6 rows ---
    row_lbl = ls('_rl', fontSize=3, textColor=gray, fontName='Helvetica', leading=3.5)
    row_val = ls('_rv', fontSize=4.5, textColor=navy, fontName='Helvetica-Bold', leading=5)
    hw = W / 2 - 1*mm
    
    def row_cell(label, value, width=hw):
        return Table([
            [Paragraph(label, row_lbl)],
            [Paragraph(value, row_val)]
        ], colWidths=[width], rowHeights=[2.5*mm, 4*mm])
    
    def make_row(cells, bg_color, height=6.5*mm):
        t = Table([cells], colWidths=[hw + 1*mm] * len(cells) if len(cells) > 1 else [W], rowHeights=[height])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 1.5*mm),
            ('TOPPADDING', (0,0), (-1,-1), 0.5*mm),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0.5*mm),
            ('LINEBELOW', (0,0), (-1,-1), 0.2, border),
        ]))
        return t
    
    # Row 1: Eselon | Lokasi
    elements['back'].append(make_row([row_cell("ESELON I", eselon1), row_cell("LOKASI", loc)], colors.white))
    # Row 1.5: Eselon II
    elements['back'].append(make_row([row_cell("ESELON II", eselon2, W - 2*mm)], stripebg))
    # Row 2: User
    elements['back'].append(make_row([row_cell("PENANGGUNG JAWAB", usr, W - 2*mm)], stripebg))
    # Row 3: Tgl | SPM
    elements['back'].append(make_row([row_cell("TGL PEROLEHAN", pdate), row_cell("NO. SPM", spm)], colors.white))
    # Row 4: Kontrak
    elements['back'].append(make_row([row_cell("NO. KONTRAK", kontrak, W - 2*mm)], stripebg))
    # Row 5: BAST
    elements['back'].append(make_row([row_cell("BUKTI PEROLEHAN", bukti, W - 2*mm)], colors.white))
    # Row 6: Supplier | Catatan
    elements['back'].append(make_row([row_cell("SUPPLIER", supplier), row_cell("KATEGORI", cat)], stripebg))
    
    # --- FOOTER (9mm) - Price ---
    bft = Table([[
        Paragraph(f"ID: {kreg if kreg != '-' else code}", ls('_bfi', fontSize=3, textColor=lightgray, fontName='Courier')),
        Paragraph(price_str, ls('_bfp', fontSize=8, textColor=colors.HexColor('#22d3ee'), fontName='Courier-Bold', alignment=2))
    ]], colWidths=[W*0.5, W*0.5], rowHeights=[9*mm])
    bft.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), navy),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (0,0), 2*mm),
        ('RIGHTPADDING', (1,0), (1,0), 2*mm),
    ]))
    elements['back'].append(bft)
    
    return elements

@cards_router.get("/assets/{asset_id}/card")
async def get_asset_card_pdf(asset_id: str):
    """Generate a printable KTP-sized inventory card PDF for a single asset (front + back)"""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    buffer = io.BytesIO()

    # Create PDF with A4 page containing the KTP card
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    
    # Center the card on page
    x_offset = (page_w - KTP_WIDTH) / 2
    y_offset_front = page_h - 50*mm - KTP_HEIGHT
    y_offset_back = y_offset_front - KTP_HEIGHT - 10*mm
    
    # Draw card borders
    c.setStrokeColor(colors.HexColor('#e2e8f0'))
    c.setLineWidth(0.5)
    
    # Front card border
    c.roundRect(x_offset - 2*mm, y_offset_front - 2*mm, KTP_WIDTH + 4*mm, KTP_HEIGHT + 4*mm, 2*mm)
    
    # Back card border
    c.roundRect(x_offset - 2*mm, y_offset_back - 2*mm, KTP_WIDTH + 4*mm, KTP_HEIGHT + 4*mm, 2*mm)
    
    # Labels
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.HexColor('#64748b'))
    c.drawString(x_offset, y_offset_front + KTP_HEIGHT + 5*mm, "TAMPAK DEPAN")
    c.drawString(x_offset, y_offset_back + KTP_HEIGHT + 5*mm, "TAMPAK BELAKANG")
    
    # Generate card elements
    card_elements = create_ktp_card_elements(asset)
    
    # Build front card
    frame_front = Frame(x_offset, y_offset_front, KTP_WIDTH, KTP_HEIGHT, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_front.addFromList(card_elements['front'], c)
    
    # Build back card
    frame_back = Frame(x_offset, y_offset_back, KTP_WIDTH, KTP_HEIGHT, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_back.addFromList(card_elements['back'], c)
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kartu_inventaris_{asset_id}.pdf"}
    )

@cards_router.post("/assets/cards/bulk")
async def get_bulk_asset_cards(asset_ids: List[str]):
    """Generate KTP-sized inventory cards for multiple assets"""
    if not asset_ids:
        raise HTTPException(status_code=400, detail="Tidak ada aset yang dipilih")
    
    assets = await db.assets.find({"id": {"$in": asset_ids}}, {"_id": 0}).to_list(len(asset_ids))
    if not assets:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    
    from reportlab.lib.pagesizes import A4
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    
    # Layout: 2 columns x 2 rows of card pairs (front above back) per page
    # Each pair: front card + back card vertically stacked
    margin_x = 10*mm
    margin_y = 12*mm
    gap_x = 6*mm  # Horizontal gap between columns
    gap_y = 4*mm  # Vertical gap between card pairs
    gap_fb = 2*mm  # Gap between front and back
    
    # Calculate positions
    # col_width = (page_w - 2*margin_x - gap_x) / 2  # reserved for future layout tuning
    pair_height = KTP_HEIGHT * 2 + gap_fb
    
    cards_per_page = 4  # 2 columns x 2 rows
    total_cards = len(assets)
    
    for page_idx in range((total_cards + cards_per_page - 1) // cards_per_page):
        if page_idx > 0:
            c.showPage()
        
        # Page header
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(colors.HexColor('#1e40af'))
        c.drawString(margin_x, page_h - margin_y + 2*mm, f"KARTU INVENTARIS - Hal {page_idx + 1}")
        
        start_idx = page_idx * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        
        for local_idx, asset_idx in enumerate(range(start_idx, end_idx)):
            asset = assets[asset_idx]
            
            col = local_idx % 2
            row = local_idx // 2
            
            # Position calculations
            x = margin_x + col * (KTP_WIDTH + gap_x)
            y_top = page_h - margin_y - 8*mm - row * (pair_height + gap_y)
            y_front = y_top - KTP_HEIGHT
            y_back = y_front - gap_fb - KTP_HEIGHT
            
            # Draw cutting guides (dashed borders)
            c.setStrokeColor(colors.HexColor('#94a3b8'))
            c.setLineWidth(0.3)
            c.setDash([1.5, 1.5])
            c.rect(x, y_front, KTP_WIDTH, KTP_HEIGHT)
            c.rect(x, y_back, KTP_WIDTH, KTP_HEIGHT)
            c.setDash([])
            
            # Labels
            c.setFont('Helvetica', 5)
            c.setFillColor(colors.HexColor('#94a3b8'))
            c.drawString(x + 1*mm, y_front + KTP_HEIGHT + 1*mm, "DEPAN")
            c.drawString(x + 1*mm, y_back + KTP_HEIGHT + 1*mm, "BELAKANG")
            
            # Generate card elements
            card_elements = create_ktp_card_elements(asset)
            
            # Draw front card using Frame
            frame_front = Frame(x, y_front, KTP_WIDTH, KTP_HEIGHT, 
                               leftPadding=1*mm, rightPadding=1*mm, topPadding=0, bottomPadding=0)
            frame_front.addFromList(card_elements['front'].copy(), c)
            
            # Draw back card using Frame
            frame_back = Frame(x, y_back, KTP_WIDTH, KTP_HEIGHT,
                              leftPadding=1*mm, rightPadding=1*mm, topPadding=0, bottomPadding=0)
            frame_back.addFromList(card_elements['back'].copy(), c)
        
        # Page footer
        c.setFont('Helvetica', 6)
        c.setFillColor(colors.HexColor('#94a3b8'))
        c.drawString(margin_x, 6*mm, f"Total: {total_cards} kartu | Cetak: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} | Potong sesuai garis putus-putus")
    
    c.save()
    buffer.seek(0)
    
    logger.info(f"Generated bulk cards for {len(assets)} assets")
    
    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kartu_inventaris_massal_{len(assets)}.pdf"})
