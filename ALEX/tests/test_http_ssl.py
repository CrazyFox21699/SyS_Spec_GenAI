"""Tests for HTTPS / CA bundle helpers."""

from __future__ import annotations

from web import http_ssl


def test_ssl_verify_uses_certifi_by_default(monkeypatch) -> None:
    monkeypatch.delenv("M365_SSL_VERIFY", raising=False)
    monkeypatch.delenv("ALEX_SSL_VERIFY", raising=False)
    monkeypatch.delenv("M365_CA_BUNDLE", raising=False)
    opt = http_ssl.ssl_verify_option()
    assert opt is not False
    if opt is not True:
        assert str(opt).endswith(".pem")


def test_ssl_verify_disable_via_env(monkeypatch) -> None:
    monkeypatch.setenv("M365_SSL_VERIFY", "false")
    assert http_ssl.ssl_verify_option() is False


def test_ssl_error_message_mentions_ca_certificates() -> None:
    msg = http_ssl.ssl_error_message(Exception("CERTIFICATE_VERIFY_FAILED"))
    assert "ca-certificates" in msg
