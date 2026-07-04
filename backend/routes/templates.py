"""Download template routes (CSV, XLSX) for asset import.

Schema is defined ONCE in `ASSET_TEMPLATE_SCHEMA` so the headers, sample rows,
column widths, dropdown placement and 'Panduan' sheet are guaranteed to stay
in sync. Adding a new column means appending a single dict — no off-by-one
bugs are possible from drifting parallel arrays.
"""
import io
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import xlsxwriter

from db import db
from shared_utils import (
    VALID_INVENTORY_STATUSES, VALID_KLASIFIKASI, VALID_SUB_KLASIFIKASI_ALL,
    VALID_CONDITIONS, VALID_STATUSES, VALID_STIKER_STATUSES, VALID_STIKER_SIZES
)

logger = logging.getLogger(__name__)
templates_router = APIRouter()


# ============================================================================
# SINGLE-SOURCE-OF-TRUTH TEMPLATE SCHEMA
# ============================================================================
# Each entry describes ONE column. All template artifacts (Excel headers,
# CSV header row, sample data, column widths, dropdown ranges, Panduan sheet)
# are derived from this list. To add or rename a field, edit ONLY this list.
#
# Keys:
#   field      → DB / API field name (also used as Excel header text)
#   required   → True → red header + 'YA' in panduan
#   width      → Excel column width
#   rule       → human-readable rule for Panduan sheet
#   sample1    → value for first sample row (left blank → empty cell)
#   sample2    → value for second sample row
#   dropdown   → list of valid values OR sentinel string "_DYNAMIC_CATEGORY_"
#                meaning: filled at runtime from `categories` collection.
#                None → no dropdown.
# ----------------------------------------------------------------------------
ASSET_TEMPLATE_SCHEMA = [
    {"field": "asset_code", "required": True, "width": 15,
     "rule": "Wajib. Tepat 10 digit angka.",
     "sample1": "3030103001", "sample2": "3050105007", "dropdown": None},
    {"field": "NUP", "required": False, "width": 8,
     "rule": "Nomor Urut Pendaftaran (angka).",
     "sample1": "2", "sample2": "7", "dropdown": None},
    {"field": "asset_name", "required": True, "width": 25,
     "rule": "Wajib. Nama aset.",
     "sample1": "Laptop Dell", "sample2": "Meja Kantor", "dropdown": None},
    {"field": "category", "required": True, "width": 18,
     "rule": "Wajib. Pilih dari daftar kategori (dropdown).",
     "sample1": "Elektronik & IT", "sample2": "Furniture/Mebel",
     "dropdown": "_DYNAMIC_CATEGORY_"},
    {"field": "brand", "required": False, "width": 12,
     "rule": "Merk/brand aset.",
     "sample1": "Dell", "sample2": "IKEA", "dropdown": None},
    {"field": "model", "required": False, "width": 15,
     "rule": "Model/tipe aset.",
     "sample1": "Latitude 5420", "sample2": "MALM", "dropdown": None},
    {"field": "kode_register", "required": False, "width": 35,
     "rule": "Tepat 32 karakter hexadecimal (0-9, A-F). Boleh kosong.",
     "sample1": "2C089D3BEB8BB483E063BAAAD80A726F",
     "sample2": "1CE846E5423814C8E063BCAAD80A5FF3", "dropdown": None},
    {"field": "serial_number", "required": False, "width": 15,
     "rule": "Nomor seri pabrikan.",
     "sample1": "SN123456", "sample2": "SN789012", "dropdown": None},
    {"field": "purchase_date", "required": False, "width": 12,
     "rule": "Format: YYYY-MM-DD.",
     "sample1": "2024-01-01", "sample2": "2024-01-02", "dropdown": None},
    {"field": "purchase_price", "required": False, "width": 15,
     "rule": "Harga dalam angka tanpa titik/koma.",
     "sample1": "15000000", "sample2": "2500000", "dropdown": None},
    {"field": "location", "required": False, "width": 18,
     "rule": "Lokasi fisik aset.",
     "sample1": "Ruang IT", "sample2": "Ruang Admin", "dropdown": None},
    {"field": "eselon1", "required": False, "width": 18,
     "rule": "Unit Eselon I.",
     "sample1": "Sekretariat Utama", "sample2": "Deputi Bidang A", "dropdown": None},
    {"field": "eselon2", "required": False, "width": 18,
     "rule": "Unit Eselon II.",
     "sample1": "Biro Umum", "sample2": "Direktorat Satu", "dropdown": None},
    {"field": "user", "required": False, "width": 14,
     "rule": "Nama pengguna aset.",
     "sample1": "John Doe", "sample2": "Jane Smith", "dropdown": None},
    {"field": "pengguna_melekat_ke", "required": False, "width": 18,
     "rule": "Pilih: Individual / Jabatan / Operasional.",
     "sample1": "Individual", "sample2": "",
     "dropdown": ["Individual", "Jabatan", "Operasional"]},
    {"field": "pengguna_jabatan", "required": False, "width": 24,
     "rule": "Nama jabatan — isi hanya bila pengguna_melekat_ke = Jabatan.",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "nomor_bast", "required": False, "width": 24,
     "rule": "Nomor BAST serah terima ke pengguna (dokumen BAST diunggah lewat aplikasi).",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "condition", "required": False, "width": 13,
     "rule": "Pilih: Baik / Rusak Ringan / Rusak Berat.",
     "sample1": "Baik", "sample2": "Baik", "dropdown": VALID_CONDITIONS},
    {"field": "status", "required": False, "width": 13,
     "rule": "Pilih: Aktif / Idle / Maintenance / Nonaktif.",
     "sample1": "Aktif", "sample2": "Aktif", "dropdown": VALID_STATUSES},
    {"field": "nomor_spm", "required": False, "width": 22,
     "rule": "Format: XXXXX/XXXXXX/YYYY.",
     "sample1": "02847T/621001/2024", "sample2": "03897T/621001/2024", "dropdown": None},
    {"field": "perolehan_dari_nama", "required": False, "width": 25,
     "rule": "Nama pihak asal perolehan.",
     "sample1": "TENO SULISTYANTO", "sample2": "JHON RINDU NAINGGOLAN", "dropdown": None},
    {"field": "nomor_kontrak", "required": False, "width": 25,
     "rule": "Nomor kontrak pengadaan.",
     "sample1": "SP-95/PPK.I/OIKN/2024", "sample2": "PRJ-143/PPK.IV/OIKN/2024", "dropdown": None},
    {"field": "nomor_bukti_perolehan", "required": False, "width": 25,
     "rule": "Nomor BAST atau bukti perolehan.",
     "sample1": "BAST-110/PPK.I/OIKN/2024", "sample2": "BAST-152/PPK.IV/OIKN/2024", "dropdown": None},
    {"field": "supplier", "required": False, "width": 22,
     "rule": "Nama supplier/vendor.",
     "sample1": "CV REFAN BINA KARYA", "sample2": "PT GLOIPID PUTRA INDONESIA", "dropdown": None},
    {"field": "notes", "required": False, "width": 18,
     "rule": "Catatan tambahan.",
     "sample1": "Contoh data", "sample2": "Contoh data", "dropdown": None},
    {"field": "stiker_status", "required": False, "width": 17,
     "rule": "Pilih: Belum Terpasang / Sudah Terpasang.",
     "sample1": "Sudah Terpasang", "sample2": "Belum Terpasang",
     "dropdown": VALID_STIKER_STATUSES},
    {"field": "stiker_ukuran", "required": False, "width": 14,
     "rule": "Pilih: Kecil / Sedang / Besar (jika stiker terpasang).",
     "sample1": "Kecil", "sample2": "", "dropdown": VALID_STIKER_SIZES},
    {"field": "inventory_status", "required": False, "width": 22,
     "rule": "Pilih: Belum Diinventarisasi / Ditemukan / Tidak Ditemukan / Berlebih / Sengketa.",
     "sample1": "Ditemukan", "sample2": "Tidak Ditemukan",
     "dropdown": VALID_INVENTORY_STATUSES},
    {"field": "klasifikasi_tidak_ditemukan", "required": False, "width": 25,
     "rule": "Jika Tidak Ditemukan: Kesalahan Pencatatan / Tidak Ditemukan Lainnya.",
     "sample1": "", "sample2": "Kesalahan Pencatatan",
     "dropdown": VALID_KLASIFIKASI},
    {"field": "sub_klasifikasi", "required": False, "width": 30,
     "rule": "Sub-kategori tidak ditemukan (sesuai daftar).",
     "sample1": "", "sample2": "Pencatatan Ganda",
     "dropdown": VALID_SUB_KLASIFIKASI_ALL},
    {"field": "uraian_tidak_ditemukan", "required": False, "width": 30,
     "rule": "Uraian detail mengapa BMN tidak ditemukan.",
     "sample1": "", "sample2": "BMN tercatat dua kali di sistem", "dropdown": None},
    {"field": "tindak_lanjut", "required": False, "width": 25,
     "rule": "Tindak lanjut yang sudah dilakukan.",
     "sample1": "", "sample2": "Akan dilakukan koreksi pencatatan", "dropdown": None},
    {"field": "kronologis", "required": False, "width": 30,
     "rule": "Kronologis ketidakberadaan BMN.",
     "sample1": "", "sample2": "BMN tercatat ganda pada tahun 2023", "dropdown": None},
    {"field": "koordinat_latitude", "required": False, "width": 16,
     "rule": "Koordinat GPS latitude (contoh: -6.175110).",
     "sample1": "-6.175110", "sample2": "", "dropdown": None},
    {"field": "koordinat_longitude", "required": False, "width": 16,
     "rule": "Koordinat GPS longitude (contoh: 106.865036).",
     "sample1": "106.865036", "sample2": "", "dropdown": None},
    {"field": "keterangan_berlebih", "required": False, "width": 25,
     "rule": "Keterangan jika BMN berlebih (tidak tercatat / melebihi SBSK).",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "asal_usul_berlebih", "required": False, "width": 25,
     "rule": "Asal-usul BMN berlebih.",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "nomor_perkara", "required": False, "width": 22,
     "rule": "Nomor perkara pengadilan jika BMN sengketa.",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "pihak_bersengketa", "required": False, "width": 22,
     "rule": "Pihak yang bersengketa.",
     "sample1": "", "sample2": "", "dropdown": None},
    {"field": "keterangan_sengketa", "required": False, "width": 25,
     "rule": "Keterangan detail sengketa.",
     "sample1": "", "sample2": "", "dropdown": None},
]


