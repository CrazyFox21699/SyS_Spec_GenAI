#!/usr/bin/env bash
# =============================================================================
# ALEX — Cai dat Ubuntu cong ty (CHAY 1 LAN DUY NHAT)
#
#   cd /home/tmc_ai_common/ALEX
#   chmod +x setup_ubuntu.sh
#   ./setup_ubuntu.sh
#
# Sau do: sua .env + config/company-ca.pem → ./chay.sh
# Huong dan ngan: docs/CAI_UBUNTU_DON_GIAN.md
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=============================================="
echo "  ALEX — Setup Ubuntu (lan dau)"
echo "  Thu muc: $(pwd)"
echo "=============================================="
echo ""

# --- 1. Goi he thong ---
echo "[1/6] Cai goi Ubuntu (can sudo)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y python3 python3-venv python3-pip ca-certificates curl unzip
  sudo update-ca-certificates 2>/dev/null || true
  echo "      OK"
else
  echo "      Bo qua apt (khong phai Ubuntu?) — can python3 + venv"
fi

# --- 2. Quyen script ---
echo "[2/6] Cap quyen script..."
chmod +x cai_dat.sh chay.sh setup_ubuntu.sh scripts/*.sh 2>/dev/null || true
echo "      OK"

# --- 3. IP LAN ---
echo "[3/6] Sua IP LAN trong config.yaml..."
./scripts/set_lan_ip.sh

# --- 4. Thu muc runtime ---
echo "[4/6] Tao thu muc web_data..."
mkdir -p web_data/uploads web_data/output config
echo "      OK"

# --- 5. Cai Python venv ---
echo "[5/6] Cai .venv + pip (co the mat 1-2 phut)..."
./cai_dat.sh

# --- 6. Kiem tra ---
echo "[6/6] Kiem tra ban code day du..."
if ./scripts/ubuntu_release_sync_check.sh; then
  echo "      OK — du file M365/SSL"
else
  echo "      FAIL — thieu file. Lay FULL folder ALEX (git pull hoac ZIP), khong copy le."
  exit 1
fi

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
ALEX_DIR=$(pwd)

echo ""
echo "=============================================="
echo "  CAI DAT XONG — lam 3 viec sau:"
echo "=============================================="
echo ""
echo "  A) File CA tu IT (bat buoc de Sign in M365 tren mang cong ty):"
echo "     cp /duong/dan/it/root-ca.pem config/company-ca.pem"
echo ""
echo "  B) Sua file .env (nano .env):"
echo "     M365_CLIENT_SECRET=<Value tu Azure>"
echo "     REQUESTS_CA_BUNDLE=${ALEX_DIR}/config/company-ca.pem"
echo "     M365_CA_BUNDLE=${ALEX_DIR}/config/company-ca.pem"
echo "     chmod 600 .env"
echo ""
echo "  C) Sua config.yaml — dien client_id + tenant_id (IT cap):"
echo "     assist.m365.client_id: \"...\""
echo "     assist.m365.tenant_id: \"...\""
echo ""
echo "  Kiem tra SSL (sau khi co company-ca.pem):"
echo "     ./scripts/ubuntu_m365_ssl_check.sh"
echo ""
echo "  Chay server:"
echo "     ./chay.sh"
echo ""
echo "  Mo browser:"
if [ -n "$LAN_IP" ]; then
  echo "     http://${LAN_IP}:8765/login"
else
  echo "     http://<IP-may>:8765/login"
fi
echo "     Dang nhap: admin / Alex@2025!"
echo ""
echo "  Sign in Microsoft 365: tab Review (can work account + license Copilot)"
echo ""
echo "  Huong dan: docs/CAI_UBUNTU_DON_GIAN.md"
echo "  Gui IT:    docs/IT_REQUEST_CHECKLIST.md"
echo ""
