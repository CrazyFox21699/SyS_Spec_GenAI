"""Microsoft 365 delegated login (device code) — isolated from GitHub Copilot CLI."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

WEB_DATA_ROOT = Path(__file__).resolve().parent.parent / "web_data"
M365_DIR = WEB_DATA_ROOT / "m365"
SESSION_FILE = M365_DIR / "session.json"
PENDING_LOGIN_FILE = M365_DIR / "pending_login.json"
LOCAL_CONFIG_FILE = M365_DIR / "local_config.json"

DEFAULT_TENANT = "common"
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

SETUP_MESSAGE = (
    "No Azure Application (client) ID configured. "
    "Create an app at portal.azure.com (or ask IT) and paste the ID into ALEX."
)


def _friendly_auth_error(message: str) -> str:
    """Map Microsoft OAuth errors to actionable English guidance."""
    raw = (message or "").strip()
    lower = raw.lower()
    if not raw:
        return raw
    if (
        "does not exist in the tenant" in lower
        or "không tồn tại trong đối tượng thuê" in lower
        or "cannot access the application" in lower
        or "không thể truy nhập" in lower
    ):
        return (
            "Wrong Client ID or wrong sign-in account. "
            "Clear M365 settings in ALEX → create a NEW app at portal.azure.com "
            "(Public client, multitenant) → paste the new Client ID → "
            "set Tenant to 'common' → sign in with a work/school account that has M365 Copilot "
            "(do not reuse someone else's Client ID)."
        )
    if "microsoft services" in lower:
        return (
            "Client ID belongs to the 'Microsoft Services' tenant and cannot be used with your account. "
            "Create your own app on portal.azure.com and paste a new Client ID."
        )
    if "not contained within any directory" in lower or "deprecated" in lower and "directory" in lower:
        return (
            "This Microsoft account has no Azure directory. "
            "Register for Azure free (azure.microsoft.com/free) or "
            "M365 Developer Program (developer.microsoft.com/microsoft-365/dev-program), "
            "then create a new App registration."
        )
    if "invalid_client" in lower or "client_id" in lower and "invalid" in lower:
        return "Invalid Client ID. Check the GUID from Azure → App registrations."
    if "personal microsoft account" in lower or "not supported" in lower:
        return (
            "Microsoft Copilot API does not support personal @outlook accounts. "
            "Use a work or school email with an M365 Copilot license."
        )
    if "admin consent" in lower or "consent" in lower:
        return "An administrator must grant admin consent for this app in Azure Portal."
    return raw

GRAPH_BASE = "https://graph.microsoft.com/beta"
DEFAULT_SCOPES = [
    "https://graph.microsoft.com/Sites.Read.All",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/People.Read.All",
    "https://graph.microsoft.com/OnlineMeetingTranscript.Read.All",
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/ChannelMessage.Read.All",
    "https://graph.microsoft.com/ExternalItem.Read.All",
    "offline_access",
    "openid",
    "profile",
    "User.Read",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _m365_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    m = assist.get("m365") if isinstance(assist.get("m365"), dict) else {}
    return m


def _read_local_config() -> dict[str, Any]:
    if not LOCAL_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(LOCAL_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _resolved_client_id(cfg: dict[str, Any]) -> str:
    cid = str(_m365_cfg(cfg).get("client_id") or "").strip()
    if cid:
        return cid
    cid = str(os.environ.get("M365_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID") or "").strip()
    if cid:
        return cid
    cid = str(_read_local_config().get("client_id") or "").strip()
    if cid:
        return cid
    return ""


def _resolved_tenant_id(cfg: dict[str, Any]) -> str:
    tid = str(_m365_cfg(cfg).get("tenant_id") or "").strip()
    if tid:
        return tid
    tid = str(os.environ.get("M365_TENANT_ID") or os.environ.get("AZURE_TENANT_ID") or "").strip()
    if tid:
        return tid
    tid = str(_read_local_config().get("tenant_id") or "").strip()
    return tid or DEFAULT_TENANT


def client_id_configured(cfg: dict[str, Any]) -> bool:
    return bool(_resolved_client_id(cfg))


def _tenant_id(cfg: dict[str, Any]) -> str:
    return _resolved_tenant_id(cfg)


def _client_id(cfg: dict[str, Any]) -> str:
    cid = _resolved_client_id(cfg)
    if not cid:
        raise ValueError(SETUP_MESSAGE)
    return cid


def save_local_registration(cfg: dict[str, Any], *, client_id: str, tenant_id: str = "") -> dict[str, Any]:
    cid = str(client_id or "").strip()
    if not cid:
        raise ValueError("Application (client) ID is required.")
    if not GUID_RE.match(cid):
        raise ValueError("Client ID must be a GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.")
    tid = str(tenant_id or DEFAULT_TENANT).strip() or DEFAULT_TENANT
    if tid in ("organizations", ""):
        tid = DEFAULT_TENANT
    M365_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_CONFIG_FILE.write_text(
        json.dumps({"client_id": cid, "tenant_id": tid, "saved_at": _now_iso()}, indent=2),
        encoding="utf-8",
    )
    return m365_status(cfg)


def clear_local_registration(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Remove saved client ID / session (fix wrong tenant or wrong app)."""
    if LOCAL_CONFIG_FILE.exists():
        LOCAL_CONFIG_FILE.unlink(missing_ok=True)
    if SESSION_FILE.exists():
        SESSION_FILE.unlink(missing_ok=True)
    if PENDING_LOGIN_FILE.exists():
        PENDING_LOGIN_FILE.unlink(missing_ok=True)
    return m365_status(cfg)


