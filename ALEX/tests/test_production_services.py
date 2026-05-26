from __future__ import annotations

import json
from pathlib import Path

import pytest

from web.bundle_store import load_split_bundle, save_split_bundle, update_overlay
from web.job_queue import complete, dequeue, enqueue
from web.job_store import JobRecord, get_job_record, init_db, insert_job, upsert_logic_groups


@pytest.fixture
def prod_data(tmp_path: Path) -> Path:
    init_db(tmp_path, production=True)
    return tmp_path


def test_job_store_roundtrip(prod_data: Path) -> None:
    insert_job(JobRecord(job_id="analysis_test_1", status="queued"))
    rec = get_job_record("analysis_test_1")
    assert rec is not None
    assert rec.status == "queued"


def test_get_job_prefers_sqlite_in_production(tmp_path: Path, monkeypatch) -> None:
    from web import jobs as jobs_mod

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("deployment:\n  mode: production\n", encoding="utf-8")
    monkeypatch.setattr(jobs_mod, "_CONFIG_PATH", cfg_path)
    monkeypatch.setattr(jobs_mod, "_WEB_DATA", tmp_path)
    monkeypatch.setattr(jobs_mod, "_store_initialized", False)
    monkeypatch.setattr("web.job_store._CONN", None)

    job = jobs_mod.create_job(created_by="alice")
    jobs_mod.update_job(job.job_id, status="queued", current_step="Queued for worker", progress=0)

    from web.job_store import update_job_record

    update_job_record(job.job_id, status="running", current_step="Extracting signals", progress=42)

    fresh = jobs_mod.get_job(job.job_id)
    assert fresh is not None
    assert fresh.status == "running"
    assert fresh.progress == 42
    assert fresh.current_step == "Extracting signals"


def test_logic_groups_upsert(prod_data: Path) -> None:
    upsert_logic_groups(
        "analysis_test_1",
        [
            {
                "logic_id": "T1",
                "control_name": "SHUTOFF_DECISION",
                "gate_status": "ready",
                "parse_status": "ok",
                "unresolved_count": 0,
            }
        ],
    )


def test_file_queue_enqueue_dequeue(prod_data: Path) -> None:
    enqueue(prod_data, "job_a", {"input_dir": "/tmp/in"})
    item = dequeue(prod_data)
    assert item is not None
    jid, payload = item
    assert jid == "job_a"
    assert payload["input_dir"] == "/tmp/in"
    complete(prod_data, jid)


def test_split_bundle_and_overlay_version(tmp_path: Path) -> None:
    out = tmp_path / "job1"
    out.mkdir()
    bundle = {
        "product": "ALEX",
        "test_candidates": [{"id": "TC1"}],
        "logic_blocks": [],
        "resolved_logic_blocks": [],
        "ai_assists": {"candidate_overlays": {"TC1": {"en": {"input": "a"}}}},
    }
    v1 = save_split_bundle(out, bundle)
    assert v1 == 1
    loaded = load_split_bundle(out)
    assert loaded is not None
    assert loaded["test_candidates"][0]["id"] == "TC1"
    v2 = update_overlay(out, "TC1", {"en": {"input": "b"}}, expected_version=1)
    assert v2 == 2
    with pytest.raises(ValueError, match="version conflict"):
        update_overlay(out, "TC1", {"en": {"input": "c"}}, expected_version=1)
    manifest = json.loads((out / "bundle" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 2
