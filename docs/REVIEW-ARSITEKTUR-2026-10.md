# Review arsitektur dan skalabilitas AMAN — 15 Oktober 2026

**Baseline:** `62e345422b0828f54d3ca3fd5b2c6cb876f01aa2` (`main`, setelah PR #1087).
**Hasil pekerjaan:** review dan rencana implementasi; perubahan runtime belum dikerjakan.
**Dokumen lanjutan:** [backlog eksekusi](RENCANA-OPTIMASI-SKALABILITAS.md) dan
[panduan GPT-6.1 Sol](PANDUAN-EKSEKUSI-GPT-6.1-SOL.md).

## 1. Keputusan utama

Pertahankan **monolit modular** React + FastAPI + MongoDB/GridFS. Tambahkan batas
sumber daya, kontrak mutasi yang aman diulang, pengujian integrasi, dan pemisahan
service secara bertahap. Fondasi sekarang cukup untuk melanjutkan pengembangan;
belum ada pengukuran yang membenarkan microservices, Kubernetes, database per
satker, atau penulisan ulang aplikasi.

Prioritas pertama adalah kebenaran hasil dan pemulihan kegagalan. Mempercepat
batch yang masih dapat menimpa perubahan atau menambah worker sebelum batas job
bersifat global justru memperbesar masalah. Setelah itu ukur beban representatif,
optimalkan jalur yang terbukti mahal, dan uji batas kapasitasnya.

Tidak ada insiden produksi baru yang dinyatakan terjadi oleh review ini. Nomor
baris di bawah berlaku untuk baseline; cari juga nama simbol ketika kode berubah.

## 2. Lingkup, bukti, dan batas pemeriksaan

Pemeriksaan meliputi bootstrap/routing, daftar dan edit aset, ubah massal, media,
laporan/ekspor, job, backup/restore, query/index/search, cache/realtime, frontend
daring/luring, service worker, CI, deploy, load test, dependensi, serta runbook.
Jalur berisiko dibaca lebih dalam; ini bukan pembuktian formal seluruh endpoint,
audit regulasi BMN, atau audit keamanan menyeluruh.

- `git fetch origin main` berhasil; baseline sama dengan `origin/main` saat review.
- Penghitungan statis: **208 berkas Python non-test / 98.338 baris**, **67 modul
  route**, **670 dekorator endpoint pada direktori routes**. Angka endpoint tidak
  mencakup handler tambahan di `server.py` dan bukan jumlah operasi bisnis unik.
- Frontend: **332 berkas JS/JSX/TS/TSX non-test / 85.472 baris**, dengan test/helper
  test dikecualikan. Besar berkas menunjukkan wilayah perubahan, bukan bug sendiri.
- `reports.py` 8.081 baris; `AssetForm.jsx` 3.211; `DashboardPage.jsx` 1.973.
- AST menemukan **91 kemunculan impor antar-router**, termasuk impor lokal dalam
  fungsi. Ini bukti coupling, **bukan** bukti aplikasi mengalami circular-import
  saat startup. Aturan router mandiri dalam `memory/REFACTORING_PLAN.md` adalah
  snapshot historis; review Agustus sendiri sudah mencatat impor lokal antar-router.
- Tidak mengakses data pelanggan, SSH/VPS, profil query produksi, konfigurasi
  monitor eksternal, atau menjalankan load test produksi pada review ini.
- Topologi satu VPS, supervisor, Mongo standalone, dan Redis opsional berasal dari
  kode/runbook. Jumlah worker, versi, kapasitas aktual, backup offsite, dan alert
  yang aktif harus diinventaris ulang sebelum mengubah infrastruktur.

### Baseline verifikasi lokal

| Pemeriksaan | Hasil pada baseline | Batas interpretasi |
|---|---|---|
| `python -m pytest -q` melalui `.venv` | **5.567 lulus**, 133 warning, 304,91 detik | Default mengecualikan integrasi live; bukan bukti multiworker/DB nyata |
| Jest/CRACO, `--watchAll=false --runInBand` | **198 suite / 2.189 tes lulus**, 128,41 detik | jsdom dan mock tidak membuktikan lifecycle browser/SW |
| `yarn lint` | 0 error, 7 warning | 3 terkait hook, 4 directive test tidak terpakai; telaah per kasus |
| `CI=false yarn build` | Berhasil, 57,59 detik | Build lokal, bukan artefak yang dipasang ke produksi oleh review |
| `pip check` | Tidak ada requirement rusak | Tidak menyatakan seluruh paket perlu dipakai atau bebas kerentanan |
| `python scripts/cek_rahasia.py` | Lulus | Pemeriksaan pola pada berkas tracked |
| Reproduksi fungsi terisolasi | Detail di bawah | Dekorator/dependency HTTP dilewati; bukan uji otorisasi atau Mongo nyata |

Variabel font lokal `XDG_DATA_HOME=/workspace/.local/share` dan
`XDG_CACHE_HOME=/workspace/.cache` dipakai pada pytest agar render dokumen memakai
font yang telah dipasang. Node lokal 24 dan Python lokal 3.12 berbeda dari runner
CI yang menyatakan Node 22/Python 3.11; samakan toolchain sebelum membandingkan
hasil lintas mesin.

Build baru berisi 102 berkas JS: total gzip **1.655.287 byte**, main JS
**133.623 byte**, chunk dashboard `3060` **123.322 byte**, main CSS **38.601 byte**.
Diukur dengan Python `gzip.compress(..., mtime=0)`; **jumlah semua chunk bukan
payload awal halaman**. Belum ada HAR, LCP/INP produksi, atau baseline perangkat
pengguna yang dapat dipakai untuk menjanjikan persentase percepatan.

## 3. Fondasi yang wajib dipertahankan

| Fondasi | Bukti utama | Invarian untuk pekerjaan berikutnya |
|---|---|---|
| Halaman lazy dan batas galat | `frontend/src/App.js:33`, `components/BatasGalat.jsx` | Chunk gagal punya pemulihan; jangan menarik seluruh halaman lewat barrel |
| Virtualisasi dan jangkar daftar | `VirtualizedAssetTable.jsx:133`, `VirtualizedMobileCards.jsx`, `usePosisiDaftarAset` | Identitas baris memakai ID; simpan tidak memindahkan gulir/filter |
| Penjaga respons daftar | `usePenjagaPermintaan.js`, `lib/pemuatDaftarAset.js` | Respons lama tidak mengubah konteks terbaru |
| Snapshot dan antrean luring | `offlineSnapshot.js`, `useOptimisticQueue.js` | Draf/antrean tetap ada; quota/TTL/tombstone dan pemilik akun tetap dijaga |
| Isolasi satker | `shared_utils.py`, `auth_utils.py`, `gerbang_media.py` | Scope pada baca, tulis, lookup, media, laporan, cache, dan job |
| OCC dan idempotensi jalur aset tunggal | `routes/assets.py` | Konflik tidak menjadi last-write-wins; jangan menganggap semua jalur batch setara |
| Registry/domain helpers | `asset_fields.py`, `pembukuan_utils.py`, `spasial_utils.py` | Field tidak hilang di patch/export/luring; semantik angka/laporan resmi terjaga |
| Cache lintas worker | `redis_utils.py`, `shared_utils.py` | Generasi dan satker masuk kunci; Mongo tetap sumber kebenaran |
| Realtime lintas proses | `event_bus.py`, `routes/websocket.py` | Bus bounded dan tanpa busy-loop; hilang notifikasi dapat dipulihkan lewat resync |
| Job, TTL, heartbeat, pembersih | `jobs.py`, `routes/unduhan.py`, `indexes.py` | Sudah ada; perbaiki celah, jangan membuat sistem kedua tanpa migrasi |
| CI/deploy | `.github/workflows/ci.yml`, `deploy.yml`, `scripts/deploy_vps.sh` | SHA immutable, CI push/main, anti-downgrade, env privat, health gate |
| UI kompak terbaru | `DocumentChecklist.jsx`, `BatchEditPanel.jsx`, `SelectionToolbar.jsx` | Hide mempertahankan draf; hapus seleksi eksplisit; draft reset setelah sukses |

## 4. Temuan prioritas

**P1:** perbaikan lebih dahulu, karena hasil salah atau pemulihan kegagalan tidak
andal pada skenario yang teridentifikasi. **P2:** keandalan/kapasitas/pemeliharaan
berikutnya. Tidak ada label P0 insiden aktif tanpa bukti produksi.

### R01 · P1 · Batch dapat menimpa perubahan serentak dan melaporkan jumlah keliru

`backend/routes/batch.py:251` melewati pemeriksaan lock untuk lebih dari 50 target.
Jalur foto/checklist membaca isi lama lalu menulis array penuh dengan filter hanya
`id` (`:338–436`); penambahan `version` tidak sama dengan CAS terhadap versi awal.
`updated_count` berawal dari jumlah ID input (`:263`), bukan hasil tulis nyata
yang dikembalikan (`:541`).

Reproduksi fungsi asli dengan mongomock menyisipkan edit checklist tepat sebelum
`bulk_write`: `ConcurrentEdit` hilang, hasil tinggal `Lama, BatchEdit`, versi tetap
naik menjadi 3. Input `['a1','missing','a1']` melaporkan `updated=3` meski hanya satu
dokumen cocok. Ini bukti perilaku fungsi terisolasi, belum uji konkurensi Mongo.
Perbaikan: hasil per ID, deduplikasi, CAS, dan kompensasi media. **OPT-02**.

### R02 · P1 · Retry batch parsial dapat menggandakan efek yang sudah berhasil

`DashboardPage.jsx:719–732` mengirim potongan 200 ID berurutan. Jika potongan kedua
gagal, catch `:763–769` hanya memberi pesan umum; draf dan seluruh pilihan tetap
ada. Backend menambahkan foto/checklist ke isi lama. Retry mengulang potongan
pertama; timeout juga tidak membuktikan server belum commit.

Draf berhasil memang sudah di-reset pada `:754–758`, tetapi itu baru terjadi
setelah seluruh operasi sukses. Perlu operation ID, hasil parsial persisten,
deduplikasi efek atomik, dan UI resume. **OPT-03, OPT-04**.

### R03 · P1 · Backup belum membedakan lengkap, gagal-arsip, dan berhasil tahan lama

`backup.py:292–298` melewati blob GridFS yang gagal dibaca. `:458–479` tetap memberi
status `completed` jika pemindahan ke arsip gagal. Scheduler `:1047–1081` menerima
status itu sebagai sukses, memperbarui `terakhir_sukses`, dan menjalankan retensi.
Retensi tidak selalu menghapus file pada setiap kejadian, tetapi dapat memangkas
arsip lama jika jumlahnya melebihi batas meski arsip baru belum tersimpan.

Metadata koleksi dibaca sebelum GridFS (`:407–425`), tanpa snapshot lintas keduanya;
pergantian/hapus foto bersamaan dapat memutus referensi dalam backup. Bedakan
ZIP aplikasi yang best-effort dari backup konsisten untuk pemulihan. **OPT-05, OPT-07**.

### R04 · P1 · Restore dapat terus berjalan tanpa jaminan pemulihan utuh

`backup.py:545–550` melanjutkan restore setelah safety snapshot GridFS gagal;
`:625–631` menelan galat import GridFS. Jika rollback sendiri gagal (`:675–676`),
pesan tetap menyatakan data telah dikembalikan (`:678`) dan safety ZIP selalu
dihapus (`:680–685`).

Reproduksi `import_gridfs` dengan manifest menunjuk blob hilang menghapus file dan
chunk lama, lalu mengembalikan 0 tanpa exception. Maintenance/lock sudah ada;
keduanya tidak membuktikan isi arsip valid atau rollback berhasil. Perlu preflight
sebelum destructive write, hasil jujur, dan recovery artifact tetap tersedia saat
gagal. **OPT-06, OPT-07**.

### R05 · P1 · Pusat Unduhan melakukan buffering penuh sebelum batas ukuran

`routes/unduhan.py:181` memakai `httpx.ASGITransport`; `:216–217` baru mengiterasi
body dan memeriksa batas 200 MiB. Transport httpx 0.28.1 menampung response ASGI
sebelum menyerahkannya ke konsumen, meski API bernama `stream`.

Probe transport asli: delapan chunk × 1 MiB semuanya diproduksi sebelum konsumen
pertama; puncak `tracemalloc` 32,04 MiB untuk body 8 MiB. Ini ukuran fixture,
bukan RSS VPS atau rumus pasti untuk semua ekspor. `/jobs/{id}/download` juga
memuat artifact penuh lewat `jobs.py:85–96`; `/unduhan/{id}/file` sudah memakai
`readchunk`. Perlu sink berbatas dan streaming download nyata. **OPT-09**.

### R06 · P1 · Koordinasi unduhan memiliki celah antre, klaim, dan status terminal

Heartbeat dibuat setelah memperoleh semaphore (`unduhan.py:250–252`), padahal
komentar menjanjikan denyut saat antre. Satu exception DB mengakhiri loop
heartbeat (`:163–175`). Batas satu job per pengguna memakai count lalu insert
terpisah (`:291–300`). Menghapus job berjalan menghapus record tanpa menghentikan
kerjanya (`:374–387`).

Probe fungsi asli: denyut saat menunggu = 0; satu kegagalan update membuat task
denyut selesai; dua submit serentak diterima pada batas 1. Perbaiki liveness,
klaim Mongo atomik, transisi status, dan semantik hapus. **OPT-10**.

### R07 · P1 · Rollback deploy belum meliputi seluruh fase perubahan rilis

`scripts/deploy_vps.sh:295–308` mengganti checkout/dependensi dan restart backend
sebelum install/build frontend (`:377–385`). `pulihkan` ada, tetapi dipanggil pada
galat HEAD/health; kegagalan pip, restart, yarn, atau build dapat keluar lewat
`set -e` tanpa pemulihan pasangan rilis. Dua `mv` pada `:401–403` juga bukan satu
penggantian pointer atomik.

Akibat bersyarat: backend baru melayani frontend lama atau checkout/dependensi
parsial. Bukan klaim deploy terakhir gagal. Tambah failure-injection executable,
rollback menyeluruh dan verifikasi hasil, lalu artefak rilis immutable. **OPT-08, OPT-25**.

### R08 · P1 · Sort/filter harga belum menjamin semantik angka

`asset_sorting.py:10–11` mengurutkan `purchase_price` mentah; daftar memakai mapping
itu pada `assets.py:623–635`, sementara model menyimpan harga sebagai string.
String `"10000000"` berurut sebelum `"9000000"`; campuran tipe BSON juga berbeda
dari perbandingan angka. `assets.py:449` memakai `price_max or 999999999999`,
sehingga batas maksimum eksplisit 0 dianggap tidak diisi.

Perlu koreksi semantik lebih dahulu dan field urut numerik turunan bila benchmark
membenarkannya. Jangan mengubah representasi uang/domain akuntansi secara massal.
**OPT-11**, dengan pengukuran indeks di **OPT-18**. Probe fungsi builder menghasilkan
batas atas 999999999999 untuk input maksimum 0; sort mapping asli atas string
`2,10,100` menghasilkan `10,100,2`.

### R09 · P1 · Sebagian pencarian dapat menampilkan hasil permintaan lama

Contoh: `KodefikasiPage.jsx:85–110`, `PersediaanPage.jsx:163–179`,
`PenggunaanPage.jsx:179–197`, pemilih di `PengadaanPage.jsx:58–71`, dan
`PenilaianPage.jsx:93–115`. Debounce membatalkan timer, tetapi respons yang telah
berangkat tetap menulis state. Selesaikan request B lalu A: input B dapat
menampilkan daftar A. Dashboard sudah memiliki tiket generasi yang benar.
Perlu penerapan guard per kanal dan pembatalan read yang sudah tidak relevan.
**OPT-12**.

### R10 · P1/P2 · Pilih-semua dan keyboard tabel memiliki perilaku tidak konsisten

`DashboardPage.jsx:630–634` dan `VirtualizedAssetTable.jsx:131` membandingkan jumlah
pilihan dengan panjang halaman. Lima puluh ID halaman pertama membuat header
halaman kedua yang juga berisi 50 ID tampak terpilih meski ID berbeda.
Toolbar lain sudah memakai pemeriksaan keanggotaan yang benar.

`VirtualizedAssetTable.jsx:208–210` menangani Enter/Space yang merambat dari anak;
checkbox/tombol foto hanya menghentikan event click (`:300–321`). Keyboard pada
anak dapat membuka editor dan mencegah aksi native. Perbaiki operasi himpunan
halaman dan batas event keyboard. **OPT-01**.

### R11 · P2 · Watermark realtime menganggap ObjectId mengikuti urutan sisip

`event_bus.py:177–199` menggunakan `_id > last_id`, lalu memperbarui posisi pada
`:217`. Dua ObjectId dari proses berbeda di detik yang sama tidak memiliki
jaminan urutan sesuai penyisipan. Contoh ID pertama
`65000000ffffffffffffffff`, lalu `650000000000000000000001`: ID kedua lebih kecil
meski disisipkan belakangan dan dapat dilewati setelah cursor dibuka ulang.

Counterexample algoritme terbukti; pengujian capped Mongo lintas proses belum
dijalankan. Dampaknya notifikasi/invalidation terlewat, bukan penghapusan aset.
Pertahankan ring 1 MiB/1.000 dokumen dan pengendalian busy-loop. **OPT-13**.

### R12 · P2 · Reconciler Meilisearch dapat melewati timestamp yang sama

`meili_utils.py:489–530` membatasi sapuan 2.000 dokumen lalu melanjutkan dengan
`updated_at > checkpoint`. Reproduksi 2.001 dokumen dengan timestamp identik:
putaran pertama mengirim 2.000, putaran kedua kosong; satu dokumen tertinggal.
Sinkronisasi langsung kadang menutupi celah ini, tetapi reconciler tidak
memperbaikinya setelah kegagalan jalur langsung. Relevan **jika Meilisearch aktif**;
status layanan saat ini tidak diperiksa. Perlu cursor gabungan, acknowledgement
task indeks, serta rekonsiliasi deletion. **OPT-14**.

Ada batas kelengkapan lain: `meili_utils.py:60,246–261` membatasi candidate default
5.000 tanpa metadata complete. Daftar/count yang kemudian memakai `$in` candidate
dapat tampak lengkap padahal terpotong. Perlu fallback/kontrak completeness, bukan
sekadar menaikkan cap. Belum dibuktikan data produksi mencapai batas ini.

## 5. Batas kapasitas dan pemeliharaan yang perlu diukur

| ID | Bukti struktur | Dampak bersyarat dan langkah berikutnya |
|---|---|---|
| R13 | `reports.py:1143,5389,6670` dan banyak `to_list(100000)` | Laporan dapat terpotong pada batas; jangan sekadar menaikkan angka atau `to_list(None)`. Kontrak complete/too-large dan iterator/job berbatas: **OPT-15** |
| R14 | `assets.py:630–642`: offset, exact count setiap halaman; filter substring dan `$expr` harga | Biaya tumbuh sesuai query/data; perlu `explain`, query shape, payload, cache cold/warm sebelum indeks/cursor baru: **OPT-18** |
| R15 | `offlineSnapshot.js:322–329`; `pemuatDaftarAset.js:30–65` | Setiap halaman luring memuat/filter/sort/statistik seluruh snapshot: **OPT-19** |
| R16 | `pemuatDaftarAset.js:217–241,271–298` | State mobile menampung seluruh halaman yang digulir dan refresh seluruh jendela. Batas paralel 4 sudah ada; perlu batas jumlah/byte halaman: **OPT-20** |
| R17 | `public/service-worker.js:7–17,42–49,77–112` | Cache nama tetap lintas rilis tidak memangkas entry hash lama, dan hit immutable masih di-fetch ulang. Retensi harus menjaga tab lama/offline: **OPT-21** |
| R18 | `exports.py:1503`, `unduhan.py:67`, `spasial.py:1069`, `jobs.py:99` | Semaphore terpisah per proses; job state persisten tetapi eksekusi `create_task` tidak tahan restart. Budget global dan worker ekspor bertahap: **OPT-22** |
| R19 | `stiker.py:235–248`, `pegawai.py:646`, `kodefikasi.py:173`, `lbp.py:829` | Sisa builder sinkron berada di handler async. Ukur event-loop lag dan pindahkan fase CPU utuh ke executor berbatas: **OPT-22** |
| R20 | 91 impor antar-router; form dan renderer besar | Perubahan lintas domain lebih mudah drift; ekstrak service per use-case, kontrak/registry dahulu: **OPT-23** |
| R21 | `requirements.txt:153–154` tanpa pin; runtime/dev bercampur; CRA/CRACO dan driver lama | Clean install dan upgrade sulit dipastikan; audit dependensi langsung/dinamis, lock, toolchain seragam, spike driver terpisah: **OPT-24** |
| R22 | CI default tanpa Mongo/Redis/browser; `locustfile.py:148,170`; `loadtest.yml:81–82` | Snapshot load test tanpa activity_id mendapat 422; `heavy=1` tidak memanggil laporan; dry-run mengabaikan error. Perbaiki alat ukur dan kontrak: **OPT-00, OPT-16** |
| R23 | JSON log/health sudah ada; `LOGGING.md:18–24` berbeda dari supervisor di deploy | Monitoring eksternal/offsite belum terverifikasi; health HTTP200 dapat memuat peringatan Redis/index. Inventaris, alert, drill: **OPT-07, OPT-17, OPT-28** |
| R24 | `models.py:55–60`; checklist masih dapat membawa inline base64; restore `backup.py:567,664` membaca JSON koleksi penuh | Payload/BSON dan peak memory restore tumbuh. Batas server, dual-read referensi media, restore bertahap: **OPT-26, OPT-15b** |
| R25 | `assets.py:744–750`: tombstone single-delete maksimal10.000, full-refresh hanya untuk bulk-delete | Lebih dari10.000 penghapusan individual sejak sync dapat meninggalkan item terhapus di snapshot. Ini boundary kode, bukan insiden terukur. Overflow harus memicu full refresh: **OPT-27** |

## 6. Hasil reproduksi yang dapat dijadikan regresi pertama

Probe menjalankan fungsi sumber yang diekstrak melalui AST dengan dependency
palsu/in-memory, tanpa endpoint HTTP atau database produksi. Ini mengisolasi
mekanisme kegagalan; langkah implementasi wajib mengangkatnya ke behavioral test
handler asli dan integrasi Mongo bila semantik database menentukan hasil.

| Kasus | Setup dan interleaving | Hasil yang diamati | Hasil yang wajib setelah perbaikan |
|---|---|---|---|
| Batch CAS | Baca v1; sisip edit checklist v2 sebelum bulk write | Edit konkuren hilang; v3 | Konflik atau merge eksplisit; edit lain utuh |
| Batch count | ID `a1, missing, a1`; hanya a1 ada | updated=3 | Satu ID sukses; hasil ID lain eksplisit |
| Harga nol | Builder filter asli, price_max=0 | Batas berubah ke999999999999 | Batas tetap0 |
| Sort harga | Mapping asli, string2/10/100 | Urutan10/100/2 | Urutan2/10/100 |
| Meili ties | 2.001 dokumen, timestamp identik; dua sapuan | Hanya 2.000 terkirim | Semua terkirim sekali secara efektif; retry aman |
| GridFS restore | Manifest valid secara JSON, blob yang dirujuk tidak ada | Blob lama terhapus; return0 tanpa exception | Validasi gagal sebelum data aktif disentuh |
| Heartbeat antre | Tahan semaphore, jalankan task | 0 denyut saat antre | Tetap berdenyut dan berhenti saat selesai |
| Heartbeat fail-once | Update DB pertama melempar galat | Loop berhenti setelah satu panggilan | Iterasi berikutnya mencoba lagi |
| Admission | Dua submit interleaved, cap1, keduanya melihat count0 | Dua job diterima | Satu klaim; lainnya409 |
| ASGI streaming | 8 × 1 MiB, httpx0.28.1 asli | Producer selesai sebelum konsumen mulai | Konsumen menulis sebelum producer selesai; buffer bounded |
| ObjectId | Dua ID contoh R11, sisip tinggi lalu rendah | ID kedua tidak lolos `$gt` | Event tetap teramati atau resync dijalankan |

## 7. Temuan historis tidak boleh disalin sebagai backlog baru

- CI, JSON logging/request ID, Redis generasi, snapshot luring, virtualisasi,
  offload banyak renderer, cleanup job/artifact, dan rollback health **sudah ada**.
- Bug `photoItems` yang dibahas review Agustus sudah ditangani lewat ref pada
  `AssetForm.jsx:830–831,1828,1905`.
- Backup scheduler sudah memisahkan klaim dan hasil; R03 adalah celah **gagal
  mengarsipkan dianggap sukses**, bukan mengulang klaim bahwa pemisahan belum ada.
- `docs/TINJAUAN-SISTEM-2026-08.md`, `docs/REFACTORING_REVIEW.md`, dan
  `memory/ROADMAP.md` berguna sebagai riwayat. Status setiap butir harus diverifikasi
  terhadap baseline baru; tidak semua rekomendasi lama masih terbuka.
- Besar file, jumlah pengguna hipotetis, dan skor build tidak membuktikan kebutuhan
  microservices, SSR, database baru, atau penambahan worker.

Review ini selesai sebagai dasar keputusan. Status implementasi setiap pekerjaan
ada di [backlog OPT-00 sampai OPT-28](RENCANA-OPTIMASI-SKALABILITAS.md); jangan
menandai temuan selesai hanya karena suite baseline lulus atau rencana telah ditulis.
