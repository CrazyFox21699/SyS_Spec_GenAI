"""M365 auth configuration resolution."""

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


def test_friendly_auth_error_tenant_vi() -> None:
    msg = m365_auth._friendly_auth_error(
        "User does not exist in tenant Microsoft Services and cannot access the application"
    )
    assert "Client ID" in msg or "client" in msg.lower()
    assert m365_auth.clear_local_registration()["setup_required"] is True
