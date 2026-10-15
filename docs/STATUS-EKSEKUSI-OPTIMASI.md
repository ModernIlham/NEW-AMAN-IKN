# Status pelaksanaan optimasi

**Titik pemeriksaan:** dokumen ini mencatat rilis 339 sebelum tindak lanjut
[PR #1092](https://github.com/ModernIlham/NEW-AMAN-IKN/pull/1092). Deskripsi PR #1092 menjadi rujukan
rekonsiliasi akhir SHA guard, CI/deploy dan hasil aktivasi budget setelah
eksekusi aktual. Status menunggu di bawah berlaku pada checkpoint ini.

Terakhir diperbarui: 15 Oktober 2026. Ini adalah status berjalan dari
[rencana 29 paket](RENCANA-OPTIMASI-SKALABILITAS.md). **Implementasi lokal,
pengujian lokal, dan rilis produksi dibedakan.** Bukti terfokus tidak otomatis
menutup gerbang gabungan, aktivasi flag, kapasitas, atau pemulihan offsite.

Rilis gabungan [PR #1091](https://github.com/ModernIlham/NEW-AMAN-IKN/pull/1091) sudah masuk produksi pada
[`33932042e1f41e2a594405b5c16a50b10718c80e`](https://github.com/ModernIlham/NEW-AMAN-IKN/commit/33932042e1f41e2a594405b5c16a50b10718c80e):
[CI main 38756834500](https://github.com/ModernIlham/NEW-AMAN-IKN/actions/runs/38756834500) lulus dan
[deploy 38758168446](https://github.com/ModernIlham/NEW-AMAN-IKN/actions/runs/38758168446) berhasil.
Check [Validasi rilis (teruji)](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116501999363) dan
[Hasil deploy produksi](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116503271957) mengikat bukti ke SHA tersebut.
Backend dan metadata frontend melaporkan SHA yang sama. Health/deep HTTP 200,
HTML utama/service worker HTTP 200, dan **SRI 18 aset kritis** lulus;
[bukti HTTP rilis saat ini](bukti-optimasi/OPT-28/production-current-assets-3393204.json)
membedakan pemeriksaan tersebut. Deep health tidak mengeluarkan SHA sendiri.
[Smoke login produksi](bukti-optimasi/OPT-28/production-login-3393204.json)
lulus pada 1440/360: form terlihat, credential kosong, tekstur JPEG terdekode,
font siap, tanpa overflow/error runtime/request POST. Transport memakai adapter
CDP Fetch yang memverifikasi TLS melalui OS CA/proxy; pemeriksaan ini terbatas
pada login baca-saja, bukan bukti TLS langsung Chromium atau mutasi terautentikasi.
Digest 18 aset diverifikasi terhadap manifest; tag script utama HTML tidak
memiliki atribut integrity, sehingga tidak diklaim sebagai enforcement SRI HTML.
Tiga aset pendahulu yang nyata—main `cf7538f6` dan dua chunk—juga HTTP 200 dan
digest-nya cocok dengan filesystem pendahulu serta ledger aktif:
[bukti](bukti-optimasi/OPT-28/production-predecessor-3393204.json),
[Check inventaris](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116510340997).

Probe historis chunk `9311` mendapat HTTP 404, tetapi tidak tercantum pada
manifest pendahulu tersebut dan ledger pendahulunya tidak tersedia. Provenance,
kewajiban retensi serta penyebabnya belum terbukti; tidak ada klaim expiry atau
perbaikan legacy. Bukti di atas membatasi klaim kompatibilitas seluruh tab lama.
[Bukti produksi](bukti-optimasi/OPT-28/production-release.json) memisahkan fakta ini
dari gerbang yang masih berjalan: CI/rilis penguatan guard ledger/file hashed
serta aktivasi budget ekspor 1/1. **OPT-28 belum sepenuhnya ditutup.**

Fondasi sebelumnya pada `c3ac5559178472358aa5d3d03bf5eeb17b2adaa5`
(CI `38740257953`, deploy `38741148877`) dan
[buktinya](bukti-optimasi/OPT-08/production-foundation.json) dipertahankan sebagai
riwayat. HTTP 200 chunk lama pada fondasi itu berlaku untuk probe/masa tersebut.

`Kode dirilis` di tabel berarti implementasi sudah termasuk SHA produksi di atas.
Fixture/profil lokal menjelaskan cara pembuktian dan batasnya; flag nonaktif,
aktivasi operasional, kapasitas serta DR offsite memiliki status terpisah.
Keberadaan kode yang dirilis tidak otomatis mengaktifkan mode opsionalnya.

## Status 29 paket

| Paket | Implementasi dan bukti | Status / sisa yang nyata |
|---|---|---|
| OPT-00 | [Fixture Mongo/Redis](bukti-optimasi/OPT-00/hasil.md), kontrak multiproses paket terkait, dan harness browser build produksi. Fondasi kontrak awal sudah masuk main sebelumnya. | Fixture/harness masuk main dan CI rilis lulus; browser aplikasi 16 pemeriksaan lulus. Data uji tetap sintetis, bukan pengukuran kapasitas produksi. |
| OPT-01 | [Seleksi/keyboard](bukti-optimasi/OPT-01/hasil.md): keanggotaan ID, indeterminate, toggle halaman, kontrol bersarang dan pemulihan fokus. | Kode dirilis; tes perilaku dan browser aplikasi lulus. |
| OPT-02 | [CAS batch per aset](bukti-optimasi/OPT-02-03-batch-v2.md): versi preflight, hasil per ID, media/scalar satu CAS, lock semua ukuran dan kompensasi. | Kode dirilis; unit/Mongo/GridFS lulus. Batch keseluruhan tetap bukan transaksi lintas aset. |
| OPT-03 | [Operasi batch tahan retry](bukti-optimasi/OPT-02-03-batch-v2.md): request immutable, bukti atomik, receipt, horizon dan generasi dataset. | Kode dirilis; crash/lost-reply/resume/delete diuji. Rute legacy tetap tersedia untuk tab lama. |
| OPT-04 | [UI preflight/progres/resume](bukti-optimasi/OPT-04/hasil.md): semua child disiapkan sebelum mutasi, checkpoint metadata, ID tetap dan hasil parsial. | Kode dirilis; UI preflight/progres/resume dan browser aplikasi lulus. |
| OPT-05 | [Backup/arsip jujur](bukti-optimasi/OPT-05/hasil.md): manifest/checksum, validasi ZIP dan sukses durable terpisah dari unduhan. | Backend dan UI dirilis. ZIP online tetap application_best_effort; konsistensi/offsite adalah OPT-07. |
| OPT-06 | [Restore/recovery](bukti-optimasi/OPT-06/hasil.md), [reset](bukti-optimasi/OPT-06/reset.md): preflight, safety, drain, gate persisten dan recovery operator. | Kode recovery/reset dirilis. Drill SIGKILL Mongo/GridFS terisolasi lulus; pemulihan tanpa host sumber tetap gap OPT-07. |
| OPT-07 | [CLI snapshot/enkripsi/offsite](bukti-optimasi/OPT-07/hasil.md): inventaris penulis, fsyncLock, AES-GCM, readback dan attestasi escrow. | Tooling dirilis; belum selesai operasional: tujuan offsite, escrow key di luar host, jadwal/alert dan restore host terpisah belum terverifikasi. RPO/RTO belum dinyatakan. |
| OPT-08 | [Rollback semua fase](bukti-optimasi/OPT-08/hasil.md) dan [retensi static](bukti-optimasi/OPT-08/static-retention.md): mutex restore/deploy, drain dan chunk lama 24 jam. | Controller rollback/clean-venv/SHA dirilis; tiga aset pendahulu terbukti 200/digest cocok. Penguatan guard retensi berikutnya menunggu CI/rilis; layout aplikasi/nginx belum immutable. |
| OPT-09 | [Transport artifact](bukti-optimasi/OPT-09/hasil.md): sink ASGI bertekanan balik, chunk 64 KiB, cap dan download GridFS lazy. | Kode dirilis; transport/unit/GridFS lulus. Batas transport tidak menjamin memori seluruh renderer konstan. |
| OPT-10 | [Admission/liveness unduhan](bukti-optimasi/OPT-10/hasil.md): partial unique index, heartbeat sejak antre, terminal CAS dan drain. | Kode dirilis; klaim/admission/heartbeat diuji. Heartbeat tidak membuat job legacy otomatis dapat resume setelah restart. |
| OPT-11 | [Harga/agregasi eksak](bukti-optimasi/OPT-11/hasil.md): Decimal128, nol eksplisit, tie stabil, parity luring dan JSON finite/exact. | Kode eksak dirilis; batas Decimal128/JSON dan parity luring diuji. Tidak ada backfill nilai uang resmi atau klaim sort computed lebih cepat. |
| OPT-12 | [Read terbaru dan pembatalan](bukti-optimasi/OPT-12/hasil.md): guard/signal per kanal, scope akun/satker, clear/unmount dan picker dua sumber. | Kode guard/abort dirilis; respons terbalik, cancel dan isolasi scope diuji. |
| OPT-13 | [Replay/resync realtime](bukti-optimasi/OPT-13/hasil.md): posisi kesetaraan, dedup/ring bounded, getMore idle dan rekonsiliasi berkala. | Kode replay/resync dirilis; kontrak capped Mongo dan frontend lulus. API tetap otoritas; bus bukan durable outbox. |
| OPT-14 | [Checkpoint/fencing/fallback](bukti-optimasi/OPT-14/hasil.md) search dan invalidasi sesudah restore. | Kode fallback/fencing dirilis. Substring Mongo tetap default; aktivasi prefix/typo Meili menunggu bukti engine/task nyata. |
| OPT-15 | [31 pembaca laporan lengkap/413](bukti-optimasi/OPT-15/hasil.md) dan [restore bertahap](bukti-optimasi/OPT-15b/hasil.md). | Batas laporan dan restore bertahap dirilis. Budget row tidak menjamin RSS seluruh dokumen/media konstan. |
| OPT-16 | [Seed/Locust/preflight](bukti-optimasi/OPT-16/hasil.md): dataset server, scope, CSV/job nyata dan penolakan target produksi. | Harness masuk rilis; soak lokal 15 menit / 1.952 request tanpa kegagalan tersedia. Ramp/media representatif pada VPS staging dan sertifikasi kapasitas belum tersedia. |
| OPT-17 | [Inventaris produksi](bukti-optimasi/OPT-17/vps-inventory.json), [collector/alert](bukti-optimasi/OPT-17-runtime.md) dan [overhead](bukti-optimasi/OPT-17-overhead.json). | Kode collector/alert dirilis, tetap nonaktif. Overhead <5% belum terbukti; monitor/kanal alert eksternal belum dipasang/diuji. |
| OPT-18 | [Explain 10k/50k, indeks nama dan cursor](bukti-optimasi/OPT-18/hasil.md). Cursor akhir membaca 50 key dibanding skip 10.000 key pada fixture. | Kode query/index/cursor dirilis; page tetap default, cursor opt-in. Read model harga/count/stats dan projection PSP ditunda berdasarkan pengukuran. |
| OPT-19 | [Cache query/ID luring](bukti-optimasi/OPT-19/hasil.md): batch IDB 128, scope/revisi, LRU 16 MiB dan proyeksi tanpa media 24 MiB. | Kode cache dirilis; native Chromium 1k/10k/50k terukur. Query dingin tetap scan; worker tambahan belum dibenarkan. |
| OPT-20 | [Jendela mobile/galeri](bukti-optimasi/OPT-20/hasil.md): enam halaman/estimasi 8 MiB, prepend, jangkar dan refresh viewport+margin. | Kode jendela dirilis; Chromium 200 halaman maju/mundur lulus. Data terlihat dapat melampaui anggaran dengan overBudget eksplisit. |
| OPT-21 | [Manifest/SRI/cache lintas rilis](bukti-optimasi/OPT-21/hasil.md): pin/grace, global Web Locks, quota dan pembersihan cache instalasi terputus. | Kode SW dirilis; SRI 18 aset kritis dan tiga aset pendahulu lulus. 9311 merupakan observasi historis dengan provenance/kewajiban retensi belum terbukti; klaim seluruh tab lama dibatasi. |
| OPT-22 | [Executor/budget/worker](bukti-optimasi/OPT-22-worker-budget.md): empat builder offload, admission global dan XLSX persisten bertipe. | Kode executor/budget/worker dirilis. Aktivasi budget 1/1 masih menunggu; durable XLSX tetap mati karena lifecycle worker belum terintegrasi. Renderer lain bertahap. |
| OPT-23 | [Registry/helper domain](bukti-optimasi/OPT-23/hasil.md), [satu pemilik form responsif](bukti-optimasi/OPT-23/form-responsif.md). | Kode registry/helper/form dirilis; kontrak 51 scalar dan retensi draf/tab/fokus diuji. Refactor mekanis tidak diklaim mempercepat render. |
| OPT-24 | [Hash lock/clean install/spike](bukti-optimasi/OPT-24/hasil.md), [audit Python](bukti-optimasi/OPT-24/security.md), [remediasi frontend](bukti-optimasi/OPT-24/remediasi-frontend.md). | Runtime/hash lock dan cohort frontend dirilis. Python 137 runtime/156 dev nol advisory; frontend 49 kemunculan/25 GHSA tooling/0 kritis tetap tercatat. API Motor tetap; native Async/Vite terpisah. |
| OPT-25 | [Artefak/staging immutable](bukti-optimasi/OPT-25/hasil.md), [SHA health/frontend](bukti-optimasi/OPT-25/release-health.md). | Controller clean-venv dan SHA dirilis. Artifact/layout aplikasi-nginx immutable tetap staging, belum cutover atau dua siklus aplikasi penuh dengan antrean lama. |
| OPT-26 | [Batas 26a](bukti-optimasi/OPT-26/hasil-26a.md), [adapter/ref/backfill 26b/c](bukti-optimasi/OPT-26/storage.md): dual-read, ownership, CAS, PDF asli dan backup roundtrip. | Kode batas/adapter/ref dirilis; flag write GridFS tetap mati. Backfill/purge/broad GC tidak dijalankan; kompatibilitas rollback diperlukan sebelum aktivasi. |
| OPT-27 | [Tombstone overflow](bukti-optimasi/OPT-27/hasil.md): 9.999/10.000 lengkap; 10.001 memicu full refresh, scope tetap. | Kode overflow full-refresh dirilis; boundary Mongo/HTTP nyata lulus, draf/pending/snapshot dipertahankan. |
| OPT-28 | Rekonsiliasi paket, pengujian gabungan dan rilis. Dokumen ini adalah catatan serah-terima yang masih berjalan. | CI main/deploy 339 serta aset saat ini/pendahulu lulus. Penguatan guard retensi berikutnya dan aktivasi budget 1/1 masih berjalan; gap eksternal/bersyarat tetap tercatat. |

## Gerbang integrasi terakhir

CI main pada SHA produksi meluluskan **6.192 tes backend/operasi**, **134
kontrak**, serta **2.308 tes frontend**. Build/lint/audit dan job browser lulus.
Rujukan utama adalah Check pada SHA yang sama, bukan penjumlahan run terfokus:
[Validasi rilis (teruji)](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116501999363) dan
[Hasil deploy produksi](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116503271957).

Bukti lokal dan riwayat koreksi berikut dipertahankan untuk cakupan masing-masing:

- Frontend final: **217 suite / 2.308 tes lulus**, lint **0 error / 7 warning
  baseline**, frozen install dan dua build produksi lulus. Chromium aplikasi
  **16 pemeriksaan / delapan viewport-theme** membuktikan gambar decode,
  simpan/readback, draf lintas breakpoint serta offline/reconnect tepat sekali.
  [Bukti](bukti-optimasi/OPT-24/frontend-remediasi-gates.json).
- Backend kontrak terbaru: **134/134 lulus**, tanpa gagal/error/skip,
  **189,717 detik**, Python 3.11.17 dengan Mongo/Redis nyata. Ini mencakup
  publikasi job dengan hasil Mongo belum pasti, harga eksak, media dan font lokal.
- Snapshot lokal sebelumnya menjalankan **5.940 unit lulus / satu gagal / satu
  skip** dan **169 operasi lulus / tiga gagal**. Kegagalan direproduksi pada
  pembaca timeout reusable workflow dan fake proses legacy; keduanya diperbaiki
  tanpa menghapus coverage. Run CI berikutnya meluluskan unit/operasi, lalu menemukan isolasi kuota akun
  dan timing cursor pada kontrak; keduanya diperbaiki sebelum CI main final lulus.
- Perbedaan kontrak CI sudah direproduksi: tiga HTTP 429 akibat kuota ekspor
  antar tes, dan asumsi cursor sudah restart ketika event masih ada dalam
  buffer. Akun uji kini terpisah dengan satker/izin yang sama dan tes menunggu
  restart nyata; limiter, urutan dan pemeriksaan duplikasi tetap berlaku.
  Subset tujuh tes serta seluruh 134 kontrak terbaru lulus.
- Audit lock Python runtime **137** dan dev **156** paket lulus tanpa advisory,
  skip atau ignore; dua runtime pipless bersih benar-benar memiliki 137 paket.
  Frontend tersisa **49 kemunculan / 25 GHSA tooling / nol critical**, dengan
  batas yang dijelaskan pada [remediasi](bukti-optimasi/OPT-24/remediasi-frontend.md).
- Soak final **15 menit / 1.952 permintaan / nol kegagalan**, p95 320 ms dan
  p99 810 ms. Data sintetis utuh, lima akun uji dibersihkan dan server berhenti.
  [Bukti](bukti-optimasi/OPT-16/final-soak.json) mempertahankan riwayat run gagal;
  tidak menyatakan race TCP hilang atau kapasitas VPS tersertifikasi.
- Review akhir menutup race kehilangan balasan pelepasan GLOBAL dan publikasi
  artifact job. Tes fault nyata membuktikan rilis sehat dan file/lease tetap
  dipertahankan ketika hasil penulisan belum pasti. Durable worker tetap mati.

[Catatan validasi](bukti-optimasi/OPT-28/validation-progress.json) mempertahankan
run gagal dan cakupan masing-masing bukti. Angka run terfokus tidak dijumlahkan
sebagai satu suite. CI main dan deploy sudah lulus pada SHA di atas;
CI/rilis penguatan guard berikutnya dan aktivasi budget 1/1 masih terbuka.
Probe 9311 tetap catatan historis dengan provenance/kewajiban retensi belum terbukti.
Hasil fixture staging tidak menjadi klaim kapasitas produksi, RPO atau RTO.

## Flag dan keputusan yang tetap konservatif

Default kode tidak menyatakan konfigurasi produksi saat ini. Budget aktual
terbaca pada `/api/health.capabilities.export_global_budget`; aktivasi/rollback
tercatat pada Check **Export budget operation** dari controller main yang lulus CI.

| Mekanisme | Default/keputusan saat ini | Syarat sebelum mengubah |
|---|---|---|
| `AMAN_OBSERVABILITY_ENABLED` | Mati | Ulang overhead pada beban representatif yang lebih tenang; buktikan budget CPU lalu tetapkan pemilik alert. |
| `AMAN_EXPORT_GLOBAL_BUDGET_ENABLED` | Preflight lulus; teramati mati 2/2, aktivasi 1/1 menunggu main berikutnya | UID/direktori bersama, drain dan physical flock, health SHA serta dua permintaan dokumen publik wajib lulus. Kapasitas di atas 1 memerlukan pengukuran staging representatif. |
| `AMAN_EXPORT_DURABLE_XLSX_ENABLED` | Mati; template worker `autostart=false` | Worker staging siap, restart/retry/otorisasi/artifact dan kapasitas dibuktikan sebelum API diaktifkan. |
| `AMAN_CHECKLIST_GRIDFS_WRITE` | Mati | Dual-reader terpasang, staging seluruh consumer/backup/restore dan batas lampiran nyata lulus; backfill/purge tidak otomatis. |
| Cursor aset | Default `pagination=page`; `pagination=cursor` opt-in per request, bukan flag env baru | Consumer harus menangani token, expiry/generasi, dedup dan semantik dataset berubah. UI lama tidak dialihkan otomatis. |
| Meili prefix/typo | `MEILI_SEARCH_SEMANTICS=prefix_typo` opt-in; default kode substring Mongo | Uji engine/task nyata dan kelengkapan/lag sebelum memakai hasil operasional. Kehadiran service/key bukan bukti mode aktif. |
| Native PyMongo Async | Ditunda; kandidat keamanan tetap memakai API Motor 3.7.1/PyMongo 4.19.0 | Adapter `aggregate`/`close`, mock dan seluruh kontrak; target sebelum 31 Maret 2027, mendahului akhir critical fixes Motor 14 Mei 2027. |
| Vite | Penerapan ditunda; CRA/CRACO dipertahankan | Residual frontend 25 GHSA memberi pemicu spike nyata. Migrasi harus membuktikan kontrak build/CSS/SW/deploy; jangan memaksa mayor transitif. |
| Read model/worker query tambahan | Belum diaktifkan | Profil produksi/filter langka/concurrency/tail latency harus membenarkan biaya writer/restore dan migrasinya. |

## Gap operasional dan urutan berikutnya

1. **Tutup penguatan setelah rilis OPT-28.** Kode/UI 339 serta CI/deploy dan
   aset saat ini/pendahulu sudah diverifikasi. Penguatan guard untuk ledger
   hilang/file hashed tanpa pencatatan masih melalui CI/merge/deploy berikutnya;
   verifikasi aset 339 yang menjadi pendahulu sesudahnya. Probe 9311 dipertahankan
   sebagai observasi historis tanpa klaim kewajiban retensi atau penyebab.
   Budget 1/1 menunggu aktivasi sesudah main baru. [Preflight](https://github.com/ModernIlham/NEW-AMAN-IKN/runs/116509386093)
   lulus dan mengamati disabled 2/2; hasil aktivasi, capability/physical lock,
   serta smoke 429→200 harus dicatat terpisah.
2. **Aktifkan DR OPT-07 pada tujuan yang tersedia.** Lengkapi inventaris seluruh
   penulis/cron/scheduler/uploads dan jendela stop, bucket/prefix/retensi yang
   disetujui, kredensial, escrow key di luar VPS dan host restore terpisah.
   Buktikan upload+readback+dekripsi dan pemulihan tanpa host sumber, ukur RPO/RTO,
   lalu jadwal serta alert stale. Tool lokal tidak menggantikan langkah tersebut.
3. **Ukur kapasitas dan hidupkan monitoring OPT-16/17.** Inventaris produksi
   15 Oktober 2026 tersedia: 2 CPU, RAM sekitar 8 GB, satu proses backend,
   Mongo standalone, Redis dan Meili terdeteksi. Snapshot mencatat 0 arsip pada
   direktori aplikasi, offsite/key belum terkonfigurasi; ini tidak menilai backup
   eksternal di luar aplikasi. Jalankan ramp/soak dan profil media representatif
   pada staging, ulang baseline collector on/off, sepakati SLO, pemilik/interval
   monitor eksternal serta uji alert gagal→pulih. Belum ada janji jumlah pengguna.
4. **Lakukan aktivasi opt-in secara terpisah.** Aktivasi budget 1/1 masih menunggu; worker XLSX dan checklist
   refs tetap mati sampai staging/config/drain masing-masing terbukti. Atur batas
   body/buffer proxy sepadan dengan admission aplikasi 14 MiB; ukur heap/BSON pada
   lampiran nyata. Backfill menjaga inline; disposal/GC memerlukan kebijakan serta
   pemeriksaan semua pemilik, bukan TTL atau penghapusan massal.
5. **Selesaikan cutover immutable OPT-25 setelah staging.** Integrasikan artifact
   CI dan konfigurasi supervisor/nginx yang benar, dua siklus aplikasi penuh,
   N-client→N+1-API, queued write lama, rollback dan chunk lama. Produksi sekarang
   memakai clean-venv per rilis dan layout checkout/docroot. Verifikasi tiga
   aset pendahulu tidak menggantikan dua siklus aplikasi penuh. Staging mekanisme
   pointer saja belum membuktikan cutover produksi aman.
6. **Tinjau keputusan bersyarat pada pemicunya.** Native Async sebelum tenggat
   Motor; Vite/read model/renderer worker berikutnya berdasarkan pengukuran.
   Perluas browser iOS/WebKit dan perilaku offline/reconnect perangkat nyata
   sebelum mengklaim cakupan perangkat tersebut.
7. **Terbitkan konfigurasi cloud melalui produk.** Setup tersimpan pada draf 7;
   langkah Publish pada produk masih diperlukan untuk menjadikannya konfigurasi
   cloud aktif. Ini terpisah dari website produksi yang sudah dirilis.

## Pemetaan temuan review R01–R25

Pemetaan ini menunjukkan tempat implementasi dan bukti; status rilis mengikuti
tabel paket di atas. Kode koreksi sudah dirilis; penerapan mode opsional dan
pembuktian operasional memiliki batas terpisah.

| Temuan | Paket / bukti | Kesimpulan saat ini |
|---|---|---|
| R01 batch lost update/hitungan | [OPT-02](bukti-optimasi/OPT-02-03-batch-v2.md) | Kode CAS/hasil per ID dirilis; kontrak Mongo nyata lulus. |
| R02 retry menggandakan efek | [OPT-03](bukti-optimasi/OPT-02-03-batch-v2.md), [04](bukti-optimasi/OPT-04/hasil.md) | Bukti atomik, receipt dan UI resume dirilis; retry/crash diuji. |
| R03 backup/arsip/ketidakkonsistenan | [OPT-05](bukti-optimasi/OPT-05/hasil.md), [07](bukti-optimasi/OPT-07/hasil.md) | Perbaikan arsip/UI dirilis; backup konsisten/offsite operasional masih terbuka. |
| R04 restore tanpa recovery utuh | [OPT-06](bukti-optimasi/OPT-06/hasil.md), [07](bukti-optimasi/OPT-07/hasil.md) | Recovery fail-closed dirilis; source-independent DR belum terbukti. |
| R05 buffering artifact | [OPT-09](bukti-optimasi/OPT-09/hasil.md) | Sink/download berbatas dirilis; builder tetap membutuhkan budget, aktivasi 1/1 menunggu. |
| R06 klaim/heartbeat unduhan | [OPT-10](bukti-optimasi/OPT-10/hasil.md) | Admission/transisi/heartbeat dirilis; job legacy tidak otomatis resumable. |
| R07 rollback/rilis parsial | [OPT-08](bukti-optimasi/OPT-08/hasil.md), [25](bukti-optimasi/OPT-25/hasil.md) | Controller rollback/clean-venv/SHA dirilis; full immutable aplikasi/nginx cutover belum dilakukan. |
| R08 harga leksikal/batas nol | [OPT-11](bukti-optimasi/OPT-11/hasil.md), [18](bukti-optimasi/OPT-18/hasil.md) | Koreksi eksak dirilis; read model ditunda sesuai explain. |
| R09 respons pencarian usang | [OPT-12](bukti-optimasi/OPT-12/hasil.md) | Guard/abort dirilis; tes respons terbalik/cancel lulus. |
| R10 seleksi/keyboard | [OPT-01](bukti-optimasi/OPT-01/hasil.md) | Perilaku seleksi/keyboard dirilis; browser aplikasi lulus. |
| R11 urutan ObjectId realtime | [OPT-13](bukti-optimasi/OPT-13/hasil.md) | Token kesetaraan/resync dirilis; capped Mongo multiproses diuji. |
| R12 checkpoint/cap Meili | [OPT-14](bukti-optimasi/OPT-14/hasil.md) | Fallback/fencing dirilis; prefix engine opsional perlu staging nyata. |
| R13 laporan terpotong | [OPT-15](bukti-optimasi/OPT-15/hasil.md) | Kode dirilis: lengkap di bawah cap atau 413 sebelum render. |
| R14 biaya offset/query | [OPT-18](bukti-optimasi/OPT-18/hasil.md) | Query/index/cursor dirilis; default page/exact count dipertahankan. |
| R15 scan snapshot setiap halaman | [OPT-19](bukti-optimasi/OPT-19/hasil.md) | Cache ID/proyeksi dirilis; native IDB terukur dan scan dingin tetap ada. |
| R16 histori mobile tak berbatas | [OPT-20](bukti-optimasi/OPT-20/hasil.md) | Jendela dirilis, terukur 200 halaman; pengecualian visible-data eksplisit. |
| R17 retensi/revalidasi SW | [OPT-21](bukti-optimasi/OPT-21/hasil.md) | SW/SRI 18 aset kritis dirilis/lulus dan tiga aset pendahulu terverifikasi; provenance/kewajiban retensi 9311 historis belum terbukti. |
| R18 budget/job restart | [OPT-22](bukti-optimasi/OPT-22-worker-budget.md) | Kode budget/job dirilis; aktivasi 1/1 menunggu dan worker durable tetap mati. |
| R19 builder sinkron di loop | [OPT-22](bukti-optimasi/OPT-22-worker-budget.md) | Empat façade offload dirilis; renderer lain bertahap berdasarkan profil. |
| R20 coupling/registry drift | [OPT-23](bukti-optimasi/OPT-23/hasil.md) | Boundary/helper/registry dirilis dan kontrak 51 scalar lulus; bukan rewrite seluruh modul. |
| R21 toolchain/dependency | [OPT-24 Python](bukti-optimasi/OPT-24/security.md), [frontend](bukti-optimasi/OPT-24/remediasi-frontend.md) | Lock/runtime/cohort frontend dirilis; sisa 25 GHSA tooling dijelaskan. Native Async/Vite tetap terpisah. |
| R22 alat ukur/CI tidak representatif | [OPT-00](bukti-optimasi/OPT-00/hasil.md), [16](bukti-optimasi/OPT-16/hasil.md) | CI/browser main lulus; soak lokal 15 menit tersedia, ramp/soak VPS/media representatif belum. |
| R23 monitor/offsite belum terbukti | [OPT-07](bukti-optimasi/OPT-07/hasil.md), [17](bukti-optimasi/OPT-17-runtime.md), OPT-28 | Tooling dirilis; kanal alert eksternal, DR dan SLO masih pekerjaan operasional. |
| R24 inline media/restore penuh | [OPT-26](bukti-optimasi/OPT-26/storage.md), [15b](bukti-optimasi/OPT-15b/hasil.md) | Restore/batas/adapter dirilis; flag refs mati, tanpa backfill/purge/broad GC. |
| R25 tombstone senyap | [OPT-27](bukti-optimasi/OPT-27/hasil.md) | Overflow full-refresh dirilis; boundary Mongo/HTTP diuji. |

Data/token/akun pengujian berada pada database sintetis `aman_ci_*` dan berkas
privat lokal. Kredensial tidak disalin ke bukti publik. Data pengukuran lokal,
terutama pada host bersama, tidak dijadikan kapasitas produksi atau RPO/RTO.
