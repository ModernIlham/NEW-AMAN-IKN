#!/usr/bin/env bash
# =============================================================================
# Pemasangan Redis untuk AMAN — DIJALANKAN SEKALI DI VPS oleh pemilik.
# =============================================================================
# Skrip ini TIDAK dipanggil pipeline deploy. Redis bersifat OPSIONAL: backend
# AMAN berjalan normal tanpanya (cache per-worker + rate-limit via MongoDB).
# Setelah skrip ini sukses, backend memakai Redis sebagai:
#   - CACHE BERSAMA lintas-worker (stats/filter/analytics/kategori) → invalidasi
#     seketika di ke-2 worker + beban Mongo turun, dan
#   - STORAGE RATE-LIMITER (lebih cepat dari MongoDB, tetap bersama).
#
# Yang dilakukan (idempoten — aman diulang):
#   1. Pasang redis-server (apt).
#   2. Bind HANYA ke localhost (127.0.0.1) + set password (requirepass).
#   3. Nyalakan service systemd `redis-server`.
#   4. Tambahkan REDIS_URL ke backend/.env (bila belum ada).
#   5. Restart backend (supervisor) agar membaca env baru.
#
# Pakai:
#   sudo bash scripts/setup_redis.sh
#
# Variabel lingkungan opsional:
#   APP_DIR    (default /var/www/inventarisasi)  — root aplikasi AMAN
#   REDIS_PORT (default 6379)                     — port lokal Redis
#   REDIS_PASSWORD (opsional)                      — pakai password ini, bukan acak
# =============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/inventarisasi}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_CONF="/etc/redis/redis.conf"
BACKEND_ENV="${APP_DIR}/backend/.env"

log() { echo -e "\033[1;31m[redis-setup]\033[0m $*"; }
err() { echo -e "\033[1;31m[redis-setup] GAGAL:\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || err "Jalankan sebagai root (sudo)."
command -v systemctl >/dev/null 2>&1 || err "systemd (systemctl) tidak ditemukan."

# ── 1. Pasang redis-server ──────────────────────────────────────────────────
if ! command -v redis-server >/dev/null 2>&1; then
  log "Memasang redis-server via apt ..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq redis-server || err "Gagal apt-get install redis-server"
else
  log "redis-server sudah terpasang — lewati instalasi."
fi
[ -f "$REDIS_CONF" ] || err "Konfigurasi $REDIS_CONF tidak ditemukan."

# ── 2. Password (prioritas: env → yang sudah ada di .env → acak) ────────────
PASS="${REDIS_PASSWORD:-}"
if [ -z "$PASS" ] && [ -f "$BACKEND_ENV" ]; then
  # Ambil password dari REDIS_URL lama bila ada (format redis://:PASS@host:port/db)
  OLD_URL="$(grep -E '^REDIS_URL=' "$BACKEND_ENV" | head -n1 | cut -d= -f2- || true)"
  if [[ "$OLD_URL" =~ redis://:([^@]+)@ ]]; then
    PASS="${BASH_REMATCH[1]}"
  fi
fi
if [ -z "$PASS" ]; then
  PASS="$(openssl rand -hex 24)"
  log "Password Redis baru dibuat (acak)."
else
  log "Memakai password Redis yang sudah ada."
fi

# Password WAJIB URL-safe: dipakai apa adanya di `requirepass` (tanpa kutip) dan
# di REDIS_URL (redis://:PASS@...). Karakter seperti @ : / # spasi akan merusak
# URL/konfigurasi. Default (openssl hex) selalu lolos; hanya override manual
# ber-karakter aneh yang ditolak — beri pesan jelas alih-alih korupsi senyap.
if ! printf '%s' "$PASS" | grep -qE '^[A-Za-z0-9._~-]+$'; then
  err "REDIS_PASSWORD hanya boleh berisi huruf/angka/._~- (URL-safe). Ganti passwordnya."
fi

# ── 3. Konfigurasi: bind localhost + requirepass (idempoten) ────────────────
log "Mengonfigurasi $REDIS_CONF (bind localhost + password) ..."
# Hapus baris lama yang kita kelola, lalu tambahkan yang baru di akhir file.
sed -i -E '/^\s*bind\s+/d; /^\s*requirepass\s+/d; /^\s*protected-mode\s+/d; /^\s*port\s+/d' "$REDIS_CONF"
cat >> "$REDIS_CONF" <<EOF

# --- AMAN (ditambahkan setup_redis.sh) ---
bind 127.0.0.1 -::1
protected-mode yes
port ${REDIS_PORT}
requirepass ${PASS}
EOF

# ── 4. Nyalakan service ─────────────────────────────────────────────────────
systemctl enable redis-server >/dev/null 2>&1 || true
systemctl restart redis-server
log "Menunggu Redis sehat ..."
for i in $(seq 1 10); do
  if redis-cli -p "${REDIS_PORT}" -a "${PASS}" ping 2>/dev/null | grep -q PONG; then
    log "Redis sehat di 127.0.0.1:${REDIS_PORT}."
    break
  fi
  [ "$i" -eq 10 ] && err "Redis tak merespons PING (cek: journalctl -u redis-server)."
  sleep 1
done

# ── 5. Sisipkan REDIS_URL ke backend/.env ───────────────────────────────────
[ -f "$BACKEND_ENV" ] || err "backend/.env tidak ditemukan di $BACKEND_ENV — set APP_DIR yang benar."
REDIS_URL_VAL="redis://:${PASS}@127.0.0.1:${REDIS_PORT}/0"
sed -i '/^REDIS_URL=/d' "$BACKEND_ENV"
# Pastikan file diakhiri newline sebelum menambah (cegah baris tergabung bila
# .env terakhir tak ber-newline). tail -c1 → kosong bila byte terakhir newline.
if [ -s "$BACKEND_ENV" ] && [ -n "$(tail -c1 "$BACKEND_ENV")" ]; then
  echo >> "$BACKEND_ENV"
fi
echo "REDIS_URL=${REDIS_URL_VAL}" >> "$BACKEND_ENV"
log "backend/.env diperbarui (REDIS_URL)."

# ── 6. Restart backend ──────────────────────────────────────────────────────
log "Restart backend agar membaca env baru ..."
if command -v supervisorctl >/dev/null 2>&1; then
  supervisorctl restart inventarisasi-backend || log "PERINGATAN: restart backend manual diperlukan."
else
  log "supervisorctl tak ada — restart backend AMAN secara manual."
fi

echo
log "SELESAI. Redis aktif & backend tersambung."
echo "  • URL Redis  : redis://:***@127.0.0.1:${REDIS_PORT}/0 (localhost)"
echo "  • Service    : systemctl status redis-server"
echo "  • Log        : journalctl -u redis-server -f"
echo "  • Cek cepat  : redis-cli -a '<password>' ping   → PONG"
echo "  • Verifikasi : GET /api/health/deep → checks.redis.ok = true"
echo
echo "Rollback: hapus baris REDIS_URL dari backend/.env lalu restart backend →"
echo "cache otomatis kembali ke per-worker & rate-limiter ke MongoDB."
