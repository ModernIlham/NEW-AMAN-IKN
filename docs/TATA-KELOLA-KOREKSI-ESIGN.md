# Tata Kelola Koreksi dan Validasi E-sign

Dokumen ini menetapkan aturan operasional AMAN untuk pembubuhan, pemeriksaan,
koreksi, finalisasi, serta perubahan dokumen setelah terbit. Ini adalah desain
kontrol internal aplikasi, bukan pendapat hukum formal. Untuk naskah berisiko
tinggi, unit hukum dan unit kearsipan OIKN tetap menjadi pemutus akhir.

## Keputusan utama

Pembubuhan oleh penanda tangan **bukan finalisasi**. Hasilnya berstatus
`menunggu_validasi` dan baru menjadi `terverifikasi` setelah operator atau
admin satker memeriksa PDF. Permintaan berstatus `selesai` hanya jika seluruh
pembubuhan sudah terverifikasi.

Dokumen yang pernah dibubuhkan **tidak boleh diganti diam-diam**. PP 71/2019
Pasal 59, 60, dan 62 menempatkan identitas, maksud penanda tangan, keutuhan
informasi, waktu, dan keterdeteksian perubahan sebagai unsur penting Tanda
Tangan Elektronik. Penanda tangan juga harus mengetahui dan memahami informasi
yang ditandatangani sebelum memberi afirmasi. Lihat
[PP 71 Tahun 2019 pada JDIH Kemkomdigi](https://jdih.komdigi.go.id/produk_hukum/view/id/695/t/peraturan%2Bpemerintah%2Bnomor%2B71%2Btahun%2B2019).

## Alur status

1. `aktif` — giliran penanda tangan terbuka.
2. `menunggu_validasi` — pembubuhan sudah masuk, tetapi belum final.
3. `terverifikasi` — operator/admin satker menyatakan pembubuhan sesuai.
4. `selesai` — seluruh penanda tangan terverifikasi; QR final dapat
   ditempatkan dan dokumen final dapat diunduh.

Validator wajib memakai tombol **Periksa Dokumen** sebelum mengambil keputusan.
Keputusan, waktu, pelaku, catatan, deklarasi jumlah, hash, dan bukti lama
disimpan dalam jejak audit.

## Angka jumlah TTD salah

Jika angka `jumlah_ttd` terlalu besar, penanda tangan harus:

1. membuka seluruh halaman PDF;
2. menempatkan semua area TTD yang benar-benar ditemukan;
3. mencentang pernyataan bahwa seluruh halaman sudah diperiksa dan tidak ada
   area TTD miliknya lagi; dan
4. mengirim pembubuhan ke antrean validator.

Deklarasi tidak dapat dipakai tanpa PDF atau tanpa sedikitnya satu pembubuhan.
Validator wajib memberi catatan saat menyetujuinya. Bila deklarasi/posisi salah,
validator memilih **Buka Ulang Orang Ini**. Sistem mengarsipkan bukti lama,
mematikan link lama, menerbitkan link baru hanya untuk orang tersebut, dan
tidak menghapus pembubuhan rekan lain.

## Kapan nomor surat boleh dipertahankan?

| Keadaan | Keputusan |
|---|---|
| Masih draf, belum ada pembubuhan | PDF boleh diganti; nomor booking dapat tetap dipakai sesuai SOP registrasi internal. |
| Sudah ada pembubuhan, belum final, PDF tidak berubah; yang salah hanya jumlah/posisi TTD satu orang | Buka ulang hanya orang tersebut. Nomor dan pembubuhan orang lain tetap. |
| Sudah ada pembubuhan dan isi PDF perlu berubah | Jangan menimpa PDF. Batalkan permintaan, arsipkan versi/bukti lama, unggah versi baru, lalu minta pembubuhan ulang atas PDF baru. |
| Sudah final/diterbitkan; kesalahan hanya sebagian materi | Terbitkan **naskah ralat baru** yang menyebut nomor/tanggal naskah asal dan materi sebelum/sesudah koreksi. Gunakan nomor registrasi baru untuk naskah ralat sebagai pilihan kepatuhan yang paling aman. |
| Sudah final; perubahan substansial | Gunakan lembar perubahan atau naskah pengganti sesuai jenis naskah dan kewenangan pejabat. |
| Seluruh materi tidak berlaku | Terbitkan pernyataan pembatalan dalam naskah dinas baru; jangan menghapus arsip asal. |

Dasarnya, Perka OIKN Nomor 4 Tahun 2024 Pasal 90 menyatakan perubahan bagian
tertentu melalui lembar perubahan; Pasal 92 menempatkan pembatalan dalam naskah
dinas baru; Pasal 93 menempatkan ralat sebagian materi dalam pernyataan ralat
pada naskah dinas baru; dan Pasal 94 mengatur tingkat naskah serta pejabat yang
berwenang. Lihat
[Perka OIKN Nomor 4 Tahun 2024, khususnya halaman 22](https://www.ikn.go.id/storage/galleries/20240619-perka-oikn-4-tahun-2023-tata-naskah-dinas-di-lingkungan-otorita-ibu-kota-nusantara-compressed.pdf).

Peraturan itu menyebut **naskah dinas baru**, tetapi tidak secara eksplisit
menyatakan di Pasal 93 apakah nomor asal boleh dipakai lagi. Karena setiap
naskah memiliki identitas, waktu, distribusi, dan arsipnya sendiri, AMAN
memilih kebijakan konservatif: naskah ralat mendapat nomor baru dan relasi
dua arah ke naskah asal. Nomor asal tidak “dihanguskan”; ia tetap sah sebagai
identitas arsip yang diralat atau dibatalkan.

## Watermark revisi

Watermark `DRAF — Revisi ke-X` boleh dipakai **sebagai alat kendali internal
sebelum terbit**, bersama versi, hash PDF, siapa yang mengunggah, alasan, dan
waktu. Watermark itu bukan pengganti naskah ralat/lembar perubahan setelah
naskah resmi diterbitkan.

Rekomendasi fase berikutnya untuk manajemen revisi dokumen:

- simpan tiap PDF sebagai versi immutable (`v1`, `v2`, ...), bukan overwrite;
- simpan hash SHA-256 dan hubungan `menggantikan_version_id`;
- stempel `DRAF — Revisi ke-X` hanya pada pratinjau sebelum final;
- larang unggah versi baru setelah final; arahkan ke proses ralat/perubahan;
- simpan naskah asal, naskah ralat/perubahan, bukti distribusi, dan keputusan
  validator dalam retensi arsip yang sama;
- integrasikan naskah dinas elektronik dengan tata kelola kearsipan instansi.

Sebagai rujukan umum, PerANRI Nomor 5 Tahun 2021 mengatur jenis, format,
penyiapan, pengamanan, pengabsahan, distribusi, dan media naskah dinas, termasuk
naskah elektronik dan Tanda Tangan Elektronik. Lihat
[PerANRI Nomor 5 Tahun 2021 pada JDIH ANRI](https://jdih.anri.go.id/peraturan/peraturan-arsip-nasional-republik-indonesia-no-5-tahun-2021).
