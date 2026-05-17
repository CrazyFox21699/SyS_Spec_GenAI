"""File-based analyze job queue (production without Redis)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def queue_dir(data_root: Path) -> Path:
    d = data_root / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def enqueue(data_root: Path, job_id: str, payload: dict[str, Any]) -> None:
    path = queue_dir(data_root) / f"{job_id}.json"
    path.write_text(
        json.dumps({"job_id": job_id, "status": "queued", "payload": payload}),
        encoding="utf-8",
    )


def dequeue(data_root: Path) -> tuple[str, dict[str, Any]] | None:
    qd = queue_dir(data_root)
    files = sorted(qd.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("status") != "queued":
            continue
        job_id = data.get("job_id", f.stem)
        lock = qd / f"{job_id}.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            continue
        data["status"] = "running"
        f.write_text(json.dumps(data), encoding="utf-8")
        return job_id, data.get("payload") or {}
    return None


def complete(data_root: Path, job_id: str) -> None:
    path = queue_dir(data_root) / f"{job_id}.json"
    lock = queue_dir(data_root) / f"{job_id}.lock"
    if path.exists():
        path.unlink()
    if lock.exists():
        lock.unlink()
