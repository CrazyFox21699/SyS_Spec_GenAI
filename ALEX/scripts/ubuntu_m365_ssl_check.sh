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


def probe_with_http_ssl():
    from web.http_ssl import requests_get, ssl_verify_option

    verify = ssl_verify_option()
    print("verify option:", verify)
    r = requests_get(URL, timeout=15)
    return {"ok": r.status_code == 200, "status_code": r.status_code, "verify": str(verify), "url": URL}


def probe_plain_requests():
    import requests

    print("verify option: (system default — web/http_ssl.py not found)")
    r = requests.get(URL, timeout=15)
    return {"ok": r.status_code == 200, "status_code": r.status_code, "verify": "system", "url": URL}


try:
    try:
        r = probe_with_http_ssl()
    except ImportError:
        print("NOTE: copy ALEX/web/http_ssl.py for full SSL diagnostics.")
        r = probe_plain_requests()
    except RuntimeError as exc:
        r = {"ok": False, "error": str(exc), "url": URL}
        try:
            from web.http_ssl import ssl_verify_option
            r["verify"] = str(ssl_verify_option())
        except ImportError:
            r["verify"] = "unknown"
except Exception as exc:
    r = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "url": URL}

print("probe:", r)
if not r.get("ok"):
    print("")
    print("FIX:")
    print("  sudo apt install -y ca-certificates && sudo update-ca-certificates")
    print("  pip install certifi")
    print("  copy ALEX/web/http_ssl.py + ALEX/web/m365_auth.py + ALEX/web/main.py")
    print("  company proxy: REQUESTS_CA_BUNDLE=/path/to/ca.pem in .env")
    print("  temp test only: M365_SSL_VERIFY=false in .env")
    print("  then: ./chay.sh")
    raise SystemExit(1)

print("")
print("OK — Microsoft HTTPS reachable from this server.")
PY

echo ""
echo "Next: restart ./chay.sh and Sign in on Review tab."
echo ""
