"""
Report generation routes.
Extracted from server.py to reduce monolithic file size.
Contains: Rekapitulasi, DBHI, RHI, BAHI, SP, LHI, Executive Summary,
          Berita Acara, SPTJM, Surat Koreksi, and Report Settings.
"""
import io
import os
import logging
import base64
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path

# Template directory - relative to this file's location (works on any server)
TEMPLATES_DIR = str(Path(__file__).resolve().parent.parent / "templates")

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel

from db import db
from auth_utils import require_user, require_admin, require_user_or_query_token
from shared_utils import get_photo_from_gridfs
from report_filters import active_asset_filter
from markupsafe import Markup

logger = logging.getLogger(__name__)

reports_router = APIRouter()


def _jinja_env():
    """Jinja Environment with HTML/XML autoescaping ON for every report template.
    Autoescape neutralises XSS from user-supplied asset/satker fields rendered
    into the HTML/PDF reports; base64 image data-URIs are unaffected (the base64
    alphabet has no HTML metacharacters). Server-built HTML (e.g. status_detail)
    is passed through markupsafe.Markup so only that trusted markup stays raw."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )


# ============================================================================
# KOP SURAT (LETTERHEAD) HELPER
# ============================================================================

def _kop_surat_flowables(settings, doc_width):
    """Build classic Indonesian kop surat flowables for ReportLab reports.

    Layout: logo kiri (jika ada), blok teks instansi di tengah —
    nama_instansi (besar, reguler), nama_unit_organisasi + nama_sub_unit
    (TEBAL, kapital), alamat_instansi kecil dan bisa multi-baris (tiap
    Enter di pengaturan menjadi baris kop sendiri) — lalu garis ganda
    tebal+tipis. Degrades gracefully: baris kosong dilewati, tanpa logo ->
    teks saja. Returns [] bila settings kosong.
    """
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image as RLImage, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import mm as rl_mm, cm as rl_cm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader

    settings = settings or {}
    nama_instansi = (settings.get("nama_instansi") or "").strip()
    nama_unit = (settings.get("nama_unit_organisasi") or "").strip()
    nama_sub_unit = (settings.get("nama_sub_unit") or "").strip()
    alamat = (settings.get("alamat_instansi") or "").strip()
    logo_url = settings.get("logo_url", "") or ""

    if not (nama_instansi or nama_unit or nama_sub_unit or alamat or logo_url.startswith("data:")):
        return []

    styles = getSampleStyleSheet()
    # Gaya sesuai contoh kop resmi: baris 1 besar (nama instansi), baris 2-3
    # TEBAL (unit organisasi + sub-unit/satker), alamat kecil bisa multi-baris.
    instansi_style = ParagraphStyle('KopInstansi', parent=styles['Normal'], fontSize=13, alignment=TA_CENTER, fontName='Helvetica', leading=16)
    unit_style = ParagraphStyle('KopUnit', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=15)
    alamat_style = ParagraphStyle('KopAlamat', parent=styles['Normal'], fontSize=8.5, alignment=TA_CENTER, leading=11, textColor=rl_colors.HexColor("#333333"))

    text_flow = []
    if nama_instansi:
        text_flow.append(Paragraph(nama_instansi.upper(), instansi_style))
    if nama_unit:
        text_flow.append(Paragraph(nama_unit.upper(), unit_style))
    if nama_sub_unit:
        text_flow.append(Paragraph(nama_sub_unit.upper(), unit_style))
    # Alamat multi-baris: tiap baris (Enter di pengaturan) jadi baris sendiri
    for line in alamat.splitlines():
        line = line.strip()
        if line:
            text_flow.append(Paragraph(line, alamat_style))

    # Logo: decode data-URI base64 -> BytesIO -> Image (same approach as _generate_cover_page)
    logo_img = None
    if logo_url.startswith("data:"):
        try:
            header, b64data = logo_url.split(",", 1)
            logo_bytes = base64.b64decode(b64data)
            logo_buffer = io.BytesIO(logo_bytes)
            iw, ih = ImageReader(io.BytesIO(logo_bytes)).getSize()
            target_h = 1.8 * rl_cm
            target_w = target_h * (iw / float(ih)) if ih else target_h
            logo_img = RLImage(logo_buffer, width=target_w, height=target_h)
        except Exception:
            logo_img = None

    flowables = []
    if logo_img is not None and text_flow:
        # Kolom kosong kanan selebar logo agar teks tetap di tengah halaman
        side_w = max(logo_img.drawWidth + 2*rl_mm, 2.2*rl_cm)
        kop_table = Table([[logo_img, text_flow, ""]], colWidths=[side_w, doc_width - 2*side_w, side_w])
        kop_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        flowables.append(kop_table)
    elif logo_img is not None:
        logo_img.hAlign = 'CENTER'
        flowables.append(logo_img)
    else:
        flowables.extend(text_flow)

    # Garis ganda khas kop surat: tebal + tipis
    flowables.append(Spacer(1, 2*rl_mm))
    flowables.append(HRFlowable(width="100%", thickness=2.2, color=rl_colors.black, spaceBefore=0, spaceAfter=1.5))
    flowables.append(HRFlowable(width="100%", thickness=0.7, color=rl_colors.black, spaceBefore=0, spaceAfter=0))
    flowables.append(Spacer(1, 5*rl_mm))
    return flowables


# ============================================================================
# SHARED REPORT DESIGN SYSTEM (official ReportLab reports)
# ============================================================================
# Uniform typography, title blocks, tables, signature blocks, margins and
# page footers for the official reports: Berita Acara Tim Internal, SPTJM,
# Surat Koreksi, DBHI, RHI, BAHI, SP Hasil, SP Pelaksanaan.
# Styling/layout only -- report content is produced by each builder.

_PALETTE = {
    "header_bg": "#f1f5f9",   # table header / total-row background
    "grid": "#cbd5e1",        # table grid lines + footer rule
    "zebra": "#f8fafc",       # alternate row background on large tables
    "ink": "#1e293b",         # dark slate text (table headers)
    "muted": "#64748b",       # small gray text / page footer
}

REPORT_STYLES = None  # lazily-built shared stylesheet, see _get_report_styles()


def _get_report_styles():
    """REPORT_STYLES: one shared getSampleStyleSheet-derived style set used by
    every official ReportLab report (Helvetica family throughout)."""
    global REPORT_STYLES
    if REPORT_STYLES is not None:
        return REPORT_STYLES

    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT

    ss = getSampleStyleSheet()
    ink = rl_colors.HexColor(_PALETTE["ink"])
    muted = rl_colors.HexColor(_PALETTE["muted"])

    REPORT_STYLES = {
        # Document title block
        'DocTitle': ParagraphStyle('DocTitle', parent=ss['Title'], fontName='Helvetica-Bold',
                                   fontSize=12, leading=15, alignment=TA_CENTER,
                                   spaceBefore=0, spaceAfter=2),
        'DocSubtitle': ParagraphStyle('DocSubtitle', parent=ss['Normal'], fontSize=10,
                                      leading=13, alignment=TA_CENTER, spaceAfter=2),
        'DocNumber': ParagraphStyle('DocNumber', parent=ss['Normal'], fontSize=9.5,
                                    leading=12.5, alignment=TA_CENTER, spaceAfter=2),
        # Running text
        'Body': ParagraphStyle('Body', parent=ss['Normal'], fontSize=9.5, leading=13,
                               alignment=TA_JUSTIFY, spaceAfter=4),
        'BodyIndent': ParagraphStyle('BodyIndent', parent=ss['Normal'], fontSize=9.5,
                                     leading=13, alignment=TA_JUSTIFY, leftIndent=20,
                                     spaceAfter=3),
        'Heading': ParagraphStyle('Heading', parent=ss['Normal'], fontName='Helvetica-Bold',
                                  fontSize=9.5, leading=13, spaceBefore=6, spaceAfter=4),
        'Small': ParagraphStyle('Small', parent=ss['Normal'], fontSize=8, leading=10,
                                textColor=muted),
        'Meta': ParagraphStyle('Meta', parent=ss['Normal'], fontSize=8.5, leading=11.5,
                               textColor=ink, spaceAfter=2),
        # Table cells
        'TableHeader': ParagraphStyle('TableHeader', parent=ss['Normal'], fontName='Helvetica-Bold',
                                      fontSize=8.5, leading=10.5, alignment=TA_CENTER, textColor=ink),
        'Cell': ParagraphStyle('Cell', parent=ss['Normal'], fontSize=8.5, leading=10.5,
                               alignment=TA_LEFT),
        'CellCenter': ParagraphStyle('CellCenter', parent=ss['Normal'], fontSize=8.5,
                                     leading=10.5, alignment=TA_CENTER),
        'CellRight': ParagraphStyle('CellRight', parent=ss['Normal'], fontSize=8.5,
                                    leading=10.5, alignment=TA_RIGHT),
        'CellBold': ParagraphStyle('CellBold', parent=ss['Normal'], fontName='Helvetica-Bold',
                                   fontSize=8.5, leading=10.5, alignment=TA_LEFT),
        'CellBoldCenter': ParagraphStyle('CellBoldCenter', parent=ss['Normal'], fontName='Helvetica-Bold',
                                         fontSize=8.5, leading=10.5, alignment=TA_CENTER),
        'CellBoldRight': ParagraphStyle('CellBoldRight', parent=ss['Normal'], fontName='Helvetica-Bold',
                                        fontSize=8.5, leading=10.5, alignment=TA_RIGHT),
        # Signature block
        'Signature': ParagraphStyle('Signature', parent=ss['Normal'], fontSize=9.5,
                                    leading=13, alignment=TA_CENTER),
    }
    return REPORT_STYLES


def _std_doc(buffer, landscape_mode=False):
    """SimpleDocTemplate with the uniform report margins (2cm sides, 1.6cm top/bottom)."""
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm as rl_cm
    return SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if landscape_mode else A4,
        leftMargin=2 * rl_cm, rightMargin=2 * rl_cm,
        topMargin=1.6 * rl_cm, bottomMargin=1.6 * rl_cm,
    )


def _title_block(judul, nomor=None, subjudul=None):
    """Centered document title flowables (multi-line judul via '\\n'), with
    optional subtitle and 'Nomor: ...' line, plus consistent trailing space."""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    st = _get_report_styles()
    flow = []
    for line in str(judul).split("\n"):
        flow.append(Paragraph(line.upper(), st['DocTitle']))
    if subjudul:
        flow.append(Paragraph(str(subjudul), st['DocSubtitle']))
    if nomor:
        flow.append(Paragraph(f"Nomor: {nomor}", st['DocNumber']))
    flow.append(Spacer(1, 6 * rl_mm))
    return flow


def _std_table_style(header=True, zebra=False, total_row=False, extra=None):
    """Uniform TableStyle: light header band, thin grid, tight padding,
    VALIGN TOP, 8.5pt text. Optional zebra striping and bold total row.
    Per-column alignment (e.g. right-aligned numerics) via `extra` commands."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors as rl_colors
    grid = rl_colors.HexColor(_PALETTE["grid"])
    header_bg = rl_colors.HexColor(_PALETTE["header_bg"])
    zebra_bg = rl_colors.HexColor(_PALETTE["zebra"])
    cmds = [
        ('GRID', (0, 0), (-1, -1), 0.5, grid),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    body_start = 0
    if header:
        body_start = 1
        cmds += [
            ('BACKGROUND', (0, 0), (-1, 0), header_bg),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ]
    if zebra:
        body_end = -2 if total_row else -1
        cmds.append(('ROWBACKGROUNDS', (0, body_start), (-1, body_end),
                     [rl_colors.white, zebra_bg]))
    if total_row:
        cmds += [
            ('BACKGROUND', (0, -1), (-1, -1), header_bg),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]
    if extra:
        cmds += list(extra)
    return TableStyle(cmds)


def _fit_col_widths(widths, avail):
    """Scale relative column widths so the table spans the available width."""
    total = float(sum(widths))
    if total <= 0:
        return widths
    return [w * avail / total for w in widths]


def _activity_identity(activity, settings=None):
    """Identitas satker/kasatker sebuah kegiatan untuk laporan resmi.

    Kegiatan dari UI menyimpan field FLAT (nama_satker, kasatker_nama/nip/
    jabatan, alamat_satker); dict `kasatker` hanya ada pada data era lama.
    Nama kegiatan BUKAN fallback untuk unit organisasi — fallback itu yang
    dulu membuat "Unit Organisasi: <nama kegiatan>" muncul di laporan.
    """
    legacy = activity.get("kasatker")
    if not isinstance(legacy, dict):  # data era lama bisa berupa string nama
        legacy = {"nama_pejabat": legacy} if legacy else {}
    settings = settings or {}

    def pick(*vals, default):
        for v in vals:
            v = str(v).strip() if v is not None else ""
            if v:
                return v
        return default

    return {
        "satker_name": pick(activity.get("nama_satker"), legacy.get("nama"),
                            settings.get("nama_unit_organisasi"),
                            default="................................"),
        "kasatker_nama": pick(activity.get("kasatker_nama"), legacy.get("nama_pejabat"),
                              default="........................"),
        "kasatker_nip": pick(activity.get("kasatker_nip"), legacy.get("nip"),
                             default="........................"),
        "kasatker_jabatan": pick(activity.get("kasatker_jabatan"), legacy.get("jabatan"),
                                 default="Kuasa Pengguna Barang"),
        "alamat": pick(activity.get("alamat_satker"), settings.get("alamat_instansi"),
                       default="................................"),
    }


def _member_dict(member):
    """Anggota tim sebagai dict — pada data era lama anggota bisa berupa
    string nama saja; loop tabel memakai .get() dan akan crash tanpa ini."""
    if isinstance(member, dict):
        return member
    return {"nama": str(member).strip() or "-"}


def _member_nama(member, default="-"):
    """Nama anggota tim — anggota bisa dict {nama, ...} atau string legacy."""
    if isinstance(member, dict):
        return str(member.get("nama") or default)
    return str(member).strip() or default


_BULAN_ID = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember")


def _fmt_tanggal_id(val):
    """Tanggal gaya Indonesia ('11 Juli 2026') dari datetime / 'YYYY-MM-DD' /
    'DD/MM/YYYY'. None/kosong -> "", format tak dikenal -> apa adanya."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return f"{val.day} {_BULAN_ID[val.month - 1]} {val.year}"
    sv = str(val).strip()
    if not sv:
        return sv
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            d = datetime.strptime(sv[:10], f)
            return f"{d.day} {_BULAN_ID[d.month - 1]} {d.year}"
        except ValueError:
            continue
    return sv


def _identity_table(rows):
    """Blok identitas 'Label : Nilai' dengan kolom titik dua yang sejajar.

    rows: list of (label, value). Menggantikan pola lama deretan &nbsp; yang
    membuat titik dua tidak pernah lurus antar-baris.
    """
    from xml.sax.saxutils import escape
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.units import mm as rl_mm
    st = _get_report_styles()
    body = st['Body']
    data = [[Paragraph(f"<b>{escape(str(label))}</b>", body),
             Paragraph(":", body),
             Paragraph(escape(str(value)).replace("\n", "<br/>"), body)] for label, value in rows]
    t = Table(data, colWidths=[40 * rl_mm, 4 * rl_mm, None], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 20),  # sejajar dgn BodyIndent
        ('LEFTPADDING', (1, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return t


def _signature_block(signers, doc_width):
    """Tidy, uniform signature layout as an invisible-borders table.

    signers: list of 1..2 dicts with optional keys:
      pre    -- list[str] lines above the header (e.g. 'tempat, tanggal')
      header -- str (e.g. 'Mengetahui,' / 'Yang membuat pernyataan,')
      role   -- str below header (e.g. 'Kepala Satuan Kerja')
      nama   -- str signatory name (rendered bold + underlined)
      after  -- list[str] lines below the name (e.g. jabatan, 'NIP. ...')
    One signer renders right-aligned; two render left/right; THREE render
    two on top (left/right) + the third centered below (pola BA opname:
    penghitung & saksi di atas, mengetahui di bawah).
    """
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, KeepTogether
    from reportlab.lib.units import mm as rl_mm
    st = _get_report_styles()
    sig = st['Signature']

    max_pre = max((len(s.get('pre') or []) for s in signers), default=0)
    has_header = any(s.get('header') for s in signers)
    has_role = any(s.get('role') for s in signers)
    max_after = max((len(s.get('after') or []) for s in signers), default=0)

    def _col(s):
        flow = []
        pre = list(s.get('pre') or [])
        for _ in range(max_pre - len(pre)):
            flow.append(Paragraph('&nbsp;', sig))
        for line in pre:
            flow.append(Paragraph(line, sig))
        if has_header:
            flow.append(Paragraph(s.get('header') or '&nbsp;', sig))
        if has_role:
            flow.append(Paragraph(s.get('role') or '&nbsp;', sig))
        flow.append(Spacer(1, 15 * rl_mm))  # 3-line gap for wet signature
        flow.append(Paragraph(f"<b><u>{s.get('nama', '')}</u></b>", sig))
        after = list(s.get('after') or [])
        for line in after:
            flow.append(Paragraph(line, sig))
        for _ in range(max_after - len(after)):
            flow.append(Paragraph('&nbsp;', sig))
        return flow

    if len(signers) >= 3:
        atas = _signature_block(signers[:2], doc_width)
        bawah_tbl = Table(
            [["", _col(signers[2]), ""]],
            colWidths=[doc_width * 0.30, doc_width * 0.40, doc_width * 0.30])
        bawah_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return atas + [Spacer(1, 8 * rl_mm), KeepTogether(bawah_tbl)]

    if len(signers) == 1:
        cells = [["", _col(signers[0])]]
        col_widths = [doc_width * 0.55, doc_width * 0.45]
    else:
        cells = [[_col(signers[0]), "", _col(signers[1])]]
        col_widths = [doc_width * 0.42, doc_width * 0.16, doc_width * 0.42]

    table = Table(cells, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [KeepTogether(table)]


def _page_footer_factory(report_name):
    """Build the onPage callback: thin rule, report name (left, small gray)
    and 'Halaman X' (right) on every page."""
    def _page_footer(canvas, doc):
        from reportlab.lib import colors as rl_colors
        canvas.saveState()
        x0 = doc.leftMargin
        x1 = doc.leftMargin + doc.width
        y = doc.bottomMargin - 16
        canvas.setStrokeColor(rl_colors.HexColor(_PALETTE["grid"]))
        canvas.setLineWidth(0.5)
        canvas.line(x0, y + 9, x1, y + 9)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(rl_colors.HexColor(_PALETTE["muted"]))
        canvas.drawString(x0, y, report_name)
        canvas.drawRightString(x1, y, f"Halaman {canvas.getPageNumber()}")
        canvas.restoreState()
    return _page_footer


# ============================================================================
# REKAPITULASI
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/rekapitulasi")
async def get_rekapitulasi(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Get inventory rekapitulasi summary for an activity"""
    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)

    total = len(assets)
    ditemukan = [a for a in assets if a.get("inventory_status") == "Ditemukan"]
    tidak_ditemukan = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan"]
    belum = [a for a in assets if (a.get("inventory_status") or "Belum Diinventarisasi") == "Belum Diinventarisasi"]
    berlebih = [a for a in assets if a.get("inventory_status") == "Berlebih"]
    sengketa = [a for a in assets if a.get("inventory_status") == "Sengketa"]

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0

    kesalahan_pencatatan = [a for a in tidak_ditemukan if a.get("klasifikasi_tidak_ditemukan") == "Kesalahan Pencatatan"]
    tidak_ditemukan_lainnya = [a for a in tidak_ditemukan if a.get("klasifikasi_tidak_ditemukan") == "Tidak Ditemukan Lainnya"]

    sub_breakdown = {}
    for a in tidak_ditemukan:
        sub = a.get("sub_klasifikasi", "Belum Dikategorikan") or "Belum Dikategorikan"
        if sub not in sub_breakdown:
            sub_breakdown[sub] = {"count": 0, "value": 0}
        sub_breakdown[sub]["count"] += 1
        sub_breakdown[sub]["value"] += safe_price(a)

    return {
        "activity": {
            "id": activity.get("id"),
            "nama_kegiatan": activity.get("nama_kegiatan"),
            "nomor_surat": activity.get("nomor_surat"),
            "nomor_berita_acara": activity.get("nomor_berita_acara", ""),
            "tanggal_berita_acara": activity.get("tanggal_berita_acara", ""),
        },
        "total_bmn_diteliti": total,
        "total_nilai_diteliti": sum(safe_price(a) for a in assets),
        "ditemukan": {
            "count": len(ditemukan),
            "value": sum(safe_price(a) for a in ditemukan),
            "kondisi_baik": {
                "count": len([a for a in ditemukan if a.get("condition") == "Baik"]),
                "value": sum(safe_price(a) for a in ditemukan if a.get("condition") == "Baik")
            },
            "kondisi_rusak_ringan": {
                "count": len([a for a in ditemukan if a.get("condition") == "Rusak Ringan"]),
                "value": sum(safe_price(a) for a in ditemukan if a.get("condition") == "Rusak Ringan")
            },
            "kondisi_rusak_berat": {
                "count": len([a for a in ditemukan if a.get("condition") == "Rusak Berat"]),
                "value": sum(safe_price(a) for a in ditemukan if a.get("condition") == "Rusak Berat")
            }
        },
        "tidak_ditemukan": {
            "count": len(tidak_ditemukan),
            "value": sum(safe_price(a) for a in tidak_ditemukan),
            "kesalahan_pencatatan": {
                "count": len(kesalahan_pencatatan),
                "value": sum(safe_price(a) for a in kesalahan_pencatatan)
            },
            "tidak_ditemukan_lainnya": {
                "count": len(tidak_ditemukan_lainnya),
                "value": sum(safe_price(a) for a in tidak_ditemukan_lainnya)
            }
        },
        "belum_diinventarisasi": {
            "count": len(belum),
            "value": sum(safe_price(a) for a in belum)
        },
        "berlebih": {
            "count": len(berlebih),
            "value": sum(safe_price(a) for a in berlebih)
        },
        "sengketa": {
            "count": len(sengketa),
            "value": sum(safe_price(a) for a in sengketa)
        },
        "sub_breakdown": sub_breakdown
    }


