#!/bin/bash
# ============================================
# VPS FIX SCRIPT - Perbaikan Sinkronisasi Git & Verifikasi Lengkap
# 
# Masalah: Branch VPS diverged dari remote, file-file baru tidak muncul
# Solusi: Force reset ke versi terbaru dari remote
#
# Usage: 
#   chmod +x /var/www/inventarisasi/scripts/vps-fix.sh
#   sudo /var/www/inventarisasi/scripts/vps-fix.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

APP_DIR="/var/www/inventarisasi"
BACKUP_DIR="/root/backup_env_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  VPS FIX - Sinkronisasi & Perbaikan        ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================
# STEP 1: Backup file penting (yang TIDAK di-git)
# ============================================
echo -e "${YELLOW}[1/8] Backup file penting...${NC}"

mkdir -p "${BACKUP_DIR}"

# Backup .env files
if [ -f "${APP_DIR}/backend/.env" ]; then
    cp "${APP_DIR}/backend/.env" "${BACKUP_DIR}/backend.env"
    echo -e "  ${GREEN}✅ backend/.env di-backup${NC}"
else
    echo -e "  ${YELLOW}⚠️  backend/.env tidak ditemukan${NC}"
fi

if [ -f "${APP_DIR}/frontend/.env" ]; then
    cp "${APP_DIR}/frontend/.env" "${BACKUP_DIR}/frontend.env"
    echo -e "  ${GREEN}✅ frontend/.env di-backup${NC}"
else
    echo -e "  ${YELLOW}⚠️  frontend/.env tidak ditemukan${NC}"
fi

# Backup uploads (hanya logos, yang lain di GridFS)
if [ -d "${APP_DIR}/backend/uploads/logos" ]; then
    cp -r "${APP_DIR}/backend/uploads/logos" "${BACKUP_DIR}/logos"
    echo -e "  ${GREEN}✅ uploads/logos di-backup${NC}"
fi

echo -e "  ${CYAN}Backup disimpan di: ${BACKUP_DIR}${NC}"

# ============================================
# STEP 2: Force reset git ke versi terbaru
# ============================================
echo ""
echo -e "${YELLOW}[2/8] Sinkronisasi Git (force reset ke remote)...${NC}"

cd "${APP_DIR}"

# Fetch semua perubahan terbaru dari remote
echo -e "  Fetching from remote..."
git fetch origin

# Cek status sebelum reset
LOCAL_COMMIT=$(git rev-parse HEAD 2>/dev/null)
REMOTE_COMMIT=$(git rev-parse origin/Deploy_Hostinger_VPS 2>/dev/null)

echo -e "  Commit lokal  : ${LOCAL_COMMIT:0:7}"
echo -e "  Commit remote : ${REMOTE_COMMIT:0:7}"

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo -e "  ${GREEN}✅ Sudah sinkron!${NC}"
else
    echo -e "  ${YELLOW}⚠️  Diverged - melakukan force reset...${NC}"
    git reset --hard origin/Deploy_Hostinger_VPS
    echo -e "  ${GREEN}✅ Git berhasil di-reset ke versi terbaru${NC}"
fi

# Verify current commit
NEW_COMMIT=$(git rev-parse HEAD 2>/dev/null)
echo -e "  Commit aktif  : ${NEW_COMMIT:0:7}"

# ============================================
# STEP 3: Restore file .env
# ============================================
echo ""
echo -e "${YELLOW}[3/8] Restore file .env...${NC}"

# Restore backend .env
if [ -f "${BACKUP_DIR}/backend.env" ]; then
    cp "${BACKUP_DIR}/backend.env" "${APP_DIR}/backend/.env"
    chmod 600 "${APP_DIR}/backend/.env"
    echo -e "  ${GREEN}✅ backend/.env di-restore${NC}"
else
    # Create default .env if it doesn't exist
    cat > "${APP_DIR}/backend/.env" << 'ENVEOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="inventarisasi_bmn"
