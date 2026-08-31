# Audit Sitasi Peraturan pada Dokumen Resmi

> Daftar setiap nomor peraturan yang **tercetak** ke dokumen keluaran AMAN —
> dokumen yang ditandatangani Kuasa Pengguna Barang di atas meterai dan dibaca
> pemeriksa. Dihasilkan dan dijaga oleh `backend/sitasi_regulasi.py` +
> `backend/tests/unit/test_sitasi_regulasi.py`.

## Batas riset — baca ini dulu

Riset 2026-08-16 memastikan **nomor dan judul** peraturan, **bukan isi
pasalnya**. Ini **bukan pembacaan teks asli**: seluruh sumber primer tetap
terblokir dari lingkungan pengembangan —
`jdih.kemenkeu.go.id`, `peraturan.bpk.go.id`, `djkn.kemenkeu.go.id`, bahkan
salinan resmi di mirror universitas (`hukum.ipb.ac.id`) dan Scribd. Yang
tembus hanya pencarian web, sehingga kesimpulan bertumpu pada **kecocokan
judul di beberapa sumber yang saling bebas**.

Karena itu status `terverifikasi` berarti: *nomor dan judulnya benar, dan
pemakaiannya di kode cocok dengan judul itu.* Ia **tidak** berarti pasalnya
sudah dibaca, dan **tidak** berarti peraturannya dipastikan masih berlaku.

> **Pemutakhiran 2026-08-31 — batas ini kini ada jalan keluarnya.**
> Blokirnya diuji ulang dan ternyata **lebih luas** dari yang tercatat di
> atas: bukan hanya situs hukum, melainkan web umum seluruhnya — bahkan
> `en.wikipedia.org` dan `web.archive.org` ditolak. Itu kebijakan egress
> deny-all, bukan pemblokiran khusus JDIH.
>
> Yang berubah: **runner GitHub Actions punya egress biasa.** Workflow
> **Unduh Regulasi** (`.github/workflows/unduh-regulasi.yml`) mengunduh PDF
> peraturan di sana, mengekstrak teksnya, dan mendorongnya ke cabang
> `regulasi/unduhan` — lengkap dengan sha256, jumlah halaman, dan URL sumber
> tiap berkas. Rinciannya di `docs/regulasi/README.md`.
>
> **Yang TIDAK berubah:** teks yang terunduh adalah **bukti, bukan
> kesimpulan**. Baris di tabel-tabel bawah ini baru boleh naik statusnya
> setelah pasalnya benar-benar dibaca dari teks itu — bukan karena
> unduhannya berhasil.

## Ringkasan

| | Jumlah |
|---|---|
| Sitasi berbeda yang tercetak ke dokumen | **57** |
| Berkas `.py` yang memuatnya | **28** |
| Tercatat di `PUSTAKA-REGULASI-BMN.md` | 47 |
| **Terverifikasi riset 2026-08-16** | **7** |
| **Masih belum ketemu** | **1** |
| **Bertentangan dengan pustaka repo sendiri** | **2** |

## Hasil riset 2026-08-16

### Terkonfirmasi — pemakaian di kode cocok

| Sitasi | Judul yang ditemukan | Dipakai di | Nilai |
|---|---|---|---|
| `PMK 214/PMK.05/2013` | **Bagan Akun Standar**; menggantikan PMK 91/PMK.05/2007 | `lbp_utils.py` | Judul di kode **cocok persis** |
| `KMK 620/KM.6/2015` | **Masa Manfaat dalam rangka Amortisasi BMN berupa Aset Tak Berwujud** pada Entitas Pemerintah Pusat | `lbp_utils.py` | Cocok |
| `KMK 81/KM.6/2018` | **Perubahan atas KMK 620/KM.6/2015** | `lbp_utils.py` | Rantai "620 jo. 81" di kode **benar** |
| `KMK 334/2021` | **Tata Cara Hibah BMN** selain tanah/bangunan tanpa bukti kepemilikan, nilai perolehan ≤ Rp100 juta | `pemindahtanganan_utils.py` | Klaim di kode **cocok persis** |
| `PMK 118/PMK.06/2018` | **Tata Cara Rekonsiliasi BMN dalam rangka Penyusunan LKPP**; mencabut PMK 69/PMK.06/2016 | `lbp_utils.py`, `routes/lbp.py` | **Koreksi atas audit sebelumnya** — lihat di bawah |

### Terkonfirmasi dengan catatan — perlu ditegaskan pemilik

