# Status pelaksanaan optimasi

Terakhir diperbarui: 15 Oktober 2026. Dokumen ini mencatat pelaksanaan
[rencana 29 paket](RENCANA-OPTIMASI-SKALABILITAS.md), bukan pernyataan bahwa
seluruh gerbang produksi sudah lulus. `Lokal` berarti implementasi berada di
checkout kerja dan masih harus masuk PR, CI, serta verifikasi rilis.

| Paket | Status dan bukti aktual |
|---|---|
| OPT-00 | Kontrak Mongo/Redis nyata masuk main melalui PR1089; CI/deploy sukses pada `9ef3034`. Smoke Chromium aplikasi nyata sedang dilengkapi. |
| OPT-01 | Lokal: seleksi keanggotaan, indeterminate, keyboard kontrol bersarang; tes perilaku lulus. |
| OPT-02/03 | Lokal: CAS per aset, bukti penerapan atomik, receipt rekonsiliasi, hasil per ID dan generasi dataset; 8 kontrak Mongo/GridFS lulus. |
| OPT-04 | Lokal: preflight seluruh chunk, persetujuan sebelum mutasi, checkpoint metadata dan resume ID sama; browser mutasi masih diuji. |
| OPT-05/06 | PR1090: validasi arsip, safety snapshot, recovery persisten, drain penulis dan invalidasi cache; drill proses mati sesudah wipe lulus. |
| OPT-07 | Adapter snapshot offline/enkripsi/offsite tersedia lokal. Tujuan offsite, escrow kunci, serta restore pada host terpisah belum diverifikasi. Klarifikasi pengguna masih ditunggu. |
| OPT-08 | PR1090: rollback seluruh fase dan mutex deploy/restore; fault injection serta kontrak Mongo lulus. |
| OPT-09/10 | Lokal: transport ASGI/GridFS 64KiB, admission unik, heartbeat dan terminal CAS; kontrak dua proses dan memori transport lulus. |
| OPT-11 | Lokal: harga Decimal128 eksak dan parity luring; pengujian data sintetis menemukan NaN pada agregasi lama, perbaikan seluruh pembaca yang terdampak sedang diverifikasi. |
| OPT-12 | Lokal: abort/tiket respons dan scope pencarian; tes respons terbalik lulus. |
| OPT-13 | Lokal: cursor realtime berjangkar kesetaraan, dedup bounded dan resync; kontrak capped Mongo/multiproses lulus. |
| OPT-14 | PR1090 memuat fondasi checkpoint/fencing Meili dan fallback Mongo. Mesin Meili nyata belum diprovision; semantik substring default tetap memakai Mongo. |
| OPT-15 | Lokal: 31 pembaca laporan memakai limit+1 dan menolak overflow413. Restore streaming pada PR1090; kontrak batas/rendering lulus. |
| OPT-16 | Harness seed/Locust nyata lokal, guard produksi, akun sintetis dan kelengkapan snapshot lulus. Smoke hangat 10k aset/10 pengguna/30detik:111 request,0 gagal,p95 380ms; bukan kapasitas produksi atau soak. |
| OPT-17 | Pengambilan inventaris produksi tersanitasi dan metrik operasional sedang dikerjakan. |
| OPT-18 | Explain10k lokal selesai; cursor opt-in dan pengukuran50k sedang dikerjakan. Read model belum dibenarkan oleh data yang tersedia. |
| OPT-19/20 | Cache ID/query luring bounded dan jendela mobile sedang dikerjakan; hasil JSdom belum dianggap latensi browser nyata. |
| OPT-21 | Siklus service worker dua rilis dan retensi chunk sedang dikerjakan. |
| OPT-22 | Lokal: budget lintas proses dan worker XLSX bertipe; SIGSTOP/SIGKILL, fencing dan revokasi izin lulus. Flag default mati; renderer lain serta staging masih dilengkapi. |
| OPT-23 | Boundary domain sudah diekstrak pada batch, harga, snapshot query, artifact dan opsi aset. Ekstraksi form/renderer yang tersisa sedang dikerjakan. |
| OPT-24 | Lock runtime/dev dengan hash dan clean-install sedang diuji; perubahan driver/bundler tidak digabung tanpa spike kompatibilitas. |
| OPT-25 | Paket immutable dan aktivasi/rollback pada layout staging terisolasi sedang dikerjakan; konfigurasi produksi belum ditukar. |
| OPT-26 | Inventaris referensi media dan batas checklist sedang dikerjakan; migrasi referensi harus menjaga klien/backup lama. |
| OPT-27 | Lokal: tombstone10.001 memicu full refresh, termasuk kontrak batas Mongo; pending edit dipertahankan. |
| OPT-28 | Belum lulus: menunggu semua perubahan berlaku dirilis, pengujian gabungan, browser/offline, inventaris/SLO dan bukti offsite. |

## Gerbang gabungan pertama

- 39 kontrak Mongo/Redis/GridFS/HTTP/multiproses lulus dalam57,51detik.
- Frontend:207 suite/2251 tes lulus,1 tes source-shape lama gagal; diganti
  pemeriksaan perilaku penyegaran dan respons usang,7 tes fokus lulus.
- Build frontend produksi lulus83,14detik; lint0 error,7 warning lama.
- Suite backend penuh masih berjalan. Angka akhir dan regresi akan dicatat
  sesudah seluruh proses selesai; hasil parsial tidak dianggap sukses.

Data, akun dan token pengujian berada di database `aman_ci_*` serta berkas
privat lokal; kredensial tidak disalin ke bukti publik. Pengukuran lokal saat
suite lain berjalan hanya smoke kebenaran dan indikasi latensi, bukan jaminan
jumlah pengguna. RPO/RTO offsite dan kapasitas produksi belum dinyatakan.
