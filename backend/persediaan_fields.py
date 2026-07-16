"""Registry field skalar PERSEDIAAN — satu sumber kebenaran (anti-drift).

Pola sama dengan asset_fields.py: daftar field skalar yang boleh ditulis
lewat CRUD master; turunannya (whitelist update, kolom CSV/impor kelak)
dijaga unit test. Field TERKELOLA SISTEM sengaja di luar registry:

    stok, batches (layer FIFO), version, created_at, updated_at, id
    → hanya berubah lewat transaksi persediaan / opname (masuk/keluar
      FIFO, pindah gudang, penyesuaian opname), bukan lewat edit master.

Identitas (kode_barang + nup) ditetapkan saat create dan TIDAK bisa
diubah lewat update — mengubah identitas merusak jejak layer/transaksi.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersediaanField:
    name: str
    label: str              # label kolom tampilan/CSV kelak
    editable: bool = True   # boleh diubah lewat PUT master


PERSEDIAAN_SCALAR_FIELDS = (
    PersediaanField("kode_barang", "Kode Barang", editable=False),  # 16 digit '1'
    PersediaanField("nup", "NUP", editable=False),
    PersediaanField("nama_barang", "Nama Barang"),
    PersediaanField("merk", "Merk"),
    PersediaanField("tipe", "Tipe"),
    PersediaanField("satuan", "Satuan"),
    PersediaanField("lokasi", "Lokasi/Gudang"),
    PersediaanField("batas_kritis", "Batas Kritis"),
    PersediaanField("expired_default", "Kedaluwarsa Bawaan"),  # per batch bisa beda
    PersediaanField("tahun_anggaran", "Tahun Anggaran"),
    PersediaanField("keterangan", "Keterangan"),
)

FIELD_NAMES = tuple(f.name for f in PERSEDIAAN_SCALAR_FIELDS)
EDITABLE_FIELD_NAMES = frozenset(f.name for f in PERSEDIAAN_SCALAR_FIELDS if f.editable)
MANAGED_FIELD_NAMES = frozenset({"id", "stok", "batches", "version", "created_at", "updated_at"})
