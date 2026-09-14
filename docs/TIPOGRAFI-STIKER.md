# Tipografi stiker BMN

Desain cetak tetap memakai satu keluarga font: **Helvetica-Bold** untuk judul
stiker, kode barang, NUP, dan nama barang; **Helvetica** biasa untuk sub-sub
kelompok dan baris kedua header. Font laporan resmi tidak diubah.

Di dialog **Cetak Stiker**, buka **Font dan ukuran teks**. Tabel mengikuti
ukuran stiker yang dipilih dan kertas A4/A3. Mode *sesuai pilihan per aset*
menampilkan ketiga ukuran sekaligus. Panduan hanya membaca spesifikasi;
kegagalan memuatnya tidak mengunci pembuatan PDF.

## Ukuran dan contoh

Angka pt adalah ukuran dasar **sebelum** penyesuaian teks panjang. Judul dan
kode dapat menyusut; nama barang paling banyak tiga baris lalu elipsis.
Dimensi aktual berasal dari grid pengisi halaman, bukan persis ukuran target
bahan. Jangan menyalin angka tetap ke frontend: endpoint terautentikasi
`GET /api/stiker/tipografi?kertas=A4` menggunakan `spesifikasi_tipografi`,
`grid_optimal`, dan `ukuran_font` yang juga menjadi acuan renderer.

Contoh dapat dibuat tanpa koneksi database:

```bash
python scripts/contoh_tipografi_stiker.py
```

Hasilnya `output/pdf/contoh-tipografi-stiker.pdf`: dua halaman panduan A4
yang memperlihatkan stiker besar/sedang/kecil dari grid A4 dan A3 pada ukuran
aktual 1:1, disertai angka pt dan garis uji 50 mm. Seluruh isinya ilustrasi,
bukan data aset dan bukan untuk ditempel. Data contoh tidak dimasukkan ke DB.

Cetak **100% / Ukuran aktual**, bukan *Sesuaikan halaman*, lalu ukur garis
uji dan satu label dengan penggaris. Lakukan uji pada printer serta bahan
stiker yang akan dipakai, terutama untuk ukuran kecil. PDF contoh ini bukan
lembar produksi penuh; gunakan menu Cetak Stiker untuk aset sungguhan.

Helvetica/Helvetica-Bold adalah font standar PDF yang didukung ReportLab;
ini tidak berarti ada berkas font khusus yang disematkan. Rujukan teknis:
[font ReportLab](https://docs.reportlab.com/reportlab/userguide/ch3_fonts).
