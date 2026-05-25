#!/usr/bin/env bash
# Apply Ubuntu LAN config on the server (run once after git pull).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f config.ubuntu.yaml ]; then
  echo "Missing config.ubuntu.yaml" >&2
  exit 1
fi

cp config.ubuntu.yaml config.yaml
echo "Applied config.ubuntu.yaml -> config.yaml"
echo ""
echo "Engineers open: http://10.88.152.11:8765/login"
echo ""
echo "Next steps on this Ubuntu host:"
echo "  1. Edit config.yaml — set assist.m365.client_id if using M365 API"
echo "  2. python scripts/reset_team_auth.py --yes --username admin"
echo "  3. sudo ufw allow from 10.88.0.0/16 to any port 8765 proto tcp"
echo "  4. ./scripts/start_alex_team.sh"
