#!/usr/bin/env bash
# Run ALEX on a Windows laptop from Git Bash or WSL.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Missing .venv. Run first:"
  echo "  ./setup_windows.sh"
  exit 1
fi

if [ -f ".venv/Scripts/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/Scripts/activate"
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
else
  echo "ERROR: Cannot find virtualenv activation script."
  echo "Run ./setup_windows.sh again."
  exit 1
fi

export ALEX_CONFIG="${ALEX_CONFIG:-config.local.yaml}"

echo ""
echo "=============================================="
echo "  ALEX - Windows local run"
echo "  Config: ${ALEX_CONFIG}"
echo "  URL:    http://127.0.0.1:8765/login"
echo "=============================================="
echo ""

exec python scripts/start_alex_all.py
