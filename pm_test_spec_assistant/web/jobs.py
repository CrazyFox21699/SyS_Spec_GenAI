"""Analysis job registry — in-memory (local) or SQLite-backed (production)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.utils.yaml_utils import load_yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_WEB_DATA = Path(__file__).resolve().parent.parent / "web_data"


def _production_mode() -> bool:
    try:
        cfg = load_yaml(_CONFIG_PATH)
        dep = cfg.get("deployment") or {}
        return str(dep.get("mode", "local")).lower() == "production"
    except OSError:
        return False


@dataclass
class JobState:
    job_id: str
    status: str = "waiting"
    current_step: str = ""
    progress: int = 0
    warnings: int = 0
    errors: int = 0
    log: list[str] = field(default_factory=list)
    output_dir: Path | None = None
    bundle: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bundle_version: int = 0


_jobs: dict[str, JobState] = {}
_lock = threading.Lock()
_store_initialized = False


def _ensure_store() -> None:
    global _store_initialized
    if _store_initialized:
        return
    if _production_mode():
        from web.job_store import init_db

        init_db(_WEB_DATA, production=True)
    _store_initialized = True


def create_job(*, created_by: str = "system") -> JobState:
    _ensure_store()
    jid = f"analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    job = JobState(job_id=jid)
    with _lock:
        _jobs[jid] = job
    if _production_mode():
        from web.job_store import JobRecord, insert_job

        insert_job(
            JobRecord(
                job_id=jid,
                status=job.status,
                created_by=created_by,
            )
        )
    return job


def get_job(job_id: str) -> JobState | None:
    _ensure_store()
    with _lock:
        job = _jobs.get(job_id)
    if job:
        return job
    if _production_mode():
        from web.job_store import get_job_record

        rec = get_job_record(job_id)
        if rec:
            return JobState(
                job_id=rec.job_id,
                status=rec.status,
                current_step=rec.current_step,
                progress=rec.progress,
                warnings=rec.warnings,
                errors=rec.errors,
                log=rec.log,
                output_dir=Path(rec.output_dir) if rec.output_dir else None,
                error_message=rec.error_message,
                created_at=rec.created_at,
                bundle_version=rec.bundle_version,
            )
    return None


def update_job(job_id: str, **kwargs: Any) -> None:
    _ensure_store()
    with _lock:
        j = _jobs.get(job_id)
        if not j:
            return
        for k, v in kwargs.items():
            setattr(j, k, v)
    if _production_mode():
        from web.job_store import update_job_record

        fields = {k: v for k, v in kwargs.items() if k != "bundle"}
        if "output_dir" in fields and fields["output_dir"] is not None:
            fields["output_dir"] = str(fields["output_dir"])
        if fields:
            update_job_record(job_id, **fields)


def append_log(job_id: str, line: str) -> None:
    with _lock:
        j = _jobs.get(job_id)
        if j:
            j.log.append(line)
            if len(j.log) > 200:
                j.log = j.log[-200:]
    if _production_mode():
        from web.job_store import get_job_record, update_job_record

        rec = get_job_record(job_id)
        log = list(rec.log) if rec else []
        log.append(line)
        update_job_record(job_id, log=log[-200:])


def run_job_background(
    job_id: str,
    fn: Callable[[Callable[[str, int], None]], dict[str, Any]],
    *,
    use_queue: bool | None = None,
    queue_payload: dict[str, Any] | None = None,
) -> None:
    """Run analyze in thread (local) or enqueue (production)."""
    _ensure_store()
    prod = use_queue if use_queue is not None else _production_mode()

    if prod:
        from web.job_queue import enqueue

        payload = dict(queue_payload or {})
        payload.setdefault("job_id", job_id)
        enqueue(_WEB_DATA, job_id, payload)
        update_job(job_id, status="queued", current_step="Queued for worker")
        return

    def progress(step: str, pct: int) -> None:
        append_log(job_id, step)
        update_job(job_id, current_step=step, progress=pct, status="running")

    def worker() -> None:
        update_job(job_id, status="running", progress=0)
        try:
            bundle = fn(progress)
            summary = bundle.get("summary", {})
            update_job(
                job_id,
                status="done",
                progress=100,
                current_step="Ready for review",
                bundle=bundle,
                warnings=summary.get("warnings", 0),
                errors=summary.get("errors", 0),
            )
            out = _jobs.get(job_id)
            if out and out.output_dir:
                from web.bundle_store import save_split_bundle
                from web.metrics import inc, observe_analyze_duration, record_bundle_gate_summary

                ver = save_split_bundle(out.output_dir, bundle)
                update_job(job_id, bundle_version=ver)
                record_bundle_gate_summary(bundle.get("resolved_logic_blocks") or [])
                observe_analyze_duration(0)
                inc("alex_analyze_completed_total")
                if _production_mode():
                    from web.job_store import upsert_logic_groups

                    groups = [
                        {
                            "logic_id": rb.get("id", rb.get("name", "")),
                            "control_name": rb.get("name", ""),
                            "gate_status": rb.get("gate_status", ""),
                            "parse_status": rb.get("parse_status", ""),
                            "unresolved_count": len(rb.get("gaps") or []),
                        }
                        for rb in bundle.get("resolved_logic_blocks") or []
                    ]
                    if groups:
                        upsert_logic_groups(job_id, groups)
        except Exception as exc:  # noqa: BLE001
            append_log(job_id, f"ERROR: {exc}")
            update_job(job_id, status="error", error_message=str(exc), current_step="Failed")

    threading.Thread(target=worker, daemon=True).start()


def enqueue_analyze_job(job_id: str, payload: dict[str, Any]) -> None:
    _ensure_store()
    from web.job_queue import enqueue

    enqueue(_WEB_DATA, job_id, payload)
    update_job(job_id, status="queued", current_step="Queued")
