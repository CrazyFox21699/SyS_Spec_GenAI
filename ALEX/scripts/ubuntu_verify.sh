#!/usr/bin/env bash
# Kiểm tra ALEX đang chạy (sau ./chay.sh). Chạy từ terminal thứ hai.
set -u
cd "$(dirname "$0")/.."

HOST="${ALEX_VERIFY_HOST:-127.0.0.1}"
PORT="${ALEX_VERIFY_PORT:-8765}"
BASE="http://${HOST}:${PORT}"

echo ""
echo "=== ALEX verify ==="
echo "URL: $BASE"
echo ""

if ! command -v curl >/dev/null 2>&1; then
  echo "Install curl: sudo apt install -y curl"
  exit 1
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/" || echo "000")
if [ "$code" = "200" ] || [ "$code" = "302" ] || [ "$code" = "307" ]; then
  echo "OK  GET / → HTTP $code"
else
  echo "FAIL GET / → HTTP $code (is ./chay.sh running?)"
  exit 1
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/login" || echo "000")
if [ "$code" = "200" ]; then
  echo "OK  GET /login → HTTP $code"
else
  echo "WARN GET /login → HTTP $code"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/app-config" || echo "000")
if [ "$code" = "200" ]; then
  echo "OK  GET /api/app-config → HTTP $code"
else
  echo "WARN GET /api/app-config → HTTP $code"
fi

if [ -d .venv ]; then
  echo "OK  .venv exists"
else
  echo "WARN .venv missing — run ./cai_dat.sh"
fi

if [ -f /tmp/alex-worker.log ]; then
  echo "OK  worker log: /tmp/alex-worker.log (tail if jobs stuck)"
else
  echo "NOTE no /tmp/alex-worker.log yet (production worker starts with ./chay.sh)"
fi

echo ""
echo "From another PC on LAN, open:"
if [ -f config.yaml ]; then
  url=$(grep 'public_url:' config.yaml | head -1 | sed 's/.*public_url:[[:space:]]*//' | tr -d '"' | tr -d "'")
  if [ -n "$url" ]; then
    echo "  ${url}/login"
  fi
fi
echo "  admin / Alex@2025!"
echo ""
