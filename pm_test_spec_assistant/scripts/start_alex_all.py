#!/usr/bin/env python3
"""Start ALEX in one terminal: optional Ollama + worker (production) + web UI."""

from __future__ import annotations

import atexit
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.yaml_utils import load_yaml  # noqa: E402

_CHILDREN: list[subprocess.Popen] = []


def _ollama_up(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _start_ollama_if_needed(base_url: str) -> subprocess.Popen | None:
    if _ollama_up(base_url):
        print("Ollama already running.")
        return None
    print("Starting Ollama in background (log: /tmp/alex-ollama.log)...")
    log = open("/tmp/alex-ollama.log", "ab")  # noqa: SIM115
    proc = subprocess.Popen(
        ["ollama", "serve"],
        cwd=str(ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(15):
        if _ollama_up(base_url):
            return proc
        time.sleep(0.4)
    print("Warning: Ollama did not respond yet — continuing anyway.")
    return proc


def _shutdown_children() -> None:
    for proc in reversed(_CHILDREN):
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 5
    for proc in _CHILDREN:
        if proc.poll() is not None:
            continue
        remaining = max(0.0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()


def _handle_signal(signum: int, _frame) -> None:
    print(f"\nStopping ALEX ({signum})...")
    _shutdown_children()
    raise SystemExit(0)


def main() -> int:
    cfg_path = ROOT / "config.yaml"
    cfg = load_yaml(cfg_path) if cfg_path.exists() else {}
    dep = cfg.get("deployment") or {}
    mode = str(dep.get("mode", "local")).lower()
    llm_base = str((cfg.get("llm") or {}).get("base_url") or "http://127.0.0.1:11434")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    atexit.register(_shutdown_children)

    print("")
    print(" ALEX — single terminal launcher")
    print(f" Folder: {ROOT}")
    print(f" Mode: {mode}")
    print("")

    ollama_proc = _start_ollama_if_needed(llm_base)
    if ollama_proc is not None:
        _CHILDREN.append(ollama_proc)

    if mode == "production":
        print("Starting analyze worker in background (log: /tmp/alex-worker.log)...")
        log = open("/tmp/alex-worker.log", "ab")  # noqa: SIM115
        worker = subprocess.Popen(
            [sys.executable, "-m", "web.worker"],
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        _CHILDREN.append(worker)
        time.sleep(0.5)
    else:
        print("Analyze mode: local (worker not needed).")

    print("Starting web UI — Ctrl+C stops web + worker.")
    print("")
    web = subprocess.run([sys.executable, "run_web.py"], cwd=str(ROOT))
    _shutdown_children()
    return int(web.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
