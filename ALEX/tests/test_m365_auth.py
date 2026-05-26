"""M365 auth configuration resolution."""

import base64
import json
import time
from unittest.mock import MagicMock

from web import m365_auth


def _fake_jwt(claims: dict) -> str:
    """Return a JWT-like string whose payload base64url-decodes to ``claims``."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8")).decode().rstrip("=")
    return f"{header}.{body}.sig"


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


def test_server_managed_m365_from_config_yaml() -> None:
    cfg = {
        "assist": {
            "m365": {
                "client_id": "11111111-1111-1111-1111-111111111111",
                "tenant_id": "22222222-2222-2222-2222-222222222222",
            }
        }
    }
    assert m365_auth.server_managed_m365_setup(cfg) is True
    st = m365_auth.m365_status(cfg)
    assert st["server_managed_setup"] is True
    assert st["client_id_configured"] is True
    assert st["tenant_id"] == "22222222-2222-2222-2222-222222222222"
    try:
        m365_auth.save_local_registration(cfg, client_id="33333333-3333-3333-3333-333333333333")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "config.yaml" in str(exc)


def test_client_secret_configured_from_env(monkeypatch) -> None:
    cfg = {"assist": {"m365": {"client_id": "11111111-1111-1111-1111-111111111111", "client_secret": ""}}}
    assert m365_auth.client_secret_configured(cfg) is False
    monkeypatch.setenv("M365_CLIENT_SECRET", "test-secret")
    assert m365_auth.client_secret_configured(cfg) is True
    st = m365_auth.m365_status(cfg)
    assert st["client_secret_configured"] is True


def test_device_token_error_secret_valid_suggests_public_client_flow(monkeypatch) -> None:
    cfg = {"assist": {"m365": {"client_id": "11111111-1111-1111-1111-111111111111"}}}
    monkeypatch.setenv("M365_CLIENT_SECRET", "x")
    monkeypatch.setattr(m365_auth, "_client_secret_valid", lambda _cfg: True)
    msg = m365_auth._device_token_error(cfg, "AADSTS7000218: need client_secret")
    assert "Allow public client flows" in msg


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


def test_device_login_basic_scopes_only(tmp_path, monkeypatch) -> None:
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

    def fake_post(url, data=None, timeout=30, **kwargs):
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

    def fake_request(method, url, data=None, timeout=30, **kwargs):
        if method.upper() == "POST":
            return fake_post(url, data=data, timeout=timeout, **kwargs)
        raise AssertionError(method)

    monkeypatch.setattr("web.http_ssl.requests.request", fake_request)
    out = m365_auth.start_device_login(cfg)
    assert out["user_code"] == "ABCD1234"
    assert "User.Read" in captured["scope"]
    assert "Sites.Read.All" not in captured["scope"]
    assert "22222222-2222-2222-2222-222222222222" in captured["url"]


def test_copilot_device_login_includes_copilot_scopes(tmp_path, monkeypatch) -> None:
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

    def fake_post(url, data=None, timeout=30, **kwargs):
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

    def fake_request(method, url, data=None, timeout=30, **kwargs):
        if method.upper() == "POST":
            return fake_post(url, data=data, timeout=timeout, **kwargs)
        raise AssertionError(method)

    monkeypatch.setattr("web.http_ssl.requests.request", fake_request)
    m365_auth.start_copilot_device_login(cfg)
    assert "Sites.Read.All" in captured["scope"]
    assert "Mail.Read" in captured["scope"]


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

    def fake_post(url, data=None, timeout=30, **kwargs):
        calls.append(url)
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"error": "invalid_request"}
        resp.text = "bad"
        return resp

    def fake_request(method, url, data=None, timeout=30, **kwargs):
        if method.upper() == "POST":
            return fake_post(url, data=data, timeout=timeout, **kwargs)
        raise AssertionError(method)

    monkeypatch.setattr("web.http_ssl.requests.request", fake_request)
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


def test_decode_jwt_claims_extracts_tid() -> None:
    token = _fake_jwt({"tid": "abc123", "upn": "user@contoso.com"})
    claims = m365_auth._decode_jwt_claims(token)
    assert claims["tid"] == "abc123"
    assert claims["upn"] == "user@contoso.com"


def test_decode_jwt_claims_handles_bad_token() -> None:
    assert m365_auth._decode_jwt_claims("") == {}
    assert m365_auth._decode_jwt_claims("not-a-jwt") == {}
    assert m365_auth._decode_jwt_claims("a.b.c") == {}


def test_persist_entitlement_metadata_msa(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "SESSION_FILE", tmp_path / "session.json")
    sess: dict = {"access_token": "work-token"}

    def boom(method, *a, **k):
        raise AssertionError("licenseDetails should not be probed for MSA")

    monkeypatch.setattr("web.http_ssl.requests.request", boom)
    token_payload = {"id_token": _fake_jwt({"tid": m365_auth.MSA_TENANT_ID})}
    out = m365_auth._persist_entitlement_metadata(sess, token_payload)
    assert out["is_msa"] is True
    assert out["has_copilot_license"] is False
    assert out["copilot_license_checked"] is True
    assert m365_auth.is_copilot_chat_entitled(out) is False


def test_persist_entitlement_metadata_work_with_copilot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "SESSION_FILE", tmp_path / "session.json")
    sess: dict = {"access_token": "work-token"}

    def fake_get(url, headers=None, timeout=15, **kwargs):
        assert "licenseDetails" in url
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "value": [
                {"skuPartNumber": "SPB", "servicePlans": []},
                {"skuPartNumber": "Microsoft_365_Copilot", "servicePlans": []},
            ]
        }
        return resp

    def fake_request(method, url, headers=None, timeout=15, **kwargs):
        if method.upper() == "GET":
            return fake_get(url, headers=headers, timeout=timeout, **kwargs)
        raise AssertionError(method)

    monkeypatch.setattr("web.http_ssl.requests.request", fake_request)
    token_payload = {"id_token": _fake_jwt({"tid": "22222222-2222-2222-2222-222222222222"})}
    out = m365_auth._persist_entitlement_metadata(sess, token_payload)
    assert out["is_msa"] is False
    assert out["has_copilot_license"] is True
    assert m365_auth.is_copilot_chat_entitled(out) is True


def test_persist_entitlement_metadata_work_without_copilot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "SESSION_FILE", tmp_path / "session.json")
    sess: dict = {"access_token": "work-token"}

    def fake_get(url, headers=None, timeout=15, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "value": [
                {"skuPartNumber": "SPB", "servicePlans": [
                    {"servicePlanName": "M365_COPILOT_CHAT", "provisioningStatus": "Success"}
                ]},
            ]
        }
        return resp

    def fake_request(method, url, headers=None, timeout=15, **kwargs):
        if method.upper() == "GET":
            return fake_get(url, headers=headers, timeout=timeout, **kwargs)
        raise AssertionError(method)

    monkeypatch.setattr("web.http_ssl.requests.request", fake_request)
    token_payload = {"id_token": _fake_jwt({"tid": "33333333-3333-3333-3333-333333333333"})}
    out = m365_auth._persist_entitlement_metadata(sess, token_payload)
    assert out["is_msa"] is False
    assert out["has_copilot_license"] is False
    assert m365_auth.is_copilot_chat_entitled(out) is False


def test_status_payload_includes_entitlement_flags(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "M365_DIR", tmp_path)
    monkeypatch.setattr(m365_auth, "LOCAL_CONFIG_FILE", tmp_path / "local_config.json")
    monkeypatch.setattr(m365_auth, "SESSION_FILE", tmp_path / "session.json")
    monkeypatch.setattr(m365_auth, "PENDING_LOGIN_FILE", tmp_path / "pending.json")
    cfg = {"assist": {"m365": {"client_id": "11111111-1111-1111-1111-111111111111"}}}
    (tmp_path / "session.json").write_text(
        json.dumps(
            {
                "mode": "api",
                "access_token": "tok",
                "expires_at": time.time() + 600,
                "is_msa": True,
                "has_copilot_license": False,
                "copilot_license_checked": True,
                "tenant_id_from_token": m365_auth.MSA_TENANT_ID,
                "copilot_license_skus": [],
                "copilot_license_error": "MSA",
                "copilot_license_checked_at": m365_auth._now_iso(),
            }
        )
    )
    st = m365_auth.m365_status(cfg)
    assert st["api_ready"] is True
    assert st["is_msa"] is True
    assert st["copilot_chat_entitled"] is False
    assert st["not_entitled_reason"] == "msa"
    assert "Copilot Chat API" in st["entitlement_note"]
    assert st["activation_guide_url"].endswith("README.md")


def test_m365_copilot_not_entitled_classifier() -> None:
    from web import m365_copilot

    assert (
        m365_copilot._classify_not_entitled(
            400,
            '{"error":{"code":"BadRequest","message":"This API is not supported for MSA accounts ..."}}',
        )
        == "msa"
    )
    assert (
        m365_copilot._classify_not_entitled(
            400,
            '{"error":{"message":"no addressUrl for Microsoft.CopilotChat,False"}}',
        )
        == "msa"
    )
    assert (
        m365_copilot._classify_not_entitled(
            403,
            '{"error":{"message":"User is not licensed for Copilot."}}',
        )
        == "no_license"
    )
    assert m365_copilot._classify_not_entitled(500, "boom") is None


def test_m365_session_path_per_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(m365_auth, "WEB_DATA_ROOT", tmp_path)
    m365_auth._write_session({"mode": "api", "access_token": "alice-token"}, user_id="alice")
    session_file = tmp_path / "users" / "alice" / "m365" / "session.json"
    assert session_file.exists()
    assert m365_auth._read_session("alice")["access_token"] == "alice-token"
    assert m365_auth._read_session("bob") == {}
    assert m365_auth.m365_status(user_id="alice")["mode"] in ("api", "none")


def test_session_user_id_from_team_context(monkeypatch) -> None:
    from web.team_auth import TeamUser

    user = TeamUser(user_id=1, username="admin", role="admin")
    monkeypatch.setattr("web.security.get_current_user", lambda: user)
    assert m365_auth.session_user_id() == "admin"
    assert m365_auth.session_user_id("alice") == "alice"