CORS_ORIGINS="https://amanikn-inventarisasi.com,http://amanikn-inventarisasi.com"
TINIFY_API_KEY=WX6Md8zwtPLg740tmWF9j5h1s82Ydmb2
RESEND_API_KEY=re_W7pMzGpS_KWVouHVdY4pLrbqRNVrK2ogu
SENDER_EMAIL=noreply@amanikn-inventarisasi.com
JWT_SECRET=inv_mgmt_s3cur3_k3y_2026_pr0d_x7q9w2m4
ENVEOF
    chmod 600 "${APP_DIR}/backend/.env"
    echo -e "  ${YELLOW}⚠️  backend/.env dibuat baru (default)${NC}"
fi

# Restore frontend .env
if [ -f "${BACKUP_DIR}/frontend.env" ]; then
    cp "${BACKUP_DIR}/frontend.env" "${APP_DIR}/frontend/.env"
    echo -e "  ${GREEN}✅ frontend/.env di-restore${NC}"
else
    cat > "${APP_DIR}/frontend/.env" << 'ENVEOF'
REACT_APP_BACKEND_URL=https://amanikn-inventarisasi.com
ENVEOF
    echo -e "  ${YELLOW}⚠️  frontend/.env dibuat baru (default)${NC}"
fi

# Restore logos
if [ -d "${BACKUP_DIR}/logos" ]; then
    mkdir -p "${APP_DIR}/backend/uploads/logos"
    cp -r "${BACKUP_DIR}/logos/"* "${APP_DIR}/backend/uploads/logos/" 2>/dev/null || true
    echo -e "  ${GREEN}✅ uploads/logos di-restore${NC}"
fi

# Tambahkan API keys baru ke backend .env jika belum ada
ENV_FILE="${APP_DIR}/backend/.env"
add_env_if_missing() {
    local key="$1"
    local value="$2"
    if ! grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
        echo "${key}=${value}" >> "${ENV_FILE}"
        echo -e "  ${CYAN}+ Ditambahkan: ${key}${NC}"
    fi
}

add_env_if_missing "COMPRESTO_API_KEY" "ck_ftwwJBRiofLUICf9O9I8qCX6upXgEPKX"
add_env_if_missing "UPLOADCARE_PUBLIC_KEY" "da1f1b4189357675173a"
add_env_if_missing "ILOVEAPI_PUBLIC_KEY" "project_public_1d28556af9962529937217591602fe9d_r656956aaff5765b9c189bb8d6b80f32ba370"
add_env_if_missing "ILOVEAPI_SECRET_KEY" "secret_key_006da3731d10909ea16490b8846ffd8f_uname90245b6fde6990f363066570644381a7"
add_env_if_missing "WHIPDOC_API_KEY" "pdf_live_kXs5zajHDuXLWgDJ5weXeLLvF88wFJSM"

# ============================================
# STEP 4: Verifikasi semua file backend
# ============================================
echo ""
echo -e "${YELLOW}[4/8] Verifikasi file backend...${NC}"

MISSING_FILES=0

# Required route files
ROUTE_FILES=(
    "backend/routes/__init__.py"
    "backend/routes/activities.py"
    "backend/routes/assets.py"
    "backend/routes/audit.py"
    "backend/routes/auth.py"
    "backend/routes/backup.py"
    "backend/routes/batch.py"
    "backend/routes/cards.py"
    "backend/routes/categories.py"
    "backend/routes/documents.py"
    "backend/routes/exports.py"
    "backend/routes/imports.py"
    "backend/routes/media.py"
    "backend/routes/pdf_compress.py"
    "backend/routes/reports.py"
    "backend/routes/templates.py"
    "backend/routes/users.py"
    "backend/routes/validation.py"
    "backend/routes/websocket.py"
)

# Core backend files
CORE_FILES=(
    "backend/server.py"
    "backend/db.py"
    "backend/models.py"
    "backend/shared_utils.py"
    "backend/auth_utils.py"
    "backend/requirements.txt"
)

# Template files
TEMPLATE_FILES=(
    "backend/templates/executive_summary.html"
    "backend/templates/executive_summary_data.html"
    "backend/templates/laporan_satker.html"
    "backend/templates/laporan_satker_v2.html"
)

# Frontend key files
FRONTEND_FILES=(
    "frontend/package.json"
    "frontend/src/App.js"
    "frontend/src/index.js"
    "frontend/src/pages/DashboardPage.jsx"
    "frontend/src/pages/ActivitySelectionPage.jsx"
    "frontend/src/pages/LoginPage.jsx"
)

