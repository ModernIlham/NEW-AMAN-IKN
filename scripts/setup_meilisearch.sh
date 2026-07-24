#!/usr/bin/env bash
# =============================================================================
# Pemasangan Meilisearch untuk AMAN — DIJALANKAN SEKALI DI VPS oleh pemilik.
# =============================================================================
# Skrip ini TIDAK dipanggil pipeline deploy. Meilisearch bersifat OPSIONAL:
# backend AMAN berjalan normal tanpanya (pencarian pakai regex Mongo). Setelah
# skrip ini sukses, backend memakai Meilisearch (pencarian cepat + toleran typo).
#
# Yang dilakukan (idempoten — aman diulang):
#   1. Unduh binari Meilisearch (versi tersemat) ke /usr/local/bin.
#   2. Buat user sistem `meilisearch` + direktori data /var/lib/meilisearch.
#   3. Buat master key acak (bila belum ada) + tulis /etc/meilisearch.toml
#      (bind HANYA ke 127.0.0.1 — tidak terpapar publik).
#   4. Pasang + nyalakan service systemd `meilisearch`.
#   5. Tambahkan MEILI_URL & MEILI_MASTER_KEY ke backend/.env (bila belum ada).
#   6. Restart backend (supervisor) + reindex data awal dari Mongo.
#
# Pakai:
#   sudo bash scripts/setup_meilisearch.sh
#
# Variabel lingkungan opsional:
#   APP_DIR         (default /var/www/inventarisasi)  — root aplikasi AMAN
#   MEILI_VERSION   (default v1.11.3)                  — versi binari Meili
#   MEILI_PORT      (default 7700)                     — port lokal Meili
#   MEILI_MASTER_KEY (opsional)                        — pakai key ini, bukan acak
# =============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/inventarisasi}"
MEILI_VERSION="${MEILI_VERSION:-v1.11.3}"
MEILI_PORT="${MEILI_PORT:-7700}"
MEILI_BIN="/usr/local/bin/meilisearch"
MEILI_DATA="/var/lib/meilisearch"
MEILI_CONF="/etc/meilisearch.toml"
MEILI_UNIT="/etc/systemd/system/meilisearch.service"
BACKEND_ENV="${APP_DIR}/backend/.env"

log() { echo -e "\033[1;34m[meili-setup]\033[0m $*"; }
err() { echo -e "\033[1;31m[meili-setup] GAGAL:\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || err "Jalankan sebagai root (sudo)."
command -v systemctl >/dev/null 2>&1 || err "systemd (systemctl) tidak ditemukan."

# ── 1. Unduh binari Meilisearch (sesuai arsitektur) ─────────────────────────
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64)  ASSET="meilisearch-linux-amd64" ;;
  aarch64|arm64) ASSET="meilisearch-linux-aarch64" ;;
  *) err "Arsitektur tak didukung: $ARCH" ;;
esac

if [ -x "$MEILI_BIN" ] && "$MEILI_BIN" --version 2>/dev/null | grep -q "${MEILI_VERSION#v}"; then
  log "Binari Meilisearch ${MEILI_VERSION} sudah terpasang — lewati unduh."
else
  URL="https://github.com/meilisearch/meilisearch/releases/download/${MEILI_VERSION}/${ASSET}"
  log "Mengunduh Meilisearch ${MEILI_VERSION} (${ASSET}) ..."
  TMP="$(mktemp)"
  curl -fsSL "$URL" -o "$TMP" || err "Gagal unduh dari $URL"
  install -m 0755 "$TMP" "$MEILI_BIN"
  rm -f "$TMP"
  log "Terpasang: $("$MEILI_BIN" --version)"
fi

# ── 2. User sistem + direktori data ─────────────────────────────────────────
if ! id -u meilisearch >/dev/null 2>&1; then
  log "Membuat user sistem 'meilisearch' ..."
  useradd --system --home-dir "$MEILI_DATA" --shell /usr/sbin/nologin meilisearch
fi
mkdir -p "$MEILI_DATA"
chown -R meilisearch:meilisearch "$MEILI_DATA"

# ── 3. Master key + konfigurasi ─────────────────────────────────────────────
# Prioritas key: argumen env → key yang sudah ada di backend/.env → acak baru.
MASTER_KEY="${MEILI_MASTER_KEY:-}"
if [ -z "$MASTER_KEY" ] && [ -f "$BACKEND_ENV" ]; then
  MASTER_KEY="$(grep -E '^MEILI_MASTER_KEY=' "$BACKEND_ENV" | head -n1 | cut -d= -f2- || true)"
