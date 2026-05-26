"""Microsoft 365 delegated login (device code) — isolated from GitHub Copilot CLI."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

try:
    from web.http_ssl import requests_get, requests_post, ssl_verify_option, ssl_verify_status
except ImportError:
    import logging as _logging

    _ssl_log = _logging.getLogger(__name__)

    def ssl_verify_option() -> bool:  # type: ignore[misc]
        """Fallback when web/http_ssl.py missing on server — skip SSL verify."""
        return False

    def ssl_verify_status() -> dict[str, Any]:  # type: ignore[misc]
        return {
            "verify": "False",
            "ssl_verify_disabled": True,
            "note": "web/http_ssl.py not found — using verify=False (copy http_ssl.py optional)",
        }

    def _m365_request(method: str, url: str, **kwargs: Any):
        verify = kwargs.pop("verify", False)
        try:
            return requests.request(method, url, verify=verify, **kwargs)
        except requests.exceptions.SSLError as exc:
            if verify is not False:
                _ssl_log.warning("M365 SSL failed — retry without verify: %s", exc)
                return requests.request(method, url, verify=False, **kwargs)
            raise RuntimeError(f"Microsoft HTTPS SSL error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Microsoft network error: {exc}") from exc

    def requests_get(url: str, **kwargs: Any):  # type: ignore[misc]
        return _m365_request("GET", url, **kwargs)

    def requests_post(url: str, **kwargs: Any):  # type: ignore[misc]
        return _m365_request("POST", url, **kwargs)

# Microsoft uses this well-known tenant id for personal Microsoft accounts
# (outlook.com / hotmail.com / live.com / msn.com / xbox.com / etc.). Any
# id_token whose ``tid`` claim equals this guid is an MSA — Microsoft 365
# Copilot Chat Graph API is not available for those accounts.
MSA_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

# License SKUs / service plans that unlock the Microsoft.CopilotChat Graph
# endpoint we hit from web/m365_copilot.py. The full add-on SKU is
# ``Microsoft_365_Copilot``; service plan names contain ``M365_COPILOT`` but
# we explicitly exclude the free ``M365_COPILOT_CHAT`` plan that ships with
# Business Premium and does NOT expose /copilot/conversations.
COPILOT_SKU_PARTS = ("Microsoft_365_Copilot", "M365_COPILOT_ENTERPRISE")
COPILOT_SERVICE_PLAN_PREFIXES = ("M365_COPILOT",)
COPILOT_FREE_PLAN_NAMES = ("M365_COPILOT_CHAT",)

WEB_DATA_ROOT = Path(__file__).resolve().parent.parent / "web_data"
M365_DIR = WEB_DATA_ROOT / "m365"
SESSION_FILE = M365_DIR / "session.json"
PENDING_LOGIN_FILE = M365_DIR / "pending_login.json"
LOCAL_CONFIG_FILE = M365_DIR / "local_config.json"


def _m365_paths(user_id: str | None = None) -> tuple[Path, Path, Path]:
    """Return (base_dir, session_file, pending_login_file) for a user or legacy global."""
    uid = session_user_id(user_id)
    if uid:
        base = WEB_DATA_ROOT / "users" / uid / "m365"
        return base, base / "session.json", base / "pending_login.json"
    return M365_DIR, SESSION_FILE, PENDING_LOGIN_FILE


def session_user_id(explicit: str | None = None) -> str | None:
    """Ubuntu team server: map HTTP session → web_data/users/<username>/m365/."""
    if explicit:
        return explicit
    try:
        from web.security import get_current_user
        from web.team_auth import TeamUser

        user = get_current_user()
        return user.username if isinstance(user, TeamUser) else None
    except ImportError:
        return None

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
    if "client_assertion" in lower or "client_secret" in lower and "7000218" in raw:
        return (
            "Azure app requires the client secret Value. Add M365_CLIENT_SECRET to the .env file "
            "(next to config.yaml), then restart ./dev.sh or ./chay.sh. Secret ID alone cannot be used. "
            "Alternatively, IT can enable Allow public client flows on the app registration."
        )
    if "personal microsoft account" in lower or "not supported" in lower:
        return (
            "Microsoft Copilot API does not support personal @outlook accounts. "
            "Use a work or school email with an M365 Copilot license."
        )
    if "admin consent" in lower or "consent" in lower:
        return "An administrator must grant admin consent for this app in Azure Portal."
    hint = _device_code_error_hint(lower)
    if hint:
        return hint
    return raw


def _device_code_error_hint(lower: str) -> str:
    if "expired_token" in lower or "code has expired" in lower or "hết hạn" in lower:
        return (
            "Device sign-in code expired. Click Sign in once, open the link immediately, "
            "enter the code shown in ALEX (do not reuse an old code or QR). "
            "Do not click Sign in again while waiting."
        )
    if "authorization_declined" in lower or "access_denied" in lower:
        return "Sign-in was cancelled or denied. Click Sign in and approve the request."
    if "bad_verification_code" in lower:
        return "Wrong or expired code at login.microsoft.com/device. Use the exact code shown in ALEX."
    return ""


GRAPH_BASE = "https://graph.microsoft.com/beta"

DEVICE_LOGIN_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "User.Read",
]

# Optional extra delegated scopes for Copilot context (IT must grant + admin consent).
# Sign-in uses DEVICE_LOGIN_SCOPES only. Do not request Application permissions.
COPILOT_API_SCOPES = [
    "https://graph.microsoft.com/Sites.Read.All",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/People.Read.All",
    "https://graph.microsoft.com/OnlineMeetingTranscript.Read.All",
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/ChannelMessage.Read.All",
    "https://graph.microsoft.com/ExternalItem.Read.All",
]

DEFAULT_SCOPES = DEVICE_LOGIN_SCOPES + COPILOT_API_SCOPES


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


def _yaml_client_id(cfg: dict[str, Any]) -> str:
    return str(_m365_cfg(cfg).get("client_id") or "").strip()


def _env_client_id() -> str:
    return str(os.environ.get("M365_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID") or "").strip()


def _yaml_tenant_id(cfg: dict[str, Any]) -> str:
    return str(_m365_cfg(cfg).get("tenant_id") or "").strip()


def _env_tenant_id() -> str:
    return str(os.environ.get("M365_TENANT_ID") or os.environ.get("AZURE_TENANT_ID") or "").strip()


def _client_secret(cfg: dict[str, Any]) -> str:
    """Optional — only for Azure apps registered as Web/confidential client (server config only)."""
    secret = str(_m365_cfg(cfg).get("client_secret") or "").strip()
    if secret:
        return secret
    return str(os.environ.get("M365_CLIENT_SECRET") or os.environ.get("AZURE_CLIENT_SECRET") or "").strip()


def client_secret_configured(cfg: dict[str, Any]) -> bool:
    return bool(_client_secret(cfg))


def _oauth_client_fields(cfg: dict[str, Any]) -> dict[str, str]:
    fields = {"client_id": _client_id(cfg)}
    secret = _client_secret(cfg)
    if secret:
        fields["client_secret"] = secret
    return fields


def server_managed_m365_setup(cfg: dict[str, Any]) -> bool:
    """True when Client ID is pinned in config.yaml or env — users must not re-enter in UI."""
    return bool(_yaml_client_id(cfg) or _env_client_id())


def _resolved_client_id(cfg: dict[str, Any]) -> str:
    cid = _yaml_client_id(cfg)
    if cid:
        return cid
    cid = _env_client_id()
    if cid:
        return cid
    cid = str(_read_local_config().get("client_id") or "").strip()
    if cid:
        return cid
    return ""


def _resolved_tenant_id(cfg: dict[str, Any]) -> str:
    tid = _yaml_tenant_id(cfg)
    if tid:
        return tid
    tid = _env_tenant_id()
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
    if server_managed_m365_setup(cfg):
        raise ValueError(
            "M365 app is configured in config.yaml by IT. Users only need Sign in — do not change Client ID here."
        )
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


def clear_local_registration(cfg: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    """Remove saved client ID / session (fix wrong tenant or wrong app)."""
    if cfg and not server_managed_m365_setup(cfg):
        if LOCAL_CONFIG_FILE.exists():
            LOCAL_CONFIG_FILE.unlink(missing_ok=True)
    _, session_file, pending_file = _m365_paths(user_id)
    if session_file.exists():
        session_file.unlink(missing_ok=True)
    if pending_file.exists():
        pending_file.unlink(missing_ok=True)
    return m365_status(cfg, user_id=user_id)


def _is_explicit_tenant(tenant: str) -> bool:
    return bool(GUID_RE.match(str(tenant or "").strip()))


def _copilot_extra_scopes(cfg: dict[str, Any]) -> list[str]:
    """Delegated scopes required by Graph Copilot Chat API (admin consent on Azure app)."""
    extra = _m365_cfg(cfg).get("copilot_scopes")
    if isinstance(extra, list) and extra:
        return [str(s).strip() for s in extra if str(s).strip()]
    # Empty/missing config → use Graph-required Copilot scopes (see COPILOT_API_SCOPES).
    return COPILOT_API_SCOPES[:]


def _merge_scope_lists(base: list[str], extra: list[str]) -> list[str]:
    parts = base[:]
    for scope in extra:
        s = str(scope).strip()
        if s and s not in parts:
            parts.append(s)
    if "offline_access" not in parts:
        parts.append("offline_access")
    return parts


def _scope_list(
    cfg: dict[str, Any],
    *,
    for_device_login: bool = False,
    include_copilot_scopes: bool = False,
) -> list[str]:
    raw = _m365_cfg(cfg).get("scopes")
    if isinstance(raw, list) and raw:
        parts = [str(s).strip() for s in raw if str(s).strip()]
    elif for_device_login:
        login_raw = _m365_cfg(cfg).get("login_scopes")
        if isinstance(login_raw, list) and login_raw:
            parts = [str(s).strip() for s in login_raw if str(s).strip()]
        else:
            parts = DEVICE_LOGIN_SCOPES[:]
        if include_copilot_scopes:
            parts = _merge_scope_lists(parts, _copilot_extra_scopes(cfg))
    else:
        login_raw = _m365_cfg(cfg).get("login_scopes")
        if isinstance(login_raw, list) and login_raw:
            parts = [str(s).strip() for s in login_raw if str(s).strip()]
        else:
            parts = DEVICE_LOGIN_SCOPES[:]
        if include_copilot_scopes or bool(_m365_cfg(cfg).get("copilot_scopes_at_refresh", True)):
            parts = _merge_scope_lists(parts, _copilot_extra_scopes(cfg))
    if "offline_access" not in parts:
        parts.append("offline_access")
    return parts


def _scopes(
    cfg: dict[str, Any],
    *,
    for_device_login: bool = False,
    include_copilot_scopes: bool = False,
) -> str:
    return " ".join(
        _scope_list(
            cfg,
            for_device_login=for_device_login,
            include_copilot_scopes=include_copilot_scopes,
        )
    )


def _read_session(user_id: str | None = None) -> dict[str, Any]:
    _, session_file, _ = _m365_paths(user_id)
    if not session_file.exists():
        return {}
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_session(data: dict[str, Any], *, user_id: str | None = None) -> None:
    base, session_file, _ = _m365_paths(user_id)
    base.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _token_expired(sess: dict[str, Any]) -> bool:
    exp = sess.get("expires_at")
    if not exp:
        return True
    try:
        return float(exp) < time.time() + 60
    except (TypeError, ValueError):
        return True


def _save_tokens(
    token_payload: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
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
    _write_session(sess, user_id=user_id)
    return sess


def _fetch_profile(access_token: str) -> dict[str, Any]:
    try:
        r = requests_get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except (requests.RequestException, RuntimeError):
        pass
    return {}


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode a JWT payload without verifying the signature.

    We only need a few non-secret claims (``tid``, ``upn``, ``unique_name``)
    to flag MSA accounts and tenant lookups — Microsoft already validated
    the token on its end. Returns ``{}`` on any decoding failure.
    """
    raw = (token or "").strip()
    if not raw or raw.count(".") < 2:
        return {}
    try:
        payload = raw.split(".", 2)[1]
        # JWT uses base64url and may omit padding.
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        claims = json.loads(decoded)
        return claims if isinstance(claims, dict) else {}
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        return {}


