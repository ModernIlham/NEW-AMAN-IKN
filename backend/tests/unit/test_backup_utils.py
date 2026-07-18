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
    # Data OPERASIONAL + modul baru DIHAPUS (minus koleksi konfigurasi/master
    # yang kini dipertahankan — mis. masa_manfaat, kodefikasi, categories)
    for m in [c for c in MODUL_BARU if c not in RESET_KEEP_COLLECTIONS] + [
            "assets", "audit_logs", "counters",
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
                      "akun_bas", "persediaan_akun", "referensi_akun", "satker",
                      "sbsk_standar"]
    to_reset = set(collections_to_reset(db))
    for keep in ("akun_bas", "persediaan_akun", "masa_manfaat",
                 "persuratan_settings", "klasifikasi_arsip", "referensi_akun",
                 "satker", "sbsk_standar", "report_settings", "users"):
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


def test_reset_pertahankan_master_referensi():
    """Audit #407: master referensi yang disusun payah-payah (kodefikasi impor
    Excel, master pegawai/pejabat/ruangan, unit kerja berjenjang, hierarki akun)
    harus SELAMAT dari reset-all — reset = bersihkan data operasional saja."""
    db = SAMPLE_DB + ["referensi_akun_hierarki", "unit_kerja", "pegawai",
                      "pejabat", "ruangan"]
    to_reset = set(collections_to_reset(db))
    for keep in ("kodefikasi", "categories", "referensi_akun_hierarki",
                 "unit_kerja", "pegawai", "pejabat", "ruangan"):
        assert keep not in to_reset, f"{keep} harus selamat dari reset"
        assert keep in collections_to_process(db), f"{keep} tetap ikut backup"


def test_nama_arsip_valid_anti_traversal():
    from backup_utils import nama_arsip_valid
    assert nama_arsip_valid("backup_otomatis_20260718_020000.zip")
    assert nama_arsip_valid("backup_manual_20260718_235959.zip")
    for jahat in ("../etc/passwd", "backup_otomatis_20260718_020000.zip/..",
                  "backup_otomatis_2026.zip", "lain.zip", "", None,
                  "backup_otomatis_20260718_020000.ZIP"):
        assert not nama_arsip_valid(jahat), jahat


def test_arsip_retensi_hapus_terlama():
    from backup_utils import arsip_untuk_dihapus
    daftar = [f"backup_otomatis_2026071{i}_020000.zip" for i in range(5)] + ["asing.zip"]
    assert arsip_untuk_dihapus(daftar, 3) == [
        "backup_otomatis_20260710_020000.zip",
        "backup_otomatis_20260711_020000.zip"]
    assert arsip_untuk_dihapus(daftar, 10) == []
    assert arsip_untuk_dihapus([], 3) == []
    # retensi minimal 1 — tidak pernah menghapus semuanya
    assert len(arsip_untuk_dihapus(daftar, 0)) == 4


def test_saat_jadwal_tiba():
    from datetime import datetime
    from backup_utils import saat_jadwal_tiba
    w = datetime(2026, 7, 18, 2, 5)
    assert saat_jadwal_tiba("02:00", w, "") is True
    assert saat_jadwal_tiba("02:00", w, "2026-07-17") is True  # kemarin → jalan
    assert saat_jadwal_tiba("02:00", w, "2026-07-18") is False  # sudah hari ini
    assert saat_jadwal_tiba("03:00", w, "") is False            # belum jamnya
    assert saat_jadwal_tiba("", w, "") is False                 # tak dikonfigurasi
    assert saat_jadwal_tiba("2:00", w, "") is False             # format salah
