# OPT-20 — jendela halaman mobile dan galeri

Daftar infinite-scroll menyimpan halaman absolut dalam `cacheHalamanAset`: default enam halaman dan estimasi isi 8 MiB. Eviction membuang sisi terjauh dari fokus dan mempertahankan rentang berurutan. Halaman yang sedang terlihat dilindungi; bila data terlihat sendiri melampaui anggaran, `overBudget` menyatakan pengecualian tersebut. Anggaran tidak mengklaim batas RSS atau heap browser. Seleksi tetap kumpulan ID; draf form dan antrean persisten berada di pemilik terpisah. Pending CREATE ditampilkan sebagai overlay tersendiri.

Mobile dan galeri melaporkan ID yang benar-benar terlihat, mendukung prepend, dan menggunakan jangkar ID saat jendela bergeser. Rekonsiliasi WebSocket/simpan memperbarui baris cache dan penghapusan tidak muncul kembali ketika append. Refresh setelah ubah massal membaca jendela terlihat ± satu halaman serta halaman desktop aktif; tidak memuat seluruh histori gulir.

Uji terfokus integrasi: 5 suite / 68 uji lulus, termasuk maju/mundur 200 halaman, batas byte rendah, identitas seleksi/draf, update/delete, dan request refresh berbatas.

Chromium lokal dengan komponen React/virtualizer/pemuat/cache aplikasi sesungguhnya, jaringan daftar sintetis 10.000 aset × 4.000 karakter catatan:

| Tampilan | Maju 1→200 lalu kembali 1 | Halaman/baris maksimum | Estimasi isi maksimum | Kartu DOM akhir |
|---|---:|---:|---:|---:|
| Mobile | 33,21 detik | 6 / 300 | 2.526.840 byte | 21 |
| Galeri | 37,92 detik | 6 / 300 | 2.526.840 byte | 9 |

Seleksi `p1-0` dan draf tetap utuh setelah kembali. Refresh di ujung meminta `[1,198,199,200]`; jangkar mobile `p199-35` dan galeri `p199-44` sama sebelum/sesudah. Fixture menguji lifecycle daftar nyata dengan respons sintetis; autentikasi/form dan API produksi diuji terpisah oleh smoke root. Harness menunggu render/anchor selesai di antara gerakan sintetis agar pembacaan metrik tidak mendahului commit React.

Data mentah: [pengukuran-chromium.json](pengukuran-chromium.json). Harness/perintah: [scripts/frontend_profiles/README.md](../../../scripts/frontend_profiles/README.md).
