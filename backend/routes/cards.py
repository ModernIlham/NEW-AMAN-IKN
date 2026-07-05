"""KTP-style asset card PDF generation routes.

Kartu Inventarisasi dicetak sebagai 4 panel (grid 2x2) pada satu halaman A4
landscape, dengan garis lipat (fold line) di tengah:

    [A: Tampak Depan Hal 1]  |  [B: Tampak Depan Hal 2]
    ------------- garis lipat (tampak depan & belakang) -------------
    [C: Tampak Belakang Hal 1]  |  [D: Tampak Belakang Hal 2]

Panel A: identitas aset + foto + QR.
Panel B: detail administratif (tile grid).
Panel C/D: riwayat inventarisasi (tabel 7 kolom, 3 baris per panel).
"""
import io
import base64
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from auth_utils import require_user

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    Table,
    TableStyle,
    Frame,
    Spacer,
    Image as RLImage,
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.barcode import qr
from PIL import Image as PILImage

from db import db

logger = logging.getLogger(__name__)
cards_router = APIRouter()

# ============================================================================
# ASSET CARD ENDPOINT (Kartu Inventarisasi — 4 panel fold layout, A4 landscape)
# ============================================================================

# --- Color palette (navy / blue / green, mirip mockup) ---
NAVY = colors.HexColor('#0f172a')
BLUE = colors.HexColor('#2563eb')
BLUEBG = colors.HexColor('#dbeafe')
GREEN = colors.HexColor('#16a34a')
GREENBG = colors.HexColor('#dcfce7')
ORANGE = colors.HexColor('#ea580c')
ORANGEBG = colors.HexColor('#ffedd5')
GRAY = colors.HexColor('#64748b')
LIGHTGRAY = colors.HexColor('#94a3b8')
BORDER = colors.HexColor('#e2e8f0')
STRIPEBG = colors.HexColor('#f8fafc')
NOTEBG = colors.HexColor('#eff6ff')
NOTEBORDER = colors.HexColor('#bfdbfe')
WHITE = colors.white

# --- Page / panel geometry (landscape A4, 2x2 grid with fold gaps) ---
PAGE_W, PAGE_H = landscape(A4)          # 297mm x 210mm
PANEL_MARGIN = 9 * mm                    # left/right outer margin
TOP_M = 7 * mm
BOT_M = 7 * mm
FOLD_GAP_X = 14 * mm                      # vertical fold gutter (between columns)
FOLD_GAP_Y = 12 * mm                      # horizontal fold gutter (between rows)
CAP_H = 4.5 * mm                          # caption strip above each panel row
PANEL_W = (PAGE_W - 2 * PANEL_MARGIN - FOLD_GAP_X) / 2
PANEL_H = (PAGE_H - TOP_M - BOT_M - 2 * CAP_H - FOLD_GAP_Y) / 2
FRAME_PAD = 2 * mm
UW = PANEL_W - 2 * FRAME_PAD              # usable content width inside a panel
UH = PANEL_H - 2 * FRAME_PAD              # usable content height inside a panel


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


def icon_box(fill, size=3 * mm, stroke=None):
    """Ikon sederhana: kotak kecil membulat berwarna (pengganti icon font)."""
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, rx=size * 0.28, ry=size * 0.28,
               fillColor=fill, strokeColor=stroke or fill, strokeWidth=0.4))
    return d


def _fmt_date(v):
    """tanggal_pengesahan bisa datetime atau ISO string → 'YYYY-MM-DD'."""
    if not v:
        return '-'
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d')
    sv = str(v).strip()
    return sv[:10] if len(sv) >= 10 else (sv or '-')


