"""Jenis dokumen pengadaan aset; kosong berarti belum diklasifikasikan.

Klasifikasi tidak menghapus nomor/cara bayar kontrak historis. Mengubah
jenis dokumen bukan persetujuan untuk memusnahkan data sumber sebelumnya.
"""

JENIS_DOKUMEN_PENGADAAN = (
    "Kontrak", "Non Kontrak/Penerimaan Barang", "Kontrak BLU", "Non Kontrak BLU",
)


def normalisasi_jenis_dokumen_pengadaan(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Jenis dokumen pengadaan harus berupa teks")
    value = value.strip()
    if value and value not in JENIS_DOKUMEN_PENGADAAN:
        raise ValueError("Jenis dokumen pengadaan tidak valid. Pilih: "
                         + ", ".join(JENIS_DOKUMEN_PENGADAAN))
    return value


def pertahankan_jenis_dokumen_lama(data, existing, supplied_fields):
    """PUT/impor klien lama tanpa kolom baru tidak menghapus klasifikasi."""
    if "jenis_dokumen_pengadaan" not in supplied_fields:
        data["jenis_dokumen_pengadaan"] = existing.get("jenis_dokumen_pengadaan") or ""