def _excel_col_letter(col_zero_based: int) -> str:
    """Convert 0-indexed column number to Excel letter (0→A, 25→Z, 26→AA)."""
    s = ""
    n = col_zero_based
    while True:
        s = chr(ord("A") + (n % 26)) + s
        n = n // 26 - 1
        if n < 0:
            break
    return s


# ============================================================================
# CSV TEMPLATE
# ============================================================================
@templates_router.get("/templates/csv")
async def download_csv_template():
    """Download CSV import template (derived from ASSET_TEMPLATE_SCHEMA)."""
    headers = [c["field"] for c in ASSET_TEMPLATE_SCHEMA]
    sample1 = [c["sample1"] for c in ASSET_TEMPLATE_SCHEMA]
    sample2 = [c["sample2"] for c in ASSET_TEMPLATE_SCHEMA]

    def _row(values):
        # Wrap each value in double quotes; escape any embedded quotes
        return ",".join(f'"{str(v).replace(chr(34), chr(34)*2)}"' for v in values)

    csv_lines = [",".join(headers), _row(sample1), _row(sample2)]
    csv_content = "\n".join(csv_lines) + "\n"

    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=template_import_aset.csv"},
    )


# ============================================================================
# XLSX TEMPLATE
# ============================================================================
@templates_router.get("/templates/xlsx")
async def download_xlsx_template():
    """Download Excel import template with dropdowns and professional formatting.

    Headers, sample data, dropdowns, widths, and Panduan sheet are all derived
    from a single ASSET_TEMPLATE_SCHEMA list, so they cannot drift out of sync.
    """
    # Resolve dynamic dropdown values (categories from DB)
    categories = await db.categories.find({}, {"_id": 0}).to_list(500)
    cat_labels = [c["label"] for c in categories] if categories else [
        "Elektronik & IT", "Furniture/Mebel", "Kendaraan",
        "Mesin & Peralatan", "Lainnya",
    ]

    n_cols = len(ASSET_TEMPLATE_SCHEMA)

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})

    # === Formats ===
    title_fmt = workbook.add_format({
        "bold": True, "font_size": 16, "font_color": "#1e40af",
        "bottom": 2, "bottom_color": "#3b82f6",
    })
    subtitle_fmt = workbook.add_format({
        "italic": True, "font_size": 10, "font_color": "#64748b",
    })
    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#1e40af", "font_color": "white",
        "align": "center", "valign": "vcenter", "border": 1,
        "text_wrap": True, "font_size": 10,
    })
    required_header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#dc2626", "font_color": "white",
        "align": "center", "valign": "vcenter", "border": 1,
        "text_wrap": True, "font_size": 10,
    })
    sample_fmt = workbook.add_format({
        "align": "left", "valign": "vcenter", "border": 1,
        "font_size": 10, "font_color": "#6b7280", "italic": True,
    })
    note_fmt = workbook.add_format({
        "font_size": 9, "font_color": "#ef4444", "italic": True,
    })

    # === MAIN DATA SHEET ===
    ws = workbook.add_worksheet("Data Import")

    # Merged title spans every column
    last_col_letter = _excel_col_letter(n_cols - 1)
    ws.merge_range(f"A1:{last_col_letter}1", "TEMPLATE IMPORT DATA ASET", title_fmt)
    ws.merge_range(
        f"A2:{last_col_letter}2",
        "Isi data mulai dari baris 5. Kolom merah (*) wajib diisi. "
        "Gunakan dropdown untuk Kategori, Kondisi, Status, Stiker, dan Status Inventarisasi.",
        subtitle_fmt,
    )
    ws.set_row(0, 30)
    ws.set_row(1, 20)
    ws.merge_range(
        f"A3:{last_col_letter}3",
        "ATURAN: asset_code = 10 digit angka | kode_register = 32 karakter hex | "
        "nomor_spm = format: 02847T/621001/2024",
        note_fmt,
    )

    # Headers row (row 4 → 0-indexed 3)
    header_row = 3
    for col, c in enumerate(ASSET_TEMPLATE_SCHEMA):
        label = f"{c['field']} *" if c["required"] else c["field"]
        fmt = required_header_fmt if c["required"] else header_fmt
        ws.write(header_row, col, label, fmt)
    ws.set_row(header_row, 30)

    # Sample rows (rows 5 & 6 → 0-indexed 4 & 5)
    for col, c in enumerate(ASSET_TEMPLATE_SCHEMA):
        ws.write(header_row + 1, col, c["sample1"], sample_fmt)
        ws.write(header_row + 2, col, c["sample2"], sample_fmt)

    # Column widths
    for col, c in enumerate(ASSET_TEMPLATE_SCHEMA):
        ws.set_column(col, col, c["width"])

    # === Hidden helper sheet for dropdown lists that exceed Excel's 255-char
    # inline source limit (Excel allows max 255 chars for comma-joined source).
    # We always create it; xlsxwriter will only reference it for long lists.
    helper = workbook.add_worksheet("_lists")
    helper.hide()
    helper_col = 0  # each long list occupies one column

    # Data validation dropdowns (rows 5-1000 → user data rows)
    for col, c in enumerate(ASSET_TEMPLATE_SCHEMA):
        dropdown = c.get("dropdown")
        if not dropdown:
            continue
        source = cat_labels if dropdown == "_DYNAMIC_CATEGORY_" else dropdown

        # Excel hard limits: input_title 32 chars, error_title 32 chars.
        # If the joined comma source > 255 chars, fall back to a range reference.
        joined_len = sum(len(str(s)) for s in source) + max(0, len(source) - 1)
        if joined_len > 255:
            for i, val in enumerate(source):
                helper.write(i, helper_col, val)
            col_letter = _excel_col_letter(helper_col)
            range_ref = (
                f"=_lists!${col_letter}$1:${col_letter}${len(source)}"
            )
            source_arg = range_ref
            helper_col += 1
        else:
            source_arg = source

        ws.data_validation(
            header_row + 1, col, 1000, col,
            {
                "validate": "list",
                "source": source_arg,
                "input_title": c["field"][:32],
                "input_message": f"Pilih {c['field']}"[:255],
                "error_title": (f"{c['field']} tidak valid")[:32],
                "error_message": "Pilih nilai dari daftar yang tersedia",
            },
        )

    # === PANDUAN SHEET ===
    guide = workbook.add_worksheet("Panduan")
    guide_title = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1e40af"})
    guide_header = workbook.add_format({"bold": True, "bg_color": "#e2e8f0", "border": 1, "font_size": 10})
    guide_cell = workbook.add_format({"border": 1, "font_size": 10, "text_wrap": True, "valign": "top"})
    guide_required = workbook.add_format({
        "border": 1, "font_size": 10, "text_wrap": True, "valign": "top",
        "font_color": "#dc2626", "bold": True,
    })

    guide.set_column(0, 0, 26)
    guide.set_column(1, 1, 9)
    guide.set_column(2, 2, 60)
    guide.set_column(3, 3, 40)

    guide.write(0, 0, "PANDUAN PENGISIAN DATA", guide_title)
    guide.write(2, 0, "Nama Kolom", guide_header)
    guide.write(2, 1, "Wajib?", guide_header)
    guide.write(2, 2, "Aturan / Keterangan", guide_header)
    guide.write(2, 3, "Contoh", guide_header)

    for i, c in enumerate(ASSET_TEMPLATE_SCHEMA):
        row_idx = i + 3
        fmt = guide_required if c["required"] else guide_cell
        wajib = "YA" if c["required"] else "TIDAK"
        # Use the first non-empty sample as Panduan example
        example = c["sample1"] or c["sample2"] or ""
        guide.write(row_idx, 0, c["field"], fmt)
        guide.write(row_idx, 1, wajib, fmt)
        guide.write(row_idx, 2, c["rule"], guide_cell)
        guide.write(row_idx, 3, example, guide_cell)

    workbook.close()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_import_aset.xlsx"},
    )
