"""HTTPS verify for outbound requests — Ubuntu company server skips strict SSL by default."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import requests

from src.utils.config_path import ALEX_ROOT, get_config_path

_LOG = logging.getLogger(__name__)

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


def _load_config() -> dict[str, Any]:
    try:
        from src.utils.yaml_utils import load_yaml

        path = get_config_path()
        if path.is_file():
            cfg = load_yaml(path)
            return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError, TypeError, ImportError):
        pass
    return {}


def _env_ssl_verify_disabled() -> bool:
    env = os.environ.get("M365_SSL_VERIFY", os.environ.get("ALEX_SSL_VERIFY", "")).strip().lower()
    return env in ("0", "false", "no", "off")


def _env_ssl_verify_required() -> bool:
    env = os.environ.get("M365_SSL_VERIFY", os.environ.get("ALEX_SSL_VERIFY", "")).strip().lower()
    return env in ("1", "true", "yes", "on")


def _production_server(cfg: dict[str, Any]) -> bool:
    mode = str((cfg.get("deployment") or {}).get("mode") or "").lower()
    return mode == "production"


def _config_ssl_verify_enabled() -> bool | None:
    """None = use deployment default; False = off; True = strict."""
    cfg = _load_config()
    m365 = (cfg.get("assist") or {}).get("m365") or {}
    if "ssl_verify" in m365:
        return bool(m365.get("ssl_verify"))
    if _production_server(cfg):
        return False
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
    """Ubuntu production (config.yaml): SSL verify OFF unless ssl_verify: true."""
    if _env_ssl_verify_disabled():
        return False
    if _env_ssl_verify_required():
        pass  # fall through to strict bundle lookup
    else:
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
    cfg = _load_config()
    company = _company_ca_path()
    return {
        "verify": str(ssl_verify_option()),
        "ssl_verify_disabled": ssl_verify_option() is False,
        "production_server": _production_server(cfg),
        "env_m365_ssl_verify": os.environ.get("M365_SSL_VERIFY", ""),
        "config_ssl_verify": _config_ssl_verify_enabled(),
        "company_ca": str(company) if company else None,
        "merged_ca_cache": str(_MERGED_CA_CACHE) if _MERGED_CA_CACHE.is_file() else None,
    }


def network_error_message(exc: Exception) -> str:
    return (
        "Cannot reach Microsoft login (network/firewall). "
        "Check outbound HTTPS to login.microsoftonline.com. "
        f"Detail: {exc}"
    )


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    verify = kwargs.pop("verify", ssl_verify_option())
    try:
        return requests.request(method, url, verify=verify, **kwargs)
    except requests.exceptions.SSLError as exc:
        if verify is not False:
            _LOG.warning("M365 HTTPS SSL verify failed — retrying without verify (company server default)")
            return requests.request(method, url, verify=False, **kwargs)
        raise RuntimeError(f"Microsoft HTTPS SSL error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(network_error_message(exc)) from exc


def requests_get(url: str, **kwargs: Any) -> requests.Response:
    return _request("GET", url, **kwargs)


def requests_post(url: str, **kwargs: Any) -> requests.Response:
    return _request("POST", url, **kwargs)
