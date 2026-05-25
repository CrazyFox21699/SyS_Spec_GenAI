#!/usr/bin/env bash
# Kiểm tra môi trường Ubuntu trước khi ./cai_dat.sh — chỉ đọc, không sửa.
set -u
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
NC='\033[0m'
ok=0
warn=0
fail=0

pass() { echo -e "${GRN}OK${NC}  $1"; ok=$((ok + 1)); }
note() { echo -e "${YLW}WARN${NC} $1"; warn=$((warn + 1)); }
bad()  { echo -e "${RED}FAIL${NC} $1"; fail=$((fail + 1)); }

echo ""
echo "=== ALEX Ubuntu preflight ==="
echo "Folder: $(pwd)"
echo ""

if command -v python3 >/dev/null 2>&1; then
  v=$(python3 --version 2>&1)
  pass "python3: $v"
else
  bad "python3 missing — sudo apt install -y python3 python3-venv python3-pip"
fi

if python3 -c "import venv" 2>/dev/null; then
  pass "python3-venv available"
else
  bad "python3-venv missing — sudo apt install -y python3-venv"
fi

if [ -f requirements.txt ]; then
  pass "requirements.txt found"
else
  bad "requirements.txt missing — wrong directory?"
fi

if [ -f config.yaml ]; then
  pass "config.yaml found"
  if grep -q 'lan_ipv4: 10.88.152.11' config.yaml 2>/dev/null; then
    ip_now=$(hostname -I 2>/dev/null | awk '{print $1}')
    note "config.yaml still has sample IP 10.88.152.11 — update deployment.lan_ipv4 / public_url (this machine: ${ip_now:-?})"
  fi
  if grep -q 'mode: local' config.yaml 2>/dev/null; then
    note "deployment.mode is local — use production on Ubuntu team server"
  fi
else
  bad "config.yaml missing"
fi

if [ -f .env ]; then
  if [ -r .env ]; then
    pass ".env exists"
    if grep -qE '^M365_CLIENT_SECRET=.+[^[:space:]]' .env 2>/dev/null; then
      pass "M365_CLIENT_SECRET is set in .env"
    else
      note "M365_CLIENT_SECRET empty — Copilot sign-in will fail until IT provides secret Value"
    fi
    perm=$(stat -c '%a' .env 2>/dev/null || stat -f '%OLp' .env 2>/dev/null)
    if [ "$perm" != "600" ] && [ "$perm" != "0600" ]; then
      note ".env permissions $perm — recommend: chmod 600 .env"
    fi
  else
    bad ".env exists but not readable"
  fi
else
  note ".env missing — run: cp .env.example .env && chmod 600 .env"
fi

if command -v ss >/dev/null 2>&1; then
  if ss -tln 2>/dev/null | grep -q ':8765 '; then
    note "Port 8765 already in use — stop old ALEX or change deployment.port"
  else
    pass "Port 8765 is free"
  fi
elif command -v netstat >/dev/null 2>&1; then
  if netstat -tln 2>/dev/null | grep -q ':8765 '; then
    note "Port 8765 already in use"
  else
    pass "Port 8765 appears free"
  fi
else
  note "Cannot check port 8765 (ss/netstat missing)"
fi

if command -v ufw >/dev/null 2>&1; then
  ufw_status=$(sudo ufw status 2>/dev/null || ufw status 2>/dev/null || true)
  if echo "$ufw_status" | grep -qi inactive; then
    pass "ufw inactive (or no sudo)"
  elif echo "$ufw_status" | grep -q 8765; then
    pass "ufw mentions port 8765"
  else
    note "ufw active but 8765 not listed — run: sudo ufw allow 8765/tcp"
  fi
else
  note "ufw not installed — ensure LAN firewall allows TCP 8765"
fi

lan_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$lan_ip" ]; then
  pass "LAN IP hint: $lan_ip — use in config deployment.public_url"
else
  note "Could not detect LAN IP (hostname -I)"
fi

echo ""
echo "Summary: $ok passed, $warn warnings, $fail failures"
echo ""
if [ "$fail" -gt 0 ]; then
  echo "Fix FAIL items before ./cai_dat.sh"
  exit 1
fi
echo "Preflight OK — next: ./cai_dat.sh then ./chay.sh"
exit 0