# ============================================================================
# BERITA ACARA PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/berita-acara-pdf")
async def generate_berita_acara_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate Berita Acara Tim Internal Penelitian BMN Tidak Ditemukan (PDF)"""
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)
    tidak_ditemukan = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan"]
    ditemukan = [a for a in assets if a.get("inventory_status") == "Ditemukan"]

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0

    def fmt_rp(val):
        try: return f"Rp {int(val):,}".replace(",", ".")
        except: return "Rp 0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    small_style = st['Small']
    cell_style = st['Cell']
    bold_style = st['Heading']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    # Header
    nomor_ba = activity.get("nomor_berita_acara", "-")
    elements.extend(_title_block("BERITA ACARA\nTIM INTERNAL PENELITIAN BMN TIDAK DITEMUKAN", nomor=nomor_ba))

    # Intro paragraph
    ident = _activity_identity(activity, settings)
    intro = f"""Pada hari ini, berdasarkan Surat Tugas Nomor {activity.get('nomor_surat', '-')},
    kami Tim Internal yang ditunjuk untuk melakukan penelitian terhadap BMN yang tidak ditemukan
    pada kegiatan inventarisasi "{activity.get('nama_kegiatan', '-')}",
    menyampaikan hasil penelitian sebagai berikut:"""
    elements.append(Paragraph(intro, normal_style))
    elements.append(Spacer(1, 4*rl_mm))

    # Penomoran bagian dinamis — beberapa bagian bersyarat, jadi angka romawi
    # dihitung berurutan (dulu "III." muncul dua kali).
    _romawi = iter(["I", "II", "III", "IV", "V", "VI", "VII"])
    def _sec(judul):
        return Paragraph(f"<b>{next(_romawi)}. {judul}</b>", bold_style)

    # Tim Inventarisasi (Internal)
    tim_inti = activity.get("tim_inti", [])
    tim_pembantu_list_rhi = activity.get("tim_pembantu", [])
    if tim_inti or tim_pembantu_list_rhi:
        elements.append(_sec("TIM INVENTARISASI (INTERNAL)"))
        inv_style = _std_table_style(extra=[('ALIGN', (0, 0), (0, -1), 'CENTER')])
        tim_col_widths = _fit_col_widths([25, 55, 110, 95, 95, 80], doc.width)
        if tim_inti:
            elements.append(Paragraph("<b>Tim Inti (Pelaksana)</b>", small_style))
            ti_data = [['No', 'Peran', 'Nama', 'Jabatan', 'NIP/NIK', 'Unit']]
            for i, m in enumerate(map(_member_dict, tim_inti)):
                ti_data.append([str(i+1), 'Ketua Tim' if m.get('is_ketua') else 'Anggota', Paragraph(m.get('nama', '-'), cell_style), Paragraph(m.get('jabatan', '-'), cell_style), Paragraph(str(m.get('nip', '-')), cell_style), Paragraph(m.get('unit', '-'), cell_style)])
            ti_table = Table(ti_data, colWidths=tim_col_widths, repeatRows=1)
            ti_table.setStyle(inv_style)
            elements.append(ti_table)
            elements.append(Spacer(1, 2*rl_mm))
        if tim_pembantu_list_rhi:
            elements.append(Paragraph("<b>Tim Pembantu</b>", small_style))
            tp2_data = [['No', 'Peran', 'Nama', 'Jabatan', 'NIP/NIK', 'Unit']]
            for i, m in enumerate(map(_member_dict, tim_pembantu_list_rhi)):
                tp2_data.append([str(i+1), 'Ketua Tim' if m.get('is_ketua') else 'Anggota', Paragraph(m.get('nama', '-'), cell_style), Paragraph(m.get('jabatan', '-'), cell_style), Paragraph(str(m.get('nip', '-')), cell_style), Paragraph(m.get('unit', '-'), cell_style)])
            tp2_table = Table(tp2_data, colWidths=tim_col_widths, repeatRows=1)
            tp2_table.setStyle(inv_style)
            elements.append(tp2_table)
        elements.append(Spacer(1, 4*rl_mm))

    # Tim Peneliti (Eksternal)
    elements.append(_sec("TIM PENELITI (EKSTERNAL)"))
    tim = activity.get("tim_peneliti", [])
    if tim:
        tim_data = [['No', 'Nama', 'Jabatan', 'NIP/NIK', 'Dari Satker']]
        for i, m in enumerate(map(_member_dict, tim)):
            tim_data.append([str(i+1), Paragraph(m.get('nama', '-'), cell_style), Paragraph(m.get('jabatan', '-'), cell_style), Paragraph(str(m.get('nip', '-') or '-'), cell_style), Paragraph(m.get('dari_satker', '-') or '-', cell_style)])
        tim_table = Table(tim_data, colWidths=_fit_col_widths([25, 125, 110, 95, 100], doc.width), repeatRows=1)
        tim_table.setStyle(_std_table_style(extra=[('ALIGN', (0, 0), (0, -1), 'CENTER')]))
        elements.append(tim_table)
    else:
        elements.append(Paragraph("Tim peneliti belum ditentukan.", small_style))
    elements.append(Spacer(1, 4*rl_mm))

    # Tim Pendukung (Eksternal)
    tim_pendukung = activity.get("tim_pendukung", [])
    if tim_pendukung:
        elements.append(_sec("TIM PENDUKUNG (EKSTERNAL)"))
        tp_data = [['No', 'Nama', 'Jabatan', 'NIP', 'Dari Pihak']]
        for i, m in enumerate(map(_member_dict, tim_pendukung)):
            tp_data.append([str(i+1), Paragraph(m.get('nama', '-'), cell_style), Paragraph(m.get('jabatan', '-'), cell_style), Paragraph(str(m.get('nip', '-')), cell_style), Paragraph(m.get('dari_pihak', '-'), cell_style)])
        tp_table = Table(tp_data, colWidths=_fit_col_widths([25, 125, 110, 95, 100], doc.width), repeatRows=1)
        tp_table.setStyle(_std_table_style(extra=[('ALIGN', (0, 0), (0, -1), 'CENTER')]))
        elements.append(tp_table)
        elements.append(Spacer(1, 4*rl_mm))

    # Rekapitulasi
    elements.append(_sec("REKAPITULASI HASIL PENELITIAN"))
    total = len(assets)
    total_val = sum(safe_price(a) for a in assets)
    found_val = sum(safe_price(a) for a in ditemukan)
    notfound_val = sum(safe_price(a) for a in tidak_ditemukan)

    kesalahan = [a for a in tidak_ditemukan if a.get("klasifikasi_tidak_ditemukan") == "Kesalahan Pencatatan"]
    lainnya = [a for a in tidak_ditemukan if a.get("klasifikasi_tidak_ditemukan") == "Tidak Ditemukan Lainnya"]

    rekap_data = [
        ['No', 'Uraian', 'Jumlah NUP', 'Nilai (Rp)'],
        ['1', 'BMN yang Diteliti', str(total), fmt_rp(total_val)],
        ['2', 'BMN Ditemukan', str(len(ditemukan)), fmt_rp(found_val)],
        ['3', 'BMN Tidak Ditemukan', str(len(tidak_ditemukan)), fmt_rp(notfound_val)],
        ['', '  a. Kesalahan Pencatatan', str(len(kesalahan)), fmt_rp(sum(safe_price(a) for a in kesalahan))],
        ['', '  b. Tidak Ditemukan Lainnya', str(len(lainnya)), fmt_rp(sum(safe_price(a) for a in lainnya))],
    ]
    rekap_table = Table(rekap_data, colWidths=_fit_col_widths([30, 220, 70, 110], doc.width), repeatRows=1)
    rekap_table.setStyle(_std_table_style(extra=[
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
    ]))
    elements.append(rekap_table)
    elements.append(Spacer(1, 4*rl_mm))

    # Rincian BMN Tidak Ditemukan
    if tidak_ditemukan:
        elements.append(_sec("RINCIAN BMN TIDAK DITEMUKAN"))
        detail_data = [['No', 'Kode Barang', 'NUP', 'Nama BMN', 'Klasifikasi', 'Sub Klasifikasi', 'Nilai (Rp)']]
        for i, a in enumerate(tidak_ditemukan):
            detail_data.append([
                str(i+1),
                a.get('asset_code', '-'),
                str(a.get('NUP', '-')),
                Paragraph(a.get('asset_name', '-'), cell_style),
                Paragraph(a.get('klasifikasi_tidak_ditemukan', '-'), cell_style),
                Paragraph(a.get('sub_klasifikasi', '-'), cell_style),
                fmt_rp(safe_price(a))
            ])
        detail_table = Table(detail_data, colWidths=_fit_col_widths([25, 70, 30, 100, 75, 75, 65], doc.width), repeatRows=1)
        detail_table.setStyle(_std_table_style(zebra=True, extra=[
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ]))
        elements.append(detail_table)
        elements.append(Spacer(1, 4*rl_mm))

    # Kesimpulan
    elements.append(_sec("KESIMPULAN"))
    kesimpulan_text = activity.get("kesimpulan", "Belum ada kesimpulan.")
    elements.append(Paragraph(kesimpulan_text or "Belum ada kesimpulan.", normal_style))
    elements.append(Spacer(1, 8*rl_mm))

    # Signatures
    elements.append(Paragraph("Demikian Berita Acara ini dibuat dengan sebenar-benarnya.", normal_style))
    elements.append(Spacer(1, 6*rl_mm))

    elements.extend(_signature_block([
        {'header': 'Mengetahui,', 'role': ident["kasatker_jabatan"], 'nama': ident["kasatker_nama"],
         'after': [f'NIP. {ident["kasatker_nip"]}']},
        {'header': 'Tim Peneliti,', 'role': 'Ketua Tim',
         'nama': _member_nama(tim[0], '_______________') if tim else '_______________'},
    ], doc.width))

    footer = _page_footer_factory("Berita Acara Tim Internal Penelitian BMN Tidak Ditemukan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Berita_Acara_{activity_id[:8]}.pdf"}
    )


# ============================================================================
# SPTJM PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/sptjm-pdf")
async def generate_sptjm_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate SPTJM (Surat Pernyataan Tanggung Jawab Mutlak) PDF"""
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)
    tidak_ditemukan = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan"]

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0

    def fmt_rp(val):
        try: return f"Rp {int(val):,}".replace(",", ".")
        except: return "Rp 0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    cell_style = st['Cell']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    ident = _activity_identity(activity, settings)
    kasatker = ident["kasatker_nama"]
    nip = ident["kasatker_nip"]
    jabatan = ident["kasatker_jabatan"]
    alamat = ident["alamat"]
    alamat_singkat = alamat.splitlines()[0] if alamat.splitlines() else alamat
    total_notfound = len(tidak_ditemukan)
    total_val_notfound = sum(safe_price(a) for a in tidak_ditemukan)

    # Header
    elements.extend(_title_block("SURAT PERNYATAAN TANGGUNG JAWAB MUTLAK"))

    # Body
    elements.append(Paragraph("Yang bertanda tangan di bawah ini:", normal_style))
    elements.append(Spacer(1, 2*rl_mm))
    elements.append(_identity_table([
        ("Nama", kasatker),
        ("NIP", nip),
        ("Jabatan", jabatan),
        ("Alamat", alamat),
    ]))
    elements.append(Spacer(1, 3*rl_mm))
    body = f"""Menyatakan dengan sesungguhnya bahwa:<br/><br/>
    1. Saya bertanggung jawab penuh atas pengelolaan Barang Milik Negara (BMN) yang berada
    dalam penguasaan Satuan Kerja yang saya pimpin.<br/><br/>
    2. Berdasarkan hasil inventarisasi pada kegiatan "<b>{activity.get('nama_kegiatan', '-')}</b>"
    (Nomor Surat: {activity.get('nomor_surat', '-')}), terdapat <b>{total_notfound}</b> NUP BMN
    dengan total nilai <b>{fmt_rp(total_val_notfound)}</b> yang tidak ditemukan.<br/><br/>
    3. Saya bersedia menerima sanksi sesuai ketentuan peraturan perundang-undangan yang berlaku
    apabila di kemudian hari pernyataan ini tidak benar.<br/><br/>
    Demikian Surat Pernyataan ini dibuat dengan sebenar-benarnya untuk dipergunakan sebagaimana mestinya."""
    elements.append(Paragraph(body, normal_style))
    elements.append(Spacer(1, 6*rl_mm))

    # Lampiran rincian
    if tidak_ditemukan:
        elements.append(Paragraph("<b>Lampiran: Rincian BMN Tidak Ditemukan</b>", st['Heading']))
        detail_data = [['No', 'Kode Barang', 'NUP', 'Nama BMN', 'Nilai (Rp)']]
        for i, a in enumerate(tidak_ditemukan):
            detail_data.append([
                str(i+1), a.get('asset_code', '-'), str(a.get('NUP', '-')),
                Paragraph(a.get('asset_name', '-'), cell_style), fmt_rp(safe_price(a))
            ])
        detail_data.append(['', '', '', Paragraph('<b>TOTAL</b>', cell_style), fmt_rp(total_val_notfound)])
        dt = Table(detail_data, colWidths=_fit_col_widths([30, 80, 35, 190, 90], doc.width), repeatRows=1)
        dt.setStyle(_std_table_style(zebra=True, total_row=True, extra=[
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ]))
        elements.append(dt)

    elements.append(Spacer(1, 10*rl_mm))

    # Signature
    tgl = str(activity.get("tanggal_berita_acara") or "").strip() or "......................."
    elements.extend(_signature_block([
        {'pre': [f'Dibuat di: {alamat_singkat}', f'Pada tanggal: {tgl}'],
         'header': 'Yang membuat pernyataan,',
         'nama': kasatker,
         'after': [f'NIP. {nip}']},
    ], doc.width))

    footer = _page_footer_factory("Surat Pernyataan Tanggung Jawab Mutlak (SPTJM)")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=SPTJM_{activity_id[:8]}.pdf"}
    )


# ============================================================================
# SURAT KOREKSI PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/surat-koreksi-pdf")
async def generate_surat_koreksi_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate Surat Pernyataan Koreksi Pencatatan PDF"""
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)
    koreksi_assets = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan" and a.get("klasifikasi_tidak_ditemukan") == "Kesalahan Pencatatan"]

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0

    def fmt_rp(val):
        try: return f"Rp {int(val):,}".replace(",", ".")
        except: return "Rp 0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    cell_style = st['Cell']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    ident = _activity_identity(activity, settings)
    kasatker = ident["kasatker_nama"]
    nip = ident["kasatker_nip"]
    jabatan = ident["kasatker_jabatan"]
    alamat = ident["alamat"]
    alamat_singkat = alamat.splitlines()[0] if alamat.splitlines() else alamat
    total_koreksi = len(koreksi_assets)
    total_val = sum(safe_price(a) for a in koreksi_assets)

    # Header
    elements.extend(_title_block("SURAT PERNYATAAN\nKOREKSI PENCATATAN BARANG MILIK NEGARA"))

    # Body
    elements.append(Paragraph("Yang bertanda tangan di bawah ini:", normal_style))
    elements.append(Spacer(1, 2*rl_mm))
    elements.append(_identity_table([
        ("Nama", kasatker),
        ("NIP", nip),
        ("Jabatan", jabatan),
        ("Alamat", alamat),
    ]))
    elements.append(Spacer(1, 3*rl_mm))
    body = f"""Dengan ini menyatakan bahwa berdasarkan hasil inventarisasi pada kegiatan
    "<b>{activity.get('nama_kegiatan', '-')}</b>" (Nomor Surat: {activity.get('nomor_surat', '-')}),
    terdapat <b>{total_koreksi}</b> NUP BMN dengan total nilai <b>{fmt_rp(total_val)}</b>
    yang teridentifikasi sebagai kesalahan pencatatan dan memerlukan koreksi.<br/><br/>
    Koreksi pencatatan tersebut meliputi perubahan data BMN pada aplikasi SIMAK-BMN
    sesuai dengan hasil penelitian Tim Internal."""
    elements.append(Paragraph(body, normal_style))
    elements.append(Spacer(1, 4*rl_mm))

    # Rincian
    if koreksi_assets:
        elements.append(Paragraph("<b>Rincian BMN yang Memerlukan Koreksi Pencatatan:</b>", st['Heading']))
        detail_data = [['No', 'Kode Barang', 'NUP', 'Nama BMN', 'Jenis Koreksi', 'Uraian', 'Nilai (Rp)']]
        for i, a in enumerate(koreksi_assets):
            detail_data.append([
                str(i+1), a.get('asset_code', '-'), str(a.get('NUP', '-')),
                Paragraph(a.get('asset_name', '-'), cell_style),
                Paragraph(a.get('sub_klasifikasi', '-'), cell_style),
                Paragraph(a.get('uraian_tidak_ditemukan', '-'), cell_style),
                fmt_rp(safe_price(a))
            ])
        detail_data.append(['', '', '', '', '', Paragraph('<b>TOTAL</b>', cell_style), fmt_rp(total_val)])
        dt = Table(detail_data, colWidths=_fit_col_widths([22, 60, 28, 80, 70, 95, 60], doc.width), repeatRows=1)
        dt.setStyle(_std_table_style(zebra=True, total_row=True, extra=[
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ]))
        elements.append(dt)
    else:
        elements.append(Paragraph("Tidak ada BMN yang memerlukan koreksi pencatatan.", normal_style))

    elements.append(Spacer(1, 6*rl_mm))
    elements.append(Paragraph("Demikian Surat Pernyataan ini dibuat dengan sebenar-benarnya.", normal_style))
    elements.append(Spacer(1, 10*rl_mm))

    # Signature
    tgl = str(activity.get("tanggal_berita_acara") or "").strip() or "......................."
    elements.extend(_signature_block([
        {'pre': [f'Dibuat di: {alamat_singkat}', f'Pada tanggal: {tgl}'],
         'header': 'Yang membuat pernyataan,',
         'nama': kasatker,
         'after': [f'NIP. {nip}']},
    ], doc.width))

    footer = _page_footer_factory("Surat Pernyataan Koreksi Pencatatan Barang Milik Negara")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Surat_Koreksi_{activity_id[:8]}.pdf"}
    )


# ============================================================================
# DBHI PDF REPORTS (LKPP 85/2025)
# ============================================================================

DBHI_TYPES = {
    "kondisi-baik": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nKONDISI BAIK",
        "filter": lambda a: a.get("inventory_status") == "Ditemukan" and a.get("condition") == "Baik",
        "extra_cols": False,
    },
    "kondisi-rusak-ringan": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nKONDISI RUSAK RINGAN",
        "filter": lambda a: a.get("inventory_status") == "Ditemukan" and a.get("condition") == "Rusak Ringan",
        "extra_cols": False,
    },
    "kondisi-rusak-berat": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nKONDISI RUSAK BERAT",
        "filter": lambda a: a.get("inventory_status") == "Ditemukan" and a.get("condition") == "Rusak Berat",
        "extra_cols": False,
    },
    "berlebih": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nBMN BERLEBIH",
        "filter": lambda a: a.get("inventory_status") == "Berlebih",
        "extra_cols": "berlebih",
    },
    "tidak-ditemukan": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nBMN TIDAK DITEMUKAN",
        "filter": lambda a: a.get("inventory_status") == "Tidak Ditemukan",
        "extra_cols": "tidak_ditemukan",
    },
    "sengketa": {
        "title": "DAFTAR BARANG HASIL INVENTARISASI BMN\nBMN DALAM SENGKETA",
        "filter": lambda a: a.get("inventory_status") == "Sengketa",
        "extra_cols": "sengketa",
    },
}


@reports_router.get("/inventory-activities/{activity_id}/dbhi/{dbhi_type}")
async def generate_dbhi_pdf(activity_id: str, dbhi_type: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate DBHI (Daftar Barang Hasil Inventarisasi) PDF by type"""
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    if dbhi_type not in DBHI_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipe DBHI tidak valid. Pilih: {', '.join(DBHI_TYPES.keys())}")

    dbhi_config = DBHI_TYPES[dbhi_type]

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    all_assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)
    filtered = [a for a in all_assets if dbhi_config["filter"](a)]

    def safe_price(a):
        try:
            return float(a.get("purchase_price", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    def fmt_rp(val):
        try:
            return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError):
            return "0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    cell_style = st['Cell']
    cell_center = st['CellCenter']
    cell_right = st['CellRight']
    header_style = st['TableHeader']
    info_style = st['Meta']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    # Title
    elements.extend(_title_block(dbhi_config["title"]))

    # Activity info
    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    nomor_sk = activity.get("nomor_surat", "-")
    tgl = _fmt_tanggal_id(activity.get("tanggal_mulai")) or "-"
    elements.append(Paragraph(f"Satuan Kerja: {satker_name}", info_style))
    elements.append(Paragraph(f"Nomor SK: {nomor_sk} &nbsp;&nbsp;|&nbsp;&nbsp; Tanggal: {tgl}", info_style))
    elements.append(Spacer(1, 4*rl_mm))

    # Build table headers based on type
    extra = dbhi_config["extra_cols"]
    if extra == "berlebih":
        headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Tahun\nPerolehan", "Kondisi", "Nilai (Rp)", "Lokasi", "Keterangan\nBerlebih", "Asal Usul", "Tindak Lanjut"]
        col_widths = [22, 72, 28, 110, 42, 48, 62, 80, 90, 80, 80]
    elif extra == "tidak_ditemukan":
        headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Tahun\nPerolehan", "Nilai (Rp)", "Lokasi", "Klasifikasi", "Sub Klasifikasi", "Uraian", "Tindak Lanjut"]
        col_widths = [22, 72, 28, 100, 42, 62, 70, 70, 80, 80, 80]
    elif extra == "sengketa":
        headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Tahun\nPerolehan", "Kondisi", "Nilai (Rp)", "Lokasi", "No. Perkara", "Pihak\nBersengketa", "Keterangan\nSengketa"]
        col_widths = [22, 72, 28, 100, 42, 48, 62, 70, 70, 80, 80]
    else:
        headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Merk/Tipe", "Tahun\nPerolehan", "Nilai (Rp)", "Lokasi", "Keterangan"]
        col_widths = [25, 80, 30, 130, 80, 45, 72, 110, 110]

    header_row = [Paragraph(h.replace("\n", "<br/>"), header_style) for h in headers]
    table_data = [header_row]

    total_nilai = 0
    for idx, asset in enumerate(filtered, 1):
        val = safe_price(asset)
        total_nilai += val
        year = str(asset.get("purchase_date", ""))[:4] if asset.get("purchase_date") else "-"

        if extra == "berlebih":
            row = [
                Paragraph(str(idx), cell_center),
                Paragraph(str(asset.get("asset_code", "-")), cell_style),
                Paragraph(str(asset.get("NUP", "-")), cell_center),
                Paragraph(str(asset.get("asset_name", "-")), cell_style),
                Paragraph(year, cell_center),
                Paragraph(str(asset.get("condition", "-")), cell_center),
                Paragraph(fmt_rp(val), cell_right),
                Paragraph(str(asset.get("location", "-")), cell_style),
                Paragraph(str(asset.get("keterangan_berlebih", "-")), cell_style),
                Paragraph(str(asset.get("asal_usul_berlebih", "-")), cell_style),
                Paragraph(str(asset.get("tindak_lanjut", "-")), cell_style),
            ]
        elif extra == "tidak_ditemukan":
            row = [
                Paragraph(str(idx), cell_center),
                Paragraph(str(asset.get("asset_code", "-")), cell_style),
                Paragraph(str(asset.get("NUP", "-")), cell_center),
                Paragraph(str(asset.get("asset_name", "-")), cell_style),
                Paragraph(year, cell_center),
                Paragraph(fmt_rp(val), cell_right),
                Paragraph(str(asset.get("location", "-")), cell_style),
                Paragraph(str(asset.get("klasifikasi_tidak_ditemukan", "-")), cell_style),
                Paragraph(str(asset.get("sub_klasifikasi", "-")), cell_style),
                Paragraph(str(asset.get("uraian_tidak_ditemukan", "-")), cell_style),
                Paragraph(str(asset.get("tindak_lanjut", "-")), cell_style),
            ]
        elif extra == "sengketa":
            row = [
                Paragraph(str(idx), cell_center),
                Paragraph(str(asset.get("asset_code", "-")), cell_style),
                Paragraph(str(asset.get("NUP", "-")), cell_center),
                Paragraph(str(asset.get("asset_name", "-")), cell_style),
                Paragraph(year, cell_center),
                Paragraph(str(asset.get("condition", "-")), cell_center),
                Paragraph(fmt_rp(val), cell_right),
                Paragraph(str(asset.get("location", "-")), cell_style),
                Paragraph(str(asset.get("nomor_perkara", "-")), cell_style),
                Paragraph(str(asset.get("pihak_bersengketa", "-")), cell_style),
                Paragraph(str(asset.get("keterangan_sengketa", "-")), cell_style),
            ]
        else:
            row = [
                Paragraph(str(idx), cell_center),
                Paragraph(str(asset.get("asset_code", "-")), cell_style),
                Paragraph(str(asset.get("NUP", "-")), cell_center),
                Paragraph(str(asset.get("asset_name", "-")), cell_style),
                Paragraph(f"{asset.get('brand', '')} {asset.get('model', '')}".strip() or "-", cell_style),
                Paragraph(year, cell_center),
                Paragraph(fmt_rp(val), cell_right),
                Paragraph(str(asset.get("location", "-")), cell_style),
                Paragraph(str(asset.get("notes", "-")), cell_style),
            ]
        table_data.append(row)

    # Total row
    if extra == "berlebih":
        total_row = [Paragraph("", cell_style)] * 6 + [Paragraph(f"<b>{fmt_rp(total_nilai)}</b>", cell_right)] + [Paragraph("", cell_style)] * 4
    elif extra == "tidak_ditemukan":
        total_row = [Paragraph("", cell_style)] * 5 + [Paragraph(f"<b>{fmt_rp(total_nilai)}</b>", cell_right)] + [Paragraph("", cell_style)] * 5
    elif extra == "sengketa":
        total_row = [Paragraph("", cell_style)] * 6 + [Paragraph(f"<b>{fmt_rp(total_nilai)}</b>", cell_right)] + [Paragraph("", cell_style)] * 4
    else:
        total_row = [Paragraph("", cell_style)] * 6 + [Paragraph(f"<b>{fmt_rp(total_nilai)}</b>", cell_right)] + [Paragraph("", cell_style)] * 2

    total_row[0] = Paragraph(f"<b>Total: {len(filtered)} item</b>", cell_style)
    table_data.append(total_row)

    # Kolom nilai pada baris total (label "Total" di-span hingga sebelum kolom nilai)
    val_col = 5 if extra == "tidak_ditemukan" else 6
    table = Table(table_data, colWidths=_fit_col_widths(col_widths, doc.width), repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True, extra=[
        ('SPAN', (0, -1), (val_col - 1, -1)),
    ]))
    elements.append(table)

    # Signature section
    elements.append(Spacer(1, 12*rl_mm))
    kasatker_nama = ident["kasatker_nama"]
    kasatker_nip = ident["kasatker_nip"]

    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': kasatker_nama,
         'after': [f'NIP. {kasatker_nip}']},
    ], doc.width))

    footer = _page_footer_factory(dbhi_config["title"].replace("\n", " - "))
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)

    filename = f"DBHI_{dbhi_type}_{activity_id[:8]}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============================================================================
