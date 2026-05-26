#!/usr/bin/env bash
# Cổng xác minh triển khai Ubuntu — chạy TRƯỚC khi Sign in M365.
set -u
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GRN='\033[0;32m'
NC='\033[0m'
fail=0

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo -e "${GRN}OK${NC}  $1"; }
bad()  { echo -e "${RED}FAIL${NC} $1"; fail=$((fail + 1)); }

echo ""
echo "=== ALEX Ubuntu deploy gates (ISMS-safe) ==="
echo ""

step "Gate 1 — Release sync"
if ./scripts/ubuntu_release_sync_check.sh; then
  ok "release sync"
else
  bad "release sync"
fi

step "Gate 2 — Preflight"
if ./scripts/ubuntu_preflight.sh; then
  ok "preflight"
else
  bad "preflight"
fi

step "Gate 3 — M365 SSL connectivity"
if ./scripts/ubuntu_m365_ssl_check.sh; then
  ok "M365 SSL"
else
  bad "M365 SSL — xem docs/HUONG_DAN_CAI_DAT_UBUNTU.md (SSL + company CA)"
fi

step "Gate 4 — Web server (optional if ./chay.sh chưa chạy)"
if curl -sf -o /dev/null -w '' "http://127.0.0.1:8765/" 2>/dev/null; then
  ok "GET /"
  if ./scripts/ubuntu_verify.sh; then
    ok "ubuntu_verify"
  else
    bad "ubuntu_verify"
  fi
  conn=$(curl -sf "http://127.0.0.1:8765/api/m365/connectivity" 2>/dev/null || echo "")
  if echo "$conn" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    ok "GET /api/m365/connectivity"
  else
    bad "GET /api/m365/connectivity — restart ./chay.sh sau khi SSL OK"
    echo "  response: ${conn:-<empty>}"
  fi
else
  echo "SKIP — ./chay.sh chưa chạy. Sau khi start:"
  echo "  ./scripts/ubuntu_verify.sh"
  echo "  curl -s http://127.0.0.1:8765/api/m365/connectivity | python3 -m json.tool"
fi

echo ""
if [ "$fail" -gt 0 ]; then
  echo -e "${RED}Deploy gates FAILED ($fail)${NC} — sửa trước khi Sign in M365"
  exit 1
fi
echo -e "${GRN}Deploy gates PASSED${NC} — restart ./chay.sh, hard refresh browser, Sign in M365"
echo ""