| Sitasi | Temuan | Catatan |
|---|---|---|
| `KMK 403/KMK.06/2013` | **Pedoman Pelaksanaan Tindak Lanjut Hasil Penertiban BMN pada Kementerian/Lembaga** | Judulnya terkonfirmasi. Tetapi **SPTJM** (`routes/reports.py`) memakainya sebagai dasar pernyataan tanggung jawab **"formil dan materiil"** — dan klaim spesifik itu **belum terbaca dari teks aslinya**. Perlu dipastikan pasal mana yang mendasarinya. |
| `S-115/KN/2017` | Surat Dirjen Kekayaan Negara tentang tindak lanjut **Barang Tidak Ditemukan hasil Penilaian Kembali (revaluasi) BMN**, terkait PMK 118/PMK.06/2017 dan Perpres 75/2017 | `ba_utils.py` menuliskannya sebagai dasar "tindak lanjut hasil **inventarisasi** BMN yang tidak ditemukan". Sumber menyebut konteksnya **penilaian kembali**, bukan inventarisasi. Beda konteks yang material untuk Berita Acara bertanda tangan. |

### Belum ketemu

| Sitasi | Diklaim sebagai | Status |
|---|---|---|
| `KMK 339/KM.6/2024` | Perubahan **kedua** atas KMK 295/KM.6/2019 — menambah baris 31304 (*Oil & Gas Facilities*) dan 31305 (*Wells*) pada Tabel I & II (`perbaikan_utils.py`) | **Tidak ditemukan** setelah empat sudut pencarian berbeda. Perubahan keduanya **memang ada** (terindeks sebagai dokumen "Perubahan Kedua atas KMK 295/KM.6/2019"), dan KMK 266/KM.6/2023 adalah perubahan **pertama** — sehingga perubahan kedua bertahun 2024 masuk akal. Tetapi **nomornya tidak dapat dipastikan** dari sumber mana pun yang terjangkau. |

## Riset lanjutan 2026-08-16 (putaran kedua)

### Temuan terpenting: 11 klasifikasi resmi DJKN — dan dari mana daftar aplikasi ini berasal

Tindak lanjut Barang Tidak Ditemukan hasil revaluasi BMN 2017–2018
mengklasifikasikan sebabnya ke dalam **11 klasifikasi**:

| # | Klasifikasi DJKN | Padanan di AMAN |
|---|---|---|
| 1 | Kesalahan kodefikasi | `Kesalahan Kodefikasi` |
| 2 | Tercatat di satker lain | `BMN Tercatat di Satker Lain` |
| 3 | Kegiatan **perencanaan** dicatat sebagai BMN tersendiri | `Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri` |
| 4 | Kegiatan **renovasi** dicatat sebagai BMN tersendiri | **TIDAK ADA** |
| 5 | Kesalahan pencatatan ganda | `Pencatatan Ganda` |
| 6 | Aset sudah dihibahkan, dialihstatuskan, atau dihapuskan | `BMN Objek Alih Status/Pemindahtanganan/Penghapusan` |
| 7 | Penggabungan NUP BMN | `Penggabungan BMN Satu Kesatuan Fungsi` |
| 8 | Kesalahan kodefikasi/klasifikasi (bukan objek revaluasi) | **TIDAK ADA** |
| 9 | Kesalahan pencatatan barang pihak ketiga | `Kesalahan Pencatatan Pihak Ketiga` |
| 10 | Tidak ditemukan fisiknya | `Tidak Ditemukan Fisiknya` |
| 11 | Tidak dapat ditelusuri | `Tidak Dapat Ditelusuri` |

**Artinya:** daftar sub-klasifikasi aplikasi ini **bukan karangan** — ia
turunan dari 11 klasifikasi resmi DJKN, dengan **9 dari 11 terpetakan**.
Ini sekaligus membenarkan keputusan pada PR #857 untuk memenangkan daftar
sisi layar atas daftar lawas di server: daftar layar itulah yang punya
landasan resmi.

Dua yang **belum ada** — nomor 4 (renovasi dicatat sebagai BMN tersendiri)
dan nomor 8 (kesalahan kodefikasi/klasifikasi bukan objek revaluasi) —
adalah calon penambahan, menunggu keputusan pemilik.

Sebaliknya, enam sebab kedaruratan yang ditambahkan pada PR #858
(Kebakaran, Bencana Alam, Hilang/Dicuri, Kerusuhan, Rusak Total, Sebab Lain)
**bukan** bagian dari 11 klasifikasi DJKN. Itu perluasan atas keputusan
pemilik, dan sebaiknya tetap dicatat sebagai perluasan — bukan diklaim
sebagai klasifikasi resmi.

Dicatat pula: untuk barang yang tak dapat ditelusuri, praktik DJKN
mengarahkan pelibatan **APIP/Inspektorat** untuk membuat laporan resmi dan
menentukan apakah dihapuskan, ditelusuri lebih lanjut, atau dinyatakan
sebagai dugaan kerugian negara. Ini sejalan dengan naskah Berita Acara
aplikasi yang sudah menyebut Inspektorat.

### "Formil dan materiil" pada SPTJM — kemungkinan salah rujuk

Unsur SPTJM yang berbunyi *"pernyataan tanggung jawab penuh atas kebenaran
permohonan yang diajukan, baik materiil maupun formil"* muncul sebagai
**syarat isi SPTJM dalam prosedur pemusnahan/penghapusan BMN** — ranah
**PMK 83/PMK.06/2016**, yang **sudah dirujuk repo ini** di tempat lain.

