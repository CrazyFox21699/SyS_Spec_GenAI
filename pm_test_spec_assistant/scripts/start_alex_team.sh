#!/usr/bin/env bash
# One terminal: Ollama (optional) + worker (production) + web UI
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -d ".venv/bin" ]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
fi
exec python3 scripts/start_alex_all.py
