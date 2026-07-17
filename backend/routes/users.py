"""User management routes (admin functions)."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from db import db
from models import UserUpdate
from auth_utils import hash_password, require_admin

logger = logging.getLogger(__name__)
users_router = APIRouter()

# ============================================================================
# USER MANAGEMENT (admin only)
# ============================================================================

@users_router.get("/users")
async def get_all_users(admin_id: str = "", _admin: dict = Depends(require_admin)):
    """Get all users (admin only — ditegakkan lewat JWT, bukan param).

    Temuan review keamanan: dulu cek admin hanya berjalan bila param `admin_id`
    dikirim, sehingga GET /users tanpa param bocor tanpa autentikasi. Param
    `admin_id` dipertahankan demi kompatibilitas pemanggil lama, tetapi
    otorisasi kini dari token (require_admin).
    """
    if admin_id:
        admin_user = await db.users.find_one({"id": admin_id})
        if not admin_user or admin_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Hanya admin yang dapat mengakses daftar user")
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(100)
    now = datetime.now(timezone.utc)
    for u in users:
        if u.get("role") == "user":
            u["role"] = "operator"
        # Calculate online status (active within last 5 minutes)
        last_active = u.get("last_active", "")
        if last_active:
            try:
                la_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                diff = (now - la_dt).total_seconds()
                u["is_online"] = diff < 300  # 5 minutes
            except (ValueError, TypeError):
                u["is_online"] = False
        else:
            u["is_online"] = False
    return users

@users_router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, admin_id: str = "", _admin: dict = Depends(require_admin)):
    """Toggle user active status (admin only, cannot toggle self)"""
    # Guard "self" dari identitas TERAUTENTIKASI — bukan param opsional yang
    # bisa dikosongkan pemanggil (temuan audit keandalan Jul 2026).
    if _admin.get("id") == user_id:
        raise HTTPException(status_code=400, detail="Admin tidak dapat menonaktifkan dirinya sendiri")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    current_active = user.get("is_active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": not current_active}})
    return {"message": f"User {'dinonaktifkan' if current_active else 'diaktifkan'}", "is_active": not current_active}

@users_router.put("/users/{user_id}/change-password")
async def change_user_password(user_id: str, data: dict, _admin: dict = Depends(require_admin)):
    """Change user password"""
    new_password = data.get("new_password", "")
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Password minimal 4 karakter")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    hashed = hash_password(new_password)
    await db.users.update_one({"id": user_id}, {"$set": {"password": hashed}})
    return {"message": "Password berhasil diubah"}

@users_router.put("/users/{user_id}/update-name")
async def update_user_name(user_id: str, data: UserUpdate, admin_id: str = "", _admin: dict = Depends(require_admin)):
    """Update user name (admin only, or self)"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    new_name = data.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Nama tidak boleh kosong")
    
    await db.users.update_one({"id": user_id}, {"$set": {"name": new_name}})
    return {"message": "Nama berhasil diubah", "name": new_name}

@users_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin_id: str = "", _admin: dict = Depends(require_admin)):
    """Delete a user (admin only, cannot delete self)"""
    if _admin.get("id") == user_id:
        raise HTTPException(status_code=400, detail="Admin tidak dapat menghapus dirinya sendiri")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    await db.users.delete_one({"id": user_id})
    return {"message": "User berhasil dihapus"}

@users_router.put("/users/{user_id}/change-role")
async def change_user_role(user_id: str, data: dict, _admin: dict = Depends(require_admin)):
    """Change user role (admin only; tidak boleh menurunkan role diri sendiri)"""
    new_role = data.get("new_role") or data.get("role", "user")

    # Admin men-demote dirinya = satker bisa kehilangan admin terakhir.
    if _admin.get("id") == user_id and new_role != "admin":
        raise HTTPException(status_code=400,
                            detail="Admin tidak dapat menurunkan role dirinya sendiri")

    if new_role not in ["admin", "operator", "viewer"]:
        raise HTTPException(status_code=400, detail="Role harus admin, operator, atau viewer")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    await db.users.update_one({"id": user_id}, {"$set": {"role": new_role}})
    return {"message": f"Role user diubah menjadi {new_role}", "role": new_role}

