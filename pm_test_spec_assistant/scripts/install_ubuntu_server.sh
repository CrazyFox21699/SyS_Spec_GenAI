#!/usr/bin/env bash
# Cài ALEX trên Ubuntu LAN server (10.88.152.11) — chạy 1 lần sau git clone.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LAN_IP="${ALEX_LAN_IP:-10.88.152.11}"
ALEX_PORT="${ALEX_PORT:-8765}"
INSTALL_DIR="$ROOT"

echo ""
echo "=== ALEX Ubuntu server install ==="
echo " Folder: $INSTALL_DIR"
echo " LAN IP: $LAN_IP"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Run: sudo apt install python3 python3-venv python3-pip" >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source ".venv/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "Python dependencies OK."

if [ -f config.ubuntu.yaml ]; then
  if [ -n "${ALEX_LAN_IP:-}" ]; then
    sed -i.bak "s/lan_ipv4: .*/lan_ipv4: ${LAN_IP}/" config.ubuntu.yaml
    sed -i.bak "s|public_url: .*|public_url: http://${LAN_IP}:${ALEX_PORT}|" config.ubuntu.yaml
    rm -f config.ubuntu.yaml.bak
  fi
  cp config.ubuntu.yaml config.yaml
  echo "Applied config.ubuntu.yaml -> config.yaml"
else
  echo "Warning: config.ubuntu.yaml missing — edit config.yaml manually." >&2
fi

mkdir -p web_data/uploads web_data/output
chmod +x scripts/start_alex_team.sh scripts/use_ubuntu_config.sh scripts/start_alex_all.py 2>/dev/null || true

echo ""
echo "Create admin account (required for first login):"
if [ -n "${ALEX_ADMIN_PASSWORD:-}" ]; then
  python scripts/reset_team_auth.py --yes --username admin --password "$ALEX_ADMIN_PASSWORD"
else
  echo "Tip: set team default with: ALEX_ADMIN_PASSWORD='Alex@2025!' ./scripts/install_ubuntu_server.sh"
  python scripts/reset_team_auth.py --yes --username admin
fi

echo ""
echo "=== Install complete ==="
echo ""
echo "  Engineer URL:  http://${LAN_IP}:${ALEX_PORT}/login"
echo "  Admin console: http://${LAN_IP}:${ALEX_PORT}/admin"
echo ""
echo "Firewall (adjust subnet for your company):"
echo "  sudo ufw allow from 10.88.0.0/16 to any port ${ALEX_PORT} proto tcp"
echo ""
echo "Start now (one terminal):"
echo "  source .venv/bin/activate && ./scripts/start_alex_team.sh"
echo ""
echo "Or install systemd (production):"
echo "  sudo sed -i 's|/opt/alex/SyS_Spec_GenAI/pm_test_spec_assistant|${INSTALL_DIR}|g' scripts/systemd/*.service"
echo "  sudo cp scripts/systemd/alex-*.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now alex-web alex-worker"
echo ""
echo "Full guide: docs/HUONG_DAN_CAI_DAT_UBUNTU.md"
echo ""
