"""Microsoft 365 Copilot Chat API — strict knowledge apply procedure."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from web import m365_auth
from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload

requests_post = m365_auth.requests_post

GRAPH = "https://graph.microsoft.com/beta"


def _m365_user_id_from_context() -> str | None:
    return m365_auth.session_user_id()

# Substrings the Microsoft Graph error message uses when the signed-in
# account cannot reach the Microsoft.CopilotChat service plan. Matched
# case-insensitively so we catch both English variants.
_NOT_ENTITLED_HINTS = (
    "not supported for msa accounts",
    "no addressurl for microsoft.copilotchat",
    "copilotchat is not available",
    "license is required",
    "tenant is not licensed",
    "user does not have a m365 copilot",
    "user is not licensed for copilot",
)

_MISSING_SCOPE_HINTS = (
    "required scopes",
    "insufficient privileges",
    "insufficient scope",
    "authorization_requestdenied",
)


class M365CopilotMissingScopesError(RuntimeError):
    """Raised when the access token lacks delegated scopes required by Copilot Chat API."""

    def __init__(self, *, status_code: int, raw_body: str, message: str = "") -> None:
        self.status_code = status_code
        self.raw_body = raw_body
        msg = message or (
            "Microsoft 365 Copilot API requires additional Graph delegated permissions. "
            "Sign out, then Sign in again. If the error persists, ask IT to admin-consent "
            "Sites.Read.All, Mail.Read, People.Read.All, Chat.Read, ChannelMessage.Read.All, "
            "ExternalItem.Read.All, and OnlineMeetingTranscript.Read.All on the Azure app."
        )
        super().__init__(msg)


def _classify_missing_scopes(status_code: int, body_text: str) -> bool:
    lower = (body_text or "").lower()
    if status_code in (401, 403) and any(hint in lower for hint in _MISSING_SCOPE_HINTS):
        return True
    return "required scopes" in lower


class M365CopilotNotEntitledError(RuntimeError):
    """Raised when the M365 Copilot Chat Graph API rejects the caller because of MSA / no Copilot license.

    Carries the raw Graph status + body so callers can surface a precise UI
    hint, and a stable ``reason`` discriminator (``"msa"`` / ``"no_license"``
    / ``"unknown"``).
    """

    def __init__(self, *, status_code: int, raw_body: str, reason: str, message: str = "") -> None:
        self.status_code = status_code
        self.raw_body = raw_body
        self.reason = reason
        msg = message or _default_not_entitled_message(reason)
        super().__init__(msg)


def _default_not_entitled_message(reason: str) -> str:
    if reason == "msa":
        return (
            "Microsoft 365 Copilot Chat API is not available for personal Microsoft accounts. "
            "Sign in with a work/school account that has the Microsoft 365 Copilot license "
            "(see README.md)."
        )
    if reason == "no_license":
        return (
            "This work/school account does not have a Microsoft 365 Copilot license assigned. "
            "Ask IT to add the SKU `Microsoft_365_Copilot` "
            "(see README.md)."
        )
    return (
        "Microsoft 365 Copilot Chat API rejected the request. "
        "See README.md for the activation steps."
    )


def _classify_not_entitled(status_code: int, body_text: str) -> str | None:
    """Return ``"msa"`` / ``"no_license"`` / ``"unknown"`` when the response is a Copilot entitlement failure, else None."""
    lower = (body_text or "").lower()
    matched = any(hint in lower for hint in _NOT_ENTITLED_HINTS)
    if status_code == 400 and matched:
        if "msa account" in lower:
            return "msa"
        if "no addressurl for microsoft.copilotchat" in lower:
            # This message also fires for MSA accounts; treat as MSA unless a
            # license hint appears explicitly.
            if "license" in lower:
                return "no_license"
            return "msa"
        return "unknown"
    if status_code in (401, 402, 403) and (
        "copilot" in lower or "license" in lower or "subscription" in lower
    ):
        return "no_license"
    if status_code == 404 and "copilot" in lower:
        return "no_license"
    return None


def _timezone(cfg: dict[str, Any]) -> str:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    m = assist.get("m365") if isinstance(assist.get("m365"), dict) else {}
    return str(m.get("timezone") or "UTC")


def _create_conversation(access_token: str) -> str:
    r = requests_post(
        f"{GRAPH}/copilot/conversations",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        body = r.text or ""
        if _classify_missing_scopes(r.status_code, body):
            raise M365CopilotMissingScopesError(status_code=r.status_code, raw_body=body[:500])
        reason = _classify_not_entitled(r.status_code, body)
        if reason:
            raise M365CopilotNotEntitledError(
                status_code=r.status_code, raw_body=body[:500], reason=reason
            )
        raise RuntimeError(f"M365 create conversation failed ({r.status_code}): {body[:500]}")
    data = r.json()
    cid = str(data.get("id") or "")
    if not cid:
        raise RuntimeError("M365 conversation id missing in response.")
    return cid


def _extract_assistant_text(response_json: dict[str, Any]) -> str:
    chunks: list[str] = []
    for msg in response_json.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        otype = str(msg.get("@odata.type") or "")
        if "ResponseMessage" in otype or msg.get("text"):
            text = str(msg.get("text") or "").strip()
            if text and not text.startswith("{"):
                chunks.append(text)
    return "\n".join(chunks).strip()


def _chat(access_token: str, conversation_id: str, prompt: str, *, timezone: str) -> str:
    r = requests_post(
        f"{GRAPH}/copilot/conversations/{conversation_id}/chat",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "message": {"text": prompt[:28000]},
            "locationHint": {"timeZone": timezone},
        },
        timeout=180,
    )
    if r.status_code != 200:
        body = r.text or ""
        if _classify_missing_scopes(r.status_code, body):
            raise M365CopilotMissingScopesError(status_code=r.status_code, raw_body=body[:500])
        reason = _classify_not_entitled(r.status_code, body)
        if reason:
            raise M365CopilotNotEntitledError(
                status_code=r.status_code, raw_body=body[:500], reason=reason
            )
        raise RuntimeError(f"M365 Copilot chat failed ({r.status_code}): {body[:500]}")
    return _extract_assistant_text(r.json())


def _strict_procedure_prompt(brief: str) -> str:
    return (
        "You are Microsoft 365 Copilot assisting an automotive test-spec tool (ALEX).\n"
        "Follow this procedure strictly:\n"
        "1. Read engineer knowledge and each existing test case in the brief.\n"
        "2. For every candidate_id listed, output concrete Given signal=value rows "
        "(one value per signal). Use boundary values for ranges (e.g. 100-200 km/h: "
        "101 in-range, 200 at max, 201 above max) matching each path pass/fail intent.\n"
        "3. For missing definition terms mentioned in engineer knowledge, add definition_updates.\n"
        "4. Do not invent new candidate_id values unless engineer note explicitly asks for new tests.\n"
        "5. Return JSON only (no markdown outside the JSON block):\n"
        '{"candidates":[{"candidate_id":"...","given":[{"signal":"SIG","value":"v"}],"note":"..."}],'
        '"definition_updates":[{"name":"TERM","definition":"plain or =value"}]}\n\n'
        f"{brief[:24000]}"
    )


def _parse_copilot_response(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    patches = parse_knowledge_patches_payload(text)
    definition_updates: list[dict[str, Any]] = []
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                if not patches and isinstance(parsed.get("candidates"), list):
                    patches = parsed["candidates"]
                du = parsed.get("definition_updates")
                if isinstance(du, list):
                    definition_updates = [d for d in du if isinstance(d, dict)]
        except json.JSONDecodeError:
            pass
    return patches, definition_updates


def strict_knowledge_procedure_prompt(brief: str) -> str:
    return _strict_procedure_prompt(brief)


def parse_knowledge_response(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _parse_copilot_response(text)


def _copilot_error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, M365CopilotMissingScopesError):
        return {
            "ok": False,
            "error": str(exc),
            "error_category": "m365_missing_scopes",
            "graph_status": exc.status_code,
            "raw_preview": (exc.raw_body or "")[:500],
            "user_action": (
                "Sign out of M365, then Sign in again to request Copilot Graph scopes. "
                "If it still fails, ask IT to admin-consent delegated permissions on the Azure app."
            ),
        }
    if isinstance(exc, M365CopilotNotEntitledError):
        return {
            "ok": False,
            "error": str(exc),
            "error_category": "m365_not_entitled",
            "not_entitled_reason": exc.reason,
            "graph_status": exc.status_code,
            "raw_preview": (exc.raw_body or "")[:500],
            "user_action": (
                "Sign in with a work/school account that has Microsoft 365 Copilot, "
                "or contact IT to assign SKU Microsoft_365_Copilot."
            ),
        }
    if isinstance(exc, PermissionError):
        return {
            "ok": False,
            "error": str(exc) or "M365 sign-in required.",
            "error_category": "m365_not_ready",
            "user_action": "Open Review tab and complete Microsoft 365 sign-in.",
        }
    if isinstance(exc, requests.RequestException):
        msg = str(exc) or "Microsoft Graph network error."
        lower = msg.lower()
        category = "m365_ssl" if "ssl" in lower or "certificate" in lower else "graph_500"
        return {
            "ok": False,
            "error": msg,
            "error_category": category,
            "user_action": (
                "Check server SSL settings (assist.m365.ssl_verify) and company CA, then retry."
                if category == "m365_ssl"
                else "Retry later or check M365 connectivity on the server."
            ),
        }
    msg = str(exc) or "M365 Copilot request failed."
    lower = msg.lower()
    category = "m365_copilot_api" if "conversation" in lower or "copilot" in lower else "unknown"
    return {
        "ok": False,
        "error": msg,
        "error_category": category,
        "user_action": "Use Test Copilot API on Review tab to diagnose, then retry.",
    }


def run_copilot_chat_result(
    cfg: dict[str, Any],
    prompt: str,
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
    reuse_session_conversation: bool = False,
    persist_conversation: bool = True,
) -> dict[str, Any]:
    """Single-turn M365 Copilot chat; returns structured result (never raises)."""
    uid = user_id or _m365_user_id_from_context()
    try:
        token = m365_auth.require_api_token(cfg, user_id=uid)
        conv_id = str(conversation_id or "").strip()
        if not conv_id and reuse_session_conversation:
            conv_id = m365_auth.get_copilot_conversation_id(user_id=uid)
        if conv_id:
            created = False
        else:
            conv_id = _create_conversation(token)
            created = True
        reply = _chat(token, conv_id, prompt[:28000], timezone=_timezone(cfg))
        if persist_conversation and conv_id:
            m365_auth.set_copilot_conversation_id(conv_id, user_id=uid)
        return {
            "ok": True,
            "reply": reply,
            "conversation_id": conv_id,
            "conversation_created": created,
            "chat_ok": bool(reply.strip()),
        }
    except Exception as exc:
        if isinstance(exc, (M365CopilotNotEntitledError, M365CopilotMissingScopesError)):
            if reuse_session_conversation:
                m365_auth.clear_copilot_conversation_id(user_id=uid)
        return _copilot_error_payload(exc)


def probe_copilot_api(cfg: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Create a Graph conversation and send a short ping — verifies Copilot API entitlement."""
    result = run_copilot_chat_result(
        cfg,
        "You are ALEX connectivity probe. Reply with exactly: ALEX probe OK",
        user_id=user_id,
        persist_conversation=False,
    )
    if not result.get("ok"):
        m365_auth.record_copilot_api_probe(
            cfg,
            ok=False,
            error=str(result.get("error") or ""),
            reason=str(result.get("not_entitled_reason") or ""),
            graph_status=int(result.get("graph_status") or 0),
            user_id=user_id,
        )
        return {
            "ok": False,
            "conversation_created": False,
            "chat_ok": False,
            "entitlement_hint": str(result.get("error") or ""),
            "error_category": result.get("error_category"),
            "not_entitled_reason": result.get("not_entitled_reason"),
            "graph_status": result.get("graph_status"),
            "raw_preview": result.get("raw_preview"),
            "user_action": result.get("user_action"),
        }
    reply = str(result.get("reply") or "")
    chat_ok = bool(reply.strip())
    m365_auth.record_copilot_api_probe(cfg, ok=chat_ok, user_id=user_id)
    return {
        "ok": chat_ok,
        "conversation_created": True,
        "chat_ok": chat_ok,
        "reply_preview": reply[:200],
        "entitlement_hint": "" if chat_ok else "Copilot replied but response was empty.",
        "conversation_id": result.get("conversation_id"),
    }


