#!/usr/bin/env bash
# Update aplikasi AMAN di VPS Hostinger ke origin/main.
#
# Dijalankan otomatis oleh workflow "Deploy ke Hostinger VPS" lewat SSH,
# atau manual di VPS:  bash scripts/deploy_vps.sh
#
# ── Tiga sifat yang membedakan skrip ini dari versi sebelumnya (temuan C6) ──
#
# 1. PAGAR MEMORI. `yarn build` di VPS tanpa swap adalah kandidat OOM paling
#    besar di seluruh sistem. `grep -rn NODE_OPTIONS scripts/` dulu menemukan
#    pagar itu di vps-deploy.sh dan update-all.sh, TETAPI TIDAK di berkas ini —
#    justru skrip yang benar-benar dipakai otomatislah satu-satunya tanpa pagar.
#
# 2. BUILD KE DIREKTORI SEMENTARA. react-scripts memanggil `fs.emptyDirSync`
#    di awal build, dan docroot nginx menunjuk LANGSUNG ke frontend/build
#    (vps-deploy.sh: `root ${APP_DIR}/frontend/build`). Artinya setiap deploy
#    mengosongkan docroot lalu mengisinya ulang selama puluhan detik: sepanjang
#    itu pengunjung mendapat 404. Membangun ke `build.new` lalu menukar dengan
#    `mv` memperkecil jendela itu dari "selama build" menjadi "dua panggilan
#    rename" — dan `build.old` menjadi rollback frontend instan.
#
# 3. ROLLBACK. Gerbang kesehatan sudah ada dan sudah benar, tetapi ketika ia
#    gagal skrip hanya keluar — meninggalkan produksi menjalankan commit yang
#    baru saja terbukti tidak sehat, sampai ada manusia yang bangun. Commit
#    sebelumnya kini disimpan dan dikembalikan otomatis.
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/inventarisasi}"
# Cabang tujuan bisa diganti untuk uji coba; bawaannya main.
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
cd "$APP_DIR"

# Commit yang SEDANG melayani produksi — tujuan rollback bila deploy gagal.
PREV="$(git rev-parse HEAD)"
echo "Commit saat ini (titik pulang bila gagal): $(git rev-parse --short HEAD)"

