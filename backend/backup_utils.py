"""Kebijakan koleksi backup/restore/reset — LOGIKA MURNI (tanpa Mongo/IO).

Dipisah agar daftar koleksi di-ENUMERASI dinamis dari database (bukan hardcode)
sehingga SETIAP koleksi/modul baru otomatis ikut ter-backup, ter-restore, &
ter-reset tanpa memutakhirkan daftar manual — mudah diuji unit tanpa DB.

GridFS (`fs.files`/`fs.chunks`) ditangani terpisah oleh routes/backup.py.
"""
import re

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
# akun & seluruh KONFIGURASI/pemetaan/MASTER REFERENSI agar pasca-reset admin
# tetap bisa login, kop surat tak hilang, dan referensi yang disusun payah-payah
# (pemetaan akun BAS, kodefikasi barang impor Excel, master pegawai/pejabat/
# ruangan/unit kerja, override masa manfaat, format nomor, kode klasifikasi)
# tidak perlu di-setup ulang manual. `akun_bas`/`persediaan_akun`/`kodefikasi`
# KHUSUSNYA tidak punya seed otomatis — kehilangannya = lenyap permanen.
# CATATAN GridFS: reset (server.py reset_all_data) menghapus fs.files/fs.chunks
# KECUALI berkas ber-`metadata.jenis: "foto_pegawai"` — koleksi `pegawai`
# dipertahankan, jadi fotonya juga harus tetap ada (hindari foto_file_id yatim).
RESET_KEEP_COLLECTIONS = {
    "users", "report_settings", "compression_quotas", "pdf_compression_quotas",
    "persuratan_settings", "klasifikasi_arsip", "masa_manfaat",
    "akun_bas", "persediaan_akun", "referensi_akun", "satker",
    "sbsk_standar",
    # Master referensi (ditambah saat audit backup/restore/reset — #407):
    "kodefikasi", "categories", "referensi_akun_hierarki",
    "unit_kerja", "pegawai", "pejabat", "ruangan",
    # Penanda versi seed referensi akun — ikut dipertahankan agar konsisten
    # dengan `referensi_akun` (tanpa ini seed ter-replay; tidak merusak,
    # tapi inkonsisten — audit W7).
    "referensi_akun_meta",
}

# Legacy name → canonical (untuk membaca backup lama; mis. activities.json).
LEGACY_COLLECTION_ALIASES = {"activities": "inventory_activities"}

# GridFS yang DIPERTAHANKAN saat reset "HAPUS SEMUA" — berkas yang tertaut ke
# koleksi RESET_KEEP (pegawai/pejabat) sehingga menghapusnya = referensi yatim:
#   • foto_pegawai / foto_pegawai_asli → pegawai.foto_file_id/foto_asli_file_id
#     (foto krop tampil + foto asli utk atur-ulang posisi — jenis di metadata)
#   • ttd_spesimen → pegawai/pejabat.ttd_file_id (spesimen tanda tangan; kind)
# CATATAN: berkas OPERASIONAL (ttd_sign, dokumen e-sign, foto aset, lampiran)
# TIDAK dipertahankan — koleksi induknya memang ikut direset.
RESET_KEEP_GRIDFS_JENIS = {"foto_pegawai", "foto_pegawai_asli"}
RESET_KEEP_GRIDFS_KIND = {"ttd_spesimen"}


def gridfs_dipertahankan_saat_reset(metadata) -> bool:
    """True bila satu berkas GridFS harus SELAMAT dari reset-all (tertaut koleksi
    yang dipertahankan: foto & spesimen TTD pegawai/pejabat). MURNI.

    Penanda dibaca dari `metadata`: `jenis` (foto) atau `kind` (spesimen ttd).
    """
    m = metadata or {}
    return (str(m.get("jenis") or "") in RESET_KEEP_GRIDFS_JENIS
            or str(m.get("kind") or "") in RESET_KEEP_GRIDFS_KIND)


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


# ── Arsip backup di server + jadwal otomatis (audit backup #407) ──

# Nama berkas arsip yang SAH: dibuat aplikasi sendiri — menolak traversal/injeksi
# saat unduh/hapus/restore-dari-arsip lewat parameter nama.
_NAMA_ARSIP_RE = re.compile(r"^backup_(otomatis|manual)_\d{8}_\d{6}\.zip$")


def nama_arsip_valid(nama) -> bool:
    """True hanya untuk nama berkas arsip buatan aplikasi (anti path-traversal)."""
    return bool(_NAMA_ARSIP_RE.match(str(nama or "")))


def arsip_untuk_dihapus(daftar_nama, retensi):
    """Nama arsip TERLAMA yang melebihi kuota retensi (urut nama = urut waktu).

    `retensi` = jumlah berkas yang dipertahankan (min 1). Nama tak-valid
    diabaikan (bukan buatan aplikasi — jangan pernah dihapus otomatis).
    """
    sah = sorted(n for n in (daftar_nama or []) if nama_arsip_valid(n))
    retensi = max(1, int(retensi or 1))
    return sah[:-retensi] if len(sah) > retensi else []


def saat_jadwal_tiba(jam_setelan, waktu_wib, tanggal_terakhir) -> bool:
    """True bila backup otomatis harian HARUS jalan sekarang.

    jam_setelan   : "HH:MM" (WIB) dari setelan.
    waktu_wib     : datetime zona WIB saat pengecekan.
    tanggal_terakhir: "YYYY-MM-DD" backup otomatis terakhir (atau ""/None).

    Jalan bila hari ini belum pernah jalan DAN waktu sudah >= jam setelan —
    toleran terhadap server sempat mati pada jam persisnya (jalan begitu
    hidup kembali di hari yang sama).
    """
    s = str(jam_setelan or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", s):
        return False
    if str(tanggal_terakhir or "")[:10] == waktu_wib.strftime("%Y-%m-%d"):
        return False
    return waktu_wib.strftime("%H:%M") >= s