# RHI PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/rhi-pdf")
async def generate_rhi_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate RHI (Rekapitulasi Hasil Inventarisasi BMN) PDF"""
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0.0

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except: return "0"

    total_all = assets
    ditemukan = [a for a in assets if a.get("inventory_status") == "Ditemukan"]
    tidak_ditemukan = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan"]
    berlebih = [a for a in assets if a.get("inventory_status") == "Berlebih"]
    sengketa = [a for a in assets if a.get("inventory_status") == "Sengketa"]
    belum = [a for a in assets if (a.get("inventory_status") or "Belum Diinventarisasi") == "Belum Diinventarisasi"]

    baik = [a for a in ditemukan if a.get("condition") == "Baik"]
    rusak_ringan = [a for a in ditemukan if a.get("condition") == "Rusak Ringan"]
    rusak_berat = [a for a in ditemukan if a.get("condition") == "Rusak Berat"]

    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    info_style = st['Meta']
    cell_style = st['Cell']
    cell_center = st['CellCenter']
    cell_right = st['CellRight']
    header_style = st['TableHeader']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("REKAPITULASI HASIL INVENTARISASI\nBARANG MILIK NEGARA (RHI)"))

    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    elements.append(Paragraph(f"Satuan Kerja: {satker_name}", info_style))
    elements.append(Paragraph(f"Nomor SK: {activity.get('nomor_surat') or '-'} | Periode: {_fmt_tanggal_id(activity.get('tanggal_mulai')) or '-'} s.d. {_fmt_tanggal_id(activity.get('tanggal_selesai')) or '-'}", info_style))
    elements.append(Spacer(1, 4*rl_mm))

    headers = ["No", "Kategori Hasil Inventarisasi", "Jumlah\n(NUP)", "Nilai (Rp)", "Persentase"]
    header_row = [Paragraph(h.replace("\n", "<br/>"), header_style) for h in headers]

    rows_data = [
        ("A", "BMN DITEMUKAN", len(ditemukan), sum(safe_price(a) for a in ditemukan)),
        ("  1", "   Kondisi Baik", len(baik), sum(safe_price(a) for a in baik)),
        ("  2", "   Kondisi Rusak Ringan", len(rusak_ringan), sum(safe_price(a) for a in rusak_ringan)),
        ("  3", "   Kondisi Rusak Berat", len(rusak_berat), sum(safe_price(a) for a in rusak_berat)),
        ("B", "BMN TIDAK DITEMUKAN", len(tidak_ditemukan), sum(safe_price(a) for a in tidak_ditemukan)),
        ("C", "BMN BERLEBIH", len(berlebih), sum(safe_price(a) for a in berlebih)),
        ("D", "BMN DALAM SENGKETA", len(sengketa), sum(safe_price(a) for a in sengketa)),
        ("E", "BELUM DIINVENTARISASI", len(belum), sum(safe_price(a) for a in belum)),
    ]

    total_count = len(total_all)
    total_value = sum(safe_price(a) for a in total_all)
    main_categories = {"A", "B", "C", "D", "E"}

    table_data = [header_row]
    for no, label, count, value in rows_data:
        pct = f"{(count/total_count*100):.1f}%" if total_count > 0 else "0%"
        is_main = no.strip() in main_categories
        style_l = st['CellBold'] if is_main else cell_style
        style_r = st['CellBoldRight'] if is_main else cell_right
        style_c = st['CellBoldCenter'] if is_main else cell_center
        table_data.append([
            Paragraph(str(no), style_c),
            Paragraph(label, style_l),
            Paragraph(str(count), style_c),
            Paragraph(fmt_rp(value), style_r),
            Paragraph(pct, style_c),
        ])

    pct_total = "100%" if total_count > 0 else "0%"
    table_data.append([
        Paragraph("", cell_center),
        Paragraph("<b>TOTAL BMN DITELITI</b>", cell_style),
        Paragraph(f"<b>{total_count}</b>", cell_center),
        Paragraph(f"<b>{fmt_rp(total_value)}</b>", cell_right),
        Paragraph(f"<b>{pct_total}</b>", cell_center),
    ])

    col_widths = _fit_col_widths([35, 280, 65, 120, 65], doc.width)
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    # Signature
    elements.append(Spacer(1, 12*rl_mm))
    kasatker_nama = ident["kasatker_nama"]
    kasatker_nip = ident["kasatker_nip"]
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': kasatker_nama,
         'after': [f'NIP. {kasatker_nip}']},
    ], doc.width))

    footer = _page_footer_factory("Rekapitulasi Hasil Inventarisasi Barang Milik Negara (RHI)")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="RHI_{activity_id[:8]}.pdf"'})


# ============================================================================
# DBKP PDF — Daftar Barang Kuasa Pengguna (modul Pembukuan, PMK 181/2016)
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/dbkp-pdf")
async def generate_dbkp_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """DBKP per golongan barang — pisah intra/ekstrakomptabel.

    Langkah pertama modul Pembukuan (pustaka §2.1): rekap barang per
    GOLONGAN (digit pertama kode) dengan pemilahan INTRAKOMPTABEL vs
    EKSTRAKOMPTABEL menurut ambang kapitalisasi PMK 181 (peralatan &
    mesin ≥ Rp1 jt; gedung & bangunan ≥ Rp25 jt; golongan lain selalu
    intra). Uraian golongan diambil dari referensi kodefikasi (fallback
    daftar golongan standar).
    """
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import AMBANG_KAPITALISASI_DEFAULT, build_dbkp_rows

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # Kecualikan aset yang sudah DIHAPUS (SK penghapusan, #234) agar DBKP tidak
    # double-count nilai BMN yang tak lagi dimiliki (§5A Prinsip 3).
    assets = await db.assets.find(
        active_asset_filter({"activity_id": activity_id}),
        {"_id": 0, "asset_code": 1, "purchase_price": 1},
    ).to_list(100000)

    # Uraian golongan: referensi kodefikasi (level 1) menimpa default standar
    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]

    rows, total = build_dbkp_rows(assets, uraian_map)

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError, OverflowError): return "0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    cell_style = st['Cell']
    cell_center = st['CellCenter']
    cell_right = st['CellRight']
    header_style = st['TableHeader']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("DAFTAR BARANG KUASA PENGGUNA (DBKP)\nPER GOLONGAN BARANG"))

    ident = _activity_identity(activity, settings)
    elements.append(Paragraph(f"Satuan Kerja: {ident['satker_name']}", st['Meta']))
    elements.append(Paragraph(
        f"Kegiatan: {activity.get('nama_kegiatan') or '-'} | Periode: {_fmt_tanggal_id(activity.get('tanggal_mulai')) or '-'} s.d. {_fmt_tanggal_id(activity.get('tanggal_selesai')) or '-'}",
        st['Meta']))
    elements.append(Spacer(1, 4*rl_mm))

    headers = ["Gol.", "Uraian Golongan",
               "Jml\nIntra", "Nilai Intra\n(Rp)",
               "Jml\nEkstra", "Nilai Ekstra\n(Rp)",
               "Jml\nTotal", "Nilai Total\n(Rp)"]
    table_data = [[Paragraph(h.replace("\n", "<br/>"), header_style) for h in headers]]
    for r in rows:
        table_data.append([
            Paragraph(r["golongan"], cell_center),
            Paragraph(r["uraian"], cell_style),
            Paragraph(str(r["jumlah_intra"]), cell_center),
            Paragraph(fmt_rp(r["nilai_intra"]), cell_right),
            Paragraph(str(r["jumlah_ekstra"]), cell_center),
            Paragraph(fmt_rp(r["nilai_ekstra"]), cell_right),
            Paragraph(str(r["jumlah_total"]), cell_center),
            Paragraph(fmt_rp(r["nilai_total"]), cell_right),
        ])
    table_data.append([
        Paragraph("", cell_center),
        Paragraph("<b>JUMLAH</b>", cell_style),
        Paragraph(f"<b>{total['jumlah_intra']}</b>", cell_center),
        Paragraph(f"<b>{fmt_rp(total['nilai_intra'])}</b>", cell_right),
        Paragraph(f"<b>{total['jumlah_ekstra']}</b>", cell_center),
        Paragraph(f"<b>{fmt_rp(total['nilai_ekstra'])}</b>", cell_right),
        Paragraph(f"<b>{total['jumlah_total']}</b>", cell_center),
        Paragraph(f"<b>{fmt_rp(total['nilai_total'])}</b>", cell_right),
    ])

    col_widths = _fit_col_widths([32, 180, 62, 100, 62, 100, 62, 100], doc.width)
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    ambang_pm = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("3", 0))
    ambang_gb = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("4", 0))
    elements.append(Spacer(1, 3*rl_mm))
    elements.append(Paragraph(
        f"Catatan: pemilahan intrakomptabel/ekstrakomptabel mengikuti nilai satuan minimum kapitalisasi "
        f"(PMK 181/PMK.06/2016): Peralatan dan Mesin ≥ Rp{ambang_pm}; Gedung dan Bangunan ≥ Rp{ambang_gb}; "
        f"golongan lainnya dibukukan intrakomptabel tanpa ambang.", st['Meta']))

    elements.append(Spacer(1, 12*rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': ident["kasatker_nama"],
         'after': [f'NIP. {ident["kasatker_nip"]}']},
    ], doc.width))

    footer = _page_footer_factory("Daftar Barang Kuasa Pengguna (DBKP) per Golongan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="DBKP_{activity_id[:8]}.pdf"'})


@reports_router.get("/pembukuan/posisi-bmn-pdf")
async def generate_posisi_bmn_pdf(_user: dict = Depends(require_user_or_query_token)):
    """Laporan Posisi BMN di Neraca — komponen LBKP (pustaka §2.3).

    Rekap SELURUH aset satker (lintas kegiatan) per golongan dengan
    pemilahan intra/ekstrakomptabel (ambang PMK 181) + baris Persediaan
    (aset lancar, nilai FIFO per layer). Posisi lengkap (KDP, ATB,
    penyusutan) menyusul sesuai masterplan.
    """
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import (
        AMBANG_KAPITALISASI_DEFAULT, build_dbkp_rows, posisi_neraca,
    )
    from persediaan_utils import nilai_persediaan_dari_batches

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # Posisi BMN di Neraca: hanya aset yang MASIH dimiliki — aset ber-SK
    # penghapusan (#234) dikecualikan agar nilai neraca tidak lebih saji (§5A).
    assets = await db.assets.find(
        active_asset_filter(), {"_id": 0, "asset_code": 1, "purchase_price": 1},
    ).to_list(500000)

    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]

    rows, total_aset = build_dbkp_rows(assets, uraian_map)
    p_jumlah, p_nilai = 0, 0.0
    async for it in db.persediaan.find({}, {"_id": 0, "batches": 1}):
        p_jumlah += 1
        p_nilai += nilai_persediaan_dari_batches(it.get("batches"))
    posisi = posisi_neraca(rows, total_aset, p_jumlah, p_nilai)

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError, OverflowError): return "0"

    today_iso = datetime.now(timezone.utc).date().isoformat()
    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN POSISI BARANG MILIK NEGARA DI NERACA",
                                 subjudul=f"Posisi per {_fmt_tanggal_id(today_iso)}"))
    elements.append(Paragraph(
        f"Seluruh aset satker lintas kegiatan ({posisi['total_aset']['jumlah_total']} NUP aset tetap"
        f" + {posisi['persediaan']['jumlah']} jenis persediaan) · nilai perolehan; penyusutan menyusul",
        st['Meta']))
    elements.append(Spacer(1, 4*rl_mm))

    headers = ["Gol.", "Uraian",
               "Jml\nIntra", "Nilai Intra\n(Rp)",
               "Jml\nEkstra", "Nilai Ekstra\n(Rp)",
               "Jml\nTotal", "Nilai Total\n(Rp)"]
    table_data = [[Paragraph(h.replace("\n", "<br/>"), st['TableHeader']) for h in headers]]
    for r in posisi["aset"]:
        table_data.append([
            Paragraph(r["golongan"], st['CellCenter']),
            Paragraph(r["uraian"], st['Cell']),
            Paragraph(str(r["jumlah_intra"]), st['CellCenter']),
            Paragraph(fmt_rp(r["nilai_intra"]), st['CellRight']),
            Paragraph(str(r["jumlah_ekstra"]), st['CellCenter']),
            Paragraph(fmt_rp(r["nilai_ekstra"]), st['CellRight']),
            Paragraph(str(r["jumlah_total"]), st['CellCenter']),
            Paragraph(fmt_rp(r["nilai_total"]), st['CellRight']),
        ])
    p = posisi["persediaan"]
    table_data.append([
        Paragraph("1", st['CellCenter']),
        Paragraph("Persediaan (aset lancar — nilai FIFO per layer)", st['Cell']),
        Paragraph(str(p["jumlah"]), st['CellCenter']),
        Paragraph(fmt_rp(p["nilai"]), st['CellRight']),
        Paragraph("0", st['CellCenter']),
        Paragraph("0", st['CellRight']),
        Paragraph(str(p["jumlah"]), st['CellCenter']),
        Paragraph(fmt_rp(p["nilai"]), st['CellRight']),
    ])
    g = posisi["total"]
    table_data.append([
        Paragraph("", st['CellCenter']),
        Paragraph("<b>TOTAL POSISI BMN</b>", st['Cell']),
        Paragraph(f"<b>{g['jumlah_intra']}</b>", st['CellCenter']),
        Paragraph(f"<b>{fmt_rp(g['nilai_intra'])}</b>", st['CellRight']),
        Paragraph(f"<b>{g['jumlah_ekstra']}</b>", st['CellCenter']),
        Paragraph(f"<b>{fmt_rp(g['nilai_ekstra'])}</b>", st['CellRight']),
        Paragraph(f"<b>{g['jumlah_total']}</b>", st['CellCenter']),
        Paragraph(f"<b>{fmt_rp(g['nilai_total'])}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([32, 180, 62, 100, 62, 100, 62, 100], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    ambang_pm = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("3", 0))
    ambang_gb = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("4", 0))
    elements.append(Spacer(1, 3*rl_mm))
    elements.append(Paragraph(
        "Catatan: hanya barang intrakomptabel yang tersaji di neraca; pemilahan mengikuti nilai satuan "
        f"minimum kapitalisasi PMK 181/PMK.06/2016 (Peralatan dan Mesin ≥ Rp{ambang_pm}; Gedung dan "
        f"Bangunan ≥ Rp{ambang_gb}; golongan lain tanpa ambang). Jumlah persediaan dihitung per jenis "
        "barang; komponen KDP, ATB, dan penyusutan menyusul bertahap.", st['Meta']))

    elements.append(Spacer(1, 12*rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))

    footer = _page_footer_factory("Laporan Posisi BMN di Neraca")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="Posisi_BMN_Neraca.pdf"'})


@reports_router.get("/pembukuan/lbkp-pdf")
async def generate_lbkp_pdf(
    tahun: int = Query(..., ge=2000, le=2100),
    semester: int = Query(None, ge=1, le=2),
    _user: dict = Depends(require_user_or_query_token),
):
    """LBKP per golongan — saldo awal + mutasi + saldo akhir (pustaka §2.3).

    Tiga seksi: Intrakomptabel, Ekstrakomptabel, Gabungan. Mutasi tambah
    dari tanggal pencatatan aset; mutasi kurang dari jejak audit
    penghapusan (nilai terekam sejak #94 — penghapusan lama dihitung
    jumlahnya, nilai 0, dan diungkap di catatan). Tidak pernah memuat
    data dummy: keterbatasan data historis dicantumkan eksplisit.
    """
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pelaporan_utils import kunci_unik_periode, penanda_final
    from pembukuan_utils import build_lbkp_rows, parse_harga
    from pemeliharaan_utils import rentang_periode

    dari, sampai, label_periode = rentang_periode(tahun, semester)
    periode_rec = await db.periode_pelaporan.find_one(
        {"kunci_unik": kunci_unik_periode(tahun, semester)}, {"_id": 0})
    sufiks_final = penanda_final(periode_rec)
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    assets = await db.assets.find(
        {}, {"_id": 0, "asset_code": 1, "purchase_price": 1, "created_at": 1},
    ).to_list(500000)
    tombstones = []
    async for t in db.audit_logs.find(
            {"action": "delete"},
            {"_id": 0, "asset_code": 1, "timestamp": 1, "changes": 1}):
        nilai = 0.0
        for c in t.get("changes") or []:
            if c.get("field") == "purchase_price":
                nilai = parse_harga(c.get("from"))
                break
        tombstones.append({"asset_code": t.get("asset_code"),
                           "timestamp": t.get("timestamp"), "nilai": nilai})

    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]

    per_kelas, n_tanpa_nilai = build_lbkp_rows(assets, tombstones, dari, sampai, uraian_map)
    if not per_kelas["gabungan"][0]:
        raise HTTPException(status_code=404,
                            detail=f"Belum ada data aset untuk {label_periode}")

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError, OverflowError): return "0"

    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN BARANG KUASA PENGGUNA (LBKP)\nPER GOLONGAN BARANG",
                                 subjudul=label_periode + sufiks_final))
    elements.append(Paragraph(
        f"Periode {_fmt_tanggal_id(dari)} s.d. {_fmt_tanggal_id(sampai)} · saldo akhir = "
        "saldo awal + mutasi tambah − mutasi kurang", st['Meta']))
    elements.append(Spacer(1, 3 * rl_mm))

    headers = ["Gol", "Uraian Golongan",
               "Awal\nJml", "Saldo Awal\n(Rp)",
               "Tambah\nJml", "Mutasi Tambah\n(Rp)",
               "Kurang\nJml", "Mutasi Kurang\n(Rp)",
               "Akhir\nJml", "Saldo Akhir\n(Rp)"]
    col_widths = _fit_col_widths([24, 128, 36, 86, 36, 86, 36, 86, 36, 86], doc.width)
    LABEL_KELAS = [("intra", "I. INTRAKOMPTABEL (tersaji di neraca)"),
                   ("ekstra", "II. EKSTRAKOMPTABEL (di bawah ambang kapitalisasi)"),
                   ("gabungan", "III. GABUNGAN")]
    for kunci, label in LABEL_KELAS:
        rows, total = per_kelas[kunci]
        elements.append(Paragraph(f"<b>{label}</b>", st['Meta']))
        elements.append(Spacer(1, 1.5 * rl_mm))
        table_data = [[Paragraph(h.replace("\n", "<br/>"), st['TableHeader']) for h in headers]]
        for r in rows:
            table_data.append([
                Paragraph(r["golongan"], st['CellCenter']),
                Paragraph(r["uraian"], st['Cell']),
                Paragraph(str(r["jumlah_awal"]), st['CellCenter']),
                Paragraph(fmt_rp(r["nilai_awal"]), st['CellRight']),
                Paragraph(str(r["jumlah_tambah"]), st['CellCenter']),
                Paragraph(fmt_rp(r["nilai_tambah"]), st['CellRight']),
                Paragraph(str(r["jumlah_kurang"]), st['CellCenter']),
                Paragraph(fmt_rp(r["nilai_kurang"]), st['CellRight']),
                Paragraph(str(r["jumlah_akhir"]), st['CellCenter']),
                Paragraph(fmt_rp(r["nilai_akhir"]), st['CellRight']),
            ])
        if not rows:
            table_data.append([Paragraph("—", st['CellCenter'])] +
                              [Paragraph("nihil", st['Cell'])] +
                              [Paragraph("0", st['CellCenter']) for _ in range(8)])
        table_data.append([
            Paragraph("", st['CellCenter']),
            Paragraph("<b>JUMLAH</b>", st['Cell']),
            Paragraph(f"<b>{total['jumlah_awal']}</b>", st['CellCenter']),
            Paragraph(f"<b>{fmt_rp(total['nilai_awal'])}</b>", st['CellRight']),
            Paragraph(f"<b>{total['jumlah_tambah']}</b>", st['CellCenter']),
            Paragraph(f"<b>{fmt_rp(total['nilai_tambah'])}</b>", st['CellRight']),
            Paragraph(f"<b>{total['jumlah_kurang']}</b>", st['CellCenter']),
            Paragraph(f"<b>{fmt_rp(total['nilai_kurang'])}</b>", st['CellRight']),
            Paragraph(f"<b>{total['jumlah_akhir']}</b>", st['CellCenter']),
            Paragraph(f"<b>{fmt_rp(total['nilai_akhir'])}</b>", st['CellRight']),
        ])
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(_std_table_style(zebra=True, total_row=True))
        elements.append(table)
        elements.append(Spacer(1, 4 * rl_mm))

    catatan = ("Catatan: mutasi tambah dihitung dari tanggal pencatatan aset; mutasi kurang dari "
               "jejak audit penghapusan. Aset yang dibuat dan dihapus sebelum awal periode tidak "
               "dapat direkonstruksi dari jejak yang ada. Komponen persediaan/KDP/ATB/penyusutan "
               "LBKP menyusul bertahap.")
    if n_tanpa_nilai:
        catatan += (f" Terdapat {n_tanpa_nilai} penghapusan pada periode ini yang nilai "
                    "perolehannya belum terekam (audit lama) — dihitung jumlahnya dengan nilai 0.")
    elements.append(Paragraph(catatan, st['Meta']))

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("LBKP per Golongan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    suffix = f"_S{semester}" if semester else ""
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="LBKP_{tahun}{suffix}.pdf"'})


@reports_router.get("/pembukuan/lkb-pdf")
async def generate_lkb_pdf(_user: dict = Depends(require_user_or_query_token)):
    """Laporan Kondisi Barang — lampiran LBKP tahunan (pustaka §2.3b).

    Mengikuti format LKBT-PKPB1: rincian per NUP (kode, nama, NUP,
    kuantitas, kondisi, harga perolehan) dikelompokkan per golongan +
    ringkasan B/RR/RB per golongan. Kolom Satuan belum dicatat AMAN dan
    tidak difabrikasi; kondisi kosong tampil "(belum dicatat)".
    """
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import KONDISI_LKB, build_lkb_rows, parse_harga

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    assets = await db.assets.find(
        {}, {"_id": 0, "asset_code": 1, "NUP": 1, "asset_name": 1,
             "condition": 1, "purchase_price": 1},
    ).to_list(500000)
    if not assets:
        raise HTTPException(status_code=404, detail="Belum ada data aset")

    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]
    rekap_rows, rekap_total = build_lkb_rows(assets, uraian_map)

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError, OverflowError): return "0"

    today_iso = datetime.now(timezone.utc).date().isoformat()
    _BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    per_label = f"{_BULAN_ID[int(today_iso[5:7])]} {today_iso[:4]}".upper()

    buffer = io.BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        f"LAPORAN KONDISI BARANG\nPER {per_label} — SEMUA KONDISI",
        subjudul="Lampiran LBKP Tahunan (PMK 181/PMK.06/2016)"))
    elements.append(Paragraph(
        "Ringkasan kondisi per golongan (kuantitas per kategori resmi "
        "Baik / Rusak Ringan / Rusak Berat):", st['Meta']))
    elements.append(Spacer(1, 1.5 * rl_mm))

    headers = ["Gol", "Uraian Golongan", "Baik", "Rusak\nRingan",
               "Rusak\nBerat", "Belum\nDicatat", "Jumlah", "Nilai Perolehan (Rp)"]
    table_data = [[Paragraph(h.replace("\n", "<br/>"), st['TableHeader']) for h in headers]]
    for r in rekap_rows:
        table_data.append([
            Paragraph(r["golongan"], st['CellCenter']),
            Paragraph(r["uraian"], st['Cell']),
            Paragraph(str(r["baik"]), st['CellCenter']),
            Paragraph(str(r["rusak_ringan"]), st['CellCenter']),
            Paragraph(str(r["rusak_berat"]), st['CellCenter']),
            Paragraph(str(r["belum"]), st['CellCenter']),
            Paragraph(str(r["jumlah"]), st['CellCenter']),
            Paragraph(fmt_rp(r["nilai"]), st['CellRight']),
        ])
    table_data.append([
        Paragraph("", st['CellCenter']),
        Paragraph("<b>JUMLAH</b>", st['Cell']),
        Paragraph(f"<b>{rekap_total['baik']}</b>", st['CellCenter']),
        Paragraph(f"<b>{rekap_total['rusak_ringan']}</b>", st['CellCenter']),
        Paragraph(f"<b>{rekap_total['rusak_berat']}</b>", st['CellCenter']),
        Paragraph(f"<b>{rekap_total['belum']}</b>", st['CellCenter']),
        Paragraph(f"<b>{rekap_total['jumlah']}</b>", st['CellCenter']),
        Paragraph(f"<b>{fmt_rp(rekap_total['nilai'])}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([28, 210, 54, 54, 54, 54, 54, 120], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)
    elements.append(Spacer(1, 5 * rl_mm))

    # Rincian per NUP, dikelompokkan per golongan (format LKBT-PKPB1)
    per_gol = {}
    for a in assets:
        gol = str(a.get("asset_code") or "").strip()[:1]
        per_gol.setdefault(gol if gol.isdigit() else "?", []).append(a)
    headers = ["Kode Barang", "Nama Barang", "NUP", "Kuantitas",
               "Kondisi", "Harga Perolehan (Rp)"]
    for gol in sorted(per_gol, key=lambda g: (g == "?", g)):
        uraian = uraian_map.get(gol) or (
            "Tanpa Golongan (kode belum rapi)" if gol == "?" else f"Golongan {gol}")
        rincian = sorted(per_gol[gol],
                         key=lambda a: (str(a.get("asset_code") or ""),
                                        str(a.get("NUP") or "")))
        elements.append(Paragraph(f"<b>Golongan {gol} — {uraian}</b> · {len(rincian)} NUP",
                                  st['Meta']))
        elements.append(Spacer(1, 1.5 * rl_mm))
        table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for a in rincian:
            kondisi = str(a.get("condition") or "").strip()
            if kondisi not in KONDISI_LKB:
                kondisi = "(belum dicatat)"
            table_data.append([
                Paragraph(str(a.get("asset_code") or "-"), st['CellCenter']),
                Paragraph(str(a.get("asset_name") or "-"), st['Cell']),
                Paragraph(str(a.get("NUP") or "-"), st['CellCenter']),
                Paragraph("1", st['CellCenter']),
                Paragraph(kondisi, st['CellCenter']),
                Paragraph(fmt_rp(parse_harga(a.get("purchase_price"))),
                          st['CellRight']),
            ])
        table = Table(table_data,
                      colWidths=_fit_col_widths([96, 250, 44, 56, 90, 110], doc.width),
                      repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)
        elements.append(Spacer(1, 4 * rl_mm))

    elements.append(Paragraph(
        "Catatan: kategori kondisi resmi hanya Baik / Rusak Ringan / Rusak "
        "Berat (perubahan kondisi dicatat setelah pengecekan fisik); baris "
        "berkondisi \"(belum dicatat)\" perlu dimutakhirkan pada modul "
        "inventarisasi. Kuantitas per baris = 1 NUP; kolom satuan belum "
        "dicatat pada AMAN. Dokumen resmi LKB (LKBT-PKPB1) tetap dicetak "
        "dari SIMAK-BMN/SAKTI — laporan ini bahan sandingan/kerja.", st['Meta']))
    elements.append(Spacer(1, 10 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Penanggung Jawab UAKPB',
         'role': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("Laporan Kondisi Barang (LKB)")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="LKB_{today_iso[:7]}.pdf"'})


@reports_router.get("/pembukuan/calbmn-pdf")
async def generate_calbmn_pdf(
    tahun: int = Query(..., ge=2000, le=2100),
    semester: int = Query(None, ge=1, le=2),
    _user: dict = Depends(require_user_or_query_token),
):
    """CaLBMN pra-isi tingkat UAKPB (pustaka §2.3a — struktur I–V).

    Bab I–V terisi dari data register yang ada (LBKP #95, persediaan,
    PSP/pemanfaatan/pemindahtanganan/penghapusan/idle/sengketa, PNBP
    kontribusi #121). AMAN penyiap bahan — dokumen resmi tetap dari
    SAKTI; narasi difinalkan operator. Tanpa data dummy: keterbatasan
    data historis diungkap eksplisit.
    """
    from reportlab.platypus import Table, Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pelaporan_utils import kunci_unik_periode, penanda_final
    from pembukuan_utils import (
        AMBANG_KAPITALISASI_DEFAULT, build_lbkp_rows, parse_harga,
    )
    from pemeliharaan_utils import rentang_periode
    from pengamanan_utils import is_sengketa
    from persediaan_utils import nilai_persediaan_dari_batches

    dari, sampai, label_periode = rentang_periode(tahun, semester)
    periode_rec = await db.periode_pelaporan.find_one(
        {"kunci_unik": kunci_unik_periode(tahun, semester)}, {"_id": 0})
    sufiks_final = penanda_final(periode_rec)
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    assets = await db.assets.find(
        {}, {"_id": 0, "id": 1, "asset_code": 1, "purchase_price": 1,
             "created_at": 1, "inventory_status": 1, "nomor_perkara": 1,
             "pihak_bersengketa": 1},
    ).to_list(500000)
    tombstones = []
    async for t in db.audit_logs.find(
            {"action": "delete"},
            {"_id": 0, "asset_code": 1, "timestamp": 1, "changes": 1}):
        nilai = 0.0
        for c in t.get("changes") or []:
            if c.get("field") == "purchase_price":
                nilai = parse_harga(c.get("from"))
                break
        tombstones.append({"asset_code": t.get("asset_code"),
                           "timestamp": t.get("timestamp"), "nilai": nilai})

    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]

    per_kelas, n_tanpa_nilai = build_lbkp_rows(assets, tombstones, dari, sampai, uraian_map)
    if not per_kelas["gabungan"][0]:
        raise HTTPException(status_code=404,
                            detail=f"Belum ada data aset untuk {label_periode}")

    # Persediaan (posisi kini — keterbatasan diungkap di teks)
    p_jumlah, p_nilai = 0, 0.0
    async for it in db.persediaan.find({}, {"_id": 0, "batches": 1}):
        p_jumlah += 1
        p_nilai += nilai_persediaan_dari_batches(it.get("batches"))

    # Informasi BMN lainnya — hitungan register (kueri ringan)
    psp_aset = set()
    async for s in db.psp.find({}, {"_id": 0, "aset.asset_id": 1}):
        for a in s.get("aset") or []:
            if a.get("asset_id"):
                psp_aset.add(a["asset_id"])
    n_pemanfaatan = await db.pemanfaatan.count_documents({})
    pnbp_jumlah, pnbp_nilai = 0, 0.0
    async for p in db.pemanfaatan.find({}, {"_id": 0, "kontribusi": 1}):
        for k in p.get("kontribusi") or []:
            tgl = str(k.get("tanggal") or "")[:10]
            if dari <= tgl <= sampai:
                pnbp_jumlah += 1
                pnbp_nilai += float(k.get("jumlah") or 0)
    n_pt_proses = await db.pemindahtanganan.count_documents(
        {"status": {"$in": ["diusulkan", "disetujui", "dilaksanakan"]}})
    n_pt_selesai = await db.pemindahtanganan.count_documents({"status": "selesai"})
    n_hapus_proses = await db.usulan_penghapusan.count_documents(
        {"status": {"$in": ["diusulkan", "diproses"]}})
    n_hapus_sk = await db.usulan_penghapusan.count_documents({"status": "sk_terbit"})
    n_pemusnahan = await db.pemusnahan.count_documents({})
    n_idle_aktif = await db.bmn_idle.count_documents(
        {"status": {"$in": ["klarifikasi", "usul_serah"]}})
    n_idle_serah = await db.bmn_idle.count_documents({"status": "diserahkan"})
    n_sengketa = sum(1 for a in assets if is_sengketa(a))

    def fmt_rp(val):
        try: return f"{int(val):,}".replace(",", ".")
        except (ValueError, TypeError, OverflowError): return "0"

    ambang_pm = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("3", 0))
    ambang_gb = fmt_rp(AMBANG_KAPITALISASI_DEFAULT.get("4", 0))
    satker = settings.get("kop_line2") or settings.get("kop_line1") or "Satuan Kerja"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        "CATATAN ATAS LAPORAN\nBARANG MILIK NEGARA",
        subjudul=(f"Tingkat Kuasa Pengguna Barang — {label_periode}"
                  f"{sufiks_final} · Bahan Penyusunan (Pra-isi)")))

    def bab(judul):
        elements.append(Spacer(1, 3 * rl_mm))
        elements.append(Paragraph(f"<b>{judul}</b>", st['Meta']))
        elements.append(Spacer(1, 1 * rl_mm))

    bab("I. PENDAHULUAN")
    elements.append(Paragraph(
        f"Catatan atas Laporan Barang Milik Negara (CaLBMN) ini disusun oleh "
        f"{satker} selaku Unit Akuntansi Kuasa Pengguna Barang (UAKPB) untuk "
        f"periode {label_periode} ({_fmt_tanggal_id(dari)} s.d. "
        f"{_fmt_tanggal_id(sampai)}). Dasar hukum: UU 17/2003 tentang Keuangan "
        f"Negara; UU 1/2004 tentang Perbendaharaan Negara (Ps. 49 ayat (6) dan "
        f"Ps. 55 ayat (2)); PP 27/2014 jo. PP 28/2020 tentang Pengelolaan "
        f"BMN/D; dan PMK 181/PMK.06/2016 tentang Penatausahaan BMN.", st['Meta']))

    bab("II. KEBIJAKAN PENATAUSAHAAN BMN")
    elements.append(Paragraph(
        f"BMN dibukukan per golongan mengikuti kodefikasi barang. Pemilahan "
        f"intrakomptabel/ekstrakomptabel mengikuti nilai satuan minimum "
        f"kapitalisasi PMK 181/PMK.06/2016: Peralatan dan Mesin ≥ Rp{ambang_pm}; "
        f"Gedung dan Bangunan ≥ Rp{ambang_gb}; golongan lain dibukukan "
        f"intrakomptabel tanpa ambang. Penyusutan aset tetap mengikuti "
        f"PMK 1/PMK.06/2013 jo. PMK 65/PMK.06/2017 (garis lurus semesteran — "
        f"rekap tersedia pada halaman Penilaian); rekonsiliasi internal dengan "
        f"UAKPA dan eksternal dengan KPKNL dilakukan per semester.", st['Meta']))

    bab("III. PENDEKATAN PENYUSUNAN LAPORAN")
    elements.append(Paragraph(
        f"Angka pada dokumen ini dihasilkan aplikasi AMAN dari register "
        f"inventarisasi, persediaan, dan register siklus BMN satker sebagai "
        f"BAHAN penyusunan CaLBMN. Dokumen resmi tetap disusun melalui "
        f"SIMAK-BMN/SAKTI; narasi akhir difinalkan operator BMN. Mutasi tambah "
        f"dihitung dari tanggal pencatatan aset dan mutasi kurang dari jejak "
        f"audit penghapusan pada AMAN.", st['Meta']))

    bab("IV. RINGKASAN BMN (GABUNGAN INTRA + EKSTRAKOMPTABEL)")
    rows_gab, total_gab = per_kelas["gabungan"]
    headers = ["Gol", "Uraian Golongan", "Saldo Awal (Rp)",
               "Mutasi Tambah (Rp)", "Mutasi Kurang (Rp)", "Saldo Akhir (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for r in rows_gab:
        table_data.append([
            Paragraph(r["golongan"], st['CellCenter']),
            Paragraph(r["uraian"], st['Cell']),
            Paragraph(fmt_rp(r["nilai_awal"]), st['CellRight']),
            Paragraph(fmt_rp(r["nilai_tambah"]), st['CellRight']),
            Paragraph(fmt_rp(r["nilai_kurang"]), st['CellRight']),
            Paragraph(fmt_rp(r["nilai_akhir"]), st['CellRight']),
        ])
    table_data.append([
        Paragraph("", st['CellCenter']),
        Paragraph("<b>JUMLAH ASET TETAP</b>", st['Cell']),
        Paragraph(f"<b>{fmt_rp(total_gab['nilai_awal'])}</b>", st['CellRight']),
        Paragraph(f"<b>{fmt_rp(total_gab['nilai_tambah'])}</b>", st['CellRight']),
        Paragraph(f"<b>{fmt_rp(total_gab['nilai_kurang'])}</b>", st['CellRight']),
        Paragraph(f"<b>{fmt_rp(total_gab['nilai_akhir'])}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([26, 140, 74, 74, 74, 74], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)
    elements.append(Spacer(1, 2 * rl_mm))

    t_intra, t_ekstra = per_kelas["intra"][1], per_kelas["ekstra"][1]
    ringkas = [["Kelas", "Saldo Awal (Rp)", "Saldo Akhir (Rp)", "Jumlah NUP Akhir"]]
    ringkas_rows = [
        ("Intrakomptabel (tersaji di neraca)", t_intra),
        ("Ekstrakomptabel (di bawah ambang)", t_ekstra),
        ("Gabungan", total_gab),
    ]
    table_data = [[Paragraph(h, st['TableHeader']) for h in ringkas[0]]]
    for label, tot in ringkas_rows:
        table_data.append([
            Paragraph(label, st['Cell']),
            Paragraph(fmt_rp(tot['nilai_awal']), st['CellRight']),
            Paragraph(fmt_rp(tot['nilai_akhir']), st['CellRight']),
            Paragraph(str(tot['jumlah_akhir']), st['CellCenter']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([180, 90, 90, 80], doc.width))
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)
    elements.append(Spacer(1, 2 * rl_mm))
    catatan_iv = (
        f"Persediaan (aset lancar): {p_jumlah} jenis barang dengan nilai "
        f"posisi kini Rp{fmt_rp(p_nilai)} (FIFO per layer — nilai historis "
        f"per akhir periode menyusul dengan kunci periode). Mutasi kurang "
        f"aset yang jejak nilainya belum terekam dihitung jumlahnya dengan "
        f"nilai 0. Komponen KDP dan ATB belum dicatat pada AMAN.")
    if n_tanpa_nilai:
        catatan_iv += (f" Terdapat {n_tanpa_nilai} penghapusan periode ini "
                       f"tanpa nilai perolehan terekam.")
    elements.append(Paragraph(catatan_iv, st['Meta']))

    bab("V. INFORMASI BMN LAINNYA")
    butir = [
        f"Penetapan Status Penggunaan: {len(psp_aset)} aset tercakup SK "
        f"penetapan dari {len(assets)} aset terdaftar.",
        f"Pemanfaatan: {n_pemanfaatan} perjanjian tercatat; PNBP dari "
        f"kontribusi/setoran ber-NTPN periode ini: {pnbp_jumlah} setoran "
        f"senilai Rp{fmt_rp(pnbp_nilai)}.",
        f"Pemindahtanganan: {n_pt_proses} usulan dalam proses; "
        f"{n_pt_selesai} selesai (SK Penghapusan terbit).",
        f"Penghapusan: {n_hapus_proses} usulan aktif; {n_hapus_sk} SK "
        f"terbit; {n_pemusnahan} Berita Acara Pemusnahan tercatat.",
        f"BMN idle: {n_idle_aktif} tiket aktif (klarifikasi/usul serah); "
        f"{n_idle_serah} telah diserahkan ke Pengelola Barang.",
        f"Sengketa: {n_sengketa} aset berstatus/berindikasi sengketa.",
    ]
    for b in butir:
        elements.append(Paragraph(f"• {b}", st['Meta']))
    elements.append(Spacer(1, 1 * rl_mm))
    elements.append(Paragraph(
        "Langkah strategis dan penjelasan kualitatif lainnya diisi operator "
        "sesuai kondisi satker sebelum dokumen difinalkan.", st['Meta']))

    elements.append(Spacer(1, 10 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("CaLBMN — Bahan Penyusunan (Pra-isi)")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    suffix = f"_S{semester}" if semester else ""
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="CaLBMN_{tahun}{suffix}.pdf"'})


@reports_router.get("/pembukuan/rekonsiliasi-xlsx")
async def generate_rekonsiliasi_xlsx(_user: dict = Depends(require_user_or_query_token)):
    """Ekspor rekonsiliasi Posisi BMN (XLSX) — sandingan SAKTI/MonSAKTI.

    Pustaka §2.3: ekspor pembanding rekonsiliasi. Tiga sheet dari data
    nyata: Posisi per Golongan (intra/ekstra + persediaan + total),
    Rincian Aset (klasifikasi per NUP), Rincian Persediaan (stok + nilai
    FIFO per layer).
    """
    import xlsxwriter
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import (
        build_dbkp_rows, golongan_of, klasifikasi_komptabel, parse_harga,
        posisi_neraca,
    )
    from persediaan_utils import nilai_persediaan_dari_batches

    # Rekonsiliasi Posisi BMN harus SELARAS dengan Neraca (#248): kecualikan aset
    # ber-SK penghapusan agar sandingan SAKTI/MonSAKTI tidak selisih hanya karena
    # aset yang sudah dihapus masih ikut terhitung (§5A Prinsip 3).
    assets = await db.assets.find(
        active_asset_filter(),
        {"_id": 0, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "location": 1, "condition": 1},
    ).to_list(500000)
    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]
    rows, total_aset = build_dbkp_rows(assets, uraian_map)
    persediaan = await db.persediaan.find(
        {}, {"_id": 0, "kode_barang": 1, "nup": 1, "nama_barang": 1,
             "satuan": 1, "stok": 1, "batches": 1},
    ).to_list(100000)
    p_nilai = sum(nilai_persediaan_dari_batches(it.get("batches")) for it in persediaan)
    posisi = posisi_neraca(rows, total_aset, len(persediaan), p_nilai)

    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    f_judul = wb.add_format({"bold": True})
    f_kepala = wb.add_format({"bold": True, "bg_color": "#DDE6F2", "border": 1})
    f_sel = wb.add_format({"border": 1})
    f_angka = wb.add_format({"border": 1, "num_format": "#,##0"})
    f_tebal = wb.add_format({"bold": True, "border": 1})
    f_tebal_angka = wb.add_format({"bold": True, "border": 1, "num_format": "#,##0"})

    today_iso = datetime.now(timezone.utc).date().isoformat()

    # ── Sheet 1: posisi per golongan ─────────────────────────────────
    s1 = wb.add_worksheet("Posisi Golongan")
    s1.write(0, 0, f"Posisi BMN per {today_iso} — sandingan rekonsiliasi SAKTI/MonSAKTI "
                   "(intra/ekstra per ambang PMK 181; persediaan FIFO per layer)", f_judul)
    kolom1 = ["Gol", "Uraian", "Jml Intra", "Nilai Intra", "Jml Ekstra",
              "Nilai Ekstra", "Jml Total", "Nilai Total"]
    for c, h in enumerate(kolom1):
        s1.write(2, c, h, f_kepala)
    r = 3
    for row in posisi["aset"]:
        s1.write(r, 0, row["golongan"], f_sel)
        s1.write(r, 1, row["uraian"], f_sel)
        for c, key in enumerate(["jumlah_intra", "nilai_intra", "jumlah_ekstra",
                                 "nilai_ekstra", "jumlah_total", "nilai_total"], start=2):
            s1.write_number(r, c, row[key], f_angka)
        r += 1
    p = posisi["persediaan"]
    s1.write(r, 0, "1", f_sel)
    s1.write(r, 1, "Persediaan (aset lancar — nilai FIFO per layer)", f_sel)
    for c, v in enumerate([p["jumlah"], p["nilai"], 0, 0, p["jumlah"], p["nilai"]], start=2):
        s1.write_number(r, c, v, f_angka)
    r += 1
    g = posisi["total"]
    s1.write(r, 0, "", f_tebal)
    s1.write(r, 1, "TOTAL POSISI BMN", f_tebal)
    for c, key in enumerate(["jumlah_intra", "nilai_intra", "jumlah_ekstra",
                             "nilai_ekstra", "jumlah_total", "nilai_total"], start=2):
        s1.write_number(r, c, g[key], f_tebal_angka)
    s1.set_column(0, 0, 6)
    s1.set_column(1, 1, 44)
    s1.set_column(2, 7, 15)

    # ── Sheet 2: rincian aset (dasar sanding per NUP) ────────────────
    s2 = wb.add_worksheet("Rincian Aset")
    kolom2 = ["Kode Barang", "NUP", "Nama Barang", "Gol", "Nilai Perolehan",
              "Komptabel", "Kondisi", "Lokasi"]
    for c, h in enumerate(kolom2):
        s2.write(0, c, h, f_kepala)
    for i, a in enumerate(sorted(
            assets, key=lambda x: (str(x.get("asset_code") or ""), str(x.get("NUP") or ""))),
            start=1):
        harga = parse_harga(a.get("purchase_price"))
        s2.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s2.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s2.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s2.write(i, 3, golongan_of(a.get("asset_code")) or "?", f_sel)
        s2.write_number(i, 4, harga, f_angka)
        s2.write(i, 5, klasifikasi_komptabel(a.get("asset_code"), harga), f_sel)
        s2.write(i, 6, str(a.get("condition") or ""), f_sel)
        s2.write(i, 7, str(a.get("location") or ""), f_sel)
    s2.set_column(0, 0, 14)
    s2.set_column(1, 1, 7)
    s2.set_column(2, 2, 38)
    s2.set_column(3, 3, 5)
    s2.set_column(4, 4, 16)
    s2.set_column(5, 7, 14)

    # ── Sheet 3: rincian persediaan ──────────────────────────────────
    s3 = wb.add_worksheet("Rincian Persediaan")
    kolom3 = ["Kode Barang", "NUP", "Nama Barang", "Satuan", "Stok", "Nilai (FIFO)"]
    for c, h in enumerate(kolom3):
        s3.write(0, c, h, f_kepala)
    for i, it in enumerate(sorted(
            persediaan, key=lambda x: (str(x.get("nama_barang") or ""), str(x.get("kode_barang") or ""))),
            start=1):
        s3.write(i, 0, str(it.get("kode_barang") or ""), f_sel)
        s3.write(i, 1, str(it.get("nup") or ""), f_sel)
        s3.write(i, 2, str(it.get("nama_barang") or ""), f_sel)
        s3.write(i, 3, str(it.get("satuan") or ""), f_sel)
        s3.write_number(i, 4, int(it.get("stok", 0) or 0), f_angka)
        s3.write_number(i, 5, nilai_persediaan_dari_batches(it.get("batches")), f_angka)
    s3.set_column(0, 0, 18)
    s3.set_column(1, 1, 7)
    s3.set_column(2, 2, 38)
    s3.set_column(3, 5, 12)

    wb.close()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Rekonsiliasi_Posisi_BMN.xlsx"'})


# ============================================================================
# BAHI PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/bahi-pdf")
async def generate_bahi_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate BAHI (Berita Acara Hasil Inventarisasi BMN) PDF"""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO)
    assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0, "document_checklist": 0},
    ).to_list(100000)

    def safe_price(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0.0

    def fmt_rp(val):
        try: return f"Rp {int(val):,}".replace(",", ".")
        except: return "Rp 0"

    total_all = len(assets)
    ditemukan = [a for a in assets if a.get("inventory_status") == "Ditemukan"]
    tidak_ditemukan = [a for a in assets if a.get("inventory_status") == "Tidak Ditemukan"]
    berlebih = [a for a in assets if a.get("inventory_status") == "Berlebih"]
    sengketa = [a for a in assets if a.get("inventory_status") == "Sengketa"]
    baik = [a for a in ditemukan if a.get("condition") == "Baik"]
    rusak_ringan = [a for a in ditemukan if a.get("condition") == "Rusak Ringan"]
    rusak_berat = [a for a in ditemukan if a.get("condition") == "Rusak Berat"]

    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    kasatker_nama = ident["kasatker_nama"]
    kasatker_nip = ident["kasatker_nip"]
    kasatker_jabatan = ident["kasatker_jabatan"]
    tim = activity.get("tim_peneliti", [])
    tim_pendukung_list = activity.get("tim_pendukung", [])
    nomor_sk = activity.get("nomor_surat", "-")
    tgl_mulai = _fmt_tanggal_id(activity.get("tanggal_mulai")) or "-"
    tgl_selesai = _fmt_tanggal_id(activity.get("tanggal_selesai")) or "-"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    bold_style = st['Heading']
    indent_style = st['BodyIndent']
    small_style = st['Body']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    ba = activity.get("berita_acara", {})
    ba_nomor = ba.get("nomor", "......./......./........")
    elements.extend(_title_block("BERITA ACARA\nHASIL INVENTARISASI BARANG MILIK NEGARA", nomor=ba_nomor))

    elements.append(Paragraph(
        f"Pada hari ini, .................., tanggal .................. bulan .................. "
        f"tahun ...................., bertempat di {satker_name}, kami yang bertanda tangan di bawah ini:",
        normal_style))
    elements.append(Spacer(1, 3*rl_mm))

    elements.append(_identity_table([
        ("Nama", kasatker_nama),
        ("NIP", kasatker_nip),
        ("Jabatan", kasatker_jabatan),
        ("Unit Organisasi", satker_name),
    ]))

    elements.append(Spacer(1, 3*rl_mm))
    elements.append(Paragraph(
        f"Berdasarkan Surat Keputusan Nomor {nomor_sk}, telah dilaksanakan kegiatan inventarisasi "
        f"Barang Milik Negara (BMN) di lingkungan {satker_name} pada periode {tgl_mulai} s.d. {tgl_selesai}.",
        normal_style))
    elements.append(Spacer(1, 3*rl_mm))

    elements.append(Paragraph("<b>Adapun hasil inventarisasi adalah sebagai berikut:</b>", normal_style))
    elements.append(Spacer(1, 2*rl_mm))

    summary_items = [
        f"Jumlah BMN yang diteliti: <b>{total_all} NUP</b> dengan nilai total <b>{fmt_rp(sum(safe_price(a) for a in assets))}</b>",
        f"BMN Ditemukan: <b>{len(ditemukan)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in ditemukan))})",
        f"&nbsp;&nbsp;&nbsp;a. Kondisi Baik: <b>{len(baik)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in baik))})",
        f"&nbsp;&nbsp;&nbsp;b. Kondisi Rusak Ringan: <b>{len(rusak_ringan)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in rusak_ringan))})",
        f"&nbsp;&nbsp;&nbsp;c. Kondisi Rusak Berat: <b>{len(rusak_berat)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in rusak_berat))})",
        f"BMN Tidak Ditemukan: <b>{len(tidak_ditemukan)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in tidak_ditemukan))})",
        f"BMN Berlebih: <b>{len(berlebih)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in berlebih))})",
        f"BMN Dalam Sengketa: <b>{len(sengketa)} NUP</b> ({fmt_rp(sum(safe_price(a) for a in sengketa))})",
    ]
    # Sub-butir a/b/c tidak memakai nomor — nomor urut hanya utk butir utama
    no_butir = 0
    for item in summary_items:
        if item.startswith("&nbsp;"):
            elements.append(Paragraph(item, indent_style))
        else:
            no_butir += 1
            elements.append(Paragraph(f"{no_butir}. {item}", indent_style))

    elements.append(Spacer(1, 4*rl_mm))

    elements.append(Paragraph("<b>Hasil inventarisasi sebagaimana tercantum dalam Laporan Hasil Inventarisasi (LHI) yang terdiri dari:</b>", normal_style))
    attachments = [
        "Rekapitulasi Hasil Inventarisasi BMN (RHI);",
        "Daftar Barang Hasil Inventarisasi BMN (DBHI) Kondisi Baik;",
        "DBHI Kondisi Rusak Ringan;",
        "DBHI Kondisi Rusak Berat;",
        "DBHI BMN Berlebih;",
        "DBHI BMN Tidak Ditemukan;",
        "DBHI BMN Dalam Sengketa;",
        "Surat Pernyataan Hasil Inventarisasi BMN;",
        "Surat Pernyataan Pelaksanaan Inventarisasi BMN.",
    ]
    for idx, att in enumerate(attachments, 1):
        elements.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{idx}. {att}", indent_style))

    elements.append(Spacer(1, 4*rl_mm))
    elements.append(Paragraph(
        "Demikian Berita Acara Hasil Inventarisasi ini dibuat dengan sebenar-benarnya "
        "dan dapat dipertanggungjawabkan.",
        normal_style))

    elements.append(Spacer(1, 10*rl_mm))

    if tim:
        elements.append(Paragraph("<b>Tim Pelaksana Inventarisasi:</b>", bold_style))
        for i, member in enumerate(tim, 1):
            # Anggota bisa dict {nama, jabatan, nip, dari_satker} atau string legacy
            name = member.get('nama', '-') if isinstance(member, dict) else str(member)
            elements.append(Paragraph(f"{i}. {name} &nbsp;&nbsp;&nbsp;(.......................)", small_style))
        elements.append(Spacer(1, 4*rl_mm))

    if tim_pendukung_list:
        elements.append(Paragraph("<b>Tim Pendukung:</b>", bold_style))
        for i, member in enumerate(tim_pendukung_list, 1):
            if isinstance(member, dict):
                name = member.get('nama', '-')
            else:
                name = str(member)
            elements.append(Paragraph(f"{i}. {name} &nbsp;&nbsp;&nbsp;(.......................)", small_style))
        elements.append(Spacer(1, 6*rl_mm))

    elements.extend(_signature_block([
        {'header': 'Mengetahui,',
         'nama': kasatker_nama,
         'after': [f'NIP. {kasatker_nip}']},
        {'pre': ['.................., .......................'],
         'header': 'Yang membuat Berita Acara,',
         'nama': _member_nama(tim[0], '________________________') if tim else '________________________',
         'after': ['NIP. ........................']},
    ], doc.width))

    footer = _page_footer_factory("Berita Acara Hasil Inventarisasi Barang Milik Negara (BAHI)")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BAHI_{activity_id[:8]}.pdf"'})


# ============================================================================
# SP HASIL PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/sp-hasil-pdf")
async def generate_sp_hasil_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate Surat Pernyataan Hasil Inventarisasi BMN PDF"""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    kasatker_nama = ident["kasatker_nama"]
    kasatker_nip = ident["kasatker_nip"]
    kasatker_jabatan = ident["kasatker_jabatan"]
    nomor_sk = activity.get("nomor_surat", "-")

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    indent_style = st['BodyIndent']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    elements.extend(_title_block("SURAT PERNYATAAN\nHASIL INVENTARISASI BARANG MILIK NEGARA"))

    elements.append(Paragraph("Yang bertanda tangan di bawah ini:", normal_style))
    elements.append(Spacer(1, 2*rl_mm))

    elements.append(_identity_table([
        ("Nama", kasatker_nama),
        ("NIP", kasatker_nip),
        ("Jabatan", kasatker_jabatan),
        ("Unit Organisasi", satker_name),
    ]))

    elements.append(Spacer(1, 4*rl_mm))
    elements.append(Paragraph("<b>Menyatakan dengan sesungguhnya bahwa:</b>", normal_style))
    elements.append(Spacer(1, 2*rl_mm))

    statements = [
        f"Telah melaksanakan kegiatan inventarisasi Barang Milik Negara (BMN) di lingkungan "
        f"{satker_name} sesuai dengan Pedoman Inventarisasi Barang Milik Negara sebagaimana diatur "
        f"dalam Surat Keputusan Nomor {nomor_sk}.",

        "Hasil inventarisasi sebagaimana tercantum dalam Laporan Hasil Inventarisasi (LHI) yang meliputi "
        "Rekapitulasi Hasil Inventarisasi (RHI) dan Daftar Barang Hasil Inventarisasi (DBHI) beserta "
        "seluruh lampirannya adalah <b>benar dan akurat</b> sesuai dengan kondisi serta keberadaan BMN "
        "pada saat pelaksanaan inventarisasi.",

        "Pernyataan ini dibuat untuk dipergunakan sebagaimana mestinya.",
    ]
    for idx, stmt in enumerate(statements, 1):
        elements.append(Paragraph(f"{idx}. &nbsp;{stmt}", indent_style))

    elements.append(Spacer(1, 4*rl_mm))
    elements.append(Paragraph(
        "Apabila di kemudian hari terdapat kekeliruan dalam pernyataan ini, maka kami bersedia "
        "untuk bertanggung jawab sesuai dengan ketentuan peraturan perundang-undangan yang berlaku.",
        normal_style))

    elements.append(Spacer(1, 12*rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Yang membuat pernyataan,',
         'nama': kasatker_nama,
         'after': [f'{kasatker_jabatan}', f'NIP. {kasatker_nip}']},
    ], doc.width))

    footer = _page_footer_factory("Surat Pernyataan Hasil Inventarisasi Barang Milik Negara")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="SP_Hasil_{activity_id[:8]}.pdf"'})


# ============================================================================
# SP PELAKSANAAN PDF
# ============================================================================

@reports_router.get("/inventory-activities/{activity_id}/sp-pelaksanaan-pdf")
async def generate_sp_pelaksanaan_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate Surat Pernyataan Pelaksanaan Inventarisasi BMN PDF"""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm as rl_mm

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    kasatker_nama = ident["kasatker_nama"]
    kasatker_nip = ident["kasatker_nip"]
    kasatker_jabatan = ident["kasatker_jabatan"]
    nomor_sk = activity.get("nomor_surat", "-")
    tgl_mulai = _fmt_tanggal_id(activity.get("tanggal_mulai")) or "-"
    tgl_selesai = _fmt_tanggal_id(activity.get("tanggal_selesai")) or "-"

    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    normal_style = st['Body']
    indent_style = st['BodyIndent']

    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    elements.extend(_title_block("SURAT PERNYATAAN\nPELAKSANAAN INVENTARISASI BARANG MILIK NEGARA"))

    elements.append(Paragraph("Yang bertanda tangan di bawah ini:", normal_style))
    elements.append(Spacer(1, 2*rl_mm))

    elements.append(_identity_table([
        ("Nama", kasatker_nama),
        ("NIP", kasatker_nip),
        ("Jabatan", kasatker_jabatan),
        ("Unit Organisasi", satker_name),
    ]))

    elements.append(Spacer(1, 4*rl_mm))
    elements.append(Paragraph("<b>Menyatakan dengan sesungguhnya bahwa:</b>", normal_style))
    elements.append(Spacer(1, 2*rl_mm))

    statements = [
        f"Telah melaksanakan kegiatan inventarisasi Barang Milik Negara (BMN) di lingkungan "
        f"{satker_name} sesuai dengan tahapan dan prosedur yang diatur dalam Pedoman Inventarisasi "
        f"Barang Milik Negara sebagaimana diatur dalam Surat Keputusan Nomor {nomor_sk}, "
        f"pada periode {tgl_mulai} s.d. {tgl_selesai}.",

        "Pelaksanaan inventarisasi telah dilakukan secara <b>tertib, lengkap, dan akuntabel</b>, "
        "meliputi tahap persiapan, pelaksanaan pendataan, identifikasi, pelaporan, dan tindak lanjut.",

        "Seluruh data dan informasi yang terkait dengan pelaksanaan inventarisasi telah dikumpulkan "
        "dan didokumentasikan dengan baik.",

        "Pernyataan ini dibuat untuk dipergunakan sebagaimana mestinya.",
    ]
    for idx, stmt in enumerate(statements, 1):
        elements.append(Paragraph(f"{idx}. &nbsp;{stmt}", indent_style))

    elements.append(Spacer(1, 4*rl_mm))
    elements.append(Paragraph(
        "Apabila di kemudian hari terdapat kekeliruan dalam pernyataan ini, maka kami bersedia "
        "untuk bertanggung jawab sesuai dengan ketentuan peraturan perundang-undangan yang berlaku.",
        normal_style))

    elements.append(Spacer(1, 12*rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Yang membuat pernyataan,',
         'nama': kasatker_nama,
         'after': [f'{kasatker_jabatan}', f'NIP. {kasatker_nip}']},
    ], doc.width))

    footer = _page_footer_factory("Surat Pernyataan Pelaksanaan Inventarisasi Barang Milik Negara")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="SP_Pelaksanaan_{activity_id[:8]}.pdf"'})