def _decode_photo_flowable(asset, width, height):
    """Kembalikan RLImage foto cover aset (bila ada) atau placeholder 'FOTO'."""
    placeholder = Table([['FOTO']], colWidths=[width], rowHeights=[height])
    placeholder.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), STRIPEBG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), LIGHTGRAY),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))

    photos_list = asset.get('photos', []) or []
    tidx = asset.get('thumbnail_index', 0) or 0
    img_src = photos_list[tidx] if photos_list and tidx < len(photos_list) else asset.get('photo')
    if not img_src:
        return placeholder
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
        im.thumbnail((400, 400), PILImage.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        return RLImage(buf, width=width, height=height)
    except Exception as e:
        logger.debug(f"[cards] Photo processing skipped for asset: {e}")
        return placeholder


def create_ktp_card_elements(asset, history=None):
    """Bangun 4 panel Kartu Inventarisasi.

    Returns dict {'A': [...], 'B': [...], 'C': [...], 'D': [...]} — tiap nilai
    adalah list flowable yang ditumpuk dalam Frame panel masing-masing.

    history: list record inventory_history (raw). Dipetakan jadi baris tabel
    riwayat. Panel C memakai 3 baris pertama, Panel D baris 4-6.
    """
    history = history or []

    # --- Safe string helper ---
    def s(val, maxlen=50):
        if val is None or str(val).strip() in ('', 'None'):
            return '-'
        txt = str(val).strip()
        return txt[:maxlen - 2] + '..' if len(txt) > maxlen else txt

    ls = ParagraphStyle

    # --- Extract data ---
    code = s(asset.get('asset_code'), 18)
    nup = s(asset.get('NUP'), 8)
    name = s(asset.get('asset_name'), 60)
    cat = s(asset.get('category'), 22)
    sn = s(asset.get('serial_number'), 22)
    brand = s(asset.get('brand'), 16)
    mdl = s(asset.get('model'), 16)
    cond = s(asset.get('condition'), 14)
    stat = s(asset.get('status'), 14)
    eselon1 = s(asset.get('eselon1'), 40)
    eselon2 = s(asset.get('eselon2'), 40)
    loc = s(asset.get('location'), 34)
    usr = s(asset.get('user'), 40)
    pdate = s(asset.get('purchase_date'), 20)
    spm = s(asset.get('nomor_spm'), 34)
    kontrak = s(asset.get('nomor_kontrak'), 40)
    bukti = s(asset.get('nomor_bukti_perolehan'), 40)
    supplier = s(asset.get('supplier'), 34)
    kreg = s(asset.get('kode_register'), 40)

    price = asset.get('purchase_price', 0)
    try:
        price_str = f"Rp {float(price or 0):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        price_str = "-"

    id_display = kreg if kreg != '-' else code

    # --- Shared paragraph styles ---
    lbl_style = ls('_lbl', fontSize=5.5, textColor=GRAY, fontName='Helvetica', leading=6.5)
    val_style = ls('_val', fontSize=7.5, textColor=NAVY, fontName='Helvetica-Bold', leading=9)

    # --- Reusable field tile (icon + label + value) ---
    def field_tile(icon_color, label, value, width, boxed=False, min_h=8 * mm):
        t = Table([
            [icon_box(icon_color, 2.6 * mm), Paragraph(label, lbl_style)],
            [Paragraph(value, val_style)],
        ], colWidths=[3.6 * mm, max(width - 3.6 * mm, 6 * mm)],
            rowHeights=[3.2 * mm, min_h - 3.2 * mm])
        style = [
            ('SPAN', (0, 1), (1, 1)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0.4 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.4 * mm),
        ]
        if boxed:
            style += [
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('BACKGROUND', (0, 0), (-1, -1), STRIPEBG),
                ('ROUNDEDCORNERS', [4, 4, 4, 4]),
            ]
        t.setStyle(TableStyle(style))
        return t

    def pill(text, txt_color, bg_color, width):
        t = Table([[Paragraph(
            text.upper(),
            ls('_pill', fontSize=6.5, textColor=txt_color, fontName='Helvetica-Bold', alignment=1))]],
            colWidths=[width], rowHeights=[5.5 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.3, bg_color),
            ('ROUNDEDCORNERS', [7, 7, 7, 7]),
        ]))
        return t

    def panel_header(icon_color, title, right_text='', right_font='Courier-Bold', right_size=8):
        cells = [icon_box(icon_color, 3.4 * mm),
                 Paragraph(title, ls('_ph', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold'))]
        widths = [6 * mm, UW - 6 * mm]
        if right_text:
            cells.append(Paragraph(right_text, ls('_phr', fontSize=right_size, textColor=WHITE,
                                                  fontName=right_font, alignment=2, leading=right_size + 1)))
            widths = [6 * mm, UW - 6 * mm - 47 * mm, 47 * mm]
        t = Table([cells], colWidths=widths, rowHeights=[9 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 2.5 * mm),
            ('LEFTPADDING', (1, 0), (-1, -1), 1.5 * mm),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 2.5 * mm),
            ('ROUNDEDCORNERS', [5, 5, 0, 0]),
        ]))
        return t

    elements = {'A': [], 'B': [], 'C': [], 'D': []}

    # ==================================================================
    # PANEL A — TAMPAK DEPAN HALAMAN 1 (identitas)
    # ==================================================================
    elements['A'].append(panel_header(WHITE, "KARTU INVENTARIS", f"NUP {nup}"))
    elements['A'].append(Spacer(1, 2 * mm))

    photo_w, photo_h = 33 * mm, 47 * mm
    photo_el = _decode_photo_flowable(asset, photo_w, photo_h)

    info_w = UW - photo_w - 4 * mm
    half = (info_w - 2 * mm) / 2

    spec_grid = Table([
        [field_tile(BLUE, "KATEGORI", cat, half, min_h=8.5 * mm),
         field_tile(GRAY, "S/N", sn, half, min_h=8.5 * mm)],
        [field_tile(GREEN, "MEREK/MODEL", f"{brand} / {mdl}", half, min_h=8.5 * mm),
         field_tile(ORANGE, "LOKASI", loc, half, min_h=8.5 * mm)],
    ], colWidths=[half + 1 * mm, half + 1 * mm], rowHeights=[8.5 * mm, 8.5 * mm])
    spec_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
    ]))

    cond_baik = cond.lower().startswith('baik')
    stat_aktif = stat.lower().startswith('aktif')
    nilai_block = Table([
        [Paragraph("NILAI PEROLEHAN", ls('_nl', fontSize=5.5, textColor=GRAY,
                                         fontName='Helvetica', alignment=2))],
        [Paragraph(price_str, ls('_np', fontSize=9, textColor=GREEN,
                                 fontName='Helvetica-Bold', alignment=2, leading=10))],
    ], colWidths=[info_w - 52 * mm])
    nilai_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    badges = Table([[
        pill(cond, GREEN if cond_baik else ORANGE, GREENBG if cond_baik else ORANGEBG, 24 * mm),
        pill(stat, BLUE if stat_aktif else GRAY, BLUEBG if stat_aktif else STRIPEBG, 24 * mm),
        nilai_block,
    ]], colWidths=[25 * mm, 25 * mm, info_w - 50 * mm], rowHeights=[10 * mm])
    badges.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (1, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 1.5 * mm),
        ('LEFTPADDING', (2, 0), (2, 0), 2 * mm),
    ]))

    info_col = Table([
        [Paragraph("KODE INVENTARIS", ls('_ki', fontSize=6, textColor=GRAY, fontName='Helvetica'))],
        [Paragraph(code, ls('_code', fontSize=20, textColor=NAVY, fontName='Courier-Bold', leading=22))],
        [Paragraph(name, ls('_name', fontSize=8.5, textColor=NAVY, fontName='Helvetica-Bold', leading=10))],
        [Spacer(1, 1 * mm)],
        [spec_grid],
        [badges],
    ], colWidths=[info_w], rowHeights=[4.5 * mm, 10 * mm, 7 * mm, 1 * mm, 18 * mm, 10 * mm])
    info_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    body = Table([[photo_el, info_col]], colWidths=[photo_w + 4 * mm, info_w],
                 rowHeights=[51 * mm])
    body.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 4 * mm),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
    ]))
    elements['A'].append(body)
    elements['A'].append(Spacer(1, 1.5 * mm))

    # Footer strip: QR + ID info
    raw_kreg = str(asset.get('kode_register') or '').strip()
    raw_code = str(asset.get('asset_code') or '').strip()
    raw_nup = str(asset.get('NUP') or '').strip()
    qr_payload = f"#{raw_kreg}" if raw_kreg else f"#{raw_code}-{raw_nup}"
    qr_el = build_qr_flowable(qr_payload, 15 * mm) or Table([['QR']], colWidths=[15 * mm], rowHeights=[15 * mm])

    id_block = Table([
        [Paragraph(f"ID: {id_display}", ls('_fid', fontSize=7, textColor=GRAY, fontName='Helvetica', leading=8))],
        [Paragraph(f"KODE: {code} &nbsp;|&nbsp; NUP: {nup}",
                   ls('_fkd', fontSize=8, textColor=NAVY, fontName='Courier-Bold', leading=10))],
    ], colWidths=[UW - 20 * mm])
    id_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5 * mm),
    ]))

    footer = Table([[qr_el, id_block]], colWidths=[18 * mm, UW - 18 * mm], rowHeights=[17 * mm])
    footer.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), STRIPEBG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('LEFTPADDING', (1, 0), (1, 0), 2 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
    ]))
    elements['A'].append(footer)

    # ==================================================================
    # PANEL B — TAMPAK DEPAN HALAMAN 2 (detail administratif)
    # ==================================================================
    elements['B'].append(panel_header(WHITE, "DETAIL ADMINISTRATIF"))
    elements['B'].append(Spacer(1, 2.5 * mm))

    colw = (UW - 3 * mm) / 2
    tile_h = 9.5 * mm
    gap = Spacer(1, 2 * mm)

    left_tiles = [
        field_tile(BLUE, "ESELON I", eselon1, colw, boxed=True, min_h=tile_h), gap,
        field_tile(BLUE, "ESELON II", eselon2, colw, boxed=True, min_h=tile_h), gap,
        field_tile(GREEN, "PENANGGUNG JAWAB", usr, colw, boxed=True, min_h=tile_h), gap,
        field_tile(ORANGE, "TGL PEROLEHAN", pdate, colw, boxed=True, min_h=tile_h), gap,
        field_tile(GRAY, "NO. KONTRAK", kontrak, colw, boxed=True, min_h=tile_h), gap,
        field_tile(GRAY, "BUKTI PEROLEHAN", bukti, colw, boxed=True, min_h=tile_h),
    ]
    right_tiles = [
        field_tile(ORANGE, "LOKASI", loc, colw, boxed=True, min_h=tile_h), gap,
        field_tile(GRAY, "NO. SPM", spm, colw, boxed=True, min_h=tile_h), gap,
        field_tile(GREEN, "SUPPLIER", supplier, colw, boxed=True, min_h=tile_h), gap,
        field_tile(BLUE, "KATEGORI", cat, colw, boxed=True, min_h=tile_h),
    ]

    tiles_grid = Table([[left_tiles, right_tiles]], colWidths=[colw + 1.5 * mm, colw + 1.5 * mm])
    tiles_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 1.5 * mm),
        ('LEFTPADDING', (1, 0), (1, 0), 1.5 * mm),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements['B'].append(tiles_grid)

    # ==================================================================
    # PANEL C / D — TAMPAK BELAKANG (riwayat inventarisasi)
    # ==================================================================
    mapped = []
    for i, h in enumerate(history[:6]):
        mapped.append({
            'no': str(i + 1),
            'tanggal': _fmt_date(h.get('tanggal_pengesahan')),
            'kegiatan': s(h.get('activity_name'), 44),
            'lokasi': s(h.get('location'), 24) if h.get('location') else '-',
            'petugas': s(h.get('user'), 26) if h.get('user') else '-',
            'kondisi': s(h.get('condition'), 12) if h.get('condition') else '-',
            'ket': s(h.get('inventory_status'), 18) if h.get('inventory_status') else '-',
        })

    col_widths = [8 * mm, 18 * mm, 31 * mm, 20 * mm, 20 * mm, 12 * mm, UW - 109 * mm]
    th = ls('_th', fontSize=6, textColor=GRAY, fontName='Helvetica-Bold', leading=7, alignment=1)
    td = ls('_td', fontSize=6.5, textColor=NAVY, fontName='Helvetica', leading=7.5)
    td_c = ls('_tdc', fontSize=6.5, textColor=NAVY, fontName='Helvetica', leading=7.5, alignment=1)
    td_green = ls('_tdg', fontSize=6.5, textColor=GREEN, fontName='Helvetica-Bold', leading=7.5, alignment=1)

    def riwayat_panel(rows, page_no):
        header_cells = [Paragraph(x, th) for x in
                        ["NO", "TANGGAL", "JENIS KEGIATAN", "LOKASI", "PETUGAS", "KONDISI", "KET."]]
        data = [header_cells]
        green_rows = []
        for r in range(3):
            if r < len(rows):
                row = rows[r]
                kondisi_style = td_green if row['kondisi'].lower().startswith('baik') else td_c
                if row['kondisi'].lower().startswith('baik'):
                    green_rows.append(r + 1)
                data.append([
                    Paragraph(row['no'], td_c),
                    Paragraph(row['tanggal'], td_c),
                    Paragraph(row['kegiatan'], td),
                    Paragraph(row['lokasi'], td),
                    Paragraph(row['petugas'], td),
                    Paragraph(row['kondisi'], kondisi_style),
                    Paragraph(row['ket'], td_c),
                ])
            else:
                data.append([Paragraph('', td_c) for _ in range(7)])

        tbl = Table(data, colWidths=col_widths, rowHeights=[7 * mm] + [12.5 * mm] * 3)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.6, LIGHTGRAY),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1 * mm),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (5, 0), (6, -1), 'CENTER'),
        ]))

        note = Table([[
            icon_box(BLUE, 3.2 * mm),
            Paragraph("Catatan: Riwayat akan bertambah seiring dilakukan kegiatan inventarisasi.",
                      ls('_note', fontSize=6, textColor=colors.HexColor('#1e40af'), fontName='Helvetica', leading=7.5)),
            Paragraph(f"Halaman {page_no} dari 2",
                      ls('_pg', fontSize=6.5, textColor=GRAY, fontName='Helvetica-Bold', alignment=2)),
        ]], colWidths=[5 * mm, UW - 5 * mm - 26 * mm, 26 * mm], rowHeights=[8 * mm])
        note.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NOTEBG),
            ('BOX', (0, 0), (-1, -1), 0.5, NOTEBORDER),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 1.5 * mm),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 2 * mm),
        ]))
        subtitle = "Riwayat kegiatan inventarisasi barang ini"
        return tbl, note, subtitle

    tbl_c, note_c, sub = riwayat_panel(mapped[0:3], 1)
    tbl_d, note_d, _ = riwayat_panel(mapped[3:6], 2)

    elements['C'].append(panel_header(WHITE, "RIWAYAT INVENTARISASI", sub, right_font='Helvetica', right_size=6))
    elements['C'].append(Spacer(1, 3 * mm))
    elements['C'].append(tbl_c)
    elements['C'].append(Spacer(1, 4 * mm))
    elements['C'].append(note_c)

    elements['D'].append(panel_header(WHITE, "RIWAYAT INVENTARISASI", sub, right_font='Helvetica', right_size=6))
    elements['D'].append(Spacer(1, 3 * mm))
    elements['D'].append(tbl_d)
    elements['D'].append(Spacer(1, 4 * mm))
    elements['D'].append(note_d)

    return elements


