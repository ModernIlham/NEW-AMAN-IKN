"""KTP-style asset card PDF generation routes.

Kartu Inventarisasi dicetak sebagai 4 panel (grid 2x2) pada satu halaman A4
landscape yang SALING BERSENTUHAN (contiguous block), dengan garis lipat
(fold line) berbentuk salib di tengah:

    [A: Tampak Depan Hal 1] │ [B: Tampak Depan Hal 2]
    ────────────── garis lipat (horizontal) ──────────────
    [C: Tampak Belakang Hal 1] │ [D: Tampak Belakang Hal 2]

Keempat panel menyatu tanpa celah; garis lipat digambar tepat di dua tepi
tengah yang dibagi bersama (salib putus-putus). Semua caption/keterangan lipat
diletakkan di MARGIN LUAR halaman (bukan di antar panel), sehingga blok dapat
dipotong lalu dilipat rapi.

Panel A: identitas aset + foto + QR.
Panel B: detail administratif (grid 2 kolom).
Panel C/D: riwayat inventarisasi (tabel ringkas, 3 baris per panel).
"""
import io
import base64
import logging
from datetime import datetime
from typing import List
from xml.sax.saxutils import escape as _xml_escape
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
from reportlab.graphics.shapes import (
    Drawing, Rect, Line, Circle, Polygon, PolyLine, String,
)
from reportlab.graphics import renderPDF
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

# Hex string versions (untuk inline <font color=...> di Paragraph)
HX_NAVY = '#0f172a'
HX_BLUE = '#2563eb'
HX_GREEN = '#16a34a'
HX_ORANGE = '#ea580c'
HX_GRAY = '#64748b'
HX_LIGHT = '#94a3b8'

# --- Page / panel geometry (landscape A4, 2x2 CONTIGUOUS grid) ---
PAGE_W, PAGE_H = landscape(A4)          # 297mm x 210mm
# Margin luar halaman — di sinilah caption & keterangan lipat diletakkan.
LEFT_M = 11 * mm
RIGHT_M = 11 * mm
TOP_M = 9.5 * mm
BOT_M = 9.5 * mm
GRID_W = PAGE_W - LEFT_M - RIGHT_M       # lebar blok 2x2
GRID_H = PAGE_H - TOP_M - BOT_M          # tinggi blok 2x2
PANEL_W = GRID_W / 2                      # panel saling bersentuhan (tanpa celah)
PANEL_H = GRID_H / 2
FRAME_PAD = 2.6 * mm
UW = PANEL_W - 2 * FRAME_PAD              # usable content width inside a panel
UH = PANEL_H - 2 * FRAME_PAD             # usable content height inside a panel

# Panel A "ribbon" header (digambar di canvas, bukan flowable):
#   - thin top bar full-width (rounded top-left, siku top-right) setinggi HDR_BAR
#   - banner tab kiri yang menjulur turun (tepi kanan diagonal) setinggi HDR_H
PANEL_A_HDR_BAR = 6.4 * mm
PANEL_A_HDR_H = 13.8 * mm


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


