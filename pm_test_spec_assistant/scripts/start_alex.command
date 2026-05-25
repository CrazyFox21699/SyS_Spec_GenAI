#!/bin/bash
# macOS double-click — one terminal for Ollama + web (+ worker if production)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -d ".venv/bin" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi
PORT="$(python3 -c "
from pathlib import Path
from src.utils.yaml_utils import load_yaml
print(int((load_yaml(Path('config.yaml')).get('deployment') or {}).get('port', 8765)))
" 2>/dev/null || echo 8765)"
open "http://127.0.0.1:${PORT}/" 2>/dev/null || true
exec python3 scripts/start_alex_all.py