# ============================================================================
# Page rendering — 2x2 fold layout
# ============================================================================

_PANEL_CAPTIONS = {
    'A': "TAMPAK DEPAN - HALAMAN 1",
    'B': "TAMPAK DEPAN - HALAMAN 2",
    'C': "TAMPAK BELAKANG - HALAMAN 1",
    'D': "TAMPAK BELAKANG - HALAMAN 2",
}


def _panel_rects():
    """Rect (x, y, w, h) tiap panel + koordinat garis lipat."""
    col1_x = PANEL_MARGIN
    col2_x = PANEL_MARGIN + PANEL_W + FOLD_GAP_X
    x_fold = PANEL_MARGIN + PANEL_W + FOLD_GAP_X / 2

    row1_cap_top = PAGE_H - TOP_M
    row1_panel_top = row1_cap_top - CAP_H
    row1_panel_bot = row1_panel_top - PANEL_H
    y_fold = row1_panel_bot - FOLD_GAP_Y / 2
    row2_cap_top = row1_panel_bot - FOLD_GAP_Y
    row2_panel_top = row2_cap_top - CAP_H
    row2_panel_bot = row2_panel_top - PANEL_H

    return {
        'A': (col1_x, row1_panel_bot, PANEL_W, PANEL_H),
        'B': (col2_x, row1_panel_bot, PANEL_W, PANEL_H),
        'C': (col1_x, row2_panel_bot, PANEL_W, PANEL_H),
        'D': (col2_x, row2_panel_bot, PANEL_W, PANEL_H),
        '_fold': (x_fold, y_fold, row1_panel_top, row2_panel_bot),
        '_caps': {
            'A': (col1_x, row1_panel_top), 'B': (col2_x, row1_panel_top),
            'C': (col1_x, row2_panel_top), 'D': (col2_x, row2_panel_top),
        },
    }


