# OPT-22: budget global dan worker XLSX read-only

Status: empat builder sinkron dipisahkan dan kontrak lokal nyata tersedia;
**kedua feature flag worker/budget global default mati**. Worker persisten
memulai migrasi dengan renderer XLSX aset. Aktifkan pada staging dengan
konfigurasi VPS aktual, ukur kapasitas, lalu aktifkan produksi setelah drain.
Dokumen ini tidak mengklaim seluruh renderer lama pindah proses worker;
migrasi renderer berikutnya mengikuti PR 22d sesuai profil.

## Executor dan façade builder

`render_executor.py` membatasi satu proses pada dua thread builder dan dua tugas
menunggu. Admission kelima menghasilkan 429; pembatalan coroutine tetap menunggu
thread selesai sebelum slot dilepas. Empat façade mempertahankan autentikasi dan
fetch Motor pada loop async lalu menyerahkan snapshot biasa ke builder:

- Pegawai: workbook dan dropdown/NIP teks dibangun dalam thread. Batas existing
  20.000 kini memeriksa satu baris tambahan dan menolak overflow dengan 413;
  hasil tidak dipotong diam-diam.
- Stiker: setiap thread memiliki canvas dan ImageReader sendiri; fetch aset,
  master kodefikasi dan kop tetap async. Jumlah/baris/footer batas tetap sama.
- Kodefikasi: cursor async menulis snapshot JSONL per 500 baris ke temp disk;
  builder thread membaca snapshot dan memiliki workbook write-only sendiri.
  Maksimal 250.000 baris/128 MiB snapshot ditolak eksplisit, bukan dipotong.
- LBP: seluruh fetch/otorisasi/penetapan lingkup selesai sebelum 34 nilai snapshot
  biasa dikirim ke builder DOCX yang memiliki Document sendiri. Tidak ada Motor
  atau workbook/canvas yang dibagi ke thread lain.

`test_render_executor.py` membuktikan event loop tetap berjalan, antrean terbatas,
dan cancel tidak melepaskan thread hidup. `tests/contract/test_renderers.py`
menguji XLSX pegawai (header/dropdown/NIP/satker), kedua bentuk kodefikasi, PDF
stiker, DOCX LBP, serta boundary N−1/N/N+1 dan plafon snapshot pada Mongo nyata.

## Budget gabungan pada satu VPS

`backend/export_budget.py` dan `ExportBudgetMiddleware` melindungi rute ekspor,
PDF/DOCX/XLSX laporan, kartu aset, serta stiker. Pusat Unduhan memanggil rute GET
internal yang sama sehingga melewati budget yang sama. Jalur XLSX async legacy
memakai `run_budgeted()` pada builder. Unduh artifact yang sudah jadi tidak
mengambil slot CPU render.

- `fcntl.flock` pada direktori **yang sama** adalah otoritas fisik CPU: default
  2 renderer global, 1 per pemilik, maksimal 2 per satker. Tidak bergantung jumlah
  proses Uvicorn. SIGSTOP mempertahankan lock; SIGKILL menutup descriptor.
- Mongo `export_resource_budget` berisi antrean maksimal 32 dan metadata
  holder. Admission maksimal 2 request per owner, dan operasi worker queued
  maksimal 1 per owner/8 per satker/32 global. Antrean penuh/waktu tunggu habis
  menghasilkan 429 dengan `Retry-After`; job owner yang sudah aktif menghasilkan
  409 dengan ID job yang dapat dipantau.
- FIFO berlaku di antara owner/satker yang dapat berjalan. Owner yang sudah
  memakai slot atau satker yang mencapai cap tidak menahan satker lain ketika
  slot global masih tersedia. Cancel sesudah enqueue Mongo tetapi sebelum
  balasannya diterima tetap membersihkan ticket; cleanup tahan cancel berulang.
- Metadata proses mati dipangkas hanya dengan bukti Linux host/boot/PID/start-time
  atau zombie. Tidak ada pengambilalihan berdasarkan heartbeat saja. Metadata
  Mongo yang salah/tertinggal tidak dapat membuka slot fisik tambahan.
- `run_budgeted()` melakukan shield terhadap seluruh coroutine render dan
  menunggu thread yang di-await selesai setelah pembatalan klien. Slot baru
  dilepas setelah pekerjaan betul-betul berhenti. Renderer GET juga memegang
  `writer_admission()` agar restore tidak membaca/menghasilkan setengah dataset.
- Internal ASGI yang bersarang memakai ContextVar proses tepercaya, bukan
  header dari pengguna, sehingga tidak terjadi pengambilan slot ganda/deadlock.
