# Aplikasi aktual: snapshot, simpan offline, dan reconnect

Run terpisah setelah bukti 12 pemeriksaan daring di `browser-ci-isolation.json`.
Chromium memakai frontend production build privat, backend aplikasi asli,
MongoDB loopback dengan database sintetis acak, dan akun seed melalui login UI.
Tidak ada state IndexedDB/localStorage aplikasi yang dibuat oleh harness.

Urutan pemeriksaan di `scripts/uji_browser.py`:

1. Aktifkan mode inventarisasi melalui tombol UI dan tunggu indikator snapshot
   siap berisi **202 aset**. Kembali ke tampilan biasa tanpa menghapus snapshot.
2. Pastikan halaman dikontrol service worker, putus jaringan browser melalui CDP,
   lalu reload. Banner menampilkan bahwa daftar berasal dari data tersimpan;
   pencarian UI tetap menemukan dua ID fixture yang sama.
3. Buka form dari baris yang tersimpan, pastikan pemberitahuan form offline,
   ubah brand, lalu simpan melalui tombol form. Baris optimistis menampilkan
   brand baru dan banner menunjukkan **satu simpanan tertunda**. HTTP Python
   terpisah membuktikan brand dan versi backend masih sama dengan sebelum edit.
4. Sambungkan jaringan browser. Antrean aplikasi tersinkron otomatis: ID aset
   tetap sama, versi **4 → 5**, brand berubah, serta `photos`,
   `photo_gridfs_ids` dan seluruh `document_checklist` persis sama.
5. Putus/sambungkan sekali lagi dan pastikan versi tetap 5: item yang telah
   dikonfirmasi tidak diputar ulang.

Hasil 15 Oktober 2026: **16 pemeriksaan UI lulus, 51,44 detik**, termasuk 12
pemeriksaan daring sebelumnya dan empat pemeriksaan tambahan. Delapan kombinasi
ukuran layar/tema tetap lulus; cleanup browser, proses, database dan sandbox
selesai tanpa error. Screenshot `offline-pending.png` memperlihatkan banner
luring, satu simpanan tertunda, dan brand optimistis pada baris fixture.

Artifact lokal: `/workspace/.aman/browser-ci-offline-final`. Ringkasan mesin aman
ada di [`browser-offline-app.json`](browser-offline-app.json). Pemeriksaan ini
mencakup edit scalar offline satu aset, bukan semua bentuk input offline atau
kapasitas produksi. Media lama sengaja dipertahankan; snapshot tidak menyimpan
berkas foto penuh. Pengujian lifecycle service worker lintas rilis tetap dicatat
terpisah. Tidak ada perubahan runtime produksi dalam penambahan harness ini.
