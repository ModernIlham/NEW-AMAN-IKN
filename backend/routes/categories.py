"""Category CRUD, bulk import, and progress tracking routes."""
import io
import uuid
import logging
import asyncio
import csv as csv_module
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Depends
from auth_utils import require_admin, require_user, require_writer

from db import db
from models import CategoryCreate
from shared_utils import limiter, invalidate_category_cache, _cache_categories

logger = logging.getLogger(__name__)
categories_router = APIRouter()

# In-memory progress store for bulk category import
import_progress = {}

# ============================================================================
# CATEGORY ROUTES
# ============================================================================

@categories_router.get("/categories")
async def get_categories(search: str = "", page: int = 1, page_size: int = 50,
                         _user: dict = Depends(require_user)):
    """Get categories with search and pagination"""
    import re as _re
    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    query = {}
    if search:
        rx = {"$regex": _re.escape(search.strip()), "$options": "i"}
        query = {"$or": [{"kode_aset": rx}, {"label": rx}]}

    total = await db.categories.count_documents(query)
    skip = (page - 1) * page_size
    categories = await db.categories.find(query, {"_id": 0}).sort("kode_aset", 1).skip(skip).limit(page_size).to_list(page_size)
    
    return {
        "data": categories,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size)
    }

@categories_router.get("/categories/all")
async def get_all_categories(_user: dict = Depends(require_user)):
    """Get all categories (cached for 5 min, for dropdowns)"""
    cache_key = "all"
    if cache_key in _cache_categories:
        return _cache_categories[cache_key]
    categories = await db.categories.find({}, {"_id": 0}).sort("kode_aset", 1).to_list(50000)
    _cache_categories[cache_key] = categories
    return categories

@categories_router.post("/categories")
async def create_category(category: CategoryCreate, _user: dict = Depends(require_writer)):
    """Create a new category (login wajib — temuan review keamanan)."""
    kode = category.kode_aset.strip() if category.kode_aset else ""
    label = category.label.strip()
    
    if not label:
        raise HTTPException(status_code=400, detail="Deskripsi aset wajib diisi")
    
    cat_id = kode if kode else label.replace(" ", "")
    
    existing = await db.categories.find_one({"$or": [{"id": cat_id}, {"kode_aset": kode}]}) if kode else await db.categories.find_one({"id": cat_id})
    if existing:
        raise HTTPException(status_code=400, detail="Kategori dengan kode aset ini sudah ada")
    
    doc = {"id": cat_id, "label": label, "kode_aset": kode}
    await db.categories.insert_one(doc)
    invalidate_category_cache()
    logger.info(f"Category created: {kode} - {label}")

    # Validasi silang LUNAK ke Referensi Kodefikasi (1a, non-blocking):
    # kategori tetap tersimpan; UI menampilkan peringatannya bila ada.
    peringatan = ""
    if kode:
        from kodefikasi_utils import cek_kode_kodefikasi
        terdaftar = set()
        async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
            if k.get("kode"):
                terdaftar.add(str(k["kode"]))
        hasil = cek_kode_kodefikasi(kode, terdaftar)
        if hasil.get("peringatan"):
            peringatan = hasil.get("pesan") or (
                "Kode belum terdaftar di Referensi Kodefikasi")
    return {"id": cat_id, "label": label, "kode_aset": kode,
            "peringatan_kodefikasi": peringatan}

@categories_router.delete("/categories/{category_id}")
async def delete_category(category_id: str, _admin: dict = Depends(require_admin)):
    """Delete a category (login wajib). Ditolak bila masih dipakai aset (temuan #34)."""
    cat = await db.categories.find_one({"id": category_id}, {"_id": 0, "label": 1})
    if cat and str(cat.get("label") or "").strip():
        dipakai = await db.assets.count_documents(
            {"category": cat["label"], "dihapus": {"$ne": True}})
        if dipakai:
            raise HTTPException(
                status_code=409,
                detail=f"Kategori '{cat['label']}' masih dipakai {dipakai} aset — "
                       f"pindahkan aset ke kategori lain dulu.")
    result = await db.categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kategori tidak ditemukan")
    invalidate_category_cache()
    return {"message": "Kategori berhasil dihapus"}

@categories_router.delete("/categories-all")
async def delete_all_categories(_admin: dict = Depends(require_admin)):
    """Delete ALL categories (destruktif — khusus admin, temuan review keamanan)."""
    result = await db.categories.delete_many({})
    invalidate_category_cache()
    logger.info(f"Deleted all categories: {result.deleted_count}")
    return {"message": f"Berhasil menghapus {result.deleted_count} kategori", "deleted": result.deleted_count}