fi
if [ -z "$MASTER_KEY" ]; then
  MASTER_KEY="$(openssl rand -hex 32)"
  log "Master key baru dibuat (acak 32 byte)."
else
  log "Memakai master key yang sudah ada."
fi

log "Menulis konfigurasi $MEILI_CONF ..."
cat > "$MEILI_CONF" <<EOF
# Konfigurasi Meilisearch AMAN (ditulis oleh setup_meilisearch.sh).
env = "production"
master_key = "${MASTER_KEY}"
db_path = "${MEILI_DATA}/data.ms"
dump_dir = "${MEILI_DATA}/dumps"
# Bind HANYA localhost — Meili diakses backend di VPS yang sama, tak publik.
http_addr = "127.0.0.1:${MEILI_PORT}"
# Nonaktifkan telemetri.
no_analytics = true
EOF
chmod 600 "$MEILI_CONF"
chown meilisearch:meilisearch "$MEILI_CONF"

# ── 4. Service systemd ──────────────────────────────────────────────────────
log "Menulis unit systemd $MEILI_UNIT ..."
cat > "$MEILI_UNIT" <<EOF
[Unit]
Description=Meilisearch (mesin pencari AMAN)
After=network.target

[Service]
Type=simple
User=meilisearch
Group=meilisearch
ExecStart=${MEILI_BIN} --config-file-path ${MEILI_CONF}
Restart=on-failure
RestartSec=3
WorkingDirectory=${MEILI_DATA}
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable meilisearch >/dev/null 2>&1 || true
systemctl restart meilisearch
log "Menunggu Meilisearch sehat ..."
for i in $(seq 1 15); do
  if curl -fsS --max-time 3 "http://127.0.0.1:${MEILI_PORT}/health" >/dev/null 2>&1; then
    log "Meilisearch sehat di 127.0.0.1:${MEILI_PORT}."
    break
  fi
  [ "$i" -eq 15 ] && err "Meilisearch tak sehat setelah start (cek: journalctl -u meilisearch)."
  sleep 2
done

# ── 5. Sisipkan env ke backend/.env ─────────────────────────────────────────
if [ ! -f "$BACKEND_ENV" ]; then
  err "backend/.env tidak ditemukan di $BACKEND_ENV — set APP_DIR yang benar."
fi
MEILI_URL_VAL="http://127.0.0.1:${MEILI_PORT}"
# Hapus baris lama (bila ada) lalu tambahkan yang baru — idempoten.
sed -i '/^MEILI_URL=/d;/^MEILI_MASTER_KEY=/d' "$BACKEND_ENV"
{
  echo "MEILI_URL=${MEILI_URL_VAL}"
  echo "MEILI_MASTER_KEY=${MASTER_KEY}"
} >> "$BACKEND_ENV"
log "backend/.env diperbarui (MEILI_URL, MEILI_MASTER_KEY)."

# ── 6. Restart backend + reindex ────────────────────────────────────────────
log "Restart backend agar membaca env baru ..."
if command -v supervisorctl >/dev/null 2>&1; then
  supervisorctl restart inventarisasi-backend || log "PERINGATAN: restart backend manual diperlukan."
else
  log "supervisorctl tak ada — restart backend AMAN secara manual."
fi

log "Reindex data awal dari Mongo ..."
if [ -x "${APP_DIR}/backend/venv/bin/python" ]; then
  ( cd "${APP_DIR}/backend" && venv/bin/python -m scripts.reindex_search ) \
    || log "PERINGATAN: reindex gagal — jalankan manual nanti (lihat docs/MEILISEARCH.md)."
else
  log "venv backend tak ditemukan — jalankan reindex manual (lihat docs/MEILISEARCH.md)."
fi

echo
log "SELESAI. Meilisearch aktif & backend tersambung."
echo "  • URL Meili   : ${MEILI_URL_VAL} (localhost)"
echo "  • Konfigurasi : ${MEILI_CONF}"
echo "  • Service     : systemctl status meilisearch"
echo "  • Log         : journalctl -u meilisearch -f"
echo
echo "Opsional (untuk catatan/DR): simpan MEILI_MASTER_KEY sebagai GitHub secret."
echo "Rollback: hapus MEILI_URL & MEILI_MASTER_KEY dari backend/.env lalu restart"
echo "backend → pencarian otomatis kembali ke regex Mongo."
