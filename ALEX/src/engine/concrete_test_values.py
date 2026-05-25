"""Materialize workbook Given/When/Then lines as concrete test values."""

from __future__ import annotations

import re
from typing import Any

from src.engine.coverage_intent import path_coverage_intent
from src.engine.given_value_resolver import (
    definition_to_concrete_value,
    is_discrete_guard_signal,
    normalize_discrete_value,
    sanitize_given_item,
)

_COMPARISON_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_.]*)\s*(?P<op>>=|<=|!=|==|=|>|<)\s*(?P<rhs>[^\n;]+)",
    re.I,
)
_UNIT_RE = re.compile(r"\b(km/h|kph|m/s|rpm|%|ms|s)\b", re.I)
_GENERIC_TEXT = re.compile(
    r"satisfy all guards|as interpreted|composite condition group|refer to lower|"
    r"vehicle motion state is zero|operator override is not active|remains active until timer|"
    r"the tool must|condition line is written|written as NOT",
    re.I,
)
_PROSE_HINT = re.compile(r"\b(is|are|means|must|when|otherwise|active|inactive)\b", re.I)
_BECOMES_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s+becomes\s+(.+)$",
    re.I,
)
_STATE_REACH_RE = re.compile(r"reach state.*?consistent with\s+([A-Za-z0-9_]+)", re.I)


def _clip_line(line: str) -> str:
    text = str(line or "").strip()
    return text


def _is_spurious_boundary_value(value: str) -> bool:
    val = str(value or "").strip()
    m = re.match(r"^(\d+)\.(\d+)(?:\s|$)", val)
    if not m:
        return False
    return m.group(2) in ("01", "001") or (len(m.group(2)) == 2 and m.group(2).startswith("0"))


def dedupe_expected_input_lines(lines: list[str]) -> list[str]:
    """One Given line per signal; preserve Precondition/When order first."""
    by_signal: dict[str, str] = {}
    other: list[str] = []
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        m = re.match(r"^Given:\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text, re.I)
        if m:
            sig = m.group(1).upper()
            prev = by_signal.get(sig)
            new_val = m.group(2).strip()
            if prev and is_discrete_guard_signal(sig):
                prev_val = re.sub(r"^Given:\s*[^=]+=\s*", "", prev, flags=re.I).strip()
                if _is_spurious_boundary_value(new_val) and not _is_spurious_boundary_value(prev_val):
                    continue
                if _is_spurious_boundary_value(prev_val) and not _is_spurious_boundary_value(new_val):
                    by_signal[sig] = text
                    continue
            by_signal[sig] = text
        else:
            other.append(text)
    return other + [by_signal[k] for k in by_signal]


def dedupe_expected_input_text(text: str) -> str:
    return "\n".join(dedupe_expected_input_lines(text.split("\n")))


def infer_boundary_value(operator: str, rhs: str) -> str:
    """Pick a test value just past a numeric threshold (e.g. >2 km/h -> 2.01 km/h)."""
    op = operator.strip()
    rhs_clean = rhs.strip().strip("\"'")
    unit_m = _UNIT_RE.search(rhs_clean)
    unit = f" {unit_m.group(1)}" if unit_m else ""
    num_m = re.search(r"[-+]?\d*\.?\d+", rhs_clean.replace(",", ""))
    if not num_m:
        return rhs_clean
    num = float(num_m.group())
    if op in (">", ">="):
        delta = 0.01 if abs(num - round(num)) < 1e-9 else max(abs(num) * 0.01, 0.01)
        test = num + delta
    elif op in ("<", "<="):
        delta = 0.01 if abs(num - round(num)) < 1e-9 else max(abs(num) * 0.01, 0.01)
        test = num - delta
    elif op == "!=":
        test = num + 1 if abs(num - round(num)) < 1e-9 else num * 1.05
    else:
        test = num
    if abs(test - round(test)) < 1e-9:
        body = str(int(round(test)))
    else:
        body = f"{test:.2f}".rstrip("0").rstrip(".")
    return f"{body}{unit}".strip()


def _is_prose_definition(definition: str) -> bool:
    """Long explanatory text — not a concrete SIG=value for Expected input."""
    d = definition.strip()
    if not d or _GENERIC_TEXT.search(d):
        return True
    if _COMPARISON_RE.search(d) or re.fullmatch(r"(TRUE|FALSE|ON|OFF|PASS|0|1|=?\s*\d+)", d, re.I):
        return False
    if d.startswith("="):
        val = d.lstrip("= ").strip()
        return len(val) > 32 and " " in val and _PROSE_HINT.search(val)
    return len(d) > 40 and " " in d and _PROSE_HINT.search(d)


def expand_definition_to_given_lines(definition: str) -> list[str]:
    """Split composite engineer definitions into concrete Given lines."""
    lines: list[str] = []
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,\n]+?)(?=\s+and\s+|\s*,\s*|$)", definition, re.I):
        sub_term = m.group(1).strip()
        sub_def = m.group(2).strip()
        line = definition_to_given_line(sub_term, sub_def)
        if line:
            lines.append(line)
    return lines


