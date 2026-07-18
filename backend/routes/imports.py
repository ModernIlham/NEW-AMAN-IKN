"""Asset import from CSV/Excel with validation."""
import io
import uuid
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Header, Depends
import csv as csv_module

from asset_fields import ASSET_SCALAR_FIELDS, import_row_value
from db import db
from models import AssetCreate
from auth_utils import require_user, require_writer
from shared_utils import (
    limiter, invalidate_asset_cache, log_audit, create_thumbnail,
    VALID_INVENTORY_STATUSES, VALID_KLASIFIKASI, VALID_SUB_KLASIFIKASI_ALL,
    VALID_SUB_KLASIFIKASI_PENCATATAN, VALID_SUB_KLASIFIKASI_LAINNYA,
    VALID_CONDITIONS, VALID_STATUSES, VALID_STIKER_STATUSES, VALID_STIKER_SIZES
)

logger = logging.getLogger(__name__)
imports_router = APIRouter()

# ============================================================================
# IMPORT ROUTES
# ============================================================================

import re

# Required fields for import
REQUIRED_IMPORT_FIELDS = ["asset_code", "asset_name", "category"]

def validate_asset_code(code: str) -> str:
    """Validate asset_code: must be exactly 10 digits"""
    if not code:
        return "asset_code wajib diisi"
    code = str(code).strip()
    if not re.match(r'^\d{10}$', code):
        return f"asset_code '{code}' harus tepat 10 digit angka"
    return ""

def validate_kode_register(kode: str) -> str:
    """Validate kode_register: must be exactly 32 characters alphanumeric"""
    if not kode:
        return ""  # optional
    kode = str(kode).strip()
    if len(kode) != 32:
        return f"kode_register '{kode}' harus tepat 32 karakter (saat ini {len(kode)} karakter)"
    if not re.match(r'^[A-Fa-f0-9]{32}$', kode):
        return f"kode_register '{kode}' harus berisi karakter hex (0-9, A-F)"
    return ""

def validate_nomor_spm(nomor: str) -> str:
    """Validate nomor_spm: format like 02847T/621001/2024"""
    if not nomor:
        return ""  # optional
    nomor = str(nomor).strip()
    # Pattern: digits+letter(s)/digits/digits (year)
    if not re.match(r'^\d+[A-Za-z]*/\d+/\d{4}$', nomor):
        return f"nomor_spm '{nomor}' harus sesuai format (contoh: 02847T/621001/2024)"
    return ""

