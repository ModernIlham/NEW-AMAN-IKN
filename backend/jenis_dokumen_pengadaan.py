"""Jenis dokumen pengadaan aset; kosong berarti belum diklasifikasikan."""

JENIS_DOKUMEN_PENGADAAN = (
    "Kontrak", "Non Kontrak/Penerimaan Barang", "Kontrak BLU", "Non Kontrak BLU",
)
JENIS_NON_KONTRAK = ("Non Kontrak/Penerimaan Barang", "Non Kontrak BLU")


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


def kosongkan_nomor_kontrak_non_kontrak(data, existing=None):
    """Satukan pengosongan nomor dengan tulisan aset yang sama."""
    existing = existing or {}
    jenis = data.get("jenis_dokumen_pengadaan", existing.get("jenis_dokumen_pengadaan"))
    if jenis in JENIS_NON_KONTRAK and (
        "jenis_dokumen_pengadaan" in data or "nomor_kontrak" in data
        or existing.get("nomor_kontrak")
    ):
        data["nomor_kontrak"] = ""