def _draw_card_page(c, elements):
    """Gambar satu halaman 2x2 (4 panel) beserta garis lipat & caption."""
    rects = _panel_rects()
    x_fold, y_fold, fold_top, fold_bot = rects['_fold']

    # Panel borders + captions
    for key in ('A', 'B', 'C', 'D'):
        x, y, w, h = rects[key]
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=0)
        cap_x, cap_y = rects['_caps'][key]
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(GRAY)
        c.drawString(cap_x + 1 * mm, cap_y + 1.2 * mm, _PANEL_CAPTIONS[key])

    # --- Fold lines (garis lipat) ---
    c.setStrokeColor(LIGHTGRAY)
    c.setLineWidth(0.6)
    c.setDash([2, 2])
    # Vertical fold between the two columns
    c.line(x_fold, fold_bot - 2 * mm, x_fold, fold_top + 2 * mm)
    # Horizontal fold between the two rows
    c.line(PANEL_MARGIN, y_fold, PAGE_W - PANEL_MARGIN, y_fold)
    c.setDash([])

    # Fold labels
    c.setFillColor(GRAY)
    c.setFont('Helvetica', 6)
    # Horizontal fold label — offset to the left column center so it does not
    # collide with the vertical fold label at the page center.
    h_label = "garis lipat (tampak depan & belakang)"
    h_x = PANEL_MARGIN + PANEL_W / 2
    lw = c.stringWidth(h_label, 'Helvetica', 6)
    c.setFillColor(WHITE)
    c.rect(h_x - lw / 2 - 2, y_fold - 1.6 * mm, lw + 4, 3.2 * mm, stroke=0, fill=1)
    c.setFillColor(GRAY)
    c.drawCentredString(h_x, y_fold - 0.7 * mm, h_label)
    # Vertical fold label (rotated)
    v_label = "— — garis lipat (halaman 1 & 2) — —"
    c.saveState()
    c.translate(x_fold, (fold_top + fold_bot) / 2)
    c.rotate(90)
    vw = c.stringWidth(v_label, 'Helvetica', 6)
    c.setFillColor(WHITE)
    c.rect(-vw / 2 - 2, -1.6 * mm, vw + 4, 3.2 * mm, stroke=0, fill=1)
    c.setFillColor(GRAY)
    c.drawCentredString(0, -0.7 * mm, v_label)
    c.restoreState()

    # --- Panel content frames ---
    for key in ('A', 'B', 'C', 'D'):
        x, y, w, h = rects[key]
        frame = Frame(x, y, w, h,
                      leftPadding=FRAME_PAD, rightPadding=FRAME_PAD,
                      topPadding=FRAME_PAD, bottomPadding=FRAME_PAD,
                      showBoundary=0)
        frame.addFromList(list(elements[key]), c)


