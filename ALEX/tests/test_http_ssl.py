"""Tests for HTTPS / CA bundle helpers."""

from __future__ import annotations

from web import http_ssl


def test_ssl_verify_disabled_on_production_default(monkeypatch) -> None:
    monkeypatch.delenv("M365_SSL_VERIFY", raising=False)
    monkeypatch.setattr(
        http_ssl,
        "_load_config",
        lambda: {"deployment": {"mode": "production"}, "assist": {"m365": {}}},
    )
    assert http_ssl.ssl_verify_option() is False


def test_ssl_verify_enabled_when_config_true(monkeypatch) -> None:
    monkeypatch.delenv("M365_SSL_VERIFY", raising=False)
    monkeypatch.setattr(
        http_ssl,
        "_load_config",
        lambda: {
            "deployment": {"mode": "production"},
            "assist": {"m365": {"ssl_verify": True}},
        },
    )
    opt = http_ssl.ssl_verify_option()
    assert opt is not False


def test_ssl_verify_disable_via_env(monkeypatch) -> None:
    monkeypatch.setenv("M365_SSL_VERIFY", "false")
    assert http_ssl.ssl_verify_option() is False


def test_ssl_retry_without_verify_on_failure(monkeypatch) -> None:
    from unittest.mock import MagicMock

    calls: list[bool | str] = []

    def fake_request(method, url, verify=True, **kwargs):
        calls.append(verify)
        if verify is not False:
            raise http_ssl.requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED")
        resp = MagicMock()
        resp.status_code = 200
        return resp

    monkeypatch.setattr(http_ssl.requests, "request", fake_request)
    monkeypatch.setattr(http_ssl, "ssl_verify_option", lambda: "/fake/ca.pem")
    r = http_ssl.requests_get("https://example.com", timeout=1)
    assert r.status_code == 200
    assert calls == ["/fake/ca.pem", False]
