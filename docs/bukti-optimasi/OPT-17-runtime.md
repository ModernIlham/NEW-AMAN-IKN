# OPT-17b — Observabilitas runtime ringan

15 Oktober 2026 (WITA). Collector memakai pustaka standar, tanpa stack baru dan
**default mati** sampai overhead pada baseline AMAN diukur <5% CPU. Aktifkan
`AMAN_OBSERVABILITY_ENABLED=1` lalu restart worker; rollback: ubah0 dan restart.

`GET /api/system/observability` hanya menerima super-admin pusat karena angka
mencakup trafik seluruh satker. Snapshot selalu menyebut scope process/PID,
bukan agregat seluruh worker atau seluruh VPS. Tidak ada sinkronisasi Mongo,
TTL metrics baru, per-user label, raw path, query, search term, NIP, asset ID,
token, payload form, atau foto dalam dimensi collector.

Middleware ASGI tidak membaca/buffer body. Durasi mencakup akhir streaming.
Route berasal dari template route yang benar-benar cocok, sedangkan URL yang
tidak cocok menjadi satu bucket `<unmatched>`. Maksimal256 route keys ditambah
satu overflow; method dan status juga memiliki himpunan terbatas. Histogram
bucket5ms..30detik+overflow memakai5 bucket menit terakhir (resolusi60detik),
bukan array latency mentah. Percentile adalah batas atas bucket, bukan percentile
presisi. Counter internal mencatat waktu update observer untuk sampling overhead;
pembuktian overhead total tetap membutuhkan perbandingan CPU baseline on/off.

Collector tiap1detik mengukur scheduling event-loop lag, RSS terkini dari
`/proc/self/statm` (fallback ditandai peak), dan FD count. Probe tiap30detik,
anggaran3detik dan query maxTimeMS1detik, memeriksa Mongo/GridFS, optionalRedis,
indeks, maintenance/recovery, background_jobs/PusatUnduhan depth+age, disk, dan
umur backup otomatis terakhir sukses. Probe tidak menyimpan job ID atau data
backup. Error collector tidak diumumkan sebagai Redis/core error yang keliru;
status kegagalan probe dipisah dan nilai recovery yang terakhir diketahui tidak
dibuka hanya karena probe tak dapat dibaca.

Alert lokal melalui logger JSON lama memuat event/alert_name/alert_state/
severity/observed_value/process_id. Hysteresis default3 sampel gagal dan3 sampel
pulih; cooldown60detik per alert menggabungkan transisi berulang. Core dependency
critical dibedakan dari optionalRedis/index warning, maintenance informasional,
recovery critical, disk warning/critical, backup stale, queue age, loop lag,
HTTP5xx/error ratio, serta p95 tinggi. Tidak ada pesan eksternal dikirim.

Defaults provisional yang dapat dikonfigurasi:

| Variable | Default |
| --- | --- |
| AMAN_SLO_ERROR_RATIO | 0.01; minimal100 request |
| AMAN_SLO_P95_MS | 2000; minimal100 request |
| AMAN_SLO_LOOP_LAG_MS | 200 |
| AMAN_SLO_QUEUE_AGE_SECONDS | 120 |
| AMAN_SLO_BACKUP_AGE_HOURS | 48; hanya saat backup otomatis aktif |
| AMAN_ALERT_FAILURE_SAMPLES / AMAN_ALERT_RECOVERY_SAMPLES | 3 / 3 |
| AMAN_ALERT_COOLDOWN_SECONDS | 60 |

Counter5xx mencakup503 maintenance; kategori probe maintenance tetap terpisah
sehingga operator dapat menilai penyebab, bukan menyimpulkan Mongo mati dari
rasio error saja. p95 agregat mencakup route berat; ini target awal, belum SLO
kontraktual. Jangan menggabungkan percentile antar-worker dengan penjumlahan.

Uji:

```bash
.venv/bin/python -m pytest -q \
  backend/tests/unit/test_runtime_observability.py \
  backend/tests/unit/test_log_setup.py

AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017/ \
AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
  .venv/bin/python -m pytest -q -m integration \
  backend/tests/contract/test_runtime_observability.py
```

Kontrak nyata membuktikan tanpa auth ditolak, admin satker403, pusat200;
30 URL dengan asset ID/NIP/query/token tetap satu template dan data tersebut
absen dari JSON. Mongo/Redis probe berjalan pada database kontrak terisolasi.
Kontrak kedua memasukkan job antrean lama yang sintetis, menurunkan ambang
fixture, memeriksa dua sampel sebelum alert aktif di endpoint dan log lokal,
lalu menghapus hanya job fixture dan mengambil probe Mongo sehat nyata sampai
recovery muncul di endpoint/log. Tidak memalsukan hasil probe sehat dan tidak
mengirim notifikasi eksternal. Kedua kontrak lulus (7,40 detik).
Unit menguji2000 path tak dikenal, bounded windows/overflow, streaming+exception,
hysteresis/dedup/recovery, optional warning vs core critical, sampling proses dan
pembatalan task. Fixture failure+recovery menghasilkan jenis alert yang berbeda.

Batas: penyebaran monitor eksternal, monitor ID/interval/pemilik operasional dan
uji notifikasi kanal pemilik belum dilakukan oleh collector lokal ini. DB pool
wait, cache hit/fallback dan trace browser tidak disimpulkan dari ping/RSS.
Inventaris VPS sebenarnya dicatat terpisah oleh workflow read-only. Seluruh
OPT-17 belum boleh dinyatakan tuntas hanya dari endpoint lokal yang lulus.

## Pengukuran overhead HTTP website nyata

Instance AMAN terpisah port18003/18004, masing-masing1worker, dataset sintetis
independen10.000aset pada Mongo loopback dan RedisDB11. Kedua instance memakai
kode sama, hanya flag collector0 vs1. Delapan ronde memakai urutanAB/BA
bergantian,400request/variant/ronde setelah warmup, total3200request per variant;
list/stats/analytics/snapshot memakai siklus tetap. CPU diambil dari jiffies
proses server, bukan CPU client. Akun operator fixture dihapus setelah kedua
proses berhenti; instance root18001/18002 tidak dihentikan. Percobaan terdahulu
pada dataset browser bersama dibatalkan saat count berubah; tidak dipakai.

Rata-rata CPU/request off20.684,4µs, on20.446,9µs; perbedaan rata-rata-1,15%.
Simpangan antar pasangan7,92% memperlihatkan noise sharedhost lebih besar dari
ambang5%; interval95% pasangan tercatat dalam OPT-17-overhead.json. **Angka
rata-rata tidak membuktikan overhead<5% dengan keyakinan yang memadai.** Flag
produksi tetap mati sampai ulang pada jendela representatif yang lebih tenang.
Snapshot portcollector-on menunjukkan sampling RSS/FD/loop aktif dan probe
Mongo/Redis sehat, dengan route template tanpa PII. Ini bukan klaim kapasitas
atau hasil soak15menit.

Setelah pengukuran, timeout eksplisit1detik ditambahkan pada dua probe core
untuk membedakan Mongo down dari timeout collector opsional; jalur sehat tetap
sama namun benchmark checksum mencatat versi tepat yang diukur sebelum pagar
failure-path tersebut. Tidak menganggap hasil ini sebagai izin aktivasi produksi.
Identitas SHA collector kemudian disatukan dengan konstanta release_info yang
ditangkap saat import, sehingga health dan snapshot memakai identitas sama
termasuk pada artifact immutable tanpa Git. Jalur per-request tidak berubah.
