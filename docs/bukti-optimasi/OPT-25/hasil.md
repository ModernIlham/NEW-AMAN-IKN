# OPT-25 — Bukti staging layout immutable (parsial)

15 Oktober 2026 (WITA). Produksi tidak dipindahkan ke layout baru oleh paket ini.

`scripts/releases/manager.py` kini memiliki consumer staging executable yang
membuat artefak source SHA bersih + frontend build CI, memverifikasi digest
trusted/per-file/font/requirements/publicconfig, mengekstrak archive secara
berbatas dengan proteksi traversal/link/device/duplicate, dan menyiapkan rilis
immutable. Pointer current/previous ditukar atomik, dependency disiapkan di luar
rilis aktif, health pasangan diverifikasi, kegagalan dikompensasi, serta kegagalan
rollback dipertahankan sebagai RECOVERY_REQUIRED yang memblokir aktivasi baru.

Test `backend/tests/unit/test_release_artifact_staging.py` memakai Git sementara,
dua artefak, dua venv terpisah dengan wheel lokal yang benar-benar dipasang,
proses HTTP nyata, dan health yang memuat SHA+versi dependency. HTML/manifest dan
chunk diverifikasi lewat HTTP. Dua rilis serta rollback, failure saat prepare,
health, checksum/source/chunk, interupsi, dan kegagalan rollback tercakup. Health
consumer memakai release_info yang menangkap manifest immutable saat import;
hint env stale tidak dapat menimpanya. SHA frontend publik wajib cocok dengan
artifact; dirty public/plugin/scripts dan metadata hilang/stale ditolak. Env
privat tidak ikut artifact, byte/mode tetap. Consumer fixture mempertahankan
lazy chunk lama dari rilis yang masih tersedia.

```bash
.venv/bin/python -m pytest -q backend/tests/unit/test_release_artifact_staging.py
```

Batas: callback HTTP fixture bukan backend FastAPI AMAN lengkap. Belum ada
perubahan supervisor/nginx/CI artifact publishing, port produksi, atau service
worker. Actual app health release SHA sudah dibuktikan terpisah pada dua proses
AMAN nyata (lihat release-health.md). Compat N/N+1, queued writes dan dua siklus
website nyata di staging masih menjadi gate cutover. Root staging sengaja
menolak `/var/www`. Lihat scripts/releases/README.md untuk adapter dan langkah
integrasi yang konkret. Jangan mengubah status seluruh OPT-25 menjadi selesai
hanya karena harness mekanisme staging lulus.
