#!/usr/bin/env bash
# ALEX Windows setup for Git Bash or WSL. Run once from the ALEX folder:
#   chmod +x setup_windows.sh run_windows.sh verify_windows.sh
#   ./setup_windows.sh
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=============================================="
echo "  ALEX - Setup Windows"
echo "  Shell: Git Bash or WSL"
echo "  Folder: $(pwd)"
echo "=============================================="
echo ""

find_python() {
  if command -v py >/dev/null 2>&1; then
    echo "py -3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  return 1
}

PY_CMD="$(find_python)" || {
  echo "ERROR: Python 3.10+ not found."
  echo "Install Python from https://www.python.org/downloads/windows/"
  echo "Then reopen Git Bash and run ./setup_windows.sh again."
  exit 1
}

echo "[1/5] Check Python..."
$PY_CMD - <<'PY'
import sys
version = ".".join(map(str, sys.version_info[:3]))
if sys.version_info < (3, 10):
    raise SystemExit(f"Python {version} is too old. ALEX needs Python 3.10+.")
print(f"      Python {version}")
PY

echo "[2/5] Create .venv..."
if [ ! -d .venv ]; then
  $PY_CMD -m venv .venv
fi

if [ -f ".venv/Scripts/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/Scripts/activate"
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
else
  echo "ERROR: Cannot find virtualenv activation script."
  exit 1
fi
echo "      OK"

echo "[3/5] Install Python packages..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
echo "      OK"

echo "[4/5] Create local runtime files..."
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  chmod 600 .env 2>/dev/null || true
  echo "      Created .env from .env.example"
else
  echo "      .env already exists or .env.example is missing"
fi
mkdir -p web_data/uploads web_data/output output input config
echo "      OK"

echo "[5/5] Reset local admin account..."
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
echo "      OK"

echo ""
echo "=============================================="
echo "  SETUP DONE"
echo "=============================================="
echo ""
echo "  Run ALEX:"
echo "    ./run_windows.sh"
echo ""
echo "  Open browser:"
echo "    http://127.0.0.1:8765/login"
echo ""
echo "  Login:"
echo "    admin / Alex@2025!"
echo ""
echo "  Optional check:"
echo "    ./verify_windows.sh"
echo ""