def _tenant_id_from_token(payload: dict[str, Any]) -> str:
    """Pull ``tid`` (tenant id) out of either the id_token or access_token."""
    for key in ("id_token", "access_token"):
        token = str(payload.get(key) or "").strip()
        if not token:
            continue
        claims = _decode_jwt_claims(token)
        tid = str(claims.get("tid") or "").strip()
        if tid:
            return tid
    return ""


def _probe_copilot_license(access_token: str) -> dict[str, Any]:
    """Best-effort probe of /me/licenseDetails for the Microsoft 365 Copilot SKU.

    Returns ``{"checked": bool, "has_license": bool, "skus": [...], "error": str}``
    so callers can surface a sensible UI hint even when the probe fails.
    """
    result: dict[str, Any] = {"checked": False, "has_license": False, "skus": [], "error": ""}
    if not access_token:
        result["error"] = "Missing access token"
        return result
    try:
        r = requests_get(
            "https://graph.microsoft.com/v1.0/me/licenseDetails",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except (requests.RequestException, RuntimeError) as exc:
        result["error"] = f"licenseDetails request failed: {exc}"
        return result
    if r.status_code == 403:
        # MSA accounts hit 403 here — they have no organizational license at all.
        result["checked"] = True
        result["error"] = "licenseDetails returned 403 (no organizational licenses)."
        return result
    if r.status_code != 200:
        result["error"] = f"licenseDetails HTTP {r.status_code}: {r.text[:200]}"
        return result
    try:
        payload = r.json()
    except ValueError as exc:
        result["error"] = f"licenseDetails JSON decode failed: {exc}"
        return result
    items = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        result["checked"] = True
        return result
    result["checked"] = True
    skus: list[str] = []
    has_copilot = False
    for item in items:
        if not isinstance(item, dict):
            continue
        part = str(item.get("skuPartNumber") or "").strip()
        if part:
            skus.append(part)
        if any(part.lower().startswith(p.lower()) for p in COPILOT_SKU_PARTS):
            has_copilot = True
            continue
        plans = item.get("servicePlans") if isinstance(item.get("servicePlans"), list) else []
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            name = str(plan.get("servicePlanName") or "").strip().upper()
            if not name:
                continue
            if name in COPILOT_FREE_PLAN_NAMES:
                continue
            if any(name.startswith(prefix) for prefix in COPILOT_SERVICE_PLAN_PREFIXES):
                provisioning = str(plan.get("provisioningStatus") or "").strip().lower()
                if provisioning in ("", "success", "pendingactivation"):
                    has_copilot = True
                    break
    result["skus"] = skus
    result["has_license"] = has_copilot
    return result


def _persist_entitlement_metadata(
    sess: dict[str, Any],
    token_payload: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Decode tenant id, classify MSA, probe Copilot license, write back to session."""
    access_token = str(sess.get("access_token") or "").strip()
    tid = _tenant_id_from_token(token_payload) or _tenant_id_from_token(sess)
    is_msa = tid == MSA_TENANT_ID if tid else False
    if tid:
        sess["tenant_id_from_token"] = tid
    sess["is_msa"] = bool(is_msa)
    if is_msa:
        # MSA accounts cannot have an organizational Copilot license; skip the
        # probe entirely so we do not spend an HTTP round-trip on a guaranteed 403.
        sess["has_copilot_license"] = False
        sess["copilot_license_checked"] = True
        sess["copilot_license_skus"] = []
        sess["copilot_license_error"] = "MSA account — Copilot Chat API not entitled."
        sess["copilot_license_checked_at"] = _now_iso()
        _write_session(sess, user_id=user_id)
        return sess
    probe = _probe_copilot_license(access_token)
    sess["has_copilot_license"] = bool(probe.get("has_license"))
    sess["copilot_license_checked"] = bool(probe.get("checked"))
    sess["copilot_license_skus"] = probe.get("skus") or []
    sess["copilot_license_error"] = probe.get("error") or ""
    sess["copilot_license_checked_at"] = _now_iso()
    _write_session(sess, user_id=user_id)
    return sess


def _entitlement_note(sess: dict[str, Any]) -> str:
    if sess.get("is_msa"):
        return (
            "Signed in with a personal Microsoft account. "
            "Microsoft 365 Copilot Chat API requires a work/school account "
            "with the Microsoft 365 Copilot add-on license."
        )
    if sess.get("copilot_license_checked") and not sess.get("has_copilot_license"):
        return (
            "Work/school account detected, but no Microsoft 365 Copilot license is assigned. "
            "Ask IT to add the SKU `Microsoft_365_Copilot` (see README.md)."
        )
    if sess.get("copilot_api_probe_ok") is False:
        err = str(sess.get("copilot_api_probe_error") or "").strip()
        return (
            f"Microsoft 365 Copilot API probe failed. {err}".strip()
            + " Click Test Copilot API after sign-in, or contact IT."
        )
    if not sess.get("copilot_license_checked"):
        return (
            "Could not verify Copilot license (licenseDetails probe unavailable). "
            "If Resolve with Copilot keeps failing, see README.md."
        )
    return ""


def _entitlement_check_stale(sess: dict[str, Any], *, max_age_seconds: int = 12 * 3600) -> bool:
    raw = sess.get("copilot_license_checked_at")
    if not raw:
        return True
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    age = (datetime.now(timezone.utc) - when).total_seconds()
    return age > max_age_seconds


def is_copilot_chat_entitled(sess: dict[str, Any] | None = None) -> bool:
    """True only when the signed-in account is a work/school account WITH the Copilot SKU.

    When the probe could not run (e.g. transient Graph error), we assume the
    user is entitled so the provider chain still attempts the call. The typed
    error in m365_copilot.py handles the failure path gracefully.
    """
    sess = sess if sess is not None else _read_session()
    if not sess:
        return False
    if sess.get("is_msa"):
        return False
    if sess.get("copilot_license_checked") and not sess.get("has_copilot_license"):
        return False
    if sess.get("copilot_api_probe_ok") is False:
        return False
    return True


def record_copilot_api_probe(
    cfg: dict[str, Any] | None,
    *,
    ok: bool,
    error: str = "",
    reason: str = "",
    graph_status: int = 0,
    user_id: str | None = None,
) -> None:
    """Persist Graph Copilot conversation probe result into the M365 session."""
    sess = _read_session(user_id)
    sess["copilot_api_probe_ok"] = bool(ok)
    sess["copilot_api_probe_at"] = _now_iso()
    sess["copilot_api_probe_error"] = str(error or "")
    sess["copilot_api_probe_graph_status"] = int(graph_status or 0)
    if not ok:
        if reason == "msa":
            sess["is_msa"] = True
            sess["has_copilot_license"] = False
            sess["copilot_license_checked"] = True
            sess["copilot_license_error"] = error or "MSA account — Copilot Chat API not entitled."
        elif reason in ("no_license", "unknown"):
            if reason == "no_license":
                sess["has_copilot_license"] = False
                sess["copilot_license_checked"] = True
                sess["copilot_license_error"] = error or "Copilot API probe failed — no license."
    _write_session(sess, user_id=user_id)


def get_copilot_conversation_id(*, user_id: str | None = None) -> str:
    return str(_read_session(user_id).get("copilot_conversation_id") or "")


def set_copilot_conversation_id(conversation_id: str, *, user_id: str | None = None) -> None:
    sess = _read_session(user_id)
    sess["copilot_conversation_id"] = str(conversation_id or "")
    sess["copilot_conversation_at"] = _now_iso()
    _write_session(sess, user_id=user_id)


def clear_copilot_conversation_id(*, user_id: str | None = None) -> None:
    sess = _read_session(user_id)
    sess.pop("copilot_conversation_id", None)
    sess.pop("copilot_conversation_at", None)
    _write_session(sess, user_id=user_id)


def refresh_access_token(cfg: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    sess = _read_session(user_id)
    refresh = str(sess.get("refresh_token") or "").strip()
    if not refresh:
        raise PermissionError("M365 session expired. Sign in again.")
    tenant = _tenant_id(cfg)
    scope = str(sess.get("scope_used") or "").strip()
    if not scope:
        scope = _scopes(cfg, include_copilot_scopes=bool(sess.get("copilot_scopes_granted")))
    data = {
        ** _oauth_client_fields(cfg),
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "scope": scope,
    }
    r = requests_post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=data,
        timeout=30,
    )
    if r.status_code != 200:
        raise PermissionError(f"M365 token refresh failed: {r.text[:300]}")
    payload = r.json()
    sess = _save_tokens(payload, existing=sess, user_id=user_id)
    if not sess.get("display_name"):
        prof = _fetch_profile(str(sess.get("access_token") or ""))
        sess["display_name"] = prof.get("displayName") or prof.get("userPrincipalName") or "M365 user"
        sess["user_principal"] = prof.get("userPrincipalName", "")
        _write_session(sess, user_id=user_id)
    # Re-classify entitlements if we never managed to before; subsequent
    # refreshes inside the same day reuse cached values to avoid extra Graph
    # calls.
    if not sess.get("copilot_license_checked") or _entitlement_check_stale(sess):
        sess = _persist_entitlement_metadata(sess, payload, user_id=user_id)
    return sess


def get_valid_access_token(cfg: dict[str, Any], *, user_id: str | None = None) -> str:
    sess = _read_session(user_id)
    if sess.get("mode") != "api" or not sess.get("access_token"):
        raise PermissionError("Sign in to Microsoft 365 Copilot first.")
    if _token_expired(sess):
        sess = refresh_access_token(cfg, user_id=user_id)
    token = str(sess.get("access_token") or "").strip()
    if not token:
        raise PermissionError("M365 access token missing. Sign in again.")
    return token


def _client_secret_valid(cfg: dict[str, Any]) -> bool:
    """True when a non-trivial secret is configured (delegated-only — no Application grant probe)."""
    secret = _client_secret(cfg)
    return len(secret) >= 8


def _device_token_error(cfg: dict[str, Any], raw: str) -> str:
    if "7000218" in raw:
        if client_secret_configured(cfg):
            if _client_secret_valid(cfg):
                return (
                    "Microsoft sign-in completed in the browser, but Azure blocked the token exchange. "
                    "Ask IT to enable **Allow public client flows** (App registration → Authentication), "
                    "then click Sign in again."
                )
            return (
                "M365_CLIENT_SECRET in .env is missing, wrong, or expired. "
                "Ask IT for a new secret Value, update .env, restart ./dev.sh, then Sign in again."
            )
        return (
            "Azure app requires the client secret Value in .env (M365_CLIENT_SECRET), "
            "then restart ./dev.sh. Secret ID alone cannot be used."
        )
    return _friendly_auth_error(raw)


def _device_code_request(tenant: str, client_id: str, scope: str, cfg: dict[str, Any] | None = None) -> requests.Response:
    data: dict[str, str] = {"client_id": client_id, "scope": scope}
    if cfg and client_secret_configured(cfg):
        data.update(_oauth_client_fields(cfg))
    return requests_post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
        data=data,
        timeout=30,
    )


def cancel_device_login(*, user_id: str | None = None) -> None:
    _, _, pending_file = _m365_paths(user_id)
    if pending_file.exists():
        pending_file.unlink(missing_ok=True)


def start_device_login(
    cfg: dict[str, Any],
    *,
    user_id: str | None = None,
    include_copilot_scopes: bool = False,
) -> dict[str, Any]:
    cancel_device_login(user_id=user_id)
    client_id = _client_id(cfg)
    scope = _scopes(cfg, for_device_login=True, include_copilot_scopes=include_copilot_scopes)
    tenant = _tenant_id(cfg)
    try:
        r = _device_code_request(tenant, client_id, scope, cfg)
        if r.status_code != 200 and not _is_explicit_tenant(tenant) and tenant != DEFAULT_TENANT:
            r = _device_code_request(DEFAULT_TENANT, client_id, scope, cfg)
            tenant = DEFAULT_TENANT
    except RuntimeError:
        raise
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Microsoft login network error: {exc}. "
            "Check firewall/proxy or SSL CA (see README Ubuntu SSL section)."
        ) from exc
    if r.status_code != 200:
        try:
            err_body = r.json()
            detail = err_body.get("error_description") or err_body.get("error") or r.text
        except (json.JSONDecodeError, ValueError):
            detail = r.text[:400]
        raise RuntimeError(_friendly_auth_error(str(detail)))
    payload = r.json()
    expires_in = int(payload.get("expires_in") or 900)
    interval = int(payload.get("interval") or 5)
    pending = {
        "device_code": payload.get("device_code"),
        "user_code": payload.get("user_code"),
        "verification_uri": payload.get("verification_uri"),
        "verification_uri_complete": payload.get("verification_uri_complete"),
        "expires_in": expires_in,
        "expires_at": time.time() + expires_in,
        "interval": interval,
        "started_at": _now_iso(),
        "tenant_used": tenant,
        "scope_used": scope,
        "include_copilot_scopes": bool(include_copilot_scopes),
    }
    base, _, pending_file = _m365_paths(user_id)
    try:
        base.mkdir(parents=True, exist_ok=True)
        pending_file.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write M365 login data to {base}. "
            f"Run: chmod -R u+rwX web_data && chown -R $USER web_data. Detail: {exc}"
        ) from exc
    return {
        "ok": True,
        "user_code": pending.get("user_code"),
        "verification_uri": pending.get("verification_uri"),
        "verification_uri_complete": pending.get("verification_uri_complete"),
        "message": payload.get("message"),
        "expires_in": expires_in,
        "interval": interval,
        "include_copilot_scopes": bool(include_copilot_scopes),
    }


def start_copilot_device_login(cfg: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Device login requesting Graph Copilot delegated scopes (after IT admin consent)."""
    return start_device_login(cfg, user_id=user_id, include_copilot_scopes=True)


def poll_device_login(cfg: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    _, _, pending_file = _m365_paths(user_id)
    if not pending_file.exists():
        sess = _read_session(user_id)
        if sess.get("mode") == "api" and sess.get("access_token") and not _token_expired(sess):
            return {"ok": True, "status": "completed", **m365_status(cfg, user_id=user_id)}
        return {"ok": False, "status": "no_pending_login", "error": "Call login/start first."}
    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    expires_at = pending.get("expires_at")
    try:
        if expires_at and float(expires_at) < time.time():
            cancel_device_login(user_id=user_id)
            return {
                "ok": False,
                "status": "failed",
                "error": _friendly_auth_error("expired_token"),
            }
    except (TypeError, ValueError):
        pass
    device_code = pending.get("device_code")
    tenant = str(pending.get("tenant_used") or _tenant_id(cfg) or DEFAULT_TENANT)
    try:
        r = requests_post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                ** _oauth_client_fields(cfg),
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            timeout=30,
        )
    except RuntimeError as exc:
        return {"ok": False, "status": "failed", "error": str(exc)}
    body = r.json() if r.text else {}
    err = body.get("error")
    if err == "authorization_pending":
        remaining = None
        try:
            if expires_at:
                remaining = max(0, int(float(expires_at) - time.time()))
        except (TypeError, ValueError):
            pass
        return {
            "ok": False,
            "status": "pending",
            "message": "Complete sign-in in the browser.",
            "expires_in": remaining,
        }
    if err == "slow_down":
        return {"ok": False, "status": "pending", "interval": int(body.get("interval", 5))}
    if err in ("expired_token", "authorization_declined", "bad_verification_code"):
        cancel_device_login(user_id=user_id)
    if r.status_code != 200:
        raw_err = str(body.get("error_description") or body.get("error") or r.text[:300])
        return {"ok": False, "status": "failed", "error": _device_token_error(cfg, raw_err), "error_raw": raw_err[:500]}
    pending_file.unlink(missing_ok=True)
    sess = _save_tokens(body, user_id=user_id)
    scope_used = str(pending.get("scope_used") or "")
    if scope_used:
        sess["scope_used"] = scope_used
    sess["copilot_scopes_granted"] = bool(pending.get("include_copilot_scopes"))
    if not sess.get("copilot_scopes_granted"):
        sess.pop("copilot_api_probe_ok", None)
        sess.pop("copilot_api_probe_at", None)
        sess.pop("copilot_api_probe_error", None)
    prof = _fetch_profile(str(sess.get("access_token") or ""))
    sess["display_name"] = prof.get("displayName") or prof.get("userPrincipalName") or "M365 user"
    sess["user_principal"] = prof.get("userPrincipalName", "")
    _write_session(sess, user_id=user_id)
    sess = _persist_entitlement_metadata(sess, body, user_id=user_id)
    return {"ok": True, "status": "completed", **m365_status(cfg, user_id=user_id)}


def m365_status(cfg: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    sess = _read_session(user_id)
    mode = str(sess.get("mode") or "")
    api_ready = mode == "api" and bool(sess.get("access_token")) and not _token_expired(sess)
    session_refresh_failed = False
    session_expired = bool(mode == "api" and sess.get("access_token") and _token_expired(sess))
    if session_expired and cfg:
        try:
            refresh_access_token(cfg, user_id=user_id)
            sess = _read_session(user_id)
            api_ready = True
            session_expired = False
        except (PermissionError, requests.RequestException, ValueError, RuntimeError):
            api_ready = False
            session_refresh_failed = True
    configured = client_id_configured(cfg) if cfg else bool(sess.get("access_token"))
    _, _, pending_file = _m365_paths(user_id)
    pending = pending_file.exists()
    local = _read_local_config() if cfg else {}
    resolved_cid = _resolved_client_id(cfg) if cfg else ""
    server_managed = server_managed_m365_setup(cfg) if cfg else False
    resolved_tid = _resolved_tenant_id(cfg) if cfg else DEFAULT_TENANT
    is_msa = bool(sess.get("is_msa"))
    license_checked = bool(sess.get("copilot_license_checked"))
    has_license = bool(sess.get("has_copilot_license"))
    copilot_chat_entitled = api_ready and is_copilot_chat_entitled(sess)
    not_entitled_reason = ""
    if api_ready and not copilot_chat_entitled:
        if is_msa:
            not_entitled_reason = "msa"
        elif license_checked and not has_license:
            not_entitled_reason = "no_copilot_license"
        else:
            not_entitled_reason = "unknown"
    entitlement_note = _entitlement_note(sess) if api_ready else ""
    probe_ok = sess.get("copilot_api_probe_ok")
    probe_at = sess.get("copilot_api_probe_at")
    probe_error = str(sess.get("copilot_api_probe_error") or "")
    copilot_scopes_granted = bool(sess.get("copilot_scopes_granted"))
    return {
        "connected": api_ready,
        "mode": "api" if api_ready else (mode or "none"),
        "connected_at": sess.get("connected_at"),
        "display_name": sess.get("display_name"),
        "user_principal": sess.get("user_principal"),
        "api_ready": api_ready,
        "session_expired": session_expired and not api_ready,
        "session_refresh_failed": session_refresh_failed,
        "client_id_configured": configured,
        "server_managed_setup": server_managed,
        "setup_required": not configured,
        "login_pending": pending,
        "setup_message": SETUP_MESSAGE,
        "tenant_id": resolved_tid,
        "tenant_id_preview": (
            f"{resolved_tid[:8]}…" if _is_explicit_tenant(resolved_tid) and len(resolved_tid) > 8 else resolved_tid
        ),
        "tenant_id_from_token": str(sess.get("tenant_id_from_token") or ""),
        "is_msa": is_msa,
        "msa_tenant_id": MSA_TENANT_ID,
        "has_copilot_license": has_license,
        "copilot_license_checked": license_checked,
        "copilot_license_skus": list(sess.get("copilot_license_skus") or []),
        "copilot_license_error": str(sess.get("copilot_license_error") or ""),
        "copilot_chat_entitled": copilot_chat_entitled,
        "copilot_api_probe_ok": probe_ok,
        "copilot_api_probe_at": probe_at,
        "copilot_api_probe_error": probe_error,
        "copilot_scopes_granted": copilot_scopes_granted,
        "not_entitled_reason": not_entitled_reason,
        "entitlement_note": entitlement_note,
        "client_id_preview": f"{resolved_cid[:8]}…" if len(resolved_cid) > 8 else "",
        "client_secret_configured": client_secret_configured(cfg) if cfg else False,
        "local_client_id": str(local.get("client_id") or ""),
        "local_tenant_id": str(local.get("tenant_id") or DEFAULT_TENANT),
        "has_local_config": bool(local.get("client_id")),
        "device_login_url": "https://login.microsoft.com/device",
        "azure_portal_url": "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/applicationsListBlade",
        "activation_guide_url": "README.md",
        "note": (
            entitlement_note
            or "Signed in to Microsoft 365 Copilot (Graph API)."
            if api_ready
            else SETUP_MESSAGE
            if not configured
            else "Sign in with Microsoft 365 to apply Knowledge workbench via Copilot."
        ),
    }


def probe_microsoft_connectivity() -> dict[str, Any]:
    """Test HTTPS to Microsoft — for Ubuntu SSL / firewall troubleshooting."""
    url = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
    verify = ssl_verify_option()
    meta = ssl_verify_status()
    try:
        r = requests_get(url, timeout=15)
        return {
            "ok": r.status_code == 200,
            "status_code": r.status_code,
            "verify": str(verify),
            "url": url,
            **meta,
        }
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc), "verify": str(verify), "url": url, **meta}


def disconnect(*, user_id: str | None = None) -> dict[str, Any]:
    _, session_file, _ = _m365_paths(user_id)
    if session_file.exists():
        session_file.unlink(missing_ok=True)
    cancel_device_login(user_id=user_id)
    return m365_status(user_id=user_id)


def is_api_ready(cfg: dict[str, Any], *, user_id: str | None = None) -> bool:
    try:
        get_valid_access_token(cfg, user_id=user_id)
        return True
    except (PermissionError, ValueError, requests.RequestException):
        return False


def require_api_token(cfg: dict[str, Any], *, user_id: str | None = None) -> str:
    return get_valid_access_token(cfg, user_id=user_id)
