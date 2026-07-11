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

# Frontend: dependensi bisa bertambah (mis. leaflet) + build produksi.
cd frontend
yarn install --frozen-lockfile
yarn build

echo "Deploy selesai: $(git -C "$APP_DIR" rev-parse --short HEAD)"