`routes/reports.py` melekatkan frasa itu pada `KMK 403/KMK.06/2013`. Dugaan
kuat: rujukannya **tertukar**, dan yang tepat adalah PMK 83/PMK.06/2016.
Belum diubah — perlu konfirmasi pasal, karena ini dokumen bermeterai.

### `PMK 181/PMK.06/2016` — indikasi masih dipakai

Ditemukan dokumen resmi **Laporan Barang Pengguna Semester I TA 2025** yang
masih menyandarkan penyajian BMN di Neraca pada PMK 181/PMK.06/2016. Ini
bukan bukti non-pencabutan, tetapi bukti **pemakaian resmi yang masih
berjalan** pada 2025 — cukup untuk meredakan kekhawatiran pada `[#864]`,
belum cukup untuk menutup pertanyaannya.

## Bertentangan dengan pustaka repo sendiri

Kedua temuan ini **tidak butuh akses hukum** untuk disimpulkan — cukup repo
konsisten dengan dirinya sendiri.

| Sitasi | Tercetak di | Pertentangannya |
|---|---|---|
| `KMK 29/PMK.6/2010` | `lbp_utils.py`, `routes/lbp.py` | Pustaka (baris 21 & 1322) menulis **PMK 29/PMK.06/2010** untuk Penggolongan & Kodefikasi. Keliru pada **dua** hal: jenisnya (KMK, padahal PMK) dan sub-kodenya (`PMK.6`, padahal `PMK.06`). Nomor **KMK** dengan sub-kode **PMK** tidak koheren. |
| `KMK 295/KMK.06/2019` | `lbp_utils.py` | Ejaan ketiga untuk peraturan yang di tempat lain ditulis `KMK 295/KM.6/2019` dan `KMK 295/2019`. **Riset menguatkan bentuk `KM.6`** — Hukumonline mengindeksnya sebagai "Keputusan Menteri Keuangan Nomor 295/KM.6/2019". Sub-kode `KMK.06` sebaiknya diseragamkan ke `KM.6`. |

Keduanya **belum diperbaiki**: mengubah nomor peraturan pada dokumen
bertanda tangan adalah keputusan pemilik, bukan tebakan pengembang.

## Koreksi atas audit sebelumnya

Audit pertama menandai `PMK 118/PMK.06/2018` sebagai **perlu-koreksi**, dengan
alasan seluruh repo lain memakai `118/PMK.06/2017` sehingga tahunnya dikira
keliru. **Itu salah.** Nomor 118 dipakai oleh **dua peraturan berbeda di dua
tahun berbeda**:

* `PMK 118/PMK.06/2017` — penilaian kembali (revaluasi) BMN;
* `PMK 118/PMK.06/2018` — tata cara rekonsiliasi BMN dalam rangka penyusunan
  LKPP, mencabut PMK 69/PMK.06/2016.

Pemakaian di `lbp_utils.py` sudah benar sejak awal. Ini kekeliruan penalaran
saya, bukan kekeliruan kode — dan justru contoh kenapa "kelihatannya salah"
tidak boleh langsung diperlakukan sebagai "salah".

## Yang masih perlu dijawab Biro Hukum / Inspektorat

1. **`KMK 403/KMK.06/2013`** — pasal mana yang mendasari pernyataan tanggung
   jawab "formil dan materiil" pada SPTJM? Apakah masih berlaku?
2. **`S-115/KN/2017`** — apakah sah dipakai sebagai dasar hukum Berita Acara
   hasil **inventarisasi**, sementara surat itu terbit dalam konteks
   **penilaian kembali**?
3. **`KMK 339/KM.6/2024`** — benarkah nomor perubahan kedua atas
   KMK 295/KM.6/2019 itu?
4. **`KMK 29/PMK.6/2010`** dan **`KMK 295/KMK.06/2019`** — konfirmasi ejaan
   bakunya sebelum diseragamkan.
5. Status berlaku terkini seluruh peraturan pada `DASAR_HUKUM_BA`
   (`backend/ba_utils.py`), yang tercetak di Berita Acara bertanda tangan.

## Cara kerja gerbangnya

1. Pemindai membaca **string literal** di seluruh `backend/**.py`, dan sengaja
   **melewati docstring & komentar** — menyebut nomor peraturan di sana justru
   dianjurkan dan tak pernah sampai ke kertas.
2. Setiap sitasi yang ditemukan wajib terdaftar di `SITASI_TERDAFTAR`.
   Menambah nomor peraturan ke naskah tanpa mendaftarkannya = **uji merah**.
3. Status `pustaka` diperiksa terhadap pustaka riset; status `terverifikasi`
   diperiksa terhadap **dokumen ini** — klaim tanpa jejaknya di sini akan
   menjatuhkan uji.
