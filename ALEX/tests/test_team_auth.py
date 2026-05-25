"""Team username/password auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.utils.yaml_utils import dump_yaml


@pytest.fixture()
def team_client(tmp_path, monkeypatch):
    cfg = {
        "deployment": {"mode": "production", "host": "127.0.0.1", "port": 8765},
        "team_auth": {"enabled": True, "session_hours": 12, "cookie_secure": False},
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
    team_auth.create_user("admin", "adminpass1", role="admin")

    return TestClient(main.app), team_auth


def test_login_logout_me(team_client) -> None:
    client, _team_auth = team_client
    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass1"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert ok.status_code == 200
    assert ok.json()["username"] == "alice"
    assert ok.cookies.get("alex_session")

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "engineer"

    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_protected_api_requires_login(team_client) -> None:
    client, _team_auth = team_client
    assert client.get("/api/files").status_code == 401


def test_change_password(team_client) -> None:
    client, team_auth = team_client
    client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpass123"},
    )
    assert changed.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": "newpass123"}).status_code == 200


def test_expired_session_rejected(team_client) -> None:
    client, team_auth = team_client
    user = team_auth.get_user_by_username("alice")
    assert user is not None
    session_id = team_auth.create_session(user.user_id, hours=-1)
    conn = team_auth._require_conn()
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    conn.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", (expired, session_id))
    conn.commit()
    client.cookies.set("alex_session", session_id)
    assert client.get("/api/auth/me").status_code == 401


def test_admin_create_and_reset_user(team_client) -> None:
    client, _team_auth = team_client
    client.post("/api/auth/login", json={"username": "admin", "password": "adminpass1"})
    listed = client.get("/api/admin/users")
    assert listed.status_code == 200
    assert len(listed.json()["users"]) >= 2

    created = client.post(
        "/api/admin/users",
        json={"username": "bob", "password": "password123", "role": "engineer"},
    )
    assert created.status_code == 200

    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "bob", "password": "password123"}).status_code == 200
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"username": "admin", "password": "adminpass1"})
    reset = client.post(
        "/api/admin/users/bob/reset-password",
        json={"new_password": "newbobpass"},
    )
    assert reset.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "bob", "password": "newbobpass"}).status_code == 200


def test_remember_login_uses_longer_session(team_client) -> None:
    client, team_auth = team_client
    short = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "password123", "remember": False},
    )
    assert short.status_code == 200
    short_cookie = short.cookies.get("alex_session")
    short_remaining = team_auth.session_remaining_hours(short_cookie)
    assert short_remaining is not None
    assert 11 <= short_remaining <= 12.1

    client.post("/api/auth/logout")

    long = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "password123", "remember": True},
    )
    assert long.status_code == 200
    long_cookie = long.cookies.get("alex_session")
    long_remaining = team_auth.session_remaining_hours(long_cookie)
    assert long_remaining is not None
    assert long_remaining > 24 * 7

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    refreshed = team_auth.session_remaining_hours(long_cookie)
    assert refreshed is not None
    assert refreshed > 24 * 7
