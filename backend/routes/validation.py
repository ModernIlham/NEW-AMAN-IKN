"""Asset data validation route."""
import logging
from fastapi import APIRouter, HTTPException

from db import db
from models import AssetCreate
from routes.imports import validate_import_row

logger = logging.getLogger(__name__)
validation_router = APIRouter()

# ============================================================================
# ASSET VALIDATION ENDPOINT (for form validation matching import rules)
# ============================================================================

@validation_router.post("/assets/validate")
async def validate_asset_data(asset: AssetCreate, exclude_id: str = ""):
    """Validate asset data using the same rules as import. exclude_id is used when editing to skip self."""
    # Get ALL categories (not just 100)
    categories = await db.categories.find({}, {"_id": 0}).to_list(100000)
    valid_categories = [cat["label"] for cat in categories] + [cat.get("id", "") for cat in categories] + [cat.get("kode_aset", "") for cat in categories if cat.get("kode_aset")]
    
    # Build category_map for kode_aset -> label validation (only needed for import, not manual input)
    # For manual input, we just check if category exists in valid list
    
    row_data = {
        "asset_code": asset.asset_code,
        "asset_name": asset.asset_name,
        "category": asset.category,
        "kode_register": asset.kode_register or "",
        "nomor_spm": asset.nomor_spm or "",
        "condition": asset.condition or "",
        "status": asset.status or "",
    }
    
    # For manual input validation, don't use category_map (no kode_aset->label enforcement)
    errors = validate_import_row(row_data, valid_categories, 0, category_map=None)
    errors = [e.replace("Baris 0: ", "") for e in errors]
    
    # Check asset_code + NUP uniqueness within activity (exclude self when editing)
    if asset.asset_code and asset.activity_id:
        dup_query = {
            "asset_code": asset.asset_code,
            "NUP": asset.NUP or "",
            "activity_id": asset.activity_id
        }
        if exclude_id:
            dup_query["id"] = {"$ne": exclude_id}
        existing = await db.assets.find_one(dup_query)
        if existing:
            errors.append(f"Kombinasi Kode Barang '{asset.asset_code}' dan NUP '{asset.NUP}' sudah digunakan dalam kegiatan ini")
    
    # Check kode_register uniqueness within activity (exclude self when editing)
    if asset.kode_register and asset.activity_id:
        kr_query = {
            "kode_register": asset.kode_register,
            "activity_id": asset.activity_id
        }
        if exclude_id:
            kr_query["id"] = {"$ne": exclude_id}
        kr_existing = await db.assets.find_one(kr_query)
        if kr_existing:
            errors.append(f"Kode Register '{asset.kode_register}' sudah digunakan dalam kegiatan ini")
    
    return {"valid": len(errors) == 0, "errors": errors}
