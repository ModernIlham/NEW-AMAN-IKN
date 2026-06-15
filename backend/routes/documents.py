"""
Document generation routes - PPT Presentation & Proposal DOCX
Generates professional documents for InventoryMaster Pro
"""
import io
import logging
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
documents_router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# PPT PRESENTATION GENERATOR
# ═══════════════════════════════════════════════════════════════════
@documents_router.get("/documents/ppt")
async def generate_ppt():
    """Generate PPT presentation for InventoryMaster Pro"""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Color palette
    BLUE = RGBColor(0x1E, 0x40, 0xAF)
    DARK = RGBColor(0x0F, 0x17, 0x2A)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    GRAY = RGBColor(0x64, 0x74, 0x8B)
    LIGHT_BG = RGBColor(0xF1, 0xF5, 0xF9)
    ACCENT = RGBColor(0x38, 0xBD, 0xF8)
    GREEN = RGBColor(0x22, 0xC5, 0x5E)
    ORANGE = RGBColor(0xF9, 0x73, 0x16)
    RED = RGBColor(0xEF, 0x44, 0x44)

    def add_bg(slide, color=DARK):
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_shape_bg(slide, left, top, width, height, color, opacity=1.0):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        return shape

    def add_text_box(slide, left, top, width, height, text, font_size=18, color=WHITE, bold=False, alignment=PP_ALIGN.LEFT, font_name="Calibri"):
        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.font.name = font_name
        p.alignment = alignment
        return txBox

    def add_bullet_list(slide, left, top, width, height, items, font_size=14, color=WHITE, spacing=Pt(6)):
        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = item
            p.font.size = Pt(font_size)
            p.font.color.rgb = color
            p.font.name = "Calibri"
            p.space_after = spacing
            p.level = 0
        return txBox

    def add_card(slide, left, top, width, height, title, desc, icon_text, color=BLUE):
        # Card background
        card = add_shape_bg(slide, left, top, width, height, RGBColor(0x1E, 0x29, 0x3B))
        card.shadow.inherit = False
        # Icon circle
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, left + Inches(0.3), top + Inches(0.3), Inches(0.6), Inches(0.6))
        circle.fill.solid()
        circle.fill.fore_color.rgb = color
        circle.line.fill.background()
        tf = circle.text_frame
        tf.paragraphs[0].text = icon_text
        tf.paragraphs[0].font.size = Pt(16)
        tf.paragraphs[0].font.color.rgb = WHITE
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        # Title
        add_text_box(slide, left + Inches(0.3), top + Inches(1.1), width - Inches(0.6), Inches(0.4), title, 14, WHITE, True)
        # Desc
        add_text_box(slide, left + Inches(0.3), top + Inches(1.5), width - Inches(0.6), height - Inches(1.8), desc, 11, GRAY)

    # ── SLIDE 1: Cover ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    # Accent bar
    add_shape_bg(slide, Inches(0), Inches(0), Inches(0.08), Inches(7.5), BLUE)
    # Title block
    add_text_box(slide, Inches(1), Inches(1.5), Inches(8), Inches(0.6), "INVENTORYMASTER PRO", 16, ACCENT, True)
    add_text_box(slide, Inches(1), Inches(2.2), Inches(10), Inches(1.5),
                 "Sistem Inventarisasi Aset Terpadu\nBarang Milik Negara (BMN)", 40, WHITE, True)
    add_text_box(slide, Inches(1), Inches(4.2), Inches(10), Inches(0.8),
                 "Solusi digital komprehensif untuk pengelolaan inventarisasi aset fisik\nsesuai SE-17/MK.1/2024 Kementerian Keuangan RI", 18, GRAY)
    # Bottom info
    add_text_box(slide, Inches(1), Inches(6.2), Inches(5), Inches(0.4),
                 f"Product Requirements Document | {datetime.now().strftime('%B %Y')}", 12, GRAY)
    # Stats boxes
    stats = [("1,475+", "Aset Terdata"), ("18+", "Modul Fitur"), ("5", "Format Export"), ("99.9%", "Uptime")]
    for i, (val, label) in enumerate(stats):
        x = Inches(8) + Inches(i * 1.35)
        add_shape_bg(slide, x, Inches(5.5), Inches(1.2), Inches(1.2), RGBColor(0x1E, 0x29, 0x3B))
        add_text_box(slide, x, Inches(5.6), Inches(1.2), Inches(0.5), val, 20, ACCENT, True, PP_ALIGN.CENTER)
        add_text_box(slide, x, Inches(6.1), Inches(1.2), Inches(0.4), label, 9, GRAY, False, PP_ALIGN.CENTER)

    # ── SLIDE 2: Latar Belakang ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "01  LATAR BELAKANG", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.2), Inches(6), Inches(1),
                 "Mengapa Sistem Ini Dibutuhkan?", 32, WHITE, True)

    problems = [
        ("Pencatatan Manual", "Inventarisasi aset masih menggunakan spreadsheet manual yang rawan kesalahan, duplikasi data, dan sulit diaudit."),
        ("Tidak Real-time", "Perubahan data tidak tersinkronisasi antar tim pencatat, menyebabkan data tidak konsisten dan overlap pencatatan."),
        ("Kepatuhan Regulasi", "SE-17/MK.1/2024 mengharuskan klasifikasi detail untuk aset tidak ditemukan (kesalahan pencatatan, penghapusan, dll)."),
        ("Dokumentasi Terbatas", "Foto aset, dokumen pendukung, dan bukti stiker sering terpisah dari data utama sehingga sulit diverifikasi.")
    ]
    for i, (title, desc) in enumerate(problems):
        y = Inches(2.2) + Inches(i * 1.25)
        add_shape_bg(slide, Inches(0.8), y, Inches(0.06), Inches(0.9), [BLUE, ORANGE, RED, GREEN][i])
        add_text_box(slide, Inches(1.2), y, Inches(5), Inches(0.4), title, 16, WHITE, True)
        add_text_box(slide, Inches(1.2), y + Inches(0.4), Inches(5), Inches(0.5), desc, 12, GRAY)

    # Right side - regulation box
    add_shape_bg(slide, Inches(7), Inches(1.5), Inches(5.5), Inches(5), RGBColor(0x1E, 0x29, 0x3B))
    add_text_box(slide, Inches(7.3), Inches(1.8), Inches(5), Inches(0.4), "DASAR HUKUM", 12, ACCENT, True)
    regs = [
        "SE-17/MK.1/2024 tentang Pelaksanaan\nInventarisasi BMN",
        "PP 27/2014 tentang Pengelolaan\nBarang Milik Negara/Daerah",
        "PMK 181/PMK.06/2016 tentang\nPenatausahaan BMN",
        "Peraturan internal K/L tentang\npedoman inventarisasi aset tetap"
    ]
    for i, reg in enumerate(regs):
        y = Inches(2.4) + Inches(i * 1.0)
        add_shape_bg(slide, Inches(7.5), y, Inches(0.35), Inches(0.35), BLUE)
        add_text_box(slide, Inches(7.55), y - Inches(0.02), Inches(0.35), Inches(0.35), str(i+1), 12, WHITE, True, PP_ALIGN.CENTER)
        add_text_box(slide, Inches(8.1), y, Inches(4), Inches(0.8), reg, 12, WHITE)

    # ── SLIDE 3: Overview Sistem ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "02  OVERVIEW SISTEM", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.2), Inches(8), Inches(0.6),
                 "Arsitektur & Teknologi", 32, WHITE, True)

    # Architecture boxes
    techs = [
        ("Frontend", "React 18 + Tailwind CSS\nShadcn/UI Components\nVirtualized Table (1000+ rows)\nResponsive & PWA Ready", BLUE),
        ("Backend", "Python FastAPI\nAsync MongoDB Driver\nWebSocket Real-time\nRESTful API + CORS", GREEN),
        ("Database", "MongoDB 7.0\nGridFS (Photo Storage)\nCompound Indexes\nUUID-based Records", ORANGE),
        ("Infrastructure", "Docker + Kubernetes\nNginx Reverse Proxy\nSupervisor Process Mgr\nSSL/TLS Encryption", RGBColor(0xA7, 0x55, 0xF5)),
    ]
    for i, (title, desc, color) in enumerate(techs):
        x = Inches(0.8) + Inches(i * 3.1)
        add_shape_bg(slide, x, Inches(2.2), Inches(2.8), Inches(2.8), RGBColor(0x1E, 0x29, 0x3B))
        add_shape_bg(slide, x, Inches(2.2), Inches(2.8), Inches(0.06), color)
        add_text_box(slide, x + Inches(0.3), Inches(2.5), Inches(2.2), Inches(0.4), title, 16, color, True)
        add_text_box(slide, x + Inches(0.3), Inches(3.0), Inches(2.2), Inches(1.8), desc, 12, GRAY)

    # Flow
    add_text_box(slide, Inches(0.8), Inches(5.3), Inches(12), Inches(0.4), "ALUR DATA", 12, ACCENT, True)
    flow_items = ["User Browser", "React SPA", "Kubernetes Ingress", "FastAPI Backend", "MongoDB + GridFS"]
    for i, item in enumerate(flow_items):
        x = Inches(0.8) + Inches(i * 2.5)
        add_shape_bg(slide, x, Inches(5.8), Inches(2.0), Inches(0.7), RGBColor(0x1E, 0x29, 0x3B))
        add_text_box(slide, x, Inches(5.85), Inches(2.0), Inches(0.6), item, 12, WHITE, False, PP_ALIGN.CENTER)
        if i < len(flow_items) - 1:
            add_text_box(slide, x + Inches(2.0), Inches(5.85), Inches(0.5), Inches(0.6), "→", 18, ACCENT, True, PP_ALIGN.CENTER)

    # ── SLIDE 4: Fitur Utama ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "03  FITUR UTAMA", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.0), Inches(8), Inches(0.6),
                 "18+ Modul Terintegrasi", 32, WHITE, True)

    features = [
        ("📋", "CRUD Aset", "Tambah, edit, hapus aset\ndengan validasi lengkap", BLUE),
        ("📷", "Multi-Photo", "Upload hingga 10 foto per\naset + thumbnail otomatis", GREEN),
        ("📊", "Dashboard", "Statistik real-time, grafik\nkondisi & status aset", ORANGE),
        ("📥", "Import CSV", "Import massal ribuan data\ndengan validasi per baris", RGBColor(0xA7, 0x55, 0xF5)),
        ("📤", "Export Multi", "PDF, Excel, CSV dengan\nfoto & halaman nomor", RED),
        ("🏷️", "Stiker", "Kelola status & foto\nstiker inventaris", ACCENT),
        ("📝", "Dokumen", "Checklist dokumen\ndengan upload file", RGBColor(0xEC, 0x48, 0x99)),
        ("👥", "Multi-User", "Role admin/viewer\ndengan audit trail", RGBColor(0x14, 0xB8, 0xA6)),
        ("🔄", "Real-time", "WebSocket sync antar\nuser bersamaan", BLUE),
        ("📑", "Rekapitulasi", "Laporan SE-17 lengkap\ndengan breakdown detail", GREEN),
        ("🎴", "Kartu BMN", "Cetak kartu ukuran\nKTP per aset", ORANGE),
        ("💾", "Backup", "Backup & restore\nseluruh data kegiatan", RGBColor(0xA7, 0x55, 0xF5)),
    ]
    for i, (icon, title, desc, color) in enumerate(features):
        col = i % 6
        row = i // 6
        x = Inches(0.5) + Inches(col * 2.1)
        y = Inches(1.8) + Inches(row * 2.7)
        add_shape_bg(slide, x, y, Inches(1.95), Inches(2.3), RGBColor(0x1E, 0x29, 0x3B))
        add_shape_bg(slide, x, y, Inches(1.95), Inches(0.05), color)
        add_text_box(slide, x, y + Inches(0.15), Inches(1.95), Inches(0.5), icon, 28, WHITE, False, PP_ALIGN.CENTER)
        add_text_box(slide, x + Inches(0.15), y + Inches(0.7), Inches(1.65), Inches(0.35), title, 12, WHITE, True, PP_ALIGN.CENTER)
        add_text_box(slide, x + Inches(0.15), y + Inches(1.1), Inches(1.65), Inches(1.0), desc, 10, GRAY, False, PP_ALIGN.CENTER)

    # ── SLIDE 5: Alur Kerja ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "04  ALUR KERJA", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.0), Inches(8), Inches(0.6),
                 "Workflow Inventarisasi", 32, WHITE, True)

    steps = [
        ("01", "Buat Kegiatan", "Admin membuat kegiatan\ninventarisasi baru dan\nmengatur parameter", BLUE),
        ("02", "Siapkan Data", "Import data BMN dari\nSIMAN/CSV atau input\nmanual per aset", GREEN),
        ("03", "Inventarisasi", "Tim lapangan mencatat\nkondisi, foto, stiker,\ndan dokumen aset", ORANGE),
        ("04", "Verifikasi", "Admin memverifikasi\ndata, klasifikasi aset\ntidak ditemukan", RED),
        ("05", "Rekapitulasi", "Generate laporan,\nberita acara, SPTJM,\ndan surat koreksi", RGBColor(0xA7, 0x55, 0xF5)),
        ("06", "Selesai", "Export final, cetak\nkartu BMN, backup\ndata kegiatan", ACCENT),
    ]
    for i, (num, title, desc, color) in enumerate(steps):
        x = Inches(0.5) + Inches(i * 2.1)
        # Number circle
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.7), Inches(2.0), Inches(0.6), Inches(0.6))
        circle.fill.solid()
        circle.fill.fore_color.rgb = color
        circle.line.fill.background()
        tf = circle.text_frame
        tf.paragraphs[0].text = num
        tf.paragraphs[0].font.size = Pt(16)
        tf.paragraphs[0].font.color.rgb = WHITE
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        # Connector line
        if i < len(steps) - 1:
            add_shape_bg(slide, x + Inches(1.35), Inches(2.25), Inches(1.5), Inches(0.04), RGBColor(0x33, 0x44, 0x55))
        # Title & desc
        add_text_box(slide, x, Inches(2.8), Inches(2.0), Inches(0.4), title, 14, WHITE, True, PP_ALIGN.CENTER)
        add_text_box(slide, x, Inches(3.2), Inches(2.0), Inches(1.2), desc, 11, GRAY, False, PP_ALIGN.CENTER)

    # Bottom: user roles
    add_text_box(slide, Inches(0.8), Inches(4.8), Inches(12), Inches(0.4), "PERAN PENGGUNA", 12, ACCENT, True)
    roles = [
        ("Admin", "Kelola kegiatan, user, kategori, export/import, reset, backup", BLUE),
        ("Pencatat", "Input data aset, foto, stiker, dokumen checklist", GREEN),
        ("Viewer", "Lihat data, export laporan, cetak kartu (read-only)", GRAY),
    ]
    for i, (role, desc, color) in enumerate(roles):
        x = Inches(0.8) + Inches(i * 4.2)
        add_shape_bg(slide, x, Inches(5.3), Inches(3.8), Inches(1.4), RGBColor(0x1E, 0x29, 0x3B))
        add_shape_bg(slide, x, Inches(5.3), Inches(0.06), Inches(1.4), color)
        add_text_box(slide, x + Inches(0.3), Inches(5.5), Inches(3.2), Inches(0.35), role, 14, color, True)
        add_text_box(slide, x + Inches(0.3), Inches(5.9), Inches(3.2), Inches(0.6), desc, 11, GRAY)

    # ── SLIDE 6: SE-17 Compliance ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "05  KEPATUHAN SE-17/MK.1/2024", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.0), Inches(10), Inches(0.6),
                 "Klasifikasi Inventarisasi BMN", 32, WHITE, True)

    statuses = [
        ("Ditemukan", "Aset terverifikasi keberadaannya di lokasi sesuai catatan", GREEN, [
            "Kondisi: Baik / Rusak Ringan / Rusak Berat",
            "Foto aset wajib dilampirkan",
            "Stiker inventaris dipasang"
        ]),
        ("Tidak Ditemukan", "Aset tidak dapat diverifikasi di lokasi pencatatan", RED, [
            "Kesalahan Pencatatan → Koreksi data",
            "Dipindahtangankan → Proses transfer",
            "Penghapusan/BMN Hilang → Proses hapus",
            "Tidak Ditemukan Lainnya → Investigasi"
        ]),
        ("Belum Diinventarisasi", "Aset yang belum dilakukan pengecekan fisik", GRAY, [
            "Status default saat data di-import",
            "Menunggu kunjungan tim lapangan",
            "Dashboard menampilkan progress %"
        ]),
    ]
    for i, (status, desc, color, items) in enumerate(statuses):
        x = Inches(0.5) + Inches(i * 4.2)
        add_shape_bg(slide, x, Inches(1.8), Inches(3.9), Inches(5.2), RGBColor(0x1E, 0x29, 0x3B))
        add_shape_bg(slide, x, Inches(1.8), Inches(3.9), Inches(0.06), color)
        add_text_box(slide, x + Inches(0.3), Inches(2.1), Inches(3.3), Inches(0.4), status, 18, color, True)
        add_text_box(slide, x + Inches(0.3), Inches(2.55), Inches(3.3), Inches(0.6), desc, 11, GRAY)
        for j, item in enumerate(items):
            add_text_box(slide, x + Inches(0.3), Inches(3.3) + Inches(j * 0.55), Inches(3.3), Inches(0.5),
                        f"• {item}", 11, WHITE)

    # ── SLIDE 7: RAB ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "06  RENCANA ANGGARAN BIAYA", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.0), Inches(8), Inches(0.6),
                 "RAB Pengembangan Sistem", 32, WHITE, True)

    # Table header
    add_shape_bg(slide, Inches(0.8), Inches(2.0), Inches(11.5), Inches(0.6), BLUE)
    headers = [("No", 0.5), ("Komponen", 3.5), ("Vol", 0.8), ("Satuan", 1.2), ("Harga Satuan", 2.0), ("Total (Rp)", 2.5)]
    x_pos = Inches(0.8)
    for header, w in headers:
        add_text_box(slide, x_pos, Inches(2.05), Inches(w), Inches(0.5), header, 11, WHITE, True, PP_ALIGN.CENTER)
        x_pos += Inches(w)

    rab_items = [
        ("1", "Pengembangan Aplikasi (Full-stack Dev)", "1", "Paket", "85.000.000", "85.000.000"),
        ("2", "UI/UX Design & Prototyping", "1", "Paket", "15.000.000", "15.000.000"),
        ("3", "Cloud Server (VPS/Kubernetes) - 1 Tahun", "12", "Bulan", "1.500.000", "18.000.000"),
        ("4", "Domain & SSL Certificate", "1", "Tahun", "500.000", "500.000"),
        ("5", "Database MongoDB Atlas (M10)", "12", "Bulan", "800.000", "9.600.000"),
        ("6", "Quality Assurance & Testing", "1", "Paket", "10.000.000", "10.000.000"),
        ("7", "Training & Dokumentasi", "2", "Sesi", "5.000.000", "10.000.000"),
        ("8", "Maintenance & Support (1 Tahun)", "12", "Bulan", "3.000.000", "36.000.000"),
    ]
    for i, (no, item, vol, sat, harga, total) in enumerate(rab_items):
        y = Inches(2.65) + Inches(i * 0.48)
        bg_color = RGBColor(0x1E, 0x29, 0x3B) if i % 2 == 0 else DARK
        add_shape_bg(slide, Inches(0.8), y, Inches(11.5), Inches(0.46), bg_color)
        vals = [no, item, vol, sat, harga, total]
        x_pos = Inches(0.8)
        for j, (_, w) in enumerate(headers):
            align = PP_ALIGN.CENTER if j != 1 else PP_ALIGN.LEFT
            add_text_box(slide, x_pos + Inches(0.1), y + Inches(0.02), Inches(w - 0.2), Inches(0.4),
                        vals[j], 10, WHITE, False, align)
            x_pos += Inches(w)

    # Total row
    total_y = Inches(2.65) + Inches(len(rab_items) * 0.48)
    add_shape_bg(slide, Inches(0.8), total_y, Inches(11.5), Inches(0.55), BLUE)
    add_text_box(slide, Inches(0.8), total_y + Inches(0.05), Inches(8.5), Inches(0.45),
                 "TOTAL ANGGARAN", 12, WHITE, True, PP_ALIGN.RIGHT)
    add_text_box(slide, Inches(9.3), total_y + Inches(0.05), Inches(3.0), Inches(0.45),
                 "Rp 184.100.000", 14, WHITE, True, PP_ALIGN.CENTER)

    # ── SLIDE 8: Timeline ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5), "07  TIMELINE IMPLEMENTASI", 14, ACCENT, True)
    add_text_box(slide, Inches(0.8), Inches(1.0), Inches(8), Inches(0.6),
                 "Jadwal Pengembangan", 32, WHITE, True)

    timeline = [
        ("Bulan 1-2", "Analisis & Desain", "Requirements gathering\nUI/UX prototyping\nDesain database", BLUE),
        ("Bulan 3-5", "Pengembangan Core", "Backend API development\nFrontend development\nDatabase setup", GREEN),
        ("Bulan 6-7", "Integrasi & Testing", "Modul integration\nUAT & bug fixing\nPerformance tuning", ORANGE),
        ("Bulan 8", "Deployment", "Production deployment\nData migration\nUser training", RGBColor(0xA7, 0x55, 0xF5)),
        ("Bulan 9-12", "Maintenance", "Bug fixes & updates\nFeature enhancement\nTechnical support", ACCENT),
    ]
    # Timeline line
    add_shape_bg(slide, Inches(0.8), Inches(3.0), Inches(11.5), Inches(0.04), RGBColor(0x33, 0x44, 0x55))
    for i, (period, title, desc, color) in enumerate(timeline):
        x = Inches(0.5) + Inches(i * 2.5)
        # Dot
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.85), Inches(2.82), Inches(0.35), Inches(0.35))
        circle.fill.solid()
        circle.fill.fore_color.rgb = color
        circle.line.fill.background()
        # Period
        add_text_box(slide, x, Inches(2.2), Inches(2.3), Inches(0.4), period, 11, color, True, PP_ALIGN.CENTER)
        # Title & desc
        add_shape_bg(slide, x, Inches(3.5), Inches(2.3), Inches(2.5), RGBColor(0x1E, 0x29, 0x3B))
        add_shape_bg(slide, x, Inches(3.5), Inches(2.3), Inches(0.05), color)
        add_text_box(slide, x + Inches(0.2), Inches(3.7), Inches(1.9), Inches(0.4), title, 13, WHITE, True)
        add_text_box(slide, x + Inches(0.2), Inches(4.2), Inches(1.9), Inches(1.5), desc, 10, GRAY)

    # ── SLIDE 9: Penutup ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, DARK)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(0.08), Inches(7.5), BLUE)
    add_text_box(slide, Inches(1), Inches(2.0), Inches(10), Inches(1),
                 "Terima Kasih", 48, WHITE, True, PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(3.2), Inches(10), Inches(1),
                 "InventoryMaster Pro — Solusi Inventarisasi BMN yang Andal,\nCepat, dan Sesuai Regulasi", 20, GRAY, False, PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(5.0), Inches(10), Inches(0.4),
                 "Siap untuk demo & diskusi lebih lanjut", 16, ACCENT, False, PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(6.5), Inches(10), Inches(0.4),
                 f"© {datetime.now().year} InventoryMaster Pro | Product Requirements Document", 11, GRAY, False, PP_ALIGN.CENTER)

    # Save to buffer
    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=InventoryMaster_PRD_Presentation.pptx"}
    )


