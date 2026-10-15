# Indeks lampiran tersimpan dan urutan checklist form

Review screenshot aplikasi nyata menemukan foto STNK rusak meskipun smoke awal
lulus. STNK berada pada indeks server 0; rekomendasi kelengkapan form memindahkannya
ke posisi visual 4. URL foto/PDF memakai posisi visual sehingga meminta endpoint
`checklist/4/...` dan mendapat 404. Thumbnail inline dapat menyembunyikan masalah
pada tampilan kecil, sementara pratinjau penuh masih salah.

`mediaChecklist.js` kini menggabungkan metadata berdasarkan ID item stabil lebih
dahulu dan nama legacy secara berurutan tanpa memakai satu item dua kali.
`_serverItemIndex` mencatat posisi server dan tetap mengikuti objek ketika
rekomendasi/urutan visual berubah. Foto streaming, fallback thumbnail, pratinjau
penuh dan PDF memakai indeks asal yang sama. Thumbnail inline serta upload baru
tetap bekerja. ID item/dokumen yang diberikan server dipertahankan pada payload;
metadata UI tidak dikirim. Sentinel `__existing__:N` tetap indeks foto/PDF di dalam
item, tidak diubah menjadi indeks checklist atau URL.

Verifikasi lokal: **5 suite / 25 tes lulus**, 11,9 detik
(`/tmp/aman-checklist-index-tests.log`). Uji mencakup form AssetForm sebenarnya:
STNK server0 dipindah rekomendasi, URL thumbnail/pratinjau tetap server0, lalu
uncheck/simpan menghasilkan ID dan sentinel asli tanpa metadata UI. Komponen
checklist diuji ulang setelah reorder dengan/tanpa thumbnail inline; foto penuh
serta PDF tetap menunjuk item/file asal. Duplicate legacy names dan stable ID
rename/reorder diuji terpisah. Lint frontend: **0 error / 7 warning baseline**.

Harness browser diperketat agar setiap thumbnail terlihat dan pratinjau penuh
harus `complete && naturalWidth > 0`, bukan hanya elemen URL tersedia. Run Chromium aplikasi nyata setelah rebuild perbaikan ini **lulus 12 pemeriksaan /
8 kombinasi viewport-theme dalam 29,2 detik**. Thumbnail dashboard, lightbox utama,
thumbnail STNK dan pratinjau STNK semuanya berhasil decode. Log backend mencatat
`checklist/0/photos/0` HTTP200; screenshot mobile 360px memperlihatkan piksel foto
fixture yang valid. Artifact sesi lokal:
`/workspace/.aman/browser-ci-isolated-media-final`, `cleanup_errors=[]`.
Smoke hijau sebelum assertion decode gambar tidak dipakai sebagai bukti
perbaikan bug ini. PDF tetap mempunyai regresi URL komponen setelah reorder;
hasil suite/build/CI gabungan final dicatat koordinator secara terpisah.
