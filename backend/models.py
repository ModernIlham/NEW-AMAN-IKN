"""
Pydantic models for the Inventory Management System.
Shared by server.py and route modules.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


class UserCreate(BaseModel):
    username: str
    password: str
    name: str = ""

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    name: str
    role: str = "user"
    is_active: bool = True
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class OTPRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class OTPVerify(BaseModel):
    email: str
    otp: str

class UserUpdate(BaseModel):
    name: str

class CategoryCreate(BaseModel):
    label: str
    kode_aset: Optional[str] = ""

class CategoryResponse(BaseModel):
    id: str
    label: str
    kode_aset: Optional[str] = ""

class DocumentCheckItem(BaseModel):
    name: str
    checked: bool = False
    notes: Optional[str] = ""
    photos: Optional[List[str]] = []
    documents: Optional[List[dict]] = []

class AssetCreate(BaseModel):
    asset_code: str
    NUP: Optional[str] = ""
    asset_name: str
    category: str
    brand: Optional[str] = ""
    model: Optional[str] = ""
    kode_register: Optional[str] = ""
    serial_number: Optional[str] = ""
    purchase_date: Optional[str] = ""
    purchase_price: Optional[str] = ""
    location: Optional[str] = ""
    eselon1: Optional[str] = ""
    eselon2: Optional[str] = ""
    user: Optional[str] = ""
    condition: Optional[str] = "Baik"
    status: Optional[str] = "Aktif"
    nomor_spm: Optional[str] = ""
    perolehan_dari_nama: Optional[str] = ""
    nomor_kontrak: Optional[str] = ""
    nomor_bukti_perolehan: Optional[str] = ""
    supplier: Optional[str] = ""
    notes: Optional[str] = ""
    photo: Optional[str] = None
    photos: Optional[List[str]] = []
    thumbnail: Optional[str] = None
    thumbnail_index: Optional[int] = 0
    document_checklist: Optional[List[DocumentCheckItem]] = []
    activity_id: Optional[str] = None
    stiker_status: Optional[str] = "Belum Terpasang"
    stiker_ukuran: Optional[str] = ""
    stiker_photo_index: Optional[int] = None
    inventory_status: Optional[str] = "Belum Diinventarisasi"
    klasifikasi_tidak_ditemukan: Optional[str] = ""
    sub_klasifikasi: Optional[str] = ""
    uraian_tidak_ditemukan: Optional[str] = ""
    tindak_lanjut: Optional[str] = ""
    koordinat_latitude: Optional[str] = ""
    koordinat_longitude: Optional[str] = ""
    kronologis: Optional[str] = ""
    keterangan_berlebih: Optional[str] = ""
    asal_usul_berlebih: Optional[str] = ""
    nomor_perkara: Optional[str] = ""
    pihak_bersengketa: Optional[str] = ""
    keterangan_sengketa: Optional[str] = ""

class DocumentCheckItemResponse(BaseModel):
    """Response model for document checklist items - includes photo/doc counts for exclude_media mode"""
    name: str
    checked: bool = False
    notes: Optional[str] = ""
    photos: Optional[List[str]] = []
    documents: Optional[List[dict]] = []
    photo_count: Optional[int] = None  # Added for exclude_media mode
    document_count: Optional[int] = None  # Added for exclude_media mode

class AssetResponse(BaseModel):
    id: str
    asset_code: str
    NUP: Optional[str] = ""
    asset_name: str
    category: str
    brand: Optional[str] = ""
    model: Optional[str] = ""
    kode_register: Optional[str] = ""
    serial_number: Optional[str] = ""
    purchase_date: Optional[str] = ""
    purchase_price: Optional[Any] = ""
    location: Optional[str] = ""
    eselon1: Optional[str] = ""
    eselon2: Optional[str] = ""
    user: Optional[str] = ""
    condition: Optional[str] = "Baik"
    status: Optional[str] = "Aktif"
    nomor_spm: Optional[str] = ""
    perolehan_dari_nama: Optional[str] = ""
    nomor_kontrak: Optional[str] = ""
    nomor_bukti_perolehan: Optional[str] = ""
    supplier: Optional[str] = ""
    notes: Optional[str] = ""
    photo: Optional[str] = None
    photos: Optional[List[str]] = []
    photo_count: Optional[int] = None  # Added for exclude_media mode
    photo_thumbnails: Optional[List[str]] = []
    photo_gridfs_ids: Optional[List[str]] = []
    thumbnail: Optional[str] = None
    thumbnail_index: Optional[int] = 0
    document_checklist: Optional[List[DocumentCheckItemResponse]] = []
    activity_id: Optional[str] = None
    stiker_status: Optional[str] = "Belum Terpasang"
    stiker_ukuran: Optional[str] = ""
    stiker_photo_index: Optional[int] = None
    inventory_status: Optional[str] = "Belum Diinventarisasi"
    klasifikasi_tidak_ditemukan: Optional[str] = ""
    sub_klasifikasi: Optional[str] = ""
    uraian_tidak_ditemukan: Optional[str] = ""
    tindak_lanjut: Optional[str] = ""
    koordinat_latitude: Optional[str] = ""
    koordinat_longitude: Optional[str] = ""
    kronologis: Optional[str] = ""
    keterangan_berlebih: Optional[str] = ""
    asal_usul_berlebih: Optional[str] = ""
    nomor_perkara: Optional[str] = ""
    pihak_bersengketa: Optional[str] = ""
    keterangan_sengketa: Optional[str] = ""
    created_at: str
    # Optimistic Concurrency Control — incremented on every write
    version: Optional[int] = 1

    @field_validator('purchase_price', mode='before')
    @classmethod
    def convert_purchase_price(cls, v):
        if v is None:
            return ""
        return str(v) if not isinstance(v, str) else v

class InventoryActivityCreate(BaseModel):
    nama_kegiatan: str
    nomor_surat: Optional[str] = ""
    tanggal_mulai: Optional[str] = ""
    tanggal_selesai: Optional[str] = ""
    penanggung_jawab: Optional[str] = ""
    keterangan: Optional[str] = ""
    tim_pelaksana: Optional[List[str]] = []
    kasatker: Optional[dict] = {}
    berita_acara: Optional[dict] = {}
    tim_peneliti: Optional[List[dict]] = []
    kasatker_nama: Optional[str] = ""
    kasatker_nip: Optional[str] = ""
    kasatker_jabatan: Optional[str] = ""
    alamat_satker: Optional[str] = ""
    nomor_berita_acara: Optional[str] = ""
    tanggal_berita_acara: Optional[str] = ""
    kesimpulan: Optional[str] = ""

class InventoryActivityResponse(BaseModel):
    id: str
    nama_kegiatan: str
    nomor_surat: Optional[str] = ""
    tanggal_mulai: Optional[str] = ""
    tanggal_selesai: Optional[str] = ""
    penanggung_jawab: Optional[str] = ""
    keterangan: Optional[str] = ""
    status: Optional[str] = "Aktif"
    tim_pelaksana: Optional[List[str]] = []
    kasatker: Optional[dict] = {}
    berita_acara: Optional[dict] = {}
    tim_peneliti: Optional[List[dict]] = []
    kasatker_nama: Optional[str] = ""
    kasatker_nip: Optional[str] = ""
    kasatker_jabatan: Optional[str] = ""
    alamat_satker: Optional[str] = ""
    nomor_berita_acara: Optional[str] = ""
    tanggal_berita_acara: Optional[str] = ""
    kesimpulan: Optional[str] = ""
    created_at: str
    total_assets: Optional[int] = 0

class ResetConfirmation(BaseModel):
    admin_id: str
    confirmation: str
