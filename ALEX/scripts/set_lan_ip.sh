#!/usr/bin/env bash
# Tự sửa IP LAN trong config.yaml theo hostname -I
set -euo pipefail
cd "$(dirname "$0")/.."

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$IP" ]; then
  echo "FAIL: khong lay duoc IP (hostname -I). Sua tay config.yaml"
  exit 1
fi

python3 <<PY
import re
from pathlib import Path

ip = "${IP}"
path = Path("config.yaml")
text = path.read_text(encoding="utf-8")
text = re.sub(r"(?m)^(\s*lan_ipv4:\s*).*$", rf"\g<1>{ip}", text, count=1)
text = re.sub(
    r"(?m)^(\s*public_url:\s*)http://[^\s]+",
    rf"\g<1>http://{ip}:8765",
    text,
    count=1,
)
path.write_text(text, encoding="utf-8")
print(f"OK — config.yaml: lan_ipv4={ip}, public_url=http://{ip}:8765")
PY
