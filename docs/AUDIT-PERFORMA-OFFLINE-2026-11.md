# Audit performa, offline, dan ketahanan isian — diperbarui 9 November 2026

Audit mencakup jalur inti inventarisasi: formulir aset dan media, kamera,
Back/penutupan panel, antrean simpan, pemeriksaan koneksi, snapshot IndexedDB,
service worker, daftar/paginasi, operasi massal, serta kebijakan draf portal.
Kode backend daftar/snapshot dan observabilitas juga ditinjau. Pengukuran memakai
Chromium lokal dengan data sintetis, bukan pengukuran produksi atau seluruh
rute bisnis. Tidak ada pengiriman data/tes beban ke server produksi.

## Integrasi dengan produksi terbaru

Merge diselaraskan dengan `main` **57e734165fd56f8c5b2d9f862ddf2ed9d21d7a75**
(PR #1102–#1105), yang sudah terdeploy. Implementasi akhir mempertahankan
pratinjau foto, konfirmasi hapus, kepala form ringkas, chip draf, dan dialog
keluar dari rilis tersebut.

Draf memakai database produksi **aman_draf_aset**, store **draf**, serta kunci
`pengguna|kegiatan|aset` yang sama. Rekaman lama tanpa `revision` dibaca sebagai
revisi 0, lalu dinaikkan pada commit. Tidak ada migrasi ke database draf baru.
Pemulihan otomatis, format foto/checklist dan TTL 14 hari mengikuti rilis
produksi. Hook/vault draf eksperimental tahap awal telah digantikan; bukti
pengujiannya di bawah tetap merupakan catatan historis, bukan format aktif.

Tambahan perlindungan pada alur produksi: keluar menunggu commit lokal dan
tertahan bila disk gagal, isian menunggu receipt antrean sebelum direset, tulisan
per kunci diserialkan, serta compare-and-swap menolak tulis/hapus dari revisi
usang. Cadangan JSON dapat diunduh dari rincian draf. Kontrak penyimpanan lama,
UI foto terbaru, dan ringkasan kepala form diuji kembali bersama perubahan ini.
Validasi hasil gabungan: **2.493 tes pada 239 suite frontend lulus**; seluruh
lint tidak memiliki error. API `/api/health` dan `/aman-release.json` produksi
sama-sama melaporkan SHA dasar di atas sebelum rilis ini.
Tab versi lama tetap perlu ditutup sebelum upgrade outbox; kode lama belum
memeriksa revisi sehingga koordinasi penuh selama dua versi aktif bersamaan
belum dijamin.

## Temuan dan tindakan

| Prioritas | Temuan dan akibat | Tindakan/status |
| --- | --- | --- |
| P1 | `AssetForm.jsx` menyimpan isian/foto belum dikirim dalam state; tombol Tutup mereset isian, sedangkan Back dapat menutup panel atau mengganti aset. | **Diperbaiki:** draf IndexedDB kompatibel produksi dengan debounce 300 ms, flush saat keluar/halaman tersembunyi, pemulihan otomatis sesuai rilis terbaru, tombol unduh cadangan. Tutup tidak lagi mereset sebelum draf tersimpan. Back menunggu commit lokal dan ditahan bila gagal. |
| P1 | `useOptimisticQueue.js` menulis IndexedDB tanpa menunggu hasil, lalu langsung mengirim; induk menutup/reset form sebelum tahu data aman di perangkat. | **Diperbaiki:** receipt `persisted` terpisah dari respons server; request menunggu commit; form/alur kamera/peta menunggu receipt sebelum melanjutkan. Semua kegagalan penyimpanan memberi pesan, bukan hanya kuota. |
| P1 | Pemeriksaan identitas simpanan lalu penghapusan antrean memakai operasi IDB terpisah; penulisan baru dapat masuk di antaranya. | **Diperbaiki dan diperkuat:** ack, penghapusan payload, dan pembaruan dependensi dalam satu transaksi readwrite yang memeriksa token lease. |
| P1 | Respons health check lama dapat datang setelah event offline dan mengubah status menjadi online. Backend mati tanpa event jaringan juga tidak terdeteksi oleh hook. | **Diperbaiki:** nomor generasi membuang respons usang; probe awal dan berkala 10 detik saat antarmuka jaringan aktif. Penghapusan otomatis database antrean warisan saat mount dihilangkan agar audit tidak membuang pekerjaan lama. |
| P2 | Tombol hapus foto pada form langsung menghapusnya. | **Diperbaiki:** konfirmasi sebelum penghapusan; kamera menggunakan konfirmasi yang sudah tersedia. Ini melindungi penghapusan foto, bukan mengganti perilaku Ctrl+Z teks. |
| P1 | Antrean tetap berkunci `statusKey` (ID aset), walau beberapa operasi aset yang sama bisa ada saat request terdahulu sedang berjalan. Crash di antara operasi masih berpotensi menyisakan hanya rekaman terakhir. Penggabungan di RAM bukan jurnal per operasi. | **Diperbaiki:** jurnal per operasi unik, urutan per aset/satker/pemilik, ack atomik, dan idempotency key tetap untuk hasil kirim yang belum diketahui. Migrasi dari `aman_save_queue` v1 ke v2 menyalin payload sebelum mengosongkan store lama dalam satu transaksi. Ini bukan klaim exactly-once end-to-end. |
| P1 | Serialisasi antrean/snapshot terutama memakai ref/peta dalam satu tab. Tab lain dapat melakukan replay atau full sync bersamaan. | **Antrean diperbaiki:** lease IDB 150 detik, heartbeat 15 detik, token fencing, BroadcastChannel dan polling 10 detik. Dua tab Chromium dan penutupan tab pengirim telah diuji. **Masih terbuka:** serialisasi full sync snapshot lintas tab; perubahan ini hanya membuat tulisan aset/indeks/revisi snapshot atomik, belum mengunci seluruh rangkaian HTTP full sync. |
| P2 | Pada 50 ribu aset, pembacaan pertama memindai semua row snapshot yang membawa thumbnail. | **Diperbaiki sebagian dan diukur:** metadata pencarian disimpan terpisah tanpa thumbnail. Scan ringan per 512 row; media hanya dibaca untuk halaman tampil. Cold 50k ~1,46–2,10 detik pada dua run lokal. Backfill 256 row/transaksi dapat dilanjutkan; bila gagal/kuota penuh, reader memakai row lama. Indeks filter khusus dan worker CPU belum diterapkan. |
| P2 | Service worker mewajibkan Web Locks; browser tanpa API tersebut gagal instalasi cache baru. Navigasi memakai network-first tanpa timeout. | **Lanjutan:** tetapkan matriks browser minimum; fallback koordinasi cache yang aman dan batas tunggu navigasi sebelum shell lokal. Uji worker dua rilis/dua tab sebelum mengubah aturan penghapusan cache. |
| P2 | Snapshot baca berumur tujuh hari dan tidak menyimpan foto/dokumen penuh; portal mempunyai TTL sesi dan menghapus data kedaluwarsa sesuai kebijakan yang ada. | **Batas saat ini:** offline lama dan media penuh tidak dijamin. Pisahkan retensi bukti belum terkirim dari cache yang bisa dibangun kembali; tinjau kebijakan portal bersama pemilik alur sebelum mengubahnya. |
| P2 | Edit massal memiliki checkpoint operasi, tetapi isian sebelum membuat operasi belum otomatis mendapat perlindungan draf form aset. | **Lanjutan:** perluas vault draf ke editor massal dan formulir lain dengan schema serta scope masing-masing; jangan menganggap satu hook sudah melindungi seluruh halaman. |

## Perilaku draf akhir

- Draf tetap terikat pengguna, kegiatan dan ID aset/mode baru, menggunakan
  database dan kunci yang sudah terdeploy. Ini isolasi aplikasi, bukan enkripsi
  terhadap orang yang menguasai profil browser perangkat.
- Foto baru, baseline edit, versi, susunan foto lama dan checklist disimpan
  dalam schema produksi. Pemulihan otomatis mempertahankan perilaku yang
  sudah dipakai; perubahan server pada field lain tetap terbawa. Versi berbeda
  tidak menerapkan ulang penghapusan/indeks foto lama secara otomatis.
- Revisi diperiksa dalam transaksi untuk menolak tab yang menulis/hapus dari
  dasar usang. Autosave satu tab dan penghapusan draf menunggu urutan commit.
  Penyelesaian simpan aset lama tidak membersihkan state draf aset berikutnya.
- Keluar/Back melalui gerbang form menunggu commit lokal. Jika gagal, form
  tetap terbuka dan cadangan JSON berisi media dapat diunduh. Form hanya direset
  setelah parent membuktikan handoff ke outbox lokal atau server berhasil.
- Persistent storage diminta sekali bila API tersedia. Persetujuan browser
  tidak dijamin. OS kill sebelum commit masih dapat menghilangkan ketikan
  terakhir; IndexedDB bukan pengganti backup server. TTL draf produksi tetap
  14 hari dan perlu ditinjau tersendiri untuk kerja offline sangat panjang.

## Hasil pengukuran

Satu run Chromium headless Linux, tanpa backend, thumbnail sintetis 4 KiB per
aset. Angka ini bukan p95 produksi dan tidak mewakili HP kelas rendah.

| Jumlah aset | Pembacaan pertama | Halaman kedua | Mengubah filter |
| ---: | ---: | ---: | ---: |
| 1.000 | 80,6 ms | 2,2 ms | 4,4 ms |
| 10.000 | 636,0 ms | 2,7 ms | 26,3 ms |
| 50.000 | 3.601,9 ms | 2,7 ms | 234,1 ms |

Bukti: [snapshot.json](bukti-audit-offline-2026-11/snapshot.json).
Pembacaan pertama 50k memerlukan ~3.434 ms di IDB, sehingga memisahkan metadata
query dari byte thumbnail merupakan prioritas yang lebih kuat daripada sekadar
mengganti komponen tampilan. Paginasi setelah cache terbentuk sudah murah.

Uji vault nyata: penulisan foto sintetis 2 MiB ketika jaringan dimatikan melalui
CDP selesai sekitar 32,5 ms. Setelah navigasi/reload dan offline kembali, nama dan
seluruh byte foto tetap sama. Dua penulis memakai revisi sama menghasilkan satu
commit dan satu penolakan; penghapusan revisi lama mempertahankan revisi baru.
Bukti: [draft.json](bukti-audit-offline-2026-11/draft.json).
Reload halaman dilakukan saat online untuk memuat fixture; uji ini membuktikan
persistensi IDB melewati reload, bukan jaminan bootstrap aplikasi offline.

Uji otomatis mencakup draf, pemulihan foto pada form nyata, kegagalan storage,
Back tertahan saat commit gagal, pemisahan akun/sesi, receipt antrean, koneksi
putus-sambung, regresi form/kamera/peta, snapshot, dan operasi massal.
Pada tahap awal, 127 pengujian relevan lulus (126 regresi ditambah satu uji popstate;
suite draf/form terakhir juga dijalankan ulang). Build produksi dan lint
berkas perubahan turut diperiksa. Peringatan hooks lama
pada ImportDialog, PhotoLightbox, dan useRowLocking tetap ada.

## Penguatan antrean dan snapshot — 9 November

- Setiap simpanan memiliki ID operasi dan idempotency key sendiri. Operasi berikutnya
  untuk aset yang sama menunggu pendahulunya. Keberhasilan satu simpanan tidak
  menghapus payload simpanan lain. Body dan status disimpan terpisah sehingga
  heartbeat/polling tidak menulis ulang foto; cache payload mengikuti revisinya.
- Maksimal tiga request per tab. Transaksi IDB memilih pemegang lease; jika tab
  berhenti, tab lain dapat mengambil alih setelah lease 150 detik kedaluwarsa.
  Token lama tidak dapat menyelesaikan atau menggagalkan lease baru. Browser
  yang membekukan tab tetap dapat membuat request beririsan di server; kunci
  idempotensi stabil diperlukan untuk deduplikasi server.
- Gangguan jaringan memakai backoff 2–60 detik, dan `Retry-After` dihormati,
  termasuk ketika tombol retry ditekan. Respons 409 “sedang diproses” memakai
  key/body/versi yang sama. Hanya 409 dengan `current_version` merupakan konflik
  OCC. Respons sukses tanpa ID aset tidak menghapus antrean.
- Konflik tidak diselesaikan otomatis oleh reconnect, tombol sinkron global,
  atau penutupan halaman. Retry per aset dapat merebase perubahan skalar setelah
  peninjauan. Foto, checklist, dan indeks foto memerlukan peninjauan manual;
  toast menyediakan unduhan JSON cadangan. Import/penggabungan cadangan otomatis
  belum tersedia. NUP dummy yang ditolak secara definitif tetap dapat dinomori
  ulang; payload baru dan key baru harus commit sebelum dikirim.
- Penolakan validasi/hak akses/sesi (4xx selain timeout/rate limit) tidak diulang
  terus-menerus. Pengguna memperbaiki penyebabnya lalu memilih retry per aset.
  Hapus simpanan tertunda meminta konfirmasi. Riwayat ack/batal dibersihkan
  setelah tujuh hari ketika antrean diproses; pekerjaan belum terkirim tidak
  dibersihkan berdasarkan umur.
- Pemilik dan satker saat enqueue tetap melekat. Rekaman migrasi tanpa identitas
  pemilik **dipertahankan tetapi tidak otomatis dikirim oleh akun aktif**;
  pemulihan administratif untuk rekaman warisan ini masih diperlukan. Migrasi
  yang tertahan oleh tab versi lama memberi pesan agar tab lama menyimpan draf
  lalu ditutup. Tab baru melanjutkan setelah penguncian upgrade dilepas.
- Snapshot v3 mempertahankan semua row versi lama. Backfill indeks menyimpan
  checkpoint setiap batch dan baru memasang `queryReady` setelah lengkap.
  Upsert/delete menulis aset, metadata query, dan revisi dalam transaksi yang sama.
  Kegagalan sinkron maupun exception sinkron sebelum commit membatalkan transaksi,
  termasuk jika row aset sempat ditulis sebelum indeksnya gagal.
- Permintaan persistent storage tetap best effort. Migrasi awal perlu membaca
  row lama sekali dan dapat lambat; angka di bawah mengukur cold query **sesudah
  indeks tersedia**, bukan durasi migrasi atau bootstrap PWA offline.

Hasil Chromium dengan indeks baru (fixture yang sama: thumbnail 4 KiB/row):

| Jumlah aset | Pembacaan pertama | Halaman kedua | Mengubah filter |
| ---: | ---: | ---: | ---: |
| 1.000 | 93,7 ms | 5,0 ms | 9,1 ms |
| 10.000 | 278,8 ms | 3,0 ms | 30,5 ms |
| 50.000 | 1.462,3 ms | 3,3 ms | 93,6 ms |

Run pertama memperbaiki pembacaan awal 50k sekitar 59%. Pada run verifikasi
berikutnya yang berjalan bersamaan dengan build produksi, cold 50k 2.104,2 ms
dan halaman kedua 5,1 ms. Rentang pengamatan 1,46–2,10 detik ini menunjukkan
pengaruh beban mesin; ini bukan p95 atau target perangkat. 1k belum menunjukkan
perbaikan. Bukti run verifikasi: [snapshot-indexed-rerun.json](bukti-audit-offline-2026-11/snapshot-indexed-rerun.json).
Bukti run pertama: [snapshot-indexed.json](bukti-audit-offline-2026-11/snapshot-indexed.json).
Retained JS heap pada 50k sekitar 12,7 MB; ini bukan ukuran seluruh RAM browser.

Uji IndexedDB asli menggunakan **dua halaman Chromium**: satu pemenang claim,
tab pengirim ditutup, tab lain dimuat ulang, jaringan dimatikan, lalu lease
kedaluwarsa disimulasikan dengan memajukan waktu pada fungsi claim. Foto 2 MiB,
key, dan base version identik setelah pemulihan; edit kedua baru diambil setelah
ack pertama. Bukti: [outbox-native.json](bukti-audit-offline-2026-11/outbox-native.json).
Uji ini tidak mengirim request mutasi ke backend; ack server disimulasikan.
Reload fixture dilakukan online, lalu recovery IDB dilakukan offline.

Validasi lanjutan: 231 uji regresi lulus, kemudian lima uji tambahan untuk
rollback kuota outbox, fallback/rollback indeks snapshot, konfirmasi penghapusan,
`Retry-After`, dan simpan ulang sesudah disk gagal lulus bersama pengulangan
suite inti (236 uji unik).
Jest memakai `fake-indexeddb` untuk semantik transaksi; bukti Chromium di atas
melengkapi simulasi tersebut. Build produksi berhasil; lint berkas perubahan
bersih. Peringatan hooks lama pada ImportDialog, PhotoLightbox, dan useRowLocking
masih ada. Tidak ada deployment ke produksi.

Untuk mengulang fixture lokal:

```sh
NODE_ENV=production node scripts/frontend_profiles/build.cjs snapshot /tmp/aman-offline-qa
node scripts/frontend_profiles/offline-cdp.cjs /tmp/aman-offline-qa /tmp/aman-offline-results
```

## Prioritas yang masih terbuka

1. Koordinasi seluruh full sync snapshot lintas tab, fallback service worker
   pada browser tanpa Web Locks, batas tunggu navigasi, dan cold start offline.
2. Pusat status offline: jumlah draf/antrean/konflik, kuota/persistensi, usia
   snapshot dan kesiapan shell; impor cadangan dengan validasi versi/pemilik.
   Pembersihan cache harus mengecualikan draf dan outbox.
3. Perluasan draf ke editor massal, dokumen, dan portal sesuai scope/retensinya.
   Media besar masih base64; pertimbangkan Blob dan worker kompresi agar tidak
   menyalin semua foto pada setiap perubahan isian.
4. Matriks perangkat nyata: Chrome Android, Safari iOS/PWA, desktop, mode privat,
   kuota penuh, layar terkunci, tab dimatikan OS, pergantian akun, pembaruan worker,
   captive portal, serta pemulihan sesudah respons backend hilang. Pengukuran
   lokal belum membuktikan keandalan semua perangkat atau performa produksi.