def validate_import_row(row_data: dict, valid_categories: list, row_num: int, category_map: dict = None) -> list:
    """Validate a single import row. Returns list of error messages.
    category_map: dict mapping kode_aset -> label (deskripsi) for validation
    """
    errors = []
    
    # Required fields check
    for field in REQUIRED_IMPORT_FIELDS:
        val = str(row_data.get(field, '')).strip()
        if not val:
            errors.append(f"Baris {row_num}: Kolom '{field}' wajib diisi")
    
    # asset_code validation
    asset_code = str(row_data.get('asset_code', '')).strip()
    ac_err = validate_asset_code(asset_code)
    if ac_err:
        errors.append(f"Baris {row_num}: {ac_err}")
    
    # category must be in valid list
    cat = str(row_data.get('category', '')).strip()
    if cat and cat not in valid_categories:
        errors.append(f"Baris {row_num}: category '{cat}' tidak ada dalam daftar kategori")
    
    # Validate asset_code matches category description (kode_aset -> label)
    if category_map and asset_code and cat:
        expected_label = category_map.get(asset_code)
        if expected_label:
            # asset_code found in categories, check if category matches the label
            if cat != expected_label:
                errors.append(f"Baris {row_num}: Kode aset '{asset_code}' terdaftar dengan deskripsi '{expected_label}', tetapi category diisi '{cat}'. Harap sesuaikan category dengan deskripsi yang benar.")
    
    # kode_register validation
    kr_err = validate_kode_register(row_data.get('kode_register', ''))
    if kr_err:
        errors.append(f"Baris {row_num}: {kr_err}")
    
    # nomor_spm validation
    spm_err = validate_nomor_spm(row_data.get('nomor_spm', ''))
    if spm_err:
        errors.append(f"Baris {row_num}: {spm_err}")
    
    # condition validation
    cond = str(row_data.get('condition', '')).strip()
    if cond and cond not in VALID_CONDITIONS:
        errors.append(f"Baris {row_num}: condition '{cond}' tidak valid. Pilihan: {', '.join(VALID_CONDITIONS)}")
    
    # status validation
    stat = str(row_data.get('status', '')).strip()
    if stat and stat not in VALID_STATUSES:
        errors.append(f"Baris {row_num}: status '{stat}' tidak valid. Pilihan: {', '.join(VALID_STATUSES)}")
    
    # stiker_status validation
    stiker_st = str(row_data.get('stiker_status', '')).strip()
    if stiker_st and stiker_st not in VALID_STIKER_STATUSES:
        errors.append(f"Baris {row_num}: stiker_status '{stiker_st}' tidak valid. Pilihan: {', '.join(VALID_STIKER_STATUSES)}")
    
    # stiker_ukuran validation
    stiker_uk = str(row_data.get('stiker_ukuran', '')).strip()
    if stiker_uk and stiker_uk not in VALID_STIKER_SIZES:
        errors.append(f"Baris {row_num}: stiker_ukuran '{stiker_uk}' tidak valid. Pilihan: {', '.join(VALID_STIKER_SIZES)}")
    
    # inventory_status validation
    inv_st = str(row_data.get('inventory_status', '')).strip()
    if inv_st and inv_st not in VALID_INVENTORY_STATUSES:
        errors.append(f"Baris {row_num}: inventory_status '{inv_st}' tidak valid. Pilihan: {', '.join(VALID_INVENTORY_STATUSES)}")
    
    # klasifikasi_tidak_ditemukan validation
    klas = str(row_data.get('klasifikasi_tidak_ditemukan', '')).strip()
    if klas and klas not in VALID_KLASIFIKASI:
        errors.append(f"Baris {row_num}: klasifikasi_tidak_ditemukan '{klas}' tidak valid. Pilihan: {', '.join(VALID_KLASIFIKASI)}")
    
    # sub_klasifikasi validation
    sub_klas = str(row_data.get('sub_klasifikasi', '')).strip()
    if sub_klas and sub_klas not in VALID_SUB_KLASIFIKASI_ALL:
        errors.append(f"Baris {row_num}: sub_klasifikasi '{sub_klas}' tidak valid.")
    
    return errors

def parse_csv_content(content: bytes) -> list:
    """Parse CSV content and return list of dicts"""
    # Try UTF-8, then latin-1
    try:
        csv_text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        csv_text = content.decode('latin-1')
    
    reader = csv_module.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        cleaned = {}
        for key, val in row.items():
            if key:
                cleaned[key.strip().replace('"', '')] = str(val or '').strip().replace('"', '')
        if any(v for v in cleaned.values()):
            rows.append(cleaned)
    return rows

def parse_excel_content(content: bytes) -> tuple:
    """Parse Excel content and return (list of dicts, header_row_number)"""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    
    # Find the header row by looking for 'asset_code' in any cell
    header_row_idx = None
    headers = []
    all_rows = list(ws.iter_rows(values_only=True))
    
    for row_idx, row in enumerate(all_rows):
        row_strs = [str(cell or '').strip().lower().replace('*', '').strip() for cell in row]
        if 'asset_code' in row_strs or 'asset_code *' in row_strs:
            header_row_idx = row_idx
            # Clean header names - remove *, whitespace
            headers = []
            for cell in row:
                h = str(cell or '').strip().replace('*', '').strip()
                headers.append(h)
            break
    
    if header_row_idx is None:
        # Fallback: try first row as header
        header_row_idx = 0
        headers = [str(cell or '').strip() for cell in all_rows[0]]
    
    rows_data = []
    for row_idx in range(header_row_idx + 1, len(all_rows)):
        row = all_rows[row_idx]
        if not any(cell for cell in row):
            continue
        row_dict = {}
        for col_idx, cell in enumerate(row):
            if col_idx < len(headers) and headers[col_idx]:
                row_dict[headers[col_idx]] = str(cell or '').strip() if cell is not None else ''
        if any(v for v in row_dict.values()):
            rows_data.append(row_dict)
    
    # Return data and the Excel row number where data starts (1-indexed for user display)
    return rows_data, header_row_idx + 2  # +2 because header_row_idx is 0-based and data starts after header

