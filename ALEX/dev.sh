#!/usr/bin/env bash
# Chạy ALEX trên Mac (dev local) — không ảnh hưởng config.yaml của Ubuntu.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Tao .venv lan dau..."
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate

if ! python -c "import fastapi" 2>/dev/null; then
  pip install -q -r requirements.txt
fi

export ALEX_CONFIG=config.local.yaml
echo "ALEX dev — config.local.yaml (localhost, mode=local, no login)"
echo ""
exec python scripts/start_alex_all.py
