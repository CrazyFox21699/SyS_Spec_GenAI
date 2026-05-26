#!/usr/bin/env bash
# =============================================================================
# ALEX — Cai dat Ubuntu (CHAY 1 LAN DUY NHAT)
#
# Lan dau (clone tu GitHub):
#   git clone https://github.com/CrazyFox21699/SyS_Spec_GenAI.git
#   cd SyS_Spec_GenAI/ALEX
#   chmod +x setup_ubuntu.sh && ./setup_ubuntu.sh
#
# Da co code — cap nhat:
#   git pull origin main && ./setup_ubuntu.sh
#
# Huong dan day du: docs/CAI_UBUNTU_DON_GIAN.md
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=============================================="
echo "  ALEX — Setup Ubuntu"
echo "  Folder: $(pwd)"
echo "  Doc:    docs/CAI_UBUNTU_DON_GIAN.md"
echo "=============================================="
echo ""

# --- 1. Goi he thong ---
echo "[1/6] Cai goi Ubuntu (can sudo)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y python3 python3-venv python3-pip ca-certificates curl unzip git
  sudo update-ca-certificates 2>/dev/null || true
  echo "      OK"
else
  echo "      Bo qua apt — can python3 + venv"
fi

# --- 2. Quyen script ---
echo "[2/6] Cap quyen script..."
chmod +x cai_dat.sh chay.sh setup_ubuntu.sh scripts/*.sh 2>/dev/null || true
echo "      OK"

# --- 3. IP LAN ---
echo "[3/6] Sua IP LAN trong config.yaml..."
./scripts/set_lan_ip.sh

# --- 4. Thu muc runtime ---
echo "[4/6] Tao thu muc web_data + config..."
mkdir -p web_data/uploads web_data/output config
echo "      OK"

# --- 5. Cai Python venv ---
echo "[5/6] Cai .venv + pip (1-2 phut)..."
./cai_dat.sh

# --- 6. Kiem tra ---
echo "[6/6] Kiem tra ban code day du..."
if ./scripts/ubuntu_release_sync_check.sh; then
  echo "      OK"
else
  echo "      FAIL — git pull full repo, khong copy le file"
  exit 1
fi

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "=============================================="
echo "  CAI DAT XONG — 4 buoc tiep theo"
echo "=============================================="
echo ""
echo "  1) nano .env"
echo "       M365_CLIENT_SECRET=<Value tu Azure>"
echo "       chmod 600 .env"
echo ""
echo "  2) nano config.yaml"
echo "       assist.m365.client_id + tenant_id (IT cap)"
echo ""
echo "  3) ./scripts/ubuntu_m365_ssl_check.sh"
echo "       OK → buoc 4"
echo "       FAIL → dat file IT vao config/company-ca.pem, chay lai"
echo ""
echo "  4) ./chay.sh"
if [ -n "$LAN_IP" ]; then
  echo "       Browser: http://${LAN_IP}:8765/login"
else
  echo "       Browser: http://<IP-may>:8765/login"
fi
echo "       admin / Alex@2025!"
echo ""
echo "  VS Code: Remote SSH → Open Folder → $(pwd)"
echo "  Chi tiet: docs/CAI_UBUNTU_DON_GIAN.md"
echo ""
