# Sinkronisasi identitas satker

## Temuan dan perbaikan

1. Edit kegiatan tidak mendaftarkan satker baru, sementara pemilih menampilkan
   satker hasil agregasi kegiatan. Header satker yang belum ada di master
   dahulu diabaikan sehingga data kembali lintas satker. CREATE/EDIT kini
   memakai registrasi yang sama; satker legacy dalam kegiatan tetap dikenali.
   Kode yang benar-benar tidak dikenal menghasilkan 409, bukan Semua Satker.
2. Konflik identitas mengecualikan kegiatan sendiri, sehingga satker dengan
   satu kegiatan lolos tanpa memperbarui master. Master dan kegiatan sumber
   sekarang ikut diperiksa. Kode/nama dinormalisasi sebelum disimpan.
3. Nama master yang diedit juga memperbarui nama di kegiatan/riwayat. Lookup
   mendahulukan identitas master tanpa membuang struktur eselon anak kegiatan.
4. Daftar statis migrasi kode melewatkan e-sign, denah, pejabat, ruangan,
   persuratan dan setelannya. Migrasi sekarang memindahkan stempel top-level
   `kode_satker` pada koleksi aplikasi yang benar-benar tersedia. Field kosong,
   dokumen satker lain, isi naskah, nomor surat, serta blob tidak diubah.
   Counter agenda/sisipan, tiket dan BA perbaikan diteruskan dengan `$max`;
   counter lama tetap menjadi riwayat reservasi, bukan nomor untuk digunakan ulang.
5. Kelola Pengguna menyaring satker belum terdaftar; stempel dan sejumlah
   modul hanya memuat referensi sekali. Hook bersama memperbarui pilihan
   setelah edit, perubahan antar-tab dan fokus kembali, serta mengabaikan
   respons usang. Berlaku pada stempel, pengguna, pejabat, perencanaan,
   penggunaan, pengadaan, kegiatan dan halaman master satker.
6. Dekorator POST kegiatan menempel pada helper validasi, bukan fungsi create.
   Route dikembalikan ke create dengan dependensi autentikasi penulis dan
   dikunci oleh uji HTTP, bukan hanya pemanggilan fungsi langsung.

## Perubahan nama, kode, dan dokumen terbit

- Mengubah nama satker adalah pemutakhiran metadata master/kegiatan.
- Mengubah kode, termasuk kode dan nama sekaligus, meminta konfirmasi
  pemindahan seluruh referensi satker sumber. Hanya super-admin yang dapat
  memindahkan antar-kode. Tujuan yang sudah dipakai ditolak: penggabungan dua
  satker bukan operasi edit kegiatan.
- Jangan menjalankan migrasi kode saat ada penyuntingan atau antrean offline
  satker yang belum terkirim. Ini operasi administrasi lintas koleksi, bukan
  transaksi MongoDB atomik. Kunci pada master mencegah dua migrasi kode
  bersamaan; perubahan yang terdeteksi selama migrasi membatalkan proses.
- Galat normal memulihkan hanya dokumen yang dipindahkan run itu. Kegagalan
  pemulihan dilaporkan dan kunci dipertahankan. SIGKILL/padam saat migrasi
  membutuhkan audit administrator terhadap kode sumber/tujuan dan penanda
  `migrasi_kode`; jangan menghapus penanda secara membabi buta.
- File PDF/Word dan nomor dokumen yang sudah diterbitkan tidak ditulis ulang.
  Perubahan identitas bukan penerbitan revisi naskah resmi.
- Tidak ada migrasi massal data produksi saat deployment. Data legacy yang
  ambigu (dua kode/nama yang mungkin memang dua satker berbeda) tidak
  digabung otomatis; operator harus memeriksa identitasnya.

## Bukti uji

Uji backend memakai Mongo tiruan: POST melalui router, normalisasi edit,
registrasi satker, filter header, ikatan akun, satu kegiatan, nama/kode
bersamaan, stempel pada modul baru, preservasi nomor/blob/counter, penolakan
kode tujuan terpakai, batas admin satker, kegagalan tulis dan pemulihan,
kunci migrasi, serta data era lama dengan kode kosong.

Uji frontend memakai hook/komponen nyata dengan API tiruan: pembaruan nama,
respons terlambat, event antar-tab, dialog tertutup, dan header kosong
eksplisit untuk memulihkan pilihan satker aktif yang sudah usang.
