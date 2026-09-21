"""Referensi jenis operasional; label lama tetap diterima sebagai alias.

Tidak memigrasikan data atau mengubah dokumen/foto/audit historis. Pemakai
menormalkan tampilan/ekspor, sementara formulir baru memilih nama yang sama.
"""
JENIS_OPERASIONAL = ("Unit/Tempat/Tugas", "Ruangan")


def nama_jenis_operasional(nilai):
    teks = str(nilai or "").strip()
    kunci = "".join(teks.split()).casefold()
    if kunci in ("kegiatan/acara/kebutuhan", "unit/tempat/tugas"):
        return JENIS_OPERASIONAL[0]
    if kunci == "ruangan":
        return JENIS_OPERASIONAL[1]
    return teks
