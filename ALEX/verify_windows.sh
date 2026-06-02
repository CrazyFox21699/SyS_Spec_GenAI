#!/usr/bin/env bash
# Quick local verification for a Windows Git Bash or WSL setup.
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "=============================================="
echo "  ALEX - Verify Windows setup"
echo "=============================================="
echo ""

if [ ! -d .venv ]; then
  echo "FAIL: .venv does not exist. Run ./setup_windows.sh first."
  exit 1
fi

if [ -f ".venv/Scripts/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/Scripts/activate"
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
else
  echo "FAIL: Cannot find virtualenv activation script."
  exit 1
fi

echo "[1/4] Python version"
python - <<'PY'
import sys
print("      " + sys.version.replace("\n", " "))
if sys.version_info < (3, 10):
    raise SystemExit("FAIL: Python 3.10+ is required.")
PY

echo "[2/4] Required Python imports"
python - <<'PY'
modules = [
    "bcrypt",
    "docx",
    "fastapi",
    "openpyxl",
    "pandas",
    "uvicorn",
    "yaml",
]
for name in modules:
    __import__(name)
print("      OK")
PY

echo "[3/4] Runtime files"
test -f .env && echo "      .env OK" || echo "      WARN: .env missing"
test -f config.local.yaml && echo "      config.local.yaml OK" || echo "      WARN: config.local.yaml missing"
mkdir -p web_data/uploads web_data/output
echo "      web_data OK"

echo "[4/4] Python syntax check"
python -m py_compile run_web.py scripts/start_alex_all.py scripts/reset_team_auth.py
echo "      OK"

echo ""
echo "Verify done. Start server with:"
echo "  ./run_windows.sh"
echo ""
