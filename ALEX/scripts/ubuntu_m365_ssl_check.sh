#!/usr/bin/env bash
# Kiểm tra SSL/network tới Microsoft trên Ubuntu — chạy trên server ALEX.
set -u
cd "$(dirname "$0")/.."

echo ""
echo "=== ALEX M365 connectivity check ==="
echo ""

if [ ! -d .venv ]; then
  echo "FAIL: chua cai .venv — chay ./cai_dat.sh truoc"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

python3 <<'PY'
import sys
from pathlib import Path

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.utils.env_loader import load_dotenv
    load_dotenv()
except Exception:
    pass

URL = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"

try:
    try:
        from web.http_ssl import requests_get, ssl_verify_option, ssl_verify_status

        verify = ssl_verify_option()
        print("verify option:", verify)
        print("ssl status:", ssl_verify_status())
        r_obj = requests_get(URL, timeout=15)
        r = {"ok": r_obj.status_code == 200, "status_code": r_obj.status_code, "verify": str(verify), "url": URL}
    except ImportError:
        print("FAIL: web/http_ssl.py missing — redeploy full release (docs/UBUNTU_UPDATE_POLICY.md)")
        r = {"ok": False, "error": "web/http_ssl.py not found", "url": URL}
    except RuntimeError as exc:
        r = {"ok": False, "error": str(exc), "url": URL}
        try:
            from web.http_ssl import ssl_verify_option, ssl_verify_status
            r["verify"] = str(ssl_verify_option())
            r.update(ssl_verify_status())
        except ImportError:
            r["verify"] = "unknown"
except Exception as exc:
    r = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "url": URL}

print("probe:", r)
if not r.get("ok"):
    print("")
    print("FIX (ISMS-safe — không tắt SSL verify):")
    print("  1. IT gửi root CA → config/company-ca.pem")
    print("  2. .env: REQUESTS_CA_BUNDLE=/path/to/company-ca.pem")
    print("  3. config.yaml: assist.m365.ssl_verify: true")
    print("  4. sudo apt install -y ca-certificates && sudo update-ca-certificates")
    print("  5. Redeploy full release nếu thiếu web/http_ssl.py")
    print("  docs/IT_REQUEST_CHECKLIST.md  docs/HUONG_DAN_CAI_DAT_UBUNTU.md")
    raise SystemExit(1)

# ISMS: cảnh báo nếu verify bị tắt
try:
    from web.http_ssl import ssl_verify_status
    st = ssl_verify_status()
    if st.get("ssl_verify_disabled"):
        print("")
        print("WARN: SSL verify DISABLED — không phù hợp ISMS. Dùng company-ca.pem + ssl_verify: true")
        raise SystemExit(1)
except ImportError:
    pass

print("")
print("OK — Microsoft HTTPS reachable from this server.")
PY

echo ""
echo "Next: restart ./chay.sh and Sign in on Review tab."
echo ""
