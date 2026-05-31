"""Tests for M365 Copilot background task store."""

from __future__ import annotations

import time
from pathlib import Path

from web.m365_copilot_tasks import cancel_task, get_task_status, start_task


def test_start_and_complete_task(tmp_path: Path) -> None:
    job_id = "job-test-1"
    done: dict = {}

    def runner(task: dict, progress) -> dict:
        progress("Working…", current=1, total=1)
        time.sleep(0.05)
        return {"ok": True, "value": 42}

    public = start_task(
        job_id,
        tmp_path,
        kind="code_refine",
        payload={"instruction": "fix"},
        label="Test refine",
        runner=runner,
    )
    assert public["status"] == "running"
    task_id = public["task_id"]

    for _ in range(40):
        st = get_task_status(job_id, task_id, tmp_path)
        assert st is not None
        if st["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)

    final = get_task_status(job_id, task_id, tmp_path)
    assert final is not None
    assert final["status"] == "completed"
    assert final["result"]["ok"] is True
    assert final["result"]["value"] == 42


def test_cancel_task(tmp_path: Path) -> None:
    job_id = "job-test-2"

    def runner(task: dict, progress) -> dict:
        progress("Slow…")
        time.sleep(2)
        return {"ok": True}

    public = start_task(job_id, tmp_path, kind="copilot_plan", payload={}, runner=runner)
    task_id = public["task_id"]
    cancelled = cancel_task(job_id, task_id, tmp_path)
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
