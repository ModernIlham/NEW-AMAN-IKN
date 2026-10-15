# Status pelaksanaan optimasi

Terakhir diperbarui: 15 Oktober 2026. Ini adalah status berjalan dari
[rencana 29 paket](RENCANA-OPTIMASI-SKALABILITAS.md). **Implementasi lokal,
pengujian lokal, dan rilis produksi dibedakan.** Bukti terfokus tidak otomatis
menutup gerbang gabungan, aktivasi flag, kapasitas, atau pemulihan offsite.

Fondasi OPT-05/06/08 dan pengaman OPT-14 sudah masuk main dan dirilis pada
[`c3ac5559178472358aa5d3d03bf5eeb17b2adaa5`](https://github.com/ModernIlham/NEW-AMAN-IKN/commit/c3ac5559178472358aa5d3d03bf5eeb17b2adaa5):
[CI 38740257953](https://github.com/ModernIlham/NEW-AMAN-IKN/actions/runs/38740257953),
[deploy 38741148877](https://github.com/ModernIlham/NEW-AMAN-IKN/actions/runs/38741148877).
[Bukti produksi](bukti-optimasi/OPT-08/production-foundation.json) mencatat health
HTTP 200, manifest publik, dan chunk rilis lama tetap HTTP 200 dengan SHA-256
sesuai. Bukti ini berlaku untuk fondasi tersebut, bukan seluruh perubahan lokal
berikutnya. Identitas rilis gabungan berikutnya belum dicatat di dokumen ini.

`Lokal` di tabel berarti kode dan bukti tersedia di checkout kerja, masih
menunggu CI/rilis gabungan serta pemeriksaan setelah rilis. `Fondasi produksi`
berarti bagian yang disebut di atas sudah dirilis; pelengkap lokal tetap perlu
melewati gerbangnya sendiri. `Bersyarat/operasional` menyebut pekerjaan yang
memerlukan konfigurasi, staging, atau keputusan berdasarkan pengukuran.

## Status 29 paket

| Paket | Implementasi dan bukti | Status / sisa yang nyata |
|---|---|---|
| OPT-00 | [Fixture Mongo/Redis](bukti-optimasi/OPT-00/hasil.md), kontrak multiproses paket terkait, dan harness browser build produksi. Fondasi kontrak awal sudah masuk main sebelumnya. | Penguatan fixture/browser lokal; gerbang browser akhir dan CI gabungan masih menunggu. |
| OPT-01 | [Seleksi/keyboard](bukti-optimasi/OPT-01/hasil.md): keanggotaan ID, indeterminate, toggle halaman, kontrol bersarang dan pemulihan fokus. | Lokal; tes perilaku dan smoke browser aplikasi lulus, menunggu rilis. |
| OPT-02 | [CAS batch per aset](bukti-optimasi/OPT-02-03-batch-v2.md): versi preflight, hasil per ID, media/scalar satu CAS, lock semua ukuran dan kompensasi. | Lokal; unit dan Mongo/GridFS nyata tersedia, menunggu CI/rilis. Batch keseluruhan bukan transaksi lintas aset. |
| OPT-03 | [Operasi batch tahan retry](bukti-optimasi/OPT-02-03-batch-v2.md): request immutable, bukti atomik, receipt, horizon dan generasi dataset. | Lokal; crash/lost-reply/resume/delete diuji. Rute legacy terpisah dipertahankan untuk tab lama. |
| OPT-04 | [UI preflight/progres/resume](bukti-optimasi/OPT-04/hasil.md): semua child disiapkan sebelum mutasi, checkpoint metadata, ID tetap dan hasil parsial. | Lokal; unit dan browser aplikasi nyata lulus, menunggu CI/rilis. |
| OPT-05 | [Backup/arsip jujur](bukti-optimasi/OPT-05/hasil.md): manifest/checksum, validasi ZIP dan sukses durable terpisah dari unduhan. | Fondasi backend produksi; pelengkap UI lokal. ZIP online tetap `application_best_effort`; konsistensi/offsite adalah OPT-07. |
| OPT-06 | [Restore/recovery](bukti-optimasi/OPT-06/hasil.md), [reset](bukti-optimasi/OPT-06/reset.md): preflight, safety, drain, gate persisten dan recovery operator. | Fondasi produksi; pelengkap lokal menunggu rilis. Drill SIGKILL Mongo/GridFS terisolasi lulus; bukan drill host sumber hilang. |
| OPT-07 | [CLI snapshot/enkripsi/offsite](bukti-optimasi/OPT-07/hasil.md): inventaris penulis, fsyncLock, AES-GCM, readback dan attestasi escrow. | Tooling lokal diuji; **belum selesai operasional**: tujuan offsite, escrow key di luar host, jadwal/alert dan restore host terpisah belum tersedia/terverifikasi. RPO/RTO belum dinyatakan. |
| OPT-08 | [Rollback semua fase](bukti-optimasi/OPT-08/hasil.md) dan [retensi static](bukti-optimasi/OPT-08/static-retention.md): mutex restore/deploy, drain dan chunk lama 24 jam. | Fondasi produksi pada SHA di atas. Verifikasi SHA worker/frontend tambahan berada di OPT-25 lokal; layout produksi belum immutable. |
| OPT-09 | [Transport artifact](bukti-optimasi/OPT-09/hasil.md): sink ASGI bertekanan balik, chunk 64 KiB, cap dan download GridFS lazy. | Lokal; unit, Mongo/GridFS dan profil alokasi transport lulus. Batas transport bukan batas memori seluruh renderer. |
| OPT-10 | [Admission/liveness unduhan](bukti-optimasi/OPT-10/hasil.md): partial unique index, heartbeat sejak antre, terminal CAS dan drain. | Lokal; kontrak dua proses lulus. Rollout memerlukan audit/drain job legacy; heartbeat tidak berarti job lama dapat resume setelah restart. |
| OPT-11 | [Harga/agregasi eksak](bukti-optimasi/OPT-11/hasil.md): Decimal128, nol eksplisit, tie stabil, parity luring dan JSON finite/exact. | Lokal; unit dan kontrak Mongo batas besar/overflow/underflow lulus. Tidak ada backfill nilai uang resmi atau klaim sort computed lebih cepat. |
| OPT-12 | [Read terbaru dan pembatalan](bukti-optimasi/OPT-12/hasil.md): guard/signal per kanal, scope akun/satker, clear/unmount dan picker dua sumber. | Lokal; 8 suite/76 tes terfokus lulus, termasuk deferred respons terbalik. |
| OPT-13 | [Replay/resync realtime](bukti-optimasi/OPT-13/hasil.md): posisi kesetaraan, dedup/ring bounded, getMore idle dan rekonsiliasi berkala. | Lokal; 47 unit/4 kontrak capped Mongo serta integrasi frontend lulus. API tetap otoritas; bus bukan durable outbox. |
| OPT-14 | [Checkpoint/fencing/fallback](bukti-optimasi/OPT-14/hasil.md) search dan invalidasi sesudah restore. | Fondasi produksi. Default kode memakai substring Mongo; prefix/typo Meili adalah opt-in. Layanan Meili terdeteksi pada inventaris, tetapi engine/task HTTP nyata belum diuji untuk aktivasi mode opsional tersebut. |
| OPT-15 | [31 pembaca laporan lengkap/413](bukti-optimasi/OPT-15/hasil.md) dan [restore bertahap](bukti-optimasi/OPT-15b/hasil.md). | Batas laporan lokal, menunggu rilis; pembaca restore termasuk fondasi recovery. Budget row tidak menjamin RSS semua dokumen/media konstan. |
| OPT-16 | [Seed/Locust/preflight](bukti-optimasi/OPT-16/hasil.md): dataset server, scope, CSV/job nyata dan penolakan target produksi. | Lokal; smoke hangat 10k tercatat, belum ramp/soak representatif pada VPS staging. Belum ada klaim kapasitas pengguna produksi. |
| OPT-17 | [Inventaris produksi](bukti-optimasi/OPT-17/vps-inventory.json), [collector/alert](bukti-optimasi/OPT-17-runtime.md) dan [overhead](bukti-optimasi/OPT-17-overhead.json). | Inventaris baca-saja tersedia; collector lokal default mati. Noise pengukuran belum membuktikan overhead <5%; monitor/kanal alert eksternal belum dipasang/diuji. |
| OPT-18 | [Explain 10k/50k, indeks nama dan cursor](bukti-optimasi/OPT-18/hasil.md). Cursor akhir membaca 50 key dibanding skip 10.000 key pada fixture. | Lokal; API tetap default `pagination=page`, cursor hanya permintaan opt-in. Read model harga/count/stats dan projection PSP baru ditunda berdasarkan pengukuran, bukan dianggap sudah diterapkan. |
| OPT-19 | [Cache query/ID luring](bukti-optimasi/OPT-19/hasil.md): batch IDB 128, scope/revisi, LRU 16 MiB dan proyeksi tanpa media 24 MiB. | Lokal; native Chromium 1k/10k/50k tersedia, halaman cache 50k 2,6 ms. Query dingin tetap scan; worker tambahan belum dibenarkan oleh dominasi I/O. |
| OPT-20 | [Jendela mobile/galeri](bukti-optimasi/OPT-20/hasil.md): enam halaman/estimasi 8 MiB, prepend, jangkar dan refresh viewport+margin. | Lokal; Chromium 200 halaman maju/mundur lulus. Data yang sedang terlihat dilindungi dan dapat melampaui anggaran, dengan `overBudget` eksplisit. |
| OPT-21 | [Manifest/SRI/cache lintas rilis](bukti-optimasi/OPT-21/hasil.md): pin/grace, global Web Locks, quota dan pembersihan cache instalasi terputus. | Lokal; fixture Chromium dua rilis/offline/quota/SRI lulus. Server static grace sudah ada pada fondasi; rollout SW dan kompatibilitas aplikasi lintas rilis tetap gerbang integrasi/rilis. |
| OPT-22 | [Executor/budget/worker](bukti-optimasi/OPT-22-worker-budget.md): empat builder offload, admission global dan XLSX persisten bertipe. | Lokal; kontrak ASGI/multiproses SIGSTOP/SIGKILL lulus. Budget global dan durable XLSX default mati; staging konfigurasi/kapasitas wajib sebelum aktivasi. Renderer lain tetap bertahap. |
| OPT-23 | [Registry/helper domain](bukti-optimasi/OPT-23/hasil.md), [satu pemilik form responsif](bukti-optimasi/OPT-23/form-responsif.md). | Lokal; 51 scalar lintas patch/cache/CSV diuji; resize/hide mempertahankan draf/tab/fokus. Refactor mekanis tidak diklaim sebagai percepatan render. |
| OPT-24 | [Hash lock/clean install/spike](bukti-optimasi/OPT-24/hasil.md), [audit Python](bukti-optimasi/OPT-24/security.md), [remediasi frontend](bukti-optimasi/OPT-24/remediasi-frontend.md). | Lokal: dua install Python 137 paket identik/audit nol; frontend Axios/Router/tooling diperbarui dan 217 suite/2.308 tes + Chromium lulus. Sisa frontend 49 kemunculan/25 GHSA tooling, 0 kritis. API Motor tetap; native Async/Vite ditunda dengan batas/pemicu tertulis. |
| OPT-25 | [Artefak/staging immutable](bukti-optimasi/OPT-25/hasil.md), [SHA health/frontend](bukti-optimasi/OPT-25/release-health.md). | Mekanisme staging lokal lulus; identitas dua proses AMAN nyata diuji. **Belum cutover** supervisor/nginx/CI publishing produksi, belum dua siklus aplikasi penuh N/N+1+rollback dengan antrean lama. |
| OPT-26 | [Batas 26a](bukti-optimasi/OPT-26/hasil-26a.md), [adapter/ref/backfill 26b/c](bukti-optimasi/OPT-26/storage.md): dual-read, ownership, CAS, PDF asli dan backup roundtrip. | Lokal; flag tulis GridFS default mati. Backfill eksplisit/dry-run mempertahankan inline; audit orphan read-only. Tidak ada purge, broad GC, backfill atau aktivasi flag produksi. |
| OPT-27 | [Tombstone overflow](bukti-optimasi/OPT-27/hasil.md): 9.999/10.000 lengkap; 10.001 memicu full refresh, scope tetap. | Lokal; kontrak Mongo/HTTP nyata lulus, pending edit/snapshot tidak dihapus. |
| OPT-28 | Rekonsiliasi paket, pengujian gabungan dan rilis. Dokumen ini adalah catatan serah-terima yang masih berjalan. | **Belum ditutup.** Frontend final lokal lulus; backend gabungan/browser akhir/CI/rilis berikutnya serta gap operasional di bawah masih perlu bukti. |

## Gerbang integrasi terakhir

Hasil yang sudah diterima koordinator pada checkout gabungan sebelum delta
indeks lampiran berikutnya:

- Frontend wave3: **214 suite / 2.297 tes lulus**, 186,048 detik
  (`/tmp/aman-jest-wave3.log`). Timeout fixture SelectionToolbar pada run
  sebelumnya diperbaiki dengan satu change event untuk setup draf, tanpa
  menaikkan timeout; alur klik dan pemeriksaan retensi tetap diuji.
- Production build frontend: **lulus, 58,18 detik**
  (`/tmp/aman-build-wave3.log`). Lint: **0 error / 7 warning baseline**, 13,78 detik
  (`/tmp/aman-lint-final.log`). Ini hasil lokal, bukan CI/rilis baru.
- Browser aplikasi wave2: **lulus, 17,75 detik**, termasuk checklist yang
  benar-benar terlihat/lebar >0 pada 320/360/768/1440 × light/dark, retensi
  draf lintas breakpoint, keyboard, simpan/readback dan preflight batch.
  Bukti [form responsif](bukti-optimasi/OPT-23/form-responsif.md). Browser akhir
  dari snapshot final/harness CI masih menunggu; wave2 bukan penggantinya.
- Fixture SW Chromium native terpisah: **lulus, 7,37 detik**, dua tab/rilis,
  offline, SRI, install gagal dan quota; [bukti](bukti-optimasi/OPT-21/hasil.md).
  Fixture ini bukan dua siklus rilis aplikasi penuh pada produksi.

Review visual setelah wave3 menemukan URL lampiran STNK memakai posisi visual
rekomendasi, bukan indeks item server. [Perbaikan indeks media](bukti-optimasi/OPT-23/indeks-media.md)
lulus 5 suite/25 tes terfokus dan lint 0 error/7 warning baseline. Rebuild privat
berikutnya lulus Chromium 12 pemeriksaan/8 viewport-theme dalam 29,2 detik,
termasuk thumbnail/lightbox/pratinjau yang berhasil decode dan URL STNK HTTP200.
Gerbang frontend penuh/build kemudian diulang pada cohort dependency berikut;
hasil wave3 di atas tetap merupakan riwayat, bukan hasil frontend terakhir.

Cohort dependency frontend final lokal: **217 suite / 2.308 tes lulus**,
172,925 detik; lint **0 error / 7 warning baseline**; dua build produksi lulus.
Chromium asli **16 pemeriksaan / 55,95 detik** membuktikan media decode,
form/batch readback, delapan viewport/theme, snapshot/reload offline, pending
tanpa mutasi backend dan reconnect sekali tanpa replay kedua.
[Bukti seluruh gerbang](bukti-optimasi/OPT-24/frontend-remediasi-gates.json),
[batas audit frontend](bukti-optimasi/OPT-24/remediasi-frontend.md).
Hasil ini berasal dari kandidat source/lock yang sama pada salinan privat,
bukan bukti CI atau deployment.

**Belum dicatat lulus:** suite backend gabungan final, kontrak gabungan pada
snapshot final, gerbang CI, CI SHA rilis berikutnya, deploy serta
pemeriksaan HTTP/health setelah rilis tersebut. Koordinator akan menambahkan
hasil dan SHA tepatnya setelah selesai. Angka terfokus di setiap paket tidak
dijumlahkan sebagai satu run final dan tidak dipakai menyatakan semua gerbang lulus.

## Flag dan keputusan yang tetap konservatif

| Mekanisme | Default/keputusan saat ini | Syarat sebelum mengubah |
|---|---|---|
| `AMAN_OBSERVABILITY_ENABLED` | Mati | Ulang overhead pada beban representatif yang lebih tenang; buktikan budget CPU lalu tetapkan pemilik alert. |
| `AMAN_EXPORT_GLOBAL_BUDGET_ENABLED` | Mati | Lock directory bersama/UID/cap identik, drain semua proses dan kontrak staging dengan beban representatif. |
| `AMAN_EXPORT_DURABLE_XLSX_ENABLED` | Mati; template worker `autostart=false` | Worker staging siap, restart/retry/otorisasi/artifact dan kapasitas dibuktikan sebelum API diaktifkan. |
| `AMAN_CHECKLIST_GRIDFS_WRITE` | Mati | Dual-reader terpasang, staging seluruh consumer/backup/restore dan batas lampiran nyata lulus; backfill/purge tidak otomatis. |
| Cursor aset | Default `pagination=page`; `pagination=cursor` opt-in per request, bukan flag env baru | Consumer harus menangani token, expiry/generasi, dedup dan semantik dataset berubah. UI lama tidak dialihkan otomatis. |
| Meili prefix/typo | `MEILI_SEARCH_SEMANTICS=prefix_typo` opt-in; default kode substring Mongo | Uji engine/task nyata dan kelengkapan/lag sebelum memakai hasil operasional. Kehadiran service/key bukan bukti mode aktif. |
| Native PyMongo Async | Ditunda; kandidat keamanan tetap memakai API Motor 3.7.1/PyMongo 4.19.0 | Adapter `aggregate`/`close`, mock dan seluruh kontrak; target sebelum 31 Maret 2027, mendahului akhir critical fixes Motor 14 Mei 2027. |
| Vite | Penerapan ditunda; CRA/CRACO dipertahankan | Residual frontend 25 GHSA memberi pemicu spike nyata. Migrasi harus membuktikan kontrak build/CSS/SW/deploy; jangan memaksa mayor transitif. |
| Read model/worker query tambahan | Belum diaktifkan | Profil produksi/filter langka/concurrency/tail latency harus membenarkan biaya writer/restore dan migrasinya. |

## Gap operasional dan urutan berikutnya

1. **Tutup gerbang rilis gabungan OPT-28.** Gunakan satu SHA/snapshot, selesaikan
   backend+kontrak+browser/CI, catat seluruh hasil, lalu rilis melalui jalur deploy
   normal dan verifikasi SHA worker, metadata frontend, HTTP/health, mutasi,
   media dan klien lama. Jaga drain/receipt/checkpoint/antrean selama pergantian.
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
4. **Lakukan aktivasi opt-in secara terpisah.** Budget/worker XLSX dan checklist
   refs tetap mati sampai staging/config/drain masing-masing terbukti. Atur batas
   body/buffer proxy sepadan dengan admission aplikasi 14 MiB; ukur heap/BSON pada
   lampiran nyata. Backfill menjaga inline; disposal/GC memerlukan kebijakan serta
   pemeriksaan semua pemilik, bukan TTL atau penghapusan massal.
5. **Selesaikan cutover immutable OPT-25 setelah staging.** Integrasikan artifact
   CI dan konfigurasi supervisor/nginx yang benar, dua siklus aplikasi penuh,
   N-client→N+1-API, queued write lama, rollback dan chunk lama. Produksi sekarang
   tetap layout checkout/docroot lama dengan retensi static; staging mekanisme
   pointer saja belum membuktikan cutover produksi aman.
6. **Tinjau keputusan bersyarat pada pemicunya.** Native Async sebelum tenggat
   Motor; Vite/read model/renderer worker berikutnya berdasarkan pengukuran.
   Perluas browser iOS/WebKit dan perilaku offline/reconnect perangkat nyata
   sebelum mengklaim cakupan perangkat tersebut.

## Pemetaan temuan review R01–R25

Pemetaan ini menunjukkan tempat implementasi dan bukti; status rilis mengikuti
tabel paket di atas. `Lokal` tidak berarti temuan sudah diperbaiki pada produksi.

| Temuan | Paket / bukti | Kesimpulan saat ini |
|---|---|---|
| R01 batch lost update/hitungan | [OPT-02](bukti-optimasi/OPT-02-03-batch-v2.md) | CAS dan hasil per ID lokal, kontrak Mongo nyata. |
| R02 retry menggandakan efek | [OPT-03](bukti-optimasi/OPT-02-03-batch-v2.md), [04](bukti-optimasi/OPT-04/hasil.md) | Bukti atomik, receipt dan UI resume lokal. |
| R03 backup/arsip/ketidakkonsistenan | [OPT-05](bukti-optimasi/OPT-05/hasil.md), [07](bukti-optimasi/OPT-07/hasil.md) | Fondasi arsip produksi; backup offsite/konsisten operasional masih terbuka. |
| R04 restore tanpa recovery utuh | [OPT-06](bukti-optimasi/OPT-06/hasil.md), [07](bukti-optimasi/OPT-07/hasil.md) | Fondasi fail-closed produksi; source-independent DR belum terbukti. |
| R05 buffering artifact | [OPT-09](bukti-optimasi/OPT-09/hasil.md) | Sink/download berbatas lokal; builder tetap membutuhkan budget. |
| R06 klaim/heartbeat unduhan | [OPT-10](bukti-optimasi/OPT-10/hasil.md) | Admission/transisi atomik lokal, rollout perlu drain legacy. |
| R07 rollback/rilis parsial | [OPT-08](bukti-optimasi/OPT-08/hasil.md), [25](bukti-optimasi/OPT-25/hasil.md) | Fondasi rollback produksi; immutable cutover belum dilakukan. |
| R08 harga leksikal/batas nol | [OPT-11](bukti-optimasi/OPT-11/hasil.md), [18](bukti-optimasi/OPT-18/hasil.md) | Koreksi eksak lokal; read model ditunda sesuai explain. |
| R09 respons pencarian usang | [OPT-12](bukti-optimasi/OPT-12/hasil.md) | Guard/abort lokal, tes respons terbalik. |
| R10 seleksi/keyboard | [OPT-01](bukti-optimasi/OPT-01/hasil.md) | Perilaku lokal dan browser aplikasi lulus. |
| R11 urutan ObjectId realtime | [OPT-13](bukti-optimasi/OPT-13/hasil.md) | Token kesetaraan/resync lokal, capped Mongo multiproses. |
| R12 checkpoint/cap Meili | [OPT-14](bukti-optimasi/OPT-14/hasil.md) | Fondasi fallback/fencing produksi; prefix engine opsional perlu staging. |
| R13 laporan terpotong | [OPT-15](bukti-optimasi/OPT-15/hasil.md) | Lokal: lengkap di bawah cap atau 413 sebelum render. |
| R14 biaya offset/query | [OPT-18](bukti-optimasi/OPT-18/hasil.md) | Explain/indeks/cursor lokal; default page dan exact count dipertahankan. |
| R15 scan snapshot setiap halaman | [OPT-19](bukti-optimasi/OPT-19/hasil.md) | Cache ID/proyeksi lokal, native IDB terukur; scan dingin tetap ada. |
| R16 histori mobile tak berbatas | [OPT-20](bukti-optimasi/OPT-20/hasil.md) | Jendela lokal terukur 200 halaman; pengecualian visible-data eksplisit. |
| R17 retensi/revalidasi SW | [OPT-21](bukti-optimasi/OPT-21/hasil.md) | SW lokal; static server fondasi produksi; lifecycle aplikasi lintas rilis belum final. |
| R18 budget/job restart | [OPT-22](bukti-optimasi/OPT-22-worker-budget.md) | Budget/worker lokal default mati, aktivasi staging belum selesai. |
| R19 builder sinkron di loop | [OPT-22](bukti-optimasi/OPT-22-worker-budget.md) | Empat façade offload lokal; migrasi renderer lainnya bertahap berdasarkan profil. |
| R20 coupling/registry drift | [OPT-23](bukti-optimasi/OPT-23/hasil.md) | Boundary/helper/registry lokal dan kontrak 51 scalar; bukan rewrite seluruh modul. |
| R21 toolchain/dependency | [OPT-24 Python](bukti-optimasi/OPT-24/security.md), [frontend](bukti-optimasi/OPT-24/remediasi-frontend.md) | Lock/audit/dua install Python; cohort frontend lulus seluruh gerbang lokal, sisa 25 GHSA tooling dijelaskan. Native Async/Vite masih terpisah. |
| R22 alat ukur/CI tidak representatif | [OPT-00](bukti-optimasi/OPT-00/hasil.md), [16](bukti-optimasi/OPT-16/hasil.md) | Kontrak/harness diperbaiki; final browser/CI dan ramp/soak belum ditutup. |
| R23 monitor/offsite belum terbukti | [OPT-07](bukti-optimasi/OPT-07/hasil.md), [17](bukti-optimasi/OPT-17-runtime.md), OPT-28 | Inventaris tersedia; kanal alert eksternal, DR dan SLO masih pekerjaan operasional. |
| R24 inline media/restore penuh | [OPT-26](bukti-optimasi/OPT-26/storage.md), [15b](bukti-optimasi/OPT-15b/hasil.md) | Restore bertahap fondasi; adapter/batas lokal, flag refs mati, tanpa purge/GC. |
| R25 tombstone senyap | [OPT-27](bukti-optimasi/OPT-27/hasil.md) | Overflow full-refresh lokal, boundary Mongo/HTTP diuji. |

Data/token/akun pengujian berada pada database sintetis `aman_ci_*` dan berkas
privat lokal. Kredensial tidak disalin ke bukti publik. Data pengukuran lokal,
terutama pada host bersama, tidak dijadikan kapasitas produksi atau RPO/RTO.