echo -e "  ${CYAN}--- Route files (19 files) ---${NC}"
for f in "${ROUTE_FILES[@]}"; do
    if [ -f "${APP_DIR}/${f}" ]; then
        echo -e "  ${GREEN}✅ ${f}${NC}"
    else
        echo -e "  ${RED}❌ MISSING: ${f}${NC}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

echo -e "  ${CYAN}--- Core backend files ---${NC}"
for f in "${CORE_FILES[@]}"; do
    if [ -f "${APP_DIR}/${f}" ]; then
        echo -e "  ${GREEN}✅ ${f}${NC}"
    else
        echo -e "  ${RED}❌ MISSING: ${f}${NC}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

echo -e "  ${CYAN}--- Template files ---${NC}"
for f in "${TEMPLATE_FILES[@]}"; do
    if [ -f "${APP_DIR}/${f}" ]; then
        echo -e "  ${GREEN}✅ ${f}${NC}"
    else
        echo -e "  ${RED}❌ MISSING: ${f}${NC}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

echo -e "  ${CYAN}--- Frontend key files ---${NC}"
for f in "${FRONTEND_FILES[@]}"; do
    if [ -f "${APP_DIR}/${f}" ]; then
        echo -e "  ${GREEN}✅ ${f}${NC}"
    else
        echo -e "  ${RED}❌ MISSING: ${f}${NC}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

if [ $MISSING_FILES -gt 0 ]; then
    echo -e "  ${RED}❌ Ada ${MISSING_FILES} file yang hilang! Periksa git status.${NC}"
else
    echo -e "  ${GREEN}✅ Semua file lengkap (0 missing)${NC}"
fi

# ============================================
# STEP 5: Verifikasi konfigurasi penting
# ============================================
echo ""
echo -e "${YELLOW}[5/8] Verifikasi konfigurasi...${NC}"

# Check TEMPLATES_DIR di reports.py (bukan media.py!)
if grep -q "TEMPLATES_DIR" "${APP_DIR}/backend/routes/reports.py"; then
    echo -e "  ${GREEN}✅ TEMPLATES_DIR ada di reports.py (benar)${NC}"
else
    echo -e "  ${RED}❌ TEMPLATES_DIR tidak ditemukan di reports.py${NC}"
fi

# Check pdf_compress_router di pdf_compress.py
if [ -f "${APP_DIR}/backend/routes/pdf_compress.py" ]; then
    if grep -q "pdf_compress_router" "${APP_DIR}/backend/routes/pdf_compress.py"; then
        echo -e "  ${GREEN}✅ pdf_compress_router terdefinisi${NC}"
    else
        echo -e "  ${RED}❌ pdf_compress_router tidak ditemukan di pdf_compress.py${NC}"
    fi
fi

# Check media_router di media.py
if grep -q "media_router" "${APP_DIR}/backend/routes/media.py"; then
    echo -e "  ${GREEN}✅ media_router terdefinisi di media.py${NC}"
else
    echo -e "  ${RED}❌ media_router tidak ditemukan di media.py${NC}"
fi

# Check server.py imports all routers
ROUTER_IMPORTS=(
    "from routes.media import media_router"
    "from routes.pdf_compress import pdf_compress_router"
    "from routes.reports import reports_router"
    "from routes.exports import exports_router"
    "from routes.batch import batch_router"
    "from routes.documents import documents_router"
    "from routes.backup import backup_router"
)

for imp in "${ROUTER_IMPORTS[@]}"; do
    if grep -q "$imp" "${APP_DIR}/backend/server.py"; then
        echo -e "  ${GREEN}✅ ${imp}${NC}"
    else
        echo -e "  ${RED}❌ Missing import: ${imp}${NC}"
    fi
done

# Check no hardcoded /app/ paths
HARDCODED=$(grep -rn '"/app/' "${APP_DIR}/backend/" --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "test" | grep -v ".pyc" || true)
if [ -z "$HARDCODED" ]; then
    echo -e "  ${GREEN}✅ Tidak ada hardcoded /app/ path${NC}"
else
    echo -e "  ${YELLOW}⚠️  Ditemukan hardcoded path:${NC}"
    echo "$HARDCODED"
fi

# ============================================
# STEP 6: Update backend dependencies
# ============================================
echo ""
echo -e "${YELLOW}[6/8] Update backend dependencies...${NC}"

