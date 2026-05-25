"""Local GitHub Copilot CLI bridge for the web app.

This module keeps the deterministic parser as source of truth and only sends
small audited context packs to Copilot to reduce token usage and improve
traceability.
"""

from __future__ import annotations

import json
import os
import pty
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_COPILOT_PATH = "copilot"
_CODE_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")
_URL_RE = re.compile(r"https://github\.com/login/device")
_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_MAX_TABLE_ROWS = 18
_MAX_ISSUES = 10
_MAX_CANDIDATES = 8
_MAX_TEXT = 700


@dataclass
class CopilotCommandState:
    command_id: str
    kind: str
    status: str = "waiting"
    log: list[str] = field(default_factory=list)
    error_message: str | None = None
    verify_url: str | None = None
    one_time_code: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    current_logic_id: str | None = None
    progress_current: int = 0
    progress_total: int = 0


_commands: dict[str, CopilotCommandState] = {}
_commands_lock = threading.Lock()
_last_verify: dict[str, Any] | None = None
_last_login: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_last_verify(payload: dict[str, Any]) -> None:
    global _last_verify
    _last_verify = payload


def _set_last_login(payload: dict[str, Any]) -> None:
    global _last_login
    _last_login = payload


def _append_log(command_id: str, line: str) -> None:
    line = str(line).rstrip()
    if not line:
        return
    with _commands_lock:
        st = _commands.get(command_id)
        if not st:
            return
        st.log.append(line)
        if len(st.log) > 200:
            st.log = st.log[-200:]
        if not st.one_time_code:
            m = _CODE_RE.search(line)
            if m:
                st.one_time_code = m.group(1)
        if not st.verify_url and _URL_RE.search(line):
            st.verify_url = "https://github.com/login/device"


def _update_command(command_id: str, **kwargs: Any) -> None:
    with _commands_lock:
        st = _commands.get(command_id)
        if not st:
            return
        for k, v in kwargs.items():
            setattr(st, k, v)


def get_command(command_id: str) -> CopilotCommandState | None:
    with _commands_lock:
        return _commands.get(command_id)


def _create_command(kind: str) -> CopilotCommandState:
    cmd = CopilotCommandState(command_id=f"copilot_{kind}_{uuid.uuid4().hex[:8]}", kind=kind)
    with _commands_lock:
        _commands[cmd.command_id] = cmd
    return cmd


def _command_dict(st: CopilotCommandState) -> dict[str, Any]:
    return {
        "command_id": st.command_id,
        "kind": st.kind,
        "status": st.status,
        "verify_url": st.verify_url,
        "one_time_code": st.one_time_code,
        "error_message": st.error_message,
        "log": st.log[-80:],
        "started_at": st.started_at,
        "completed_at": st.completed_at,
        "result": st.result,
        "current_logic_id": st.current_logic_id,
        "progress_current": st.progress_current,
        "progress_total": st.progress_total,
    }


