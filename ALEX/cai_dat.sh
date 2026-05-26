#!/usr/bin/env bash
# Cài ALEX lần đầu trên Ubuntu công ty — chạy 1 lần duy nhất.
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=== ALEX — Cai dat (Ubuntu) ==="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Chua co python3. Chay:"
  echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip curl"
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  chmod 600 .env 2>/dev/null || true
  echo "Da tao .env tu .env.example — hay dien M365_CLIENT_SECRET truoc khi dung Copilot."
fi

python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

mkdir -p web_data/uploads web_data/output
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "=== Xong ==="
echo ""
echo "  Kiem tra truoc khi chay (khuyen nghi):"
echo "    ./scripts/ubuntu_preflight.sh"
echo ""
echo "  Buoc tiep theo — chay server:"
echo "    ./chay.sh"
echo ""
if [ -n "$LAN_IP" ]; then
  echo "  Mo browser (sua config.yaml neu IP khac):"
  echo "    http://${LAN_IP}:8765/login"
else
  echo "  Mo browser:"
  echo "    http://<IP-may-ban>:8765/login"
fi
echo ""
echo "  Dang nhap:  admin  /  Alex@2025!"
echo ""
echo "  Huong dan ngan:"
echo "    docs/CAI_UBUNTU_DON_GIAN.md"
echo ""
echo "  Lan dau tren Ubuntu — chay 1 lenh:"
echo "    ./setup_ubuntu.sh"
echo ""
echo "  (Neu chua mo port: sudo ufw allow 8765/tcp)"
echo "  (Ollama Unavailable tren UI la binh thuong — ALEX dung M365 Copilot, khong can Ollama)"
echo ""
