"""Deterministic Google Test skeleton generation from spec candidates and logic blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.engine.concrete_test_values import (
    materialize_expected_input,
    materialize_expected_output,
    _format_when_line,
)
from src.engine.path_tc_matrix import _candidate_logic_id

_GIVEN_RE = re.compile(r"^Given:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?P<val>.+)$", re.I)
_THEN_SIG_RE = re.compile(r"^Then:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?P<val>.+)$", re.I)
_THEN_STATE_RE = re.compile(r"^Then:\s*System state\s*=\s*(?P<state>[A-Za-z0-9_]+)", re.I)
_PRECOND_STATE_RE = re.compile(r"^Precondition:\s*System state\s*=\s*(?P<state>[A-Za-z0-9_]+)", re.I)
_WHEN_ELAPSED_RE = re.compile(r"(?:When:\s*)?(?:elapsed_time|time)\s*(?:>=|>|=)\s*(\d+)\s*ms", re.I)
_WHEN_GENERIC_RE = re.compile(r"^When:\s*(.+)$", re.I)

_LOGIC_GATE_TOKENS = frozenset({"AND", "OR", "NOT"})
_RESERVED_TOKENS = _LOGIC_GATE_TOKENS | frozenset(
    {"OFF", "ON", "OK", "NOK", "YES", "NO", "TRUE", "FALSE", "ACCESSORY", "RUN", "PARK"}
)


@dataclass
class GTestHarnessConfig:
    fixture_class: str = "PowerModeTest"
    inputs_member: str = "in"
    outputs_member: str = "out"
    state_member: str = "state"
    state_enum: str = "PowerModeState"
    evaluate_fn: str = "EvaluatePowerMode"
    set_signal_fn: str = "SetSignal"
    advance_time_fn: str = "RunForMs"
    include_header: str = "#include <gtest/gtest.h>"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GTestHarnessConfig:
        if not data:
            return cls()
        helpers = data.get("helpers") or {}
        return cls(
            fixture_class=str(data.get("fixture_class") or "PowerModeTest"),
            inputs_member=str(data.get("inputs_member") or "in"),
            outputs_member=str(data.get("outputs_member") or "out"),
            state_member=str(data.get("state_member") or "state"),
            state_enum=str(data.get("state_enum") or "PowerModeState"),
            evaluate_fn=str(data.get("evaluate_fn") or "EvaluatePowerMode"),
            set_signal_fn=str(helpers.get("set_signal") or data.get("set_signal_fn") or "SetSignal"),
            advance_time_fn=str(helpers.get("advance_time") or data.get("advance_time_fn") or "RunForMs"),
            include_header=str(data.get("include_header") or "#include <gtest/gtest.h>"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_class": self.fixture_class,
            "inputs_member": self.inputs_member,
            "outputs_member": self.outputs_member,
            "state_member": self.state_member,
            "state_enum": self.state_enum,
            "evaluate_fn": self.evaluate_fn,
            "include_header": self.include_header,
            "helpers": {
                "set_signal": self.set_signal_fn,
                "advance_time": self.advance_time_fn,
            },
        }


@dataclass
class GTestDraft:
    source_kind: str
    source_id: str
    test_name: str
    spec_comment_block: str
    code_body: str
    full_snippet: str
    unmapped_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "test_name": self.test_name,
            "spec_comment_block": self.spec_comment_block,
            "code_body": self.code_body,
            "full_snippet": self.full_snippet,
            "unmapped_signals": self.unmapped_signals,
        }


def default_harness_from_config(cfg: dict[str, Any] | None) -> GTestHarnessConfig:
    gtest_cfg = (cfg or {}).get("gtest") or {}
    return GTestHarnessConfig.from_dict(gtest_cfg)


def sanitize_test_name(*parts: str) -> str:
    raw = "_".join(p for p in parts if str(p or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        return "GeneratedTest"
    if cleaned[0].isdigit():
        cleaned = f"T_{cleaned}"
    return cleaned[:120]


def _format_cpp_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "0"
    if re.match(r"^-?\d+(\.\d+)?$", text):
        return f"{text}U" if "." not in text else text
    if text.upper() in {"TRUE", "FALSE"}:
        return "true" if text.upper() == "TRUE" else "false"
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text) and text.isupper():
        return text
    return text


def _is_plausible_signal(name: str) -> bool:
    key = str(name or "").strip().upper()
    if not key or key in _RESERVED_TOKENS:
        return False
    return bool(re.match(r"^[A-Z][A-Z0-9_]+$", key))


def _extract_triplet_signals(given_when_text: str, then_text: str) -> tuple[set[str], set[str]]:
    inputs: set[str] = set()
    outputs: set[str] = set()
    for raw in given_when_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = _GIVEN_RE.match(line)
        if m and _is_plausible_signal(m.group("sig")):
            inputs.add(m.group("sig").strip())
    for raw in then_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = _THEN_SIG_RE.match(line)
        if m and _is_plausible_signal(m.group("sig")):
            outputs.add(m.group("sig").strip())
    return inputs, outputs


def _default_code_expr(
    spec_name: str,
    harness: GTestHarnessConfig,
    *,
    prefer_output: bool = False,
) -> str:
    key = spec_name.strip()
    member = harness.outputs_member if prefer_output else harness.inputs_member
    return f"{member}.{key}"


def _resolve_code_expr(
    spec_name: str,
    variable_map: dict[str, str],
    harness: GTestHarnessConfig,
    *,
    prefer_output: bool = False,
) -> tuple[str, bool]:
    key = spec_name.strip()
    if not key:
        return "", True
    for lookup in (key, key.upper()):
        mapped = str(variable_map.get(lookup) or "").strip()
        if mapped:
            return mapped, True
    return _default_code_expr(key, harness, prefer_output=prefer_output), True


def _collect_spec_signals(candidate: dict[str, Any] | None, logic_block: dict[str, Any] | None) -> set[str]:
    names: set[str] = set()
    if candidate:
        for item in (candidate.get("operation") or {}).get("given") or []:
            if isinstance(item, dict) and item.get("signal"):
                names.add(str(item["signal"]))
        for item in candidate.get("expectation") or []:
            if isinstance(item, dict) and item.get("signal"):
                names.add(str(item["signal"]))
    if logic_block:
        expr = str(logic_block.get("raw_expression") or logic_block.get("expression") or "")
        for token in re.findall(r"\b[A-Z][A-Z0-9_]+\b", expr):
            names.add(token)
    return names


def suggest_variable_map(
    *,
    signals: list[dict[str, Any]] | None = None,
    alias_map: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    logic_blocks: list[dict[str, Any]] | None = None,
    harness: GTestHarnessConfig | None = None,
    existing: dict[str, str] | None = None,
    given_when_text: str = "",
    then_text: str = "",
    code_references: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Build rename map. When triplet text is supplied, only map signals used in that case."""
    h = harness or GTestHarnessConfig()
    out = dict(existing or {})

    if given_when_text or then_text:
        ins, outs = _extract_triplet_signals(given_when_text, then_text)
        for sig in sorted(ins):
            if sig not in out:
                out[sig] = f"{h.inputs_member}.{sig}"
        for sig in sorted(outs):
            if sig not in out:
                out[sig] = f"{h.outputs_member}.{sig}"
    else:
        for sig in signals or []:
            name = str(sig.get("name") or "").strip()
            if name and _is_plausible_signal(name) and name not in out:
                out[name] = f"{h.inputs_member}.{name}"

    for row in alias_map or []:
        target = str(row.get("target") or "").strip()
        alias = str(row.get("alias") or "").strip()
        if target and _is_plausible_signal(target) and target not in out:
            out[target] = f"{h.inputs_member}.{target}"
        if alias and _is_plausible_signal(alias) and alias not in out:
            out[alias] = f"{h.inputs_member}.{target or alias}"

    for ref in code_references or []:
        spec = str(ref.get("spec_name") or ref.get("spec") or "").strip()
        code = str(ref.get("code_name") or ref.get("code") or "").strip()
        if spec and code and _is_plausible_signal(spec):
            out[spec] = code

    if not given_when_text and not then_text:
        for cand in candidates or []:
            for name in _collect_spec_signals(cand, None):
                if _is_plausible_signal(name) and name not in out:
                    out[name] = f"{h.inputs_member}.{name}"
            for item in cand.get("expectation") or []:
                if isinstance(item, dict) and item.get("signal"):
                    sig = str(item["signal"])
                    if _is_plausible_signal(sig) and sig not in out:
                        out[sig] = f"{h.outputs_member}.{sig}"
        for block in logic_blocks or []:
            for name in _collect_spec_signals(None, block):
                if _is_plausible_signal(name) and name not in out:
                    out[name] = f"{h.inputs_member}.{name}"
    return out


