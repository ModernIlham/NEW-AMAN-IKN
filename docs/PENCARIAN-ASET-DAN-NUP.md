# Pemilih aset dan NUP

28 Oktober 2026. Pemilih pada Catat SK Penetapan Penggunaan sebelumnya hanya
meminta 8 baris pertama (server membulatkannya menjadi 10) tanpa navigasi hasil.
Satu kode dengan banyak NUP membuat barang di luar halaman awal tidak terjangkau.

`PencarianAset` menjadi pemilih bersama untuk 23 pencarian di 12 halaman:
Penggunaan (SK PSP, proses, henti guna), Pengadaan, Penilaian, Perencanaan,
Pemeliharaan, Pemanfaatan, Penganggaran, Pengamanan, Pemindahtanganan,
Pemusnahan, Pelaporan, serta Buku Barang/KIB. Pencarian referensi kode barang
dan persediaan memakai sumber data berbeda; daftar utama inventarisasi sudah
memiliki pagination dan tidak diganti dengan pemilih form ini.

Hasil diminta 20 aset per halaman dengan jumlah total dan tombol sebelum/
berikutnya. Tidak ada pemuatan seluruh aset ke browser. Pilihan form tetap
tersimpan antarhalaman dan barang yang telah dipilih dinonaktifkan menurut ID,
bukan menurut kode barang. Kolom NUP tersendiri meminta kesetaraan: `1` tidak
mencocokkan `11`, `101`, nama, atau harga. NUP satu digit dapat dicari sendiri
atau bersama nama/kode. NUP integer lama dan teks dengan nol depan tetap cocok;
input tidak valid menghasilkan galat, bukan pencarian tanpa filter.

API `/assets` dan `/assets/stats` menerima `nup` dan `pencarian_lengkap`.
Pemilih memakai sumber Mongo yang otoritatif agar daftar kandidat indeks
pencarian yang terbatas/tertinggal tidak memotong hasil. Pencarian biasa tetap
memakai perilaku indeks sebelumnya. Batas satker dan akses kegiatan tetap
diterapkan. NUP disaring sebelum count dan pagination; hasil dikirim terbatas
per halaman dan total dihitung di Mongo. Batas transaksi pencatatan SK tidak diubah.

Perubahan nama/kode/NUP/filter/satker mengembalikan hasil ke halaman pertama,
membatalkan request lama, dan menyembunyikan hasil usang sebelum debounce
berikutnya. Header Satker Aktif terikat konteks permintaan. Galat jaringan
dibedakan dari hasil kosong dan menyediakan percobaan ulang. Pencarian kandidat
pemusnahan tetap dapat dibuka kosong dengan filter Rusak Berat.

Regresi frontend menguji 55 NUP pada tiga halaman, NUP persis, pilihan lintas
halaman, respons terlambat, pergantian satker, dan simpan form SK dengan ID
yang tepat. Kontrak ASGI/Mongo terisolasi menguji halaman lanjutan, indeks
yang tidak lengkap, angka/teks NUP, statistik, penyimpanan SK, serta penolakan
aset satker lain. Data pengujian tidak diarahkan ke produksi.
