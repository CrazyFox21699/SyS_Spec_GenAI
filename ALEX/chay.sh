#!/usr/bin/env bash
# Chay ALEX — giu terminal nay mo. Ctrl+C de dung.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Chua cai dat. Chay truoc: ./cai_dat.sh"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
exec python scripts/start_alex_all.py