# ---------------------------------------------------------------------------
# ICONS — ikon vektor monokrom sederhana (ReportLab tak punya icon font).
# Digambar via reportlab.graphics.shapes; setiap ikon Drawing(size, size).
# ---------------------------------------------------------------------------
def card_icon(name, size=3.6 * mm, color=NAVY):
    """Kembalikan Drawing berisi ikon garis/solid monokrom bernama `name`.

    Ikon: box, building, person/users, pin, calendar, file, tag, truck,
    inbox, clock, rupiah, barcode, check, info. Tak dikenal → titik kecil.
    """
    d = Drawing(size, size)
    sw = max(size * 0.075, 0.5)
    s = size

    def L(x1, y1, x2, y2, w=sw):
        d.add(Line(x1 * s, y1 * s, x2 * s, y2 * s,
                   strokeColor=color, strokeWidth=w, strokeLineCap=1))

    def C(cx, cy, r, fill=None, w=sw):
        d.add(Circle(cx * s, cy * s, r * s, strokeColor=color,
                     fillColor=fill, strokeWidth=w))

    def POLY(pts, fill=None, w=sw):
        d.add(Polygon([c * s for c in pts], strokeColor=color,
                      fillColor=fill, strokeWidth=w, strokeLineJoin=1))

    def PLINE(pts, w=sw):
        d.add(PolyLine([c * s for c in pts], strokeColor=color,
                       strokeWidth=w, strokeLineJoin=1, strokeLineCap=1))

    def BAR(x, y, w, h):
        d.add(Rect(x * s, y * s, w * s, h * s, strokeColor=None, fillColor=color))

    if name == 'box':
        POLY([0.5, 0.98, 0.94, 0.74, 0.94, 0.26, 0.5, 0.02, 0.06, 0.26, 0.06, 0.74])
        L(0.5, 0.5, 0.5, 0.98)
        L(0.5, 0.5, 0.06, 0.26)
        L(0.5, 0.5, 0.94, 0.26)
    elif name == 'building':
        POLY([0.08, 0.6, 0.5, 0.94, 0.92, 0.6])          # pediment
        L(0.1, 0.6, 0.9, 0.6)                             # entablature
        for cx in (0.22, 0.41, 0.59, 0.78):               # columns
            L(cx, 0.56, cx, 0.18)
        L(0.06, 0.12, 0.94, 0.12)                         # base
    elif name in ('person', 'users'):
        C(0.5, 0.72, 0.17)                                # head
        PLINE([0.18, 0.08, 0.28, 0.36, 0.72, 0.36, 0.82, 0.08])   # shoulders
        if name == 'users':                               # second person hint
            C(0.82, 0.66, 0.1)
    elif name == 'pin':
        C(0.5, 0.66, 0.28)
        L(0.30, 0.47, 0.5, 0.04)
        L(0.70, 0.47, 0.5, 0.04)
        C(0.5, 0.66, 0.1, fill=color)
    elif name == 'calendar':
        d.add(Rect(0.12 * s, 0.08 * s, 0.76 * s, 0.66 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))
        L(0.12, 0.6, 0.88, 0.6)                           # header band
        L(0.34, 0.74, 0.34, 0.92)                         # rings
        L(0.66, 0.74, 0.66, 0.92)
        for (dx, dy) in ((0.3, 0.42), (0.5, 0.42), (0.7, 0.42), (0.3, 0.26), (0.5, 0.26)):
            BAR(dx - 0.04, dy - 0.04, 0.08, 0.08)
    elif name == 'file':
        POLY([0.22, 0.06, 0.22, 0.94, 0.62, 0.94, 0.8, 0.76, 0.8, 0.06])
        PLINE([0.62, 0.94, 0.62, 0.76, 0.8, 0.76])        # folded corner
        L(0.32, 0.5, 0.7, 0.5)
        L(0.32, 0.38, 0.7, 0.38)
        L(0.32, 0.26, 0.6, 0.26)
    elif name == 'tag':
        POLY([0.14, 0.5, 0.42, 0.86, 0.9, 0.86, 0.9, 0.14, 0.42, 0.14])
        C(0.36, 0.5, 0.07)
    elif name == 'truck':
        d.add(Rect(0.06 * s, 0.3 * s, 0.48 * s, 0.4 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))
        POLY([0.54, 0.3, 0.54, 0.62, 0.72, 0.62, 0.9, 0.44, 0.9, 0.3])
        C(0.26, 0.2, 0.1)
        C(0.72, 0.2, 0.1)
    elif name == 'inbox':
        PLINE([0.14, 0.42, 0.14, 0.16, 0.86, 0.16, 0.86, 0.42])   # tray
        L(0.5, 0.88, 0.5, 0.48)                           # arrow shaft
        PLINE([0.34, 0.62, 0.5, 0.44, 0.66, 0.62])        # arrow head
    elif name == 'clock':
        C(0.5, 0.5, 0.4)
        L(0.5, 0.5, 0.5, 0.8)
        L(0.5, 0.5, 0.7, 0.48)
        C(0.5, 0.5, 0.03, fill=color)
    elif name == 'rupiah':
        C(0.5, 0.5, 0.42)
        d.add(String(0.5 * s, 0.36 * s, "Rp", textAnchor='middle',
                     fontName='Helvetica-Bold', fontSize=size * 0.42, fillColor=color))
    elif name == 'barcode':
        for (bx, bw) in ((0.16, 0.06), (0.26, 0.03), (0.33, 0.05), (0.44, 0.03),
                         (0.52, 0.07), (0.63, 0.03), (0.7, 0.05), (0.8, 0.05)):
            BAR(bx, 0.2, bw, 0.6)
    elif name == 'check':
        d.add(Rect(0.16 * s, 0.05 * s, 0.68 * s, 0.82 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))
        d.add(Rect(0.38 * s, 0.8 * s, 0.24 * s, 0.12 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))
        PLINE([0.3, 0.42, 0.44, 0.28, 0.7, 0.6], w=sw * 1.2)
    elif name == 'info':
        C(0.5, 0.5, 0.42)
        C(0.5, 0.72, 0.05, fill=color)
        L(0.5, 0.58, 0.5, 0.3)
    elif name == 'shield':
        POLY([0.16, 0.82, 0.84, 0.82, 0.84, 0.46, 0.5, 0.06, 0.16, 0.46])
        PLINE([0.34, 0.52, 0.46, 0.4, 0.66, 0.64], w=sw * 1.2)   # check
    elif name == 'camera':
        d.add(Rect(0.1 * s, 0.2 * s, 0.8 * s, 0.5 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))
        d.add(Rect(0.32 * s, 0.66 * s, 0.24 * s, 0.12 * s,
                   strokeColor=color, fillColor=None, strokeWidth=sw))   # viewfinder
        C(0.5, 0.45, 0.15)                                       # lens
        C(0.78, 0.6, 0.028, fill=color)                          # flash dot
    else:
        C(0.5, 0.5, 0.12, fill=color)
    return d


def esc(t):
    """Escape teks dinamis untuk dipakai di dalam markup Paragraph."""
    if t is None:
        return ''
    return _xml_escape(str(t))


# Bulan Indonesia (singkatan) untuk tanggal ringkas
_ID_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
           'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


def _fmt_date(v):
    """tanggal_pengesahan bisa datetime atau ISO string → 'YYYY-MM-DD'."""
    if not v:
        return '-'
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d')
    sv = str(v).strip()
    return sv[:10] if len(sv) >= 10 else (sv or '-')


