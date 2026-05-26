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


def run_copilot_chat(cfg: dict[str, Any], prompt: str) -> str:
    """Single-turn M365 Copilot chat; returns assistant text."""
    token = m365_auth.require_api_token(cfg, user_id=_m365_user_id_from_context())
    conv_id = _create_conversation(token)
    return _chat(token, conv_id, prompt[:28000], timezone=_timezone(cfg))


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
    try:
        reply = run_copilot_chat(cfg, f"{prompt}\n\nReturn JSON only.")
    except M365CopilotNotEntitledError as exc:
        return {"ok": False, "error": str(exc), "reason": "not_entitled"}
    except (RuntimeError, PermissionError, ValueError) as exc:
        return {"ok": False, "error": str(exc) or "M365 Copilot request failed"}
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
    reply = run_copilot_chat(cfg, prompt)
    conv_id = ""
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
