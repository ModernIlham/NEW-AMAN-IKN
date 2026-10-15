# OPT-00 — Kontrak layanan nyata

Status: PR00a siap review; kelanjutan multiworker/browser belum ditutup.

Fixture baru hanya menerima URL loopback eksplisit dan membuat database
`aman_ci_<uuid>`. Ia tidak memakai DB_NAME/MONGO_URL aplikasi, tidak flush Redis,
dan hanya menghapus database yang dibuat sendiri. Semua API menjalankan handler,
middleware dan dependency asli melalui ASGI. Tidak ada dependency override auth.

Perintah lokal:

```bash
AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 \
AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
.venv/bin/python -m pytest -m integration backend/tests/contract/test_core.py -q
```

Mongo7.0.30 lokal, Redis7.4.2 terisolasi (container localhost16379), Python3.12.14.
Hasil awal: **5 lulus dalam6,68detik**. Kontrak menguji bootstrap/login/anonim,
create idempotent, stale If-Match409, scope dua satker, unique index dan dua
CAS bersamaan, GridFS roundtrip/chunk delete, serta generasi cache Redis.

CI menambahkan job mandiri dengan Mongo7.0.30+Redis7.4.2. Default unit bebas infra
tetap terpisah. Suite historis live tidak diaktifkan. Kegagalan dependency/index/
kontrak membuat job gagal, tidak memakai continue-on-error.

Tahap berikutnya: kontrak batch/unduhan/recovery dari paket masing-masing;
dua proses sungguhan, lifecycle browser production-build, dan failure artifacts.
Baseline ini belum menyatakan kapasitas produksi atau semua OPT-00 selesai.