def _supplement_when_text(candidate: dict[str, Any], given_when_text: str) -> str:
    """Append operation.when lines when materialize skipped them (logic-block TCs)."""
    if not candidate:
        return given_when_text
    existing = given_when_text.lower()
    extra: list[str] = []
    for item in (candidate.get("operation") or {}).get("when") or []:
        line = _format_when_line(item)
        if line and line.lower() not in existing:
            extra.append(line)
    if not extra:
        return given_when_text
    base = given_when_text.strip()
    return "\n".join(filter(None, [base, *extra]))


def _build_spec_comments(
    *,
    candidate: dict[str, Any] | None,
    logic_block: dict[str, Any] | None,
    given_when_text: str,
    then_text: str,
) -> str:
    lines: list[str] = []
    if candidate:
        cid = str(candidate.get("id") or "")
        event = str(candidate.get("event") or candidate.get("test_function") or "")
        lines.append(f"// Spec reference: {cid} · {event}".rstrip(" ·"))
        trace = candidate.get("traceability") or {}
        control = trace.get("control_name") or trace.get("logic_block") or ""
        if control:
            lines.append(f"// Control: {control}")
    elif logic_block:
        lid = str(logic_block.get("logic_id") or logic_block.get("id") or "")
        control = str(logic_block.get("control_name") or "")
        lines.append(f"// Logic reference: {lid} · {control}".rstrip(" ·"))

    logic_expr = ""
    if logic_block:
        logic_expr = str(
            logic_block.get("raw_expression") or logic_block.get("expression") or ""
        ).strip()
    if logic_expr:
        lines.append(f"// Logic: {logic_expr}")

    for block in (given_when_text, then_text):
        for line in block.split("\n"):
            text = line.strip()
            if text:
                if not text.startswith("//"):
                    lines.append(f"// {text}")
                else:
                    lines.append(text)
    return "\n".join(lines)


