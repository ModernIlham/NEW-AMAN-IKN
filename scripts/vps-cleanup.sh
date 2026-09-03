#!/bin/bash
# ============================================
# Script untuk Membersihkan Deployment Lama
# Jalankan PERTAMA sebelum vps-setup.sh
# Usage: chmod +x vps-cleanup.sh && sudo ./vps-cleanup.sh
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Pagar keadaan harus berjalan SEBELUM prompt dan mutasi pertama. Nama skrip
# ini mudah tertukar dengan skrip deploy saat operator sedang memulihkan VPS;
# konfirmasi "YA" saja tidak membuktikan bahwa server memang kosong.
AMAN_CLEANUP_APP_DIR="${AMAN_CLEANUP_APP_DIR:-${APP_DIR:-/var/www/inventarisasi}}"
AMAN_CLEANUP_TERDETEKSI=()

if [ -e "$AMAN_CLEANUP_APP_DIR" ]; then
    AMAN_CLEANUP_TERDETEKSI+=("direktori aplikasi: $AMAN_CLEANUP_APP_DIR")
fi
if [ -e /var/lib/mongodb/WiredTiger ]; then
    AMAN_CLEANUP_TERDETEKSI+=("data MongoDB: /var/lib/mongodb/WiredTiger")
fi
if [ -e /etc/supervisor/conf.d/inventarisasi-backend.conf ]; then
    AMAN_CLEANUP_TERDETEKSI+=("konfigurasi Supervisor AMAN")
fi
if [ -e /etc/nginx/sites-available/inventarisasi ]; then
    AMAN_CLEANUP_TERDETEKSI+=("konfigurasi Nginx AMAN")
fi
if [ -e /etc/nginx/sites-enabled/inventarisasi ]; then
    AMAN_CLEANUP_TERDETEKSI+=("site Nginx AMAN aktif")
fi

# Instalasi dengan APP_DIR/dbPath kustom tetap terjaring lewat perangkat
# deployment yang sudah terpasang. False positive di sini disengaja: operator
# harus memilih override sebelum membersihkan mesin yang tidak benar-benar baru.
for alat in mongod nginx supervisord supervisorctl pm2 docker; do
    if command -v "$alat" >/dev/null 2>&1; then
        AMAN_CLEANUP_TERDETEKSI+=("perangkat deployment: $alat")
    fi
done

if [ "${AMAN_CLEANUP_PAKSA:-0}" != "1" ] && \
   [ "${#AMAN_CLEANUP_TERDETEKSI[@]}" -gt 0 ]; then
    echo -e "${RED}DIBATALKAN: keadaan server tidak aman untuk dibersihkan.${NC}" >&2
    printf '  - %s\n' "${AMAN_CLEANUP_TERDETEKSI[@]}" >&2
    echo -e "${YELLOW}Skrip berhenti sebelum layanan apa pun dihentikan.${NC}" >&2
    echo "Pastikan backup dapat dipulihkan. Jika penghapusan total memang disengaja:" >&2
    echo "  sudo env AMAN_CLEANUP_PAKSA=1 $0" >&2
    exit 1
elif [ "${AMAN_CLEANUP_PAKSA:-0}" = "1" ]; then
    echo -e "${RED}PERINGATAN: AMAN_CLEANUP_PAKSA=1 aktif; pagar keadaan dilewati.${NC}" >&2
else
    echo -e "${GREEN}Preflight aman: tidak ada deployment lama yang terdeteksi.${NC}"
fi

echo -e "${RED}============================================${NC}"
echo -e "${RED}  PEMBERSIHAN DEPLOYMENT LAMA               ${NC}"
echo -e "${RED}  VPS: amanikn-inventarisasi.com            ${NC}"
echo -e "${RED}============================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  Script ini akan menghapus semua software deployment lama!${NC}"
echo -e "${YELLOW}   Pastikan Anda sudah backup data penting.${NC}"
echo ""
read -p "Ketik 'YA' untuk melanjutkan: " confirm
if [ "$confirm" != "YA" ]; then
    echo "Dibatalkan."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/6] Menghentikan semua services...${NC}"
systemctl stop nginx 2>/dev/null || true
systemctl stop apache2 2>/dev/null || true
systemctl stop mongod 2>/dev/null || true
systemctl stop mysql 2>/dev/null || true
supervisorctl stop all 2>/dev/null || true
systemctl stop supervisor 2>/dev/null || true
pm2 kill 2>/dev/null || true
docker stop $(docker ps -q) 2>/dev/null || true

echo -e "${YELLOW}[2/6] Menghapus web servers...${NC}"
apt purge apache2 apache2-utils apache2-bin libapache2-mod-* -y 2>/dev/null || true
apt purge nginx nginx-common nginx-core -y 2>/dev/null || true

echo -e "${YELLOW}[3/6] Menghapus databases...${NC}"
apt purge mongodb* mongod* -y 2>/dev/null || true
rm -rf /var/lib/mongodb 2>/dev/null || true
rm -rf /var/log/mongodb 2>/dev/null || true
# Uncomment baris berikut jika MySQL juga ingin dihapus:
# apt purge mysql-server mysql-client mysql-common mariadb-server mariadb-client -y 2>/dev/null || true
# rm -rf /var/lib/mysql 2>/dev/null || true

echo -e "${YELLOW}[4/6] Menghapus runtimes...${NC}"
apt purge nodejs npm -y 2>/dev/null || true
apt purge php* libapache2-mod-php* -y 2>/dev/null || true
rm -rf /usr/local/lib/node_modules 2>/dev/null || true
rm -rf /usr/local/bin/node /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn 2>/dev/null || true
rm -rf ~/.nvm 2>/dev/null || true
npm uninstall -g pm2 2>/dev/null || true

echo -e "${YELLOW}[5/6] Menghapus tools lainnya...${NC}"
apt purge supervisor -y 2>/dev/null || true
snap remove certbot 2>/dev/null || true
apt purge certbot python3-certbot-nginx -y 2>/dev/null || true
apt purge docker* containerd* -y 2>/dev/null || true
rm -rf /var/lib/docker 2>/dev/null || true

# Hapus sources lama
rm -f /etc/apt/sources.list.d/mongodb*.list 2>/dev/null || true
rm -f /etc/apt/sources.list.d/nodesource*.list 2>/dev/null || true

echo -e "${YELLOW}[6/6] Membersihkan sistem...${NC}"
apt autoremove -y
apt autoclean

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  PEMBERSIHAN SELESAI!                      ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Langkah selanjutnya:${NC}"
echo "  1. Jalankan: chmod +x vps-setup.sh && sudo ./vps-setup.sh"
echo ""
