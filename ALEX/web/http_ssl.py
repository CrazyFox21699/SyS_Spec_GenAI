"""HTTPS verify for outbound requests — Ubuntu ca-certificates and corporate CA bundles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


def ssl_verify_option() -> bool | str:
    """CA bundle for requests — certifi, env override, or disable (dev only)."""
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

        return certifi.where()
    except ImportError:
        return True


def ssl_error_message(exc: Exception) -> str:
    return (
        "SSL certificate verification failed when connecting to Microsoft. "
        "On Ubuntu run: sudo apt install -y ca-certificates && sudo update-ca-certificates, "
        "then restart ./chay.sh. "
        "If your company uses HTTPS inspection, ask IT for the root CA file and set in .env: "
        "REQUESTS_CA_BUNDLE=/path/to/company-ca.pem (or M365_CA_BUNDLE=...), then restart. "
        f"Technical detail: {exc}"
    )


def requests_get(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("verify", ssl_verify_option())
    try:
        return requests.get(url, **kwargs)
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(ssl_error_message(exc)) from exc


def requests_post(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("verify", ssl_verify_option())
    try:
        return requests.post(url, **kwargs)
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(ssl_error_message(exc)) from exc
