# Artefak dan layout rilis — staging OPT-25

`manager.py` membuat/memeriksa artefak dari SHA source yang tepat dan menyiapkan
layout staging terisolasi. **Produksi tetap memakai deploy_vps.sh** sampai
konfigurasi supervisor/nginx, kompatibilitas klien lama, dan dua siklus rilis
website AMAN pada layout baru terbukti. Skrip tidak memasang trap produksi,
menjalankan SSH, atau mengubah service VPS.

## Package dan stage

Gunakan checkout CI bersih dengan production build yang sudah dihasilkan CI
tersebut, dengan `REACT_APP_RELEASE_SHA` diset ke SHA tersebut saat build.
`aman-release.json.source_sha` wajib cocok; metadata hilang atau stale ditolak.
Source runtime/backend/plugin dirty/untracked, SHA tidak cocok, chunk yang hilang,
symlink, serta config frontend di luar allowlist ditolak. Snapshot `.env` atau
venv tidak dimasukkan ke artefak. Public config JSON hanya menerima
REACT_APP_BACKEND_URL, REACT_APP_VERSION, PUBLIC_URL.

```bash
AMAN_BUILD_NODE_VERSION=22.x AMAN_BUILD_YARN_VERSION=1.22.22 \
  python scripts/releases/manager.py package \
  --repo /path/checkout-ci-bersih \
  --frontend-build /path/checkout-ci-bersih/frontend/build \
  --sha SHA_LENGKAP_YANG_LULUS_CI \
  --public-config /tmp/frontend-public-config.json \
  --output /tmp/rilis-aman.tar.gz

python scripts/releases/manager.py stage \
  --root /tmp/aman-release-staging-001 \
  --artifact /tmp/rilis-aman.tar.gz \
  --sha SHA_LENGKAP_YANG_LULUS_CI \
  --artifact-sha256 DIGEST_ARTEFAK_DARI_RUN_CI_YANG_DIPERCAYA
```

Output package mencatat SHA artefak. Digest yang diberikan ke stage harus berasal
dari hasil CI yang dipercaya; menghitung ulang artefak yang tidak dipercaya
bukan bukti provenance. Manifest memuat SHA source, hash/bytes setiap file,
requirements, font, entrypoints, public-config fingerprint dan toolchain yang
tersedia, serta frontend source SHA. node/yarn yang tidak diberikan dicatat `not_supplied`, bukan ditebak.
Stream hashing/copy berbatas1MiB/64KiB, maksimal30.000file/512MiB dan manifest8MiB.

Layout:

```text
root-staging/
  releases/<sha>/backend/...
  releases/<sha>/frontend/build/...
  releases/<sha>/release-manifest.json
  envs/<sha>/...                 # dependency state terpisah, di luar artefak
  shared/backend.env            # privat; tidak dimasukkan artefak
  current -> releases/<sha>
  previous -> releases/<sha-sebelumnya>
```

Stage hanya menerima root privat milik pengguna pada `/tmp/aman-release-*` atau
`/workspace/.aman/release-staging-*`. `/var/www` ditolak. Archive path traversal,
symlink/hardlink/device, nama duplicate, checksum salah, dan SHA mismatch ditolak
sebelum pointer diubah. SHA yang sama tidak boleh diisi artefak berbeda.

API Python `activate(root, sha, prepare, restart, health)` adalah adapter staging,
dipakai executable test. Ia mempersiapkan dependency terisolasi sebelum pointer,
menukar pointer `current` dengan `os.replace`, restart instance staging, lalu
memvalidasi pasangan frontend/API. Callback health wajib membuktikan SHA API,
dependency, HTML/manifest/chunk. Kegagalan kembali ke pointer/process sebelumnya
dan baru menyatakan pulih setelah health berhasil. Rollback gagal menulis
RECOVERY_REQUIRED.json dan memblokir aktivasi berikutnya. Callbacks berupa fungsi
Python, bukan input shell/command arbitrer.

Instance dari direktori immutable wajib dijalankan dengan
`PYTHONDONTWRITEBYTECODE=1` atau `python -B`; alternatif cache bytecode memakai
`PYTHONPYCACHEPREFIX` di direktori runtime terpisah. Import module tidak boleh
menambah `__pycache__` di artifact karena verifikasi set file saat rollback akan
menolak perubahan tersebut. Upload, log, backup, dan env tetap di shared/runtime.

## Bukti executable

```bash
.venv/bin/python -m pytest -q backend/tests/unit/test_release_artifact_staging.py
```

Fixture membuat repository Git dua rilis, artefak, dua venv Python terpisah,
memasang wheel dependency lokal nyata tanpa network, dan menyalakan proses HTTP
nyata dari rilis yang dipilih. Test memeriksa health SHA/dependency, HTML dan
chunk; perpindahanA→B→A, aktivasiB gagal→A pulih, private env tetap, dan chunk lama
masih dilayani consumer fixture dari rilis yang dipertahankan. Kasus dependency,
checksum/source/chunk hilang, path traversal, interupsi dan rollback gagal juga
diuji. HTTP consumer ini fixture staging dan bukan seluruh aplikasi AMAN.

## Sebelum cutover produksi

Integrasi CI masih harus mengunggah artifact trusted untuk SHA yang sama dengan
main CI; deploy harus memverifikasi digest, main ancestry, anti-downgrade, dan
mutex restore. Persiapan venv penuh mengikuti requirements release sebelum
aktivasi. Supervisor/nginx perlu konfigurasi path/current, health release SHA,
dan fallback lazy chunks sesuai grace period. Perlindungan env privat harus
memakai mekanisme snapshot teruji OPT-08; jangan menyalin env ke artifact.

Kompatibilitas N-client→N+1-API, N+1→N rollback, service worker, antrean offline,
serta queued jobs pada **website AMAN nyata** wajib dibuktikan. Hasil fixture
membuktikan mekanisme staging, bukan izin otomatis mengganti layout produksi,
zero downtime, atau penyelesaian seluruh OPT-25.