def _scopes(cfg: dict[str, Any]) -> str:
    raw = _m365_cfg(cfg).get("scopes")
    if isinstance(raw, list) and raw:
        parts = [str(s).strip() for s in raw if str(s).strip()]
    else:
        parts = DEFAULT_SCOPES[:]
    if "offline_access" not in parts:
        parts.append("offline_access")
    return " ".join(parts)


def _read_session() -> dict[str, Any]:
    if not SESSION_FILE.exists():
        return {}
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_session(data: dict[str, Any]) -> None:
    M365_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _token_expired(sess: dict[str, Any]) -> bool:
    exp = sess.get("expires_at")
    if not exp:
        return True
    try:
        return float(exp) < time.time() + 60
    except (TypeError, ValueError):
        return True


def _save_tokens(token_payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    sess = dict(existing or {})
    sess.update(
        {
            "mode": "api",
            "access_token": token_payload.get("access_token"),
            "refresh_token": token_payload.get("refresh_token") or sess.get("refresh_token"),
            "expires_at": time.time() + int(token_payload.get("expires_in", 3600)),
            "connected_at": _now_iso(),
        }
    )
    _write_session(sess)
    return sess


def _fetch_profile(access_token: str) -> dict[str, Any]:
    try:
        r = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return {}


def refresh_access_token(cfg: dict[str, Any]) -> dict[str, Any]:
    sess = _read_session()
    refresh = str(sess.get("refresh_token") or "").strip()
    if not refresh:
        raise PermissionError("M365 session expired. Sign in again.")
    tenant = _tenant_id(cfg)
    data = {
        "client_id": _client_id(cfg),
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "scope": _scopes(cfg),
    }
    r = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=data,
        timeout=30,
    )
    if r.status_code != 200:
        raise PermissionError(f"M365 token refresh failed: {r.text[:300]}")
    payload = r.json()
    sess = _save_tokens(payload, existing=sess)
    if not sess.get("display_name"):
        prof = _fetch_profile(str(sess.get("access_token") or ""))
        sess["display_name"] = prof.get("displayName") or prof.get("userPrincipalName") or "M365 user"
        sess["user_principal"] = prof.get("userPrincipalName", "")
        _write_session(sess)
    return sess


def get_valid_access_token(cfg: dict[str, Any]) -> str:
    sess = _read_session()
    if sess.get("mode") != "api" or not sess.get("access_token"):
        raise PermissionError("Sign in to Microsoft 365 Copilot first.")
    if _token_expired(sess):
        sess = refresh_access_token(cfg)
    token = str(sess.get("access_token") or "").strip()
    if not token:
        raise PermissionError("M365 access token missing. Sign in again.")
    return token


def _device_code_request(tenant: str, client_id: str, scope: str) -> requests.Response:
    return requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
        data={"client_id": client_id, "scope": scope},
        timeout=30,
    )


def start_device_login(cfg: dict[str, Any]) -> dict[str, Any]:
    client_id = _client_id(cfg)
    scope = _scopes(cfg)
    tenant = _tenant_id(cfg)
    r = _device_code_request(tenant, client_id, scope)
    if r.status_code != 200 and tenant != DEFAULT_TENANT:
        r = _device_code_request(DEFAULT_TENANT, client_id, scope)
        tenant = DEFAULT_TENANT
    if r.status_code != 200:
        try:
            err_body = r.json()
            detail = err_body.get("error_description") or err_body.get("error") or r.text
        except (json.JSONDecodeError, ValueError):
            detail = r.text[:400]
        raise RuntimeError(_friendly_auth_error(str(detail)))
    payload = r.json()
    pending = {
        "device_code": payload.get("device_code"),
        "user_code": payload.get("user_code"),
        "verification_uri": payload.get("verification_uri"),
        "expires_in": payload.get("expires_in"),
        "interval": payload.get("interval", 5),
        "started_at": _now_iso(),
        "tenant_used": tenant,
    }
    M365_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_LOGIN_FILE.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "user_code": pending.get("user_code"),
        "verification_uri": pending.get("verification_uri"),
        "message": payload.get("message"),
        "expires_in": pending.get("expires_in"),
        "interval": pending.get("interval"),
    }