async def _fetch_asset_history(asset):
    """Ambil riwayat inventarisasi untuk identitas aset (robust; [] bila gagal).

    Identitas: prioritas kode_register; fallback (asset_code, NUP). Bila aset
    punya activity dengan kode_satker, riwayat dibatasi pada satker yang sama
    (record legacy tanpa kode_satker tetap disertakan). Cap 6 record untuk dua
    panel belakang.
    """
    try:
        kreg = str(asset.get('kode_register') or '').strip()
        if kreg:
            identity_query = {"kode_register": kreg}
        else:
            identity_query = {
                "asset_code": str(asset.get('asset_code') or '').strip(),
                "NUP": str(asset.get('NUP') or '').strip(),
            }
        query = dict(identity_query)
        try:
            activity_id = asset.get('activity_id')
            if activity_id:
                activity = await db.inventory_activities.find_one(
                    {"id": activity_id}, {"_id": 0, "kode_satker": 1})
                kode_satker = str((activity or {}).get('kode_satker') or '').strip()
                if kode_satker:
                    query["$or"] = [
                        {"kode_satker": kode_satker},
                        {"kode_satker": {"$in": ["", None]}},
                        {"kode_satker": {"$exists": False}},
                    ]
        except Exception as e:
            logger.debug(f"[cards] satker scope skipped: {e}")

        return await db.inventory_history.find(query, {"_id": 0}).sort(
            [("tanggal_pengesahan", -1), ("ticket_number", -1)]
        ).to_list(6)
    except Exception as e:
        logger.warning(f"[cards] history fetch failed: {e}")
        return []


