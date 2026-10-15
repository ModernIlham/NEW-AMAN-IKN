# OPT-13 — Replay realtime dan rekonsiliasi

Implementasi backend 15 Oktober 2026: `event_bus.py`, handler WebSocket, tes unit
dan capped Mongo nyata. Frontend menangani kontrak `resync_required` pada paket
frontend yang digabungkan bersama perubahan ini.

## Perubahan

- Tidak ada `_id > last_id`, urutan timestamp, ataupun sequence yang dialokasikan
  terpisah. `_id` terakhir dalam `$natural` hanya token **kesetaraan** untuk
  menemukan kontinuitas. ID baru lebih kecil tetap diterima menurut urutan sisip.
- Ring capped tetap **1 MiB / 1.000 dokumen**. Dedup dibatasi **2.000 ID**, termasuk
  event worker sendiri. Event sendiri dipakai menjaga kontinuitas lalu dilewati
  pada delivery. UUID `_bus_event_id` ditambahkan ke envelope, dilucuti sebelum
  diteruskan; envelope lama tanpa UUID tetap berfungsi memakai kesetaraan `_id`.
- Kursor tailable yang masih alive dipertahankan melewati batch kosong sehingga
  memakai getMore/awaitData, bukan membentuk query ulang tiap batch. Kursor mati
  dan kursor alive yang cepat-kosong tetap dibatasi minimal100ms per putaran;
  maxAwaitTimeMS tetap2.000. Handler memiliki deadline15detik.
- Restart mengulang ring secara bounded dan mengabaikan ID yang sudah diproses.
  Posisi terpangkas/collection drop memicu resync. Handler gagal/terlalu lambat
  juga meminta rekonsiliasi. Publish gagal memberi invalidasi lokal dan marker
  pemulihan global sesudah Mongo menerima insert kembali (retry dibatasi).
- Rekonsiliasi periodik60detik mencakup crash publisher sesudah commit data
  sebelum event tersimpan; bus bukan durable outbox. Koneksi idle normal dapat
  menunggu getMore hingga2detik lagi sebelum tick periodik. Tidak menjanjikan
  seluruh notifikasi individual tersimpan selamanya: data API tetap otoritas.
- Jika capped collection tak tersedia, fallback mengirim invalidasi periodik
  tanpa menambah histori pada collection biasa yang tidak berbatas.

## Kontrak frontend dan scope

```json
{"type":"resync_required","reason":"ring_gap","timestamp":"2026-10-15T00:00:00+00:00"}
```

Alasan lain: `cursor_reconnected`, `publish_failed`, `periodic_reconcile`,
`handler_failed`, `event_bus_unavailable`. Tidak ada payload aset lintas satker.
Penanda internal room`*` dikembangkan **hanya** menjadi room lokal yang sudah
memiliki koneksi terautentikasi dan lolos otorisasi kegiatan/satker. Fanout room
dijalankan sejajar agar satu room lambat tidak menahan seluruh resync.
Event perubahan biasa mempertahankan exclude-sender. Frontend harus debounce,
memperbarui data/stats/locks konteks aktif, dan mempertahankan draft/seleksi.

## Bukti

Tes unit replay: ID turun di detik sama, restart/dedup, gap bootstrap, rollover,
set ID berbatas, loopback, publish gagal→marker pemulihan, handler lambat,
rekonsiliasi periodik, fallback, dan scope room. Tes throttling historis tetap
dijalankan; assertion lama yang mewajibkan `_id >` diganti kontrak kontinuitas
yang benar. Tes timeout WebSocket existing tetap lulus.

Empat tes capped Mongo nyata pada fixture localhost `aman_ci_*`:

1. Dua proses publisher dengan ObjectId eksplisit yang lebih kecil dalam detik
   sama: seluruh4event diterima tepat sekali pada pengamatan tersebut.
2. Kursor nyata ditutup lalu dibuat ulang: replay tanpa duplikat, event berikutnya
   tetap diterima.
3. Handler ditahan sementara ring5slot digulung38insert: menerima resync eksplisit.
4. Idle0,6detik mempertahankan satu kursor, tanpa query find berulang.

[idle.json](idle.json): probe lokal ring1.000dokumen selama2,5045detik,
**1find + 1anchor read**, **0,023detik CPU proses Python**. Pengukuran ini bukan
benchmark kapasitas VPS atau pengukuran CPU mongod; ia membuktikan jalur idle
memakai satu kursor dan tidak menghidupkan busy-loop lama.

```bash
.venv/bin/python -m pytest backend/tests/unit/test_event_bus_tak_berputar.py backend/tests/unit/test_event_bus_replay.py backend/tests/unit/test_broadcast_ws_berbatas_waktu.py -q
AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 .venv/bin/python -m pytest -m integration backend/tests/contract/test_event_bus.py -q
```

Hasil: **47 unit terfokus lulus, 4 kontrak Mongo nyata lulus**.

## Rollback

`AMAN_EVENT_BUS_MODE=natural` adalah default. `AMAN_EVENT_BUS_MODE=reconcile`
menonaktifkan tail baru dan memakai invalidasi periodik aman; ring/envelope tetap
dipertahankan, tidak menghidupkan asumsi ObjectId lama. Nilai tidak dikenal juga
memakai fallback. Aktifkan flag lewat konfigurasi+runtimes restart sesuai jalur
deploy normal. Jangan rollback frontend ke versi yang mengabaikan resync ketika
flag reconcile dipakai.

## Frontend: resync terikat koneksi dan kegiatan

`useWebSocket` menerima `resync_required` dan menggabungkan burst selama 200 ms.
Reconnect juga memicu catch-up. Setiap callback memeriksa koneksi+scope aktif;
message/close dari koneksi kegiatan sebelumnya ditolak, dan unmount membatalkan
resync tertunda. Dashboard meneruskan ke refresh assets/stats yang sudah ber-
debounce 2 detik dan menunda saat form sedang diedit, serta menyegarkan lock
segera melalui read bertiket/AbortSignal. Draf batch, seleksi dan jangkar tidak
direset. Polling lock juga menolak respons aktivitas lama.

Tes frontend `useWebSocket.test.jsx` dan `useRowLocking.test.jsx`: **2 suite /
3 tes lulus**, log `/tmp/aman-ws-frontend-tests.log`.

## Regresi pembatalan Python 3.11 setelah pengujian gabungan

Full contract mengungkap race saat handler selesai pada tick yang sama dengan
pembatalan task tail. asyncio.wait_for pada Python 3.11.17 dapat mengembalikan
hasil child dan menelan pembatalan parent; task tetap hidup dengan
cancelling()==1. Reproducer deterministik membuktikan kondisi lama
cancelled=False dan kondisi baru cancelled=True pada [cancellation-race.json](cancellation-race.json).
Delivery kini memakai asyncio.timeout dan direct await, sehingga sinyal
pembatalan tetap milik task tail. Cursor close memiliki deadline lima detik.
Stop pada test memakai shield serta deadline delapan detik agar pembatalan yang
tertelan menjadi kegagalan terbatas, bukan menggantung seluruh suite.

Sesudah perbaikan:25 unit event-bus lulus5,09detik; empat kontrak Mongo nyata
lulus11,23detik pada final security runtime Python3.11.17.
