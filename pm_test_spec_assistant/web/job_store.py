"""Persistent job metadata (SQLite) for production mode; falls back to memory in local mode."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DB_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None
_DB_PATH: Path | None = None


@dataclass
class JobRecord:
    job_id: str
    status: str = "waiting"
    current_step: str = ""
    progress: int = 0
    warnings: int = 0
    errors: int = 0
    log: list[str] = field(default_factory=list)
    output_dir: str | None = None
    bundle_version: int = 0
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    queue_position: int | None = None


def init_db(data_root: Path, *, production: bool = False) -> None:
    global _CONN, _DB_PATH
    if not production:
        _CONN = None
        return
    data_root.mkdir(parents=True, exist_ok=True)
    _DB_PATH = data_root / "alex_jobs.db"
    _CONN = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    _CONN.row_factory = sqlite3.Row
    with _DB_LOCK:
        _CONN.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_step TEXT,
                progress INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                log_json TEXT,
                output_dir TEXT,
                bundle_version INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT,
                created_by TEXT,
                queue_position INTEGER
            );
            CREATE TABLE IF NOT EXISTS job_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE,
                payload_json TEXT,
                status TEXT DEFAULT 'queued',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS logic_groups (
                job_id TEXT,
                logic_id TEXT,
                control_name TEXT,
                gate_status TEXT,
                parse_status TEXT,
                unresolved_count INTEGER,
                PRIMARY KEY (job_id, logic_id)
            );
            """
        )
        _CONN.commit()


def _require_conn() -> sqlite3.Connection:
    if _CONN is None:
        raise RuntimeError("Job store not initialized (deployment.mode != production)")
    return _CONN


def insert_job(record: JobRecord) -> None:
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs
            (job_id, status, current_step, progress, warnings, errors, log_json,
             output_dir, bundle_version, error_message, created_at, created_by, queue_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id,
                record.status,
                record.current_step,
                record.progress,
                record.warnings,
                record.errors,
                json.dumps(record.log[-200:]),
                record.output_dir,
                record.bundle_version,
                record.error_message,
                record.created_at,
                record.created_by,
                record.queue_position,
            ),
        )
        conn.commit()


def update_job_record(job_id: str, **fields: Any) -> None:
    conn = _require_conn()
    allowed = {
        "status",
        "current_step",
        "progress",
        "warnings",
        "errors",
        "output_dir",
        "bundle_version",
        "error_message",
        "queue_position",
    }
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
        if k == "log":
            sets.append("log_json = ?")
            vals.append(json.dumps(v[-200:] if isinstance(v, list) else []))
    if not sets:
        return
    vals.append(job_id)
    with _DB_LOCK:
        conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", vals)
        conn.commit()


def get_job_record(job_id: str) -> JobRecord | None:
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return JobRecord(
        job_id=row["job_id"],
        status=row["status"],
        current_step=row["current_step"] or "",
        progress=row["progress"] or 0,
        warnings=row["warnings"] or 0,
        errors=row["errors"] or 0,
        log=json.loads(row["log_json"] or "[]"),
        output_dir=row["output_dir"],
        bundle_version=row["bundle_version"] or 0,
        error_message=row["error_message"],
        created_at=row["created_at"] or "",
        created_by=row["created_by"] or "system",
        queue_position=row["queue_position"],
    )


def list_jobs(limit: int = 50) -> list[JobRecord]:
    conn = _require_conn()
    with _DB_LOCK:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        JobRecord(
            job_id=r["job_id"],
            status=r["status"],
            current_step=r["current_step"] or "",
            progress=r["progress"] or 0,
            warnings=r["warnings"] or 0,
            errors=r["errors"] or 0,
            log=json.loads(r["log_json"] or "[]"),
            output_dir=r["output_dir"],
            bundle_version=r["bundle_version"] or 0,
            error_message=r["error_message"],
            created_at=r["created_at"] or "",
            created_by=r["created_by"] or "system",
            queue_position=r["queue_position"],
        )
        for r in rows
    ]


def upsert_logic_groups(job_id: str, groups: list[dict[str, Any]]) -> None:
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute("DELETE FROM logic_groups WHERE job_id = ?", (job_id,))
        for g in groups:
            conn.execute(
                """
                INSERT INTO logic_groups (job_id, logic_id, control_name, gate_status, parse_status, unresolved_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    g.get("logic_id", ""),
                    g.get("control_name", ""),
                    g.get("gate_status", ""),
                    g.get("parse_status", ""),
                    g.get("unresolved_count", 0),
                ),
            )
        conn.commit()


def enqueue_analyze(job_id: str, payload: dict[str, Any]) -> None:
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute(
            """
            INSERT OR REPLACE INTO job_queue (job_id, payload_json, status, created_at)
            VALUES (?, ?, 'queued', ?)
            """,
            (job_id, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def dequeue_analyze() -> tuple[str, dict[str, Any]] | None:
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute(
            "SELECT job_id, payload_json FROM job_queue WHERE status = 'queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE job_queue SET status = 'running' WHERE job_id = ?", (row["job_id"],)
        )
        conn.commit()
    return row["job_id"], json.loads(row["payload_json"] or "{}")