- Konfigurasi kapasitas disimpan di direktori lock dan diperiksa semua proses.
  Mengubah kapasitas memerlukan drain/stop seluruh proses lalu konfigurasi ulang;
  dua worker dengan cap berbeda gagal tertutup.

Budget ini **khusus satu kernel Linux/shared directory pada VPS sekarang**.
Jangan memperluas ke host kedua dengan menyalin env; keputusan lintas host perlu
mekanisme resource fencing tersendiri.

## Worker persisten read-only

`backend/export_worker.py` menyimpan `JobSpec` version 1 pada `background_jobs`:
renderer/resource class/retry policy, ID principal, epoch sesi, satker asal dan
satker efektif, generasi dataset, serta parameter filter bertipe. Tidak ada
Bearer/header Authorization atau raw Mongo query dalam job.

`POST /api/export/xlsx/async` memasukkan job persisten bila flag aktif. Worker
terpisah `python -m export_worker` membaca queue; request selesai atau proses
API restart tidak menghilangkan job. Filter dibangun ulang lewat builder query
aplikasi dari parameter bertipe, sesudah reautorisasi akun/satker/epoch dan generasi.

Claim CAS memiliki token worker, attempt, lease, heartbeat, dan identitas proses.
Publication artifact memakai CAS token+attempt+status yang sama; attempt lama
tidak dapat menerbitkan hasil. Byte ditulis ke GridFS per 64 KiB. Pengakuan commit
yang hilang ditelusuri sebelum blob dibersihkan. Kegagalan read-only sementara
mengantre ulang dengan backoff maksimal 3 attempt; error izin/scope/parameter
bersifat terminal. Reaper legacy tidak mematikan job protokol worker baru.

Worker memegang physical slot dan writer admission sepanjang build/upload/publish.
Setelah SIGKILL, worker berikutnya membuktikan PID lama mati, merebut ulang claim,
dan menghapus **hanya writer lease yang ID-nya tersimpan di claim lama**. Crash
sebelum claim masih memakai pemulihan operator fail-closed. SIGTERM/SIGINT normal
menyelesaikan pekerjaan aktif lalu berhenti; Supervisor menunggu hingga 30 menit.

Download memeriksa ulang principal pembuat dan scope saat ini, termasuk bagi admin
yang hendak mengunduh hasil milik akun yang sudah dicabut. Artifact dari generasi
dataset sebelum restore ditahan. Status publik menyembunyikan JobSpec/token
worker/identitas proses/lease internal.

Builder XLSX existing masih memiliki plafon 5.000 aset berfoto dan menyimpan
workbook/hasil dalam memori. Migrasi worker membatasi konkurensi dan memulihkan
restart; tidak mengklaim RAM builder menjadi konstan. Batas 200 MiB hasil worker
dan batas renderer lama tetap berlaku sampai profil membenarkan perubahan.

## Konfigurasi dan pemasangan staging

Semua proses API dan worker harus memakai nilai identik:

```dotenv
AMAN_EXPORT_GLOBAL_BUDGET_ENABLED=1
AMAN_EXPORT_DURABLE_XLSX_ENABLED=1
AMAN_EXPORT_GLOBAL_SLOTS=2
AMAN_EXPORT_SATKER_SLOTS=2
AMAN_EXPORT_LOCK_DIR=/var/lib/aman/export-locks
```

Direktori lock wajib milik UID aplikasi, mode 0700, tidak dapat ditulis grup/umum,
dan tetap berada di luar direktori rilis. Template Supervisor tersedia di
`scripts/supervisor/inventarisasi-export-worker.conf.example`; `autostart=false`
untuk mencegah aktivasi otomatis sebelum staging. Sesuaikan path dan UID dengan
API yang terpasang; template mengikuti path/UID dokumentasi VPS existing.

1. Pasang kode, biarkan flag API mati, siapkan lock directory dan Supervisor.
2. Jalankan suite unit dan kontrak pada Mongo/Redis **loopback sintetis**:

   ```bash
   .venv/bin/python -m pytest backend/tests/unit/test_export_budget.py \
     backend/tests/unit/test_export_worker.py -q
   AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 \
   AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
   .venv/bin/python -m pytest -m integration \
     backend/tests/contract/test_export_worker.py -q
   ```

3. Aktifkan kedua flag di staging, jalankan satu proses worker, uji filter dua
   satker, unduhan ulang, akun dicabut, burst export bersama endpoint ringan,
   serta restart dengan job aktif. Simpan SHA, kapasitas, queue age/RSS/event-loop
   lag dan bukti artifact valid. Jangan menjadikan pengukuran unit sebagai SLO.
