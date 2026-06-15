#!/bin/bash
# ============================================
# Script Deploy Aplikasi setelah file ditransfer
# Jalankan SETELAH vps-setup.sh dan transfer file
# Usage: chmod +x vps-deploy.sh && sudo ./vps-deploy.sh
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/var/www/inventarisasi"
DOMAIN="amanikn-inventarisasi.com"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Deploy Aplikasi Inventarisasi BMN         ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================
# STEP 1: Setup Backend
# ============================================
echo -e "${YELLOW}[1/5] Setting up Backend...${NC}"
cd ${APP_DIR}/backend

# Buat virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>/dev/null || true

# Buat direktori upload
mkdir -p uploads

# Setup .env backend
cat > .env << 'ENVEOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="inventarisasi_bmn"
CORS_ORIGINS="https://amanikn-inventarisasi.com,http://amanikn-inventarisasi.com"
TINIFY_API_KEY=WX6Md8zwtPLg740tmWF9j5h1s82Ydmb2
RESEND_API_KEY=re_W7pMzGpS_KWVouHVdY4pLrbqRNVrK2ogu
SENDER_EMAIL=noreply@amanikn-inventarisasi.com
JWT_SECRET=inv_mgmt_s3cur3_k3y_2026_pr0d_x7q9w2m4
ENVEOF

chmod 600 .env
deactivate

echo -e "${GREEN}  Backend setup complete${NC}"

# ============================================
# STEP 2: Setup Frontend
# ============================================
echo -e "${YELLOW}[2/5] Setting up Frontend (this may take a while)...${NC}"
cd ${APP_DIR}/frontend

# Setup .env frontend
cat > .env << ENVEOF
REACT_APP_BACKEND_URL=https://${DOMAIN}
ENVEOF

# Install dependencies
yarn install

# Build for production
export NODE_OPTIONS="--max-old-space-size=4096"
yarn build

echo -e "${GREEN}  Frontend build complete${NC}"

# ============================================
# STEP 3: Setup Nginx
# ============================================
echo -e "${YELLOW}[3/5] Configuring Nginx...${NC}"

# Hapus default
rm -f /etc/nginx/sites-enabled/default

# Buat config
cat > /etc/nginx/sites-available/inventarisasi << NGINXEOF
# Redirect www ke non-www
server {
    listen 80;
    server_name www.${DOMAIN};
    return 301 http://${DOMAIN}\$request_uri;
}

server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 50M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        proxy_buffering on;
        proxy_buffer_size 16k;
        proxy_buffers 4 32k;
    }

    # WebSocket
    location /api/ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    # Frontend static files
    location / {
        root ${APP_DIR}/frontend/build;
        index index.html;
        try_files \$uri \$uri/ /index.html;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Upload files
    location /uploads/ {
        alias ${APP_DIR}/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }
}
NGINXEOF

# Enable site
ln -sf /etc/nginx/sites-available/inventarisasi /etc/nginx/sites-enabled/

# Test & reload
nginx -t
systemctl reload nginx

echo -e "${GREEN}  Nginx configured${NC}"

# ============================================
# STEP 4: Setup Supervisor
# ============================================
echo -e "${YELLOW}[4/5] Configuring Supervisor...${NC}"

cat > /etc/supervisor/conf.d/inventarisasi-backend.conf << SUPEOF
[program:inventarisasi-backend]
command=${APP_DIR}/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
directory=${APP_DIR}/backend
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
environment=PATH="${APP_DIR}/backend/venv/bin:%(ENV_PATH)s"
SUPEOF

supervisorctl reread
supervisorctl update
supervisorctl start inventarisasi-backend

echo -e "${GREEN}  Supervisor configured & backend started${NC}"

# ============================================
# STEP 5: Setup Firewall
# ============================================
echo -e "${YELLOW}[5/5] Configuring Firewall...${NC}"

ufw allow ssh
ufw allow 80
ufw allow 443
echo "y" | ufw enable

echo -e "${GREEN}  Firewall configured${NC}"

# ============================================
# FINAL
# ============================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SELESAI!                       ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Service status:"
echo "  MongoDB   : $(systemctl is-active mongod)"
echo "  Nginx     : $(systemctl is-active nginx)"
echo "  Backend   : $(supervisorctl status inventarisasi-backend 2>/dev/null | awk '{print $2}')"
echo ""
echo -e "${YELLOW}LANGKAH TERAKHIR - Setup SSL:${NC}"
echo "  sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
echo ""
echo -e "${YELLOW}Test akses:${NC}"
echo "  curl http://${DOMAIN}/api/docs"
echo "  Buka browser: http://${DOMAIN}"
echo ""