@imports_router.post("/import")
@limiter.limit("3/minute")
async def import_assets(request: Request, file: UploadFile = File(...), force_update: bool = False, activity_id: str = "", _user: dict = Depends(require_writer)):
    """Import assets from CSV or Excel file with comprehensive validation"""
    if not activity_id:
        raise HTTPException(status_code=400, detail="activity_id diperlukan untuk import")
    
    # Verify activity exists
    activity = await db.inventory_activities.find_one({"id": activity_id})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan inventarisasi tidak ditemukan")
    if activity.get("status_pengesahan") == "disahkan":
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    filename = (file.filename or "").lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="File harus berformat CSV atau Excel (.xlsx)")

    try:
        content = await file.read()
        # Batas ukuran (cegah zip-bomb/decompression openpyxl & OOM).
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Berkas melebihi 15MB")
        
        # Parse file
        if filename.endswith('.csv'):
            rows = parse_csv_content(content)
            data_start_row = 2  # CSV: row 1 is header, data starts at row 2
        else:
            rows, data_start_row = parse_excel_content(content)
        
        if not rows:
            raise HTTPException(status_code=400, detail="File kosong atau tidak ada data valid")
        
        # Get valid categories and build mapping kode_aset -> label
        categories = await db.categories.find({}, {"_id": 0, "label": 1, "kode_aset": 1}).to_list(100000)
        valid_categories = [cat.get("label", "") for cat in categories] + [cat.get("kode_aset", "") for cat in categories if cat.get("kode_aset")]
        # Map kode_aset to label for validation
        category_map = {cat.get("kode_aset", ""): cat.get("label", "") for cat in categories if cat.get("kode_aset")}
        
        # Get existing assets in this activity for duplicate check
        existing_assets = await db.assets.find(
            {"activity_id": activity_id},
            {"_id": 0, "asset_code": 1, "NUP": 1}
        ).to_list(None)
        existing_asset_keys = {(a.get("asset_code", ""), a.get("NUP", "")) for a in existing_assets}
        
        # Validate ALL rows first
        all_errors = []
        
        # Check for duplicates WITHIN the imported file itself
        seen_keys = {}
        for idx, row in enumerate(rows):
            asset_code = str(row.get('asset_code', '')).strip()
            nup = str(row.get('NUP', '')).strip()
            kode_register = str(row.get('kode_register', '')).strip()
            
            # Check Kode Aset + NUP duplicate within file
            file_key = (asset_code, nup)
            if file_key in seen_keys and asset_code:
                prev_row = seen_keys[file_key]
                all_errors.append(f"Baris {data_start_row + idx}: Data ganda dalam file - Kode Aset '{asset_code}' + NUP '{nup}' sudah ada di Baris {prev_row}")
            elif asset_code:
                seen_keys[file_key] = data_start_row + idx
            
            # Check Kode Register duplicate within file
            if kode_register:
                kr_key = ("kr", kode_register)
                if kr_key in seen_keys:
                    prev_row = seen_keys[kr_key]
                    all_errors.append(f"Baris {data_start_row + idx}: Data ganda dalam file - Kode Register '{kode_register}' sudah ada di Baris {prev_row}")
                else:
                    seen_keys[kr_key] = data_start_row + idx
        
        for idx, row in enumerate(rows):
            row_errors = validate_import_row(row, valid_categories, data_start_row + idx, category_map)
            all_errors.extend(row_errors)
            
            # Check for duplicates within existing data in this activity
            asset_code = str(row.get('asset_code', '')).strip()
            nup = str(row.get('NUP', '')).strip()
            if (asset_code, nup) in existing_asset_keys:
                all_errors.append(f"Baris {data_start_row + idx}: Kode Barang '{asset_code}' dan NUP '{nup}' sudah ada dalam kegiatan ini. Data duplikat akan ditolak.")
        
        # If any errors, reject ALL data
        if all_errors:
            return {
                "success": False,
                "message": f"Validasi gagal: {len(all_errors)} kesalahan ditemukan. Semua data ditolak.",
                "errors": all_errors,
                "imported": 0,
                "skipped": len(rows),
                "duplicates": []
            }
        
        # Check for duplicates WITHIN THE SAME ACTIVITY only
        duplicates = []
        new_rows = []
        for idx, row in enumerate(rows):
            asset_code = str(row.get('asset_code', '')).strip()
            nup = str(row.get('NUP', '')).strip()
            existing = await db.assets.find_one({"asset_code": asset_code, "NUP": nup, "activity_id": activity_id})
            if existing:
                duplicates.append({
                    "row": data_start_row + idx,
                    "asset_code": asset_code,
                    "asset_name": row.get('asset_name', ''),
                    "existing_name": existing.get('asset_name', '')
                })
            else:
                new_rows.append(row)
        
        # If duplicates found and not force_update, return info
        if duplicates and not force_update:
            return {
                "success": False,
                "message": f"Ditemukan {len(duplicates)} data duplikat. Pilih untuk mengupdate atau membatalkan.",
                "errors": [],
                "imported": 0,
                "skipped": 0,
                "duplicates": duplicates,
                "total_new": len(new_rows)
            }
        
        # Setelan opt-in "wajib pegawai terdaftar" berlaku juga utk impor
        # (temuan #29). Set NIP dimuat SEKALI (bukan query per baris); baris
        # melanggar dilewati sebagai error baris — bukan menolak seluruh file.
        _settings = await db.report_settings.find_one(
            {"type": "global"}, {"_id": 0, "wajib_pegawai_terdaftar": 1}) or {}
        wajib_pegawai = bool(_settings.get("wajib_pegawai_terdaftar"))
        nip_terdaftar = set()
        if wajib_pegawai:
            nip_terdaftar = {str(n).strip() for n in await db.pegawai.distinct("nip")
                             if str(n or "").strip()}
        pegawai_errors = []

        # Process import
        imported = 0
        updated = 0

        for row in rows:
            asset_code = str(row.get('asset_code', '')).strip()
            nup = str(row.get('NUP', '')).strip()
            existing = await db.assets.find_one({"asset_code": asset_code, "NUP": nup, "activity_id": activity_id})

            # Semua field skalar dipetakan dari registry (asset_fields.py) —
            # field baru otomatis ikut ter-impor tanpa mengedit mapping ini.
            asset_data = {f.name: import_row_value(row, f) for f in ASSET_SCALAR_FIELDS}
            asset_data["asset_code"] = asset_code
            asset_data["activity_id"] = activity_id

            _nip = str(asset_data.get("pengguna_nip") or "").strip()
            if wajib_pegawai and _nip and _nip not in nip_terdaftar:
                pegawai_errors.append(
                    f"{asset_code} NUP {nup}: NIP '{_nip}' belum terdaftar di Master Pegawai")
                continue
            
            if existing and force_update:
                # Update existing within the same activity
                await db.assets.update_one(
                    {"asset_code": asset_code, "NUP": nup, "activity_id": activity_id},
                    {"$set": asset_data}
                )
                updated += 1
            elif not existing:
                # Create new
                asset_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                asset_data["id"] = asset_id
                asset_data["photo"] = None
                asset_data["photos"] = []
                asset_data["thumbnail"] = None
                asset_data["document_checklist"] = []
                asset_data["stiker_photo_index"] = None
                asset_data["created_at"] = now
                await db.assets.insert_one(asset_data)
                imported += 1
        
        logger.info(f"Import: {imported} new, {updated} updated")
        invalidate_asset_cache()
        
        return {
            "success": True,
            "message": f"Berhasil import {imported} aset baru"
                       + (f", {updated} aset diupdate" if updated else "")
                       + (f", {len(pegawai_errors)} baris dilewati (NIP tak terdaftar)"
                          if pegawai_errors else ""),
            "errors": pegawai_errors[:20],
            "imported": imported,
            "updated": updated,
            "duplicates": []
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=400, detail=f"Gagal import: {str(e)}")

