#!/bin/bash
# ============================================
# UPDATE SCRIPT - Batch 1-6 Semua Optimasi
# Jalankan di VPS setelah git pull
# Usage: chmod +x update-all.sh && sudo ./update-all.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

APP_DIR="/var/www/inventarisasi"

echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  UPDATE APLIKASI - Batch 1-6 Optimasi     ${NC}"
echo -e "${YELLOW}============================================${NC}"
echo ""

# ============================================
# STEP 1: Pull latest code (handle diverged branches)
# ============================================
echo -e "${YELLOW}[1/7] Pulling latest code...${NC}"
cd ${APP_DIR}

# Backup .env files before any git operation
cp ${APP_DIR}/backend/.env /tmp/backend_env_backup 2>/dev/null || true
cp ${APP_DIR}/frontend/.env /tmp/frontend_env_backup 2>/dev/null || true

# Check if branches have diverged
git fetch origin
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/Deploy_Hostinger_VPS 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}  ✅ Already up to date${NC}"
else
    # Check if branches diverged
    MERGE_BASE=$(git merge-base HEAD origin/Deploy_Hostinger_VPS 2>/dev/null || echo "none")
    if [ "$MERGE_BASE" = "$LOCAL" ]; then
        # Simple fast-forward
        git pull origin Deploy_Hostinger_VPS
        echo -e "${GREEN}  ✅ Code updated (fast-forward)${NC}"
    else
        # Branches diverged - force reset
        echo -e "${YELLOW}  ⚠️  Branches diverged - force resetting to remote...${NC}"
        git reset --hard origin/Deploy_Hostinger_VPS
        echo -e "${GREEN}  ✅ Code force-updated to latest remote${NC}"
    fi
fi

# Restore .env files
cp /tmp/backend_env_backup ${APP_DIR}/backend/.env 2>/dev/null || true
cp /tmp/frontend_env_backup ${APP_DIR}/frontend/.env 2>/dev/null || true
chmod 600 ${APP_DIR}/backend/.env 2>/dev/null || true
echo -e "${GREEN}  ✅ .env files preserved${NC}"

# ============================================
# STEP 2: Verify critical files exist
# ============================================
echo -e "${YELLOW}[2/7] Verifying critical files...${NC}"

MISSING=0
CRITICAL_FILES=(
    "backend/server.py"
    "backend/db.py"
    "backend/shared_utils.py"
    "backend/routes/media.py"
    "backend/routes/pdf_compress.py"
    "backend/routes/reports.py"
    "backend/routes/exports.py"
    "backend/routes/batch.py"
    "backend/routes/documents.py"
    "backend/routes/backup.py"
    "backend/templates/executive_summary.html"
    "backend/templates/laporan_satker.html"
    "backend/templates/laporan_satker_v2.html"
)

for f in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "${APP_DIR}/${f}" ]; then
        echo -e "${RED}  ❌ MISSING: ${f}${NC}"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -eq 0 ]; then
    echo -e "${GREEN}  ✅ All critical files present${NC}"
else
    echo -e "${RED}  ❌ ${MISSING} critical files missing! Run vps-fix.sh instead.${NC}"
    echo -e "${YELLOW}  sudo ${APP_DIR}/scripts/vps-fix.sh${NC}"
    exit 1
fi

# Fix hardcoded paths (legacy check)
if grep -q 'FileSystemLoader("/app/backend/templates")' ${APP_DIR}/backend/routes/reports.py 2>/dev/null; then
    if ! grep -q "TEMPLATES_DIR" ${APP_DIR}/backend/routes/reports.py; then
        sed -i '7a import os\nfrom pathlib import Path\n\n# Template directory - relative path\nTEMPLATES_DIR = str(Path(__file__).resolve().parent.parent / "templates")' ${APP_DIR}/backend/routes/reports.py
    fi
    sed -i 's|FileSystemLoader("/app/backend/templates")|FileSystemLoader(TEMPLATES_DIR)|g' ${APP_DIR}/backend/routes/reports.py
    echo -e "${GREEN}  ✅ Hardcoded paths fixed${NC}"
else
    echo -e "${GREEN}  ✅ Paths already correct${NC}"
fi

# ============================================
# STEP 3: Update backend .env (tambah API keys baru)
# ============================================
echo -e "${YELLOW}[3/7] Updating backend .env...${NC}"

ENV_FILE="${APP_DIR}/backend/.env"

# Tambahkan key baru jika belum ada
add_env_if_missing() {
    local key="$1"
    local value="$2"
    if ! grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
        echo "${key}=${value}" >> "${ENV_FILE}"
        echo "  + Added ${key}"
    else
        echo "  = ${key} already exists"
    fi
}