4. Sebelum aktivasi produksi: verifikasi kapasitas VPS, seluruh process config
   identik dan worker hidup; drain deploy/restore terlebih dahulu. Aktifkan API
   setelah worker siap. Restart worker juga pada setiap perubahan kodenya;
   jangan membiarkan proses lama memuat modul rilis sebelumnya.

## Bukti kontrak yang sudah dijalankan

`backend/tests/contract/test_export_worker.py`: 3 tes pada Mongo/GridFS/Redis lokal
nyata, termasuk **dua subprocess Linux**. SIGSTOP mempertahankan hard cap 1;
SIGKILL membuat subprocess lain mendapat slot tanpa menunggu TTL. API membuat job,
worker dibunuh setelah claim, worker restart memakai builder produksi menghasilkan
XLSX ZIP valid dengan satu artifact dan attempt 2. Attempt stale gagal publish
serta blob sementaranya dibersihkan. Akun pembuat dicabut → unduhan oleh admin
pusat ditolak. Suite unit menambah pembatalan thread, nested budget, perubahan cap,
typed-filter, admission owner, revokasi epoch/satker, dan perubahan generasi.

`backend/tests/contract/test_export_budget_asgi.py`: **5 tes lulus** melalui
aplikasi ASGI sebenarnya dengan flag budget aktif, Mongo/Redis sintetis terpisah:

- Cap global 1, antrean uji 2 (default produksi 32), dua satker dan dua pegawai.
  Request A dibatalkan ketika builder thread masih hidup; slot fisik dan writer
  lease tetap ditahan. B lalu A menunggu, admission tambahan mendapat 429,
  termasuk header bypass palsu. Semua hasil XLSX dibuka dan lingkupnya diperiksa.
- Dua belas permintaan health tetap berhasil selama thread A ditahan. Pengukuran
  lokal 15 Oktober 2026: p95 0,664 ms; antrean 560/655 ms; peak RSS proses
  142.276 → 165.824 KiB. Data mentah berada di
  [`OPT-22/asgi-stress.json`](OPT-22/asgi-stress.json). Ini fixture kecil pada
  loopback, **bukan SLO, ukuran RAM satu ekspor, atau kapasitas VPS produksi**.
- Cap global 2/satker 1: A yang menunggu A aktif tidak menganggurkan slot kedua;
  B dapat menghasilkan XLSX sebelum A dilepas.
- Rute privat tanpa autentikasi menghasilkan 401; proposal DOCX/PPT publik tetap
  dapat dibuka. Duplicate Authorization/query token memakai principal yang sama
  dengan handler FastAPI, sehingga budget tidak dapat dibebankan ke akun lain.
- Failure injection sesudah Mongo enqueue sebelum balasan menguji cancel pada
  admission; request berikutnya pemilik yang sama berhasil. Akhir uji tidak ada
  holder, waiter, atau request writer lease yang tersisa.

Unit inventory menelusuri decorator rute pembuat PDF/DOCX/XLSX/ZIP/CSV nyata;
setiap rute harus masuk budget atau mempunyai alasan eksplisit sebagai download
berkas existing/upload/template statis. Ekspor CSV integritas dan SIMAN juga
masuk admission. Pemeriksaan ini melengkapi kontrak, bukan pengukuran semua
ukuran laporan. Kedua flag tetap default mati sampai staging VPS membuktikan
kapasitas dan konfigurasi bersama yang sama.

## Drain, rollback, dan pemulihan

Untuk mematikan renderer baru: hentikan admission baru (flag durable XLSX pada
API), biarkan worker menyelesaikan queue, verifikasi tidak ada queued/running
protokol `export_v1`, lalu hentikan worker. Budget global boleh tetap aktif untuk
renderer legacy. Jangan drop job/artifact atau menghapus lockfile saat process
masih hidup. Rollback schema additive mempertahankan pembacaan status/unduh.

Job aktif pada proses yang diketahui mati dapat dipulihkan worker. Ketika tidak
ada bukti positif proses sudah berhenti, pertahankan lease/lock dan ikuti prosedur
operator restore; jangan menghapus semua writer lease berdasarkan usia. Untuk
mengubah cap/direktori: drain, stop **semua** API/worker, periksa tidak ada renderer
hidup, ubah konfigurasi bersama, lalu mulai ulang. Menghapus file lock yang sedang
dibuka dapat menciptakan dua inode dan merusak hard cap.