def probe_copilot_cli() -> dict[str, Any]:
    """Cheap local probe that avoids spending a Copilot request."""
    path = shutil.which(_COPILOT_PATH)
    gh_path = shutil.which("gh")
    version = None
    install_hint = "npm install -g @github/copilot"
    if path:
        try:
            cp = subprocess.run(
                [_COPILOT_PATH, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            version = (cp.stdout or cp.stderr or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            version = f"unavailable ({exc})"

    gh_status = None
    gh_summary = None
    if gh_path:
        try:
            cp = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            gh_status = cp.returncode == 0
            text = (cp.stdout or cp.stderr or "").strip()
            gh_summary = text.splitlines()[0] if text else None
        except Exception as exc:  # noqa: BLE001
            gh_summary = f"gh auth status unavailable ({exc})"

    env_auth = any(os.environ.get(k) for k in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"))
    config_ok, config_reason = _copilot_config_auth_ok()
    trust_state = "not_verified"
    trust_reason = "Log in with Copilot once, then use Test prompt only if you need a live model reply."
    if _last_verify and _last_verify.get("ok"):
        if _last_verify.get("verification_mode") == "runtime_prompt":
            trust_state = "runtime_verified"
            trust_reason = "A live Copilot prompt succeeded in this app session."
        else:
            trust_state = "auth_verified"
            trust_reason = _last_verify.get("reason") or "GitHub auth is configured for Copilot CLI."
    elif _last_login and _last_login.get("ok"):
        trust_state = "auth_verified"
        trust_reason = "Device login completed in this app session."
    elif config_ok:
        trust_state = "auth_verified"
        trust_reason = config_reason or "Copilot CLI is logged in."
    return {
        "installed": bool(path),
        "path": path,
        "version": version,
        "install_hint": install_hint,
        "gh_installed": bool(gh_path),
        "gh_auth_ok": gh_status,
        "gh_summary": gh_summary,
        "env_auth_present": env_auth,
        "login_state": "configured"
        if env_auth or gh_status or config_ok or (_last_login and _last_login.get("ok"))
        else "unknown",
        "last_verify": _last_verify,
        "last_login": _last_login,
        "trust_state": trust_state,
        "trust_reason": trust_reason,
        "notes": [
            "Copilot CLI login uses GitHub device flow; session is stored in ~/.copilot/config.json.",
            "GitHub CLI (gh) is optional. Auth check does not use Copilot quota.",
        ],
    }


def start_login(cwd: Path) -> CopilotCommandState:
    cmd = _create_command("login")
    path = shutil.which(_COPILOT_PATH)
    if not path:
        _update_command(
            cmd.command_id,
            status="failed",
            error_message="copilot CLI not found. Install with `npm install -g @github/copilot`.",
            completed_at=_now_iso(),
        )
        return get_command(cmd.command_id) or cmd

    def worker() -> None:
        _update_command(cmd.command_id, status="running")
        master_fd = slave_fd = None
        try:
            master_fd, slave_fd = pty.openpty()
            proc = subprocess.Popen(
                [_COPILOT_PATH, "login"],
                cwd=str(cwd),
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                close_fds=True,
            )
            os.close(slave_fd)
            slave_fd = None
            sent_enter = False
            buffer = ""
            while True:
                data = os.read(master_fd, 4096)
                if not data:
                    break
                chunk = data.decode(errors="replace")
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    _append_log(cmd.command_id, line)
                    if ("Press any key" in line or "Waiting for authorization" in line) and not sent_enter:
                        os.write(master_fd, b"\n")
                        sent_enter = True
            if buffer.strip():
                _append_log(cmd.command_id, buffer)
            rc = proc.wait(timeout=5)
            if rc == 0:
                _set_last_login(
                    {
                        "ok": True,
                        "completed_at": _now_iso(),
                        "verification_mode": "device_login",
                    }
                )
                _update_command(cmd.command_id, status="completed", completed_at=_now_iso())
            else:
                _set_last_login(
                    {
                        "ok": False,
                        "completed_at": _now_iso(),
                        "verification_mode": "device_login",
                        "reason": f"`copilot login` exited with code {rc}.",
                    }
                )
                _update_command(
                    cmd.command_id,
                    status="failed",
                    completed_at=_now_iso(),
                    error_message=f"`copilot login` exited with code {rc}.",
                )
        except Exception as exc:  # noqa: BLE001
            _append_log(cmd.command_id, f"ERROR: {exc}")
            _set_last_login(
                {
                    "ok": False,
                    "completed_at": _now_iso(),
                    "verification_mode": "device_login",
                    "reason": str(exc),
                }
            )
            _update_command(
                cmd.command_id,
                status="failed",
                completed_at=_now_iso(),
                error_message=str(exc),
            )
        finally:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass

    threading.Thread(target=worker, daemon=True).start()
    return get_command(cmd.command_id) or cmd


def _load_copilot_config() -> dict[str, Any]:
    path = Path.home() / ".copilot" / "config.json"
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        lines = [line for line in raw.splitlines() if not line.strip().startswith("//")]
        payload = json.loads("\n".join(lines))
        return payload if isinstance(payload, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _copilot_config_auth_ok() -> tuple[bool, str | None]:
    data = _load_copilot_config()
    last_user = data.get("lastLoggedInUser")
    if isinstance(last_user, dict) and last_user.get("login"):
        return True, f"Copilot CLI logged in as {last_user.get('login')}."
    users = data.get("loggedInUsers")
    if isinstance(users, list) and users:
        names = [str(u.get("login") or "") for u in users if isinstance(u, dict) and u.get("login")]
        if names:
            active = names[0]
            return True, f"Copilot CLI account: {active}" + (f" (+{len(names) - 1} more)" if len(names) > 1 else "")
    return False, None


def _auth_probe_ok() -> tuple[bool, str | None]:
    """Check GitHub/Copilot auth without spending a Copilot model request."""
    env_auth = any(os.environ.get(k) for k in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"))
    if env_auth:
        return True, "Environment token is configured."
    if _last_login and _last_login.get("ok"):
        return True, "Device login completed in this app session."
    config_ok, config_reason = _copilot_config_auth_ok()
    if config_ok:
        return True, config_reason
    gh_path = shutil.which("gh")
    if gh_path:
        try:
            cp = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if cp.returncode == 0:
                return True, "GitHub CLI auth is active."
            text = (cp.stderr or cp.stdout or "").strip()
            return False, text.splitlines()[0] if text else "GitHub CLI is not logged in."
        except Exception as exc:  # noqa: BLE001
            return False, f"gh auth status failed: {exc}"
    return (
        False,
        "Copilot is not logged in yet. Use Login Copilot (GitHub device flow). "
        "GitHub CLI (`gh`) is optional — not required after login.",
    )


def verify_copilot_access(cwd: Path, *, deep: bool = False) -> dict[str, Any]:
    path = shutil.which(_COPILOT_PATH)
    if not path:
        payload = {
            "ok": False,
            "authenticated": False,
            "reason": "copilot CLI not installed",
            "checked_at": _now_iso(),
            "verification_mode": "auth_probe",
            "trust_level": "not_confirmed",
        }
        _set_last_verify(payload)
        return payload

    auth_ok, auth_reason = _auth_probe_ok()
    if auth_ok and not deep:
        payload = {
            "ok": True,
            "authenticated": True,
            "reason": auth_reason,
            "checked_at": _now_iso(),
            "verification_mode": "auth_probe",
            "trust_level": "auth_confirmed",
            "note": "This check does not use Copilot quota. Use a test prompt only if you need a live model reply.",
        }
        _set_last_verify(payload)
        return payload

    if not auth_ok and not deep:
        payload = {
            "ok": False,
            "authenticated": False,
            "reason": auth_reason,
            "checked_at": _now_iso(),
            "verification_mode": "auth_probe",
            "trust_level": "not_confirmed",
        }
        _set_last_verify(payload)
        return payload

    try:
        cp = subprocess.run(
            [_COPILOT_PATH, "-sp", "Reply exactly with READY"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        raw = (cp.stdout or cp.stderr or "").strip()
        ok = cp.returncode == 0 and "READY" in raw
        reason = None if ok else (raw or f"copilot exited with code {cp.returncode}")
        error_kind = None
        detail = None
        if not ok and reason:
            error_kind, friendly, detail = _classify_copilot_error(reason)
            reason = friendly
        payload = {
            "ok": ok,
            "authenticated": ok or auth_ok,
            "reason": reason if not ok else auth_reason,
            "detail": detail,
            "error_kind": error_kind,
            "checked_at": _now_iso(),
            "verification_mode": "runtime_prompt",
            "trust_level": "runtime_confirmed" if ok else ("auth_confirmed" if auth_ok else "not_confirmed"),
            "note": "This test used one Copilot request." if deep else None,
        }
        _set_last_verify(payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        error_kind, reason, detail = _classify_copilot_error(str(exc))
        payload = {
            "ok": auth_ok,
            "authenticated": auth_ok,
            "reason": reason,
            "detail": detail,
            "error_kind": error_kind,
            "checked_at": _now_iso(),
            "verification_mode": "runtime_prompt",
            "trust_level": "auth_confirmed" if auth_ok else "not_confirmed",
        }
        _set_last_verify(payload)
        return payload


def _looks_like_policy_error(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        token in lowered
        for token in (
            "access denied by policy",
            "policy settings",
            "copilot cli policy",
            "organization has restricted",
            "does not include this feature",
            "required policies have not been enabled",
            "restricted copilot access",
        )
    )


def _looks_like_quota_error(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        token in lowered
        for token in (
            "quota",
            "rate limit",
            "usage limit",
            "billing",
            "exceeded",
            "too many requests",
            "resource exhausted",
        )
    )


def _classify_copilot_error(text: str) -> tuple[str | None, str, str | None]:
    """Return (error_kind, friendly_message, optional_detail)."""
    raw = str(text or "").strip()
    if not raw:
        return None, "Copilot request failed.", None
    if _looks_like_policy_error(raw):
        return (
            "policy",
            (
                "Login is OK, but GitHub Copilot policy blocked the CLI prompt. "
                "Your organization or plan may restrict Copilot CLI — ask your admin or review "
                "https://github.com/settings/copilot"
            ),
            _clip(raw, 1200),
        )
    if _looks_like_quota_error(raw):
        return (
            "quota",
            (
                f"{_clip(raw, 400)} — This is usually Copilot subscription quota, not an ALEX bug. "
                "Try again later or check billing on your GitHub account."
            ),
            None,
        )
    return "other", _clip(raw, 600), _clip(raw, 1200) if len(raw) > 600 else None


def _clip(value: Any, limit: int = _MAX_TEXT) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_source(src: dict[str, Any] | None) -> str:
    if not isinstance(src, dict):
        return ""
    parts = [
        src.get("file") or src.get("document") or "",
        src.get("table") or src.get("table_id") or "",
        f"row {src.get('row')}" if src.get("row") else "",
        f"sheet {src.get('sheet')}" if src.get("sheet") else "",
    ]
    return " / ".join(p for p in parts if p)


def _serialize_given(op: dict[str, Any] | None) -> str:
    if not isinstance(op, dict):
        return ""
    parts: list[str] = []
    for item in op.get("given") or []:
        if isinstance(item, dict):
            sig = item.get("signal")
            val = item.get("value")
            note = item.get("note")
            if sig and val is not None:
                parts.append(f"{sig}={val}")
            elif note:
                parts.append(str(note))
            else:
                parts.append(_clip(item, 120))
        else:
            parts.append(_clip(item, 120))
    return "; ".join(x for x in parts if x)


def _serialize_when(op: dict[str, Any] | None) -> str:
    if not isinstance(op, dict):
        return ""
    parts: list[str] = []
    for item in op.get("when") or []:
        if isinstance(item, dict):
            if item.get("description"):
                parts.append(str(item["description"]))
            elif item.get("timing"):
                parts.append(str(item["timing"]))
            else:
                parts.append(_clip(item, 120))
        else:
            parts.append(_clip(item, 120))
    return "; ".join(x for x in parts if x)


def _serialize_expectation(expectation: Any) -> str:
    parts: list[str] = []
    for item in expectation or []:
        if isinstance(item, dict):
            desc = item.get("description") or item.get("review_note")
            if desc:
                parts.append(str(desc))
        else:
            parts.append(_clip(item, 120))
    return "; ".join(parts)


def _find_logic_item(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    for item in bundle.get("logic_review_items") or []:
        if item.get("logic_id") == logic_id:
            return item
    raise KeyError(f"Logic review item not found: {logic_id}")


def _logic_context_markdown(
    bundle: dict[str, Any],
    logic_item: dict[str, Any],
    *,
    engineer_note: str = "",
) -> str:
    issues = logic_item.get("issues") or []
    rows = logic_item.get("table_rows") or []
    candidates = logic_item.get("candidates") or []
    block_id = logic_item.get("logic_id")
    source = logic_item.get("source_evidence") or {}

    raw_terms = " ".join(
        [
            logic_item.get("control_name", ""),
            logic_item.get("expression", ""),
            " ".join(str(r.get("raw_condition", "")) for r in rows[:_MAX_TABLE_ROWS]),
        ]
    )
    defs = []
    for d in bundle.get("condition_definitions") or []:
        name = str(d.get("name", "")).strip()
        if name and name in raw_terms:
            defs.append(d)
        if len(defs) >= 12:
            break

    lines = [
        "# Copilot context pack",
        "",
        "## Rules",
        "- Use only the evidence in this file.",
        "- The deterministic parser owns the final logic structure.",
        "- Do not invent signal values, gates, states, outputs, or document references.",
        "- If something is unclear, keep it blank and mark review_required true.",
        "- Return JSON only when asked.",
        "",
        "## Logic block",
        f"- logic_id: {block_id}",
        f"- control_name: {logic_item.get('control_name', '')}",
        f"- parse_status: {logic_item.get('parse_status', '')}",
        f"- expression: {_clip(logic_item.get('expression', ''), 1200)}",
        f"- source: {_clip(source.get('summary', ''), 400)}",
        "",
        "## Source table rows",
    ]
    for row in rows[:_MAX_TABLE_ROWS]:
        lines.append(
            f"- row {row.get('row_no')}: depth={row.get('depth')} type={row.get('detected_type')} "
            f"text={_clip(row.get('raw_condition', ''), 240)}"
        )

    if defs:
        lines.extend(["", "## Matching condition definitions"])
        for d in defs:
            lines.append(
                f"- {d.get('name')}: {_clip(d.get('definition', ''), 220)} | source={_format_source(d.get('source'))}"
            )

    if issues:
        lines.extend(["", "## Relevant issues"])
        for issue in issues[:_MAX_ISSUES]:
            lines.append(
                f"- {issue.get('severity', 'info')} {issue.get('type', '')}: {_clip(issue.get('message', ''), 240)}"
            )

    if engineer_note.strip():
        lines.extend(["", "## Engineer clarification note"])
        lines.append(f"- {_clip(engineer_note, 1200)}")

    attachments = ((bundle.get("ai_assists") or {}).get("logic_attachments") or {}).get(block_id, [])
    if attachments:
        lines.extend(["", "## Extra engineer attachments"])
        for att in attachments[:8]:
            lines.append(f"- file: {att.get('name')} ({att.get('kind')})")
            lines.append(f"  preview: {_clip(att.get('preview', ''), 900)}")

    lines.extend(["", "## Deterministic candidate rows"])
    for cand in candidates[:_MAX_CANDIDATES]:
        op = cand.get("operation") or {}
        lines.append(f"- candidate_id: {cand.get('id')}")
        lines.append(f"  event: {_clip(cand.get('event', ''), 160)}")
        lines.append(f"  use_case: {_clip(cand.get('use_case_description', ''), 220)}")
        lines.append(f"  operation: {_clip(_serialize_when(op), 220)}")
        lines.append(f"  expected_input: {_clip(_serialize_given(op), 220)}")
        lines.append(f"  expected_output: {_clip(_serialize_expectation(cand.get('expectation')), 220)}")
        lines.append(f"  source: {_clip(cand.get('traceability', {}).get('source_evidence', ''), 220)}")

    return "\n".join(lines).strip() + "\n"


def _logic_prompt(logic_item: dict[str, Any], *, language: str = "EN") -> str:
    language = (language or "EN").upper()
    return (
        "Read ./context.md in the current directory.\n"
        "You are helping build a trustworthy automotive test specification workbook.\n"
        f"Draft workbook text for language: {language}.\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "logic_id": "string",\n'
        '  "control_name": "string",\n'
        '  "summary": "string",\n'
        '  "warnings": ["string"],\n'
        '  "term_resolutions": [\n'
        "    {\n"
        '      "term": "string",\n'
        '      "matched_definition_name": "string",\n'
        '      "reason": "string",\n'
        '      "confidence": "low|medium|high"\n'
        "    }\n"
        "  ],\n"
        '  "candidate_updates": [\n'
        "    {\n"
        '      "candidate_id": "string",\n'
        '      "use_case_en": "string",\n'
        '      "use_case_jp": "string",\n'
        '      "operation_text_en": "string",\n'
        '      "operation_text_jp": "string",\n'
        '      "expected_input_en": "string",\n'
        '      "expected_input_jp": "string",\n'
        '      "expected_output_en": "string",\n'
        '      "expected_output_jp": "string",\n'
        '      "confidence": "low|medium|high",\n'
        '      "review_required": true,\n'
        '      "open_questions": ["string"],\n'
        '      "evidence_refs": ["string"],\n'
        '      "changed_fields": ["UseCase","Operation","ExpectedInput","ExpectedOutput"]\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Constraints:\n"
        "- Keep the deterministic expression unchanged; explain it, do not replace it.\n"
        "- Keep each field concise and workbook-ready.\n"
        "- expected_input and expected_output must use concrete test values (numbers with units), not prose.\n"
        "  Example: Given: VEH_SPD=2.01 km/h, Then: PWR_STATE=1 — never 'vehicle motion is zero'.\n"
        "- For thresholds (>2, >=5 ms), pick a value just past the boundary (2.01, 5.01 ms).\n"
        f"- Fill the {language} fields first. If the other language is not requested, leave it empty.\n"
        "- If a missing term looks like it matches an attached definition by spacing, punctuation, or naming variation, add it to term_resolutions instead of silently assuming it.\n"
        "- If engineer clarification resolves a missing term, use it as working evidence and reflect that in the output.\n"
        "- If engineer clarification is still incomplete, ask precise follow-up questions instead of guessing.\n"
        "- If evidence is missing, use empty string for that field and add an open question.\n"
        f"- Focus on control `{logic_item.get('control_name', '')}` only.\n"
    )


def _definition_query_prompt(*, term: str, question: str) -> str:
    return (
        "Read ./context.md in the current directory.\n"
        "You are helping resolve a missing or ambiguous spec term for an automotive test engineer.\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "term": "string",\n'
        '  "answer": "string",\n'
        '  "suggested_matches": [\n'
        "    {\n"
        '      "name": "string",\n'
        '      "reason": "string",\n'
        '      "confidence": "low|medium|high"\n'
        "    }\n"
        "  ],\n"
        '  "follow_up_questions": ["string"],\n'
        '  "evidence_refs": ["string"]\n'
        "}\n"
        "Constraints:\n"
        "- Use only the uploaded evidence, attached files, and engineer note in context.md.\n"
        "- Do not change the deterministic logic tree.\n"
        "- If the engineer note already gives a usable plain-language meaning for the focus term, normalize it and do not ask another question.\n"
        "- Ask at most one follow-up question.\n"
        "- Only ask a follow-up question if missing information blocks a workbook-ready definition, such as units, threshold, polarity, or value mapping.\n"
        "- If a rough definition is already enough for review, leave follow_up_questions empty.\n"
        f"- Focus term: `{term}`.\n"
        f"- Engineer query: `{question.strip()}`.\n"
    )


def _extract_json(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = _JSON_RE.search(text)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Copilot response did not contain parseable JSON.")


def _overlay_from_update(
    update: dict[str, Any],
    *,
    logic_id: str,
    control_name: str,
    raw_response: str,
) -> dict[str, Any]:
    return {
        "provider": "copilot_cli",
        "logic_id": logic_id,
        "control_name": control_name,
        "updated_at": _now_iso(),
        "confidence": update.get("confidence", "low"),
        "review_required": bool(update.get("review_required", True)),
        "open_questions": update.get("open_questions") or [],
        "evidence_refs": update.get("evidence_refs") or [],
        "changed_fields": update.get("changed_fields") or [],
        "summary": update.get("summary") or "",
        "en": {
            "use_case": update.get("use_case_en", ""),
            "operation": update.get("operation_text_en", ""),
            "expected_input": update.get("expected_input_en", ""),
            "expected_output": update.get("expected_output_en", ""),
        },
        "jp": {
            "use_case": update.get("use_case_jp", ""),
            "operation": update.get("operation_text_jp", ""),
            "expected_input": update.get("expected_input_jp", ""),
            "expected_output": update.get("expected_output_jp", ""),
        },
        "raw_response": raw_response,
    }


def _run_copilot_prompt(
    *,
    ctx_dir: Path,
    prompt_text: str,
    command_id: str | None,
) -> str:
    proc = subprocess.Popen(
        [_COPILOT_PATH, "-sp", prompt_text],
        cwd=str(ctx_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    chunks: list[str] = []
    if command_id:
        _append_log(command_id, "Copilot request started.")
    assert proc.stdout is not None
    for line in proc.stdout:
        chunks.append(line)
        if command_id:
            _append_log(command_id, line)
    rc = proc.wait(timeout=180)
    raw = "".join(chunks).strip()
    if rc != 0:
        raise RuntimeError(raw or f"copilot exited with code {rc}")
    if command_id and not raw:
        _append_log(command_id, "Copilot finished with empty stdout.")
    return raw


def _apply_logic_assist(
    *,
    output_dir: Path,
    bundle: dict[str, Any],
    logic_id: str,
    engineer_note: str = "",
    language: str = "EN",
    command_id: str | None = None,
) -> dict[str, Any]:
    if not shutil.which(_COPILOT_PATH):
        raise RuntimeError("copilot CLI not found. Install it first, then retry.")

    logic_item = _find_logic_item(bundle, logic_id)
    ctx_dir = output_dir / "copilot_context" / logic_id
    ctx_dir.mkdir(parents=True, exist_ok=True)
    context_md = _logic_context_markdown(bundle, logic_item, engineer_note=engineer_note)
    prompt_text = _logic_prompt(logic_item, language=language)
    (ctx_dir / "context.md").write_text(context_md, encoding="utf-8")
    (ctx_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    if engineer_note.strip():
        (ctx_dir / "engineer_note.txt").write_text(engineer_note.strip() + "\n", encoding="utf-8")
    if command_id:
        _append_log(command_id, f"Context pack ready for {logic_item.get('control_name', logic_id)}.")
        _append_log(command_id, f"Context folder: {ctx_dir}")

    raw = _run_copilot_prompt(ctx_dir=ctx_dir, prompt_text=prompt_text, command_id=command_id)

    parsed = _extract_json(raw)
    parsed.setdefault("logic_id", logic_id)
    parsed.setdefault("control_name", logic_item.get("control_name"))

    ai = bundle.setdefault("ai_assists", {})
    ai["provider"] = "copilot_cli"
    ai["last_logic_id"] = logic_id
    ai["updated_at"] = _now_iso()
    ai.setdefault("logic_reviews", {})[logic_id] = {
        "context_dir": str(ctx_dir),
        "summary": parsed.get("summary", ""),
        "warnings": parsed.get("warnings") or [],
        "term_resolutions": parsed.get("term_resolutions") or [],
        "raw_response": raw,
        "response": parsed,
    }
    ai.setdefault("term_resolution_hints", {})[logic_id] = parsed.get("term_resolutions") or []
    overlays = ai.setdefault("candidate_overlays", {})
    for update in parsed.get("candidate_updates") or []:
        cid = update.get("candidate_id")
        if not cid:
            continue
        overlays[cid] = _overlay_from_update(
            update,
            logic_id=logic_id,
            control_name=str(parsed.get("control_name") or logic_item.get("control_name") or ""),
            raw_response=raw,
        )

    return {
        "logic_id": logic_id,
        "control_name": parsed.get("control_name"),
        "summary": parsed.get("summary", ""),
        "warnings": parsed.get("warnings") or [],
        "term_resolutions": parsed.get("term_resolutions") or [],
        "candidate_updates": parsed.get("candidate_updates") or [],
        "context_dir": str(ctx_dir),
        "raw_response": raw,
    }


def run_logic_assist(
    *,
    output_dir: Path,
    bundle: dict[str, Any],
    logic_id: str,
    engineer_note: str = "",
    language: str = "EN",
) -> dict[str, Any]:
    return _apply_logic_assist(
        output_dir=output_dir,
        bundle=bundle,
        logic_id=logic_id,
        engineer_note=engineer_note,
        language=language,
        command_id=None,
    )


def start_definition_query_command(
    *,
    output_dir: Path,
    bundle: dict[str, Any],
    logic_id: str,
    term: str,
    question: str,
    engineer_note: str = "",
    save_bundle: Callable[[dict[str, Any]], None] | None = None,
) -> CopilotCommandState:
    cmd = _create_command("definition_query")
    _update_command(cmd.command_id, status="running", current_logic_id=logic_id, progress_total=1, progress_current=0)

    def worker() -> None:
        try:
            if not shutil.which(_COPILOT_PATH):
                raise RuntimeError("copilot CLI not found. Install it first, then retry.")
            logic_item = _find_logic_item(bundle, logic_id)
            ctx_dir = output_dir / "copilot_context" / logic_id / "definition_query"
            ctx_dir.mkdir(parents=True, exist_ok=True)
            context_md = _logic_context_markdown(bundle, logic_item, engineer_note=engineer_note)
            context_md += f"\n## Focus term\n- {term}\n\n## Engineer question\n- {question.strip()}\n"
            prompt_text = _definition_query_prompt(term=term, question=question)
            (ctx_dir / "context.md").write_text(context_md, encoding="utf-8")
            (ctx_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
            _append_log(cmd.command_id, f"Resolving term {term} for {logic_item.get('control_name', logic_id)}")
            raw = _run_copilot_prompt(ctx_dir=ctx_dir, prompt_text=prompt_text, command_id=cmd.command_id)
            parsed = _extract_json(raw)
            ai = bundle.setdefault("ai_assists", {})
            query_rows = ai.setdefault("definition_queries", {}).setdefault(logic_id, [])
            entry = {
                "term": parsed.get("term") or term,
                "question": question.strip(),
                "answer": parsed.get("answer", ""),
                "suggested_matches": parsed.get("suggested_matches") or [],
                "follow_up_questions": parsed.get("follow_up_questions") or [],
                "evidence_refs": parsed.get("evidence_refs") or [],
                "updated_at": _now_iso(),
                "raw_response": raw,
            }
            query_rows.append(entry)
            ai.setdefault("term_resolution_hints", {}).setdefault(logic_id, [])
            ai["term_resolution_hints"][logic_id].extend(
                [
                    {
                        "term": term,
                        "matched_definition_name": row.get("name", ""),
                        "reason": row.get("reason", ""),
                        "confidence": row.get("confidence", "low"),
                    }
                    for row in entry["suggested_matches"]
                ]
            )
            if save_bundle:
                save_bundle(bundle)
            _update_command(
                cmd.command_id,
                status="completed",
                completed_at=_now_iso(),
                progress_current=1,
                result=entry,
            )
        except Exception as exc:  # noqa: BLE001
            _append_log(cmd.command_id, f"ERROR: {exc}")
            _kind, friendly, _detail = _classify_copilot_error(str(exc))
            _update_command(
                cmd.command_id,
                status="failed",
                completed_at=_now_iso(),
                error_message=friendly,
            )

    threading.Thread(target=worker, daemon=True).start()
    return get_command(cmd.command_id) or cmd


def start_logic_assist_command(
    *,
    output_dir: Path,
    bundle: dict[str, Any],
    logic_ids: list[str],
    engineer_notes: dict[str, str] | None = None,
    language: str = "EN",
    save_bundle: Callable[[dict[str, Any]], None] | None = None,
) -> CopilotCommandState:
    cmd = _create_command("assist")
    notes = engineer_notes or {}
    _update_command(
        cmd.command_id,
        status="running",
        progress_total=len(logic_ids),
        progress_current=0,
    )

    def worker() -> None:
        try:
            results: list[dict[str, Any]] = []
            for idx, logic_id in enumerate(logic_ids, start=1):
                logic_item = _find_logic_item(bundle, logic_id)
                _update_command(
                    cmd.command_id,
                    current_logic_id=logic_id,
                    progress_current=idx - 1,
                    progress_total=len(logic_ids),
                )
                _append_log(cmd.command_id, f"[{idx}/{len(logic_ids)}] Drafting {logic_item.get('control_name', logic_id)}")
                res = _apply_logic_assist(
                    output_dir=output_dir,
                    bundle=bundle,
                    logic_id=logic_id,
                    engineer_note=notes.get(logic_id, ""),
                    language=language,
                    command_id=cmd.command_id,
                )
                results.append(res)
                if save_bundle:
                    save_bundle(bundle)
                _append_log(cmd.command_id, f"Completed {logic_item.get('control_name', logic_id)}")
            if save_bundle:
                save_bundle(bundle)
            _update_command(
                cmd.command_id,
                status="completed",
                completed_at=_now_iso(),
                progress_current=len(logic_ids),
                result={"logic_results": results, "count": len(results)},
            )
        except Exception as exc:  # noqa: BLE001
            _append_log(cmd.command_id, f"ERROR: {exc}")
            _kind, friendly, _detail = _classify_copilot_error(str(exc))
            _update_command(
                cmd.command_id,
                status="failed",
                completed_at=_now_iso(),
                error_message=friendly,
            )

    threading.Thread(target=worker, daemon=True).start()
    return get_command(cmd.command_id) or cmd


def apply_knowledge_via_copilot(
    bundle: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    failure_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply knowledge patches via GitHub Copilot CLI (same JSON procedure as M365)."""
    import json

    from web.m365_brief import build_copilot_brief
    from web.m365_copilot import parse_knowledge_response, strict_knowledge_procedure_prompt

    auth_ok, auth_reason = _auth_probe_ok()
    if not auth_ok:
        return {"ok": False, "error": auth_reason or "Sign in to GitHub Copilot CLI on the Review tab."}
    if not shutil.which(_COPILOT_PATH):
        return {"ok": False, "error": "copilot CLI not found. Install with `npm install -g @github/copilot`."}

    brief = build_copilot_brief(bundle, logic_id, engineer_note)
    prompt = strict_knowledge_procedure_prompt(brief)
    if failure_context:
        prompt += "\n\nFix these logic_compliance failures:\n"
        prompt += json.dumps(failure_context[:30], ensure_ascii=False)[:6000]

    ctx_root = Path(__file__).resolve().parent.parent / "web_data" / "copilot_knowledge"
    ctx_dir = ctx_root / logic_id
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / "brief.md").write_text(brief, encoding="utf-8")
    (ctx_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    try:
        raw = _run_copilot_prompt(ctx_dir=ctx_dir, prompt_text=prompt, command_id=None)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    patches, definition_updates = parse_knowledge_response(raw)
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
                    "source": "copilot_cli",
                }
    return {
        "ok": True,
        "patches": patches,
        "definition_updates": definition_updates,
        "context_dir": str(ctx_dir),
        "reply_preview": raw[:500],
    }
