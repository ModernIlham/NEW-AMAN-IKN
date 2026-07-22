#!/usr/bin/env bash
# Update aplikasi AMAN di VPS Hostinger ke origin/main.
#
# Dijalankan otomatis oleh workflow "Deploy ke Hostinger VPS" lewat SSH,
# atau manual di VPS:  bash scripts/deploy_vps.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/inventarisasi}"
cd "$APP_DIR"

# .env berisi kredensial produksi dan TIDAK ikut repo — amankan dulu.
cp backend/.env /tmp/backend_env_backup
cp frontend/.env /tmp/frontend_env_backup

# JANGAN git pull — selalu fetch + reset agar identik dengan main.
git fetch origin main
git reset --hard origin/main

cp /tmp/backend_env_backup backend/.env
cp /tmp/frontend_env_backup frontend/.env

# Dependensi backend bisa bertambah antar rilis.
if [ -x backend/venv/bin/pip ]; then
  backend/venv/bin/pip install -q -r backend/requirements.txt
fi

# Restart backend (tanpa sudo bila user sudah root).
sudo -n supervisorctl restart inventarisasi-backend 2>/dev/null \
  || supervisorctl restart inventarisasi-backend

# Verifikasi backend BENAR-BENAR hidup setelah restart. `supervisorctl restart`
# bisa mengembalikan 0 walau proses gagal start (mis. import error) → deploy
# "sukses" padahal situs mati (false-green). Poll /api/health (no-auth, instan)
# sampai ~30 dtk; gagal → exit non-zero agar job deploy jelas GAGAL.
HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8001/api/health}"
echo "Cek kesehatan backend di ${HEALTH_URL} ..."
for i in $(seq 1 15); do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Backend sehat."
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "GAGAL: backend tidak sehat setelah restart (health-check timeout)." >&2
    sudo -n supervisorctl status inventarisasi-backend 2>/dev/null \
      || supervisorctl status inventarisasi-backend 2>/dev/null || true
    exit 1
  fi
  sleep 2
done

# Liveness dangkal saja tidak cukup: proses bisa hidup tapi MongoDB/GridFS tak
# terjangkau (kredensial DB salah, disk penuh, Mongo mati) → aplikasi "hidup"
# padahal setiap operasi data gagal. Verifikasi DEEP: /api/health/deep membalas
# 200 hanya bila Mongo ping + GridFS terbaca; 503 bila degraded → curl -f gagal.
# Beri jendela retry sendiri (~30 dtk) untuk pemanasan pool koneksi Mongo.
DEEP_HEALTH_URL="${BACKEND_DEEP_HEALTH_URL:-http://127.0.0.1:8001/api/health/deep}"
echo "Cek kesehatan mendalam (Mongo+GridFS) di ${DEEP_HEALTH_URL} ..."
for i in $(seq 1 15); do
  if curl -fsS --max-time 5 "$DEEP_HEALTH_URL" >/dev/null 2>&1; then
    echo "Dependensi backend (MongoDB + GridFS) sehat."
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "GAGAL: dependensi backend tak sehat setelah restart (deep health 503/timeout)." >&2
    echo "Respons terakhir /api/health/deep:" >&2
    curl -sS --max-time 5 "$DEEP_HEALTH_URL" 2>/dev/null | head -c 500 >&2 || true
    echo >&2
    exit 1
  fi
  sleep 2
done

# Frontend: dependensi bisa bertambah (mis. leaflet) + build produksi.
cd frontend
yarn install --frozen-lockfile
yarn build

echo "Deploy selesai: $(git -C "$APP_DIR" rev-parse --short HEAD)"