cd "${APP_DIR}/backend"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "  ${YELLOW}⚠️  venv tidak ada, membuat baru...${NC}"
    python3.11 -m venv venv
fi

source venv/bin/activate

# Remove emergentintegrations from requirements (not needed on VPS)
sed -i '/emergentintegrations/d' requirements.txt 2>/dev/null || true

# Install/update dependencies
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>&1 | tail -5
echo -e "  ${GREEN}✅ Dependencies terinstal${NC}"

# ============================================
# STEP 7: Test Python imports
# ============================================
echo ""
echo -e "${YELLOW}[7/8] Test Python imports...${NC}"

cd "${APP_DIR}/backend"

# Test critical imports
python3 -c "
import sys
errors = []

# Test core imports
try:
    from pathlib import Path
    import os
    os.chdir('${APP_DIR}/backend')
    
    # Add backend to path
    sys.path.insert(0, '${APP_DIR}/backend')
    
    from dotenv import load_dotenv
    load_dotenv('${APP_DIR}/backend/.env')
    
    print('  ✅ dotenv loaded')
except Exception as e:
    errors.append(f'dotenv: {e}')
    print(f'  ❌ dotenv: {e}')

try:
    from fastapi import FastAPI, APIRouter
    print('  ✅ fastapi OK')
except Exception as e:
    errors.append(f'fastapi: {e}')
    print(f'  ❌ fastapi: {e}')

try:
    import motor.motor_asyncio
    print('  ✅ motor OK')
except Exception as e:
    errors.append(f'motor: {e}')
    print(f'  ❌ motor: {e}')

try:
    from PIL import Image
    print('  ✅ Pillow OK')
except Exception as e:
    errors.append(f'Pillow: {e}')
    print(f'  ❌ Pillow: {e}')

try:
    import reportlab
    print('  ✅ reportlab OK')
except Exception as e:
    errors.append(f'reportlab: {e}')
    print(f'  ❌ reportlab: {e}')

try:
    import weasyprint
    print('  ✅ weasyprint OK')
except Exception as e:
    errors.append(f'weasyprint: {e}')
    print(f'  ❌ weasyprint: {e}')

try:
    from jinja2 import Environment, FileSystemLoader
    print('  ✅ jinja2 OK')
except Exception as e:
    errors.append(f'jinja2: {e}')
    print(f'  ❌ jinja2: {e}')

try:
    import openpyxl
    print('  ✅ openpyxl OK')
except Exception as e:
    errors.append(f'openpyxl: {e}')
    print(f'  ❌ openpyxl: {e}')

try:
    import xlsxwriter
    print('  ✅ xlsxwriter OK')
except Exception as e:
    errors.append(f'xlsxwriter: {e}')
    print(f'  ❌ xlsxwriter: {e}')

try:
    import httpx
    print('  ✅ httpx OK')
except Exception as e:
    errors.append(f'httpx: {e}')
    print(f'  ❌ httpx: {e}')

try:
    import tinify
    print('  ✅ tinify OK')
except Exception as e:
    errors.append(f'tinify: {e}')
    print(f'  ❌ tinify: {e}')

try:
    import resend
    print('  ✅ resend OK')
except Exception as e:
    errors.append(f'resend: {e}')
    print(f'  ❌ resend: {e}')

try:
    from slowapi import Limiter
    print('  ✅ slowapi OK')
except Exception as e:
    errors.append(f'slowapi: {e}')
    print(f'  ❌ slowapi: {e}')

try:
    import websockets
    print('  ✅ websockets OK')
except Exception as e:
    errors.append(f'websockets: {e}')
    print(f'  ❌ websockets: {e}')

if errors:
    print(f'\n  ❌ {len(errors)} errors found!')
    sys.exit(1)
else:
    print(f'\n  ✅ Semua imports berhasil!')
"

deactivate

# ============================================
# STEP 8: Restart backend & verifikasi
# ============================================
echo ""
echo -e "${YELLOW}[8/8] Restart backend & verifikasi...${NC}"

# Ensure upload directories exist
mkdir -p "${APP_DIR}/backend/uploads/logos"