def _parse_triplet_lines(
    given_when_text: str,
    then_text: str,
    *,
    variable_map: dict[str, str],
    harness: GTestHarnessConfig,
) -> tuple[list[str], list[str], list[str], list[str]]:
    given_lines: list[str] = []
    when_lines: list[str] = []
    then_lines: list[str] = []
    unmapped: list[str] = []

    for raw in given_when_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m_given = _GIVEN_RE.match(line)
        if m_given:
            sig = m_given.group("sig")
            val = _format_cpp_value(m_given.group("val"))
            expr, _mapped = _resolve_code_expr(sig, variable_map, harness)
            given_lines.append(f"    {expr} = {val};")
            continue
        m_pre = _PRECOND_STATE_RE.match(line)
        if m_pre:
            state = m_pre.group("state")
            given_lines.append(f"    {harness.state_member} = {harness.state_enum}::{state};")
            continue
        m_when_elapsed = _WHEN_ELAPSED_RE.search(line)
        if m_when_elapsed:
            when_lines.append(f"    {harness.advance_time_fn}({m_when_elapsed.group(1)}U);")
            continue
        m_when = _WHEN_GENERIC_RE.match(line)
        if m_when:
            desc = m_when.group(1).strip()
            if re.search(r"evaluate|judgment|control", desc, re.I):
                when_lines.append(
                    f"    {harness.state_member} = {harness.evaluate_fn}("
                    f"{harness.state_member}, {harness.inputs_member}, {harness.outputs_member});"
                )
            else:
                when_lines.append(f"    // When: {desc}")
            continue
        if line.lower().startswith("precondition:"):
            given_lines.append(f"    // {line}")
        elif line.lower().startswith("when:"):
            when_lines.append(f"    // {line}")

    for raw in then_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m_then = _THEN_SIG_RE.match(line)
        if m_then:
            sig = m_then.group("sig")
            val = _format_cpp_value(m_then.group("val"))
            expr, _mapped = _resolve_code_expr(sig, variable_map, harness, prefer_output=True)
            then_lines.append(f"    EXPECT_EQ({expr}, {val});")
            continue
        m_state = _THEN_STATE_RE.match(line)
        if m_state:
            state = m_state.group("state")
            then_lines.append(
                f"    EXPECT_EQ({harness.state_member}, {harness.state_enum}::{state});"
            )
            continue
        if line.lower().startswith("then:"):
            then_lines.append(f"    // {line}")
        else:
            then_lines.append(f"    // {line}")

    return given_lines, when_lines, then_lines, sorted(set(unmapped))


