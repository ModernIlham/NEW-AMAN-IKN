# Identitas rilis worker dan frontend — OPT-25

15 Oktober 2026. Layout produksi tetap checkout lama. Field additive
`release_sha` pada `/health` dan `/api/health` ditangkap sekali saat import
`release_info.py`, bukan membaca Git setiap request. Worker lama tetap
melaporkan SHA lamanya meski checkout sudah berpindah.

Urutan sumber: manifest immutable yang cocok dengan nama direktori SHA,
`git rev-parse HEAD` 40 digit saat import, lalu hint `AMAN_RELEASE_SHA` valid
hanya bila tidak ada repository/manifest. Hint environment tidak dapat
menimpa identitas Git yang diketahui. Identitas yang tidak diketahui bernilai
null; deploy menolaknya. Tidak ada perubahan env privat atau query Git pada
jalur request. Snapshot observability memakai konstanta identitas yang sama,
termasuk saat runtime memakai direktori immutable tanpa Git.

`deploy_vps.sh` membandingkan health worker dengan DEPLOY_SHA sebelum build dan
sesudah aktivasi. Build menerima `REACT_APP_RELEASE_SHA` hanya pada command
build; `build.new/aman-release.json.source_sha` wajib identik sebelum aktivasi.
Respons HTTP200 dengan worker lama, SHA hilang, metadata frontend hilang/stale,
atau rollback worker yang salah SHA menyebabkan kegagalan. SHA frontend
diverifikasi dari file publik yang akan dilayani docroot; ini tidak mengklaim
nginx/CDN seluruh klien sudah menyajikan versi baru tanpa pengujian HTTP terpisah.

Pada rollout pertama, bila source sebelum deploy belum memiliki release_info,
rollback memakai pemeriksaan Git/docroot/dependency/restart dan kedua health
lama. Batas transisi ini eksplisit karena health lama belum mengeluarkan SHA.
Rollback setelah rilis mendukung identitas wajib membuktikan SHA worker lama;
kegagalan mempertahankan mutex dan status RECOVERY_REQUIRED. Deploy manual
menuju rilis lama tanpa kontrak metadata/SHA baru akan gagal validasi; gunakan
prosedur pemulihan rilis legacy yang diverifikasi operator jika diperlukan.

## Bukti

- 13 unit test release_info/artifact staging lulus dalam 10,91 detik. Test menangkap identitas import, immutable manifest mismatch, hint env
  dan unknown source. Proses yang sudah mengimpor A tetap A setelah commit B;
  proses baru mendapat B.
- 113 tes shell deployment/env/sintaks/fault injection lulus dalam 187,52 detik.
  Termasuk worker SHA hilang/stale, frontend SHA hilang/stale, serta rollback
  dengan worker salah yang tidak mengumumkan sukses.
- Kontrak full AMAN nyata lulus dalam 19,45 detik: dua proses uvicorn server:app
  pada port loopback ephemeral, startup/deep health dengan Mongo sementara.
  Worker A melaporkan A pada kedua endpoint sebelum dan sesudah checkout B;
  worker B melaporkan B walaupun environment memuat hint SHA stale. Byte/mode
  `.env` fixture tetap, proses dan database fixture dibersihkan.
- Artifact staging kini mewajibkan metadata frontend source SHA cocok,
  memeriksa dirty public/plugin/scripts, serta menjalankan consumer immutable
  dengan bytecode cache di luar artifact (`PYTHONDONTWRITEBYTECODE=1`).

```bash
.venv/bin/python -m pytest -q \
  backend/tests/unit/test_release_info.py \
  backend/tests/unit/test_release_artifact_staging.py

AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python -m pytest -q -m integration \
  backend/tests/contract/test_release_health.py
```

Ini membuktikan identitas worker AMAN dan mekanisme staging. Cutover layout
immutable supervisor/nginx, seluruh kompatibilitas klien/API, queued offline
writes, serta operational rollback produksi tetap gate OPT-21/25 terpisah.
