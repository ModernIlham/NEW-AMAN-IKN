# OPT-15a — Laporan lengkap atau penolakan eksplisit

31 pembacaan dataset laporan melalui `baca_laporan_lengkap`:

- Rekapitulasi, BA tidak ditemukan, SPTJM, surat koreksi/pernyataan,
  DBHI PDF/DOCX, RHI PDF/DOCX, DBKP PDF/DOCX, BAHI PDF/DOCX.
- Posisi BMN, DBR, KIR, penyusutan, LBKP, LKB, CaLBMN,
  rekonsiliasi XLSX (aset dan persediaan).
- Builder Eksekutif (HTML/PDF/Data Aset), laporan gabungan satker,
  daftar pemegang PDF/DOCX.
- Peta ruangan KIR, node spasial beserta leluhur, daftar kegiatan satker,
  unit organisasi pendukung laporan gabungan juga harus lengkap.

Helper membatasi cursor di server pada cap+1 dan memeriksa overflow sebelum
perakitan dokumen. Di atas cap mengembalikan HTTP413 dengan arahan persempit
filter yang tersedia, buat per kegiatan, atau ekspor CSV. Tidak ada dokumen resmi
berisi subset yang tampak lengkap. Batas sinkron global100000baris menurunkan
jalur lama500000ke100000; batas sempit yang sudah ada (mis.100kegiatan,
5000ruangan/unit,20000node) tetap berlaku dengan deteksi overflow eksplisit.
Kontrak laporan data per halaman tetap subset berlabel, sedangkan agregatnya
memerlukan seluruh dataset sah di bawah budget yang sama.

Batch ZIP mempertahankan `_LAPORAN-GAGAL.txt` ketika sebagian jenis gagal.
Bila semua jenis gagal karena overflow, respons HTTP413 tetap dipertahankan
(semula semua kegagalan menjadi500). Ekspor foto yang sudah count-gated5000
tidak diubah. Pembacaan taxonomy categories10000/kodefikasi60000 dan pejabat2000
berfungsi sebagai lookup label/referensi, bukan daftar transaksi/total laporan;
cap tersebut tidak diganti secara massal. Lookup kode prefiks menggunakan batas
berdasar jumlah key yang diminta. Rekap ringan memakai agregasi, tidak dibatasi
jumlah aset sebagai list.

Bukti:168tes unit regresi PDF/filter/gabungan/eksekutif lulus. Kontrak Mongo+HTTP
nyata menginjeksi cap3 dan menguji2/3/4baris pada rekap JSON, PDF RHI sungguhan
(dibaca kembali pypdf), dan HTML Eksekutif sungguhan: <=cap sukses, >cap413sebelum
renderer. Semua-jenis batch ZIP overflow juga mempertahankan413. Taxonomy tidak terkena cap injeksi dataset.

Budget ini membatasi jumlah row, bukan jaminan puncak RSS/CPU untuk media. Worker
terpisah dan streaming builder tetap keputusan berbasis OPT-16/22; mengirim job
ke builder yang sama tidak boleh melewati budget ini. Rollback tidak memerlukan
schema; jangan mengembalikan pemotongan senyap. OPT-15b restore berbatas ditangani
pada bukti paket backup/restore.

## Ekspor geo lengkap

Review terakhir juga menutup dua pemotongan senyap pada KML/KMZ/SHP:
pilihan di atas5000 ID ditolak413, dan titik valid ke100001 ditolak413
sebelum renderer, bukan menghasilkan berkas sebagian100000 titik. Titik invalid
memang tidak menjadi fitur peta dan tidak memakan budget; scope satker/filter
berlaku sebelum pembacaan. Array legacy foto memakai typeguard.
`test_geo_completeness.py`:10 kontrak Mongo nyata, cap diinjeksi2 dengan1/2/3
titik pada ketiga format. KML dibaca XML, KMZ dibuka lalu XML diperiksa, SHP
ZIP dibaca shapefile.Reader; <=cap memuat semua fitur, >cap JSON413 tanpa berkas
parsial. Selection overflow juga413. Run fokus10 tes lulus7,05 detik.

Run gabungan final50 kontrak data termasuk10 geo boundary lulus24,34 detik;
118 unit terkait reader/render lulus9,75 detik. Tidak ada penulisan produksi
atau purge/migrasi data pada tahap bukti ini.