def definition_to_given_line(term: str, definition: str) -> str | None:
    definition = definition.strip()
    if not definition or _GENERIC_TEXT.search(definition):
        return None
    concrete = definition_to_concrete_value(term, definition, path_intent="satisfy")
    if concrete is not None:
        return f"Given: {term}={concrete}"
    if definition.startswith("="):
        val = definition.lstrip("= ").strip()
        if val and not _is_prose_definition(val):
            return f"Given: {term}={val}"
        definition = val
    if _is_prose_definition(definition):
        if re.search(rf"\bNOT\s+{re.escape(term)}\b", definition, re.I):
            return f"Given: {term}=0"
        if re.search(rf"\b{re.escape(term)}\b", definition, re.I) and re.search(
            r"\b(active|true|enabled|on)\b", definition, re.I
        ):
            return f"Given: {term}=1"
        return None
    if re.fullmatch(r"(TRUE|FALSE|ON|OFF|PASS|0|1)", definition, re.I):
        return f"Given: {term}={normalize_discrete_value(definition)}"
    if len(definition) <= 48 and " " not in definition.strip():
        return f"Given: {term}={definition}"
    return None


def _format_signal_given(item: dict[str, Any], *, path_intent: str = "satisfy") -> str | None:
    if not isinstance(item, dict):
        return None
    item = sanitize_given_item(item, path_intent=path_intent)
    sig = item.get("signal")
    val = item.get("value")
    if sig is not None and val is not None:
        sig_str = str(sig).strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", sig_str)
        if m:
            sig_str = m.group(1).strip()
            if not str(val).strip() or str(val).strip() == "1":
                val = m.group(2).strip()
        rendered = str(val).strip()
        if (
            not is_discrete_guard_signal(sig_str)
            and str(item.get("operator") or "==") in (">", ">=", "<", "<=")
            and path_intent == "violate"
        ):
            rendered = infer_boundary_value(str(item.get("operator")), str(val))
        return f"Given: {sig_str}={rendered}"
    note = str(item.get("note") or "").strip()
    if note and not _GENERIC_TEXT.search(note):
        return note if note.lower().startswith("given:") else f"Given: {note}"
    timing = str(item.get("timing") or "").strip()
    if timing:
        return f"When: {timing}" if not timing.lower().startswith("when:") else timing
    return None


def _format_when_line(item: Any) -> str | None:
    if isinstance(item, dict):
        timing = str(item.get("timing") or "").strip()
        if timing:
            return timing if timing.lower().startswith("when:") else f"When: {timing}"
        desc = str(item.get("description") or "").strip()
        if desc and not _GENERIC_TEXT.search(desc):
            return desc if desc.lower().startswith("when:") else f"When: {desc}"
        return None
    text = str(item).strip()
    if not text or _GENERIC_TEXT.search(text):
        return None
    return text if text.lower().startswith("when:") else f"When: {text}"


def _format_then_item(item: Any, *, default_state: str | None = None) -> str | None:
    if isinstance(item, dict):
        sig = item.get("signal")
        val = item.get("value")
        if sig is not None and val is not None:
            return f"Then: {sig}={val}"
        desc = str(item.get("description") or item.get("review_note") or "").strip()
        if desc:
            m = _BECOMES_RE.match(desc)
            if m:
                return f"Then: {m.group(1)}={m.group(2).strip()}"
            m2 = _STATE_REACH_RE.search(desc)
            if m2:
                state = m2.group(1)
                return f"Then: System state = {state}"
            if not _GENERIC_TEXT.search(desc):
                return desc if desc.lower().startswith("then:") else f"Then: {desc}"
        return None
    text = str(item).strip()
    if not text:
        return None
    m = _BECOMES_RE.match(text)
    if m:
        return f"Then: {m.group(1)}={m.group(2).strip()}"
    return text if text.lower().startswith("then:") else f"Then: {text}"


