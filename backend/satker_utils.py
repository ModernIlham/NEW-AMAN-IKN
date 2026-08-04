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
    # REVIEW-9 R15b — lihat catatan pada FIELD_KOP_SATKER (routes/satker.py):
    # tanpa lima baris ini, membatasi tulis `report_settings` ke super-admin
    # membuat admin satker tak punya jalan mengatur kop laporannya sendiri.
    "logo_url": "logo_url",
    "judul_laporan": "judul_laporan",
    "subjudul_laporan": "subjudul_laporan",
    "tahun_anggaran": "tahun_anggaran",
    "catatan_kaki": "catatan_kaki",
    # Kebijakan penyajian NILAI PEROLEHAN pada surat serah terima (lihat
    # `tampilkan_nilai_dokumen`): "" = ikut global, "tampilkan"/"sembunyikan".
    "nilai_dokumen": "nilai_dokumen",
}

# Kebijakan penyajian nilai perolehan pada dokumen serah terima.
NILAI_DOKUMEN = ("tampilkan", "sembunyikan")
NILAI_DOKUMEN_DEFAULT = "tampilkan"


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


def kebijakan_nilai_dokumen(settings) -> str:
    """Kebijakan satker atas NILAI PEROLEHAN di surat serah terima:
    "tampilkan" (bawaan) atau "sembunyikan". Nilai tak dikenal/kosong →
    bawaan, sehingga data lama & satker yang belum menyetel tetap mencetak
    nilai seperti sebelumnya. MURNI."""
    v = str((settings or {}).get("nilai_dokumen") or "").strip().lower()
    return v if v in NILAI_DOKUMEN else NILAI_DOKUMEN_DEFAULT


def tampilkan_nilai_dokumen(settings, pilihan=None) -> bool:
    """Apakah kolom Nilai Perolehan dicetak pada dokumen ini?

    Banyak instansi/satker berkebijakan MENYEMBUNYIKAN nilai perolehan pada
    naskah yang dibaca umum atau dipegang pegawai (BAST, KIB yang ditempel di
    ruangan). Urutan kewenangan:

      1. `pilihan` — keputusan eksplisit per DOKUMEN/unduhan (True/False);
      2. kebijakan satker/global (`nilai_dokumen`) bila `pilihan` None.

    `pilihan` sengaja tri-state: None berarti "ikut kebijakan", sehingga
    dokumen lama (tanpa field pilihan) otomatis mengikuti kebijakan berjalan.
    MURNI (teruji unit)."""
    if pilihan is not None:
        return bool(pilihan)
    return kebijakan_nilai_dokumen(settings) != "sembunyikan"


def pilihan_nilai_dari_query(nilai: str = ""):
    """Terjemahkan parameter unduhan `?nilai=` → tri-state `pilihan`.

    "1"/"true"/"tampilkan" → True · "0"/"false"/"sembunyikan" → False ·
    kosong/tak dikenal → None (ikut kebijakan). Dipakai agar satu dokumen
    yang sama bisa dicetak dua versi (arsip ber-nilai, salinan pegawai
    tanpa nilai) tanpa mengubah data. MURNI."""
    v = str(nilai or "").strip().lower()
    if v in ("1", "true", "ya", "tampilkan"):
        return True
    if v in ("0", "false", "tidak", "sembunyikan"):
        return False
    return None
