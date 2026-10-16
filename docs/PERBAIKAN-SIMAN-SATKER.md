# Identitas satker pada sinkronisasi SIMAN

16 Oktober 2026. Pencocokan impor menggunakan **satker + kode barang + NUP**.
Kode register tetap menjadi jalur utama untuk reklasifikasi, tetapi juga wajib
berada pada satker yang sama. Hak akses dan pemilihan Satker Aktif tetap berlaku.

Kode enam digit dicocokkan hanya dengan segmen satker dalam kode lokasi BMN:
`126 | 01 | 1600 | 691778 | 000 | KP`. Kode satkernya ialah `691778`,
bukan `160069` yang kebetulan muncul sebagai substring. Titik, spasi, tanda
hubung, dan huruf kecil pada kewenangan dinormalisasi. Dua kode lengkap yang
berbeda wilayah, subsatker, atau kewenangan tetap berbeda walaupun enam digit
satkernya sama. Bila kode enam digit merujuk beberapa kode lengkap yang diketahui,
pencocokan dihentikan untuk identitas yang ambigu dan operator diminta memakai
kode lengkap. Simpan kode Excel sebagai teks agar nol depan dan angka panjang
utuh; kode yang sudah dibulatkan Excel tidak ditebak kembali.
Identitas lama di luar format resmi dipertahankan persis setelah trim; huruf
besar/kecil dan pemisahnya tidak disatukan menjadi satker lain.

Pemilik aset ditentukan dari kegiatan inventarisasinya. Kode lengkap pada
kegiatan diprioritaskan; master satker melengkapi isian yang belum tersedia.
Identitas aset menjadi fallback untuk data lama yang memang mempunyai stempel
pemilik. Kop laporan global tidak dipakai sebagai identitas seluruh aset.

File tanpa kolom Kode Satker atau tanpa identitas satker yang dapat dipastikan
ditolak sebelum penulisan. Baris satker lain dari Satker Aktif dilewati dan
jumlahnya dilaporkan. Opsi menandai aset tidak ditemukan hanya berlaku pada
satker yang benar-benar dicakup file; tidak menandai aset satker lain.

Pembuatan draft memeriksa satker baris sumber dan kegiatan tujuan. Aset milik
satker lain dengan kode barang/NUP sama tidak menghalangi draft. CSV dan baris
belum tercatat menyimpan kode serta nama satker sumber. Impor baru menyimpan
identitas satker di subdokumen SIMAN; penerapan memeriksa ulang pemilik saat ini
serta versi aset agar referensi tidak diterapkan setelah data berubah.

**Data dari impor lama:** tidak ada penghapusan tanda massal, pemindahan aset,
atau pembatalan nilai yang sebelumnya sudah diterapkan. Unggah ulang ekspor
SIMAN masing-masing satker agar penanda dihitung ulang dengan identitas yang
benar. Referensi lama tanpa identitas sumber ditolak saat diterapkan dan
memberi petunjuk unggah ulang. Ini mencegah penerapan berdasarkan kecocokan lama
yang satkernya tidak dapat dibuktikan.

Pengujian mencakup benturan kode barang/NUP dan register antar satker, file
campuran, format enam digit dan lengkap, variasi wilayah/subsatker/kewenangan,
identitas kosong/ambigu, batas penandaan tidak ditemukan, draft, CSV, provenance,
dan perubahan versi/kegiatan saat penerapan. Kontrak HTTP memakai MongoDB lokal
terisolasi; tidak melakukan percobaan impor pada data produksi. Hasil CI,
SHA rilis, dan verifikasi produksi dicatat pada deskripsi PR perubahan ini.

Konflik versi/kegiatan selama bulk impor menghasilkan HTTP 409 dan petunjuk
mengimpor ulang. Operasi valid yang sudah ditulis sebelum konflik dapat tetap
tersimpan; impor bukan transaksi lintas semua aset. Identitas kegiatan/master
juga diperiksa ulang tepat sebelum penulisan. Pemeriksaan ulang dan CAS tidak
mengklaim transaksi atomik lintas koleksi atau mengunci seluruh jalur perubahan
identitas satker pada arsitektur MongoDB standalone saat ini.
