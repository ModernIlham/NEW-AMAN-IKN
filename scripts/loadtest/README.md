# Uji beban AMAN

Wajib memakai loopback atau hostname staging yang disebut persis dalam
`AMAN_STAGING_HOSTS`. Domain produksi `amanikn-inventarisasi.com` beserta seluruh
subdomain ditolak sebelum request. Harness ini menguji layanan yang benar-benar
berisi dataset; menghasilkan NDJSON saja tidak dianggap seed server.

## Install dan smoke mandiri

```bash
.venv/bin/pip install -r scripts/loadtest/requirements.txt
.venv/bin/python scripts/loadtest/run.py --dry-run --output /tmp/aman-smoke/hasil
```

Locust dipin `2.37.14`. Dry-run menjalankan API fixture HTTP loopback nyata,
memeriksa list/statistik/analitik/snapshot dengan activity_id, memvalidasi file
CSV, menjalankan Locust 1 pengguna selama 3 detik, serta menilai statistik akhir.
Tidak ada `|| true`, target port mati, atau galat yang dijadikan sukses. Ini
pemeriksaan harness dan kontrak, bukan angka kapasitas aplikasi AMAN.

## Seed Mongo lokal terisolasi

CLI menolak Mongo eksternal dan nama database selain `aman_ci_*`. Ia juga
menolak database berisi data dan output yang sudah ada. Tidak membaca `.env`
produksi. Setiap run memiliki 3 satker, 5 kegiatan, distribusi sparse/sort ties,
10% foto PNG kecil inline dan 20% checklist berfoto, serta pool akun sintetis
password bcrypt. Token sementara dan JWT secret acak hanya ditulis pada berkas
privat mode0600 sehingga throughput tidak didominasi login/rate limiter per IP.
Profil media kecil ini harus dilaporkan; tidak mewakili foto produksi berukuran
besar. Dependency CLI berasal dari environment backend.

```bash
AMAN_LOADTEST_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python scripts/loadtest/seed.py seed \
  --database aman_ci_load_00123456 --count 10000 --accounts 10 \
  --manifest /tmp/aman-load-00123456/manifest.json \
  --accounts-file /tmp/aman-load-00123456/accounts.json \
  --runtime-env-file /tmp/aman-load-00123456/runtime.env
```

Jalankan instance backend lokal terpisah dengan MONGO_URL/DB_NAME/JWT_SECRET
pada runtime.env tersebut, port terpisah, dan Redis DB terpisah bila dipakai.
Jangan menyalin `.env` produksi. Seed harus dilakukan sebelum instance tersebut
mengisi koleksi; startup normal membuat indeks aplikasi setelah seed.

```bash
AMAN_ACCOUNTS_FILE=/tmp/aman-load-00123456/accounts.json \
AMAN_DATASET_MANIFEST=/tmp/aman-load-00123456/manifest.json \
AMAN_LOADTEST_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python scripts/loadtest/run.py --host http://127.0.0.1:8002 \
  --users 10 --spawn-rate 1 --run-time 5m --profile read \
  --output /tmp/aman-load-00123456/read
```

Preflight memeriksa count list dan statistik per akun, scope kegiatan, seluruh
halaman snapshot dengan cursor unik, dan jumlah aset server sesuai manifest.
Respons 401/422, schema salah, dataset kosong, atau snapshot parsial menggagalkan
run. Pool minimal sebanyak pengguna, username unik; tokens tidak tercatat pada
artifact. Preflight memanaskan sebagian jalur: label cold memerlukan restart
instance sebelum run dan observasi preflight terpisah; label saja tidak
menghapus cache.

## Profil dan guard

- `read`: list dua halaman, statistik, analitik, snapshot scoped activity.
- `crud`: tambah/read/delete hanya aset milik virtual user dengan marker run.
  Wajib `AMAN_ENABLE_CRUD=1`; postflight memastikan count kembali ke baseline.
  Cleanup pada interupsi tersedia melalui seed CLI, selalu berdasar run ID.
- `heavy`: memanggil `/api/export/csv` sungguhan, memvalidasi header CSV, jumlah
  baris preflight, status/content type dan batas artifact64MiB. Bukan parameter
  `heavy=1` pada analitik. File dibaca secara berbatas.
- `--enable-job` ditambah `AMAN_ENABLE_JOB=1`: preflight membuat job CSV melalui
  Pusat Unduhan, memantau hingga done, memvalidasi artifact hasil, lalu menghapus
  job/artifact selesai. Job aktif yang timeout dilaporkan gagal dan tidak dibatalkan
  paksa; operator harus menunggu/menyelidiki sebelum cleanup.
- `auth`: workload login/rate limiter terpisah. HTTP429 dengan schema limiter yang
  valid dihitung sebagai respons limiter yang diharapkan, dicatat pada
  `status_counts`, dan hasilnya tidak boleh disebut kapasitas throughput.

Batas: 1..50 pengguna, spawn0.1..10/detik, 3detik..30menit, pool maksimal100,
seed10..100.000 aset. Mulai1000/10.000 aset; ramp10→25→50, masing-masing smoke5m
lalu stabil15m. Soak30m dan50k/100k hanya sesudah tingkat sebelumnya sehat.
Harness menghentikan run bila request gagal≥1% setelah20 request, disk lokal
free<20%, CPU lokal>85% selama2menit, atau batas wall-clock terlampaui. Hasil
akhir gagal bila failure ratio≥1% atau p95>2000ms (boleh diperketat).

Set `AMAN_TARGET_PID` hanya untuk PID server lokal agar RSS proses server dan
anaknya tercatat; RSS client tidak diklaim sebagai RSS server. Observasi CPU/IO/
RSS remote, OOM, browser request count, WebSocket dan replay offline perlu
pengukur terpisah. API harness tidak mengaku sudah mengukurnya. Set
`AMAN_LOADTEST_MONGO_URL` loopback untuk explain examined/returned, jumlah indeks,
dan antrean job dari database manifest. Metadata mencatat SHA sumber, toolchain,
dataset, seed, profil, akun, request/route, p50/p95/p99, status dan resource.
Statistik final `*.final.json` diambil setelah user berhenti; CSV periodik Locust
bisa tertinggal dari request terakhir dan bukan sumber count akhir.

## Workflow manual

`Load Test (manual)` kosong host menjalankan smoke fixture. Untuk staging nyata,
admin mengisi vars `LOADTEST_STAGING_HOSTS`, vars `LOADTEST_MANIFEST_JSON`, serta
secret `LOADTEST_ACCOUNTS_JSON` (pool schema sama dengan output seed, untuk akun
staging). Input host tidak dapat menambah allowlist. Secret `LOADTEST_USERNAME`
dan `LOADTEST_PASSWORD` tetap tidak memiliki nilai bawaan. Semua input dipindahkan
melalui environment; tidak disisipkan ke kode shell. Workflow tidak melakukan
seed DB remote atau menebak kredensial.

## Cleanup run

```bash
AMAN_LOADTEST_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python scripts/loadtest/seed.py cleanup \
  --database aman_ci_load_00123456 \
  --manifest /tmp/aman-load-00123456/manifest.json
```

Cleanup memverifikasi marker run/database, menolak job aktif milik akun run,
lalu hanya menghapus aset/kegiatan/satker/akun/audit milik run. Database tidak
di-drop, data lain tidak dihapus. Berkas akun/runtime.env privat dapat dihapus
operator setelah run tidak lagi diperlukan; jangan diunggah sebagai artifact.