@categories_router.post("/categories/import-bulk")
@limiter.limit("3/minute")
async def import_categories_bulk(request: Request, file: UploadFile = File(...), _user: dict = Depends(require_writer)):
    """Bulk import categories from Excel/CSV with progress tracking. Returns job_id for progress polling."""
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="File harus berformat CSV atau Excel (.xlsx)")
    
    content = await file.read()
    job_id = str(uuid.uuid4())
    
    # Store progress in memory
    import_progress[job_id] = {"status": "parsing", "total": 0, "processed": 0, "imported": 0, "skipped": 0, "errors": 0, "done": False}
    
    # Parse file
    rows = []
    try:
        if filename.endswith('.csv'):
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('latin-1')
            reader = csv_module.DictReader(io.StringIO(text))
            for row in reader:
                cleaned = {}
                for k, v in row.items():
                    if k:
                        cleaned[k.strip().replace('"', '').lower()] = str(v or '').strip().replace('"', '')
                if any(v for v in cleaned.values()):
                    rows.append(cleaned)
        else:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            headers = []
            header_found = False
            for row_data in ws.iter_rows(values_only=True):
                row_strs = [str(c or '').strip().lower() for c in row_data]
                if not header_found:
                    if 'kode aset' in row_strs or 'kode_aset' in row_strs:
                        headers = [str(c or '').strip() for c in row_data]
                        header_found = True
                        continue
                    elif row_strs[0] and any(c.isdigit() for c in row_strs[0]):
                        headers = ['Kode Aset', 'Deskripsi Barang']
                    else:
                        headers = [str(c or '').strip() for c in row_data]
                        header_found = True
                        continue
                
                if not any(c for c in row_data):
                    continue
                row_dict = {}
                for ci, cell in enumerate(row_data):
                    if ci < len(headers):
                        key = headers[ci].lower().replace(' ', '_')
                        row_dict[key] = str(cell or '').strip() if cell is not None else ''
                if any(v for v in row_dict.values()):
                    rows.append(row_dict)
            wb.close()
    except Exception as e:
        import_progress[job_id] = {"status": "error", "total": 0, "processed": 0, "imported": 0, "skipped": 0, "errors": 0, "done": True, "error_message": str(e)}
        raise HTTPException(status_code=400, detail=f"Gagal parse file: {str(e)}")
    
    total = len(rows)
    import_progress[job_id]["total"] = total
    import_progress[job_id]["status"] = "importing"
    
    # Start background import
    asyncio.create_task(_do_bulk_import(job_id, rows))
    
    return {"job_id": job_id, "total": total, "message": f"Import dimulai: {total} data kategori"}

async def _do_bulk_import(job_id: str, rows: list):
    """Background task for bulk category import"""
    from log_setup import set_job_id
    set_job_id(job_id)   # korelasi log ke JOB, bukan request pemicu (task latar)
    progress = import_progress[job_id]
    batch_size = 500
    imported = 0
    skipped = 0
    errors = 0
    
    # Get existing kode_aset set for fast duplicate check
    existing_codes = set()
    async for doc in db.categories.find({}, {"kode_aset": 1, "_id": 0}):
        if doc.get("kode_aset"):
            existing_codes.add(doc["kode_aset"])
    
    batch = []
    for idx, row in enumerate(rows):
        # Map various possible column names
        kode = row.get('kode_aset', '') or row.get('kode aset', '') or row.get('kode', '') or ''
        kode = str(kode).strip().replace('.0', '')  # handle Excel float formatting
        # Pad to 10 digits if numeric
        if kode.isdigit() and len(kode) < 10:
            kode = kode.zfill(10)
        
        deskripsi = row.get('deskripsi_barang', '') or row.get('deskripsi barang', '') or row.get('deskripsi', '') or row.get('label', '') or row.get('nama', '') or ''
        deskripsi = str(deskripsi).strip()
        
        if not kode or not deskripsi:
            errors += 1
            progress["processed"] = idx + 1
            progress["errors"] = errors
            continue
        
        if kode in existing_codes:
            skipped += 1
            progress["processed"] = idx + 1
            progress["skipped"] = skipped
            continue
        
        existing_codes.add(kode)
        batch.append({
            "id": kode,
            "kode_aset": kode,
            "label": deskripsi
        })
        
        if len(batch) >= batch_size:
            try:
                await db.categories.insert_many(batch, ordered=False)
                imported += len(batch)
            except Exception as e:
                # Handle partial failures (duplicate key etc)
                imported += len(batch) - getattr(e, 'details', {}).get('nInserted', 0) if hasattr(e, 'details') else len(batch)
                logger.error(f"Batch insert error: {e}")
            batch = []
            progress["imported"] = imported
            progress["processed"] = idx + 1
    
    # Insert remaining batch
    if batch:
        try:
            await db.categories.insert_many(batch, ordered=False)
            imported += len(batch)
        except Exception as e:
            logger.error(f"Final batch error: {e}")
    
    progress["imported"] = imported
    progress["skipped"] = skipped
    progress["errors"] = errors
    progress["processed"] = len(rows)
    progress["status"] = "done"
    progress["done"] = True
    logger.info(f"Bulk import complete: {imported} imported, {skipped} skipped, {errors} errors")
    invalidate_category_cache()
    
    # Auto-cleanup: remove progress entry after 5 minutes to prevent memory leaks
    await asyncio.sleep(300)
    import_progress.pop(job_id, None)

@categories_router.get("/categories/import-progress/{job_id}")
async def get_import_progress(job_id: str, _user: dict = Depends(require_user)):
    """Get import progress for a job"""
    if job_id not in import_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    return import_progress[job_id]

