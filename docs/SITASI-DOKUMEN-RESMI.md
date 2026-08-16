# Audit Sitasi Peraturan pada Dokumen Resmi

> Daftar setiap nomor peraturan yang **tercetak** ke dokumen keluaran AMAN —
> dokumen yang ditandatangani Kuasa Pengguna Barang di atas meterai dan dibaca
> pemeriksa. Dihasilkan dan dijaga oleh `backend/sitasi_regulasi.py` +
> `backend/tests/unit/test_sitasi_regulasi.py`.
>
> **Yang TIDAK diklaim dokumen ini:** apakah suatu peraturan masih berlaku.
> Teks asli JDIH tidak terjangkau dari lingkungan pengembangan (HTTP 403), dan
> menebaknya justru pangkal masalah yang diaudit di sini. Yang ditegakkan hanya
> hal-hal yang bisa dipastikan tanpa akses hukum sama sekali.

## Ringkasan

| | Jumlah |
|---|---|
| Sitasi berbeda yang tercetak ke dokumen | **57** |
| Berkas `.py` yang memuatnya | **28** |
| Tercatat di `PUSTAKA-REGULASI-BMN.md` | 47 |
| **Belum pernah diriset** | **7** |
| **Bertentangan dengan pustaka repo sendiri** | **3** |

Angka-angka di atas dihitung ulang oleh uji setiap kali CI berjalan; bila
berubah tanpa registry diperbarui, uji merah.

## Cara kerja gerbangnya

1. Pemindai membaca **string literal** di seluruh `backend/**.py`, dan sengaja
   **melewati docstring & komentar** — menyebut nomor peraturan di sana justru
   dianjurkan dan tak pernah sampai ke kertas.
2. Setiap sitasi yang ditemukan wajib terdaftar di `SITASI_TERDAFTAR`. Menambah
   nomor peraturan ke naskah tanpa mendaftarkannya = **uji merah**.
3. Status di registry diperiksa **terhadap pustaka riset**, bukan dipercaya
   begitu saja. (Versi pertama registry ini salah pada lima entri; semuanya
   ketahuan oleh pemeriksaan ini, bukan oleh penulisnya.)

## Belum pernah diriset — pertanyaan untuk Biro Hukum/Inspektorat

Sitasi berikut tercetak ke dokumen tetapi **tidak ada jejaknya** di
`docs/PUSTAKA-REGULASI-BMN.md`. Untuk masing-masing, yang perlu dipastikan:
**(a)** nomor & judulnya benar, **(b)** masih berlaku, **(c)** memang relevan
untuk konteks tempat ia dipakai.

| Sitasi | Tercetak di | Catatan |
|---|---|---|
| `KMK 403/KMK.06/2013` | `routes/reports.py` | **Paling mendesak.** Dipakai di **SPTJM** sebagai dasar pernyataan tanggung jawab "formil dan materiil" — dokumen bermeterai yang ditandatangani KPB. |
| `S-115/KN/2017` | `ba_utils.py` | **Paling mendesak.** Masuk daftar **Dasar Hukum Berita Acara** yang ikut ditandatangani. |
| `PMK 214/PMK.05/2013` | `lbp_utils.py` | Laporan Barang Pengguna. |
| `KMK 620/KM.6/2015` | `lbp_utils.py` | Laporan Barang Pengguna. |
| `KMK 81/KM.6/2018` | `lbp_utils.py` | Laporan Barang Pengguna. |
| `KMK 339/KM.6/2024` | `perbaikan_utils.py` | Naskah perbaikan/pemeliharaan. |
| `KMK 334/2021` | `pemindahtanganan_utils.py` | Naskah pemindahtanganan. |

## Bertentangan dengan pustaka repo sendiri

Ketiga temuan ini **tidak butuh akses hukum** untuk disimpulkan — cukup repo
konsisten dengan dirinya sendiri. Perbaikannya menunggu keputusan pemilik,
bukan ditebak.

| Sitasi | Tercetak di | Pertentangannya |
|---|---|---|
| `KMK 29/PMK.6/2010` | `lbp_utils.py`, `routes/lbp.py` | Pustaka (baris 21 & 1322) menulis **PMK 29/PMK.06/2010** untuk Penggolongan & Kodefikasi. Sitasi ini keliru pada **dua** hal: jenisnya (KMK, padahal PMK) dan sub-kodenya (`PMK.6`, padahal `PMK.06`). Nomor **KMK** dengan sub-kode **PMK** tidak koheren. |
| `PMK 118/PMK.06/2018` | `lbp_utils.py`, `routes/lbp.py` | Seluruh repo lain memakai **118/PMK.06/2017**, dan pustaka baris 480 menulis "118/PMK.06/2017 jo. 57/2018 jo. 107/2019". Entah tahunnya keliru, entah ini memang peraturan lain — harus dipastikan. |
| `KMK 295/KMK.06/2019` | `lbp_utils.py` | Ejaan ketiga untuk peraturan yang di tempat lain ditulis `KMK 295/KM.6/2019` (sesuai pustaka) dan `KMK 295/2019`. Sub-kode `KM.6` vs `KMK.06` — satu di antaranya salah ketik, keduanya tercetak. |

## Yang sengaja TIDAK dilakukan

Rekomendasi awal atas temuan ini adalah **mencabut nomor peraturan** dari
dasar hukum Berita Acara. Itu **tidak** dikerjakan, karena landasannya sendiri
tak terverifikasi: klaim "dasar hukum naskah dinas tidak wajib menyebut nomor"
tidak dapat dipastikan dari lingkungan ini. Mencabut dasar hukum dari dokumen
yang justru diperiksa BPK bisa memperburuk keadaan, dan menukar satu tebakan
dengan tebakan lain bukan perbaikan.

Yang dikerjakan adalah yang **bisa dipertanggungjawabkan**: membuat seluruh
sitasi terlihat, tertagih provenansnya, dan tak bisa bertambah diam-diam —
lalu menyerahkan tujuh pertanyaan konkret di atas kepada pihak yang memang
punya akses ke teks aslinya.
