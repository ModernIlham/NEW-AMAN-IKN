# Lokasi manual dan penempatan denah

Sejak perbaikan September 2026, kedua informasi dipisahkan:

- **Lokasi** adalah isian petugas. Penyimpanan denah dan penerapan opname
  tidak menimpa, mengosongkan, atau menyelaraskannya secara otomatis.
- **Lokasi Denah (otomatis)** adalah kolom baca-saja tepat di bawah Lokasi.
  Isinya berasal dari penempatan tersimpan: hierarki node, keterangan di luar
  kawasan, atau belum ditempatkan. Tidak dikirim sebagai field edit aset.
- Setelah mengubah koordinat, buka **Denah**, deteksi ulang, lalu simpan.
  Koordinat, penempatan, versi aset dan cache diperbarui bersama, tanpa
  membuang draft lokasi manual/foto/catatan yang belum disimpan.
- Cabut Penempatan melepas denah tanpa menghapus koordinat atau lokasi manual.
  Hasil opname memperbarui penempatan dan jejak perpindahan, bukan teks Lokasi.
  Dokumen berbasis lokasi manual (misalnya KIR/DBR) tetap memakai isian manual.

## Laporan eksekutif

Distribusi lokasi memisahkan **Di luar kawasan terpetakan** dari
**(belum ditempatkan di denah)**. Kategori luar memakai titik penempatan
tersimpan yang valid tanpa node, bukan tebakan dari GPS mentah. Koordinat
rusak, titik nol-nol, pencabutan penempatan, dan referensi node hilang tidak
dianggap bukti berada di luar kawasan. Nama lokasi manual tetap menjadi daun
hierarki. Total hanya menjumlahkan kelompok teratas, bukan induk dan anak
sekaligus. Pemisahan tetap berlaku bila laporan tidak memiliki node denah.

## Offline dan data lama

Ringkasan denah disertakan dalam cache baca. Saat sinkron daring berikutnya,
cache dengan proyeksi lama dimuat penuh sekali; setelah berhasil kembali
menggunakan delta. Cache yang sudah ada tidak dihapus saat pembaruan aplikasi,
dan antrean edit offline tidak diubah. Bila kuota habis, proyeksi tidak
ditandai lengkap sehingga sinkron berikutnya mencoba melengkapinya kembali.

Tidak ada pemulihan massal teks Lokasi yang sudah ditimpa versi terdahulu.
Nilai lama harus diperiksa lewat riwayat/backup sebelum dikoreksi; menebaknya
dari denah saat ini justru akan menimpa data petugas sekali lagi.

## Pemeriksaan regresi

Uji route penempatan/opname, OCC/idempotensi, proyeksi daftar, form dan draft
manual, cache offline, pengelompokan/total serta render PDF produksi dengan
data sintetis melindungi pemisahan ini. Tidak ada migrasi data produksi pada
deploy.
