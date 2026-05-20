"""M365 auth configuration resolution."""

import json
import time
from unittest.mock import MagicMock

from web import m365_auth


def test_client_id_from_local_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "LOCAL_CONFIG_FILE", tmp_path / "local_config.json")
    monkeypatch.setattr(m365_auth, "SESSION_FILE", tmp_path / "session.json")
    monkeypatch.setattr(m365_auth, "PENDING_LOGIN_FILE", tmp_path / "pending.json")
    cfg = {"assist": {"m365": {"client_id": ""}}}
    assert m365_auth.client_id_configured(cfg) is False
    m365_auth.save_local_registration(cfg, client_id="11111111-1111-1111-1111-111111111111")
    assert m365_auth.client_id_configured(cfg) is True
    st = m365_auth.m365_status(cfg)
    assert st["setup_required"] is False
    assert st["client_id_configured"] is True
    assert st["tenant_id"] == "common"
    assert st["local_client_id"] == "11111111-1111-1111-1111-111111111111"


def test_friendly_auth_error_tenant_vi() -> None:
    msg = m365_auth._friendly_auth_error(
        "User does not exist in tenant Microsoft Services and cannot access the application"
    )
    assert "Client ID" in msg or "client" in msg.lower()
    assert m365_auth.clear_local_registration()["setup_required"] is True


def test_friendly_auth_error_expired_code() -> None:
    msg = m365_auth._friendly_auth_error("expired_token")
    assert "expired" in msg.lower()
    assert "Sign in once" in msg


def test_device_login_uses_minimal_scopes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "PENDING_LOGIN_FILE", tmp_path / "pending.json")
    cfg = {
        "assist": {
            "m365": {
                "client_id": "11111111-1111-1111-1111-111111111111",
                "tenant_id": "22222222-2222-2222-2222-222222222222",
            }
        }
    }
    captured: dict[str, str] = {}

    def fake_post(url, data=None, timeout=30):
        captured["url"] = url
        captured["scope"] = data.get("scope", "")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "user_code": "ABCD1234",
            "device_code": "device-secret",
            "verification_uri": "https://login.microsoft.com/device",
            "expires_in": 900,
            "interval": 5,
        }
        return resp

    monkeypatch.setattr(m365_auth.requests, "post", fake_post)
    out = m365_auth.start_device_login(cfg)
    assert out["user_code"] == "ABCD1234"
    assert "User.Read" in captured["scope"]
    assert "Sites.Read.All" not in captured["scope"]
    assert "22222222-2222-2222-2222-222222222222" in captured["url"]


def test_explicit_tenant_no_fallback_to_common(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "PENDING_LOGIN_FILE", tmp_path / "pending.json")
    cfg = {
        "assist": {
            "m365": {
                "client_id": "11111111-1111-1111-1111-111111111111",
                "tenant_id": "22222222-2222-2222-2222-222222222222",
            }
        }
    }
    calls: list[str] = []

    def fake_post(url, data=None, timeout=30):
        calls.append(url)
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"error": "invalid_request"}
        resp.text = "bad"
        return resp

    monkeypatch.setattr(m365_auth.requests, "post", fake_post)
    try:
        m365_auth.start_device_login(cfg)
    except RuntimeError:
        pass
    assert len(calls) == 1
    assert "22222222-2222-2222-2222-222222222222" in calls[0]


def test_poll_expired_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    pending = tmp_path / "pending.json"
    monkeypatch.setattr(m365_auth, "PENDING_LOGIN_FILE", pending)
    pending.write_text(
        json.dumps(
            {
                "device_code": "x",
                "expires_at": time.time() - 10,
            }
        ),
        encoding="utf-8",
    )
    cfg = {"assist": {"m365": {"client_id": "11111111-1111-1111-1111-111111111111"}}}
    out = m365_auth.poll_device_login(cfg)
    assert out["status"] == "failed"
    assert "expired" in out["error"].lower()
    assert not pending.exists()