def poll_device_login(cfg: dict[str, Any]) -> dict[str, Any]:
    if not PENDING_LOGIN_FILE.exists():
        sess = _read_session()
        if sess.get("mode") == "api" and sess.get("access_token") and not _token_expired(sess):
            return {"ok": True, "status": "completed", **m365_status(cfg)}
        return {"ok": False, "status": "no_pending_login", "error": "Call login/start first."}
    pending = json.loads(PENDING_LOGIN_FILE.read_text(encoding="utf-8"))
    device_code = pending.get("device_code")
    tenant = str(pending.get("tenant_used") or _tenant_id(cfg) or DEFAULT_TENANT)
    client_id = _client_id(cfg)
    r = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
            "device_code": device_code,
        },
        timeout=30,
    )
    body = r.json() if r.text else {}
    err = body.get("error")
    if err == "authorization_pending":
        return {"ok": False, "status": "pending", "message": "Complete sign-in in the browser."}
    if err == "slow_down":
        return {"ok": False, "status": "pending", "interval": int(body.get("interval", 5))}
    if r.status_code != 200:
        raw_err = str(body.get("error_description") or body.get("error") or r.text[:300])
        return {"ok": False, "status": "failed", "error": _friendly_auth_error(raw_err), "error_raw": raw_err[:500]}
    PENDING_LOGIN_FILE.unlink(missing_ok=True)
    sess = _save_tokens(body)
    prof = _fetch_profile(str(sess.get("access_token") or ""))
    sess["display_name"] = prof.get("displayName") or prof.get("userPrincipalName") or "M365 user"
    sess["user_principal"] = prof.get("userPrincipalName", "")
    _write_session(sess)
    return {"ok": True, "status": "completed", **m365_status(cfg)}


def m365_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    sess = _read_session()
    mode = str(sess.get("mode") or "")
    api_ready = mode == "api" and bool(sess.get("access_token")) and not _token_expired(sess)
    if mode == "api" and sess.get("access_token") and _token_expired(sess) and cfg:
        try:
            refresh_access_token(cfg)
            sess = _read_session()
            api_ready = True
        except (PermissionError, requests.RequestException, ValueError):
            api_ready = False
    configured = client_id_configured(cfg) if cfg else bool(sess.get("access_token"))
    pending = PENDING_LOGIN_FILE.exists()
    local = _read_local_config() if cfg else {}
    resolved_cid = _resolved_client_id(cfg) if cfg else ""
    return {
        "connected": api_ready,
        "mode": "api" if api_ready else (mode or "none"),
        "connected_at": sess.get("connected_at"),
        "display_name": sess.get("display_name"),
        "user_principal": sess.get("user_principal"),
        "api_ready": api_ready,
        "client_id_configured": configured,
        "setup_required": not configured,
        "login_pending": pending,
        "setup_message": SETUP_MESSAGE,
        "tenant_id": _resolved_tenant_id(cfg) if cfg else DEFAULT_TENANT,
        "client_id_preview": f"{resolved_cid[:8]}…" if len(resolved_cid) > 8 else "",
        "has_local_config": bool(local.get("client_id")),
        "device_login_url": "https://microsoft.com/devicelogin",
        "azure_portal_url": "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/applicationsListBlade",
        "note": (
            "Signed in to Microsoft 365 Copilot (Graph API)."
            if api_ready
            else SETUP_MESSAGE
            if not configured
            else "Sign in with Microsoft 365 to apply Knowledge workbench via Copilot."
        ),
    }


def disconnect() -> dict[str, Any]:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink(missing_ok=True)
    if PENDING_LOGIN_FILE.exists():
        PENDING_LOGIN_FILE.unlink(missing_ok=True)
    return m365_status()


def is_api_ready(cfg: dict[str, Any]) -> bool:
    try:
        get_valid_access_token(cfg)
        return True
    except (PermissionError, ValueError, requests.RequestException):
        return False


def require_api_token(cfg: dict[str, Any]) -> str:
    return get_valid_access_token(cfg)
