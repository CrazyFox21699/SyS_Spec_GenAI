"""Persistent generation run registry.

Tracks batch code generation attempts per-job so progress survives browser
reloads and server restarts. The task thread runs independently of HTTP
sessions; this file provides the durable record that lets the UI reattach.

Status lifecycle:  RUNNING → COMPLETED | FAILED | CANCELLED | PAUSED
A RUNNING run whose updated_at predates the current server process start is
treated as PAUSED (the thread was killed by a restart) and can be resumed.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
# Used to detect runs that were RUNNING when the server restarted.
_SERVER_START = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _path(job_output: Path) -> Path:
    return job_output / "generation_runs.json"


def _load_raw(job_output: Path) -> dict[str, Any]:
    p = _path(job_output)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(job_output: Path, runs: dict[str, Any]) -> None:
    p = _path(job_output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")


def create_run(
    job_id: str,
    job_output: Path,
    *,
    candidate_ids: list[str],
    task_id: str,
    language: str = "EN",
    engineer_note: str = "",
    batch_size: int = 10,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    run: dict[str, Any] = {
        "run_id": run_id,
        "job_id": job_id,
        "task_id": task_id,
        "status": "RUNNING",
        "candidate_ids": list(candidate_ids),
        "candidate_count": len(candidate_ids),
        "language": language,
        "engineer_note": engineer_note,
        "batch_size": batch_size,
        "scope": scope,
        "group_key": group_key,
        "group_field": group_field,
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "can_resume": False,
        "last_error": None,
    }
    with _lock:
        runs = _load_raw(job_output)
        runs[run_id] = run
        _save_raw(job_output, runs)
    return run


def update_run(job_output: Path, run_id: str, **kwargs: Any) -> dict[str, Any] | None:
    with _lock:
        runs = _load_raw(job_output)
        run = runs.get(run_id)
        if not run:
            return None
        run.update(kwargs)
        run["updated_at"] = _now_iso()
        if kwargs.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            run.setdefault("completed_at", _now_iso())
        _save_raw(job_output, runs)
        return dict(run)


def get_active_run(
    job_output: Path,
    *,
    task_status_by_id: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return the most recent RUNNING/PAUSED run, resolving stale state lazily."""
    with _lock:
        runs = _load_raw(job_output)
    active = [r for r in runs.values() if str(r.get("status") or "") in ("RUNNING", "PAUSED")]
    if not active:
        return None
    run = dict(sorted(active, key=lambda r: str(r.get("started_at") or ""))[-1])
    task_id = str(run.get("task_id") or "")
    task_st = (task_status_by_id or {}).get(task_id, "")

    # Stale RUNNING: server restarted (updated_at is before this server's start time)
    if run["status"] == "RUNNING" and str(run.get("updated_at") or "") < _SERVER_START:
        run["status"] = "PAUSED"
        run["can_resume"] = True
        _patch_on_disk(job_output, run["run_id"], status="PAUSED", can_resume=True)
    elif run["status"] == "RUNNING" and task_st in ("completed", "failed", "cancelled", "MISSING"):
        new_st = {"completed": "COMPLETED", "failed": "FAILED", "cancelled": "CANCELLED"}.get(task_st, "PAUSED")
        run["status"] = new_st
        can_res = new_st in ("PAUSED", "FAILED")
        run["can_resume"] = can_res
        _patch_on_disk(job_output, run["run_id"], status=new_st, can_resume=can_res)
    return run


def _patch_on_disk(job_output: Path, run_id: str, **kwargs: Any) -> None:
    with _lock:
        runs = _load_raw(job_output)
        if run_id in runs:
            runs[run_id].update(kwargs)
            runs[run_id]["updated_at"] = _now_iso()
            _save_raw(job_output, runs)


def list_runs(job_output: Path) -> list[dict[str, Any]]:
    return sorted(_load_raw(job_output).values(), key=lambda r: str(r.get("started_at") or ""), reverse=True)


def scan_and_mark_stale(jobs_root: Path) -> int:
    """Called on server startup: mark any RUNNING run as PAUSED across all jobs."""
    if not jobs_root.exists():
        return 0
    count = 0
    for job_dir in jobs_root.iterdir():
        if not job_dir.is_dir():
            continue
        p = _path(job_dir)
        if not p.exists():
            continue
        try:
            with _lock:
                runs = _load_raw(job_dir)
                changed = False
                for run in runs.values():
                    if run.get("status") == "RUNNING":
                        run["status"] = "PAUSED"
                        run["can_resume"] = True
                        run["updated_at"] = _SERVER_START
                        changed = True
                        count += 1
                if changed:
                    _save_raw(job_dir, runs)
        except Exception:  # noqa: BLE001
            pass
    return count


def compute_run_diagnostics(
    run: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    task_status: str = "",
) -> dict[str, Any]:
    """Compute live diagnostics for a generation run from gtest_state."""
    candidate_ids = list(run.get("candidate_ids") or [])
    drafts = gtest_state.get("drafts") or {}
    confirmed = generated = failed = no_code = 0
    for cid in candidate_ids:
        d = drafts.get(cid) or {}
        cs = str(d.get("code_status") or "").upper()
        has_code = bool(str(d.get("full_snippet") or d.get("code_body") or "").strip())
        is_confirmed = bool(d.get("exportable")) or str(d.get("approval_status") or "").upper() in ("CONFIRMED", "APPROVED")
        if is_confirmed:
            confirmed += 1
        if has_code and cs in ("SAVED", "NEEDS_REVIEW"):
            generated += 1
        if cs == "ERROR":
            failed += 1
        if not has_code:
            no_code += 1
    total = len(candidate_ids)
    remaining = max(0, total - generated - confirmed)
    can_resume = run.get("status") in ("PAUSED", "FAILED") and remaining > 0
    batch_run = (gtest_state.get("copilot_batch") or {}).get("run") or {}
    checkpoint = (gtest_state.get("copilot_batch") or {}).get("run_checkpoint") or {}
    chk_cids = checkpoint.get("current_candidate_ids")
    last_persisted = str(chk_cids[-1]) if isinstance(chk_cids, list) and chk_cids else ""
    return {
        "run_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "status": run.get("status"),
        "task_status": task_status,
        "started_at": run.get("started_at"),
        "updated_at": run.get("updated_at"),
        "total_count": total,
        "generated_count": generated,
        "confirmed_count": confirmed,
        "failed_count": failed,
        "no_code_count": no_code,
        "persisted_count": total - no_code,
        "remaining_count": remaining,
        "completed_count": generated + confirmed,
        "can_resume": can_resume,
        "last_error": run.get("last_error"),
        "last_persisted_candidate_id": last_persisted,
        "batch_saved": batch_run.get("saved") or 0,
        "batch_needs_review": batch_run.get("needs_review") or 0,
        "batch_error": batch_run.get("error") or 0,
        "batch_completed_chunks": batch_run.get("completed_chunks") or 0,
        "batch_total_chunks": batch_run.get("batch_total") or 0,
        "batch_status_message": batch_run.get("status_message") or "",
        "candidate_ids": candidate_ids,
        "language": run.get("language"),
        "engineer_note": run.get("engineer_note"),
        "batch_size": run.get("batch_size"),
    }
