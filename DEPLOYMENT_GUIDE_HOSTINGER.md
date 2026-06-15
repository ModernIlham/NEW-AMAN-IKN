# 🚀 Panduan Deployment Lengkap ke Hostinger VPS
## Aplikasi Inventarisasi BMN - amanikn-inventarisasi.com

> **VPS Target:** Ubuntu 24.04.4 LTS (x86_64), 8GB RAM, IP: 72.62.126.24
> **Domain:** amanikn-inventarisasi.com
> 
> ⚠️ **PENTING - Sebelum Mulai Deployment:**
> 1. **Push kode ke GitHub terlebih dahulu** menggunakan fitur "Save to GitHub" di Emergent.sh
> 2. **Branch default: `main`** - Pastikan Anda menggunakan branch yang benar
> 3. Catat nama repository dan username GitHub Anda untuk digunakan di FASE 3
> 4. Jika repository private, siapkan Personal Access Token dari GitHub

---

## 📋 DAFTAR ISI
1. [Arsitektur Production](#1-arsitektur-production)
2. [Versi Teknologi yang Harus Diinstal](#2-versi-teknologi)
3. [FASE 1: Bersihkan Deployment Lama](#fase-1)
4. [FASE 2: Instal Software yang Dibutuhkan](#fase-2)
5. [FASE 3: Transfer File Aplikasi](#fase-3)
6. [FASE 4: Setup Backend](#fase-4)
7. [FASE 5: Setup Frontend (Build Production)](#fase-5)
8. [FASE 6: Konfigurasi Nginx + SSL](#fase-6)
9. [FASE 7: Setup Supervisor (Process Manager)](#fase-7)
10. [FASE 8: Firewall & Keamanan](#fase-8)
11. [FASE 9: Testing & Verifikasi](#fase-9)
12. [Troubleshooting](#troubleshooting)
13. [Maintenance & Backup](#maintenance)

---

<a name="1-arsitektur-production"></a>
## 1️⃣ Arsitektur Production di Hostinger

```
Internet (HTTPS:443)
        │
        ▼
┌───────────────────────────────────┐
│          NGINX (Port 80/443)       │
│  ┌─────────────────────────────┐  │
│  │ SSL Termination (Let's Enc) │  │
│  └─────────────────────────────┘  │
│                                    │
│  /api/*  ──► proxy_pass localhost:8001 (Backend FastAPI)
│  /*      ──► /var/www/inventarisasi/frontend/build (Static React)
└───────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│ FastAPI      │    │ React Build      │
│ (Uvicorn)    │    │ (Static Files)   │
│ Port 8001    │    │ Served by Nginx  │
└──────┬───────┘    └──────────────────┘
       │
       ▼
┌──────────────┐
│ MongoDB 7.0  │
│ Port 27017   │
│ (localhost)  │
└──────────────┘
```

**Perbedaan dengan Emergent.sh:**
| Aspek | Emergent.sh | Hostinger VPS |
|-------|-------------|---------------|
| Frontend | Dev server (yarn start) port 3000 | Build static, served by Nginx |
| Routing | Kubernetes Ingress | Nginx reverse proxy |
| SSL | Otomatis | Let's Encrypt + Certbot |
| Process Manager | Supervisor | Supervisor (sama) |
| MongoDB | Local | Local (sama) |

---

<a name="2-versi-teknologi"></a>
## 2️⃣ Versi Teknologi yang HARUS Diinstal (Sama Persis dengan Emergent.sh)

| Software | Versi di Emergent.sh | Cara Install di Ubuntu 24.04 |
|----------|---------------------|------------------------------|
| **Python** | 3.11.14 | deadsnakes PPA |
| **Node.js** | 20.20.0 | NodeSource repo |
| **Yarn** | 1.22.22 | npm install -g |
| **MongoDB** | 7.0.30 | MongoDB official repo |
| **Nginx** | Latest stable | apt install |
| **Supervisor** | 4.2.x | apt install |
| **Certbot** | Latest | snap install |

---

<a name="fase-1"></a>
## 🧹 FASE 1: Bersihkan Deployment Lama (15 menit)

> ⚠️ **PENTING:** Pastikan Anda sudah backup data penting sebelum membersihkan!

### 1.1 Login ke VPS via SSH
```bash
ssh root@72.62.126.24
# atau
ssh root@amanikn-inventarisasi.com
```

### 1.2 Cek Apa Saja yang Terinstal Saat Ini
```bash
# Cek web server
echo "=== Web Server ==="
which nginx && nginx -v 2>&1
which apache2 && apache2 -v 2>&1
which httpd && httpd -v 2>&1

# Cek runtime/bahasa
echo "=== Runtime ==="
which python3 && python3 --version
which node && node --version
which php && php --version 2>&1 | head -1

# Cek database
echo "=== Database ==="
which mongod && mongod --version 2>&1 | head -1
which mysql && mysql --version 2>&1
which psql && psql --version 2>&1

# Cek process manager
echo "=== Process Manager ==="
which pm2 && pm2 --version
which supervisord && supervisord --version
which systemctl && echo "systemd tersedia"

# Cek Docker
echo "=== Docker ==="
which docker && docker --version

# Cek running services
echo "=== Running Services ==="
systemctl list-units --type=service --state=running | grep -E "nginx|apache|node|mongo|mysql|docker|pm2|supervisor"

# Cek listening ports
echo "=== Listening Ports ==="
ss -tlnp | grep -E "80|443|3000|8001|27017|3306"
```

### 1.3 Stop Semua Service Lama
```bash
# Stop web servers
sudo systemctl stop nginx 2>/dev/null
sudo systemctl stop apache2 2>/dev/null

# Stop databases
sudo systemctl stop mongod 2>/dev/null
sudo systemctl stop mysql 2>/dev/null

# Stop Node.js apps (jika pakai PM2)
pm2 kill 2>/dev/null

# Stop Supervisor managed apps
sudo supervisorctl stop all 2>/dev/null
sudo systemctl stop supervisor 2>/dev/null

# Stop Docker containers (jika ada)
docker stop $(docker ps -q) 2>/dev/null
```

### 1.4 Hapus/Uninstall Software Lama
```bash
# ==========================================
# UNINSTALL - Jalankan yang relevan saja
# ==========================================

# Hapus Apache (jika terinstal)
sudo apt purge apache2 apache2-utils apache2-bin libapache2-mod-* -y 2>/dev/null
sudo apt autoremove -y

# Hapus PHP (jika terinstal) 
sudo apt purge php* libapache2-mod-php* -y 2>/dev/null
sudo apt autoremove -y

# Hapus MySQL/MariaDB (jika terinstal & TIDAK dipakai)
# ⚠️ Ini akan HAPUS semua data MySQL!
sudo apt purge mysql-server mysql-client mysql-common mariadb-server mariadb-client -y 2>/dev/null
sudo rm -rf /var/lib/mysql
sudo apt autoremove -y

# Hapus MongoDB LAMA (kita akan install ulang versi yang tepat)
sudo apt purge mongodb* mongod* -y 2>/dev/null
sudo rm -rf /var/lib/mongodb
sudo rm -rf /var/log/mongodb
sudo apt autoremove -y

# Hapus Node.js LAMA (kita akan install ulang versi yang tepat)
sudo apt purge nodejs npm -y 2>/dev/null
sudo rm -rf /usr/local/lib/node_modules
sudo rm -rf /usr/local/bin/node /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn
# Hapus nvm jika ada
rm -rf ~/.nvm

# Hapus PM2 (jika ada)
npm uninstall -g pm2 2>/dev/null

# Hapus Docker (jika ada & tidak dipakai)
sudo apt purge docker* containerd* -y 2>/dev/null
sudo rm -rf /var/lib/docker
sudo apt autoremove -y

# Hapus Nginx LAMA (kita akan install ulang)
sudo apt purge nginx nginx-common nginx-core -y 2>/dev/null

# Hapus Supervisor LAMA (kita akan install ulang)
sudo apt purge supervisor -y 2>/dev/null

# Hapus Certbot LAMA
sudo snap remove certbot 2>/dev/null
sudo apt purge certbot python3-certbot-nginx -y 2>/dev/null

# Hapus Python LAMA versi tambahan (keep system python)
sudo apt purge python3.11 python3.11-venv python3.11-dev -y 2>/dev/null
```

### 1.5 Hapus File Aplikasi Lama
```bash
# ⚠️ BACKUP dulu jika ada data penting!
sudo rm -rf /var/www/html/*
sudo rm -rf /var/www/inventarisasi 2>/dev/null
sudo rm -rf /opt/app 2>/dev/null
# Hapus apt sources lama yang mungkin conflict
sudo rm -f /etc/apt/sources.list.d/mongodb*.list
sudo rm -f /etc/apt/sources.list.d/nodesource*.list
```

### 1.6 Bersihkan Sistem
```bash
sudo apt autoremove -y
sudo apt autoclean
sudo apt update
sudo apt upgrade -y
```

---

<a name="fase-2"></a>
## 📦 FASE 2: Instal Semua Software yang Dibutuhkan (30 menit)

### 2.1 Install Paket Dasar
```bash
sudo apt update
sudo apt install -y \
  build-essential \
  curl \
  wget \
  git \
  unzip \
  software-properties-common \
  apt-transport-https \
  ca-certificates \
  gnupg \
  lsb-release
```

### 2.2 Install Python 3.11 (Sama dengan Emergent: 3.11.14)
```bash
# Ubuntu 24.04 default-nya Python 3.12, kita perlu 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3.11-distutils

# Verifikasi
python3.11 --version
# Output harus: Python 3.11.x

# Install pip untuk Python 3.11
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
```

### 2.3 Install System Dependencies untuk WeasyPrint & Pillow
```bash
# WeasyPrint membutuhkan library sistem untuk render PDF
sudo apt install -y \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libpangoft2-1.0-0 \
  libcairo2 \
  libcairo-gobject2 \
  libgdk-pixbuf-2.0-0 \
  libffi-dev \
  libglib2.0-0 \
  libxml2 \
  libxslt1.1 \
  librsvg2-2 \
  libgirepository1.0-dev \
  gir1.2-pango-1.0 \
  python3-gi \
  python3-gi-cairo \
  shared-mime-info \
  fonts-noto \
  fonts-noto-cjk \
  libjpeg-dev \
  zlib1g-dev \
  libfreetype6-dev
```

### 2.4 Install Node.js 20.x (Sama dengan Emergent: v20.20.0)
```bash
# Install Node.js 20 dari NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verifikasi
node --version
# Output harus: v20.x.x

npm --version
```

### 2.5 Install Yarn 1.22.22 (Sama dengan Emergent)
```bash
# Install Yarn classic via npm
sudo npm install -g yarn@1.22.22

# Verifikasi
yarn --version
# Output harus: 1.22.22
```

### 2.6 Install MongoDB 7.0 (Sama dengan Emergent: 7.0.30)
```bash
# Import MongoDB GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Tambahkan repo MongoDB 7.0
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt update
sudo apt install -y mongodb-org

# Start MongoDB & enable auto-start
sudo systemctl start mongod
sudo systemctl enable mongod

# Verifikasi
mongod --version
# Output harus: db version v7.0.x

# Test koneksi
mongosh --eval "db.runCommand({ ping: 1 })"
```

> **Catatan:** Jika `apt update` untuk MongoDB gagal karena Ubuntu 24.04 (noble) belum tersedia, gunakan repo `jammy` (22.04) yang kompatibel. Command di atas sudah menggunakan `jammy`.

### 2.7 Install Nginx
```bash
sudo apt install -y nginx

# Verifikasi
nginx -v

# Start & enable
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 2.8 Install Supervisor (Process Manager)
```bash
sudo apt install -y supervisor

# Start & enable
sudo systemctl start supervisor
sudo systemctl enable supervisor

# Verifikasi
supervisord --version
```

### 2.9 Install Certbot untuk SSL
```bash
# Install via snap (cara yang direkomendasikan)
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Verifikasi
certbot --version
```

### 2.10 Verifikasi Semua Instalasi
```bash
echo "========================================="
echo "  VERIFIKASI SEMUA INSTALASI"
echo "========================================="
echo ""
echo "Python 3.11 : $(python3.11 --version 2>&1)"
echo "Node.js     : $(node --version 2>&1)"
echo "Yarn        : $(yarn --version 2>&1)"
echo "MongoDB     : $(mongod --version 2>&1 | head -1)"
echo "Nginx       : $(nginx -v 2>&1)"
echo "Supervisor  : $(supervisord --version 2>&1)"
echo "Certbot     : $(certbot --version 2>&1)"
echo "Git         : $(git --version 2>&1)"
echo ""
echo "========================================="
echo "  SERVICE STATUS"
echo "========================================="
sudo systemctl is-active mongod
sudo systemctl is-active nginx
sudo systemctl is-active supervisor
```

---

<a name="fase-3"></a>
## 📁 FASE 3: Transfer File Aplikasi ke VPS (10 menit)

### Metode yang Direkomendasikan: Git (GitHub)

**Langkah A - Di Emergent.sh (Simpan ke GitHub):**
1. Buka aplikasi di Emergent.sh
2. Klik ikon **Profile** di pojok kanan atas
3. Pilih **"Save to GitHub"**
4. Buat repository baru (private recommended): `aman-inventarisasi` atau nama pilihan Anda
5. Tunggu sampai push selesai
6. **PENTING:** Catat nama repository dan branch yang digunakan (biasanya `main`)

**Langkah B - Di VPS Hostinger (Clone dari GitHub):**
```bash
# Buat direktori aplikasi
sudo mkdir -p /var/www/inventarisasi
cd /var/www/inventarisasi

# Clone repository dari GitHub Anda
# Ganti USERNAME_ANDA dengan username GitHub Anda
# Ganti NAMA_REPO dengan nama repository yang Anda buat di step A
git clone https://github.com/USERNAME_ANDA/NAMA_REPO.git .

# Jika private repo, gunakan Personal Access Token:
# git clone https://TOKEN@github.com/USERNAME_ANDA/NAMA_REPO.git .

# Pastikan branch yang benar
git checkout main
```

> **Cara membuat GitHub Personal Access Token** (jika repo private):
> 1. Buka https://github.com/settings/tokens
> 2. Klik "Generate new token (classic)"
> 3. Pilih scope: `repo` (full control of private repositories)
> 4. Copy token dan gunakan untuk clone

### Metode Alternatif: SCP (Transfer Langsung)

**Di Emergent.sh terminal, buat archive:**
```bash
cd /app
# Buat archive (exclude node_modules dan file tidak perlu)
tar czf /tmp/inventarisasi-app.tar.gz \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='test_reports' \
  --exclude='*.pyc' \
  --exclude='backend/uploads/*' \
  --exclude='frontend/build' \
  backend/ frontend/ tests/ README.md
```

**Download file dari Emergent, lalu upload ke VPS:**
```bash
# Dari komputer lokal Anda
scp inventarisasi-app.tar.gz root@72.62.126.24:/var/www/inventarisasi/

# Di VPS
cd /var/www/inventarisasi
tar xzf inventarisasi-app.tar.gz
rm inventarisasi-app.tar.gz
```

### 3.1 Verifikasi Struktur File
```bash
ls -la /var/www/inventarisasi/
# Harus ada:
# backend/
# frontend/
# README.md
```

---

<a name="fase-4"></a>
## ⚙️ FASE 4: Setup Backend (15 menit)

### 4.1 Buat Python Virtual Environment
```bash
cd /var/www/inventarisasi/backend

# Buat virtual environment dengan Python 3.11
python3.11 -m venv venv

# Aktivasi
source venv/bin/activate

# Verifikasi
python --version
# Output: Python 3.11.x
```

### 4.2 Install Python Dependencies
```bash
# Pastikan pip terbaru
pip install --upgrade pip

# Install semua dependencies
pip install -r requirements.txt

# Install emergentintegrations (jika diperlukan)
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/

# Verifikasi key packages
pip show fastapi uvicorn motor weasyprint reportlab pillow
```

> **Jika ada error saat install WeasyPrint:**
> ```bash
> sudo apt install -y python3.11-dev libcairo2-dev pkg-config
> pip install weasyprint
> ```

### 4.3 Konfigurasi File .env Backend
```bash
# Buat/edit file .env
nano /var/www/inventarisasi/backend/.env
```

**Isi file `/var/www/inventarisasi/backend/.env`:**
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="inventarisasi_bmn"
CORS_ORIGINS="https://amanikn-inventarisasi.com,http://amanikn-inventarisasi.com"
TINIFY_API_KEY=WX6Md8zwtPLg740tmWF9j5h1s82Ydmb2
RESEND_API_KEY=re_W7pMzGpS_KWVouHVdY4pLrbqRNVrK2ogu
SENDER_EMAIL=noreply@amanikn-inventarisasi.com
JWT_SECRET=inv_mgmt_s3cur3_k3y_2026_pr0d_x7q9w2m4
```

> ⚠️ **PENTING:** 
> - `DB_NAME` bisa Anda ganti sesuai keinginan
> - `JWT_SECRET` **HARUS diganti** dengan string random yang lebih kuat untuk production!
> - `CORS_ORIGINS` sudah diset ke domain Anda

### 4.4 Buat Direktori Upload
```bash
mkdir -p /var/www/inventarisasi/backend/uploads
chmod 755 /var/www/inventarisasi/backend/uploads
```

### 4.5 Test Backend Manual
```bash
cd /var/www/inventarisasi/backend
source venv/bin/activate

# Test jalankan backend
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
# Buka terminal baru, test:
# curl http://localhost:8001/api/health
# atau curl http://localhost:8001/docs
# Ctrl+C untuk stop setelah berhasil
```

---

<a name="fase-5"></a>
## 🎨 FASE 5: Setup Frontend - Build untuk Production (15 menit)

### 5.1 Konfigurasi File .env Frontend
```bash
# Buat/edit file .env
nano /var/www/inventarisasi/frontend/.env
```

**Isi file `/var/www/inventarisasi/frontend/.env`:**
```env
REACT_APP_BACKEND_URL=https://amanikn-inventarisasi.com
```

> **Penjelasan:** Di production, Nginx akan menangani routing. 
> Frontend dan backend diakses melalui domain yang sama.
> Request ke `/api/*` akan di-proxy ke backend port 8001.

### 5.2 Install Dependencies & Build
```bash
cd /var/www/inventarisasi/frontend

# Install dependencies dengan Yarn
yarn install

# Build untuk production
yarn build

# Verifikasi build berhasil
ls -la build/
# Harus ada: index.html, static/, dll
```

> **Jika `yarn build` gagal karena memory:**
> ```bash
> # Tambah swap (untuk VPS 8GB biasanya tidak perlu)
> export NODE_OPTIONS="--max-old-space-size=4096"
> yarn build
> ```

### 5.3 Verifikasi Build
```bash
# Cek ukuran build
du -sh /var/www/inventarisasi/frontend/build/
# Cek file index.html ada
cat /var/www/inventarisasi/frontend/build/index.html | head -5
```

---

<a name="fase-6"></a>
## 🌐 FASE 6: Konfigurasi Nginx + SSL (20 menit)

### 6.1 Pastikan Domain Mengarah ke VPS
Sebelum setup SSL, pastikan DNS domain sudah benar:
```bash
# Cek DNS
dig amanikn-inventarisasi.com +short
# Harus menampilkan: 72.62.126.24

# Atau
nslookup amanikn-inventarisasi.com
```

> **Di Hostinger DNS Manager:**
> - A Record: `@` → `72.62.126.24`
> - A Record: `www` → `72.62.126.24`

### 6.2 Buat Konfigurasi Nginx (Tanpa SSL Dulu)
```bash
# Hapus default config
sudo rm -f /etc/nginx/sites-enabled/default

# Buat config baru
sudo nano /etc/nginx/sites-available/inventarisasi
```

**Isi file `/etc/nginx/sites-available/inventarisasi`:**
```nginx
# Konfigurasi untuk amanikn-inventarisasi.com
# Backend API + Frontend Static Files

# Redirect www ke non-www
server {
    listen 80;
    server_name www.amanikn-inventarisasi.com;
    return 301 http://amanikn-inventarisasi.com$request_uri;
}

server {
    listen 80;
    server_name amanikn-inventarisasi.com;

    # Batas upload file (sesuaikan jika perlu, default 1MB terlalu kecil)
    client_max_body_size 50M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # =============================================
    # BACKEND API - Proxy ke FastAPI port 8001
    # =============================================
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout untuk operasi besar (export PDF, import, dll)
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 16k;
        proxy_buffers 4 32k;
    }

    # =============================================
    # WebSocket Support (jika ada)
    # =============================================
    location /api/ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # =============================================
    # FRONTEND - Serve static React build
    # =============================================
    location / {
        root /var/www/inventarisasi/frontend/build;
        index index.html;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # =============================================
    # Upload files (jika backend serve file statis)
    # =============================================
    location /uploads/ {
        alias /var/www/inventarisasi/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }
}
```

### 6.3 Aktifkan Config & Test
```bash
# Buat symbolic link
sudo ln -s /etc/nginx/sites-available/inventarisasi /etc/nginx/sites-enabled/

# Test konfigurasi Nginx
sudo nginx -t
# Output harus: syntax is ok, test is successful

# Reload Nginx
sudo systemctl reload nginx
```

### 6.4 Install SSL Certificate dengan Let's Encrypt
```bash
# Pastikan Nginx berjalan dan port 80 terbuka
sudo certbot --nginx -d amanikn-inventarisasi.com -d www.amanikn-inventarisasi.com

# Ikuti instruksi:
# 1. Masukkan email Anda
# 2. Agree to Terms of Service
# 3. Pilih redirect HTTP to HTTPS (recommended)
```

> **Certbot akan otomatis:**
> - Membuat SSL certificate
> - Memodifikasi config Nginx untuk HTTPS
> - Setup auto-renewal

### 6.5 Verifikasi SSL Auto-Renewal
```bash
# Test auto-renewal
sudo certbot renew --dry-run

# Cek timer renewal
sudo systemctl list-timers | grep certbot
```

### 6.6 Verifikasi Nginx Final Config
```bash
# Setelah Certbot, config akan berubah. Lihat hasilnya:
sudo cat /etc/nginx/sites-available/inventarisasi

# Test & restart
sudo nginx -t
sudo systemctl restart nginx
```

---

<a name="fase-7"></a>
## 🔄 FASE 7: Setup Supervisor (Process Manager Backend) (10 menit)

### 7.1 Buat Konfigurasi Supervisor untuk Backend
```bash
sudo nano /etc/supervisor/conf.d/inventarisasi-backend.conf
```

**Isi file (v2.1 — Multi-Worker Production, Juli 2025):**
```ini
[program:inventarisasi-backend]
command=/var/www/inventarisasi/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 4 --proxy-headers --forwarded-allow-ips=127.0.0.1 --log-level info
directory=/var/www/inventarisasi/backend
user=root
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=30
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=/var/log/supervisor/inventarisasi-backend.out.log
stderr_logfile=/var/log/supervisor/inventarisasi-backend.err.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=PATH="/var/www/inventarisasi/backend/venv/bin:%(ENV_PATH)s"
```

> **⚠️ PENTING — Perubahan dari versi sebelumnya:**
> - `--workers 4` (naik dari 2) — memanfaatkan multi-core VPS untuk >50 user konkuren
> - `--reload` DIHAPUS — jangan pakai di production (bikin memory leak & restart loop)
> - `--proxy-headers` ditambah — agar backend kenali IP asli klien via nginx
>
> **Kapan menaikkan/menurunkan workers:**
> - VPS 4GB RAM + 2 core → `--workers 2` (hemat RAM)
> - VPS 8GB RAM + 4 core → `--workers 4` (default production) ← **rekomendasi saat ini**
> - VPS 16GB RAM + 8 core → `--workers 6-8` (high-traffic)
> - Formula: `workers = min(2 × CPU_cores + 1, RAM_GB / 1.5)`
>
> **Multi-worker sudah aman digunakan (sejak Juli 2025):**
> Aplikasi memakai **cross-worker WebSocket event bus** via MongoDB capped collection (`ws_events`).
> Setiap worker publish event ke capped collection, worker lain tail cursor-nya dan fanout ke WS klien
> lokal. Tidak perlu Redis, tidak perlu replica set. Latency <100ms antar worker.
> Lihat: `backend/event_bus.py` dan bagian **POST-DEPLOY VERIFICATION** di akhir dokumen.

### 7.2 Reload & Start Supervisor
```bash
# Reload konfigurasi
sudo supervisorctl reread
sudo supervisorctl update

# Start backend
sudo supervisorctl start inventarisasi-backend

# Cek status
sudo supervisorctl status
# Output: inventarisasi-backend   RUNNING   pid XXXX, uptime 0:00:XX
```

### 7.3 Cek Log Backend
```bash
# Lihat log real-time
sudo tail -f /var/log/supervisor/inventarisasi-backend.out.log

# Lihat error log
sudo tail -50 /var/log/supervisor/inventarisasi-backend.err.log
```

### 7.4 Command Supervisor yang Berguna
```bash
# Restart backend
sudo supervisorctl restart inventarisasi-backend

# Stop backend
sudo supervisorctl stop inventarisasi-backend

# Start backend
sudo supervisorctl start inventarisasi-backend

# Lihat status semua
sudo supervisorctl status

# Reload semua config
sudo supervisorctl reread && sudo supervisorctl update
```

---

<a name="fase-8"></a>
## 🔒 FASE 8: Firewall & Keamanan (10 menit)

### 8.1 Setup UFW Firewall
```bash
# Enable UFW
sudo ufw status

# Allow SSH (JANGAN LUPA INI!)
sudo ufw allow ssh
# atau: sudo ufw allow 22

# Allow HTTP & HTTPS
sudo ufw allow 80
sudo ufw allow 443

# JANGAN allow port 8001 dan 27017 dari luar!
# Backend dan MongoDB hanya diakses dari localhost

# Enable firewall
sudo ufw enable

# Verifikasi
sudo ufw status verbose
```

**Output yang diharapkan:**
```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

### 8.2 Amankan MongoDB
```bash
# MongoDB secara default hanya listen di localhost (127.0.0.1)
# Verifikasi:
grep bindIp /etc/mongod.conf
# Harus: bindIp: 127.0.0.1

# Jika ingin tambahkan authentication (opsional tapi recommended):
mongosh
```
```javascript
// Di mongosh shell:
use admin
db.createUser({
  user: "inventarisasi_admin",
  pwd: "GANTI_PASSWORD_KUAT_ANDA",
  roles: [{ role: "readWrite", db: "inventarisasi_bmn" }]
})
exit
```

> **Jika menambahkan auth MongoDB:**
> Edit `/etc/mongod.conf`:
> ```yaml
> security:
>   authorization: enabled
> ```
> Edit `.env` backend:
> ```env
> MONGO_URL="mongodb://inventarisasi_admin:PASSWORD@localhost:27017/inventarisasi_bmn?authSource=admin"
> ```
> Restart: `sudo systemctl restart mongod`

### 8.3 Set Permissions yang Benar
```bash
# Set ownership
sudo chown -R root:root /var/www/inventarisasi

# Set permissions
sudo chmod -R 755 /var/www/inventarisasi
sudo chmod 600 /var/www/inventarisasi/backend/.env
sudo chmod 600 /var/www/inventarisasi/frontend/.env
```

---

<a name="fase-9"></a>
## ✅ FASE 9: Testing & Verifikasi Final (10 menit)

### 9.1 Cek Semua Service Berjalan
```bash
echo "========================================="
echo "  FINAL VERIFICATION"
echo "========================================="

echo "1. MongoDB:"
sudo systemctl is-active mongod && echo "  ✅ Running" || echo "  ❌ Not running"

echo "2. Nginx:"
sudo systemctl is-active nginx && echo "  ✅ Running" || echo "  ❌ Not running"

echo "3. Backend (Supervisor):"
sudo supervisorctl status inventarisasi-backend

echo "4. SSL Certificate:"
sudo certbot certificates 2>/dev/null | grep -E "Domains|Expiry" || echo "  Belum ada SSL"

echo "5. Listening Ports:"
ss -tlnp | grep -E "80|443|8001|27017"
```

### 9.2 Test Backend API
```bash
# Test health endpoint (dari VPS)
curl -s http://localhost:8001/api/health 2>/dev/null || curl -s http://localhost:8001/ 

# Test via domain
curl -s https://amanikn-inventarisasi.com/api/health 2>/dev/null || echo "Coba endpoint lain"

# Test API docs
curl -s -o /dev/null -w "%{http_code}" https://amanikn-inventarisasi.com/api/docs
```

### 9.3 Test Frontend
```bash
# Test static files served
curl -s -o /dev/null -w "%{http_code}" https://amanikn-inventarisasi.com/
# Harus: 200
```

### 9.4 Test dari Browser
Buka browser dan akses:
1. ✅ `https://amanikn-inventarisasi.com` - Halaman utama
2. ✅ `https://amanikn-inventarisasi.com/api/docs` - API Documentation
3. ✅ Login dan test fitur-fitur utama

---

<a name="troubleshooting"></a>
## 🔧 Troubleshooting

### Backend Tidak Jalan
```bash
# Cek log error
sudo tail -100 /var/log/supervisor/inventarisasi-backend.err.log

# Cek manual
cd /var/www/inventarisasi/backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001
# Lihat error langsung di terminal
```

### MongoDB Tidak Konek
```bash
# Cek status
sudo systemctl status mongod

# Cek log
sudo tail -50 /var/log/mongodb/mongod.log

# Restart
sudo systemctl restart mongod
```

### Nginx Error
```bash
# Cek syntax config
sudo nginx -t

# Cek log
sudo tail -50 /var/log/nginx/error.log

# Restart
sudo systemctl restart nginx
```

### SSL Certificate Gagal
```bash
# Pastikan domain mengarah ke IP VPS
dig amanikn-inventarisasi.com

# Pastikan port 80 terbuka
sudo ufw status

# Retry certbot
sudo certbot --nginx -d amanikn-inventarisasi.com
```

### Frontend Blank/Error
```bash
# Cek apakah build ada
ls -la /var/www/inventarisasi/frontend/build/

# Cek nginx serve path
sudo nginx -T | grep root

# Cek REACT_APP_BACKEND_URL di .env frontend sebelum build
cat /var/www/inventarisasi/frontend/.env
# Jika URL salah, edit dan build ulang:
cd /var/www/inventarisasi/frontend
yarn build
```

### Import/Export/PDF Error (WeasyPrint)
```bash
# Cek dependencies WeasyPrint
source /var/www/inventarisasi/backend/venv/bin/activate
python -c "import weasyprint; print('WeasyPrint OK')"
python -c "import reportlab; print('ReportLab OK')"
python -c "from PIL import Image; print('Pillow OK')"
```

---

<a name="maintenance"></a>
## 📋 Maintenance & Backup

### Update Aplikasi (Setelah Perubahan Kode)

> ⚠️ **PENTING:** Jangan gunakan `git pull` biasa! Jika branch diverged (bercabang), 
> file-file baru tidak akan muncul dan backend bisa crash. Selalu gunakan metode **fetch + reset** di bawah ini.

**Metode Aman (Recommended):**
```bash
# 1. Backup .env files dulu (WAJIB sebelum reset!)
cp /var/www/inventarisasi/backend/.env /tmp/backend_env_backup
cp /var/www/inventarisasi/frontend/.env /tmp/frontend_env_backup

# 2. Fetch & force reset ke versi terbaru
cd /var/www/inventarisasi
git fetch origin
# GANTI 'main' dengan nama branch Anda jika berbeda
git reset --hard origin/main

# 3. Restore .env files (karena git reset menghapus perubahan lokal)
cp /tmp/backend_env_backup /var/www/inventarisasi/backend/.env
cp /tmp/frontend_env_backup /var/www/inventarisasi/frontend/.env
chmod 600 /var/www/inventarisasi/backend/.env

# 4. Update backend dependencies (jika ada perubahan)
cd /var/www/inventarisasi/backend
source venv/bin/activate
sed -i '/emergentintegrations/d' requirements.txt
pip install -r requirements.txt
deactivate

# 5. Restart backend
sudo supervisorctl restart inventarisasi-backend

# 6. Rebuild frontend (jika ada perubahan)
cd /var/www/inventarisasi/frontend
yarn install
export NODE_OPTIONS="--max-old-space-size=4096"
yarn build
# Nginx otomatis serve file baru, tidak perlu restart
```

**Atau gunakan script otomatis:**
```bash
# Script ini otomatis handle semua langkah di atas termasuk backup .env
chmod +x /var/www/inventarisasi/scripts/vps-fix.sh
sudo /var/www/inventarisasi/scripts/vps-fix.sh
```

**Kenapa `git pull` saja tidak cukup?**
- Emergent.sh kadang melakukan force-push yang mengubah history commit
- Ini menyebabkan branch lokal VPS "diverged" (bercabang) dari remote
- `git pull` biasa akan gagal atau tidak mengambil file baru
- `git fetch + git reset --hard` memastikan VPS selalu identik dengan remote

**Verifikasi setelah update:**
```bash
# Cek semua file route ada (harus 19 file)
ls /var/www/inventarisasi/backend/routes/*.py | wc -l

# Cek backend berjalan
sudo supervisorctl status inventarisasi-backend

# Cek API merespons
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/docs

# Cek log jika ada error
sudo tail -30 /var/log/supervisor/inventarisasi-backend.out.log
```

### Backup MongoDB
```bash
# Backup database
mongodump --db inventarisasi_bmn --out /root/backup/$(date +%Y%m%d)

# Restore database
mongorestore --db inventarisasi_bmn /root/backup/20260228/inventarisasi_bmn/
```

### Backup Otomatis (Cron Job)
```bash
# Edit crontab
crontab -e

# Tambahkan backup harian jam 2 pagi
0 2 * * * mongodump --db inventarisasi_bmn --out /root/backup/$(date +\%Y\%m\%d) && find /root/backup -mtime +7 -delete
```

### Monitor Server
```bash
# Cek resource usage
htop

# Cek disk usage
df -h

# Cek memory
free -m

# Cek backend logs
sudo tail -f /var/log/supervisor/inventarisasi-backend.out.log
```

---

## 📌 RINGKASAN COMMAND PENTING

| Aksi | Command |
|------|---------|
| **Update kode dari GitHub** | `cd /var/www/inventarisasi && git fetch origin && git reset --hard origin/main` |
| **Script update otomatis** | `sudo /var/www/inventarisasi/scripts/vps-fix.sh` |
| Start backend | `sudo supervisorctl start inventarisasi-backend` |
| Stop backend | `sudo supervisorctl stop inventarisasi-backend` |
| Restart backend | `sudo supervisorctl restart inventarisasi-backend` |
| Backend log | `sudo tail -f /var/log/supervisor/inventarisasi-backend.out.log` |
| Restart Nginx | `sudo systemctl restart nginx` |
| Restart MongoDB | `sudo systemctl restart mongod` |
| Nginx error log | `sudo tail -f /var/log/nginx/error.log` |
| SSL renew | `sudo certbot renew` |
| Rebuild frontend | `cd /var/www/inventarisasi/frontend && yarn build` |
| Backup DB | `mongodump --db inventarisasi_bmn --out /root/backup/` |

> ⚠️ **JANGAN** gunakan `git pull origin main` — selalu gunakan `git fetch + git reset --hard` untuk menghindari masalah branch diverged.

---

## 🎯 CHECKLIST DEPLOYMENT

- [ ] Fase 1: Bersihkan deployment lama
- [ ] Fase 2: Install Python 3.11, Node.js 20, Yarn, MongoDB 7.0, Nginx, Supervisor, Certbot
- [ ] Fase 3: Transfer file aplikasi ke VPS
- [ ] Fase 4: Setup backend (venv, pip install, .env)
- [ ] Fase 5: Setup frontend (yarn install, .env, yarn build)
- [ ] Fase 6: Konfigurasi Nginx + SSL
- [ ] Fase 7: Setup Supervisor
- [ ] Fase 8: Firewall & Keamanan
- [ ] Fase 9: Testing & Verifikasi

**Estimasi total waktu: ~2 jam**

---

## 🆕 POST-DEPLOY VERIFICATION — Fitur v2.1 (Juli 2025)

Setelah deployment selesai, verifikasi fitur stabilitas kolaborasi & performa baru:

### ✅ 1. Event Bus Cross-Worker Aktif

Setelah start supervisor, cek log backend:
```bash
sudo grep "event_bus" /var/log/supervisor/inventarisasi-backend.out.log | tail -10
```

**Log yang HARUS muncul (setiap worker):**
```
[event_bus] Using existing capped collection 'ws_events'    # atau "Created capped collection..."
[event_bus] Started
[event_bus] Tail loop starting (worker_id=worker-abc123def4)
```

Jika ada 4 workers, Anda akan lihat 4 baris `worker_id=` berbeda. Ini memastikan
cross-worker WebSocket fanout bekerja.

**Verifikasi capped collection di MongoDB:**
```bash
mongosh inventarisasi_bmn --eval 'db.getCollectionInfos({name:"ws_events"})[0].options'
# Expected output:
# { capped: true, size: 10485760, max: 20000 }
```

### ✅ 2. Multi-Worker Status Sehat

```bash
sudo supervisorctl status
ps aux | grep uvicorn | grep -v grep | wc -l
# Expected: 5 (1 master + 4 workers) untuk --workers 4
```

### ✅ 3. Test OCC (Anti Lost-Update)

Buka 2 browser/incognito dengan akun berbeda. Edit aset yang sama:
- User A save dulu → sukses
- User B save kemudian (dengan data lama) → **toast orange** "Data telah diubah pengguna lain"
  muncul + baris otomatis refresh dengan data terbaru
- Di tabel aset: baris yang konflik ada **ikon orange ⚠️** di kolom paling kiri

### ✅ 4. Test Atomic Row Lock

Buka 2 browser, klik edit baris yang sama hampir bersamaan:
- Hanya **satu** yang berhasil masuk edit mode
- Yang lain dapat peringatan "Sedang diedit oleh [nama]" (ikon kunci 🔒)

### ✅ 5. Test WebSocket Heartbeat (Anti Proxy Timeout)

Buka Developer Tools → Network → WS tab. Filter `/api/ws/`:
- Setiap 25 detik harus terlihat message masuk: `{"type":"server_ping","ts":"..."}`
- Jika tidak ada ping selama 60+ detik, koneksi akan putus → nginx/cloudflare timeout
  → perbarui config `proxy_read_timeout` di nginx ke minimal `65s`.

### ✅ 6. Test Client-Side Image Compression

Upload foto 3-5MB via form tambah aset:
- Sebelum upload harus muncul toast: `"Mengompresi N foto..."` lalu
  `"Foto dikompresi: hemat XX% bandwidth"`
- Network tab browser: payload POST /api/assets turun drastis (dari MB ke KB)
- Waktu save < 2 detik untuk 5 foto (sebelumnya: 15-30 detik)

### ✅ 7. Test Idempotency (Retry Aman)

Simulasi:
1. Edit aset, klik Simpan
2. Matikan internet tepat sebelum response datang
3. Nyalakan internet kembali → auto-retry
4. Cek MongoDB: hanya **1** dokumen untuk edit tersebut, tidak ganda

Query verifikasi:
```bash
mongosh inventarisasi_bmn --eval 'db.idempotency_keys.stats()'
```
TTL index akan auto-cleanup setelah 5 menit.

### ✅ 8. Nginx `proxy_read_timeout` untuk WebSocket

Pastikan konfigurasi nginx block `/api/ws/`:
```nginx
location /api/ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;      # 1 jam — WS long-lived connection
    proxy_send_timeout 3600s;
}
```

Restart nginx setelah perubahan:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🛠️ Troubleshooting v2.1

| Masalah | Diagnosa | Solusi |
|---------|----------|--------|
| WS disconnect setiap 60s di production | nginx/cloudflare timeout | Set `proxy_read_timeout 3600s` di nginx config |
| User A save, User B tidak dapat notif | Cross-worker fanout gagal | Cek log: `[event_bus] Tail cursor error` → restart backend |
| Toast "Konflik versi" muncul terus | User tidak refresh data | Pastikan frontend versi terbaru (OCC handling ada di `useOptimisticQueue.js`) |
| Save lambat meskipun foto kecil | Server-side Tinify round-trip | Cek API key Tinify; client compression sudah aktif jika foto <500KB skip Tinify |
| Lock tidak release setelah save | Lock TTL 5 menit | Otomatis dibersihkan; atau force: `db.row_locks.deleteMany({})` |
| ws_events growing besar | Bukan growing — sudah capped | Cek: `db.ws_events.stats().maxSize` = 10485760 |
| "Capped collection unavailable" log | Race condition saat start | Normal, hanya worker pertama yg bikin; worker lain pakai yg sudah ada |

---

*Guide dibuat Juli 2025 untuk deployment dari Emergent.sh ke Hostinger VPS*
*Versi teknologi disesuaikan persis dengan environment Emergent.sh*
*Update v2.1 (Juli 2025): Multi-worker production + Fase 1-5 collaborative stability*