@cards_router.get("/assets/{asset_id}/card")
async def get_asset_card_pdf(asset_id: str, _user: dict = Depends(require_user)):
    """Kartu Inventarisasi (1 aset = 1 halaman A4 landscape, 4 panel fold)."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    history = await _fetch_asset_history(asset)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    elements = create_ktp_card_elements(asset, history)
    _draw_card_page(c, elements)
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kartu_inventaris_{asset_id}.pdf"}
    )


@cards_router.post("/assets/cards/bulk")
async def get_bulk_asset_cards(asset_ids: List[str], _user: dict = Depends(require_user)):
    """Kartu Inventarisasi massal: satu halaman A4 landscape (4 panel fold) per aset."""
    if not asset_ids:
        raise HTTPException(status_code=400, detail="Tidak ada aset yang dipilih")

    assets = await db.assets.find({"id": {"$in": asset_ids}}, {"_id": 0}).to_list(len(asset_ids))
    if not assets:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    for idx, asset in enumerate(assets):
        if idx > 0:
            c.showPage()
        # Riwayat per aset (find per aset dapat diterima untuk jumlah wajar).
        history = await _fetch_asset_history(asset)
        elements = create_ktp_card_elements(asset, history)
        _draw_card_page(c, elements)

    c.save()
    buffer.seek(0)

    logger.info(f"Generated bulk fold cards for {len(assets)} assets")

    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kartu_inventaris_massal_{len(assets)}.pdf"})
