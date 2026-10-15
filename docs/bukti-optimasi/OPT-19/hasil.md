# OPT-19 — query snapshot berbatas

Implementasi memakai indeks aktivitas IndexedDB v2 yang sudah ada; tidak ada migrasi store atau penghapusan antrean. Query pertama membaca kunci lalu batch 128 baris, membuang media dari proyeksi pencarian dan menyimpan hasil ID/statistik. Halaman berikut hanya membaca ID halaman tersebut. Query lain memakai proyeksi tanpa media bila masih masuk anggaran. Filter nominal menggunakan pembanding Decimal128 eksak OPT-11.

Anggaran RAM merupakan estimasi isi, bukan batas heap fisik: LRU empat hasil ID/statistik dengan total 16 MiB; satu proyeksi pencarian tanpa media maksimal 24 MiB. Proyeksi yang lebih besar tidak disimpan, sehingga query berikut kembali ke pembacaan bertahap. Kunci mencakup pemilik, satker, aktivitas, revisi/lastSync, filter, sort, dan revisi antrean. Mutasi snapshot, lintas tab, dan fokus menginvalidasi cache. Abort/guard mencegah hasil lama menimpa layar. `REACT_APP_OFFLINE_QUERY_CACHE=false` mempertahankan jalur lama untuk rollback.

Uji integrasi terfokus: 5 suite / 67 uji lulus pada fase integrasi; suite snapshot terbaru juga memverifikasi registri skalar dan pengosongan `barang_bersejarah`. Uji menggunakan deferred request serta penyimpan IDB bermodel transaksi untuk membuktikan satu scan indeks, pembacaan hanya 50 ID pada halaman berikut, pembatalan, dan invalidasi setelah upsert/delete/sync.

Pengukuran Chromium native IndexedDB lokal, data sintetis 4 KiB thumbnail/baris, satu kali per ukuran:

| Baris | Query dingin | Halaman cache | Query berbeda memakai proyeksi | Heap tertahan setelah GC |
|---:|---:|---:|---:|---:|
| 1.000 | 349,5 ms | 2,7 ms | 5,1 ms | 0,94 MiB |
| 10.000 | 944,8 ms | 3,1 ms | 41,8 ms | 2,97 MiB |
| 50.000 | 3.228,2 ms | 2,6 ms | 239,4 ms | 11,77 MiB |

Pada 50k, pembacaan IDB query dingin 3.082,6 ms; CPU query 142,1 ms. Query berbeda tidak membaca ulang 50k media; pembacaan halaman 4 ms, CPU query 59,4 ms, sisanya termasuk yield berkala agar event loop tetap mendapat giliran. Worker tambahan belum diperlukan untuk jalur ini: I/O mendominasi query pertama. Heap saat fungsi kembali sebelum GC 57,20 MB bukan ukuran peak. Hasil ini bukan p95 produksi atau pembuktian semua browser/perangkat.

Data mentah: [pengukuran-chromium.json](pengukuran-chromium.json). Harness persisten dan perintah ulang ada di [scripts/frontend_profiles/README.md](../../../scripts/frontend_profiles/README.md).
