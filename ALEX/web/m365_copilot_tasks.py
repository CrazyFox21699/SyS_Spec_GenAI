"""Background M365 Copilot task queue — non-blocking API for long Graph calls."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Callable

_lock = threading.Lock()
_tasks: dict[str, dict[str, dict[str, Any]]] = {}  # job_id -> task_id -> task

TASK_KINDS = frozenset(
    {
        "code_generate",
        "code_refine",
        "code_batch",
        "code_exemplar_batch",
        "code_copilot_batch",
        "copilot_plan",
        "copilot_write",
        "copilot_context_plan",
        "write_from_row",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tasks_path(job_output: Path) -> Path:
    return job_output / "m365_tasks.json"


def _load_disk(job_output: Path) -> dict[str, dict[str, Any]]:
    path = _tasks_path(job_output)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _persist_disk(job_output: Path, job_id: str) -> None:
    path = _tasks_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        tasks = dict(_tasks.get(job_id) or {})
    path.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


def _task_error_message(result: dict[str, Any]) -> str:
    err = str(result.get("error") or "").strip()
    if err:
        return err
    validation = result.get("validation") or {}
    flags = validation.get("flags") or []
    if flags:
        return f"Validation failed: {', '.join(flags)}"
    raw = str(result.get("raw_preview") or "").strip()
    if raw:
        return f"Copilot response could not be applied. Preview: {raw[:200]}"
    return "Task failed — no error detail from Copilot."


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    started = task.get("_started_mono") or monotonic()
    elapsed = int(monotonic() - started) if task.get("status") == "running" else int(task.get("elapsed_s") or 0)
    status = task.get("status")
    return {
        "task_id": task.get("task_id"),
        "job_id": task.get("job_id"),
        "kind": task.get("kind"),
        "status": status,
        "label": task.get("label") or task.get("kind"),
        "started_at": task.get("started_at"),
        "elapsed_s": elapsed,
        "progress": task.get("progress") or {},
        "log": list(task.get("log") or [])[-30:],
        "logic_id": task.get("logic_id") or "",
        "candidate_id": task.get("candidate_id") or "",
        "target_page": task.get("target_page") or "",
        "result": task.get("result") if status in ("completed", "failed") else None,
        "error": task.get("error"),
        "error_category": task.get("error_category"),
    }


def _get_task(job_id: str, task_id: str, job_output: Path | None = None) -> dict[str, Any] | None:
    with _lock:
        task = (_tasks.get(job_id) or {}).get(task_id)
    if task:
        return task
    if job_output:
        disk = _load_disk(job_output)
        task = disk.get(task_id)
        if task:
            with _lock:
                _tasks.setdefault(job_id, {})[task_id] = task
            return task
    return None


def list_tasks(job_id: str, job_output: Path | None = None) -> list[dict[str, Any]]:
    with _lock:
        merged = dict(_tasks.get(job_id) or {})
    if job_output:
        merged = {**_load_disk(job_output), **merged}
    return [_public_task(t) for t in merged.values()]


def start_task(
    job_id: str,
    job_output: Path,
    *,
    kind: str,
    payload: dict[str, Any],
    label: str = "",
    logic_id: str = "",
    candidate_id: str = "",
    target_page: str = "",
    runner: Callable[[dict[str, Any], Callable[[str, dict[str, Any]], None]], dict[str, Any]],
) -> dict[str, Any]:
    if kind not in TASK_KINDS:
        raise ValueError(f"Unknown task kind: {kind}")

    task_id = uuid.uuid4().hex[:12]
    task: dict[str, Any] = {
        "task_id": task_id,
        "job_id": job_id,
        "kind": kind,
        "status": "running",
        "cancelled": False,
        "label": label or kind,
        "logic_id": logic_id,
        "candidate_id": candidate_id,
        "target_page": target_page,
        "started_at": _now_iso(),
        "_started_mono": monotonic(),
        "elapsed_s": 0,
        "progress": {"current": 0, "total": 0, "message": "Starting…"},
        "log": ["Task queued"],
        "payload": payload,
        "result": None,
        "error": None,
        "error_category": None,
    }

    with _lock:
        _tasks.setdefault(job_id, {})[task_id] = task
    _persist_disk(job_output, job_id)

    def progress(message: str, **extra: Any) -> None:
        with _lock:
            t = (_tasks.get(job_id) or {}).get(task_id)
            if not t or t.get("cancelled"):
                return
            t["progress"] = {**dict(t.get("progress") or {}), "message": message, **extra}
            t["log"] = list(t.get("log") or []) + [message]

    def worker() -> None:
        try:
            if task.get("cancelled"):
                return
            progress("Running…")
            result = runner(task, progress)
            with _lock:
                t = (_tasks.get(job_id) or {}).get(task_id)
                if not t:
                    return
                t["elapsed_s"] = int(monotonic() - t["_started_mono"])
                if t.get("cancelled"):
                    t["status"] = "cancelled"
                    t["log"] = list(t.get("log") or []) + ["Cancelled"]
                elif result.get("ok") is False:
                    t["status"] = "failed"
                    t["error"] = _task_error_message(result)
                    t["error_category"] = result.get("error_category") or "m365_task"
                    t["result"] = result
                else:
                    t["status"] = "completed"
                    t["result"] = result
                    t["log"] = list(t.get("log") or []) + ["Completed"]
        except Exception as exc:  # noqa: BLE001
            with _lock:
                t = (_tasks.get(job_id) or {}).get(task_id)
                if t:
                    t["status"] = "failed"
                    t["error"] = str(exc)
                    t["error_category"] = "m365_task"
                    t["elapsed_s"] = int(monotonic() - t.get("_started_mono", monotonic()))
        finally:
            _persist_disk(job_output, job_id)

    threading.Thread(target=worker, daemon=True).start()
    return _public_task(task)


def get_task_status(job_id: str, task_id: str, job_output: Path) -> dict[str, Any] | None:
    task = _get_task(job_id, task_id, job_output)
    if not task:
        return None
    return _public_task(task)


def cancel_task(job_id: str, task_id: str, job_output: Path) -> dict[str, Any] | None:
    task = _get_task(job_id, task_id, job_output)
    if not task:
        return None
    with _lock:
        t = (_tasks.get(job_id) or {}).get(task_id)
        if not t:
            return None
        t["cancelled"] = True
        if t.get("status") == "running":
            t["status"] = "cancelled"
            t["log"] = list(t.get("log") or []) + ["Cancel requested"]
    _persist_disk(job_output, job_id)
    return _public_task(task)


def is_cancelled(job_id: str, task_id: str) -> bool:
    with _lock:
        t = (_tasks.get(job_id) or {}).get(task_id)
        return bool(t and t.get("cancelled"))