def _fmt_date_compact(v):
    """Tanggal ringkas & profesional → 'DD Mon YYYY' (mis. '27 Nov 2024').

    Terima datetime atau ISO/`YYYY-MM-DD` string. Bila gagal parse, kembalikan
    10 karakter pertama (YYYY-MM-DD) supaya tetap ringkas.
    """
    if not v:
        return '-'
    dt = None
    if isinstance(v, datetime):
        dt = v
    else:
        sv = str(v).strip()
        if not sv:
            return '-'
        try:
            dt = datetime.fromisoformat(sv.replace('Z', '+00:00'))
        except Exception:
            try:
                dt = datetime.strptime(sv[:10], '%Y-%m-%d')
            except Exception:
                return sv[:10]
    return f"{dt.day} {_ID_MON[dt.month]} {dt.year}"


def _decode_photo_flowable(asset, width, height):
    """Kembalikan RLImage foto cover aset (bila ada) atau placeholder (kamera + 'FOTO ASET' + '4:3')."""
    cam = card_icon('camera', 9 * mm, LIGHTGRAY)
    cam.hAlign = 'CENTER'
    placeholder = Table([
        [cam],
        [Paragraph("FOTO ASET", ParagraphStyle(
            '_fap', fontSize=8, textColor=GRAY, fontName='Helvetica-Bold', alignment=1, leading=10))],
        [Paragraph("4 : 3", ParagraphStyle(
            '_far', fontSize=6.5, textColor=LIGHTGRAY, fontName='Helvetica', alignment=1, leading=8))],
    ], colWidths=[width], rowHeights=[height * 0.5, height * 0.28, height * 0.22])
    placeholder.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), STRIPEBG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (0, 0), 'BOTTOM'),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
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
    bast = s(asset.get('nomor_bast') or asset.get('nomor_bukti_perolehan'), 40)
    supplier = s(asset.get('supplier'), 34)
    perolehan = s(asset.get('perolehan_dari_nama'), 34)
    kreg = s(asset.get('kode_register'), 40)

    # --- Penanggung jawab = pengguna (asset.user) + qualifier melekat ---
    melekat = str(asset.get('pengguna_melekat_ke') or '').strip()
    jabatan = str(asset.get('pengguna_jabatan') or '').strip()
    operasional = str(asset.get('operasional_jenis') or '').strip()
    if melekat == 'Jabatan' and jabatan:
        pj_qual = f"Jabatan: {jabatan}"
    elif melekat == 'Operasional' and operasional:
        pj_qual = f"Operasional: {operasional}"
    elif melekat:
        pj_qual = melekat
    else:
        pj_qual = ''
    pj_value = f"<font color='{HX_NAVY}'>{esc(usr)}</font>"
    if pj_qual:
        pj_value += f" <font size='6' color='{HX_GRAY}'>({esc(pj_qual)})</font>"

    # --- Kelengkapan dokumen: checked / total dari document_checklist ---
    dc = asset.get('document_checklist') or []
    if isinstance(dc, list) and dc:
        doc_total = len(dc)
        doc_checked = sum(1 for it in dc if isinstance(it, dict) and it.get('checked'))
    else:
        doc_total = int(asset.get('doc_total') or 0)
        doc_checked = int(asset.get('doc_checked') or 0)
    if doc_total > 0:
        kel_value = (f"<font color='{HX_NAVY}'>{doc_checked}/{doc_total} dokumen</font>"
                     f" <font size='6' color='{HX_GRAY}'>"
                     f"({int(round(100 * doc_checked / doc_total))}%)</font>")
    else:
        kel_value = f"<font color='{HX_GRAY}'>-</font>"

    price = asset.get('purchase_price', 0)
    try:
        price_str = f"Rp {float(price or 0):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        price_str = "-"

    id_display = kreg if kreg != '-' else code

    # --- Shared paragraph styles ---
    lbl_style = ls('_lbl', fontSize=5.5, textColor=GRAY, fontName='Helvetica', leading=6.5)
    val_style = ls('_val', fontSize=7.5, textColor=NAVY, fontName='Helvetica-Bold', leading=8.6)

    # --- Reusable field tile (icon + label + value) ---
    def field_tile(icon, icon_color, label, value, width, boxed=False,
                   min_h=9 * mm, raw=False):
        val = value if raw else esc(value)
        t = Table([
            [card_icon(icon, 3.4 * mm, icon_color), Paragraph(label, lbl_style)],
            [Paragraph(val, val_style)],
        ], colWidths=[4.6 * mm, max(width - 4.6 * mm, 6 * mm)],
            rowHeights=[3.6 * mm, max(min_h - 3.6 * mm, 4 * mm)])
        style = [
            ('SPAN', (0, 1), (1, 1)),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('VALIGN', (0, 1), (1, 1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.6 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0.3 * mm),
            ('BOTTOMPADDING', (0, 0), (0, 0), 0.2 * mm),
            ('BOTTOMPADDING', (0, 1), (1, 1), 0.6 * mm),
            ('TOPPADDING', (0, 1), (1, 1), 0.4 * mm),
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
            ls('_pill', fontSize=6, textColor=txt_color, fontName='Helvetica-Bold', alignment=1))]],
            colWidths=[width], rowHeights=[4.8 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.3, bg_color),
            ('ROUNDEDCORNERS', [6, 6, 6, 6]),
        ]))
        return t

    def panel_header(icon, title, right_text='', right_font='Helvetica', right_size=6,
                     subtitle=''):
        if subtitle:
            title_cell = Table([
                [Paragraph(title, ls('_ph', fontSize=9.5, textColor=WHITE, fontName='Helvetica-Bold', leading=10.5))],
                [Paragraph(subtitle, ls('_phs', fontSize=6, textColor=colors.HexColor('#93c5fd'),
                                        fontName='Helvetica', leading=6.5))],
            ])
            title_cell.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (0, 0), 0), ('BOTTOMPADDING', (0, 0), (0, 0), 0.4 * mm),
                ('TOPPADDING', (0, 1), (0, 1), 0), ('BOTTOMPADDING', (0, 1), (0, 1), 0),
            ]))
            cells = [card_icon(icon, 4.6 * mm, WHITE), title_cell]
        else:
            cells = [card_icon(icon, 4 * mm, WHITE),
                     Paragraph(title, ls('_ph', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold'))]
        row_h = 10.5 * mm if subtitle else 9 * mm
        widths = [6.5 * mm, UW - 6.5 * mm]
        if right_text:
            cells.append(Paragraph(right_text, ls('_phr', fontSize=right_size, textColor=colors.HexColor('#cbd5e1'),
                                                  fontName=right_font, alignment=2, leading=right_size + 1)))
            widths = [6.5 * mm, UW - 6.5 * mm - 44 * mm, 44 * mm]
        t = Table([cells], colWidths=widths, rowHeights=[row_h])
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
    # Header 2 baris; QR di kanan-atas body (bukan footer); footer = ID ASET.
    # ==================================================================
    # Header "ribbon" (top bar + banner tab diagonal + judul) digambar di canvas
    # oleh _draw_panel_a_header; di sini cukup sisakan tinggi band-nya.
    elements['A'].append(Spacer(1, PANEL_A_HDR_H - FRAME_PAD + 1.5 * mm))

    photo_w, photo_h = 33 * mm, 46 * mm
    photo_el = _decode_photo_flowable(asset, photo_w, photo_h)

    info_w = UW - photo_w - 4 * mm
    half = (info_w - 2 * mm) / 2

    # QR di kanan-atas body (payload sama seperti sebelumnya)
    raw_kreg = str(asset.get('kode_register') or '').strip()
    raw_code = str(asset.get('asset_code') or '').strip()
    raw_nup = str(asset.get('NUP') or '').strip()
    qr_payload = f"#{raw_kreg}" if raw_kreg else f"#{raw_code}-{raw_nup}"
    qr_size = 15 * mm
    qr_el = build_qr_flowable(qr_payload, qr_size) or Table([['QR']], colWidths=[qr_size], rowHeights=[qr_size])
    qr_el.hAlign = 'RIGHT'

    # Label "KODE INVENTARIS" digambar di canvas (band header, kanan diagonal);
    # blok body hanya berisi nomor kode besar + nama aset (maks 2 baris).
    code_w = info_w - qr_size - 2.5 * mm
    code_block = Table([
        [Paragraph(code, ls('_code', fontSize=16.5, textColor=NAVY, fontName='Courier-Bold', leading=18))],
        [Paragraph(name, ls('_name', fontSize=7.5, textColor=NAVY, fontName='Helvetica-Bold', leading=9))],
    ], colWidths=[code_w], rowHeights=[8.6 * mm, 9.4 * mm])
    code_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    top_area = Table([[code_block, qr_el]],
                     colWidths=[code_w, qr_size + 2.5 * mm], rowHeights=[18 * mm])
    top_area.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 1 * mm), ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # Spec grid ringkas: nilai dibatasi agar tetap SATU baris (LOKASI lengkap
    # tetap tampil utuh di Panel B). Cegah wrap yang menabrak baris badges.
    loc_short = s(asset.get('location'), 26)
    spec_grid = Table([
        [field_tile('tag', BLUE, "KATEGORI", cat, half, min_h=8.5 * mm),
         field_tile('barcode', BLUE, "S/N", sn, half, min_h=8.5 * mm)],
        [field_tile('tag', BLUE, "MEREK/MODEL", f"{brand} / {mdl}", half, min_h=8.5 * mm),
         field_tile('pin', ORANGE, "LOKASI", loc_short, half, min_h=8.5 * mm)],
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

    # Tiga kolom berlabel: STATUS | AKTIVITAS | NILAI PEROLEHAN
    def labeled_col(label, value_flowable, width):
        value_flowable.hAlign = 'LEFT'
        t = Table([
            [Paragraph(label, ls('_bl', fontSize=5.5, textColor=GRAY, fontName='Helvetica-Bold', leading=6.5))],
            [value_flowable],
        ], colWidths=[width], rowHeights=[3.4 * mm, 6.6 * mm])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (0, 0), 0), ('BOTTOMPADDING', (0, 0), (0, 0), 0.9 * mm),
            ('TOPPADDING', (0, 1), (0, 1), 0), ('BOTTOMPADDING', (0, 1), (0, 1), 0),
        ]))
        return t

    status_pill = pill(cond, GREEN if cond_baik else ORANGE, GREENBG if cond_baik else ORANGEBG, 22 * mm)
    aktivitas_pill = pill(stat, BLUE if stat_aktif else GRAY, BLUEBG if stat_aktif else STRIPEBG, 22 * mm)
    # Tanpa ikon — beri lebar penuh agar angka rupiah berdigit banyak tetap muat
    # pada satu baris. Ukuran diperkecil ke 9pt untuk headroom nominal besar.
    nilai_val = Paragraph(price_str, ls('_np', fontSize=9, textColor=GREEN, fontName='Helvetica-Bold', leading=10.5))

    badges = Table([[
        labeled_col("STATUS", status_pill, 24 * mm),
        labeled_col("AKTIVITAS", aktivitas_pill, 24 * mm),
        labeled_col("NILAI PEROLEHAN", nilai_val, info_w - 48 * mm),
    ]], colWidths=[24 * mm, 24 * mm, info_w - 48 * mm], rowHeights=[11 * mm])
    badges.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    info_col = Table([
        [top_area],
        [spec_grid],
        [badges],
    ], colWidths=[info_w], rowHeights=[18 * mm, 17 * mm, 11 * mm])
    info_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    body = Table([[photo_el, info_col]], colWidths=[photo_w + 4 * mm, info_w],
                 rowHeights=[46 * mm])
    body.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 4 * mm),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
    ]))
    elements['A'].append(body)
    elements['A'].append(Spacer(1, 2 * mm))

    # Footer (bar abu-abu): kotak navy KECIL berisi ikon shield SAJA di kiri |
    # "ID ASET" + kode register (mono, satu baris) | KODE / NUP di kanan.
    shield = card_icon('shield', 5 * mm, WHITE)
    shield.hAlign = 'CENTER'
    sq = 9 * mm
    id_box = Table([[shield]], colWidths=[sq], rowHeights=[sq])
    id_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('ROUNDEDCORNERS', [3.5, 3.5, 3.5, 3.5]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    id_w = 57 * mm
    id_block = Table([
        [Paragraph("ID ASET", ls('_ida', fontSize=5.5, textColor=GRAY,
                                 fontName='Helvetica-Bold', leading=6))],
        [Paragraph(esc(id_display), ls('_idv', fontSize=7, textColor=NAVY,
                                       fontName='Courier-Bold', leading=8))],
    ], colWidths=[id_w])
    id_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0), ('BOTTOMPADDING', (0, 0), (0, 0), 0.4 * mm),
        ('TOPPADDING', (0, 1), (0, 1), 0), ('BOTTOMPADDING', (0, 1), (0, 1), 0),
    ]))

    kode_nup = Paragraph(f"KODE: {esc(code)}&nbsp;&nbsp;|&nbsp;&nbsp;NUP: {esc(nup)}",
                         ls('_kn', fontSize=7.5, textColor=NAVY, fontName='Courier-Bold',
                            alignment=2, leading=9))

    footer = Table([[id_box, id_block, kode_nup]],
                   colWidths=[sq + 3 * mm, id_w, UW - sq - 3 * mm - id_w],
                   rowHeights=[12 * mm])
    footer.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), STRIPEBG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 1.6 * mm), ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 2.4 * mm),
        ('RIGHTPADDING', (2, 0), (2, 0), 3 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 1 * mm), ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
    ]))
    elements['A'].append(footer)

    # ==================================================================
    # PANEL B — TAMPAK DEPAN HALAMAN 2 (detail administratif)
    # Grid 2 kolom rapi. PENANGGUNG JAWAB membentang penuh (pengguna + qualifier).
    # KATEGORI diganti PEROLEHAN DARI; ditambah tile KELENGKAPAN.
    # ==================================================================
    elements['B'].append(panel_header('file', "DETAIL ADMINISTRATIF"))
    elements['B'].append(Spacer(1, 2.5 * mm))

    colw = (UW - 3 * mm) / 2
    tile_h = 10.4 * mm
    full_w = UW - 3 * mm

    pj_tile = field_tile('person', BLUE, "PENANGGUNG JAWAB (PENGGUNA)", pj_value,
                         full_w, boxed=True, min_h=tile_h, raw=True)
    tiles_data = [
        [pj_tile, ''],
        [field_tile('building', BLUE, "ESELON I", eselon1, colw, boxed=True, min_h=tile_h),
         field_tile('building', BLUE, "ESELON II", eselon2, colw, boxed=True, min_h=tile_h)],
        [field_tile('inbox', BLUE, "PEROLEHAN DARI", perolehan, colw, boxed=True, min_h=tile_h),
         field_tile('truck', BLUE, "SUPPLIER", supplier, colw, boxed=True, min_h=tile_h)],
        [field_tile('calendar', BLUE, "TGL PEROLEHAN", pdate, colw, boxed=True, min_h=tile_h),
         field_tile('pin', ORANGE, "LOKASI", loc, colw, boxed=True, min_h=tile_h)],
        [field_tile('file', BLUE, "NO. KONTRAK", kontrak, colw, boxed=True, min_h=tile_h),
         field_tile('file', BLUE, "BAST", bast, colw, boxed=True, min_h=tile_h)],
        [field_tile('file', BLUE, "NO. SPM", spm, colw, boxed=True, min_h=tile_h),
         field_tile('check', GREEN, "KELENGKAPAN", kel_value, colw, boxed=True, min_h=tile_h, raw=True)],
    ]
    tiles_grid = Table(tiles_data, colWidths=[colw, colw],
                       rowHeights=[tile_h + 1.4 * mm] * 6)
    tiles_grid.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 1.5 * mm),
        ('LEFTPADDING', (1, 0), (1, -1), 1.5 * mm),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4 * mm),
    ]))
    elements['B'].append(tiles_grid)

    # ==================================================================
    # PANEL C / D — TAMPAK BELAKANG (riwayat inventarisasi)
    # 5 kolom: NO | TIKET/TANGGAL | KEGIATAN | PETUGAS/CATATAN | KONDISI/DOK
    # Maks 8 baris (4 per panel). `history` datang newest-first dari fetch;
    # ambil 8 TERBARU lalu BALIK agar tampil kronologis menaik (terlama dulu):
    # NO 1 = terlama dari 8 yang ditampilkan, baris terakhir = terbaru.
    # Panel C = 4 pertama (lebih lama), Panel D = 4 berikutnya (lebih baru).
    # ==================================================================
    display_history = list(reversed(history[:8]))
    mapped = []
    for i, h in enumerate(display_history):
        dt = h.get('dokumen_total')
        dc = h.get('dokumen_checked')
        dokumen = f"{int(dc or 0)}/{int(dt)}" if dt else '-'
        mapped.append({
            'no': str(i + 1),
            'ticket': s(h.get('ticket_number'), 18),
            'date': _fmt_date_compact(h.get('tanggal_pengesahan')),
            'kegiatan': s(h.get('activity_name'), 46),
            'nomor_surat': s(h.get('nomor_surat'), 34) if h.get('nomor_surat') else '-',
            'lokasi': s(h.get('location'), 30) if h.get('location') else '',
            # petugas: field baru; fallback ke `user` untuk record legacy
            'petugas': s(h.get('petugas') or h.get('user'), 24),
            'kondisi': s(h.get('condition'), 14) if h.get('condition') else '-',
            'status': s(h.get('inventory_status'), 20) if h.get('inventory_status') else '-',
            'dokumen': dokumen,
            'catatan': s(h.get('catatan'), 30) if h.get('catatan') else '-',
        })

    # 5 kolom: NO | TIKET/TANGGAL | KEGIATAN | PETUGAS/CATATAN | KONDISI/DOK.
    # KEGIATAN & PETUGAS/CATATAN diberi lebar terbesar.
    no_w, tk_w, kondok_w = 6 * mm, 22 * mm, 22 * mm
    rest = UW - (no_w + tk_w + kondok_w)
    keg_w = rest * 0.54
    petcat_w = rest - keg_w
    col_widths = [no_w, tk_w, keg_w, petcat_w, kondok_w]

    th = ls('_th', fontSize=5.2, textColor=GRAY, fontName='Helvetica-Bold', leading=6.2, alignment=1)
    cell = ls('_cell', fontSize=6.2, textColor=NAVY, fontName='Helvetica', leading=7.6)
    cell_c = ls('_cellc', fontSize=6.8, textColor=NAVY, fontName='Helvetica-Bold', leading=7.6, alignment=1)

    def tiket_cell(r):
        return Paragraph(
            f"<font name='Helvetica-Bold' size='6.4' color='{HX_NAVY}'>{esc(r['ticket'])}</font>"
            f"<br/><font size='5.4' color='{HX_GRAY}'>{esc(r['date'])}</font>", cell)

    def kegiatan_cell(r):
        html = (f"<font name='Helvetica-Bold' size='6.4' color='{HX_NAVY}'>{esc(r['kegiatan'])}</font>"
                f"<br/><font size='5.4' color='{HX_GRAY}'>No. Surat: {esc(r['nomor_surat'])}</font>")
        if r['lokasi']:
            html += f"<br/><font size='5' color='{HX_LIGHT}'>Lokasi: {esc(r['lokasi'])}</font>"
        return Paragraph(html, cell)

    def petcat_cell(r):
        # Petugas (bold) + catatan (baris kecil abu-abu, boleh membungkus)
        html = f"<font name='Helvetica-Bold' size='6.4' color='{HX_NAVY}'>{esc(r['petugas'])}</font>"
        if r['catatan'] and r['catatan'] != '-':
            html += f"<br/><font size='5.4' color='{HX_GRAY}'>{esc(r['catatan'])}</font>"
        return Paragraph(html, cell)

    def kondok_cell(r):
        # Kondisi (badge) + dok + inventory_status, semua ringkas & terpusat
        cclr = HX_GREEN if r['kondisi'].lower().startswith('baik') else HX_ORANGE
        dok_txt = f"Dok: {esc(r['dokumen'])}"
        html = (f"<font name='Helvetica-Bold' size='6.2' color='{cclr}'>{esc(r['kondisi'])}</font>"
                f"<br/><font size='5' color='{HX_GRAY}'>{dok_txt}</font>")
        if r['status'] and r['status'] != '-':
            html += f"<br/><font size='4.8' color='{HX_LIGHT}'>{esc(r['status'])}</font>"
        return Paragraph(html, ls('_kon', fontSize=6, alignment=1, leading=7))

    def riwayat_panel(rows, page_no):
        header_cells = [Paragraph(x, th) for x in
                        ["NO", "TIKET / TANGGAL", "KEGIATAN", "PETUGAS / CATATAN", "KONDISI / DOK"]]
        data = [header_cells]
        for r in range(4):
            if r < len(rows):
                row = rows[r]
                data.append([
                    Paragraph(row['no'], cell_c),
                    tiket_cell(row),
                    kegiatan_cell(row),
                    petcat_cell(row),
                    kondok_cell(row),
                ])
            else:
                data.append([Paragraph('', cell_c) for _ in range(5)])

        tbl = Table(data, colWidths=col_widths, rowHeights=[6 * mm] + [14.5 * mm] * 4)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.6, LIGHTGRAY),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.3 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1 * mm),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
        ]))

        note = Table([[
            card_icon('info', 3.2 * mm, BLUE),
            Paragraph("Catatan: Riwayat bertambah setiap kegiatan inventarisasi disahkan.",
                      ls('_note', fontSize=6, textColor=colors.HexColor('#1e40af'), fontName='Helvetica', leading=7.5)),
            Paragraph(f"Halaman {page_no} dari 2",
                      ls('_pg', fontSize=6.5, textColor=GRAY, fontName='Helvetica-Bold', alignment=2)),
        ]], colWidths=[5 * mm, UW - 5 * mm - 24 * mm, 24 * mm], rowHeights=[7.5 * mm])
        note.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NOTEBG),
            ('BOX', (0, 0), (-1, -1), 0.5, NOTEBORDER),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 1.5 * mm),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 2 * mm),
        ]))
        return tbl, note

    tbl_c, note_c = riwayat_panel(mapped[0:4], 1)
    tbl_d, note_d = riwayat_panel(mapped[4:8], 2)

    elements['C'].append(panel_header('clock', "RIWAYAT INVENTARISASI", "Riwayat kegiatan aset ini"))
    elements['C'].append(Spacer(1, 2.5 * mm))
    elements['C'].append(tbl_c)
    elements['C'].append(Spacer(1, 3 * mm))
    elements['C'].append(note_c)

    elements['D'].append(panel_header('clock', "RIWAYAT INVENTARISASI", "Riwayat kegiatan aset ini"))
    elements['D'].append(Spacer(1, 2.5 * mm))
    elements['D'].append(tbl_d)
    elements['D'].append(Spacer(1, 3 * mm))
    elements['D'].append(note_d)

    return elements


