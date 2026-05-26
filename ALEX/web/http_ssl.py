"""HTTPS verify for outbound requests — Ubuntu ca-certificates and corporate CA bundles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/cert.pem",
)


def ssl_verify_option() -> bool | str:
    """CA bundle for requests — env override, certifi, Ubuntu system store, or disable."""
    env = os.environ.get("M365_SSL_VERIFY", os.environ.get("ALEX_SSL_VERIFY", "")).strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    for key in ("M365_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(key, "").strip()
        if path:
            resolved = Path(path).expanduser()
            if resolved.is_file():
                return str(resolved)
    try:
        import certifi

        bundle = certifi.where()
        if bundle and Path(bundle).is_file():
            return bundle
    except ImportError:
        pass
    for system_path in _SYSTEM_CA_BUNDLES:
        if Path(system_path).is_file():
            return system_path
    return True


def ssl_error_message(exc: Exception) -> str:
    return (
        "SSL certificate verification failed when connecting to Microsoft. "
        "On Ubuntu run: sudo apt install -y ca-certificates && sudo update-ca-certificates, "
        "then: cd ALEX && source .venv/bin/activate && pip install certifi && ./chay.sh. "
        "Company proxy: add to .env → REQUESTS_CA_BUNDLE=/path/to/company-ca.pem and restart. "
        "Temporary test only: M365_SSL_VERIFY=false in .env. "
        f"Technical detail: {exc}"
    )


def network_error_message(exc: Exception) -> str:
    return (
        "Cannot reach Microsoft login (network/firewall/proxy). "
        "Ask IT to allow HTTPS outbound to login.microsoftonline.com and graph.microsoft.com. "
        f"Technical detail: {exc}"
    )


def _raise_friendly_request_error(exc: Exception) -> None:
    if isinstance(exc, requests.exceptions.SSLError):
        raise RuntimeError(ssl_error_message(exc)) from exc
    if isinstance(exc, requests.exceptions.RequestException):
        raise RuntimeError(network_error_message(exc)) from exc
    raise exc


def requests_get(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("verify", ssl_verify_option())
    try:
        return requests.get(url, **kwargs)
    except Exception as exc:
        _raise_friendly_request_error(exc)
        raise AssertionError("unreachable")


def requests_post(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("verify", ssl_verify_option())
    try:
        return requests.post(url, **kwargs)
    except Exception as exc:
        _raise_friendly_request_error(exc)
        raise AssertionError("unreachable")
