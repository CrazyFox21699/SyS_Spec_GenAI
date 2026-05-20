"""Microsoft 365 Copilot Chat API — strict knowledge apply procedure."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from web import m365_auth
from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload

GRAPH = "https://graph.microsoft.com/beta"


def _timezone(cfg: dict[str, Any]) -> str:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    m = assist.get("m365") if isinstance(assist.get("m365"), dict) else {}
    return str(m.get("timezone") or "UTC")


def _create_conversation(access_token: str) -> str:
    r = requests.post(
        f"{GRAPH}/copilot/conversations",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"M365 create conversation failed ({r.status_code}): {r.text[:500]}")
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
    r = requests.post(
        f"{GRAPH}/copilot/conversations/{conversation_id}/chat",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "message": {"text": prompt[:28000]},
            "locationHint": {"timeZone": timezone},
        },
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"M365 Copilot chat failed ({r.status_code}): {r.text[:500]}")
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


def apply_knowledge_via_m365(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    failure_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Single M365 Copilot call with strict JSON procedure."""
    token = m365_auth.require_api_token(cfg)
    brief = build_copilot_brief(bundle, logic_id, engineer_note)
    prompt = _strict_procedure_prompt(brief)
    if failure_context:
        prompt += "\n\nFix these logic_compliance failures:\n"
        prompt += json.dumps(failure_context[:30], ensure_ascii=False)[:6000]
    conv_id = _create_conversation(token)
    reply = _chat(token, conv_id, prompt, timezone=_timezone(cfg))
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
