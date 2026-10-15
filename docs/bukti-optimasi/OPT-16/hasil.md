# OPT-16 — Harness beban dengan dataset server yang terbukti

Tanggal: 15 Oktober 2026 (WITA). Tidak ada beban yang diarahkan ke produksi.

## Perbaikan

- `scripts/loadtest/run.py` menjadi entrypoint dengan allowlist origin: loopback
  atau hostname staging eksplisit. Domain produksi beserta subdomain tetap
  ditolak sekalipun salah dimasukkan ke allowlist. Credentials dalam URL,
  path/query, HTTP eksternal, port salah, users/ramp/durasi tak berbatas ditolak.
- Seed CLI benar-benar memasukkan data ke Mongo loopback database `aman_ci_*`
  kosong, menghitung hasil, menyiapkan 3 satker/5 kegiatan/sparse/sort ties/media
  kecil, akun password bcrypt dan token sementara. Berkas akun/runtime.env mode
  0600, JWT acak; manifest tidak berisi password/token. Preissued token menghindari
  pembatas login per IP mendominasi hasil throughput.
- Preflight setiap akun memastikan count list/statistik server sama dengan
  manifest, scope kegiatan benar, seluruh halaman snapshot selesai tanpa
  duplikasi/kehilangan. Snapshot selalu mengirim `activity_id`. Dataset NDJSON
  lokal tidak dipakai untuk menyimpulkan data server sudah ada.
- Heavy benar-benar mengunduh `/api/export/csv`, memeriksa content type, header,
  baris, dan batas64MiB; opsi job membuat job CSV nyata, menunggu hasil, memeriksa
  file, menghapus artifact selesai. Status401/422 atau file parsial gagal.
- Profil read, CRUD, heavy, auth dipisah. CRUD/job memerlukan flag eksplisit;
  CRUD menghapus hanya ID milik virtual user dan postflight memverifikasi count
  awal. Auth mengukur limiter dengan429 valid tercatat sebagai limiter yang
  diharapkan, bukan klaim kapasitas throughput. Cleanup seed hanya data run ID;
  tes sentinel membuktikan dokumen lain dipertahankan.
- Locust dipin2.37.14. Dry-run menjalankan API fixture HTTP sungguhan + Locust,
  bukan port mati/galat yang ditelan. Workflow memakai environment untuk input,
  administrator host allowlist, private pool secret dan manifest yang benar.
- Statistik final dikumpulkan pada `test_stop`, karena CSV periodik Locust bisa
  tertinggal dari request terakhir. Summary JSON berisi SHA, toolchain, dataset,
  request/route/status, p50/p95/p99, RPS, resource samples dan batas bukti. Token
  dan password tidak dimasukkan ke log/statistik/summary/artifact workflow.

## Perintah dan hasil

```bash
.venv/bin/python -m pytest -q \
  backend/tests/unit/test_loadtest_harness.py \
  backend/tests/unit/test_kredensial_bawaan.py

AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python -m pytest -q -m integration \
  backend/tests/contract/test_loadtest_seed.py

.venv/bin/python scripts/loadtest/run.py --dry-run \
  --output /workspace/.aman/loadtest-smoke/hasil-final
```

- Unit guard/kontrak/workflow dan credential regression: **46 lulus**.
- Seed/cleanup Mongo nyata: **1 lulus**, 20 aset,3 satker,5 kegiatan,2 akun;
  count/izin/hash password diperiksa, data sentinel run lain tetap ada.
- Smoke API fixture + Locust3detik: **32 request,0 kegagalan,p95=8ms**, seluruh
  endpoint list/statistik/analitik/snapshot/CSV diverifikasi preflight. Angka ini
  mengukur fixture pengujian harness, **bukan kinerja website AMAN**.
- Compile Python, pemeriksaan diff dan scanner rahasia lulus untuk perubahan ini.

Baseline website nyata10k menjadi run terpisah pada instance backend lokal
terisolasi. Detail akun/runtime.env privat tidak ikut bukti publik. Lampirkan
summary JSON yang sudah disanitasi dan profil infra setelah run tersebut;
hasil fixture di atas tidak menggantikannya.

## Ambang dan batas bukti

