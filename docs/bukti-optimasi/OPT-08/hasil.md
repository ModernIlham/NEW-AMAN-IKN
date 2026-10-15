# OPT-08 — Pemulihan deploy sesuai fase

Tanggal pengujian: 15 Oktober 2026 (WITA). Hasil ini berasal dari checkout
pengembangan dan Mongo loopback sementara; tidak menyatakan fault injection
pernah dijalankan pada produksi.

## Perubahan

`scripts/deploy_vps.sh` memakai EXIT handler tunggal yang menggabungkan
kompensasi deploy dengan helper snapshot `.env` privat yang juga dipakai
`update-all.sh`. Fase tercatat meliputi reset kode, pemulihan env, dependency
backend, restart, health, dependency frontend, build, aktivasi, dan pemeriksaan
akhir. Kegagalan setelah reset, termasuk HUP/INT/TERM, kembali ke SHA awal,
memasang env semula, memasang requirements awal bila sempat tersentuh,
mengembalikan docroot yang benar, restart, lalu memeriksa health dangkal dan
dalam. Status awal gagal tetap diteruskan setelah rollback sehat. Rollback yang
tidak terverifikasi mengembalikan exit 70, mencetak `RECOVERY_REQUIRED`, serta
mempertahankan mutex untuk pemeriksaan operator; tidak mencetak sukses palsu.

Flag rename dipasang sebelum operasi sehingga interupsi sesudah rename tidak
meninggalkan perkiraan lokasi build yang keliru. `build.old` pada rilis sukses
berisi frontend tepat sebelum rilis tersebut. Output tanpa `build.new/index.html`
ditolak. PATH/SHA/config produksi tidak diubah oleh harness.

`restore_control` `_id=GLOBAL` menjadi mutex atomik bersama restore. Deploy
mengklaim state `deploying` dengan token owner unik hanya dari dokumen absen
atau state terminal `completed`, `rolled_back`, `aborted`. Semua state aktif,
unknown state, dan `recovery_required` memblokir deploy tanpa bergantung pada
heartbeat/TTL/job yang sudah hilang. Pelepasan memakai token owner yang sama.
Pemeriksa Mongo gagal tertutup; Python dari venv aplikasi dipakai dengan
pymongo/dotenv, dengan fallback mongosh. Pesan exception Mongo tidak dicetak
karena bisa mengandung kredensial. Legacy job restore segar tetap diperiksa.

Sesudah mengklaim mutex, deploy menolak restart bila `restore_write_leases`
belum kosong, unduhan masih `queued`/`running`, atau background_jobs nonterminal
(import/spasial/ekspor terlepas dari request) belum selesai. Query drain memiliki
maxTimeMS5detik dan timeout driver5detik; timeout menolak deploy. Writer/admission backend
baru memeriksa mutex ini sehingga permintaan baru tidak melewati batas drain.
Deploy tidak menghapus lease/job atau menghentikan unduhan untuk memaksa lolos.

## Pengujian executable

```bash
.venv/bin/python -m pytest -q \
  backend/tests/unit/test_deploy_fase.py \
  backend/tests/unit/test_skrip_deploy.py \
  backend/tests/unit/test_env_deploy.py \
  backend/tests/unit/test_batas_sha_deploy.py \
  backend/tests/unit/test_jendela_retry_deploy.py

AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017/ \
  .venv/bin/python -m pytest -q -m integration \
  backend/tests/contract/test_deploy_restore_guard.py
```

Harness membuat repository Git sementara tiga commit. Target yang disetujui
CI berbeda dari main terbaru sehingga teruji bahwa SHA immutable dipertahankan.
Git reset, byte env, izin, rename, trap, cleanup, dan kode exit berjalan nyata;
package manager, health HTTP, supervisor dan shell Mongo adalah batas eksternal
sintetis. Seluruh data, URL Mongo, env, dan service hanya milik fixture.

Skenario meliputi reset parsial, HEAD tidak cocok, env, pip, restart, health
shallow/deep, yarn install/build, output build hilang, penghapusan staging,
rename build lama/baru, health pascaaktivasi, TERM pada reset/env/pip/restart/
install/build/dua rename/health akhir, kegagalan rollback Git/env/pip/restart/
health/frontend, pelepasan mutex gagal, fetch gagal, restore/recovery stale,
state tidak dikenal, active unduhan, anti-downgrade, rollback manual, serta
commit valid yang bukan bagian main. Tidak ada keberhasilan rollback yang
disimpulkan hanya dari nama fungsi atau assertion teks sumber.

Kontrak Mongo nyata membuktikan enam proses berkompetisi menghasilkan satu
pemilik mutex, owner lain tidak dapat melepasnya, state restore dengan heartbeat
sangat lama dan tanpa backup_jobs tetap memblokir deploy, serta writer lease dan
unduhan aktif serta background_jobs importing/unknown nonterminal mencegah restart;
terminal atau done=true baru dapat lolos drain. Database dibuat dengan nama acak
`aman_deploy_contract_*` di loopback, kemudian hanya database tersebut dihapus.