# Restart backend
sudo supervisorctl restart inventarisasi-backend 2>/dev/null || {
    echo -e "  ${YELLOW}⚠️  Supervisor restart gagal, coba reread + update...${NC}"
    sudo supervisorctl reread
    sudo supervisorctl update
    sudo supervisorctl start inventarisasi-backend 2>/dev/null || true
}

# Wait for backend to start
echo -e "  Menunggu backend start (10 detik)..."
sleep 10

# Check backend status
BACKEND_STATUS=$(sudo supervisorctl status inventarisasi-backend 2>/dev/null | awk '{print $2}')
if [ "$BACKEND_STATUS" = "RUNNING" ]; then
    echo -e "  ${GREEN}✅ Backend RUNNING${NC}"
else
    echo -e "  ${RED}❌ Backend status: ${BACKEND_STATUS}${NC}"
    echo -e "  ${YELLOW}Cek log error:${NC}"
    # Try both possible log file locations
    if [ -f "/var/log/supervisor/inventarisasi-backend.err.log" ]; then
        tail -30 /var/log/supervisor/inventarisasi-backend.err.log
    elif [ -f "/var/log/supervisor/inventarisasi-backend.out.log" ]; then
        tail -30 /var/log/supervisor/inventarisasi-backend.out.log
    else
        echo -e "  ${YELLOW}Log file tidak ditemukan. Coba cek manual:${NC}"
        echo -e "  ls -la /var/log/supervisor/"
    fi
fi

# Test API endpoints
echo ""
echo -e "  ${CYAN}--- Test API Endpoints ---${NC}"

test_endpoint() {
    local path="$1"
    local name="$2"
    local code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001${path}" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo -e "  ${GREEN}✅ ${name} (HTTP ${code})${NC}"
    elif [ "$code" = "401" ] || [ "$code" = "422" ]; then
        echo -e "  ${GREEN}✅ ${name} (HTTP ${code} - auth required, endpoint aktif)${NC}"
    elif [ "$code" = "000" ]; then
        echo -e "  ${RED}❌ ${name} (Server tidak merespons)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  ${name} (HTTP ${code})${NC}"
    fi
}

test_endpoint "/api/docs" "API Docs"
test_endpoint "/api/compression-quotas" "Compression Quotas"
test_endpoint "/api/pdf-compression-quotas" "PDF Compression Quotas"
test_endpoint "/api/inventory/classifications" "Inventory Classifications"

# ============================================
# SUMMARY
# ============================================
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  RINGKASAN                                 ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Git info
echo -e "  Git commit : $(git rev-parse --short HEAD)"
echo -e "  Git branch : $(git branch --show-current)"

# Service status
echo ""
echo -e "  Service Status:"
echo -e "    MongoDB   : $(systemctl is-active mongod 2>/dev/null || echo 'unknown')"
echo -e "    Nginx     : $(systemctl is-active nginx 2>/dev/null || echo 'unknown')"
echo -e "    Backend   : $(sudo supervisorctl status inventarisasi-backend 2>/dev/null | awk '{print $2}' || echo 'unknown')"

echo ""
echo -e "  Backup .env : ${BACKUP_DIR}"

if [ $MISSING_FILES -eq 0 ]; then
    echo ""
    echo -e "  ${GREEN}🎉 Semua file lengkap dan tersinkronisasi!${NC}"
else
    echo ""
    echo -e "  ${RED}⚠️  Ada ${MISSING_FILES} file yang hilang.${NC}"
    echo -e "  ${YELLOW}Coba: git checkout origin/Deploy_Hostinger_VPS -- <file_path>${NC}"
fi

echo ""
echo -e "${YELLOW}LANGKAH SELANJUTNYA:${NC}"
echo -e "  1. Jika backend sudah RUNNING, rebuild frontend:"
echo -e "     cd ${APP_DIR}/frontend && yarn install && yarn build"
echo -e ""
echo -e "  2. Jika ada error, cek log:"
echo -e "     sudo tail -50 /var/log/supervisor/inventarisasi-backend.out.log"
echo -e "     sudo tail -50 /var/log/supervisor/inventarisasi-backend.err.log"
echo -e ""
echo -e "  3. Untuk update berikutnya, gunakan:"
echo -e "     cd ${APP_DIR} && git fetch origin && git reset --hard origin/Deploy_Hostinger_VPS"
echo -e "     sudo supervisorctl restart inventarisasi-backend"
echo ""
