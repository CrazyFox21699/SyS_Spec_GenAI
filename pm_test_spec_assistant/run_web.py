#!/usr/bin/env python3
"""Start local web UI: python run_web.py"""

import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("Missing dependencies. Run:")
        print(f"  cd {ROOT}")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    from src.utils.yaml_utils import load_yaml

    cfg = load_yaml(ROOT / "config.yaml") if (ROOT / "config.yaml").exists() else {}
    dep = cfg.get("deployment") or {}
    host = str(dep.get("host", "127.0.0.1"))
    port = int(dep.get("port", 8765))
    mode = str(dep.get("mode", "local")).lower()

    print(f"Starting ALEX at http://{host}:{port}/")
    if mode == "local":
        print("Analyze mode: local (runs inside web — no separate worker terminal needed).")
    else:
        print("Analyze mode: production — also run: python -m web.worker")
    lan_ip = str(dep.get("lan_ipv4") or "").strip()
    if host in ("0.0.0.0", "::"):
        shown = lan_ip or _lan_ip()
        print(f"LAN URL: http://{shown}:{port}/")
    elif lan_ip:
        print(f"LAN URL: http://{lan_ip}:{port}/")
    if (cfg.get("team_auth") or {}).get("enabled"):
        login_host = host if host not in ("0.0.0.0", "::") else (lan_ip or _lan_ip())
        print(f"Team login: http://{login_host}:{port}/login")
    print("Press Ctrl+C to stop.")
    uvicorn.run("web.main:app", host=host, port=port, reload=False)
