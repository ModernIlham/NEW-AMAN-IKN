# Diagnosis terbatas HTTP VPS

Pada 9 September 2026 sekitar 05:57 UTC, pemeriksaan luar mendapatkan `/`
403 dan `/index.html` 500, sedangkan `/manifest.json` serta health API 200.
Pemeriksaan 05:58 UTC kembali 200 tanpa perubahan server dari pemeriksa.
Deploy PR #1043 baru dimulai sekitar 06:03 UTC. Urutan waktu ini **bukan bukti
bahwa deploy tersebut menyebabkan insiden**.

Template nginx repository dapat menghasilkan kombinasi serupa ketika
direktori build ada tetapi index sementara tidak tersedia: directory index
forbidden pada akar dan siklus internal redirect pada index. Ini hipotesis,
bukan penyebab VPS yang sudah terbukti; konfigurasi produksi tidak dibaca.

## Cara menjalankan

Setelah commit di `main` lulus CI, jalankan Actions → **Diagnosis HTTP VPS** →
Run workflow pada `main`. Tidak ada input path, tanggal, perintah, atau isi
konfigurasi. SHA checkout dikunci ke SHA run dan diperiksa memiliki CI
push/main sukses. Workflow mengantre bersama deploy, tetapi **tidak deploy**.
Jangan rerun inventaris lama untuk menjalankan script diagnosis baru.

Script berjalan dari stdin menggunakan Python standar di VPS. Ia tidak
diinstal, tidak mengubah konfigurasi/izin, tidak restart layanan, dan tidak
membaca isi index. SSH menggunakan secret deploy yang sudah tersedia.

## Bukti yang boleh keluar

- Log tetap: `error.log`, `.1`, `.2.gz` sampai `.7.gz` di direktori log nginx.
- Jendela inklusif 2026-09-09 05:50:00–06:10:00 UTC; hitungan per menit untuk
  directory-index-forbidden, internal-redirect-cycle, index-missing, dan
  permission-denied.
- Tiga kategori berbasis path harus menunjuk docroot AMAN persis. Pesan
  redirect-cycle tidak membawa docroot: wajib field `server` AMAN persis,
  request akar/index, dan target internal `/index.html`. Ini tidak membuktikan
  mapping server ke docroot produksi yang sekarang berlaku.
- Metadata keberadaan, mode izin, dan mtime direktori build/index/index rilis
  sebelumnya. Metadata **saat dibaca** bukan rekaman kondisi saat insiden.
- Status baca, jumlah byte/baris diabaikan, dan rentang timestamp setiap log.

Tidak ada baris log mentah, alamat klien, query token, header, konfigurasi,
hostname lain, atau pesan exception yang dipublikasikan. Runner memvalidasi
allowlist keluaran SSH sebelum menulis ringkasan/log; banner atau format yang
tidak sesuai ditolak seluruhnya.

## Batas penafsiran

Bacaan dibatasi 16 MiB per file setelah dekompresi, 64 MiB total, 32 KiB per
baris, dan 15 detik pemindaian. Sesi SSH maksimal 90 detik. Baris panjang atau
terpotong dibuang, bukan ditafsirkan sebagai baris baru. File symlink/FIFO
ditolak. Pembacaan dapat memperbarui atime menurut kebijakan filesystem.

`selesai` berarti pemindaian file mencapai EOF; **bukan** berarti log meliputi
seluruh insiden. Log terotasi, tak terbaca, terpotong, memakai lokasi lain,
atau perubahan zona mesin dapat membatasi bukti. Timestamp nginx tanpa
offset ditafsirkan memakai zona lokal VPS pada tanggal kejadian (termasuk
aturan DST), bukan offset hari pemeriksaan. Perubahan zona mesin sejak
kejadian tidak dapat diketahui dari alat ini.

Jumlah nol bukan bukti tidak pernah terjadi gangguan. Alat ini tidak membaca
access log, seluruh error backend, konfigurasi nginx, ataupun status WAF dan
tidak dapat menyatakan semuanya sehat. Bila bukti kurang, catat **penyebab
belum terkonfirmasi**; jangan mengubah konfigurasi berdasarkan dugaan.
