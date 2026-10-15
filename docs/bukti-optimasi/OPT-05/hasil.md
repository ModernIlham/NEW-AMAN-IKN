# OPT-05 — Backup lengkap dan status arsip yang jujur

Implementasi backend selesai, dengan pengujian builder dan scheduler aktual.

- GridFS dibaca `readchunk()`; gagal baca/ukuran berubah menggagalkan backup,
  tidak lagi melewati foto lalu mengklaim berhasil.
- `backup-manifest.json` schema 1 memuat SHA-256 dan ukuran setiap entri, jumlah
  koleksi/blob/uploads, `complete: true`, serta kelas konsistensi eksplisit
  `application_best_effort`. Metadata schema baru mewajibkan manifest tersedia.
- ZIP dibaca ulang untuk CRC, format, ukuran, jumlah dan checksum sebelum siap.
- Arsip server dibuat melalui staging tersembunyi, fsync, validasi, rename dan
  validasi final. Berkas final yang gagal diverifikasi dikarantina `.failed`.
  Berkas temp tetap tersedia bila penyalinan arsip gagal.
- Kontrak additive: `status=completed` berarti ZIP unduhan valid;
  `download_ready`, `complete`, `archive_state` (`not_requested`, `archived`,
  `archive_failed`), `durable_verified`, dan `archive_error` membedakan hasil.
- Scheduler hanya memajukan `terakhir_sukses` dan menjalankan retensi setelah
  `completed + archived + durable_verified + arsip_nama` sah. Gagal arsip
  mempertahankan sukses lama, arsip lama dan membuka klaim harian untuk retry.

Verifikasi: `test_backup_recovery_fail_closed.py` menjalankan builder/scheduler
asli dengan PermissionError, ENOSPC, gagal baca blob dan manifest incomplete;
suite lama `test_backup_status_jujur.py` dan `test_backup_json_bertahap.py`
menjaga kompatibilitas unduhan serta format JSON lama. Detail jumlah tes akhir
ada pada bukti verifikasi gabungan PR.

Batas yang dinyatakan: ini cadangan aplikasi best-effort, bukan snapshot
point-in-time, bukan backup offsite, dan tidak membuktikan OPT-07. Manifest
mendeteksi kerusakan/kelengkapan, bukan perubahan bersamaan yang menghasilkan
arsip konsisten secara sintaks tetapi berbeda waktu antar koleksi.

Rollback: field dan manifest additive; arsip legacy tetap dibaca. Jangan
menghapus backup valid lama atau recovery artifacts saat rollback kode.

## Frontend: unduhan dan arsip dibedakan

BackgroundTaskBar menampilkan `archive_failed` berwarna kuning dengan unduhan
masih tersedia; hanya `archived`+`durable_verified` menyatakan arsip telah
diverifikasi. Hasil lama tanpa status arsip tidak dianggap arsip terverifikasi.
Tes interaksi aktual meliputi archive_failed/archived/not_requested dan unduhan
native satu kali. Suite BackgroundTaskBar: 4 tes lulus (termasuk recovery OPT-06).