# ============================================================================
# Page rendering — 2x2 CONTIGUOUS fold layout (panels touch, dashed fold cross)
# ============================================================================

_PANEL_CAPTIONS = {
    'A': "TAMPAK DEPAN — HALAMAN 1",
    'B': "TAMPAK DEPAN — HALAMAN 2",
    'C': "TAMPAK BELAKANG — HALAMAN 1",
    'D': "TAMPAK BELAKANG — HALAMAN 2",
}


def _panel_rects():
    """Rect (x, y, w, h) tiap panel (saling bersentuhan) + koordinat lipat."""
    grid_left = LEFT_M
    grid_bottom = BOT_M
    col1_x = grid_left
    col2_x = grid_left + PANEL_W
    row_top_y = grid_bottom + PANEL_H          # panel baris atas (A/B)
    row_bot_y = grid_bottom                     # panel baris bawah (C/D)
    x_fold = grid_left + PANEL_W                 # tepi tengah vertikal (bersama)
    y_fold = grid_bottom + PANEL_H               # tepi tengah horizontal (bersama)
    return {
        'A': (col1_x, row_top_y, PANEL_W, PANEL_H),
        'B': (col2_x, row_top_y, PANEL_W, PANEL_H),
        'C': (col1_x, row_bot_y, PANEL_W, PANEL_H),
        'D': (col2_x, row_bot_y, PANEL_W, PANEL_H),
        '_grid': (grid_left, grid_bottom, GRID_W, GRID_H),
        '_fold': (x_fold, y_fold),
    }


