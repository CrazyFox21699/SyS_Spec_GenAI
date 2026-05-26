"""Copilot error taxonomy for clearer UI and API responses."""

from __future__ import annotations

from typing import Any


def classify_copilot_error(
    *,
    m365_ready: bool = True,
    copilot_entitled: bool = True,
    has_bundle: bool = True,
    has_logic_id: bool = True,
    has_context_pack: bool = True,
    has_plan: bool = True,
    has_candidates: bool = True,
    raw_error: str = "",
    http_status: int | None = None,
) -> dict[str, Any]:
    """Return structured error category for Copilot endpoints."""
    if not m365_ready:
        return {
            "ok": False,
            "error_category": "m365_not_ready",
            "error": "Sign in to Microsoft 365 Copilot first.",
            "user_action": "Open Review tab and complete M365 sign-in.",
        }
    if not copilot_entitled:
        return {
            "ok": False,
            "error_category": "m365_not_entitled",
            "error": "Microsoft 365 Copilot Chat is not available for this account.",
            "user_action": "Contact IT to enable Copilot Chat API for your tenant/user.",
        }
    if not has_bundle:
        return {
            "ok": False,
            "error_category": "no_bundle",
            "error": "No analysis bundle for this job.",
            "user_action": "Run Review specification or Import existing TestSpec.",
        }
    if not has_candidates:
        return {
            "ok": False,
            "error_category": "no_candidates",
            "error": "No test cases in this job.",
            "user_action": "Import a Final TestSpec workbook or add test candidates manually.",
        }
    if not has_logic_id:
        return {
            "ok": False,
            "error_category": "no_logic_group",
            "error": "Select a logic group or import a workbook with Test Function column.",
            "user_action": "Import TestSpec xlsx — synthetic logic groups are created automatically.",
        }
    if not has_context_pack:
        return {
            "ok": False,
            "error_category": "no_context",
            "error": "Build context first.",
            "user_action": "Click Build context, or use Generate code from testcase on Test Code tab.",
        }
    if not has_plan:
        return {
            "ok": False,
            "error_category": "no_plan",
            "error": "Generate or save a plan first.",
            "user_action": "Click Generate plan after Build context completes.",
        }

    lower = (raw_error or "").lower()
    if http_status and http_status >= 500:
        return {
            "ok": False,
            "error_category": "graph_500",
            "error": raw_error or "Microsoft Graph internal server error.",
            "user_action": "Retry later or check M365 connectivity on the server.",
        }
    if "ssl" in lower or "certificate" in lower:
        return {
            "ok": False,
            "error_category": "m365_ssl",
            "error": raw_error,
            "user_action": "Install company root CA and set assist.m365.ssl_verify correctly.",
        }
    if "required scopes" in lower or "missing_scopes" in lower:
        return {
            "ok": False,
            "error_category": "m365_missing_scopes",
            "error": raw_error or "Access token missing Copilot Graph delegated scopes.",
            "user_action": (
                "Sign out of M365, then Sign in again. Ask IT to admin-consent "
                "Sites.Read.All, Mail.Read, People.Read.All, Chat.Read, "
                "ChannelMessage.Read.All, ExternalItem.Read.All, OnlineMeetingTranscript.Read.All."
            ),
        }
    if "conversation" in lower or "copilot" in lower:
        return {
            "ok": False,
            "error_category": "m365_copilot_api",
            "error": raw_error or "Copilot conversation request failed.",
            "user_action": "Verify Copilot entitlement and retry.",
        }
    return {
        "ok": False,
        "error_category": "unknown",
        "error": raw_error or "Copilot request failed.",
        "user_action": "Check server logs and M365 status.",
    }


def enrich_error_response(result: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    if result.get("ok"):
        return result
    if result.get("error_category"):
        return result
    classified = classify_copilot_error(raw_error=str(result.get("error") or ""), **kwargs)
    merged = dict(result)
    merged.update({k: v for k, v in classified.items() if k not in merged or merged.get(k) in (None, "", False)})
    return merged