# ═══════════════════════════════════════════════════════════════════
# PROPOSAL DOCX GENERATOR
# ═══════════════════════════════════════════════════════════════════
@documents_router.get("/documents/proposal")
async def generate_proposal():
    """Generate proposal DOCX with BAB chapters and RAB"""
    from docx import Document
    from docx.shared import Pt as DPt, RGBColor as DRGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()

    # ── Styles ──
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = DPt(11)
    pf = style.paragraph_format
    pf.space_after = DPt(6)
    pf.line_spacing = 1.15

    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2.54)

    def add_heading_styled(text, level=1):
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.color.rgb = DRGBColor(0x1E, 0x40, 0xAF)
        return h

    def add_para(text, bold=False, italic=False, alignment=None, space_after=6):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = DPt(11)
        run.font.name = 'Calibri'
        if alignment:
            p.alignment = alignment
        p.paragraph_format.space_after = DPt(space_after)
        return p

    def add_table_row(table, cells_data, bold=False, bg_color=None):
        row = table.add_row()
        for i, text in enumerate(cells_data):
            cell = row.cells[i]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(text))
            run.bold = bold
            run.font.size = DPt(10)
            run.font.name = 'Calibri'
            if bg_color:
                from docx.oxml.ns import qn
                shading = cell._element.get_or_add_tcPr()
                shading_elem = shading.makeelement(qn('w:shd'), {
                    qn('w:val'): 'clear',
                    qn('w:color'): 'auto',
                    qn('w:fill'): bg_color
                })
                shading.append(shading_elem)
        return row

    # ══════════════════════════════════════
    # HALAMAN JUDUL
    # ══════════════════════════════════════
    for _ in range(4):
        doc.add_paragraph()
    
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run("PROPOSAL PENGEMBANGAN")
    run.bold = True
    run.font.size = DPt(24)
    run.font.color.rgb = DRGBColor(0x1E, 0x40, 0xAF)

    title_p2 = doc.add_paragraph()
    title_p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p2.add_run("SISTEM INVENTARISASI ASET TERPADU")
    run.bold = True
    run.font.size = DPt(20)
    run.font.color.rgb = DRGBColor(0x0F, 0x17, 0x2A)

    title_p3 = doc.add_paragraph()
    title_p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p3.add_run("(InventoryMaster Pro)")
    run.font.size = DPt(16)
    run.font.color.rgb = DRGBColor(0x64, 0x74, 0x8B)

    for _ in range(2):
        doc.add_paragraph()

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Aplikasi Pengelolaan Inventarisasi Barang Milik Negara (BMN)\nSesuai SE-17/MK.1/2024 Kementerian Keuangan RI")
    run.font.size = DPt(12)
    run.font.color.rgb = DRGBColor(0x64, 0x74, 0x8B)

    for _ in range(4):
        doc.add_paragraph()

    year_p = doc.add_paragraph()
    year_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = year_p.add_run(f"Tahun {datetime.now().year}")
    run.bold = True
    run.font.size = DPt(14)
    
    doc.add_page_break()

    # ══════════════════════════════════════
    # DAFTAR ISI
    # ══════════════════════════════════════
    add_heading_styled("DAFTAR ISI", 1)
    toc_items = [
        ("BAB I", "PENDAHULUAN", "1"),
        ("", "1.1 Latar Belakang", "1"),
        ("", "1.2 Dasar Hukum", "2"),
        ("", "1.3 Tujuan dan Sasaran", "2"),
        ("", "1.4 Ruang Lingkup", "3"),
        ("BAB II", "GAMBARAN UMUM SISTEM", "4"),
        ("", "2.1 Deskripsi Sistem", "4"),
        ("", "2.2 Arsitektur Teknologi", "5"),
        ("", "2.3 Fitur dan Fungsionalitas", "6"),
        ("BAB III", "METODOLOGI PENGEMBANGAN", "9"),
        ("", "3.1 Metode Pengembangan", "9"),
        ("", "3.2 Tahapan Pengembangan", "10"),
        ("", "3.3 Timeline Implementasi", "11"),
        ("BAB IV", "SPESIFIKASI TEKNIS", "12"),
        ("", "4.1 Kebutuhan Perangkat Keras", "12"),
        ("", "4.2 Kebutuhan Perangkat Lunak", "13"),
        ("", "4.3 Kebutuhan Jaringan", "14"),
        ("BAB V", "RENCANA ANGGARAN BIAYA (RAB)", "15"),
        ("", "5.1 Rincian Biaya Pengembangan", "15"),
        ("", "5.2 Biaya Operasional Tahunan", "16"),
        ("", "5.3 Total Investasi", "17"),
        ("BAB VI", "PENUTUP", "18"),
        ("", "6.1 Kesimpulan", "18"),
        ("", "6.2 Rekomendasi", "18"),
    ]
    for bab, title, page in toc_items:
        p = doc.add_paragraph()
        if bab:
            run = p.add_run(f"{bab}  ")
            run.bold = True
            run.font.size = DPt(11)
        run = p.add_run(title)
        run.font.size = DPt(11)
        run.bold = bool(bab)
        # Add tab and page number
        run = p.add_run(f"\t{page}")
        run.font.size = DPt(11)
        p.paragraph_format.space_after = DPt(2)

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB I: PENDAHULUAN
    # ══════════════════════════════════════
    add_heading_styled("BAB I  PENDAHULUAN", 1)

    add_heading_styled("1.1 Latar Belakang", 2)
    add_para("Barang Milik Negara (BMN) merupakan aset penting yang harus dikelola secara akuntabel dan transparan. Inventarisasi BMN adalah kegiatan pendataan, pencatatan, dan pelaporan hasil pendataan seluruh BMN yang dikuasai oleh Kementerian/Lembaga. Proses inventarisasi ini menjadi krusial untuk memastikan keakuratan data aset negara.")
    add_para("Saat ini, banyak satuan kerja masih mengandalkan metode pencatatan manual menggunakan spreadsheet yang memiliki berbagai keterbatasan:")
    
    limitations = [
        "Rentan terhadap kesalahan input dan duplikasi data",
        "Tidak mendukung kolaborasi real-time antar tim pencatat",
        "Dokumentasi foto aset terpisah dari data utama",
        "Tidak ada validasi otomatis terhadap format dan kelengkapan data",
        "Proses rekapitulasi dan pembuatan laporan memakan waktu lama",
        "Tidak ada audit trail untuk melacak perubahan data"
    ]
    for item in limitations:
        p = doc.add_paragraph(item, style='List Bullet')
        p.paragraph_format.space_after = DPt(3)

    add_para("Dengan diterbitkannya Surat Edaran Menteri Keuangan Nomor SE-17/MK.1/2024 tentang Pelaksanaan Inventarisasi BMN, diperlukan sistem yang mampu mengakomodasi klasifikasi inventarisasi yang lebih detail, termasuk sub-klasifikasi untuk aset yang tidak ditemukan (kesalahan pencatatan, dipindahtangankan, penghapusan/BMN hilang, dan tidak ditemukan lainnya).")
    add_para("Berdasarkan kondisi tersebut, diusulkan pengembangan Sistem Inventarisasi Aset Terpadu (InventoryMaster Pro) sebagai solusi digital komprehensif yang dapat meningkatkan efisiensi, akurasi, dan kepatuhan dalam pelaksanaan inventarisasi BMN.")

    add_heading_styled("1.2 Dasar Hukum", 2)
    regulations = [
        "Peraturan Pemerintah Nomor 27 Tahun 2014 tentang Pengelolaan Barang Milik Negara/Daerah sebagaimana telah diubah dengan PP Nomor 28 Tahun 2020",
        "Peraturan Menteri Keuangan Nomor 181/PMK.06/2016 tentang Penatausahaan Barang Milik Negara",
        "Surat Edaran Menteri Keuangan Nomor SE-17/MK.1/2024 tentang Pelaksanaan Inventarisasi Barang Milik Negara",
        "Peraturan Menteri Komunikasi dan Informatika tentang Sistem Pemerintahan Berbasis Elektronik (SPBE)",
        "Peraturan internal Kementerian/Lembaga tentang pedoman inventarisasi aset tetap"
    ]
    for i, reg in enumerate(regulations, 1):
        p = doc.add_paragraph(f"{i}. {reg}")
        p.paragraph_format.space_after = DPt(3)

    add_heading_styled("1.3 Tujuan dan Sasaran", 2)
    add_para("Tujuan:", bold=True)
    objectives = [
        "Menyediakan sistem informasi terintegrasi untuk mendukung pelaksanaan inventarisasi BMN secara efisien dan akurat",
        "Memenuhi ketentuan klasifikasi inventarisasi sesuai SE-17/MK.1/2024",
        "Meningkatkan transparansi dan akuntabilitas pengelolaan aset negara",
        "Mempercepat proses rekapitulasi dan pelaporan hasil inventarisasi"
    ]
    for obj in objectives:
        p = doc.add_paragraph(obj, style='List Bullet')
        p.paragraph_format.space_after = DPt(3)

    add_para("Sasaran:", bold=True)
    targets = [
        "100% data BMN tercatat secara digital dan terstruktur",
        "Pengurangan waktu inventarisasi hingga 60% dibanding metode manual",
        "Dokumentasi foto dan dokumen pendukung terintegrasi dalam satu platform",
        "Laporan hasil inventarisasi dapat dihasilkan secara otomatis"
    ]
    for target in targets:
        p = doc.add_paragraph(target, style='List Bullet')
        p.paragraph_format.space_after = DPt(3)

    add_heading_styled("1.4 Ruang Lingkup", 2)
    add_para("Ruang lingkup pengembangan sistem mencakup:")
    scopes = [
        "Modul manajemen data aset (CRUD) dengan dukungan multi-foto dan validasi",
        "Modul klasifikasi inventarisasi sesuai SE-17/MK.1/2024",
        "Modul manajemen dokumen dan checklist kelengkapan",
        "Modul pengelolaan stiker inventaris",
        "Modul import/export data dalam format CSV, XLSX, dan PDF",
        "Modul rekapitulasi dan pembuatan laporan otomatis",
        "Modul manajemen pengguna dengan hak akses berbasis peran (role-based)",
        "Modul kolaborasi real-time menggunakan teknologi WebSocket",
        "Modul backup dan restore data kegiatan",
        "Modul cetak kartu inventaris BMN (format KTP)"
    ]
    for scope in scopes:
        p = doc.add_paragraph(scope, style='List Bullet')
        p.paragraph_format.space_after = DPt(3)

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB II: GAMBARAN UMUM SISTEM
    # ══════════════════════════════════════
    add_heading_styled("BAB II  GAMBARAN UMUM SISTEM", 1)

    add_heading_styled("2.1 Deskripsi Sistem", 2)
    add_para("InventoryMaster Pro adalah aplikasi web berbasis cloud yang dirancang khusus untuk mendukung proses inventarisasi Barang Milik Negara (BMN). Sistem ini dibangun menggunakan arsitektur modern full-stack dengan pendekatan Single Page Application (SPA) yang memungkinkan pengalaman pengguna yang responsif dan interaktif.")
    add_para("Sistem mendukung pengelolaan aset secara komprehensif mulai dari pencatatan data aset, dokumentasi foto, pengelolaan stiker inventaris, klasifikasi status inventarisasi, hingga pembuatan laporan final. Dengan fitur kolaborasi real-time, beberapa pengguna dapat bekerja secara bersamaan pada satu kegiatan inventarisasi tanpa konflik data.")

    add_heading_styled("2.2 Arsitektur Teknologi", 2)
    add_para("Sistem dibangun menggunakan arsitektur three-tier yang terdiri dari:", bold=True)
    
    # Tech table
    tech_table = doc.add_table(rows=1, cols=3)
    tech_table.style = 'Table Grid'
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_cells = tech_table.rows[0].cells
    for i, text in enumerate(["Lapisan", "Teknologi", "Deskripsi"]):
        header_cells[i].text = text
        for p in header_cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(10)

    tech_items = [
        ("Presentasi (Frontend)", "React 18 + Tailwind CSS", "Single Page Application dengan komponen UI modern, virtualized table untuk menampilkan ribuan data, dan dukungan responsive/PWA"),
        ("Logika Bisnis (Backend)", "Python FastAPI", "RESTful API asynchronous dengan WebSocket untuk real-time sync, validasi data komprehensif, dan integrasi GridFS untuk manajemen file"),
        ("Data (Database)", "MongoDB 7.0", "Document-oriented database dengan GridFS untuk penyimpanan foto berukuran besar, compound indexes untuk performa query optimal"),
        ("Infrastruktur", "Docker + Kubernetes", "Container orchestration untuk high availability, Nginx reverse proxy, SSL/TLS encryption, dan auto-scaling"),
    ]
    for row_data in tech_items:
        add_table_row(tech_table, row_data)

    doc.add_paragraph()
    add_para("Keunggulan Arsitektur:", bold=True)
    arch_advantages = [
        "Scalable: Dapat menangani ribuan aset dan puluhan pengguna secara bersamaan",
        "Reliable: Arsitektur microservices dengan supervisor process management",
        "Secure: Autentikasi JWT, role-based access control, dan enkripsi end-to-end",
        "Maintainable: Kode terstruktur modular dengan separation of concerns yang jelas"
    ]
    for adv in arch_advantages:
        p = doc.add_paragraph(adv, style='List Bullet')
        p.paragraph_format.space_after = DPt(3)

    add_heading_styled("2.3 Fitur dan Fungsionalitas", 2)

    features_detail = [
        ("A. Manajemen Data Aset", [
            "Pencatatan data aset dengan 30+ field termasuk kode aset, NUP, kategori, merk, model, lokasi, eselon, kondisi, dan status",
            "Upload hingga 10 foto per aset dengan kompresi otomatis dan thumbnail generation",
            "Inline editing langsung pada tabel data dengan auto-save dan optimistic update",
            "Validasi format kode aset (10 digit), NUP, dan kelengkapan data wajib",
            "Pencarian dan filter multi-kriteria (kategori, kondisi, status, lokasi, eselon)"
        ]),
        ("B. Klasifikasi Inventarisasi SE-17", [
            "Status Ditemukan: Pencatatan kondisi (Baik/Rusak Ringan/Rusak Berat) dengan foto wajib",
            "Status Tidak Ditemukan dengan sub-klasifikasi: Kesalahan Pencatatan, Dipindahtangankan, Penghapusan/BMN Hilang, Tidak Ditemukan Lainnya",
            "Status Belum Diinventarisasi sebagai default untuk aset baru yang belum dicek",
            "Progress tracking persentase inventarisasi secara real-time"
        ]),
        ("C. Manajemen Dokumen", [
            "Checklist dokumen kelengkapan per aset dengan status centang",
            "Upload dokumen pendukung (PDF) dan foto per item checklist",
            "Catatan tambahan per item dokumen"
        ]),
        ("D. Export & Laporan", [
            "Export data ke format PDF dengan foto aset dan layout tabel profesional",
            "Export ke Excel (XLSX) dengan semua field dan data lengkap",
            "Export ke CSV untuk integrasi dengan sistem lain",
            "Rekapitulasi otomatis: ringkasan kondisi, status, progress inventarisasi",
            "Generate laporan: Berita Acara, SPTJM, dan Surat Koreksi dalam format PDF",
            "Executive Summary PDF dengan ringkasan eksekutif kegiatan"
        ]),
        ("E. Import Data Massal", [
            "Import dari file CSV dengan validasi per baris",
            "Preview data sebelum import dengan penanda error",
            "Template CSV yang dapat diunduh untuk panduan pengisian",
            "Dukungan encoding UTF-8 untuk karakter Indonesia"
        ]),
        ("F. Stiker Inventaris", [
            "Pencatatan status pemasangan stiker (Terpasang/Tidak Terpasang)",
            "Pilihan ukuran stiker (Kecil/Sedang/Besar)",
            "Upload foto stiker yang terpasang pada aset"
        ]),
        ("G. Kolaborasi & Manajemen Pengguna", [
            "Multi-user dengan role-based access (Admin, Pencatat, Viewer)",
            "Real-time sync menggunakan WebSocket untuk update langsung",
            "Row locking saat editing untuk mencegah konflik data",
            "Indikator online/offline pengguna",
            "Audit trail lengkap untuk melacak setiap perubahan"
        ]),
        ("H. Fitur Pendukung", [
            "Cetak kartu inventaris BMN format KTP dengan foto dan barcode",
            "Backup dan restore seluruh data per kegiatan",
            "Dashboard analytics dengan grafik kondisi, status, dan kategori aset",
            "Dark mode dan responsive design untuk akses mobile",
            "Offline sync capability untuk area dengan koneksi terbatas"
        ]),
    ]

    for section_title, items in features_detail:
        add_para(section_title, bold=True, space_after=3)
        for item in items:
            p = doc.add_paragraph(item, style='List Bullet')
            p.paragraph_format.space_after = DPt(2)
        doc.add_paragraph()

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB III: METODOLOGI
    # ══════════════════════════════════════
    add_heading_styled("BAB III  METODOLOGI PENGEMBANGAN", 1)

    add_heading_styled("3.1 Metode Pengembangan", 2)
    add_para("Pengembangan sistem menggunakan metodologi Agile Development dengan pendekatan Scrum, yang memungkinkan pengembangan iteratif dan adaptif terhadap perubahan kebutuhan. Setiap sprint berdurasi 2 minggu dengan deliverables yang terukur.")
    add_para("Keuntungan metode Agile:", bold=True)
    agile_benefits = [
        "Feedback loop yang cepat dari stakeholder",
        "Fleksibilitas terhadap perubahan requirements",
        "Deliverables yang inkremental dan dapat dievaluasi",
        "Deteksi dini terhadap risiko dan masalah teknis",
        "Transparansi progress pengembangan"
    ]
    for benefit in agile_benefits:
        p = doc.add_paragraph(benefit, style='List Bullet')

    add_heading_styled("3.2 Tahapan Pengembangan", 2)
    stages = [
        ("Fase 1: Analisis & Perancangan (Bulan 1-2)", [
            "Pengumpulan dan analisis kebutuhan (requirement gathering)",
            "Desain arsitektur sistem dan database",
            "Pembuatan wireframe dan mockup UI/UX",
            "Review dan validasi desain dengan stakeholder",
            "Penyusunan spesifikasi teknis detail"
        ]),
        ("Fase 2: Pengembangan Core System (Bulan 3-5)", [
            "Setup infrastruktur development dan deployment",
            "Pengembangan backend API (authentication, CRUD, import/export)",
            "Pengembangan frontend UI components dan halaman utama",
            "Implementasi database schema dan indexing",
            "Integrasi WebSocket untuk real-time collaboration",
            "Unit testing dan code review per sprint"
        ]),
        ("Fase 3: Integrasi & Testing (Bulan 6-7)", [
            "Integration testing seluruh modul",
            "User Acceptance Testing (UAT) dengan user representatif",
            "Performance testing dan optimization",
            "Security testing dan vulnerability assessment",
            "Bug fixing dan refinement berdasarkan feedback"
        ]),
        ("Fase 4: Deployment & Go-Live (Bulan 8)", [
            "Setup production environment (Kubernetes cluster)",
            "Migrasi data dari sistem lama (jika ada)",
            "Training pengguna dan administrator",
            "Soft launch dan monitoring",
            "Go-live dan handover dokumentasi"
        ]),
        ("Fase 5: Maintenance & Support (Bulan 9-12)", [
            "Monitoring dan troubleshooting",
            "Bug fixes dan minor enhancements",
            "Performance monitoring dan optimization",
            "Knowledge transfer dan capacity building",
            "Evaluasi dan perencanaan fitur lanjutan"
        ]),
    ]
    for stage_title, items in stages:
        add_para(stage_title, bold=True, space_after=3)
        for item in items:
            p = doc.add_paragraph(item, style='List Bullet')
            p.paragraph_format.space_after = DPt(2)
        doc.add_paragraph()

    add_heading_styled("3.3 Timeline Implementasi", 2)
    timeline_table = doc.add_table(rows=1, cols=7)
    timeline_table.style = 'Table Grid'
    headers = ["Fase", "Kegiatan", "Bln 1-2", "Bln 3-5", "Bln 6-7", "Bln 8", "Bln 9-12"]
    for i, h in enumerate(headers):
        timeline_table.rows[0].cells[i].text = h
        for p in timeline_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(9)

    tl_data = [
        ("1", "Analisis & Perancangan", "████", "", "", "", ""),
        ("2", "Pengembangan Core", "", "████", "", "", ""),
        ("3", "Integrasi & Testing", "", "", "████", "", ""),
        ("4", "Deployment & Go-Live", "", "", "", "████", ""),
        ("5", "Maintenance & Support", "", "", "", "", "████"),
    ]
    for row_data in tl_data:
        add_table_row(timeline_table, row_data)

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB IV: SPESIFIKASI TEKNIS
    # ══════════════════════════════════════
    add_heading_styled("BAB IV  SPESIFIKASI TEKNIS", 1)

    add_heading_styled("4.1 Kebutuhan Perangkat Keras (Server)", 2)
    hw_table = doc.add_table(rows=1, cols=4)
    hw_table.style = 'Table Grid'
    for i, h in enumerate(["Komponen", "Minimum", "Rekomendasi", "Keterangan"]):
        hw_table.rows[0].cells[i].text = h
        for p in hw_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(10)

    hw_data = [
        ("Processor", "4 vCPU", "8 vCPU", "Untuk menangani concurrent users"),
        ("Memory (RAM)", "8 GB", "16 GB", "Untuk PDF generation & caching"),
        ("Storage (SSD)", "100 GB", "500 GB", "Untuk foto aset & backup"),
        ("Bandwidth", "100 Mbps", "1 Gbps", "Untuk transfer file & WebSocket"),
        ("OS", "Ubuntu 22.04 LTS", "Ubuntu 24.04 LTS", "Linux-based server"),
    ]
    for row_data in hw_data:
        add_table_row(hw_table, row_data)

    add_heading_styled("4.2 Kebutuhan Perangkat Lunak", 2)
    sw_table = doc.add_table(rows=1, cols=4)
    sw_table.style = 'Table Grid'
    for i, h in enumerate(["Software", "Versi", "Fungsi", "Lisensi"]):
        sw_table.rows[0].cells[i].text = h
        for p in sw_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(10)

    sw_data = [
        ("Python", "3.11+", "Backend runtime", "Open Source"),
        ("Node.js", "18 LTS", "Frontend build tools", "Open Source"),
        ("MongoDB", "7.0+", "Database server", "SSPL (Free tier)"),
        ("Docker", "24+", "Container runtime", "Open Source"),
        ("Kubernetes", "1.28+", "Container orchestration", "Open Source"),
        ("Nginx", "1.24+", "Reverse proxy & SSL", "Open Source"),
        ("React", "18.2+", "Frontend framework", "MIT License"),
        ("FastAPI", "0.104+", "Backend framework", "MIT License"),
    ]
    for row_data in sw_data:
        add_table_row(sw_table, row_data)

    add_heading_styled("4.3 Kebutuhan Jaringan", 2)
    add_para("Spesifikasi jaringan yang diperlukan:")
    network_reqs = [
        "Koneksi internet stabil dengan bandwidth minimal 10 Mbps per concurrent user",
        "Alamat IP publik statis untuk akses server",
        "Domain name dengan SSL certificate (Let's Encrypt atau komersial)",
        "Firewall rules: port 80 (HTTP redirect), 443 (HTTPS), MongoDB internal only",
        "WebSocket support pada load balancer/reverse proxy"
    ]
    for req in network_reqs:
        p = doc.add_paragraph(req, style='List Bullet')

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB V: RAB
    # ══════════════════════════════════════
    add_heading_styled("BAB V  RENCANA ANGGARAN BIAYA (RAB)", 1)

    add_heading_styled("5.1 Rincian Biaya Pengembangan", 2)
    add_para("Berikut adalah rincian biaya pengembangan Sistem Inventarisasi Aset Terpadu (InventoryMaster Pro):")
    
    rab_table = doc.add_table(rows=1, cols=6)
    rab_table.style = 'Table Grid'
    rab_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(["No", "Komponen Biaya", "Volume", "Satuan", "Harga Satuan (Rp)", "Jumlah (Rp)"]):
        rab_table.rows[0].cells[i].text = h
        for p in rab_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(9)

    rab_dev = [
        ("A", "BIAYA PENGEMBANGAN", "", "", "", ""),
        ("1", "Full-stack Development", "1", "Paket", "85.000.000", "85.000.000"),
        ("2", "UI/UX Design & Prototyping", "1", "Paket", "15.000.000", "15.000.000"),
        ("3", "Quality Assurance & Testing", "1", "Paket", "10.000.000", "10.000.000"),
        ("4", "Dokumentasi & User Manual", "1", "Paket", "5.000.000", "5.000.000"),
        ("5", "Training Pengguna (2 sesi)", "2", "Sesi", "5.000.000", "10.000.000"),
        ("", "Subtotal Pengembangan", "", "", "", "125.000.000"),
        ("B", "BIAYA INFRASTRUKTUR (1 TAHUN)", "", "", "", ""),
        ("6", "Cloud Server (VPS/Kubernetes)", "12", "Bulan", "1.500.000", "18.000.000"),
        ("7", "Domain & SSL Certificate", "1", "Tahun", "500.000", "500.000"),
        ("8", "MongoDB Atlas (M10 Cluster)", "12", "Bulan", "800.000", "9.600.000"),
        ("9", "Backup Storage (100 GB)", "12", "Bulan", "200.000", "2.400.000"),
        ("", "Subtotal Infrastruktur", "", "", "", "30.500.000"),
        ("C", "BIAYA OPERASIONAL (1 TAHUN)", "", "", "", ""),
        ("10", "Maintenance & Bug Fix", "12", "Bulan", "2.000.000", "24.000.000"),
        ("11", "Technical Support", "12", "Bulan", "1.000.000", "12.000.000"),
        ("", "Subtotal Operasional", "", "", "", "36.000.000"),
    ]

    for row_data in rab_dev:
        is_header = row_data[0] in ("A", "B", "C") or row_data[0] == ""
        add_table_row(rab_table, row_data, bold=is_header)

    # Total
    total_row = add_table_row(rab_table, ["", "TOTAL KESELURUHAN", "", "", "", "191.500.000"], bold=True, bg_color="1E40AF")

    doc.add_paragraph()

    add_heading_styled("5.2 Biaya Operasional Tahunan (Tahun ke-2 dst)", 2)
    add_para("Setelah tahun pertama, biaya yang diperlukan adalah biaya infrastruktur dan operasional:")
    
    annual_table = doc.add_table(rows=1, cols=4)
    annual_table.style = 'Table Grid'
    for i, h in enumerate(["No", "Komponen", "Biaya/Bulan (Rp)", "Biaya/Tahun (Rp)"]):
        annual_table.rows[0].cells[i].text = h
        for p in annual_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(10)

    annual_data = [
        ("1", "Cloud Server", "1.500.000", "18.000.000"),
        ("2", "MongoDB Atlas", "800.000", "9.600.000"),
        ("3", "Domain & SSL", "-", "500.000"),
        ("4", "Backup Storage", "200.000", "2.400.000"),
        ("5", "Maintenance & Support", "3.000.000", "36.000.000"),
    ]
    for row_data in annual_data:
        add_table_row(annual_table, row_data)
    add_table_row(annual_table, ["", "TOTAL PER TAHUN", "", "66.500.000"], bold=True, bg_color="1E40AF")

    add_heading_styled("5.3 Total Investasi", 2)
    add_para("Ringkasan total investasi untuk 3 tahun pertama:")
    inv_table = doc.add_table(rows=1, cols=3)
    inv_table.style = 'Table Grid'
    for i, h in enumerate(["Periode", "Komponen", "Biaya (Rp)"]):
        inv_table.rows[0].cells[i].text = h
        for p in inv_table.rows[0].cells[i].paragraphs:
            p.runs[0].bold = True
            p.runs[0].font.size = DPt(10)

    inv_data = [
        ("Tahun 1", "Pengembangan + Infrastruktur + Operasional", "191.500.000"),
        ("Tahun 2", "Infrastruktur + Operasional", "66.500.000"),
        ("Tahun 3", "Infrastruktur + Operasional", "66.500.000"),
    ]
    for row_data in inv_data:
        add_table_row(inv_table, row_data)
    add_table_row(inv_table, ["", "TOTAL INVESTASI 3 TAHUN", "324.500.000"], bold=True, bg_color="1E40AF")

    doc.add_page_break()

    # ══════════════════════════════════════
    # BAB VI: PENUTUP
    # ══════════════════════════════════════
    add_heading_styled("BAB VI  PENUTUP", 1)

    add_heading_styled("6.1 Kesimpulan", 2)
    add_para("Sistem Inventarisasi Aset Terpadu (InventoryMaster Pro) merupakan solusi digital yang komprehensif dan modern untuk mendukung pelaksanaan inventarisasi Barang Milik Negara. Dengan arsitektur teknologi yang scalable, fitur yang lengkap, dan kepatuhan terhadap regulasi SE-17/MK.1/2024, sistem ini diharapkan dapat:")
    conclusions = [
        "Meningkatkan efisiensi proses inventarisasi hingga 60% dibanding metode manual",
        "Menjamin akurasi data melalui validasi otomatis dan audit trail",
        "Memfasilitasi kolaborasi tim inventarisasi secara real-time",
        "Menghasilkan laporan dan dokumen inventarisasi secara otomatis dan profesional",
        "Mendukung pengambilan keputusan berbasis data yang akurat dan terkini"
    ]
    for item in conclusions:
        p = doc.add_paragraph(item, style='List Bullet')

    add_heading_styled("6.2 Rekomendasi", 2)
    add_para("Berdasarkan analisis kebutuhan dan pertimbangan teknis, direkomendasikan:")
    recommendations = [
        "Segera dilakukan pengembangan sistem untuk mengantisipasi pelaksanaan inventarisasi BMN periode berikutnya",
        "Pembentukan tim pengelola sistem yang terdiri dari administrator teknis dan super user dari masing-masing unit",
        "Pelaksanaan training pengguna secara bertahap sebelum go-live",
        "Evaluasi dan pengembangan fitur lanjutan secara berkala berdasarkan feedback pengguna",
        "Alokasi anggaran untuk maintenance dan pengembangan berkelanjutan"
    ]
    for item in recommendations:
        p = doc.add_paragraph(item, style='List Bullet')

    doc.add_paragraph()
    add_para("Demikian proposal ini disampaikan sebagai bahan pertimbangan. Atas perhatian dan persetujuannya, kami ucapkan terima kasih.")
    
    for _ in range(3):
        doc.add_paragraph()
    
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(f"Jakarta, {datetime.now().strftime('%d %B %Y')}")
    
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("Tim Pengembang\nInventoryMaster Pro")
    run.bold = True

    # Save
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=Proposal_InventoryMaster_Pro.docx"}
    )