# ============================================================================
# REPORT SETTINGS (Logo, Cover Page)
# ============================================================================

class ReportSettingsUpdate(BaseModel):
    nama_instansi: Optional[str] = ""
    nama_unit_organisasi: Optional[str] = ""
    nama_sub_unit: Optional[str] = ""
    alamat_instansi: Optional[str] = ""
    judul_laporan: Optional[str] = "LAPORAN HASIL INVENTARISASI"
    subjudul_laporan: Optional[str] = "BARANG MILIK NEGARA (BMN)"
    tahun_anggaran: Optional[str] = ""
    catatan_kaki: Optional[str] = ""


@reports_router.get("/report-settings")
async def get_report_settings(_user: dict = Depends(require_user)):
    """Get report settings (logo, cover page text)"""
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0})
    if not settings:
        return {
            "type": "global",
            "logo_url": "",
            "nama_instansi": "",
            "nama_unit_organisasi": "",
            "nama_sub_unit": "",
            "alamat_instansi": "",
            "judul_laporan": "LAPORAN HASIL INVENTARISASI",
            "subjudul_laporan": "BARANG MILIK NEGARA (BMN)",
            "tahun_anggaran": "",
            "catatan_kaki": "",
        }
    return settings


@reports_router.put("/report-settings")
async def update_report_settings(data: ReportSettingsUpdate, _admin: dict = Depends(require_admin)):
    """Update report settings (text fields only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    update_data["type"] = "global"
    await db.report_settings.update_one(
        {"type": "global"},
        {"$set": update_data},
        upsert=True
    )
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0})
    return settings


@reports_router.post("/report-settings/logo")
async def upload_report_logo(file: UploadFile = File(...), _admin: dict = Depends(require_admin)):
    """Upload/replace the institution logo for report cover page"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar (PNG/JPG)")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 5MB")

    b64 = base64.b64encode(content).decode("utf-8")
    logo_url = f"data:{file.content_type};base64,{b64}"

    await db.report_settings.update_one(
        {"type": "global"},
        {"$set": {"logo_url": logo_url, "type": "global"}},
        upsert=True
    )
    return {"message": "Logo berhasil diupload", "logo_url": logo_url}


