# Konsolidasi konfigurasi produksi

## Tujuan yang disepakati

Hanya dua file **konfigurasi aktif**:

- `/var/www/inventarisasi/backend/.env`: konfigurasi server dan rahasia backend.
- `/var/www/inventarisasi/frontend/.env`: konfigurasi publik build frontend.

Backend memuat `.env` relatif ke direktori modul (`backend/db.py` dan
`backend/server.py`), bukan dari working directory `/root`. Environment proses
dapat mengungguli nilai file. Build React juga mengenal `.env.production.local`,
`.env.local`, dan `.env.production`; varian serta environment layanan harus
diaudit agar tidak ada sumber konfigurasi yang diam-diam mengungguli dua file ini.

**Status:** perbaikan skrip bukan bukti konsolidasi server sudah selesai.
Audit langsung isi/pemakai file lama, pemindahan nilai, dan penghapusan di VPS
memerlukan akses administrator. Jangan menyimpulkan sebuah file tidak terpakai
hanya karena tidak ditemukan referensinya dalam repository.

## Urutan pemeriksaan dan migrasi

1. Periksa metadata, pemilik, permission, symlink/hardlink dan waktu perubahan
   dua file aktif, `/root/inventaris/deploy/.env`, `/root/.env`, serta salinan lama
   `/tmp/backend_env_backup` dan `/tmp/frontend_env_backup`. Jangan mengikuti
   symlink tanpa memastikan tujuannya. Jangan menyalin nilai rahasia ke log/chat.
2. Telusuri Supervisor/systemd, cron, konfigurasi container/Compose, skrip deploy,
   shell profile dan environment proses. Periksa `directory`, `EnvironmentFile`,
   `env_file`, `--env-file`, `source` serta jalur relatif terhadap working directory.
   Catat **nama file/pemakai**, bukan baris konfigurasi yang mengandung nilainya.
3. Bandingkan konfigurasi di dalam VPS dengan parser dotenv yang memahami format
   kutip/multiline; **jangan menjalankan `.env` sebagai skrip shell**. Laporkan
   nama variabel dan status sama/unik/konflik saja. Jangan mencatat nilai ataupun
   hash nilai rahasia. Nilai unik wajib dipertahankan; konflik perlu keputusan
   operator, bukan ditimpa berdasarkan waktu file semata.
4. Pindahkan setelan ke tempat yang tepat dan sesuaikan pemakainya. Rahasia hanya
   di backend; jangan memindahkan kunci privat ke `REACT_APP_*`. Jangan mengganti
   JWT secret atau kredensial DB tanpa rencana rotasi dan dampak sesi/koneksi.
5. Pastikan pemilik sesuai akun layanan/build, file `0600`, lalu uji konfigurasi
   layanan. Restart backend atau build ulang frontend hanya jika diperlukan.
   Periksa health, MongoDB/GridFS, login dan fitur yang memakai layanan eksternal.
6. Baca ulang sumber/tujuan setelah uji; pastikan tidak ada perubahan bersamaan,
   semua nilai yang diperlukan masih tersedia, dan seluruh pemakai lama dialihkan.
   Baru hapus **file lama yang sudah diverifikasi**, satu per satu dengan jalur
   absolut. Jangan memakai glob/rekursi untuk menghapus `.env` lain atau arsip
   pemulihan. Penghapusan plaintext tidak membuktikan data hilang dari snapshot
   penyedia/backup; kelola retensi dan rotasi bila ada bukti paparan.
7. Verifikasi ulang aplikasi setelah penghapusan, daftar file yang tersisa, dan
   satu deploy normal. Catat file yang dihapus, waktu, pemakai yang dialihkan,
   hasil uji, dan cara pemulihan tanpa mencantumkan nilai rahasia.

## Snapshot deploy dan kondisi gagal

`scripts/deploy_vps.sh` menyediakan helper snapshot bersama yang juga dipakai
`update-all.sh`. Workflow tetap dapat mengirim satu skrip melalui stdin, termasuk
saat checkout VPS belum mempunyai pembaruan ini.

- Snapshot baru memakai direktori acak privat `/tmp/aman-env.XXXXXXXXXX`, bukan
  nama file tetap yang bisa tertukar antar proses atau tersisa dari run lama.
- File `0600` berada dalam direktori `0700`. Pemulihan menggunakan file staging
  pada direktori tujuan dan rename atomik, mempertahankan pemilik asli.
- Sumber/tujuan symlink atau bukan file biasa ditolak. Main deploy memerlukan
  kedua `.env`; updater lama hanya memulihkan snapshot yang benar-benar dibuat
  pada run itu. Galat tidak disamarkan sebagai sukses.
- Selesai/gagal normal/HUP/INT/TERM membersihkan snapshot. Pemulihan gagal
  mempertahankan snapshot privat sebagai jalur penyelamatan; log menyebut lokasi
  saja. SIGKILL atau mesin padam dapat meninggalkan snapshot privat.
- Jangan membersihkan snapshot milik deploy yang masih berjalan. Salinan lama
  bernama tetap di `/tmp` tetap memerlukan pemeriksaan dan penghapusan terpisah.
- Arsip `vps-fix.sh` di `/root/backup_env_*` berisi konfigurasi dan logo untuk
  pemulihan operator. Inventarisasi/retensinya terpisah; bukan sumber aktif,
  bukan target penghapusan massal, dan bukan alasan membuat `.env` aktif ketiga.

Lihat [panduan Hostinger](../DEPLOYMENT_GUIDE_HOSTINGER.md#maintenance) untuk
jalur PR/CI/deploy dan pemulihan rilis. Jadwal fetch lokal tetap tidak diaktifkan.
