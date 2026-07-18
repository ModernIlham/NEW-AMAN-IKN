"""Kebijakan koleksi backup/restore/reset — LOGIKA MURNI (tanpa Mongo/IO).

Dipisah agar daftar koleksi di-ENUMERASI dinamis dari database (bukan hardcode)
sehingga SETIAP koleksi/modul baru otomatis ikut ter-backup, ter-restore, &
ter-reset tanpa memutakhirkan daftar manual — mudah diuji unit tanpa DB.

GridFS (`fs.files`/`fs.chunks`) ditangani terpisah oleh routes/backup.py.
"""

# Transient/derivable — TIDAK di-backup & TIDAK relevan direset:
#   row_locks (lock edit TTL), otp_store (OTP TTL), backup_jobs (progress job
#   backup/restore itu sendiri), idempotency_keys (dedup replay TTL — membawanya
#   ke DB hasil restore bisa menelan save sah), ws_events (bus realtime capped),
#   media_previews (cache JPEG hasil-resize ber-TTL, derivable dari GridFS asli).
SKIP_COLLECTIONS = {
    "row_locks", "otp_store", "backup_jobs", "idempotency_keys",
    "ws_events", "media_previews",
}

# Koleksi yang _id-nya BERMAKNA (bukan ObjectId acak) → wajib dipertahankan saat
# backup/restore: counters (_id = "inventory_activity_ticket_{tahun}").
KEEP_ID_COLLECTIONS = {"counters"}

# Reset "HAPUS SEMUA": wipe seluruh data OPERASIONAL + GridFS, TAPI pertahankan
# akun & seluruh KONFIGURASI/pemetaan agar pasca-reset admin tetap bisa login,
# kop surat tak hilang, dan setelan akuntansi/persuratan yang disusun satker
# (pemetaan akun BAS, override masa manfaat, format nomor, kode klasifikasi)
# tidak perlu di-setup ulang manual. `akun_bas`/`persediaan_akun` KHUSUSNYA
# tidak punya seed otomatis — kehilangannya = pemetaan lenyap permanen.
RESET_KEEP_COLLECTIONS = {
    "users", "report_settings", "compression_quotas", "pdf_compression_quotas",
    "persuratan_settings", "klasifikasi_arsip", "masa_manfaat",
    "akun_bas", "persediaan_akun", "referensi_akun", "satker",
    "sbsk_standar",
}

# Legacy name → canonical (untuk membaca backup lama; mis. activities.json).
LEGACY_COLLECTION_ALIASES = {"activities": "inventory_activities"}


def collections_to_process(all_names, skip=None):
    """Saring daftar nama koleksi → hanya koleksi DATA aplikasi.

    Buang GridFS (`fs.*`), koleksi sistem (`system.*`), & transient (SKIP).
    """
    skip = SKIP_COLLECTIONS if skip is None else skip
    return sorted(n for n in (all_names or [])
                  if n not in skip
                  and not n.startswith("fs.")
                  and not n.startswith("system."))


def collections_to_reset(all_names, keep=None, skip=None):
    """Koleksi yang DIHAPUS saat reset-all = koleksi aplikasi minus yang dipertahankan."""
    keep = RESET_KEEP_COLLECTIONS if keep is None else keep
    return [n for n in collections_to_process(all_names, skip) if n not in keep]


def collections_from_backup(zip_names):
    """Nama koleksi yang ADA di dalam ZIP backup (file `<name>.json` di root,
    kecuali metadata). Restore mengiterasi INI agar koleksi apa pun di backup
    ikut dipulihkan meski DB tujuan masih kosong."""
    return sorted(n[:-5] for n in (zip_names or [])
                  if n.endswith(".json") and n != "metadata.json" and "/" not in n)
