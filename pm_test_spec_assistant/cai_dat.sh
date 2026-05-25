#!/usr/bin/env bash
# Cài ALEX lần đầu trên Ubuntu công ty — chạy 1 lần duy nhất.
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=== ALEX — Cai dat (Ubuntu) ==="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Chua co python3. Chay:"
  echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip git curl"
  exit 1
fi

python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

mkdir -p web_data/uploads web_data/output
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'

echo ""
echo "=== Xong ==="
echo ""
echo "  Buoc tiep theo — chay server:"
echo "    ./chay.sh"
echo ""
echo "  Mo browser:"
echo "    http://10.88.152.11:8765/login"
echo ""
echo "  Dang nhap:  admin  /  Alex@2025!"
echo ""
echo "  (Neu chua mo port: sudo ufw allow 8765/tcp)"
echo ""
