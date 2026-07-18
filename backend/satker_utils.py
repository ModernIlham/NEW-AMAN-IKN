"""Logika murni resolusi KOP PER-SATKER (Mandat-2, M-SATKER — tanpa Mongo/IO).

Resolusi nilai kop/identitas laporan (dari paling spesifik):

    kegiatan (field flat) → master satker (koleksi `satker`) → report_settings

`gabung_kop` menghasilkan dict setelan EFEKTIF: report_settings global
di-overlay field kop satker yang NON-KOSONG — jadi satker cukup mengisi
field yang memang berbeda; sisanya tetap ikut global.
"""

# Field master satker → field report_settings yang ditimpanya.
PETA_KOP_SATKER = {
    "nama_unit_organisasi": "nama_unit_organisasi",
    "nama_sub_unit": "nama_sub_unit",
    "alamat": "alamat_instansi",
    "tempat_laporan": "tempat_laporan",
    "tembusan_laporan": "tembusan_laporan",
    "kode_satker_lengkap": "kode_satker_lengkap",
}


def gabung_kop(settings, satker):
    """Overlay kop satker di atas setelan global. Non-destruktif (dict baru).

    Baris ke-3 kop (`nama_sub_unit`) default ke NAMA SATKER bila profil satker
    tidak mengisinya — di aplikasi multi-satker, baris satker pada kop memang
    seharusnya nama satker ybs., bukan satu nilai global untuk semua.
    """
    out = dict(settings or {})
    s = satker or {}
    for f_satker, f_setting in PETA_KOP_SATKER.items():
        v = str(s.get(f_satker) or "").strip()
        if v:
            out[f_setting] = v
    if not str(s.get("nama_sub_unit") or "").strip():
        nama = str(s.get("nama_satker") or "").strip()
        if nama:
            out["nama_sub_unit"] = nama
    return out
