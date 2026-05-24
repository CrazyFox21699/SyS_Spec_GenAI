#!/bin/bash
# macOS team launcher: Ollama + web + analyze worker (production mode)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  nohup ollama serve >/tmp/alex-ollama.log 2>&1 &
  sleep 3
fi

if [ -d ".venv/bin" ]; then source ".venv/bin/activate"; fi

PORT="$(python3 -c "
from pathlib import Path
from src.utils.yaml_utils import load_yaml
print(int((load_yaml(Path('config.yaml')).get('deployment') or {}).get('port', 8765)))
" 2>/dev/null || echo 8765)"

nohup python3 -m web.worker >/tmp/alex-worker.log 2>&1 &
sleep 1
open "http://127.0.0.1:${PORT}/login" 2>/dev/null || true
exec python3 run_web.py