def _assemble_test_body(
    *,
    test_name: str,
    given_lines: list[str],
    when_lines: list[str],
    then_lines: list[str],
    harness: GTestHarnessConfig,
    unmapped: list[str],
    logic_only: bool,
) -> str:
    body: list[str] = [f"TEST_F({harness.fixture_class}, {test_name}) {{"]
    body.append("    // Given")
    if given_lines:
        body.extend(given_lines)
    elif logic_only:
        body.append(f"    // TODO: set inputs via {harness.inputs_member}")
    else:
        body.append("    // (no Given lines materialized)")
    body.append("")
    body.append("    // When")
    if when_lines:
        body.extend(when_lines)
    elif logic_only:
        body.append(
            f"    {harness.state_member} = {harness.evaluate_fn}("
            f"{harness.state_member}, {harness.inputs_member}, {harness.outputs_member});"
        )
    else:
        body.append(f"    {harness.advance_time_fn}(0U);")
    body.append("")
    body.append("    // Then")
    if then_lines:
        body.extend(then_lines)
    elif logic_only:
        body.append("    // TODO: add EXPECT_* assertions from spec Then lines")
    else:
        body.append("    // (no Then lines materialized)")
    for sig in unmapped:
        body.append(f"    // TODO(unmapped): {sig}")
    body.append("}")
    return "\n".join(body)


def build_gtest_skeleton(
    *,
    candidate: dict[str, Any] | None = None,
    logic_block: dict[str, Any] | None = None,
    variable_map: dict[str, str] | None = None,
    harness: GTestHarnessConfig | None = None,
    definition_lookup: dict[str, list[dict[str, Any]]] | None = None,
    given_when_override: str | None = None,
    then_override: str | None = None,
) -> GTestDraft:
    h = harness or GTestHarnessConfig()
    vmap = dict(variable_map or {})
    logic_only = candidate is None and logic_block is not None

    gw_text = ""
    th_text = ""
    source_kind = "logic" if logic_only else "candidate"
    source_id = ""
    test_name = "GeneratedTest"

    if candidate:
        source_id = str(candidate.get("id") or "")
        event = str(candidate.get("event") or candidate.get("test_function") or "Test")
        test_name = sanitize_test_name(source_id, event)
        gw_text = (
            given_when_override
            if given_when_override is not None
            else materialize_expected_input(candidate, definition_lookup)
        )
        th_text = (
            then_override
            if then_override is not None
            else materialize_expected_output(candidate)
        )
        gw_text = _supplement_when_text(candidate, gw_text or "")
        if not logic_block:
            logic_id = _candidate_logic_id(candidate)
            if logic_id and logic_block is None:
                pass
    if logic_block and not source_id:
        source_id = str(logic_block.get("logic_id") or logic_block.get("id") or "")
        control = str(logic_block.get("control_name") or "Logic")
        test_name = sanitize_test_name(source_id or "LOGIC", control)

    spec_comments = _build_spec_comments(
        candidate=candidate,
        logic_block=logic_block,
        given_when_text=gw_text,
        then_text=th_text,
    )
    given_lines, when_lines, then_lines, unmapped = _parse_triplet_lines(
        gw_text,
        th_text,
        variable_map=vmap,
        harness=h,
    )
    code_body = _assemble_test_body(
        test_name=test_name,
        given_lines=given_lines,
        when_lines=when_lines,
        then_lines=then_lines,
        harness=h,
        unmapped=unmapped,
        logic_only=logic_only,
    )
    header = h.include_header.strip()
    full = "\n".join(part for part in (header, spec_comments, "", code_body) if part)
    return GTestDraft(
        source_kind=source_kind,
        source_id=source_id,
        test_name=test_name,
        spec_comment_block=spec_comments,
        code_body=code_body,
        full_snippet=full,
        unmapped_signals=unmapped,
    )


def compose_full_translation_unit(
    drafts: list[GTestDraft],
    harness: GTestHarnessConfig | None = None,
) -> str:
    h = harness or GTestHarnessConfig()
    parts = [
        h.include_header.strip(),
        "",
        f"// Generated by ALEX — {len(drafts)} test(s)",
        "",
    ]
    for draft in drafts:
        parts.append(draft.spec_comment_block)
        parts.append("")
        parts.append(draft.code_body)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
