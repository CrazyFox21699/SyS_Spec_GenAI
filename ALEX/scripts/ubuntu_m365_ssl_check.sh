#!/usr/bin/env bash
# Kiểm tra SSL/network tới Microsoft trên Ubuntu — chạy trên server ALEX.
set -u
cd "$(dirname "$0")/.."

echo ""
echo "=== ALEX M365 connectivity check ==="
echo ""

if [ ! -d .venv ]; then
  echo "FAIL: chưa cài .venv — chạy ./cai_dat.sh trước"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

python3 <<'PY'
from web.m365_auth import probe_microsoft_connectivity
from web.http_ssl import ssl_verify_option

print("verify option:", ssl_verify_option())
r = probe_microsoft_connectivity()
print("probe:", r)
if not r.get("ok"):
    print("")
    print("FIX:")
    print("  sudo apt install -y ca-certificates && sudo update-ca-certificates")
    print("  pip install certifi")
    print("  # company proxy: REQUESTS_CA_BUNDLE=/path/to/ca.pem in .env")
    print("  # temp test only: M365_SSL_VERIFY=false in .env")
    raise SystemExit(1)
print("")
print("OK — Microsoft HTTPS reachable from this server.")
PY

echo ""
echo "Next: restart ./chay.sh and Sign in on Review tab."
echo ""
