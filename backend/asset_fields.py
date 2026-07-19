"""Registry field skalar aset — SATU sumber kebenaran.

Latar belakang (docs/REFACTORING_REVIEW.md rekomendasi #1): menambah satu
field aset dulu menyentuh 13+ titik dan sebagian sempat terlewat (kelas bug
"ada di form tapi hilang di ekspor/impor/audit"). Registry ini menurunkan
daftar-daftar backend supaya titik sentuh mengecil dan drift tertangkap test.

Menambah field skalar (string) baru pada aset:
  1. Tambahkan AssetField pada ASSET_SCALAR_FIELDS di bawah — tentukan label
     kolom XLSX, flag ``batchable`` (boleh diubah massal), dan default impor.
  2. Tambahkan field yang sama di models.py (AssetCreate + AssetResponse).
  3. Tambahkan kolomnya pada sheet "Data Aset" ekspor XLSX (exports.py) dan
     baris template impor (templates.py) — test registry menagih keduanya.
  4. Frontend: emptyForm/buildEditFormData/TEXT_FIELDS (AssetForm.jsx),
     SNAPSHOT_FIELDS (offlineSnapshot.js), dan input UI-nya.
PATCH per-aset, ubah massal, audit trail, proyeksi list, dan kolom CSV/impor
ikut otomatis dari registry ini. backend/tests/unit/test_asset_field_registry.py
menjaga semua turunan tetap selaras dengan model Pydantic.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetField:
    name: str
    xlsx_label: str            # label kolom sheet "Data Aset" pada ekspor XLSX
    batchable: bool = False    # boleh diubah massal (BATCH_ALLOWED_FIELDS)
    import_default: str = ""   # dipakai saat kolom tidak ada di file impor
    import_force_default: bool = False  # terapkan juga saat nilai impor kosong


# Urutan tuple = urutan kolom CSV ekspor, mapping impor, dan audit trail.
ASSET_SCALAR_FIELDS = (
    AssetField("asset_code", "Kode Aset"),
    AssetField("NUP", "NUP"),
    AssetField("asset_name", "Nama Aset"),
    AssetField("category", "Kategori", batchable=True, import_default="Lainnya"),
    AssetField("brand", "Brand", batchable=True),
    AssetField("model", "Model", batchable=True),
    AssetField("kode_register", "Kode Register"),
    AssetField("serial_number", "Serial Number"),
    AssetField("purchase_date", "Tgl Beli", batchable=True),
    AssetField("purchase_price", "Harga", batchable=True),
    AssetField("location", "Lokasi", batchable=True),
    AssetField("eselon1", "Eselon I", batchable=True),
    AssetField("eselon2", "Eselon II", batchable=True),
    AssetField("user", "Pengguna", batchable=True),
    AssetField("pengguna_melekat_ke", "Melekat Ke", batchable=True),
    AssetField("pengguna_jabatan", "Jabatan Pengguna", batchable=True),
    AssetField("pengguna_nip", "NIP/NIK Pegawai", batchable=True),
    AssetField("operasional_jenis", "Jenis Operasional", batchable=True),
    AssetField("nomor_bast", "Nomor BAST", batchable=True),
    AssetField("condition", "Kondisi", batchable=True,
               import_default="Baik", import_force_default=True),
    AssetField("status", "Status", batchable=True,
               import_default="Aktif", import_force_default=True),
    AssetField("nomor_spm", "Nomor SPM", batchable=True),
    AssetField("perolehan_dari_nama", "Perolehan Dari", batchable=True),
    AssetField("nomor_kontrak", "Nomor Kontrak", batchable=True),
    AssetField("nomor_bukti_perolehan", "Bukti Perolehan", batchable=True),
    AssetField("supplier", "Supplier", batchable=True),
    AssetField("notes", "Catatan", batchable=True),
    AssetField("stiker_status", "Stiker Status", batchable=True,
               import_default="Belum Terpasang", import_force_default=True),
    AssetField("stiker_ukuran", "Ukuran Stiker", batchable=True),
    AssetField("inventory_status", "Status Inventarisasi", batchable=True,
               import_default="Belum Diinventarisasi", import_force_default=True),
    AssetField("klasifikasi_tidak_ditemukan", "Klasifikasi"),
    AssetField("sub_klasifikasi", "Sub Klasifikasi"),
    AssetField("uraian_tidak_ditemukan", "Uraian Tidak Ditemukan"),
    AssetField("tindak_lanjut", "Tindak Lanjut"),
    AssetField("koordinat_latitude", "Latitude", batchable=True),
    AssetField("koordinat_longitude", "Longitude", batchable=True),
    AssetField("kronologis", "Kronologis"),
    AssetField("keterangan_berlebih", "Keterangan Berlebih"),
    AssetField("asal_usul_berlebih", "Asal Usul Berlebih"),
    AssetField("nomor_perkara", "Nomor Perkara"),
    AssetField("pihak_bersengketa", "Pihak Bersengketa"),
    AssetField("keterangan_sengketa", "Keterangan Sengketa"),
    # Garansi aset: tanggal BERAKHIR masa garansi (rentang lazim dihitung
    # sejak tanggal perolehan). Terisi manual saat inventarisasi ATAU
    # auto-isi dari riwayat inventarisasi sebelumnya (kode+NUP/register).
    AssetField("garansi_hingga", "Garansi Hingga", batchable=True),
    AssetField("garansi_jenis", "Jenis Garansi", batchable=True),
)

SCALAR_FIELD_NAMES = tuple(f.name for f in ASSET_SCALAR_FIELDS)
BATCHABLE_FIELD_NAMES = frozenset(f.name for f in ASSET_SCALAR_FIELDS if f.batchable)


def import_row_value(row: dict, f: AssetField) -> str:
    """Nilai satu field dari baris file impor, dengan aturan default lama."""
    val = str(row.get(f.name, f.import_default)).strip()
    if f.import_force_default and not val:
        return f.import_default
    return val
