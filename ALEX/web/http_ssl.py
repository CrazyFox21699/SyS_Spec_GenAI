"""HTTPS verify for outbound requests — Ubuntu ca-certificates and corporate CA bundles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from src.utils.config_path import ALEX_ROOT, get_config_path

_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/cert.pem",
)

_COMPANY_CA_CANDIDATES = (
    "company-ca.pem",
    "config/company-ca.pem",
    "web_data/company-ca.pem",
)

_MERGED_CA_CACHE = ALEX_ROOT / "web_data" / ".ssl" / "merged-ca.pem"


def _env_ssl_verify_disabled() -> bool:
    env = os.environ.get("M365_SSL_VERIFY", os.environ.get("ALEX_SSL_VERIFY", "")).strip().lower()
    return env in ("0", "false", "no", "off")


def _config_ssl_verify_enabled() -> bool | None:
    """None = not set in config; False = explicit disable (corporate proxy)."""
    try:
        from src.utils.yaml_utils import load_yaml

        path = get_config_path()
        if not path.is_file():
            return None
        cfg = load_yaml(path)
        m365 = (cfg.get("assist") or {}).get("m365") or {}
        if "ssl_verify" not in m365:
            return None
        return bool(m365.get("ssl_verify"))
    except (OSError, ValueError, TypeError, ImportError):
        return None


def _company_ca_path() -> Path | None:
    env_path = os.environ.get("M365_CA_BUNDLE", "").strip()
    if env_path:
        resolved = Path(env_path).expanduser()
        if resolved.is_file():
            return resolved
    for rel in _COMPANY_CA_CANDIDATES:
        candidate = ALEX_ROOT / rel
        if candidate.is_file():
            return candidate
    return None


def _base_ca_bundle() -> str | None:
    for key in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
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
    return None


def _merge_ca_files(*paths: Path) -> str:
    _MERGED_CA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    seen: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        parts.append(text)
    _MERGED_CA_CACHE.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return str(_MERGED_CA_CACHE)


def ssl_verify_option() -> bool | str:
    """CA bundle for requests — env/config override, merged company CA, or disable."""
    if _env_ssl_verify_disabled():
        return False
    cfg_verify = _config_ssl_verify_enabled()
    if cfg_verify is False:
        return False

    company = _company_ca_path()
    base = _base_ca_bundle()
    if company and base:
        return _merge_ca_files(Path(base), company)
    if company:
        return str(company)
    if base:
        return base
    return True


def ssl_verify_status() -> dict[str, Any]:
    """Diagnostics for ubuntu_m365_ssl_check.sh and /api/m365/connectivity."""
    company = _company_ca_path()
    return {
        "verify": str(ssl_verify_option()),
        "ssl_verify_disabled": ssl_verify_option() is False,
        "env_m365_ssl_verify": os.environ.get("M365_SSL_VERIFY", ""),
        "config_ssl_verify": _config_ssl_verify_enabled(),
        "company_ca": str(company) if company else None,
        "merged_ca_cache": str(_MERGED_CA_CACHE) if _MERGED_CA_CACHE.is_file() else None,
    }


def ssl_error_message(exc: Exception) -> str:
    return (
        "SSL certificate verification failed when connecting to Microsoft "
        "(unable to get local issuer certificate — common on company proxy). "
        "Fix option 1 (fast): add M365_SSL_VERIFY=false to .env and restart ./chay.sh. "
        "Fix option 2 (secure): ask IT for root CA, save as ALEX/config/company-ca.pem, restart. "
        "Fix option 3: sudo apt install -y ca-certificates && sudo update-ca-certificates && pip install certifi. "
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
