#!/bin/bash
# ============================================
# Script Setup VPS untuk Inventarisasi BMN
# Jalankan sebagai root di VPS Hostinger
# Usage: chmod +x vps-setup.sh && sudo ./vps-setup.sh
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/var/www/inventarisasi"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Setup VPS - Inventarisasi BMN             ${NC}"
echo -e "${BLUE}  Domain: amanikn-inventarisasi.com         ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================
# FASE 1: Update sistem
# ============================================
echo -e "${YELLOW}[1/8] Updating system...${NC}"
apt update && apt upgrade -y
apt install -y build-essential curl wget git unzip software-properties-common \
  apt-transport-https ca-certificates gnupg lsb-release

# ============================================
# FASE 2: Install Python 3.11
# ============================================
echo -e "${YELLOW}[2/8] Installing Python 3.11...${NC}"
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.11 python3.11-venv python3.11-dev
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# System deps for WeasyPrint & Pillow
apt install -y \
  libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
  libcairo2 libcairo-gobject2 libgdk-pixbuf-2.0-0 \
  libffi-dev libglib2.0-0 libxml2 libxslt1.1 librsvg2-2 \
  libgirepository1.0-dev gir1.2-pango-1.0 \
  shared-mime-info fonts-noto \
  libjpeg-dev zlib1g-dev libfreetype6-dev

echo -e "${GREEN}  Python $(python3.11 --version) installed${NC}"

# ============================================
# FASE 3: Install Node.js 20 + Yarn
# ============================================
echo -e "${YELLOW}[3/8] Installing Node.js 20 + Yarn...${NC}"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g yarn@1.22.22

echo -e "${GREEN}  Node $(node --version) installed${NC}"
echo -e "${GREEN}  Yarn $(yarn --version) installed${NC}"

# ============================================
# FASE 4: Install MongoDB 7.0
# ============================================
echo -e "${YELLOW}[4/8] Installing MongoDB 7.0...${NC}"
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  tee /etc/apt/sources.list.d/mongodb-org-7.0.list

apt update
apt install -y mongodb-org
systemctl start mongod
systemctl enable mongod

echo -e "${GREEN}  MongoDB 7.0 installed${NC}"

# ============================================
# FASE 5: Install Nginx
# ============================================
echo -e "${YELLOW}[5/8] Installing Nginx...${NC}"
apt install -y nginx
systemctl start nginx
systemctl enable nginx

echo -e "${GREEN}  Nginx installed${NC}"

# ============================================
# FASE 6: Install Supervisor
# ============================================
echo -e "${YELLOW}[6/8] Installing Supervisor...${NC}"
apt install -y supervisor
systemctl start supervisor
systemctl enable supervisor

echo -e "${GREEN}  Supervisor installed${NC}"

# ============================================
# FASE 7: Install Certbot
# ============================================
echo -e "${YELLOW}[7/8] Installing Certbot...${NC}"
snap install --classic certbot 2>/dev/null || apt install -y certbot python3-certbot-nginx
ln -sf /snap/bin/certbot /usr/bin/certbot 2>/dev/null || true

echo -e "${GREEN}  Certbot installed${NC}"

# ============================================
# FASE 8: Setup direktori
# ============================================
echo -e "${YELLOW}[8/8] Creating app directories...${NC}"
mkdir -p ${APP_DIR}
mkdir -p /root/backup

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  SEMUA SOFTWARE BERHASIL DIINSTAL!         ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Verifikasi versi:"
echo "  Python 3.11 : $(python3.11 --version 2>&1)"
echo "  Node.js     : $(node --version 2>&1)"
echo "  Yarn        : $(yarn --version 2>&1)"
echo "  MongoDB     : $(mongod --version 2>&1 | head -1)"
echo "  Nginx       : $(nginx -v 2>&1)"
echo "  Supervisor  : $(supervisord --version 2>&1)"
echo ""
echo -e "${YELLOW}LANGKAH SELANJUTNYA:${NC}"
echo "  1. Transfer file aplikasi ke ${APP_DIR}/"
echo "  2. Jalankan: chmod +x /var/www/inventarisasi/scripts/vps-deploy.sh"
echo "  3. Jalankan: /var/www/inventarisasi/scripts/vps-deploy.sh"
echo ""
