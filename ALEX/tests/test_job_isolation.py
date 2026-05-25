"""Job isolation by team user."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.utils.yaml_utils import dump_yaml


@pytest.fixture()
def isolated_client(tmp_path, monkeypatch):
    cfg = {
        "deployment": {"mode": "production"},
        "team_auth": {"enabled": True, "session_hours": 12},
        "security": {"enabled": True, "require_token": False},
    }
    cfg_path = tmp_path / "config.yaml"
    dump_yaml(cfg_path, cfg)

    import web.main as main

    monkeypatch.setattr(main, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(main, "WEB_DATA", tmp_path)
    monkeypatch.setattr(main, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr("web.jobs._WEB_DATA", tmp_path)
    monkeypatch.setattr("web.jobs._store_initialized", False)
    monkeypatch.setattr("web.job_store._CONN", None)
    monkeypatch.setattr(
        "web.security.TeamAuthMiddleware._cfg_loaded",
        lambda self: cfg,
    )

    from web import team_auth

    monkeypatch.setattr(team_auth, "_CONN", None)
    monkeypatch.setattr(team_auth, "_DB_PATH", None)
    team_auth.init_user_db(tmp_path)
    team_auth.create_user("alice", "password123", role="engineer")
    team_auth.create_user("bob", "password123", role="engineer")
    team_auth.create_user("admin", "adminpass1", role="admin")

    from web.job_store import JobRecord, init_db, insert_job

    init_db(tmp_path, production=True)
    job_id = "analysis_test_alice_001"
    out_dir = tmp_path / "output" / "alice" / job_id
    out_dir.mkdir(parents=True)
    dump_yaml(out_dir / "ui_bundle.yaml", {"product": "ALEX", "summary": {}, "test_candidates": []})
    insert_job(JobRecord(job_id=job_id, status="done", created_by="alice", output_dir=str(out_dir)))

    client = TestClient(main.app)
    return client, job_id


def _login(client: TestClient, username: str) -> None:
    password = "adminpass1" if username == "admin" else "password123"
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text


def test_engineer_cannot_read_other_job(isolated_client) -> None:
    client, job_id = isolated_client
    _login(client, "bob")
    assert client.get(f"/api/jobs/{job_id}/summary").status_code == 403


def test_owner_can_read_job(isolated_client) -> None:
    client, job_id = isolated_client
    _login(client, "alice")
    res = client.get(f"/api/jobs/{job_id}/summary")
    assert res.status_code == 200
    assert res.json()["job_id"] == job_id


def test_admin_can_read_any_job(isolated_client) -> None:
    client, job_id = isolated_client
    _login(client, "admin")
    assert client.get(f"/api/jobs/{job_id}/summary").status_code == 200


def test_job_list_filtered_for_engineer(isolated_client) -> None:
    client, job_id = isolated_client
    _login(client, "alice")
    jobs = client.get("/api/jobs").json()["jobs"]
    assert any(j["job_id"] == job_id for j in jobs)
    client.post("/api/auth/logout")
    _login(client, "bob")
    jobs_b = client.get("/api/jobs").json()["jobs"]
    assert not any(j["job_id"] == job_id for j in jobs_b)