def _lookup_definition_lines(
    candidate: dict[str, Any],
    definition_lookup: dict[str, list[dict[str, Any]]],
    *,
    ignore_terms: set[str] | None = None,
) -> list[str]:
    ignore = ignore_terms or set()
    texts: list[str] = []
    operation = candidate.get("operation") or {}
    for item in operation.get("given") or []:
        if isinstance(item, dict):
            note = str(item.get("note") or "")
            if note:
                texts.append(note)
    trace = candidate.get("traceability") or {}
    if trace.get("transition"):
        texts.append(str(trace.get("transition")))
    terms: list[str] = []
    for text in texts:
        terms.extend(re.findall(r"\b[A-Z][A-Z0-9_]+\b", text or ""))
    for item in operation.get("given") or []:
        if isinstance(item, dict) and item.get("signal"):
            terms.append(str(item["signal"]))
    lines: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term in ignore or term in seen:
            continue
        rows = definition_lookup.get(term) or definition_lookup.get(re.sub(r"[^A-Z0-9]", "", term.upper())) or []
        if not rows:
            continue
        line = definition_to_given_line(term, str(rows[0].get("definition") or ""))
        if line:
            seen.add(term)
            lines.append(line)
    return lines


def _is_logic_block_candidate(candidate: dict[str, Any]) -> bool:
    trace = candidate.get("traceability") or {}
    return bool(trace.get("logic_block")) or candidate.get("source") == "two_column_logic_block"


def materialize_expected_input(
    candidate: dict[str, Any],
    definition_lookup: dict[str, list[dict[str, Any]]] | None = None,
    *,
    bundle: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    logic_block = _is_logic_block_candidate(candidate)
    for item in candidate.get("precondition") or []:
        if isinstance(item, dict):
            state = item.get("current_state")
            if state and not logic_block:
                lines.append(f"Precondition: System state = {state}")
            elif item.get("note"):
                note = str(item["note"]).strip()
                if note and not _GENERIC_TEXT.search(note):
                    lines.append(
                        note if note.lower().startswith("precondition:") else f"Precondition: {note}"
                    )
    operation = candidate.get("operation") or {}
    control_out = str((candidate.get("traceability") or {}).get("control_name") or "")
    path_intent = path_coverage_intent(candidate) if logic_block else "satisfy"
    for item in operation.get("given") or []:
        if isinstance(item, dict):
            note = str(item.get("note") or "").strip()
            if note and note.lower().startswith("given:"):
                lines.append(note)
                continue
            if note and note.lower().startswith("precondition:"):
                lines.append(note)
                continue
            sig = str(item.get("signal") or "")
            if control_out and sig.upper() == control_out.upper():
                continue
            line = _format_signal_given(item, path_intent=path_intent)
            if line:
                lines.append(line)
    if not logic_block:
        for item in operation.get("when") or []:
            line = _format_when_line(item)
            if line:
                lines.append(line)
    if definition_lookup and not logic_block:
        ignore = {t.split("=")[0].replace("Given:", "").strip() for t in lines if t.startswith("Given:")}
        lines.extend(_lookup_definition_lines(candidate, definition_lookup, ignore_terms=ignore))
    return dedupe_expected_input_text("\n".join(lines))


def materialize_expected_output(
    candidate: dict[str, Any],
    binding: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    for item in candidate.get("expectation") or []:
        to_state = None
        trace = candidate.get("traceability") or {}
        if isinstance(trace, dict):
            to_state = trace.get("to_state")
        line = _format_then_item(item, default_state=to_state)
        if line:
            lines.append(line)
    for row in (binding or {}).get("state_outputs") or []:
        state = str(row.get("state") or "").strip()
        name = str(row.get("name") or "").strip()
        value = str(row.get("expression") or row.get("definition") or "").strip()
        if name and value:
            if re.search(r"(=|>|<|>=|<=)", value):
                m = _COMPARISON_RE.search(value)
                if m:
                    lhs = m.group("lhs").strip() or name
                    op = m.group("op")
                    rhs = m.group("rhs").strip()
                    val = infer_boundary_value(op, rhs) if op in (">", ">=", "<", "<=") else rhs
                    lines.append(f"Then: {lhs}={val}")
                    continue
            if state:
                lines.append(f"Then: {state} {name}={value}")
            else:
                lines.append(f"Then: {name}={value}")
    trace = candidate.get("traceability") or {}
    if (
        isinstance(trace, dict)
        and trace.get("to_state")
        and trace.get("transition")
        and not _is_logic_block_candidate(candidate)
        and not any("System state" in ln for ln in lines)
    ):
        lines.insert(0, f"Then: System state = {trace['to_state']}")
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = line.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(line)
    return "\n".join(unique)