def run_copilot_chat(cfg: dict[str, Any], prompt: str) -> str:
    """Single-turn M365 Copilot chat; returns assistant text (raises on failure)."""
    result = run_copilot_chat_result(cfg, prompt)
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or "M365 Copilot request failed"))
    return str(result.get("reply") or "")


def _parse_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def improve_io_via_m365(cfg: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Improve Expected I/O fields via M365 Copilot (JSON response)."""
    chat = run_copilot_chat_result(cfg, f"{prompt}\n\nReturn JSON only.")
    if not chat.get("ok"):
        out = dict(chat)
        out["reason"] = "not_entitled" if chat.get("error_category") == "m365_not_entitled" else "api_error"
        return out
    reply = str(chat.get("reply") or "")
    result = _parse_json_object(reply)
    if result:
        return {"ok": True, "result": result, "provider": "m365"}
    return {"ok": False, "error": "Could not parse JSON from Copilot response.", "raw": reply[:500]}


def translate_text_via_m365(cfg: dict[str, Any], text: str, *, target_language: str = "JP") -> str:
    """Translate spec text via M365 Copilot."""
    target = str(target_language or "JP").upper()
    prompt = (
        f"Translate the following automotive test specification text to {'Japanese' if target == 'JP' else target}.\n"
        "Rules:\n"
        "- Keep signal / variable names in ASCII (e.g. OK_SHUTOFF, VEHICLE_STOPPED).\n"
        "- Keep line-oriented structure (Given:, Then:, Precondition: prefixes where present).\n"
        "- Return translated text only — no markdown or commentary.\n\n"
        f"{text[:12000]}"
    )
    return run_copilot_chat(cfg, prompt)


def apply_knowledge_via_m365(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    failure_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Single M365 Copilot call with strict JSON procedure."""
    brief = build_copilot_brief(bundle, logic_id, engineer_note)
    prompt = _strict_procedure_prompt(brief)
    if failure_context:
        prompt += "\n\nFix these logic_compliance failures:\n"
        prompt += json.dumps(failure_context[:30], ensure_ascii=False)[:6000]
    chat = run_copilot_chat_result(cfg, prompt)
    if not chat.get("ok"):
        return chat
    reply = str(chat.get("reply") or "")
    conv_id = str(chat.get("conversation_id") or "")
    patches, definition_updates = _parse_copilot_response(reply)
    if definition_updates:
        eng = bundle.setdefault("ai_assists", {}).setdefault("engineer_definitions", {})
        for row in definition_updates:
            nm = str(row.get("name") or "").strip()
            df = str(row.get("definition") or "").strip()
            if nm and df:
                eng[nm] = {
                    "name": nm,
                    "definition": df,
                    "logic_id": logic_id,
                    "source": "m365_copilot",
                }
    return {
        "ok": True,
        "patches": patches,
        "definition_updates": definition_updates,
        "conversation_id": conv_id,
        "reply_preview": reply[:500],
    }