Run dibatasi1..50users,0.1..10spawn/detik,3detik..30menit, maksimal100akun dan
seed100k. Error≥1% setelah20request menghentikan run. Summary gagal untuk error
akhir≥1% atau p95>2000ms. Disk lokal free<20%,CPU lokal>85% selama2menit, serta
wall-clock melewati durasi+90detik menghentikan client. Awal ramp yang disarankan
10→25→50, smoke5m lalu stabil15m per tingkat, soak30m hanya setelah sehat.

`AMAN_TARGET_PID` mengukur RSS backend lokal dan child process; RSS client tidak
dianggap RSS server. Mongo evidence opsional hanya dari URL loopback eksplisit,
memuat explain examined/returned dan jumlah job aktif. Server remote memerlukan
observer infra terpisah. Browser request count, WS/reconnect, replay offline,
OOM kernel, dan beban foto berukuran produksi bukan klaim harness API ini.
Cold cache memerlukan restart/observasi terpisah; label metadata tidak menghapus
cache. Tidak ada klaim kapasitas sampai ramp/soak pada infra representatif dan
profil media yang sesuai selesai.

Generator memakai `asset_options.py` murni yang dire-export oleh shared_utils;
import generator tidak lagi menginisialisasi DB/Redis/limiter. Tes subprocess
memverifikasi modul runtime tidak dimuat, bukan menyembunyikan warning shutdown.

Fixture normal/mixed memakai kode aset numerik10digit dan kode register32hex
valid, serta membuat kategori referensi yang dipakai aset. Profil edge tetap
memiliki anomali disengaja. Cleanup kategori milik run hanya menghapus kategori
yang tidak dirujuk aset lain; ini memungkinkan smoke form browser memakai
fixture yang lolos validasi UI, bukan seluruh fixture berkode invalid.

## Satu soak akhir 15 menit — 15 Oktober 2026, UTC

[final-soak.json](final-soak.json) mencatat **1.952 request, nol kegagalan dan
nol transport error**, p50 47 ms, **p95 320 ms**, p99 810 ms, maksimum
1.426,9 ms. Locust dan wrapper keluar dengan kode 0. Pengujian memakai backend
lokal terisolasi, 10.000 aset, lima kegiatan/akun, lima pengguna bersamaan,
profil read, satu worker Uvicorn, keepalive bawaan 5 detik, think time 1–3
detik, serta stop timeout 35 detik. Tidak ada retry request atau perubahan
source, runtime, profil, konfigurasi maupun ambang selama run.

Source yang diuji adalah snapshot validasi immutable
`7601d14a356c897a669324fd167f68cb9442326b`, **bukan SHA rilis main**.
Seluruh 243 berkas runtime dalam fingerprint diverifikasi ulang terhadap
snapshot; digest backend tetap sama selama pengujian. Helper wrapper lama
menamai field `git_sha` dengan HEAD checkout aktif saat itu; artifact final
membedakannya dari SHA snapshot yang benar. Runtime Python 3.11.17 memakai
137 distribusi runtime dan tiga tool bootstrap aman; harness tetap Locust
2.37.14 dengan hash empat berkas yang sama seperti run sebelumnya.

Deep health akhir 200, jumlah aset tetap 10.000, kelima akun sintetis terhapus
dan tidak ada akun uji tersisa. Proses server milik run sudah berhenti. Median
RSS server tiga menit awal 165,16 MB dan tiga menit akhir 167,35 MB; maksimum
27 file descriptor. Ini sampel durabilitas pada host bersama, bukan bukti
ketiadaan kebocoran untuk durasi tak terbatas.

Riwayat baseline/candidate yang gagal tetap dipertahankan. Khusus run
`durability-a977d22aa9064f2fadd420887e707556`, **1 dari 1.883 request gagal**
dengan `ConnectionResetError(errno=104)` dan tetap berstatus gagal. Satu
sampel akhir yang lulus tidak membuktikan race TCP sebelumnya telah hilang.
Tidak ada klaim sertifikasi kapasitas produksi; ramp dan soak pada staging
representatif, media nyata, concurrency lebih tinggi serta alur lain tetap
menjadi prasyarat klaim kapasitas.
