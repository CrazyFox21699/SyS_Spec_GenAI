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


class M365Copilot500ConversationObjectError(RuntimeError):
    """Raised when the Copilot chat endpoint returns HTTP 500 whose body is a copilotConversation
    object instead of an assistant reply.

    The client must retry with a fresh conversation — reusing the same conversation_id
    repeats the failure.
    """

    def __init__(self, *, conversation_id: str, display_name: str, body_preview: str) -> None:
        self.conversation_id = conversation_id
        self.display_name = display_name
        self.body_preview = body_preview
        super().__init__(
            f"M365 Copilot chat 500: API returned conversation object instead of reply "
            f"(id={conversation_id!r}, displayName={display_name[:80]!r})"
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


def _chat_timeout(cfg: dict[str, Any]) -> int:
    """Return the Copilot chat request timeout in seconds.

    Default 90 s — Copilot code-generation requests regularly take 45-90+ seconds.
    Configurable via assist.m365.chat_timeout in config.yaml.
    """
    try:
        assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
        m = assist.get("m365") if isinstance(assist.get("m365"), dict) else {}
        v = m.get("chat_timeout")
        if v is not None:
            n = int(v)
            return max(30, min(n, 300))   # clamp 30-300 s
    except (TypeError, ValueError):
        pass
    return 90   # was 35 — increased; 35 s is too short for code generation


_CREATE_PAYLOAD: dict[str, Any] = {}  # Graph Copilot API does not accept displayName on creation


def _create_conversation(access_token: str) -> tuple[str, int, str, list[str]]:
    """Create a new Copilot conversation.

    Returns (conversation_id, http_status_code, server_display_name, create_payload_keys).
    Graph auto-assigns displayName — the client must not send it (400 badRequest).
    """
    r = requests_post(
        f"{GRAPH}/copilot/conversations",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=_CREATE_PAYLOAD,
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
    server_dn = str(data.get("displayName") or "")
    return cid, r.status_code, server_dn, list(_CREATE_PAYLOAD.keys())


def _msg_text(m: dict[str, Any]) -> str:
    """Extract the best available text from a Graph message object.

    Tries: text → body.content (HTML stripped) → content → message.text.
    """
    text = str(m.get("text") or "").strip()
    if text and not text.startswith("{"):
        return text
    body = m.get("body")
    if isinstance(body, dict):
        content = str(body.get("content") or "").strip()
        if content and not content.startswith("{"):
            return re.sub(r"<[^>]+>", "", content).strip()
    content = str(m.get("content") or "").strip()
    if content and not content.startswith("{"):
        return content
    nested = m.get("message")
    if isinstance(nested, dict):
        t = str(nested.get("text") or "").strip()
        if t and not t.startswith("{"):
            return t
    return ""


def _msg_role(m: dict[str, Any]) -> str:
    """Extract a normalized role string from a Graph message object."""
    role = str(m.get("role") or "").strip().lower()
    if role:
        return role
    frm = m.get("from")
    if isinstance(frm, dict):
        if any(k in frm for k in ("bot", "application", "copilot")):
            return "assistant"
        if "user" in frm:
            return "user"
        frm_role = str(frm.get("role") or "").strip().lower()
        if frm_role:
            return frm_role
    sender = m.get("sender")
    if isinstance(sender, dict):
        s_role = str(sender.get("role") or "").strip().lower()
        if s_role:
            return s_role
    return ""


def _extract_assistant_text(
    response_json: dict[str, Any],
    prompt: str = "",
) -> tuple[str, dict[str, Any]]:
    """Extract the assistant reply from the Graph chat response.

    Returns (reply_text, extraction_diagnostics).

    Selection priority:
      1. Messages whose @odata.type contains 'ResponseMessage'
      2. Messages whose role/from indicates assistant/copilot/bot
      3. All messages (fallback)

    In all cases the last matching message is preferred over the first, and any
    candidate whose text starts with the same prefix as the submitted prompt is
    rejected to prevent returning the user message as the assistant reply.

    Returns ("", diag) when all candidates are rejected (prompt echo).
    """
    prompt_prefix = prompt[:100].strip()
    msgs = [m for m in (response_json.get("messages") or []) if isinstance(m, dict)]

    # Debug snapshot of first 5 messages
    messages_debug: list[dict[str, Any]] = []
    message_type_list: list[str] = []
    for i, m in enumerate(msgs):
        otype = str(m.get("@odata.type") or "")
        message_type_list.append(otype)
        if i < 5:
            body = m.get("body") or {}
            messages_debug.append({
                "index": i,
                "@odata.type": otype,
                "role": _msg_role(m),
                "text_preview": _msg_text(m)[:120],
                "body_content_preview": str(
                    body.get("content") if isinstance(body, dict) else ""
                )[:120],
                "keys": list(m.keys())[:15],
            })

    indexed_msgs = list(enumerate(msgs))
    response_indexed = [
        (i, m) for i, m in indexed_msgs
        if "ResponseMessage" in str(m.get("@odata.type") or "")
    ]
    assistant_indexed = [
        (i, m) for i, m in indexed_msgs
        if _msg_role(m) in ("assistant", "copilot", "bot")
    ]

    if response_indexed:
        candidates_indexed = response_indexed
        candidates_from = "ResponseMessage"
    elif assistant_indexed:
        candidates_indexed = assistant_indexed
        candidates_from = "assistant_role"
    else:
        candidates_indexed = indexed_msgs
        candidates_from = "fallback_all"

    rejected_count = 0
    chosen_idx: int | None = None
    chosen_type = ""
    chosen_text = ""

    # Prefer last matching message — assistant replies tend to come after user messages
    for orig_idx, m in reversed(candidates_indexed):
        text = _msg_text(m)
        if not text:
            continue
        if prompt_prefix and text.strip()[:len(prompt_prefix)] == prompt_prefix:
            rejected_count += 1
            continue
        chosen_text = text
        chosen_idx = orig_idx
        chosen_type = str(m.get("@odata.type") or "")
        break

    extraction_diag: dict[str, Any] = {
        "message_count": len(msgs),
        "message_type_list": message_type_list,
        "messages_debug": messages_debug,
        "extracted_message_index": chosen_idx,
        "extracted_message_type": chosen_type,
        "extracted_text_startswith": chosen_text[:80] if chosen_text else "",
        "rejected_prompt_echo_count": rejected_count,
        "candidates_from": candidates_from,
    }
    return chosen_text.strip(), extraction_diag


def _chat(
    access_token: str,
    conversation_id: str,
    prompt: str,
    *,
    timezone: str,
    timeout: int = 90,
) -> tuple[str, dict[str, Any]]:
    """Send one turn to the Copilot chat endpoint.

    Returns (assistant_reply_text, diagnostics_dict).
    Raises M365Copilot500ConversationObjectError when Graph returns HTTP 500
    whose body is a copilotConversation object — the prompt must NOT be retried
    on the same conversation_id.
    """
    payload = {
        "message": {"text": prompt[:28000]},
        "locationHint": {"timeZone": timezone},
    }
    r = requests_post(
        f"{GRAPH}/copilot/conversations/{conversation_id}/chat",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    body_text = r.text or ""
    chat_diag: dict[str, Any] = {
        "chat_status": r.status_code,
        "payload_keys": list(payload.keys()),
        "response_body_preview": body_text[:300],
    }

    if r.status_code == 500:
        # Detect the conversation-object 500: body is a copilotConversation dict
        # (Graph stored the prompt as displayName and then failed internally).
        try:
            bj = json.loads(body_text)
            if isinstance(bj, dict) and (
                "displayName" in bj
                or "copilotConversation" in str(bj.get("@odata.type") or "")
                or bj.get("state") is not None
            ):
                raise M365Copilot500ConversationObjectError(
                    conversation_id=str(bj.get("id") or conversation_id),
                    display_name=str(bj.get("displayName") or ""),
                    body_preview=body_text[:500],
                )
        except (json.JSONDecodeError, KeyError):
            pass

    if r.status_code != 200:
        if _classify_missing_scopes(r.status_code, body_text):
            raise M365CopilotMissingScopesError(status_code=r.status_code, raw_body=body_text[:500])
        reason = _classify_not_entitled(r.status_code, body_text)
        if reason:
            raise M365CopilotNotEntitledError(
                status_code=r.status_code, raw_body=body_text[:500], reason=reason
            )
        raise RuntimeError(f"M365 Copilot chat failed ({r.status_code}): {body_text[:500]}")

    body_json = r.json()
    chat_diag["response_body_keys"] = list(body_json.keys())[:10] if isinstance(body_json, dict) else []
    reply, extraction_diag = _extract_assistant_text(body_json, prompt=prompt)
    chat_diag.update(extraction_diag)
    if not reply and extraction_diag.get("rejected_prompt_echo_count", 0) > 0:
        chat_diag["api_result_class"] = "API_RESPONSE_EXTRACTION_FAILED"
    return reply, chat_diag


def _is_graph_unauthorized(exc: Exception) -> bool:
    text = str(exc).lower()
    return "(401)" in text or "invalidauthenticationtoken" in text or "not authenticated" in text


def _user_id_candidates(user_id: str | None) -> list[str | None]:
    uid = str(user_id or "").strip() or None
    if uid:
        return [uid, None]
    return [None]


def _run_chat_once(
    cfg: dict[str, Any],
    prompt: str,
    *,
    uid: str | None,
    conversation_id: str | None,
    reuse_session_conversation: bool,
    persist_conversation: bool,
) -> dict[str, Any]:
    token = m365_auth.require_api_token(cfg, user_id=uid)
    conv_id = str(conversation_id or "").strip()
    create_status: int | None = None
    server_display_name = ""
    create_payload_keys: list[str] = []
    if not conv_id and reuse_session_conversation:
        conv_id = m365_auth.get_copilot_conversation_id(user_id=uid)
    if conv_id:
        created = False
    else:
        conv_id, create_status, server_display_name, create_payload_keys = _create_conversation(token)
        created = True
    reply, chat_diag = _chat(token, conv_id, prompt[:28000], timezone=_timezone(cfg), timeout=_chat_timeout(cfg))
    if persist_conversation and conv_id:
        m365_auth.set_copilot_conversation_id(conv_id, user_id=uid)
    return {
        "ok": True,
        "reply": reply,
        "conversation_id": conv_id,
        "conversation_created": created,
        "chat_ok": bool(reply.strip()),
        # API call diagnostics
        "create_status": create_status,
        "create_payload_keys": create_payload_keys,
        "server_displayName": server_display_name,
        "reuse_session_conversation": reuse_session_conversation,
        "persist_conversation": persist_conversation,
        **chat_diag,
    }


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
    if isinstance(exc, M365Copilot500ConversationObjectError):
        return {
            "ok": False,
            "error": str(exc),
            "error_category": "api_chat_500_conversation_object",
            "conversation_id": exc.conversation_id,
            "server_displayName": exc.display_name,
            "raw_preview": exc.body_preview[:500],
            "retried_with_fresh_conversation": False,
            "user_action": (
                "Copilot API returned a conversation object instead of a reply. "
                "Retry generation. If it fails again, use Copy Copilot Web Prompt."
            ),
        }
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
    text = str(exc) or ""
    lower_text = text.lower()
    if "m365" in lower_text and "(401)" in lower_text:
        return {
            "ok": False,
            "error": text,
            "error_category": "m365_not_ready",
            "graph_status": 401,
            "user_action": "Sign out of M365 on the Review tab, sign in again, then Authorize/Test Copilot API.",
        }
    if "m365" in lower_text and "(403)" in lower_text:
        return {
            "ok": False,
            "error": text,
            "error_category": "m365_missing_scopes",
            "graph_status": 403,
            "user_action": "Authorize Copilot API again. If it still fails, ask IT to admin-consent the required Graph scopes.",
        }
    if isinstance(exc, requests.RequestException):
        msg = str(exc) or "Microsoft Graph network error."
        lower = msg.lower()
        if "read timed out" in lower or "read timeout" in lower or "timed out" in lower:
            category = "m365_graph_timeout"
        elif "ssl" in lower or "certificate" in lower:
            category = "m365_ssl"
        else:
            category = "graph_network"
        return {
            "ok": False,
            "error": msg,
            "error_category": category,
            "user_action": (
                "Check server SSL settings (assist.m365.ssl_verify) and company CA, then retry."
                if category == "m365_ssl"
                else (
                    "Microsoft Graph Copilot did not return before timeout. Use Copy Copilot Web Prompt for this testcase, or retry when Graph is responsive."
                    if category == "m365_graph_timeout"
                    else "Retry later or check M365 connectivity on the server."
                )
            ),
        }
    msg = str(exc) or "M365 Copilot request failed."
    lower = msg.lower()
    if "read timed out" in lower or "read timeout" in lower or "timed out" in lower:
        category = "m365_graph_timeout"
    elif "conversation" in lower or "copilot" in lower:
        category = "m365_copilot_api"
    elif "graph.microsoft.com" in lower:
        category = "graph_network"
    else:
        category = "unknown"
    return {
        "ok": False,
        "error": msg,
        "error_category": category,
        "user_action": (
            "Microsoft Graph Copilot timed out. Use Copy Copilot Web Prompt for this testcase, or retry when Graph is responsive."
            if category == "m365_graph_timeout"
            else "Use Test Copilot API on Review tab to diagnose, then retry."
        ),
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
    requested_uid = user_id or _m365_user_id_from_context()
    last_exc: Exception | None = None
    try:
        for uid in _user_id_candidates(requested_uid):
            try:
                return _run_chat_once(
                    cfg,
                    prompt,
                    uid=uid,
                    conversation_id=conversation_id,
                    reuse_session_conversation=reuse_session_conversation,
                    persist_conversation=persist_conversation,
                )
            except M365Copilot500ConversationObjectError as exc:
                # Graph returned a conversation object instead of an assistant reply.
                # The same conversation_id cannot be reused — retry once with fresh state.
                try:
                    result = _run_chat_once(
                        cfg,
                        prompt,
                        uid=uid,
                        conversation_id=None,
                        reuse_session_conversation=False,
                        persist_conversation=False,
                    )
                    result["retried_with_fresh_conversation"] = True
                    result["original_500_conversation_id"] = exc.conversation_id
                    result["original_500_display_name"] = exc.display_name
                    return result
                except Exception as retry_exc:  # noqa: BLE001
                    last_exc = retry_exc
                    if uid is not None:
                        continue
                    raise
            except PermissionError as exc:
                last_exc = exc
                if uid is not None:
                    continue
                raise
            except Exception as exc:
                if isinstance(exc, (M365CopilotNotEntitledError, M365CopilotMissingScopesError)):
                    raise
                if _is_graph_unauthorized(exc):
                    last_exc = exc
                    if reuse_session_conversation:
                        m365_auth.clear_copilot_conversation_id(user_id=uid)
                    try:
                        m365_auth.refresh_access_token(cfg, user_id=uid)
                        return _run_chat_once(
                            cfg,
                            prompt,
                            uid=uid,
                            conversation_id=None,
                            reuse_session_conversation=False,
                            persist_conversation=persist_conversation,
                        )
                    except Exception as retry_exc:  # noqa: BLE001
                        last_exc = retry_exc
                        if uid is not None:
                            continue
                        raise
                raise
        if last_exc:
            raise last_exc
        raise PermissionError("Sign in to Microsoft 365 Copilot first.")
    except Exception as exc:
        if isinstance(exc, (M365CopilotNotEntitledError, M365CopilotMissingScopesError)):
            if reuse_session_conversation:
                m365_auth.clear_copilot_conversation_id(user_id=requested_uid)
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
            error_category=str(result.get("error_category") or ""),
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