# ── Gerbang restore (prasyarat C30): deploy tak boleh menimpa pemulihan ──
# data yang sedang berjalan. `restart_backend` di bawah membunuh task restore
# di TENGAH wipe — sampai kini itu terjadi DIAM-DIAM dan meninggalkan DB
# separuh terisi. Periksa job restore aktif (active_lock GLOBAL, denyut
# < 30 menit — cutoff yang sama dengan cleanup_stale_jobs backend) langsung
# ke Mongo SEBELUM menyentuh apa pun; bila ada, batalkan deploy.
#
# GAGAL-BUKA disengaja: pemeriksa yang rusak (mongosh hilang, URI tak
# terbaca) tidak boleh memblokir semua deploy selamanya — ia memperingatkan
# lalu melanjutkan, persis perilaku hari ini.
periksa_restore_aktif() {
  command -v mongosh >/dev/null 2>&1 || {
    echo "PERINGATAN: mongosh tidak ditemukan — gerbang restore dilewati." >&2
    return 0
  }
  local uri dbn batas n
  uri="$(grep -E '^MONGO_URL=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  dbn="$(grep -E '^DB_NAME=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  if [ -z "$uri" ]; then
    echo "PERINGATAN: MONGO_URL tak terbaca dari backend/.env — gerbang restore dilewati." >&2
    return 0
  fi
  batas="$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || true)"
  n="$(mongosh "$uri" --quiet --eval "
    db = db.getSiblingDB('${dbn:-inventaris_bmn}');
    db.backup_jobs.countDocuments({type: 'restore', active_lock: 'GLOBAL',
      status: {\$in: ['queued', 'running']},
      updated_at: {\$gt: '${batas}'}})" 2>/dev/null || true)"
  if [ "${n:-0}" -ge 1 ] 2>/dev/null; then
    echo "DEPLOY DIBATALKAN: ada pemulihan data (restore) sedang berjalan." >&2
    echo "restart_backend akan membunuh restore di tengah wipe dan meninggalkan DB separuh terisi." >&2
    echo "Tunggu restore selesai (pantau layar Pengaturan) lalu jalankan deploy ulang." >&2
    exit 1
  fi
  return 0
}
periksa_restore_aktif

# .env berisi kredensial produksi dan TIDAK ikut repo — amankan dulu.
cp backend/.env /tmp/backend_env_backup
cp frontend/.env /tmp/frontend_env_backup

pasang_env() {
  cp /tmp/backend_env_backup backend/.env
  cp /tmp/frontend_env_backup frontend/.env
}

pasang_dependensi_backend() {
  if [ -x backend/venv/bin/pip ]; then
    backend/venv/bin/pip install -q -r backend/requirements.txt
  fi
}

restart_backend() {
  sudo -n supervisorctl restart inventarisasi-backend 2>/dev/null \
    || supervisorctl restart inventarisasi-backend
}

# Kembalikan produksi ke commit sebelumnya lalu hidupkan lagi.
#
# Sengaja BUKAN `set -e`-fatal di dalam sini: kalau rollback pun bermasalah,
# yang kita inginkan adalah pesan selengkap mungkin di log deploy — bukan
# skrip yang mati di tengah pemulihan dan menyisakan tebakan.
pulihkan() {
  echo "ROLLBACK: mengembalikan kode ke ${PREV} ..." >&2
  git reset --hard "$PREV" || echo "ROLLBACK: git reset GAGAL" >&2
  pasang_env || true
  pasang_dependensi_backend || echo "ROLLBACK: pip install GAGAL" >&2
  restart_backend || echo "ROLLBACK: restart backend GAGAL" >&2
  # Frontend belum tersentuh pada tahap ini (build berjalan setelah gerbang
  # kesehatan), jadi docroot masih memuat bundel lama yang cocok dengan PREV.
  echo "ROLLBACK selesai pada $(git rev-parse --short HEAD). PERIKSA LOG BACKEND." >&2
}

# JANGAN git pull — selalu fetch + reset agar identik dengan cabang tujuan.
git fetch origin "$DEPLOY_BRANCH"
git reset --hard "origin/${DEPLOY_BRANCH}"

pasang_env
# Dependensi backend bisa bertambah antar rilis.
pasang_dependensi_backend

restart_backend

# Verifikasi backend BENAR-BENAR hidup setelah restart. `supervisorctl restart`
# bisa mengembalikan 0 walau proses gagal start (mis. import error) → deploy
# "sukses" padahal situs mati (false-green). Poll /api/health (no-auth, instan)
# sampai ~90 dtk; gagal → rollback lalu exit non-zero agar job deploy jelas GAGAL.
#
# 45 × sleep 2 ≈ 90 dtk per gerbang. Angka ini ANGGARAN BOOT, bukan angka
# keramat: create_indexes + backfill startup berjalan SEBELUM port masuk
# state listen (uvicorn bind() dulu, listen() setelah lifespan.startup),
# jadi selama startup curl gagal instan dan hanya sleep yang menghitung.
# Terlalu ketat = rollback commit yang sebenarnya sehat. Satu variabel untuk
# EMPAT angka yang dulu literal — mengubah `seq` tapi lupa pembanding `-eq`
# menghasilkan gerbang yang diam-diam gagal LEBIH cepat.
PERCOBAAN_KESEHATAN=45
HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8001/api/health}"
echo "Cek kesehatan backend di ${HEALTH_URL} ..."
for i in $(seq 1 "$PERCOBAAN_KESEHATAN"); do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Backend sehat."
    break
  fi
  if [ "$i" -eq "$PERCOBAAN_KESEHATAN" ]; then
    echo "GAGAL: backend tidak sehat setelah restart (health-check timeout)." >&2
    sudo -n supervisorctl status inventarisasi-backend 2>/dev/null \
      || supervisorctl status inventarisasi-backend 2>/dev/null || true
    pulihkan
    exit 1
  fi
  sleep 2
