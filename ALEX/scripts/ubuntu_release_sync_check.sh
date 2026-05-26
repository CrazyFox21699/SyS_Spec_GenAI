#!/usr/bin/env bash
# Kiểm tra bản ALEX trên Ubuntu đã đồng bộ release đầy đủ — không copy lẻ file.
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
echo "=== ALEX release sync check ==="
echo "Folder: $(pwd)"
echo ""
echo "Một nguồn sự thật: /home/tmc_ai_common/ALEX (hoặc path cố định trên server)."
echo "Không copy lẻ file từ GitHub — dùng ZIP/git full tree. Xem docs/UBUNTU_UPDATE_POLICY.md"
echo ""

REQUIRED=(
  web/http_ssl.py
  web/m365_auth.py
  web/m365_copilot.py
  web/main.py
  scripts/ubuntu_preflight.sh
  scripts/ubuntu_m365_ssl_check.sh
  scripts/ubuntu_verify.sh
  scripts/ubuntu_deploy_gates.sh
  cai_dat.sh
  chay.sh
  setup_ubuntu.sh
  config.yaml
  requirements.txt
)

for f in "${REQUIRED[@]}"; do
  if [ -f "$f" ]; then
    pass "found $f"
  else
    bad "missing $f — redeploy full release (ZIP hoặc git), không patch từng file"
  fi
done

if [ -f config.yaml ]; then
  if grep -qE 'ssl_verify:[[:space:]]*false' config.yaml 2>/dev/null; then
    note "config.yaml assist.m365.ssl_verify: false — ISMS: đổi true + company-ca.pem từ IT"
  elif grep -qE 'ssl_verify:[[:space:]]*true' config.yaml 2>/dev/null; then
    pass "config.yaml ssl_verify: true (ISMS)"
  else
    note "config.yaml không có ssl_verify — xem docs/HUONG_DAN_CAI_DAT_UBUNTU.md"
  fi
fi

CA_FOUND=0
for ca in config/company-ca.pem company-ca.pem web_data/company-ca.pem; do
  if [ -f "$ca" ]; then
    pass "company CA: $ca"
    CA_FOUND=1
    break
  fi
done
if [ "$CA_FOUND" -eq 0 ]; then
  if [ -f .env ] && grep -qE '^REQUESTS_CA_BUNDLE=.+' .env 2>/dev/null; then
    pass "REQUESTS_CA_BUNDLE set in .env"
    CA_FOUND=1
  fi
fi
if [ "$CA_FOUND" -eq 0 ]; then
  note "chưa có company CA — nhờ IT file root CA (docs/IT_REQUEST_CHECKLIST.md)"
fi

if [ -d .venv ]; then
  pass ".venv exists"
  # shellcheck source=/dev/null
  if source .venv/bin/activate 2>/dev/null && python3 -c "from web.http_ssl import ssl_verify_option" 2>/dev/null; then
    pass "import web.http_ssl OK"
  else
    bad "cannot import web.http_ssl — redeploy full release"
  fi
else
  note ".venv missing — run ./cai_dat.sh"
fi

echo ""
echo "Summary: $ok passed, $warn warnings, $fail failures"
echo ""
if [ "$fail" -gt 0 ]; then
  echo "FAIL — redeploy full release trước khi chạy ./chay.sh"
  echo "  docs/UBUNTU_UPDATE_POLICY.md"
  exit 1
fi
echo "Release sync OK — next: ./scripts/ubuntu_deploy_gates.sh"
exit 0
