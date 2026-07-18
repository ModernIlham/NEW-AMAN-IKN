"""Uji kebijakan koleksi backup/restore/reset DINAMIS (#290).

Inti: daftar koleksi di-enumerasi dari DB, jadi modul baru otomatis ikut —
tak ada lagi daftar hardcode yang tertinggal.
"""
from backup_utils import (
    RESET_KEEP_COLLECTIONS, SKIP_COLLECTIONS,
    collections_from_backup, collections_to_process, collections_to_reset,
)

# Contoh isi DB nyata: koleksi lama + modul-modul baru + GridFS + sistem + transient.
SAMPLE_DB = [
    "users", "categories", "inventory_activities", "assets", "report_settings",
    "audit_logs", "compression_quotas", "pdf_compression_quotas",
    "inventory_history", "counters",
    # modul-modul baru (dulu HILANG dari backup/reset):
    "kodefikasi", "masa_manfaat", "penilaian_koreksi", "usulan_penghapusan",
    "persediaan", "transaksi_persediaan", "jadwal_pemeliharaan", "pemeliharaan",
    "pemanfaatan", "pemusnahan", "pemindahtanganan", "penertiban",
    "pemantauan_insidentil", "pengadaan", "pengamanan_checklist",
    "pengamanan_dokumen", "pengamanan_kasus", "pengamanan_polis",
    "penganggaran", "penganggaran_kalender", "penggunaan_proses", "psp",
    "perencanaan_usulan", "periode_pelaporan", "bmn_idle",
    # GridFS + sistem + transient (harus DIKECUALIKAN):
    "fs.files", "fs.chunks", "system.indexes",
    "row_locks", "otp_store", "backup_jobs", "idempotency_keys",
    "ws_events", "media_previews",
]

MODUL_BARU = [
    "kodefikasi", "masa_manfaat", "penilaian_koreksi", "usulan_penghapusan",
    "persediaan", "transaksi_persediaan", "jadwal_pemeliharaan", "pengadaan",
    "penganggaran", "psp", "pemanfaatan", "pemusnahan", "pemindahtanganan",
    "pengamanan_kasus", "periode_pelaporan", "bmn_idle",
]


def test_process_mencakup_modul_baru_dan_buang_gridfs_sistem_transient():
    out = collections_to_process(SAMPLE_DB)
    # SEMUA modul baru ikut (regression guard utama)
    for m in MODUL_BARU:
        assert m in out, f"{m} harus ikut backup"
    # GridFS, sistem, & transient dibuang
    for excl in ("fs.files", "fs.chunks", "system.indexes",
                 "row_locks", "otp_store", "backup_jobs",
                 "idempotency_keys", "ws_events", "media_previews"):
        assert excl not in out
    # Terurut & tanpa duplikat
    assert out == sorted(set(out))


def test_reset_hapus_semua_kecuali_akun_dan_konfigurasi():
    to_reset = set(collections_to_reset(SAMPLE_DB))
    # Akun & konfigurasi DIPERTAHANKAN
    for keep in RESET_KEEP_COLLECTIONS:
        assert keep not in to_reset
    # Data OPERASIONAL + modul baru DIHAPUS (minus koleksi konfigurasi
    # yang kini dipertahankan — mis. masa_manfaat)
    for m in [c for c in MODUL_BARU if c not in RESET_KEEP_COLLECTIONS] + [
            "assets", "categories", "audit_logs", "counters",
            "inventory_history", "inventory_activities"]:
        assert m in to_reset, f"{m} harus ikut direset"
    # Transient & GridFS tidak masuk daftar hapus (ditangani terpisah / auto-TTL)
    for excl in SKIP_COLLECTIONS | {"fs.files", "fs.chunks"}:
        assert excl not in to_reset


def test_reset_pertahankan_pemetaan_akuntansi_dan_persuratan():
    """Regression Mandat-2: pemetaan yang disusun satker TANPA seed otomatis
    (akun_bas/persediaan_akun) + setelan persuratan/masa manfaat harus
    selamat dari reset-all — kehilangannya berarti setup ulang manual."""
    db = SAMPLE_DB + ["persuratan_settings", "klasifikasi_arsip",
                      "akun_bas", "persediaan_akun", "referensi_akun", "satker"]
    to_reset = set(collections_to_reset(db))
    for keep in ("akun_bas", "persediaan_akun", "masa_manfaat",
                 "persuratan_settings", "klasifikasi_arsip", "referensi_akun",
                 "satker", "report_settings", "users"):
        assert keep not in to_reset, f"{keep} harus selamat dari reset"
    # ...tapi tetap ikut BACKUP (bukan transient)
    assert "akun_bas" in collections_to_process(db)


def test_collections_from_backup_ambil_json_root_saja():
    names = [
        "assets.json", "kodefikasi.json", "penilaian_koreksi.json",
        "metadata.json",                # dikecualikan
        "gridfs/manifest.json",         # dikecualikan (bukan di root)
        "gridfs/abc123.bin", "uploads/logo.png",  # bukan .json
    ]
    cols = collections_from_backup(names)
    assert cols == ["assets", "kodefikasi", "penilaian_koreksi"]
    assert "metadata" not in cols and "gridfs/manifest" not in cols


def test_aman_untuk_masukan_kosong():
    assert collections_to_process([]) == []
    assert collections_to_process(None) == []
    assert collections_to_reset(None) == []
    assert collections_from_backup(None) == []