done

# Liveness dangkal saja tidak cukup: proses bisa hidup tapi MongoDB/GridFS tak
# terjangkau (kredensial DB salah, disk penuh, Mongo mati) → aplikasi "hidup"
# padahal setiap operasi data gagal. Verifikasi DEEP: /api/health/deep membalas
# 200 hanya bila Mongo ping + GridFS terbaca; 503 bila degraded → curl -f gagal.
# Beri jendela retry sendiri (~90 dtk, anggaran yang sama) untuk pemanasan
# pool koneksi Mongo.
DEEP_HEALTH_URL="${BACKEND_DEEP_HEALTH_URL:-http://127.0.0.1:8001/api/health/deep}"
echo "Cek kesehatan mendalam (Mongo+GridFS) di ${DEEP_HEALTH_URL} ..."
for i in $(seq 1 "$PERCOBAAN_KESEHATAN"); do
  if curl -fsS --max-time 5 "$DEEP_HEALTH_URL" >/dev/null 2>&1; then
    echo "Dependensi backend (MongoDB + GridFS) sehat."
    break
  fi
  if [ "$i" -eq "$PERCOBAAN_KESEHATAN" ]; then
    echo "GAGAL: dependensi backend tak sehat setelah restart (deep health 503/timeout)." >&2
    echo "Respons terakhir /api/health/deep:" >&2
    curl -sS --max-time 5 "$DEEP_HEALTH_URL" 2>/dev/null | head -c 500 >&2 || true
    echo >&2
    pulihkan
    exit 1
  fi
  sleep 2
done

# ── Frontend: dependensi bisa bertambah (mis. leaflet) + build produksi ──
cd frontend
# --ignore-engines: Node VPS (20.x) lebih tua dari runner CI (22). Paket uji
# seperti @testing-library/jest-dom 6.10 mensyaratkan Node >=22 dan membuat
# yarn MENOLAK install padahal paket itu tak pernah ikut bundel produksi.
# Pemeriksaan engines hanya nasihat metadata; bila ada dependensi jalur build
# yang sungguh tak jalan di Node VPS, `yarn build` keluar non-zero dan
# `set -e` di atas menghentikan skrip SEBELUM penukaran build — docroot lama
# utuh. (Gerbang build.new/index.html di bawah menangkap kasus berbeda:
# build exit 0 tapi tak menghasilkan bundel.) Cek engines yarn juga DILEWATI
# bila node_modules sudah mutakhir — itulah kenapa kegagalan ini baru muncul
# saat lockfile berubah, bukan di setiap deploy. Obat akarnya: upgrade Node
# VPS ke 22 LTS, lalu flag ini boleh dicabut.
yarn install --frozen-lockfile --ignore-engines

# Pagar memori Node — lihat catatan (1) di kepala berkas.
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}"

# Bangun ke direktori SEMENTARA (react-scripts 5 menghormati BUILD_PATH), lalu
# tukar. Docroot lama tetap melayani selama build berjalan — lihat catatan (2).
rm -rf build.new
BUILD_PATH=build.new yarn build

if [ ! -f build.new/index.html ]; then
  echo "GAGAL: build.new/index.html tidak ada — build tidak menghasilkan bundel." >&2
  echo "Docroot LAMA tetap dipertahankan; situs tidak terganggu." >&2
  rm -rf build.new
  exit 1
fi

# Tukar. `build.old` sengaja DIPERTAHANKAN sampai deploy berikutnya: bila
# bundel baru ternyata bermasalah, memulihkan frontend cukup satu perintah —
#   cd frontend && rm -rf build && mv build.old build
rm -rf build.old
# `if`, BUKAN `[ -d build ] && mv ...` — di bawah `set -e`, rantai && yang
# berakhir false (build belum ada, mis. VPS baru) menghentikan seluruh skrip.
if [ -d build ]; then
  mv build build.old
fi
mv build.new build
echo "Bundel frontend ditukar; salinan sebelumnya tersimpan di frontend/build.old"

echo "Deploy selesai: $(git -C "$APP_DIR" rev-parse --short HEAD)"
