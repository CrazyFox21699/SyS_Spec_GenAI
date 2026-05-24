#!/bin/bash
# Double-click on macOS (Finder) to start ALEX. Keeps repo layout for development.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo " ALEX launcher"
echo " Folder: $ROOT"
echo ""

port() {
  if [ -f config.yaml ]; then
    python3 - <<'PY' 2>/dev/null || echo 8765
from pathlib import Path
try:
    from src.utils.yaml_utils import load_yaml
    cfg = load_yaml(Path("config.yaml"))
    print(int((cfg.get("deployment") or {}).get("port", 8765)))
except Exception:
    print(8765)
PY
  else
    echo 8765
  fi
}

PORT="$(port)"
URL="http://127.0.0.1:${PORT}/"

if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "Starting Ollama..."
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve >/tmp/alex-ollama.log 2>&1 &
    sleep 3
  else
    echo "Ollama not in PATH — install from https://ollama.com or open the Ollama app."
  fi
else
  echo "Ollama already running."
fi

if [ -d ".venv/bin" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

open "$URL" 2>/dev/null || true
echo "Opening $URL"
echo ""
echo "Starting ALEX web (Ctrl+C stops web only; Ollama keeps running)..."
echo ""
exec python3 run_web.py