@reports_router.delete("/report-settings/logo")
async def delete_report_logo(_admin: dict = Depends(require_admin)):
    """Remove the institution logo"""
    await db.report_settings.update_one(
        {"type": "global"},
        {"$set": {"logo_url": ""}},
        upsert=True
    )
    return {"message": "Logo berhasil dihapus"}


# ============================================================================
# COVER PAGE HELPER
# ============================================================================

async def _generate_cover_page(activity, settings):
    """Generate LHI cover page PDF as BytesIO buffer"""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import mm as rl_mm, cm as rl_cm
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=3*rl_cm, rightMargin=3*rl_cm, topMargin=3*rl_cm, bottomMargin=3*rl_cm)

    styles = getSampleStyleSheet()
    instansi_style = ParagraphStyle('CoverInstansi', parent=styles['Normal'], fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=18, spaceAfter=2)
    unit_style = ParagraphStyle('CoverUnit', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER, leading=14, spaceAfter=2)
    alamat_style = ParagraphStyle('CoverAlamat', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, leading=12, textColor=rl_colors.HexColor("#555555"))
    title_style = ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=20, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=26, spaceAfter=4, textColor=rl_colors.HexColor("#1a365d"))
    subtitle_style = ParagraphStyle('CoverSubtitle', parent=styles['Normal'], fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=18, textColor=rl_colors.HexColor("#2d3748"))
    info_style = ParagraphStyle('CoverInfo', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER, leading=15)
    tahun_style = ParagraphStyle('CoverTahun', parent=styles['Normal'], fontSize=16, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=20, textColor=rl_colors.HexColor("#1a365d"))
    footer_style = ParagraphStyle('CoverFooter', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, leading=12, textColor=rl_colors.HexColor("#718096"))

    elements = []

    # Logo
    logo_url = settings.get("logo_url", "")
    if logo_url and logo_url.startswith("data:"):
        try:
            header, b64data = logo_url.split(",", 1)
            logo_bytes = base64.b64decode(b64data)
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(io.BytesIO(logo_bytes)).getSize()
            scale = 80.0 / max(iw, ih)
            logo_buffer = io.BytesIO(logo_bytes)
            logo_img = RLImage(logo_buffer, width=iw * scale, height=ih * scale)
            logo_img.hAlign = 'CENTER'
            elements.append(logo_img)
            elements.append(Spacer(1, 6*rl_mm))
        except Exception:
            pass

    # Institution name
    nama_instansi = settings.get("nama_instansi", "")
    if nama_instansi:
        elements.append(Paragraph(nama_instansi.upper(), instansi_style))

    nama_unit = settings.get("nama_unit_organisasi", "")
    if nama_unit:
        elements.append(Paragraph(nama_unit, unit_style))

    nama_sub_unit = settings.get("nama_sub_unit", "")
    if nama_sub_unit:
        elements.append(Paragraph(nama_sub_unit, unit_style))

    alamat = settings.get("alamat_instansi", "")
    for _line in str(alamat).splitlines():
        if _line.strip():
            elements.append(Paragraph(_line.strip(), alamat_style))

    if nama_instansi or nama_unit or nama_sub_unit or alamat:
        elements.append(Spacer(1, 2*rl_mm))
        line_data = [[""]]
        line_table = Table(line_data, colWidths=[380])
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, rl_colors.HexColor("#1a365d")),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(line_table)

    elements.append(Spacer(1, 30*rl_mm))

    judul = settings.get("judul_laporan", "LAPORAN HASIL INVENTARISASI")
    subjudul = settings.get("subjudul_laporan", "BARANG MILIK NEGARA (BMN)")
    elements.append(Paragraph(judul, title_style))
    elements.append(Paragraph(subjudul, subtitle_style))

    elements.append(Spacer(1, 15*rl_mm))

    ident = _activity_identity(activity, settings)
    satker_name = ident["satker_name"]
    nomor_sk = activity.get("nomor_surat") or "-"
    tgl_mulai = _fmt_tanggal_id(activity.get("tanggal_mulai")) or "-"
    tgl_selesai = _fmt_tanggal_id(activity.get("tanggal_selesai")) or "-"

    details = [
        f"Satuan Kerja: {satker_name}",
        f"Nomor SK: {nomor_sk}",
        f"Periode: {tgl_mulai} s.d. {tgl_selesai}",
    ]
    for detail in details:
        elements.append(Paragraph(detail, info_style))

    elements.append(Spacer(1, 20*rl_mm))

    tahun = settings.get("tahun_anggaran", "")
    if tahun:
        elements.append(Paragraph(f"TAHUN ANGGARAN {tahun}", tahun_style))
    else:
        elements.append(Paragraph("TAHUN ANGGARAN ............", tahun_style))

    elements.append(Spacer(1, 30*rl_mm))
    catatan = settings.get("catatan_kaki", "")
    if catatan:
        elements.append(Paragraph(catatan, footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ============================================================================
# EXECUTIVE SUMMARY (HTML preview + PDF via weasyprint)
# ============================================================================

def _downscale_to_data_uri(raw: bytes, max_w: int = 640, quality: int = 80) -> str:
    """Perkecil bytes foto (maks lebar 640px, JPEG q80) → data-URI base64.

    Meniru _resize_jpeg di routes/assets.py. Dipakai untuk fallback GridFS
    agar embed foto ke HTML WeasyPrint tetap hemat memori/waktu (template
    menampilkan foto hanya ~58-78px, jadi 640px sudah lebih dari cukup).
    Mengembalikan '' bila gagal (template punya fallback "No Foto").
    """
    # PIL tidak di-import global di modul ini — import lokal di helper.
    import io as _io
    from PIL import Image as PILImage
    try:
        img = PILImage.open(_io.BytesIO(raw))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        if w > max_w:
            img = img.resize((max_w, max(1, round(h * max_w / w))), PILImage.LANCZOS)
        out = _io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception as e:
        logger.debug(f"[reports] downscale foto gagal: {e}")
        return ""


async def _gridfs_photo_data_uri(gid: str, max_w: int = 640) -> str:
    """Ambil foto dari GridFS lalu downscale ke data-URI; '' bila gagal.

    Fallback untuk aset hasil migrasi GridFS-only (photos=[] tapi
    photo_gridfs_ids terisi) pada laporan eksekutif & laporan berkelompok.
    """
    try:
        raw = await get_photo_from_gridfs(gid)
        if not raw:
            return ""
        return _downscale_to_data_uri(raw, max_w)
    except Exception as e:
        logger.debug(f"[reports] GridFS foto {gid} gagal diambil: {e}")
        return ""


# Kolom tambahan opsional untuk kolom "Kondisi & Status" (key, label, field aset)
EXEC_DETAIL_FIELDS = [
    ("spm", "SPM", "nomor_spm"),
    ("perolehan", "Perolehan", "perolehan_dari_nama"),
    ("kontrak", "Kontrak", "nomor_kontrak"),
    ("bast", "BAST", "nomor_bukti_perolehan"),
    ("supplier", "Supplier", "supplier"),
    ("serial", "S/N", "serial_number"),
]


def _parse_detail_fields(detail_fields: str):
    """Parse comma-separated detail_fields query param into a set of valid keys"""
    valid = {k for k, _, _ in EXEC_DETAIL_FIELDS}
    return {f.strip() for f in (detail_fields or "").split(",") if f.strip()} & valid


async def _build_executive_summary_data(activity_id: str, detail_fields=None,
                                        with_asset_rows: bool = True):
    """Build all data needed for the executive summary template.

    detail_fields: optional set of EXEC_DETAIL_FIELDS keys — extra per-asset
    fields to include in the "Kondisi & Status" column (empty = current behavior).
    """
    detail_fields = detail_fields or set()
    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        return None
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    # proyeksi: buang media base64 yang tidak dipakai (hemat memori/IO);
    # 'photos' TETAP diambil (foto sampul & stiker di-embed pada laporan data)
    # dan 'document_checklist' TETAP diambil (statistik & kolom kelengkapan dokumen).
    # Proyeksi bergaya eksklusi, jadi 'photo_gridfs_ids' & 'thumbnail_index' &
    # 'stiker_photo_index' ikut terambil — dipakai fallback GridFS di bawah.
    all_assets = await db.assets.find(
        {"activity_id": activity_id},
        {"_id": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0},
    ).to_list(100000)
    categories = await db.categories.find({}, {"_id": 0}).to_list(10000)
    cat_map = {c.get("kode_aset", ""): c.get("label", "") for c in categories}

    def sp(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0.0
    def fmt(v):
        try: return f"{int(v):,}".replace(",", ".")
        except: return "0"
    def pct(part, total):
        return round(part / total * 100, 1) if total > 0 else 0

    ditemukan = [a for a in all_assets if a.get("inventory_status") == "Ditemukan"]
    tidak = [a for a in all_assets if a.get("inventory_status") == "Tidak Ditemukan"]
    berlebih = [a for a in all_assets if a.get("inventory_status") == "Berlebih"]
    sengketa = [a for a in all_assets if a.get("inventory_status") == "Sengketa"]
    belum = [a for a in all_assets if (a.get("inventory_status") or "Belum Diinventarisasi") == "Belum Diinventarisasi"]
    baik = [a for a in ditemukan if a.get("condition") == "Baik"]
    rr = [a for a in ditemukan if a.get("condition") == "Rusak Ringan"]
    rb = [a for a in ditemukan if a.get("condition") == "Rusak Berat"]
    td_kes = [a for a in tidak if a.get("klasifikasi_tidak_ditemukan") == "Kesalahan Pencatatan"]
    td_lain = [a for a in tidak if a.get("klasifikasi_tidak_ditemukan") != "Kesalahan Pencatatan"]

    tc = len(all_assets)
    tv = sum(sp(a) for a in all_assets)
    st_terpasang = len([a for a in ditemukan if a.get("stiker_status") == "Sudah Terpasang"])
    st_belum = len(ditemukan) - st_terpasang
    st_pct = int(st_terpasang / len(ditemukan) * 100) if len(ditemukan) > 0 else 0
    circumference = 2 * 3.14159 * 32
    st_dash = circumference
    st_offset = circumference * (1 - st_pct / 100)

    satker_name = _activity_identity(activity, settings)["satker_name"]
    # _member_dict: anggota string era lama tetap tampil bernama, bukan "-"
    tim = [_member_dict(t) for t in (activity.get("tim_peneliti", []) or [])]
    tim_pendukung = [_member_dict(t) for t in (activity.get("tim_pendukung", []) or [])]
    tim_inti = [_member_dict(t) for t in (activity.get("tim_inti", []) or [])]
    tim_pembantu = [_member_dict(t) for t in (activity.get("tim_pembantu", []) or [])]
    pj_nama = activity.get("penanggung_jawab", "") or ""
    pj_jabatan = activity.get("penanggung_jawab_jabatan", "") or ""
    pj_nip = activity.get("penanggung_jawab_nip", "") or ""

    # Determine if the inventory period is currently active ("ON PROGRESS")
    is_in_progress = False
    tgl_mulai_raw = activity.get("tanggal_mulai", "")
    tgl_selesai_raw = activity.get("tanggal_selesai", "")
    today = datetime.now()
    try:
        from datetime import date as date_type
        def parse_date(d):
            if not d:
                return None
            for dfmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(str(d).strip(), dfmt).date()
                except ValueError:
                    continue
            return None
        d_mulai = parse_date(tgl_mulai_raw)
        d_selesai = parse_date(tgl_selesai_raw)
        if d_mulai and d_selesai:
            is_in_progress = d_mulai <= today.date() <= d_selesai
        elif d_mulai and not d_selesai:
            is_in_progress = d_mulai <= today.date()
    except Exception:
        is_in_progress = False

    # Build per-category breakdown (ALL categories, not truncated)
    cat_breakdown = {}
    for a in all_assets:
        cat_code = a.get("category", "")
        cat_label = cat_map.get(cat_code, cat_code or "Tanpa Kategori")
        if cat_label not in cat_breakdown:
            cat_breakdown[cat_label] = {"count": 0, "value": 0, "conditions": {}, "statuses": {}}
        cat_breakdown[cat_label]["count"] += 1
        cat_breakdown[cat_label]["value"] += sp(a)
        cond = a.get("condition", "") or "Belum Dinilai"
        cat_breakdown[cat_label]["conditions"][cond] = cat_breakdown[cat_label]["conditions"].get(cond, 0) + 1
        stat = a.get("inventory_status", "Belum Diinventarisasi")
        cat_breakdown[cat_label]["statuses"][stat] = cat_breakdown[cat_label]["statuses"].get(stat, 0) + 1
    # Sort by count descending
    cat_breakdown_sorted = sorted(cat_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)

    # Build per-location breakdown (ALL locations)
    loc_breakdown = {}
    for a in all_assets:
        loc = a.get("location", "") or "Tanpa Lokasi"
        if loc not in loc_breakdown:
            loc_breakdown[loc] = {"count": 0, "value": 0}
        loc_breakdown[loc]["count"] += 1
        loc_breakdown[loc]["value"] += sp(a)
    loc_breakdown_sorted = sorted(loc_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)

    # Build per-eselon1 breakdown
    eselon1_breakdown = {}
    for a in all_assets:
        e1 = a.get("eselon1", "") or "Tanpa Eselon I"
        if e1 not in eselon1_breakdown:
            eselon1_breakdown[e1] = {"count": 0, "value": 0}
        eselon1_breakdown[e1]["count"] += 1
        eselon1_breakdown[e1]["value"] += sp(a)
    eselon1_breakdown_sorted = sorted(eselon1_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)

    # Build year distribution
    year_breakdown = {}
    for a in all_assets:
        yr = a.get("purchase_date", "") or ""
        yr_str = str(yr)[:4] if len(str(yr)) >= 4 else "Tidak Diketahui"
        if yr_str not in year_breakdown:
            year_breakdown[yr_str] = {"count": 0, "value": 0}
        year_breakdown[yr_str]["count"] += 1
        year_breakdown[yr_str]["value"] += sp(a)
    year_breakdown_sorted = sorted(year_breakdown.items(), key=lambda x: x[0], reverse=True)

    # Document completeness stats
    total_doc_items = 0
    total_doc_checked = 0
    for a in all_assets:
        doc_ck = a.get("document_checklist", []) or []
        total_doc_items += len(doc_ck)
        total_doc_checked += sum(1 for d in doc_ck if d.get("checked"))
    doc_completeness_pct = round(total_doc_checked / total_doc_items * 100, 1) if total_doc_items > 0 else 0

    # Photo coverage stats — aset GridFS-only (photos kosong, blob di
    # photo_gridfs_ids) juga dihitung sebagai "punya foto"
    assets_with_photos = sum(
        1 for a in all_assets
        if (len(a.get("photos") or []) > 0)
        or (len([g for g in (a.get("photo_gridfs_ids") or []) if g]) > 0)
    )
    photo_coverage_pct = round(assets_with_photos / tc * 100, 1) if tc > 0 else 0

    # GPS coverage stats
    assets_with_gps = sum(1 for a in all_assets if a.get("koordinat_latitude") and a.get("koordinat_longitude"))
    gps_coverage_pct = round(assets_with_gps / tc * 100, 1) if tc > 0 else 0

    # Pre-calculate chart bar widths for ALL categories
    cat_max_count = max((c[1]["count"] for c in cat_breakdown_sorted), default=1)
    cat_chart = [{"name": c[0][:30], "count": c[1]["count"], "value": c[1]["value"], "bar_pct": round(c[1]["count"] / cat_max_count * 100)} for c in cat_breakdown_sorted]

    # Pre-calculate chart bar widths for ALL locations
    loc_max_count = max((l[1]["count"] for l in loc_breakdown_sorted), default=1)
    loc_chart = [{"name": l[0][:30], "count": l[1]["count"], "value": l[1]["value"], "bar_pct": round(l[1]["count"] / loc_max_count * 100)} for l in loc_breakdown_sorted]

    # Year chart data (sorted by year ascending for chart)
    year_sorted_asc = sorted(year_breakdown.items(), key=lambda x: x[0])
    yr_max_count = max((y[1]["count"] for y in year_sorted_asc), default=1)
    year_chart = [{"name": y[0], "count": y[1]["count"], "value": y[1]["value"], "bar_pct": round(y[1]["count"] / yr_max_count * 100)} for y in year_sorted_asc]

    # Eselon chart
    e1_max = max((e[1]["count"] for e in eselon1_breakdown_sorted), default=1)
    eselon_chart = [{"name": e[0][:25], "count": e[1]["count"], "value": e[1]["value"], "bar_pct": round(e[1]["count"] / e1_max * 100)} for e in eselon1_breakdown_sorted[:10]]

    # Status pie chart data (for SVG donut)
    status_pie = []
    status_items = [
        ("Ditemukan", len(ditemukan), "#22c55e"),
        ("Tidak Ditemukan", len(tidak), "#ef4444"),
        ("Berlebih", len(berlebih), "#f59e0b"),
        ("Sengketa", len(sengketa), "#a855f7"),
        ("Belum Inventarisasi", len(belum), "#94a3b8"),
    ]
    cumulative_pct = 0
    for name, count, color in status_items:
        if count > 0:
            p = round(count / tc * 100, 1) if tc > 0 else 0
            status_pie.append({"name": name, "count": count, "pct": p, "color": color, "offset": cumulative_pct})
            cumulative_pct += p

    # Condition pie chart data
    condition_pie = []
    cond_items = [
        ("Baik", len(baik), "#22c55e"),
        ("Rusak Ringan", len(rr), "#f59e0b"),
        ("Rusak Berat", len(rb), "#ef4444"),
    ]
    cond_total = len(ditemukan)
    cond_cumulative = 0
    for name, count, color in cond_items:
        if count > 0:
            p = round(count / cond_total * 100, 1) if cond_total > 0 else 0
            condition_pie.append({"name": name, "count": count, "pct": p, "color": color, "offset": cond_cumulative})
            cond_cumulative += p

    # Condition by top categories (cross-analysis)
    cond_by_cat = []
    for cat_name, cat_data in cat_breakdown_sorted[:8]:
        conditions = cat_data.get("conditions", {})
        total_cat = cat_data["count"]
        cond_by_cat.append({
            "name": cat_name[:20],
            "total": total_cat,
            "baik": conditions.get("Baik", 0),
            "rr": conditions.get("Rusak Ringan", 0),
            "rb": conditions.get("Rusak Berat", 0),
            "baik_pct": round(conditions.get("Baik", 0) / total_cat * 100) if total_cat > 0 else 0,
            "rr_pct": round(conditions.get("Rusak Ringan", 0) / total_cat * 100) if total_cat > 0 else 0,
            "rb_pct": round(conditions.get("Rusak Berat", 0) / total_cat * 100) if total_cat > 0 else 0,
        })

    simpulan = []
    if tc > 0:
        simpulan.append({"color": "#1e40af", "text": f"Dari <strong>{tc} NUP</strong> BMN senilai <strong>Rp {fmt(tv)}</strong>, sebanyak <strong>{pct(len(ditemukan), tc)}%</strong> ({len(ditemukan)} NUP) berhasil ditemukan."})
        if len(tidak) > 0:
            simpulan.append({"color": "#ef4444", "text": f"<strong>{len(tidak)} NUP</strong> (Rp {fmt(sum(sp(a) for a in tidak))}) tidak ditemukan: <strong>{len(td_kes)}</strong> kesalahan pencatatan, <strong>{len(td_lain)}</strong> tidak ditemukan fisik."})
        if len(berlebih) > 0:
            simpulan.append({"color": "#f59e0b", "text": f"<strong>{len(berlebih)} NUP</strong> BMN berlebih senilai <strong>Rp {fmt(sum(sp(a) for a in berlebih))}</strong>. Akan didaftarkan ke Daftar BMN."})
        if len(sengketa) > 0:
            simpulan.append({"color": "#a855f7", "text": f"<strong>{len(sengketa)} NUP</strong> BMN dalam sengketa senilai <strong>Rp {fmt(sum(sp(a) for a in sengketa))}</strong>. Koordinasi bagian hukum diperlukan."})
        if len(belum) > 0:
            simpulan.append({"color": "#94a3b8", "text": f"<strong>{len(belum)} NUP</strong> ({pct(len(belum), tc)}%) belum diinventarisasi. Perlu tindak lanjut segera."})
        if len(ditemukan) > 0:
            simpulan.append({"color": "#22c55e", "text": f"Stiker terpasang pada <strong>{st_terpasang} dari {len(ditemukan)}</strong> NUP (<strong>{st_pct}%</strong>). {f'Masih ada <strong>{st_belum}</strong> NUP belum dipasang stiker.' if st_belum > 0 else 'Seluruh BMN sudah terpasang stiker.'}"})
        simpulan.append({"color": "#0ea5e9", "text": f"Kelengkapan dokumen: <strong>{doc_completeness_pct}%</strong> terisi. Dokumentasi foto: <strong>{photo_coverage_pct}%</strong> aset terfoto. GPS: <strong>{gps_coverage_pct}%</strong> terkoordinat."})
        if is_in_progress:
            simpulan.append({"color": "#f97316", "text": "<strong>CATATAN:</strong> Laporan ini dibuat saat periode inventarisasi <strong>masih berlangsung</strong>. Data dapat berubah hingga periode berakhir."})
        simpulan.append({"color": "#0f172a", "text": "Seluruh hasil inventarisasi didokumentasikan dalam <strong>LHI</strong> (BAHI, RHI, 6 DBHI, Surat Pernyataan)."})

    asset_rows = []
    # Loop mahal (fallback GridFS per aset) — dilewati bila pemanggil hanya
    # butuh halaman ringkasan (executive-summary-html/pdf, data-info).
    for a in (all_assets if with_asset_rows else []):
        photos = a.get("photos", []) or []
        cover_idx = a.get("thumbnail_index", 0) or 0
        photo_url = photos[cover_idx] if photos and cover_idx < len(photos) else (photos[0] if photos else None)
        stiker_idx = a.get("stiker_photo_index")
        stiker_url = photos[stiker_idx] if stiker_idx is not None and photos and stiker_idx < len(photos) else None
        # Fallback GridFS: aset hasil migrasi (photos kosong) — ambil blob pada
        # indeks yang sama (di-clamp), downscale 640px agar WeasyPrint hemat
        # memori. Gagal → photo_url "" (template menampilkan "No Foto").
        if not photos:
            try:
                gids = [g for g in (a.get("photo_gridfs_ids") or []) if g]
                if gids and not photo_url:
                    gidx = max(0, min(int(cover_idx), len(gids) - 1))
                    photo_url = await _gridfs_photo_data_uri(gids[gidx]) or ""
                if gids and not stiker_url and stiker_idx is not None:
                    sidx = max(0, min(int(stiker_idx), len(gids) - 1))
                    stiker_url = await _gridfs_photo_data_uri(gids[sidx]) or None
            except Exception as e:
                logger.debug(f"[reports] fallback GridFS aset {a.get('id')} gagal: {e}")
                photo_url = photo_url or ""

        inv_status = a.get("inventory_status") or "Belum Diinventarisasi"
        condition = a.get("condition", "") or ""
        cond_badge, cond_class = "", ""
        if inv_status == "Ditemukan" and condition:
            cond_map = {"Baik": ("Baik", "badge-baik"), "Rusak Ringan": ("R.Ringan", "badge-ringan"), "Rusak Berat": ("R.Berat", "badge-berat")}
            if condition in cond_map:
                cond_badge, cond_class = cond_map[condition]
        stat_map = {"Ditemukan": ("Ditemukan", "badge-ditemukan"), "Tidak Ditemukan": ("Tidak Ditemukan", "badge-tidak"), "Berlebih": ("Berlebih", "badge-berlebih"), "Sengketa": ("Sengketa", "badge-sengketa")}
        stat_badge, stat_class = stat_map.get(inv_status, (inv_status, ""))

        # status_detail is server-built HTML (marked Markup below so autoescape
        # leaves the wrapper tags intact). The interpolated USER values are still
        # escaped individually via markupsafe.escape so a crafted asset field
        # (e.g. pihak_bersengketa="<script>") can't inject markup.
        from markupsafe import escape as _esc
        detail_parts = []
        if inv_status == "Tidak Ditemukan":
            klas = a.get("klasifikasi_tidak_ditemukan", "")
            sub = a.get("sub_klasifikasi", "")
            if klas: detail_parts.append(f'<div class="cell-sub"><span class="label">Klasifikasi:</span> {_esc(klas)}</div>')
            if sub: detail_parts.append(f'<div class="cell-sub"><span class="label">Sub:</span> {_esc(sub)}</div>')
        elif inv_status == "Berlebih":
            asal = a.get("asal_usul_berlebih", "")
            if asal: detail_parts.append(f'<div class="cell-sub"><span class="label">Asal:</span> {_esc(asal)}</div>')
        elif inv_status == "Sengketa":
            perkara = a.get("nomor_perkara", "")
            pihak = a.get("pihak_bersengketa", "")
            if perkara: detail_parts.append(f'<div class="cell-sub"><span class="label">Perkara:</span> {_esc(perkara)}</div>')
            if pihak: detail_parts.append(f'<div class="cell-sub"><span class="label">Pihak:</span> {_esc(pihak)}</div>')
        if inv_status == "Ditemukan" and condition == "Rusak Berat":
            tl = a.get("tindak_lanjut", "")
            if tl: detail_parts.append(f'<div class="cell-sub"><span class="label">Tindak Lanjut:</span> {_esc(tl)}</div>')

        # Kolom tambahan opsional (di-toggle via query param detail_fields)
        for key, label, field in EXEC_DETAIL_FIELDS:
            if key in detail_fields:
                val = a.get(field, "") or ""
                if val: detail_parts.append(f'<div class="cell-sub"><span class="label">{_esc(label)}:</span> {_esc(val)}</div>')

        doc_ck = a.get("document_checklist", []) or []
        checked = [d.get("name", "") for d in doc_ck if d.get("checked")]
        kelengkapan = ", ".join(checked) if checked else "-"
        year = a.get("purchase_date", "") or ""
        if len(str(year)) >= 4: year = str(year)[:4]
        lat = a.get("koordinat_latitude", "") or ""
        lng = a.get("koordinat_longitude", "") or ""
        coords = f"{lat}, {lng}" if lat and lng else ""
        brand = a.get("brand", "") or ""
        model = a.get("model", "") or ""

        asset_rows.append({
            "asset_code": a.get("asset_code", "-"), "nup": a.get("NUP", "-"),
            "category_label": cat_map.get(a.get("category", ""), a.get("category", "-")) or "-",
            "asset_name": a.get("asset_name", "-") or "-", "brand_model": f"{brand} {model}".strip() or "-",
            "eselon1": a.get("eselon1", "") or "", "eselon2": a.get("eselon2", "") or "",

            "year": year or "-", "value_fmt": fmt(sp(a)),
            "condition_badge": cond_badge, "condition_badge_class": cond_class,
            "status_badge": stat_badge, "status_badge_class": stat_class,
            "status_detail": Markup("\n".join(detail_parts)) if detail_parts else "",
            "location": a.get("location", "") or "-", "user": a.get("user", "") or "-",
            "coords": coords, "kelengkapan": kelengkapan,
            "notes": (a.get("notes", "") or a.get("kronologis", "") or "-"),
            "photo_url": photo_url, "stiker_url": stiker_url,
        })

    items_per_page = 140  # 70 per kolom * 2 kolom — selaras template (>=148 meluber)
    cat_pages = max(0, -(-len(cat_chart) // items_per_page)) if cat_chart else 0
    loc_pages = max(0, -(-len(loc_chart) // items_per_page)) if loc_chart else 0

    # Split asset rows into pages (max 18 per page to avoid WeasyPrint table-break bug)
    assets_per_page = 18
    asset_pages = []
    for i in range(0, len(asset_rows), assets_per_page):
        asset_pages.append(asset_rows[i:i + assets_per_page])

    # Halaman template ringkasan: 1 sampul + 1 ringkasan + halaman kategori +
    # halaman lokasi + 1 analisis lanjutan/tim. Data per aset TIDAK ada di
    # template ini (diunduh terpisah via executive-data-pdf) — dulu ikut
    # dihitung sehingga "Halaman 2 dari N" selalu terlalu besar.
    total_pages = 3 + cat_pages + loc_pages

    return {
        "logo_url": settings.get("logo_url", ""),
        "nama_instansi": settings.get("nama_instansi", ""),
        "nama_unit": settings.get("nama_unit_organisasi", ""),
        "alamat_instansi": str(settings.get("alamat_instansi", "") or "").replace("\n", " • "),
        "tahun_anggaran": settings.get("tahun_anggaran", ""),
        "satker_name": satker_name,
        "nomor_sk": activity.get("nomor_surat") or "-",
        "tgl_mulai": _fmt_tanggal_id(activity.get("tanggal_mulai")) or "-",
        "tgl_selesai": _fmt_tanggal_id(activity.get("tanggal_selesai")) or "-",
        "tanggal_cetak": _fmt_tanggal_id(datetime.now()),
        "total_count": tc, "total_value_fmt": fmt(tv),
        "cnt_ditemukan": len(ditemukan), "val_ditemukan_fmt": fmt(sum(sp(a) for a in ditemukan)), "pct_ditemukan": pct(len(ditemukan), tc),
        "cnt_tidak": len(tidak), "val_tidak_fmt": fmt(sum(sp(a) for a in tidak)), "pct_tidak": pct(len(tidak), tc),
        "cnt_berlebih": len(berlebih), "val_berlebih_fmt": fmt(sum(sp(a) for a in berlebih)), "pct_berlebih": pct(len(berlebih), tc),
        "cnt_sengketa": len(sengketa), "val_sengketa_fmt": fmt(sum(sp(a) for a in sengketa)), "pct_sengketa": pct(len(sengketa), tc),
        "cnt_belum": len(belum), "val_belum_fmt": fmt(sum(sp(a) for a in belum)), "pct_belum": pct(len(belum), tc),
        "cnt_baik": len(baik), "val_baik_fmt": fmt(sum(sp(a) for a in baik)), "pct_baik": pct(len(baik), tc),
        "cnt_rusak_ringan": len(rr), "val_rusak_ringan_fmt": fmt(sum(sp(a) for a in rr)), "pct_rusak_ringan": pct(len(rr), tc),
        "cnt_rusak_berat": len(rb), "val_rusak_berat_fmt": fmt(sum(sp(a) for a in rb)), "pct_rusak_berat": pct(len(rb), tc),
        "cnt_td_kes": len(td_kes), "val_td_kes_fmt": fmt(sum(sp(a) for a in td_kes)), "pct_td_kes": pct(len(td_kes), tc),
        "cnt_td_lain": len(td_lain), "val_td_lain_fmt": fmt(sum(sp(a) for a in td_lain)), "pct_td_lain": pct(len(td_lain), tc),
        "pct_baik_of_found": round(len(baik) / len(ditemukan) * 100, 1) if len(ditemukan) > 0 else 0,
        "pct_rr_of_found": round(len(rr) / len(ditemukan) * 100, 1) if len(ditemukan) > 0 else 0,
        "pct_rb_of_found": round(len(rb) / len(ditemukan) * 100, 1) if len(ditemukan) > 0 else 0,
        "stiker_terpasang": st_terpasang, "stiker_belum": st_belum, "stiker_pct": st_pct,
        "stiker_dash": f"{circumference:.2f}", "stiker_offset": f"{st_offset:.2f}",
        # simpulan[].text is trusted server-built HTML (only counts/percentages
        # interpolated) → Markup so autoescape keeps the <strong> tags.
        "simpulan": [{**s, "text": Markup(s["text"])} for s in simpulan],
        "tim": tim, "tim_pendukung": tim_pendukung,
        "tim_inti": tim_inti, "tim_pembantu": tim_pembantu,
        "pj_nama": pj_nama, "pj_jabatan": pj_jabatan, "pj_nip": pj_nip,
        "assets": asset_rows, "asset_pages": asset_pages, "total_pages": total_pages,
        "asset_count": len(all_assets),
        "is_in_progress": is_in_progress,
        "cat_breakdown": cat_breakdown_sorted,
        "loc_breakdown": loc_breakdown_sorted,
        "eselon1_breakdown": eselon1_breakdown_sorted,
        "year_breakdown": year_breakdown_sorted,
        "doc_completeness_pct": doc_completeness_pct,
        "photo_coverage_pct": photo_coverage_pct,
        "gps_coverage_pct": gps_coverage_pct,
        "assets_with_photos": assets_with_photos,
        "assets_with_gps": assets_with_gps,
        "cat_chart": cat_chart,
        "loc_chart": loc_chart,
        "year_chart": year_chart,
        "eselon_chart": eselon_chart,
        "status_pie": status_pie,
        "condition_pie": condition_pie,
        "cond_by_cat": cond_by_cat,
    }


@reports_router.get("/inventory-activities/{activity_id}/executive-summary-html")
async def executive_summary_html(activity_id: str, detail_fields: str = "",
                                 _user: dict = Depends(require_user_or_query_token)):
    """Serve Executive Summary as interactive HTML preview with real data"""
    from jinja2 import Environment, FileSystemLoader
    data = await _build_executive_summary_data(activity_id, _parse_detail_fields(detail_fields),
                                               with_asset_rows=False)
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    data["preview"] = True
    env = _jinja_env()
    template = env.get_template("executive_summary.html")
    html = template.render(**data)
    return HTMLResponse(content=html)


@reports_router.get("/inventory-activities/{activity_id}/executive-summary-pdf")
async def generate_executive_summary_pdf(activity_id: str, detail_fields: str = "",
                                         _user: dict = Depends(require_user_or_query_token)):
    """Generate Executive Summary PDF (Part 1: Summary only, no data detail)."""
    from jinja2 import Environment, FileSystemLoader
    import weasyprint

    data = await _build_executive_summary_data(activity_id, _parse_detail_fields(detail_fields),
                                               with_asset_rows=False)
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    data["preview"] = False

    env = _jinja_env()

    # Render summary pages only (no asset data pages)
    summary_data = {**data, "asset_pages": [], "assets": []}
    template = env.get_template("executive_summary.html")
    html = template.render(**summary_data)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    filename = f"Laporan_Eksekutif_{activity_id[:8]}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@reports_router.get("/inventory-activities/{activity_id}/executive-data-pdf")
async def generate_executive_data_pdf(activity_id: str, page: int = 1, detail_fields: str = "",
                                      _user: dict = Depends(require_user_or_query_token)):
    """Generate Executive Summary Data PDF (Part 2: Asset detail pages).

    Each page contains up to 499 assets. page=1 -> assets 1-499, page=2 -> 500-998, etc.
    """
    from jinja2 import Environment, FileSystemLoader
    import weasyprint

    data = await _build_executive_summary_data(activity_id, _parse_detail_fields(detail_fields))
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    items_per_download = 499
    all_assets = data.get("assets", [])
    total_assets = len(all_assets)
    total_data_pages = max(1, -(-total_assets // items_per_download))

    if page < 1 or page > total_data_pages:
        raise HTTPException(status_code=400, detail=f"Halaman {page} tidak valid. Total: {total_data_pages}")

    start_idx = (page - 1) * items_per_download
    end_idx = min(start_idx + items_per_download, total_assets)
    chunk_assets = all_assets[start_idx:end_idx]

    env = _jinja_env()
    template = env.get_template("executive_summary_data.html")
    html = template.render(
        chunk_assets=chunk_assets,
        total_chunk=len(chunk_assets),
        total_all=total_assets,
        satker_name=data["satker_name"],
        total_value_fmt=data["total_value_fmt"],
        global_offset=start_idx,
        data_page_num=page,
        total_data_pages=total_data_pages,
    )
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    filename = f"Data_Aset_{start_idx+1}-{end_idx}_{activity_id[:8]}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@reports_router.get("/inventory-activities/{activity_id}/executive-data-info")
async def executive_data_info(activity_id: str, detail_fields: str = "",
                              _user: dict = Depends(require_user_or_query_token)):
    """Return info about how many data download pages are available."""
    data = await _build_executive_summary_data(activity_id, _parse_detail_fields(detail_fields),
                                               with_asset_rows=False)
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    total_assets = data.get("asset_count", 0)
    items_per_download = 499
    total_pages = max(0, -(-total_assets // items_per_download)) if total_assets > 0 else 0
    
    pages = []
    for p in range(1, total_pages + 1):
        start = (p - 1) * items_per_download + 1
        end = min(p * items_per_download, total_assets)
        pages.append({"page": p, "start": start, "end": end, "count": end - start + 1})
    
    return {"total_assets": total_assets, "total_pages": total_pages, "pages": pages}


# ============================================================================
# EXECUTIVE GROUPED REPORT (Barang Serupa) - HTML preview + PDF via weasyprint
# ============================================================================

def _compact_nup_ranges(nups):
    """Compact NUP list into ranges, e.g. ['1','2','3','5','7'] -> '1-3, 5, 7'.

    NUP numerik diurutkan & run berurutan digabung; NUP non-numerik di akhir.
    """
    numeric, non_numeric = [], []
    for n in nups:
        s = str(n).strip() if n is not None else ""
        if not s:
            continue
        try:
            numeric.append(int(s))
        except ValueError:
            non_numeric.append(s)
    parts = []
    start = prev = None
    for n in sorted(set(numeric)):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            parts.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = n
    if start is not None:
        parts.append(str(start) if start == prev else f"{start}-{prev}")
    parts.extend(sorted(set(non_numeric)))
    return ", ".join(parts) if parts else "-"


async def _build_executive_grouped_data(activity_id: str, detail_fields=None):
    """Build data for Laporan Eksekutif per Barang Serupa (grouped assets).

    Group key sama dengan /api/assets/groups (batch.py) TAPI tanpa filter
    count>=2 dan tanpa limit — aset tunggal jadi kelompok sendiri sehingga
    jumlah unit seluruh kelompok = total aset kegiatan.

    detail_fields: optional set of EXEC_DETAIL_FIELDS keys — per kelompok,
    nilai DISTINCT anggota untuk field tersebut ditampilkan sebagai baris
    tambahan di bawah Nama Barang (maks 3 nilai, sisanya "+N lainnya").
    """
    detail_fields = detail_fields or set()
    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        return None
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    categories = await db.categories.find({}, {"_id": 0}).to_list(10000)
    cat_map = {c.get("kode_aset", ""): c.get("label", "") for c in categories}

    def sp(v):
        try: return float(v or 0)
        except (ValueError, TypeError): return 0.0
    def fmt(v):
        try: return f"{int(v):,}".replace(",", ".")
        except (ValueError, TypeError): return "0"

    pipeline = [
        {"$match": {"activity_id": activity_id}},
        {"$group": {
            "_id": {
                "asset_code": {"$ifNull": ["$asset_code", ""]},
                "asset_name": {"$ifNull": ["$asset_name", ""]},
                "purchase_date": {"$ifNull": ["$purchase_date", ""]},
                "brand": {"$ifNull": ["$brand", ""]},
                "model": {"$ifNull": ["$model", ""]},
                "purchase_price": {"$ifNull": ["$purchase_price", 0]}
            },
            "count": {"$sum": 1},
            "members": {"$push": {
                "id": "$id",
                "NUP": "$NUP",
                "condition": "$condition",
                "inventory_status": "$inventory_status",
                "category": "$category",
                "purchase_price": "$purchase_price",
                "nomor_spm": "$nomor_spm",
                "perolehan_dari_nama": "$perolehan_dari_nama",
                "nomor_kontrak": "$nomor_kontrak",
                "nomor_bukti_perolehan": "$nomor_bukti_perolehan",
                "supplier": "$supplier",
                "serial_number": "$serial_number",
            }}
        }},
        {"$sort": {"_id.asset_code": 1, "_id.asset_name": 1, "_id.purchase_date": 1}},
    ]
    raw_groups = []
    async for doc in db.assets.aggregate(pipeline):
        raw_groups.append(doc)

    def nup_key(m):
        """Sort key: NUP numerik terkecil dulu, non-numerik di akhir"""
        s = str(m.get("NUP", "") or "").strip()
        try:
            return (0, int(s), "")
        except ValueError:
            return (1, 0, s)

    # Representative per group = member dengan NUP numerik terkecil
    rep_ids = []
    for g in raw_groups:
        rep = min(g["members"], key=nup_key)
        g["rep_id"] = rep.get("id")
        if g["rep_id"]:
            rep_ids.append(g["rep_id"])

    # Batch-fetch foto sampul representative (satu query, hanya 1 foto per aset)
    photo_map = {}
    gid_map = {}  # Fallback GridFS: id blob sampul per aset (aset hasil migrasi)
    if rep_ids:
        photo_pipeline = [
            {"$match": {"id": {"$in": rep_ids}}},
            {"$project": {"_id": 0, "id": 1, "cover_photo": {"$let": {
                "vars": {"ph": {"$ifNull": ["$photos", []]}, "ti": {"$ifNull": ["$thumbnail_index", 0]}},
                "in": {"$cond": [
                    {"$and": [{"$gte": ["$$ti", 0]}, {"$lt": ["$$ti", {"$size": "$$ph"}]}]},
                    {"$arrayElemAt": ["$$ph", "$$ti"]},
                    {"$arrayElemAt": ["$$ph", 0]},
                ]},
            }},
            # GridFS-aware: proyeksikan juga id blob sampul dari photo_gridfs_ids
            # dengan pemilihan indeks yang sama seperti cover_photo di atas.
            "cover_gid": {"$let": {
                "vars": {"gd": {"$ifNull": ["$photo_gridfs_ids", []]}, "ti": {"$ifNull": ["$thumbnail_index", 0]}},
                "in": {"$cond": [
                    {"$and": [{"$gte": ["$$ti", 0]}, {"$lt": ["$$ti", {"$size": "$$gd"}]}]},
                    {"$arrayElemAt": ["$$gd", "$$ti"]},
                    {"$arrayElemAt": ["$$gd", 0]},
                ]},
            }}}},
        ]
        async for d in db.assets.aggregate(photo_pipeline):
            photo_map[d["id"]] = d.get("cover_photo")
            gid_map[d["id"]] = d.get("cover_gid")

    cond_abbr = [("Baik", "Baik"), ("Rusak Ringan", "RR"), ("Rusak Berat", "RB")]
    stat_abbr = [("Ditemukan", "Ditemukan"), ("Tidak Ditemukan", "Tdk Ditemukan"),
                 ("Berlebih", "Berlebih"), ("Sengketa", "Sengketa"),
                 ("Belum Diinventarisasi", "Belum")]

    rows = []
    total_units = 0
    total_value = 0.0
    for g in raw_groups:
        key = g["_id"]
        members = g["members"]
        count = g["count"]
        group_value = sum(sp(m.get("purchase_price")) for m in members)
        total_units += count
        total_value += group_value

        cond_counts = {}
        stat_counts = {}
        for m in members:
            c = m.get("condition") or ""
            if c: cond_counts[c] = cond_counts.get(c, 0) + 1
            s = m.get("inventory_status") or "Belum Diinventarisasi"
            stat_counts[s] = stat_counts.get(s, 0) + 1
        kondisi = ", ".join(f"{cond_counts[name]} {abbr}" for name, abbr in cond_abbr if cond_counts.get(name))
        status = ", ".join(f"{stat_counts[name]} {abbr}" for name, abbr in stat_abbr if stat_counts.get(name))

        brand_model = f"{key.get('brand', '')} {key.get('model', '')}".strip()
        year = str(key.get("purchase_date", ""))[:4] if key.get("purchase_date") else ""
        category = members[0].get("category", "") if members else ""

        # Baris detail opsional (di-toggle via query param detail_fields):
        # nilai DISTINCT antar anggota, maks 3 ditampilkan lalu "+N lainnya"
        detail_lines = []
        for dkey, dlabel, dfield in EXEC_DETAIL_FIELDS:
            if dkey not in detail_fields:
                continue
            distinct = []
            for m in members:
                val = str(m.get(dfield) or "").strip()
                if val and val not in distinct:
                    distinct.append(val)
            if not distinct:
                continue
            value = ", ".join(distinct[:3])
            if len(distinct) > 3:
                value += f" +{len(distinct) - 3} lainnya"
            detail_lines.append({"label": dlabel, "value": value})

        # Foto sampul kelompok: foto inline (cover_photo) lebih murah, jadi
        # dipakai lebih dulu; bila kosong tapi ada cover_gid (aset migrasi
        # GridFS-only) → ambil blob dari GridFS + downscale 640px ke data-URI.
        rep_id = g.get("rep_id")
        cover_url = photo_map.get(rep_id)
        if not cover_url and gid_map.get(rep_id):
            cover_url = await _gridfs_photo_data_uri(gid_map[rep_id]) or None

        rows.append({
            "asset_code": key.get("asset_code") or "-",
            "category_label": cat_map.get(category, category) or "-",
            "asset_name": key.get("asset_name") or "-",
            "brand_model": brand_model or "-",
            "year": year or "-",
            "nup_range": _compact_nup_ranges([m.get("NUP") for m in members]),
            "count": count,
            "unit_price_fmt": fmt(sp(key.get("purchase_price"))),
            "group_value_fmt": fmt(group_value),
            "kondisi_summary": kondisi or "-",
            "status_summary": status or "-",
            "photo_url": cover_url,
            "detail_lines": detail_lines,
        })

    satker_name = _activity_identity(activity, settings)["satker_name"]

    return {
        "logo_url": settings.get("logo_url", ""),
        "judul_laporan": settings.get("judul_laporan", "") or "LAPORAN HASIL INVENTARISASI",
        "nama_instansi": settings.get("nama_instansi", ""),
        "satker_name": satker_name,
        "nomor_sk": activity.get("nomor_surat", "-"),
        "tanggal_cetak": _fmt_tanggal_id(datetime.now()),
        "rows": rows,
        "total_groups": len(rows),
        "total_units": total_units,
        "total_value_fmt": fmt(total_value),
    }


@reports_router.get("/inventory-activities/{activity_id}/executive-grouped-html")
async def executive_grouped_html(activity_id: str, detail_fields: str = "",
                                 _user: dict = Depends(require_user_or_query_token)):
    """Serve Laporan Eksekutif per Barang Serupa as HTML preview"""
    from jinja2 import Environment, FileSystemLoader
    data = await _build_executive_grouped_data(activity_id, _parse_detail_fields(detail_fields))
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    env = _jinja_env()
    template = env.get_template("executive_grouped.html")
    html = template.render(**data)
    return HTMLResponse(content=html)


@reports_router.get("/inventory-activities/{activity_id}/executive-grouped-pdf")
async def generate_executive_grouped_pdf(activity_id: str, detail_fields: str = "",
                                         _user: dict = Depends(require_user_or_query_token)):
    """Generate Laporan Eksekutif per Barang Serupa (grouped assets) PDF"""
    from jinja2 import Environment, FileSystemLoader
    import weasyprint

    data = await _build_executive_grouped_data(activity_id, _parse_detail_fields(detail_fields))
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    env = _jinja_env()
    template = env.get_template("executive_grouped.html")
    html = template.render(**data)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    filename = "Laporan_Eksekutif_Barang_Serupa.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============================================================================
# LAPORAN PER SATKER - Full Report with Cover, Analysis, Data
# ============================================================================

async def _build_satker_report_v2(activity_id: str):
    """Build data for per-satker report — aggregates ALL activities with same kode_satker"""
    source_act = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not source_act:
        return None
    kode_satker = source_act.get("kode_satker", "")
    if not kode_satker:
        satker_acts = [source_act]
    else:
        satker_acts = await db.inventory_activities.find({"kode_satker": kode_satker}, {"_id": 0}).sort("created_at", -1).to_list(100)

    act_ids = [a.get("id") for a in satker_acts if a.get("id")]
    # proyeksi: buang media base64 yang tidak dipakai laporan ini (hemat memori/IO);
    # 'document_checklist' TETAP diambil (statistik & tabel kelengkapan dokumen)
    all_assets = await db.assets.find(
        {"activity_id": {"$in": act_ids}},
        {"_id": 0, "photos": 0, "photo": 0, "photo_thumbnails": 0, "thumbnail": 0, "gallery_thumbnail": 0},
    ).to_list(100000)
    categories = await db.categories.find({}, {"_id": 0}).to_list(10000)
    cat_map = {c.get("kode_aset", ""): c.get("label", "") for c in categories}
    act_name_map = {a.get("id", ""): (a.get("nama_kegiatan") or "") for a in satker_acts}

    def sp(a):
        try: return float(a.get("purchase_price", 0) or 0)
        except: return 0.0
    def fmt(v):
        try: return f"{int(v):,}".replace(",", ".")
        except: return "0"
    def pct(part, total):
        return round(part / total * 100, 1) if total > 0 else 0

    tc = len(all_assets)
    tv = sum(sp(a) for a in all_assets)
    ditemukan = [a for a in all_assets if a.get("inventory_status") == "Ditemukan"]
    tidak = [a for a in all_assets if a.get("inventory_status") == "Tidak Ditemukan"]
    berlebih = [a for a in all_assets if a.get("inventory_status") == "Berlebih"]
    sengketa = [a for a in all_assets if a.get("inventory_status") == "Sengketa"]
    belum = [a for a in all_assets if (a.get("inventory_status") or "Belum Diinventarisasi") == "Belum Diinventarisasi"]
    baik = [a for a in ditemukan if a.get("condition") == "Baik"]
    rr = [a for a in ditemukan if a.get("condition") == "Rusak Ringan"]
    rb = [a for a in ditemukan if a.get("condition") == "Rusak Berat"]
    st_terpasang = len([a for a in ditemukan if a.get("stiker_status") == "Sudah Terpasang"])
    st_pct = int(st_terpasang / len(ditemukan) * 100) if ditemukan else 0
    dok_scores = []
    for a in all_assets:
        ck = a.get("document_checklist", []) or []
        if ck:
            checked = sum(1 for d in ck if d.get("checked"))
            dok_scores.append(checked / len(ck) * 100)
    dok_pct = round(sum(dok_scores) / len(dok_scores), 1) if dok_scores else 0

    # Charts
    cond_colors = {"Baik": "#059669", "Rusak Ringan": "#d97706", "Rusak Berat": "#dc2626"}
    chart_kondisi = [{"name": n, "count": len(i), "pct": pct(len(i), len(ditemukan)) if ditemukan else 0, "color": cond_colors.get(n, "#64748b")} for n, i in [("Baik", baik), ("Rusak Ringan", rr), ("Rusak Berat", rb)]]
    stat_colors = {"Ditemukan": "#2563eb", "Tidak Ditemukan": "#dc2626", "Berlebih": "#d97706", "Sengketa": "#7c3aed", "Belum": "#94a3b8"}
    chart_status = [{"name": n, "count": len(i), "pct": pct(len(i), tc), "color": stat_colors.get(n, "#64748b")} for n, i in [("Ditemukan", ditemukan), ("Tidak Ditemukan", tidak), ("Berlebih", berlebih), ("Sengketa", sengketa), ("Belum", belum)] if i]

    from collections import Counter
    cat_counter = Counter((a.get("category") or "Lainnya") for a in all_assets)
    cat_vals = {}
    for a in all_assets:
        c = a.get("category") or "Lainnya"
        cat_vals[c] = cat_vals.get(c, 0) + sp(a)
    chart_kategori = [{"name": (cat_map.get(c, c) or c)[:20], "count": cnt, "pct": pct(cnt, tc), "val_fmt": fmt(cat_vals.get(c, 0))} for c, cnt in cat_counter.most_common(10)]

    loc_counter = Counter(a.get("location", "-") or "-" for a in all_assets)
    chart_lokasi = [{"name": l[:20], "count": cnt, "pct": pct(cnt, tc)} for l, cnt in loc_counter.most_common(10)]

    es1_counter = Counter(a.get("eselon1", "") for a in all_assets if a.get("eselon1"))
    es1_vals = {}
    for a in all_assets:
        e = a.get("eselon1", "")
        if e: es1_vals[e] = es1_vals.get(e, 0) + sp(a)
    chart_eselon1 = [{"name": e[:25], "count": cnt, "pct": pct(cnt, tc), "val_fmt": fmt(es1_vals.get(e, 0))} for e, cnt in es1_counter.most_common(10)]

    # Per kegiatan chart
    act_counter = Counter(a.get("activity_id", "") for a in all_assets)
    act_vals = {}
    for a in all_assets:
        aid = a.get("activity_id", "")
        act_vals[aid] = act_vals.get(aid, 0) + sp(a)
    chart_per_kegiatan = [{"name": (act_name_map.get(aid) or aid or "-")[:25], "count": cnt, "pct": pct(cnt, tc), "val_fmt": fmt(act_vals.get(aid, 0))} for aid, cnt in act_counter.most_common(10)]

    # Asset rows
    cond_map = {"Baik": ("Baik", "b-ok"), "Rusak Ringan": ("R.Ringan", "b-rr"), "Rusak Berat": ("R.Berat", "b-rb")}
    stat_map = {"Ditemukan": ("Ditemukan", "b-found"), "Tidak Ditemukan": ("Tdk Ditemukan", "b-miss"), "Berlebih": ("Berlebih", "b-extra"), "Sengketa": ("Sengketa", "b-dispute"), "Belum Diinventarisasi": ("Belum", "b-pending")}
    asset_rows = []
    for a in all_assets:
        inv = a.get("inventory_status") or "Belum Diinventarisasi"
        cond = a.get("condition", "") or ""
        cb, cc = cond_map.get(cond, ("", "")) if inv == "Ditemukan" and cond else ("", "")
        sb, sc = stat_map.get(inv, (inv, ""))
        year = str(a.get("purchase_date", "") or "")[:4]
        brand = a.get("brand", "") or ""
        model = a.get("model", "") or ""
        cat_raw = a.get("category") or ""
        asset_rows.append({
            "asset_code": a.get("asset_code") or "-", "nup": a.get("NUP") or "-",
            "asset_name": a.get("asset_name") or "-",
            "category": cat_map.get(cat_raw, cat_raw) or "-",
            "brand_model": f"{brand} {model}".strip() or "-",
            "eselon1": a.get("eselon1") or "", "eselon2": a.get("eselon2") or "",
            "location": a.get("location") or "-", "year": year or "-", "value_fmt": fmt(sp(a)),
            "cond_badge": cb, "cond_cls": cc, "stat_badge": sb, "stat_cls": sc,
            "stiker": a.get("stiker_status") or "Belum Terpasang",
            "kegiatan_nama": (act_name_map.get(a.get("activity_id", "")) or "-")[:20],
        })

    # Dok rows
    dok_headers_set = set()
    for a in all_assets:
        for d in (a.get("document_checklist", []) or []):
            dok_headers_set.add(d.get("name", ""))
    dok_headers = sorted(dok_headers_set)
    dok_rows = []
    # Hanya aset yang PUNYA data checklist — baris semua-x untuk aset tanpa
    # checklist menyesatkan (tak terbedakan dari "tidak ada yang dicentang").
    dok_eligible = [a for a in all_assets if (a.get("document_checklist") or [])]
    for a in dok_eligible[:100]:
        ck = {d.get("name", ""): d.get("checked", False) for d in (a.get("document_checklist", []) or [])}
        checks = [ck.get(h, False) for h in dok_headers]
        score = sum(1 for c in checks if c)
        dok_rows.append({"code": a.get("asset_code") or "-", "name": (a.get("asset_name") or "-")[:30], "checks": checks, "score": score, "total": len(dok_headers)})
    dok_note_parts = []
    if len(dok_eligible) > 100:
        dok_note_parts.append(f"menampilkan 100 pertama dari {len(dok_eligible)} aset")
    if len(dok_eligible) < tc:
        dok_note_parts.append(f"{tc - len(dok_eligible)} aset tanpa data kelengkapan tidak ditampilkan")
    dok_note = "; ".join(dok_note_parts)

    # Eselon list (from first activity that has data, or merge)
    eselon_list = []
    for act in satker_acts:
        for es in (act.get("eselon1", []) or []):
            if isinstance(es, dict):
                eselon_list.append({"nama": es.get("nama", ""), "eselon2": es.get("eselon2", [])})
            elif isinstance(es, str) and es:
                eselon_list.append({"nama": es, "eselon2": []})
        if eselon_list:
            break

    # Kegiatan list
    kegiatan_list = []
    for act in satker_acts:
        aid = act.get("id", "")
        act_assets = [a for a in all_assets if a.get("activity_id") == aid]
        kegiatan_list.append({
            "nomor_surat": act.get("nomor_surat", "-"),
            "nama_kegiatan": act.get("nama_kegiatan", "-"),
            "periode": f"{_fmt_tanggal_id(act.get('tanggal_mulai')) or '-'} s/d {_fmt_tanggal_id(act.get('tanggal_selesai')) or '-'}",
            "pj": act.get("penanggung_jawab") or "-",
            "count": len(act_assets),
            "value_fmt": fmt(sum(sp(a) for a in act_assets)),
        })

    # Personil (highest rank first)
    personil = []
    seen_names = set()
    kasatker_added = False
    for act in satker_acts:
        if act.get("kasatker_nama") and act["kasatker_nama"] not in seen_names:
            if not kasatker_added:
                personil.append({"is_header": True, "section": "Pimpinan Satuan Kerja"})
                kasatker_added = True
            personil.append({"is_header": False, "primary": True, "role": act.get("kasatker_jabatan") or "Kuasa Pengguna Barang", "name": act["kasatker_nama"], "nip": act.get("kasatker_nip") or "", "jabatan": ""})
            seen_names.add(act["kasatker_nama"])

    pj_added = False
    for act in satker_acts:
        if act.get("penanggung_jawab") and act["penanggung_jawab"] not in seen_names:
            if not pj_added:
                personil.append({"is_header": True, "section": "Penanggung Jawab Inventarisasi"})
                pj_added = True
            personil.append({"is_header": False, "primary": False, "role": f"PJ — {(act.get('nama_kegiatan') or '')[:40]}", "name": act["penanggung_jawab"], "nip": "", "jabatan": ""})
            seen_names.add(act["penanggung_jawab"])

    def _tambah_tim(field, section_label, role_label):
        """Semua tim masuk daftar personil; anggota string era lama dinormalkan
        via _member_dict (dulu dibuang diam-diam oleh filter isinstance)."""
        added = False
        for act in satker_acts:
            for t in map(_member_dict, act.get(field, []) or []):
                nama = t.get("nama")
                if nama and nama not in seen_names:
                    if not added:
                        personil.append({"is_header": True, "section": section_label})
                        added = True
                    personil.append({"is_header": False, "primary": False, "role": role_label,
                                     "name": nama, "nip": t.get("nip") or "", "jabatan": t.get("jabatan") or ""})
                    seen_names.add(nama)

    # Dulu bagian ini hanya memuat tim eksternal — Tim Inti & Tim Pembantu
    # (pelaksana internal) tidak pernah muncul di "Personil Terlibat".
    _tambah_tim("tim_inti", "Tim Inti (Pelaksana)", "Anggota Tim Inti")
    _tambah_tim("tim_pembantu", "Tim Pembantu", "Tim Pembantu")
    _tambah_tim("tim_peneliti", "Tim Peneliti", "Anggota Tim")
    _tambah_tim("tim_pendukung", "Tim Pendukung", "Pendukung")

    # Simpulan
    simpulan = []
    if tc > 0:
        simpulan.append({"color": "#1e40af", "text": f"Dari <strong>{tc} NUP</strong> BMN senilai <strong>Rp {fmt(tv)}</strong>, sebanyak <strong>{pct(len(ditemukan), tc)}%</strong> berhasil ditemukan."})
        if tidak: simpulan.append({"color": "#dc2626", "text": f"<strong>{len(tidak)} NUP</strong> tidak ditemukan senilai <strong>Rp {fmt(sum(sp(a) for a in tidak))}</strong>."})
        if berlebih: simpulan.append({"color": "#d97706", "text": f"<strong>{len(berlebih)} NUP</strong> BMN berlebih senilai <strong>Rp {fmt(sum(sp(a) for a in berlebih))}</strong>."})
        if sengketa: simpulan.append({"color": "#7c3aed", "text": f"<strong>{len(sengketa)} NUP</strong> BMN dalam sengketa."})
        simpulan.append({"color": "#059669", "text": f"Stiker terpasang pada <strong>{st_terpasang} dari {len(ditemukan)}</strong> NUP (<strong>{st_pct}%</strong>)."})
        simpulan.append({"color": "#0ea5e9", "text": f"Rata-rata kelengkapan dokumen: <strong>{dok_pct}%</strong>."})

    return {
        "kode_satker": source_act.get("kode_satker") or "-",
        "nama_satker": source_act.get("nama_satker") or "-",
        "alamat_satker": source_act.get("alamat_satker") or "-",
        "tanggal_cetak": _fmt_tanggal_id(datetime.now()),
        "total_kegiatan": len(satker_acts), "total_count": tc, "total_value_fmt": fmt(tv),
        "cnt_ditemukan": len(ditemukan), "pct_ditemukan": pct(len(ditemukan), tc),
        "cnt_tidak": len(tidak), "pct_tidak": pct(len(tidak), tc),
        "cnt_berlebih": len(berlebih), "pct_berlebih": pct(len(berlebih), tc),
        "cnt_sengketa": len(sengketa), "pct_sengketa": pct(len(sengketa), tc),
        "cnt_belum": len(belum), "pct_belum": pct(len(belum), tc),
        "stiker_terpasang": st_terpasang, "stiker_pct": st_pct, "dok_pct": dok_pct,
        "eselon_list": eselon_list, "kegiatan_list": kegiatan_list,
        "chart_kondisi": chart_kondisi, "chart_status": chart_status,
        "chart_kategori": chart_kategori, "chart_lokasi": chart_lokasi,
        "chart_eselon1": chart_eselon1, "chart_per_kegiatan": chart_per_kegiatan,
        "assets": asset_rows, "dok_headers": dok_headers, "dok_rows": dok_rows,
        "dok_note": dok_note,
        "personil": personil,
        # Trusted server-built HTML → Markup so autoescape keeps the <strong> tags.
        "simpulan": [{**s, "text": Markup(s["text"])} for s in simpulan],
        "tim": [_member_dict(t) for act in satker_acts for t in (act.get("tim_peneliti", []) or [])],
        "tim_pendukung": [_member_dict(t) for act in satker_acts for t in (act.get("tim_pendukung", []) or [])],
        "tim_inti": [_member_dict(t) for act in satker_acts for t in (act.get("tim_inti", []) or [])],
        "tim_pembantu": [_member_dict(t) for act in satker_acts for t in (act.get("tim_pembantu", []) or [])],
        "kesimpulan": source_act.get("kesimpulan", ""),
    }


@reports_router.get("/inventory-activities/{activity_id}/laporan-satker-html")
async def laporan_satker_html(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Serve Laporan per Satker as interactive HTML preview - aggregates ALL activities for this satker"""
    from jinja2 import Environment, FileSystemLoader
    data = await _build_satker_report_v2(activity_id)
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    data["preview"] = True
    env = _jinja_env()
    template = env.get_template("laporan_satker_v2.html")
    html = template.render(**data)
    return HTMLResponse(content=html)


@reports_router.get("/inventory-activities/{activity_id}/laporan-satker-pdf")
async def laporan_satker_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate Laporan per Satker as PDF using weasyprint"""
    from jinja2 import Environment, FileSystemLoader
    import weasyprint
    data = await _build_satker_report_v2(activity_id)
    if not data:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    data["preview"] = False
    env = _jinja_env()
    template = env.get_template("laporan_satker_v2.html")
    html_content = template.render(**data)
    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
    output = io.BytesIO(pdf_bytes)
    filename = f"Laporan_Inventarisasi_{data['kode_satker']}_{activity_id[:8]}.pdf"
    return StreamingResponse(output, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============================================================================
# LHI - LAPORAN HASIL INVENTARISASI LENGKAP
# ============================================================================

async def _get_pdf_buffer_from_response(response):
    """Extract BytesIO buffer from StreamingResponse body_iterator"""
    content = b""
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            content += chunk
        else:
            content += chunk.encode()
    return io.BytesIO(content)


@reports_router.get("/inventory-activities/{activity_id}/lhi-pdf")
async def generate_lhi_pdf(activity_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Generate LHI (Laporan Hasil Inventarisasi BMN) - Complete package PDF
    Combines: Cover Page + BAHI + RHI + 6 DBHI + SP Hasil + SP Pelaksanaan
    """
    from PyPDF2 import PdfMerger

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    merger = PdfMerger()

    # 1. Cover page
    sections_added = 0
    try:
        cover_buffer = await _generate_cover_page(activity, settings)
        if cover_buffer.getbuffer().nbytes > 0:
            merger.append(cover_buffer)
            sections_added += 1
    except Exception as e:
        logger.warning(f"LHI: Failed to generate cover page: {e}")

    # 2. Generate all PDFs in order as per LKPP 85/2025
    pdf_sections = [
        ("BAHI", generate_bahi_pdf, {"activity_id": activity_id}),
        ("RHI", generate_rhi_pdf, {"activity_id": activity_id}),
        ("DBHI Kondisi Baik", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "kondisi-baik"}),
        ("DBHI Rusak Ringan", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "kondisi-rusak-ringan"}),
        ("DBHI Rusak Berat", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "kondisi-rusak-berat"}),
        ("DBHI Berlebih", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "berlebih"}),
        ("DBHI Tidak Ditemukan", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "tidak-ditemukan"}),
        ("DBHI Sengketa", generate_dbhi_pdf, {"activity_id": activity_id, "dbhi_type": "sengketa"}),
        ("SP Hasil", generate_sp_hasil_pdf, {"activity_id": activity_id}),
        ("SP Pelaksanaan", generate_sp_pelaksanaan_pdf, {"activity_id": activity_id}),
    ]

    for section_name, gen_func, kwargs in pdf_sections:
        try:
            response = await gen_func(**kwargs)
            pdf_buffer = await _get_pdf_buffer_from_response(response)
            if pdf_buffer.getbuffer().nbytes > 0:
                merger.append(pdf_buffer)
                sections_added += 1
        except Exception as e:
            logger.warning(f"LHI: Failed to generate {section_name}: {e}")
            continue

    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)

    if sections_added == 0:
        raise HTTPException(status_code=500, detail="Gagal generate LHI - tidak ada bagian yang berhasil dibuat")

    filename = f"LHI_Lengkap_{activity_id[:8]}.pdf"
    return StreamingResponse(output, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============================================================================
# BATCH PDF ZIP DOWNLOAD
# ============================================================================

class BatchPDFRequest(BaseModel):
    types: List[str]

BATCH_PDF_MAP = {
    "rhi": ("RHI", generate_rhi_pdf),
    "bahi": ("BAHI", generate_bahi_pdf),
    "sp-hasil": ("SP_Hasil", generate_sp_hasil_pdf),
    "sp-pelaksanaan": ("SP_Pelaksanaan", generate_sp_pelaksanaan_pdf),
    "berita-acara": ("Berita_Acara", generate_berita_acara_pdf),
    "sptjm": ("SPTJM", generate_sptjm_pdf),
    "surat-koreksi": ("Surat_Koreksi", generate_surat_koreksi_pdf),
    "executive-summary": ("Laporan_Eksekutif", generate_executive_summary_pdf),
    "dbkp": ("DBKP", generate_dbkp_pdf),
}

BATCH_DBHI_TYPES = [
    "kondisi-baik", "kondisi-rusak-ringan", "kondisi-rusak-berat",
    "berlebih", "tidak-ditemukan", "sengketa"
]


@reports_router.post("/inventory-activities/{activity_id}/batch-pdf-zip")
async def batch_download_pdf_zip(activity_id: str, request: BatchPDFRequest,
                                 _user: dict = Depends(require_user)):
    """Generate a ZIP file containing multiple selected PDF reports"""
    import zipfile

    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    if not request.types:
        raise HTTPException(status_code=400, detail="Pilih minimal satu laporan")

    zip_buffer = io.BytesIO()
    generated = []
    errors = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for report_type in request.types:
            try:
                if report_type.startswith("dbhi-"):
                    dbhi_type = report_type[5:]
                    if dbhi_type in BATCH_DBHI_TYPES:
                        response = await generate_dbhi_pdf(activity_id, dbhi_type)
                        pdf_buffer = await _get_pdf_buffer_from_response(response)
                        filename = f"DBHI_{dbhi_type.replace('-', '_')}_{activity_id[:8]}.pdf"
                        zf.writestr(filename, pdf_buffer.getvalue())
                        generated.append(filename)
                    continue

                if report_type == "cover":
                    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
                    cover_buffer = await _generate_cover_page(activity, settings)
                    if cover_buffer.getbuffer().nbytes > 0:
                        zf.writestr(f"Sampul_LHI_{activity_id[:8]}.pdf", cover_buffer.getvalue())
                        generated.append("Sampul_LHI.pdf")
                    continue

                if report_type in BATCH_PDF_MAP:
                    label, gen_func = BATCH_PDF_MAP[report_type]
                    response = await gen_func(activity_id)
                    pdf_buffer = await _get_pdf_buffer_from_response(response)
                    filename = f"{label}_{activity_id[:8]}.pdf"
                    zf.writestr(filename, pdf_buffer.getvalue())
                    generated.append(filename)

            except Exception as e:
                logger.warning(f"Batch ZIP: Failed to generate {report_type}: {e}")
                errors.append(f"{report_type}: {str(e)}")

    if not generated:
        raise HTTPException(status_code=500, detail="Tidak ada laporan yang berhasil di-generate")

    zip_buffer.seek(0)
    filename = f"Laporan_Batch_{activity_id[:8]}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