add_env_if_missing "COMPRESTO_API_KEY" "ck_ftwwJBRiofLUICf9O9I8qCX6upXgEPKX"
add_env_if_missing "UPLOADCARE_PUBLIC_KEY" "da1f1b4189357675173a"
add_env_if_missing "ILOVEAPI_PUBLIC_KEY" "project_public_1d28556af9962529937217591602fe9d_r656956aaff5765b9c189bb8d6b80f32ba370"
add_env_if_missing "ILOVEAPI_SECRET_KEY" "secret_key_006da3731d10909ea16490b8846ffd8f_uname90245b6fde6990f363066570644381a7"
add_env_if_missing "WHIPDOC_API_KEY" "pdf_live_kXs5zajHDuXLWgDJ5weXeLLvF88wFJSM"

chmod 600 "${ENV_FILE}"
echo -e "${GREEN}  ✅ Backend .env updated${NC}"

# ============================================
# STEP 4: Update backend dependencies
# ============================================
echo -e "${YELLOW}[4/7] Updating backend dependencies...${NC}"
cd ${APP_DIR}/backend
source venv/bin/activate

# Remove emergentintegrations if present in requirements
sed -i '/emergentintegrations/d' requirements.txt

pip install -q -r requirements.txt
deactivate
echo -e "${GREEN}  ✅ Backend dependencies updated${NC}"

# ============================================
# STEP 5: Restart backend
# ============================================
echo -e "${YELLOW}[5/7] Restarting backend...${NC}"
sudo supervisorctl restart inventarisasi-backend
sleep 3

# Verify backend is running
if sudo supervisorctl status inventarisasi-backend | grep -q "RUNNING"; then
    echo -e "${GREEN}  ✅ Backend running${NC}"
else
    echo -e "${RED}  ❌ Backend failed! Check logs:${NC}"
    tail -20 /var/log/supervisor/inventarisasi-backend.out.log
    exit 1
fi

# ============================================
# STEP 6: Update frontend .env & rebuild
# ============================================
echo -e "${YELLOW}[6/7] Rebuilding frontend (ini butuh waktu ~2-3 menit)...${NC}"
cd ${APP_DIR}/frontend

# Pastikan .env benar
cat > .env << 'ENVEOF'
REACT_APP_BACKEND_URL=https://amanikn-inventarisasi.com
ENVEOF

# Fix title di index.html
sed -i 's/<title>Emergent | Fullstack App<\/title>/<title>AMAN | Aplikasi Manajemen Aset Negara<\/title>/' public/index.html 2>/dev/null || true
sed -i 's/A product of emergent.sh/AMAN - Aplikasi Manajemen Aset Negara | Inventory Master/' public/index.html 2>/dev/null || true
sed -i 's/Made with Emergent/Inventory Master/' public/index.html 2>/dev/null || true

# Install deps & build
yarn install --frozen-lockfile 2>/dev/null || yarn install
export NODE_OPTIONS="--max-old-space-size=4096"
yarn build

if [ -f "build/index.html" ]; then
    echo -e "${GREEN}  ✅ Frontend build successful${NC}"
else
    echo -e "${RED}  ❌ Frontend build failed!${NC}"
    exit 1
fi

# ============================================
# STEP 7: Verifikasi
# ============================================
echo -e "${YELLOW}[7/7] Verifikasi...${NC}"

# Test backend API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/compression-quotas)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  ✅ API /compression-quotas OK${NC}"
else
    echo -e "${RED}  ❌ API /compression-quotas failed (HTTP $HTTP_CODE)${NC}"
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/pdf-compression-quotas)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  ✅ API /pdf-compression-quotas OK${NC}"
else
    echo -e "${RED}  ❌ API /pdf-compression-quotas failed (HTTP $HTTP_CODE)${NC}"
fi

# Check services
echo ""
echo "Service Status:"
echo "  MongoDB   : $(systemctl is-active mongod)"
echo "  Nginx     : $(systemctl is-active nginx)"
echo "  Backend   : $(sudo supervisorctl status inventarisasi-backend | awk '{print $2}')"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  UPDATE SELESAI!                           ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Fitur yang diupdate:"
echo "  ✅ Gallery Virtualization (500+ data tanpa lag)"
echo "  ✅ Scroll to Top + Posisi Memory"
echo "  ✅ OG Meta Tags (WhatsApp preview)"
echo "  ✅ Favicon & App Icons"
echo "  ✅ Foto kegiatan: thumbnail + kompres Tinify"
echo "  ✅ Code Splitting (lazy loading halaman)"
echo "  ✅ Service Worker v3 (Stale-While-Revalidate)"
echo "  ✅ Kompresi foto fallback: Tinify → Compresto → Uploadcare → Lokal"
echo "  ✅ Kompresi PDF: iLoveAPI → WhipDoc"
echo "  ✅ Quota monitoring untuk semua service"
echo ""
echo "Buka: https://amanikn-inventarisasi.com"
echo ""