Hasil aktual akhir dicatat setelah seluruh pengujian selesai di bawah ini.

## Batas bukti dan urutan rollout

- SIGKILL, kernel OOM yang membunuh shell, listrik padam, atau host mati tidak
  dapat menjalankan trap Bash. Mutex `deploying` sengaja tidak kedaluwarsa;
  operator harus memeriksa rilis dan kesehatan sebelum membukanya.
- Backend sebelum rilis ini belum mengenal mutex `deploying` atau writer lease.
  Rollout pertama memerlukan jendela tanpa writer dan antrean unduhan kosong;
  pemeriksaan sekali tidak membuktikan request lama tidak datang sesudahnya.
  Setelah seluruh worker menjalankan versi baru, mutex ditambah lease menutup
  race admission/drain untuk deploy berikutnya.
- Pemulihan requirements menggunakan venv yang sama. Paket tambahan dari rilis
  gagal mungkin masih terpasang walau requirements lama dipasang ulang. Rilis
  immutable dengan venv terpisah adalah OPT-25; bukti ini tidak mengklaim
  isolasi dependency byte-for-byte.
- Aktivasi frontend masih dua rename pada layout VPS yang ada. Jendela rename,
  retensi lazy chunk tab lama, dan pointer `current` atomik termasuk OPT-21/25;
  pekerjaan ini tidak mengklaim zero downtime atau migrasi release directory.
- Tidak ada perubahan gerbang CI/main/SHA/anti-downgrade dan tidak ada bypass
  workflow release. Workflow tetap harus membuktikan CI sukses untuk SHA tepat.

## Membuka mutex deployment yang tertinggal

Lakukan hanya setelah proses deploy pemilik token telah berhenti, Git HEAD dan
frontend yang melayani sudah pasangan known-good, supervisor sehat, serta kedua
endpoint `/api/health` dan `/api/health/deep` berhasil. Jangan memakai langkah
ini untuk state restore atau `recovery_required`; gunakan prosedur recovery
restore pada OPT-06 dan pertahankan safety ZIP/media yang dirujuk.

Pada VPS, dari direktori aplikasi, gunakan venv aplikasi. Ganti argumen owner
persis dari log run yang diperiksa; argumen ini bukan rahasia. Perintah sengaja
memfilter `state=deploying` dan owner, bukan menghapus dokumen kontrol:

```bash
backend/venv/bin/python - 'deploy:PID:WAKTU:TOKEN' <<'PY'
import os
import sys
from datetime import datetime, timezone
from dotenv import dotenv_values
from pymongo import MongoClient
owner = sys.argv[1]
parts = owner.split(':')
if len(parts) != 4 or parts[0] != 'deploy' or not parts[1].isdigit():
    raise SystemExit('Owner deploy tidak valid')
try:
    os.kill(int(parts[1]), 0)
except ProcessLookupError:
    pass
else:
    raise SystemExit('PID pemilik masih ada; jangan membuka mutex')
config = dotenv_values('backend/.env')
with MongoClient(config['MONGO_URL'], serverSelectionTimeoutMS=5000) as client:
    result = client[config.get('DB_NAME') or 'inventaris_bmn'].restore_control.update_one(
        {'_id':'GLOBAL', 'state':'deploying', 'owner':owner},
        {'$set':{'state':'completed', 'active':False,
                 'updated_at':datetime.now(timezone.utc).isoformat(),
                 'operator_verified_release':True}})
    if result.matched_count != 1:
        raise SystemExit('Kontrol bukan milik deployment tersebut; tidak diubah')
print('Mutex deployment yang diverifikasi telah dibuka')
PY
```

## Lanjutan OPT-25

Langkah yang layak tanpa mengubah platform adalah packager artefak lokal:
frontend build dari SHA CI dengan manifest/checksum konfigurasi publik dan
dependency; stage release lengkap pada direktori terpisah; validasi semua file
sebelum aktivasi. Lalu harness staging dua rilis dan rollback harus membuktikan
pasangan backend/frontend, env privat, tab lama/lazy chunk, serta SHA pada health.
Pemindahan nginx/supervisor ke pointer `current` baru dilakukan setelah bukti
itu tersedia. Menambahkan arsip build saja belum memenuhi OPT-25.

## Hasil terukur

- Harness fase: **43 tes lulus** (137 lulus bersama 94 penjaga deploy/env/SHA/retry
  existing), 86,66 detik untuk gabungan suite pada lingkungan cloud ini.
- Kontrak mutex/drain pada Mongo lokal nyata: **7 tes lulus**, 16,76 detik.
- `bash -n scripts/deploy_vps.sh` dan `git diff --check` untuk berkas deploy lulus.
- Hasil CI rilis dan verifikasi produksi menjadi bukti terpisah setelah seluruh
  paket implementasi digabungkan; tidak ditandai lulus oleh pengujian lokal ini.
