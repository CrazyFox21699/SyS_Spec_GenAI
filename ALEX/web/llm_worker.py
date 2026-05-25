"""Dedicated LLM assist worker (run: python -m web.llm_worker)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config_path import get_config_path
from src.utils.yaml_utils import load_yaml
from web.job_store import init_db
from web.llm_assist import run_ollama_assist

WEB_DATA = ROOT / "web_data"
CONFIG_PATH = get_config_path()
LLM_QUEUE = WEB_DATA / "llm_queue"


def _queue_dir() -> Path:
    LLM_QUEUE.mkdir(parents=True, exist_ok=True)
    return LLM_QUEUE


def enqueue_llm_task(task: dict[str, Any]) -> Path:
    path = _queue_dir() / f"llm_{int(time.time() * 1000)}.json"
    path.write_text(json.dumps({"status": "queued", "task": task}), encoding="utf-8")
    return path


def dequeue_llm_task() -> tuple[Path, dict[str, Any]] | None:
    for path in sorted(_queue_dir().glob("llm_*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("status") != "queued":
            continue
        data["status"] = "running"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path, data.get("task") or {}
    return None


def complete_llm_task(path: Path) -> None:
    if path.exists():
        path.unlink()


def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    init_db(WEB_DATA, production=True)
    ollama_host = os.environ.get("OLLAMA_HOST", cfg.get("llm", {}).get("base_url", "http://localhost:11434"))
    print(f"ALEX LLM worker started; OLLAMA_HOST={ollama_host}")

    while True:
        item = dequeue_llm_task()
        if not item:
            time.sleep(2)
            continue
        path, task = item
        try:
            prompt = str(task.get("prompt") or "")
            if prompt:
                run_ollama_assist(prompt, cfg, schema_hint=str(task.get("schema_hint") or ""))
        except Exception as exc:  # noqa: BLE001
            print(f"LLM task failed: {exc}")
        finally:
            complete_llm_task(path)


if __name__ == "__main__":
    main()