def _draw_panel_a_header(c, rect):
    """Gambar 'ribbon' header Panel A langsung di canvas (bukan flowable).

    Terdiri dari: (a) bar tipis navy selebar panel dengan sudut kiri-atas
    membulat & kanan-atas siku; (b) banner tab navy di KIRI yang menjulur turun
    dengan tepi kanan DIAGONAL (kesan pita terlipat). Judul putih (ikon heksagon
    + 'KARTU INVENTARIS' + subjudul) diletakkan di atas banner; label 'KODE
    INVENTARIS' di sisi kanan diagonal (di atas nomor kode pada body).
    """
    px, py, pw, ph = rect
    top = py + ph
    left = px
    right = px + pw
    r = 2 * mm                       # radius sudut = match outer cut border
    bar_h = PANEL_A_HDR_BAR
    band_h = PANEL_A_HDR_H
    tab_top = left + 0.46 * pw       # x tepi kanan diagonal di dasar top-bar
    tab_bot = left + 0.375 * pw      # x tepi kanan diagonal di dasar banner

    c.saveState()
    # Clip region atas panel: sudut kiri-atas membulat, kanan-atas siku.
    clip = c.beginPath()
    clip.moveTo(left, top - band_h - 2 * mm)
    clip.lineTo(left, top - r)
    clip.curveTo(left, top - 0.4477 * r, left + 0.4477 * r, top, left + r, top)
    clip.lineTo(right, top)
    clip.lineTo(right, top - band_h - 2 * mm)
    clip.close()
    c.clipPath(clip, stroke=0, fill=0)

    c.setFillColor(NAVY)
    c.rect(left, top - bar_h, pw, bar_h, stroke=0, fill=1)      # bar tipis full-width
    tab = c.beginPath()                                          # banner tab diagonal
    tab.moveTo(left, top - band_h)
    tab.lineTo(left, top - bar_h)
    tab.lineTo(tab_top, top - bar_h)
    tab.lineTo(tab_bot, top - band_h)
    tab.close()
    c.drawPath(tab, stroke=0, fill=1)
    c.restoreState()

    # Judul putih di atas banner
    icon = card_icon('box', 5 * mm, WHITE)
    renderPDF.draw(icon, c, left + 2.6 * mm, top - 12.2 * mm)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(left + 9 * mm, top - 9.6 * mm, "KARTU INVENTARIS")
    c.setFillColor(colors.HexColor('#93c5fd'))
    c.setFont('Helvetica', 6)
    c.drawString(left + 9 * mm, top - 12.7 * mm, "Aset Tetap Milik Instansi")

    # Label KODE INVENTARIS di kanan diagonal (di atas nomor kode pada body)
    c.setFillColor(GRAY)
    c.setFont('Helvetica', 6)
    c.drawString(tab_top + 3.5 * mm, top - bar_h - 4.4 * mm, "KODE INVENTARIS")


