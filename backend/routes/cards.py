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
            ls('_pill', fontSize=6.5, textColor=txt_color, fontName='Helvetica-Bold', alignment=1))]],
            colWidths=[width], rowHeights=[5.5 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.3, bg_color),
            ('ROUNDEDCORNERS', [7, 7, 7, 7]),
        ]))
        return t

    def panel_header(icon, title, right_text='', right_font='Helvetica', right_size=6):
        cells = [card_icon(icon, 4 * mm, WHITE),
                 Paragraph(title, ls('_ph', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold'))]
        widths = [6.5 * mm, UW - 6.5 * mm]
        if right_text:
            cells.append(Paragraph(right_text, ls('_phr', fontSize=right_size, textColor=colors.HexColor('#cbd5e1'),
                                                  fontName=right_font, alignment=2, leading=right_size + 1)))
            widths = [6.5 * mm, UW - 6.5 * mm - 44 * mm, 44 * mm]
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
    # Judul membentang penuh; NUP TIDAK di kanan-atas (tetap ada di footer).
    # ==================================================================
    elements['A'].append(panel_header('box', "KARTU INVENTARIS"))
    elements['A'].append(Spacer(1, 2 * mm))

    photo_w, photo_h = 33 * mm, 47 * mm
    photo_el = _decode_photo_flowable(asset, photo_w, photo_h)

    info_w = UW - photo_w - 4 * mm
    half = (info_w - 2 * mm) / 2

    spec_grid = Table([
        [field_tile('tag', BLUE, "KATEGORI", cat, half, min_h=8.5 * mm),
         field_tile('barcode', GRAY, "S/N", sn, half, min_h=8.5 * mm)],
        [field_tile('tag', GREEN, "MEREK/MODEL", f"{brand} / {mdl}", half, min_h=8.5 * mm),
         field_tile('pin', ORANGE, "LOKASI", loc, half, min_h=8.5 * mm)],
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
        [card_icon('rupiah', 3.4 * mm, GREEN),
         Paragraph("NILAI PEROLEHAN", ls('_nl', fontSize=5.5, textColor=GRAY,
                                         fontName='Helvetica', alignment=0))],
        [Paragraph(price_str, ls('_np', fontSize=9, textColor=GREEN,
                                 fontName='Helvetica-Bold', alignment=0, leading=10))],
    ], colWidths=[4.4 * mm, info_w - 52 * mm - 4.4 * mm])
    nilai_block.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
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

    # Footer strip: QR + ID info (NUP tetap tampil di sini)
    raw_kreg = str(asset.get('kode_register') or '').strip()
    raw_code = str(asset.get('asset_code') or '').strip()
    raw_nup = str(asset.get('NUP') or '').strip()
    qr_payload = f"#{raw_kreg}" if raw_kreg else f"#{raw_code}-{raw_nup}"
    qr_el = build_qr_flowable(qr_payload, 15 * mm) or Table([['QR']], colWidths=[15 * mm], rowHeights=[15 * mm])

    id_block = Table([
        [Paragraph(f"ID: {esc(id_display)}", ls('_fid', fontSize=7, textColor=GRAY, fontName='Helvetica', leading=8))],
        [Paragraph(f"KODE: {esc(code)} &nbsp;|&nbsp; NUP: {esc(nup)}",
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
    # Grid 2 kolom rapi. PENANGGUNG JAWAB membentang penuh (pengguna + qualifier).
    # KATEGORI diganti PEROLEHAN DARI; ditambah tile KELENGKAPAN.
    # ==================================================================
    elements['B'].append(panel_header('file', "DETAIL ADMINISTRATIF"))
    elements['B'].append(Spacer(1, 2.5 * mm))

    colw = (UW - 3 * mm) / 2
    tile_h = 10.4 * mm
    full_w = UW - 3 * mm

    pj_tile = field_tile('person', GREEN, "PENANGGUNG JAWAB (PENGGUNA)", pj_value,
                         full_w, boxed=True, min_h=tile_h, raw=True)
    tiles_data = [
        [pj_tile, ''],
        [field_tile('building', BLUE, "ESELON I", eselon1, colw, boxed=True, min_h=tile_h),
         field_tile('building', BLUE, "ESELON II", eselon2, colw, boxed=True, min_h=tile_h)],
        [field_tile('inbox', GREEN, "PEROLEHAN DARI", perolehan, colw, boxed=True, min_h=tile_h),
         field_tile('truck', GREEN, "SUPPLIER", supplier, colw, boxed=True, min_h=tile_h)],
        [field_tile('calendar', ORANGE, "TGL PEROLEHAN", pdate, colw, boxed=True, min_h=tile_h),
         field_tile('pin', ORANGE, "LOKASI", loc, colw, boxed=True, min_h=tile_h)],
        [field_tile('file', GRAY, "NO. KONTRAK", kontrak, colw, boxed=True, min_h=tile_h),
         field_tile('file', GRAY, "BAST", bast, colw, boxed=True, min_h=tile_h)],
        [field_tile('file', GRAY, "NO. SPM", spm, colw, boxed=True, min_h=tile_h),
         field_tile('check', BLUE, "KELENGKAPAN", kel_value, colw, boxed=True, min_h=tile_h, raw=True)],
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
    # Kolom ringkas: NO | TIKET/TANGGAL | KEGIATAN (terlebar) | PETUGAS | KONDISI
    # ==================================================================
    mapped = []
    for i, h in enumerate(history[:6]):
        mapped.append({
            'no': str(i + 1),
            'ticket': s(h.get('ticket_number'), 18),
            'date': _fmt_date_compact(h.get('tanggal_pengesahan')),
            'kegiatan': s(h.get('activity_name'), 52),
            'nomor_surat': s(h.get('nomor_surat'), 40) if h.get('nomor_surat') else '-',
            'lokasi': s(h.get('location'), 34) if h.get('location') else '',
            # petugas: field baru; fallback ke `user` untuk record legacy
            'petugas': s(h.get('petugas') or h.get('user'), 28),
            'kondisi': s(h.get('condition'), 14) if h.get('condition') else '-',
            'status': s(h.get('inventory_status'), 22) if h.get('inventory_status') else '-',
        })

    no_w, tk_w, pet_w, kon_w = 7 * mm, 27 * mm, 24 * mm, 21 * mm
    keg_w = UW - (no_w + tk_w + pet_w + kon_w)
    col_widths = [no_w, tk_w, keg_w, pet_w, kon_w]

    th = ls('_th', fontSize=5.8, textColor=GRAY, fontName='Helvetica-Bold', leading=7, alignment=1)
    cell = ls('_cell', fontSize=6.4, textColor=NAVY, fontName='Helvetica', leading=8.2)
    cell_c = ls('_cellc', fontSize=7, textColor=NAVY, fontName='Helvetica-Bold', leading=8, alignment=1)

    def tiket_cell(r):
        return Paragraph(
            f"<font name='Helvetica-Bold' size='6.8' color='{HX_NAVY}'>{esc(r['ticket'])}</font>"
            f"<br/><font size='5.6' color='{HX_GRAY}'>{esc(r['date'])}</font>", cell)

    def kegiatan_cell(r):
        html = (f"<font name='Helvetica-Bold' size='6.8' color='{HX_NAVY}'>{esc(r['kegiatan'])}</font>"
                f"<br/><font size='5.6' color='{HX_GRAY}'>No. Surat: {esc(r['nomor_surat'])}</font>")
        if r['lokasi']:
            html += f"<br/><font size='5.2' color='{HX_LIGHT}'>Lokasi: {esc(r['lokasi'])}</font>"
        return Paragraph(html, cell)

    def petugas_cell(r):
        return Paragraph(f"<font size='6.4' color='{HX_NAVY}'>{esc(r['petugas'])}</font>", cell)

    def kondisi_cell(r):
        cclr = HX_GREEN if r['kondisi'].lower().startswith('baik') else HX_ORANGE
        return Paragraph(
            f"<font name='Helvetica-Bold' size='6.6' color='{cclr}'>{esc(r['kondisi'])}</font>"
            f"<br/><font size='5.2' color='{HX_GRAY}'>{esc(r['status'])}</font>",
            ls('_kon', fontSize=6.4, alignment=1, leading=8))

    def riwayat_panel(rows, page_no):
        header_cells = [Paragraph(x, th) for x in
                        ["NO", "TIKET / TANGGAL", "KEGIATAN", "PETUGAS", "KONDISI"]]
        data = [header_cells]
        for r in range(3):
            if r < len(rows):
                row = rows[r]
                data.append([
                    Paragraph(row['no'], cell_c),
                    tiket_cell(row),
                    kegiatan_cell(row),
                    petugas_cell(row),
                    kondisi_cell(row),
                ])
            else:
                data.append([Paragraph('', cell_c) for _ in range(5)])

        tbl = Table(data, colWidths=col_widths, rowHeights=[6.5 * mm] + [16 * mm] * 3)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.6, LIGHTGRAY),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5 * mm),
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
        ]], colWidths=[5 * mm, UW - 5 * mm - 24 * mm, 24 * mm], rowHeights=[8 * mm])
        note.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NOTEBG),
            ('BOX', (0, 0), (-1, -1), 0.5, NOTEBORDER),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 1.5 * mm),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 2 * mm),
        ]))
        return tbl, note

    tbl_c, note_c = riwayat_panel(mapped[0:3], 1)
    tbl_d, note_d = riwayat_panel(mapped[3:6], 2)

    elements['C'].append(panel_header('clock', "RIWAYAT INVENTARISASI", "Riwayat kegiatan aset ini"))
    elements['C'].append(Spacer(1, 3 * mm))
    elements['C'].append(tbl_c)
    elements['C'].append(Spacer(1, 4 * mm))
    elements['C'].append(note_c)

    elements['D'].append(panel_header('clock', "RIWAYAT INVENTARISASI", "Riwayat kegiatan aset ini"))
    elements['D'].append(Spacer(1, 3 * mm))
    elements['D'].append(tbl_d)
    elements['D'].append(Spacer(1, 4 * mm))
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
