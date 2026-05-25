"""Classify spec terms as guard input, system state, or output assertion."""

from __future__ import annotations

import re
from typing import Any

_LOGIC_OPS = frozenset({"AND", "OR", "NOT", "TRUE", "FALSE"})
_STATE_NAME_HINTS = re.compile(r"^(OFF|RUN|ACCESSORY|SHUT_OFF|SHUTOFF|ON|IDLE|PREPARED)$", re.I)
_OUTPUT_SUFFIXES = ("_DECISION", "_READY", "_PERMISSION", "_STS", "_STATUS")
_SYSTEM_STATE_NAMES = frozenset({"LOST", "LOST_VALUE", "TIMER", "ELAPSED"})


def classify_term(
    term: str,
    *,
    control_name: str = "",
    definition: str = "",
) -> str:
    """
    Returns: guard_input | system_state | output_assertion | composite_guard | alias_only | unknown
    """
    name = str(term or "").strip()
    if not name or name.upper() in _LOGIC_OPS:
        return "unknown"
    upper = re.sub(r"\(\*\d+\)", "", name).strip().upper()
    ctrl = str(control_name or "").strip().upper()
    defn = str(definition or "").lower()

    if ctrl and upper == ctrl:
        return "output_assertion"
    if upper.endswith(_OUTPUT_SUFFIXES) or "DECISION" in upper:
        return "output_assertion"
    if upper in _SYSTEM_STATE_NAMES or "lost" in defn and upper == "LOST":
        return "system_state"
    if _STATE_NAME_HINTS.match(upper) and not upper.startswith("CND_"):
        return "system_state"
    if upper.startswith("CND_") and any(x in upper for x in ("OUTPUT", "READY", "PERMISSION")):
        return "output_assertion"
    if upper.startswith("FORCE_") or upper.startswith("OK_") or upper.startswith("NOK_"):
        return "guard_input"
    if upper.startswith("REQ_") or upper.startswith("RESET_"):
        return "guard_input"
    if upper.startswith("CND_"):
        return "guard_input"
    if " or " in defn or " and " in defn or "==" in defn:
        return "composite_guard"
    return "guard_input"


def build_term_role_index(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map term -> {role, control_name?, source?}."""
    index: dict[str, dict[str, Any]] = {}

    def put(term: str, role: str, **extra: Any) -> None:
        key = str(term or "").strip()
        if not key:
            return
        base = re.sub(r"\(\*\d+\)", "", key).strip()
        for k in {key, base, base.upper()}:
            if not k:
                continue
            prev = index.get(k)
            if prev and prev.get("role") == "output_assertion":
                continue
            index[k] = {"term": base, "role": role, **extra}

    for lb in bundle.get("logic_blocks") or []:
        ctrl = str(lb.get("name") or "")
        put(ctrl, "output_assertion", control_name=ctrl, logic_id=lb.get("id"))
        for ref in lb.get("unresolved_refs") or []:
            put(str(ref), "guard_input", logic_id=lb.get("id"), control_name=ctrl)

    for d in bundle.get("condition_definitions") or []:
        nm = str(d.get("name") or "")
        role = classify_term(nm, control_name="", definition=str(d.get("definition") or ""))
        put(nm, role, source="condition_definition")

    for st in bundle.get("states") or []:
        nm = str(st.get("name") or st.get("id") or "")
        if nm:
            put(nm, "system_state", source="state_machine")

    for foot in bundle.get("footnote_definitions") or []:
        cond = str(foot.get("condition_name") or "")
        if cond:
            put(cond, classify_term(cond, definition=str(foot.get("definition") or "")), source="footnote")
        body = str(foot.get("definition") or foot.get("raw_text") or "")
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=", body):
            var = m.group(1)
            if var.upper() not in _LOGIC_OPS:
                put(var, classify_term(var, definition=body), source="footnote_body")

    return index


def is_state_machine_state(name: str, bundle: dict[str, Any]) -> bool:
    nm = str(name or "").strip().upper()
    if not nm:
        return False
    states = {str(s.get("name") or s.get("id") or "").upper() for s in bundle.get("states") or []}
    return nm in states