def _draw_card_page(c, elements):
    """Gambar satu halaman: blok 2x2 menyatu + salib garis lipat + caption margin."""
    rects = _panel_rects()
    gx, gy, gw, gh = rects['_grid']
    x_fold, y_fold = rects['_fold']

    # --- Outer cut border mengelilingi seluruh blok kontigu ---
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.0)
    c.roundRect(gx, gy, gw, gh, 2 * mm, stroke=1, fill=0)

    # --- Garis lipat (salib) tepat di dua tepi tengah bersama, putus-putus ---
    c.setStrokeColor(LIGHTGRAY)
    c.setLineWidth(0.7)
    c.setDash([2.4, 2.2])
    c.line(x_fold, gy, x_fold, gy + gh)          # lipat vertikal (tinggi penuh)
    c.line(gx, y_fold, gx + gw, y_fold)          # lipat horizontal (lebar penuh)
    c.setDash([])

    # --- Caption panel di MARGIN LUAR (atas untuk depan, bawah untuk belakang) ---
    c.setFillColor(GRAY)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(gx + PANEL_W / 2, gy + gh + 2.8 * mm, _PANEL_CAPTIONS['A'])
    c.drawCentredString(gx + PANEL_W + PANEL_W / 2, gy + gh + 2.8 * mm, _PANEL_CAPTIONS['B'])
    c.drawCentredString(gx + PANEL_W / 2, gy - 5.2 * mm, _PANEL_CAPTIONS['C'])
    c.drawCentredString(gx + PANEL_W + PANEL_W / 2, gy - 5.2 * mm, _PANEL_CAPTIONS['D'])

    # --- Petunjuk lipat kecil di ujung garis (di margin, bukan antar panel) ---
    c.setFillColor(LIGHTGRAY)

    def fold_tri(cx, cy, direction):
        """Segitiga penanda lipat kecil (direction: 'down','up','left','right')."""
        h = 1.4 * mm
        if direction == 'down':
            pts = [(cx - h, cy + h), (cx + h, cy + h), (cx, cy - h)]
        elif direction == 'up':
            pts = [(cx - h, cy - h), (cx + h, cy - h), (cx, cy + h)]
        elif direction == 'left':
            pts = [(cx + h, cy - h), (cx + h, cy + h), (cx - h, cy)]
        else:
            pts = [(cx - h, cy - h), (cx - h, cy + h), (cx + h, cy)]
        p = c.beginPath()
        p.moveTo(*pts[0])
        p.lineTo(*pts[1])
        p.lineTo(*pts[2])
        p.close()
        c.drawPath(p, stroke=0, fill=1)

    # vertikal fold: penanda di margin atas & bawah (dekat x_fold)
    fold_tri(x_fold, gy + gh + 1.6 * mm, 'down')
    fold_tri(x_fold, gy - 1.6 * mm, 'up')
    # horizontal fold: penanda + label rotasi di margin kiri & kanan (dekat y_fold)
    fold_tri(gx - 1.8 * mm, y_fold, 'right')
    fold_tri(gx + gw + 1.8 * mm, y_fold, 'left')

    c.setFont('Helvetica', 5.2)
    c.setFillColor(LIGHTGRAY)
    for hx in (gx - 4.4 * mm, gx + gw + 4.4 * mm):
        c.saveState()
        c.translate(hx, y_fold)
        c.rotate(90)
        c.drawCentredString(0, -0.6 * mm, "garis lipat")
        c.restoreState()

    # --- Ribbon header Panel A (canvas) — digambar sebelum frame agar konten
    #     body (di bawah band) tetap tampil di atasnya. ---
    _draw_panel_a_header(c, rects['A'])

    # --- Panel content frames (tanpa border per-panel; blok sudah kontigu) ---
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
    (record legacy tanpa kode_satker tetap disertakan). Cap 8 record untuk dua
    panel belakang (4 baris per panel).
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
        ).to_list(8)
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
