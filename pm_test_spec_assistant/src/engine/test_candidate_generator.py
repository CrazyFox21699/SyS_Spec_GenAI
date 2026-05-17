"""Generate test scenario candidates (not final approval)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.footnote_conditional import given_lines_for_footnote_rule, parse_conditional_footnote
from src.engine.term_role_classifier import classify_term


def _flatten_signals_from_tree(tree: dict[str, Any]) -> list[str]:
    out: list[str] = []
    t = tree.get("type")
    if t == "signal_condition":
        out.append(str(tree.get("signal", "")))
    for ch in tree.get("children") or []:
        if isinstance(ch, dict):
            out.extend(_flatten_signals_from_tree(ch))
    return [x for x in out if x]


def generate_candidates(
    transitions: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    timing_notes: list[dict[str, Any]],
    *,
    condition_definitions: list[dict[str, Any]] | None = None,
    footnote_definitions: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns (candidates, traceability_rows).
    Strategy: positive path + negate timing + negate primary signal when detectable.
    """
    candidates: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    sig_by_name = {s["name"]: s for s in signals if s.get("name")}
    def_map = _definition_map(condition_definitions or [])
    fn_rules = _footnote_rules_index(footnote_definitions or [])

    n = 0
    for t in transitions:
        raw = str(t.get("raw_condition", ""))
        tree = parse_condition_tree(raw)
        tr_id = t.get("id")
        from_st = t.get("from_state")
        to_st = t.get("to_state")

        n += 1
        cid = f"TC_PM_{n:03d}"
        candidates.append(
            {
                "id": cid,
                "status": "candidate",
                "test_function": "Power mode / state behavior",
                "event": str(t.get("event") or "unspecified_event"),
                "use_case_description": f"Positive path for transition {tr_id} ({from_st} -> {to_st})",
                "precondition": [{"current_state": from_st}],
                "operation": {
                    "given": _given_from_tree(
                        tree,
                        raw,
                        footnote_rules=fn_rules,
                        definition_by_name=def_map,
                    ),
                    "when": _when_from_tree(tree, timing_notes),
                },
                "expectation": _expectation_from_transition(t, to_st, tree=tree),
                "traceability": {
                    "transition": tr_id,
                    "to_state": to_st,
                    "from_state": from_st,
                    "source_evidence": [t.get("source")],
                },
                "why_recommended": [
                    "Covers stated transition row from behavior workbook",
                    "Exercises combined guard expression",
                ],
                "confidence": "medium",
                "review_required": True,
                "source": "deterministic_candidate_generator",
            }
        )
        trace_rows.append(
            {
                "test_candidate_id": cid,
                "signals": _flatten_signals_from_tree(tree) or [s.get("name") for s in signals[:3]],
                "conditions": [raw] if raw else [],
                "states": {"from": from_st, "to": to_st},
                "outputs": t.get("outputs") or [],
                "source_evidence": [
                    {
                        "file": (t.get("source") or {}).get("file"),
                        "location": f"sheet {(t.get('source') or {}).get('sheet')} row {(t.get('source') or {}).get('row_hint')}",
                        "evidence": raw[:500],
                    }
                ],
                "confidence": "medium",
                "review_required": True,
            }
        )

        # Timing not reached variant
        if timing_notes and any(tn.get("value_ms") for tn in timing_notes):
            tn0 = timing_notes[0]
            ms = tn0.get("value_ms")
            n += 1
            cid2 = f"TC_PM_{n:03d}"
            candidates.append(
                {
                    "id": cid2,
                    "status": "candidate",
                    "test_function": "Power mode / state behavior",
                    "event": "timing_boundary",
                    "use_case_description": f"Timing not yet satisfied (< {ms} ms) while other guards true",
                    "precondition": [{"current_state": from_st}],
                    "operation": {
                        "given": _given_from_tree(tree, raw),
                        "when": [{"timing": f"elapsed_time < {ms}ms"}],
                    },
                    "expectation": [{"description": "Transition/output must not fire early"}],
                    "traceability": {"transition": tr_id, "source_evidence": [t.get("source")]},
                    "why_recommended": ["Boundary before timing threshold"],
                    "confidence": "low",
                    "review_required": True,
                    "source": "deterministic_candidate_generator",
                }
            )

        # First signal toggle variant
        sigs = _flatten_signals_from_tree(tree)
        if sigs:
            primary = sigs[0]
            meta = sig_by_name.get(primary, {})
            vals = meta.get("values") or []
            alt = "0"
            for v in vals:
                rv = str(v.get("raw_value", ""))
                if rv and rv != "1":
                    alt = rv
                    break
            n += 1
            cid3 = f"TC_PM_{n:03d}"
            candidates.append(
                {
                    "id": cid3,
                    "status": "candidate",
                    "test_function": "Power mode / state behavior",
                    "event": "guard_false_signal",
                    "use_case_description": f"Negate primary guard signal {primary}",
                    "precondition": [{"current_state": from_st}],
                    "operation": {
                        "given": [{"signal": primary, "value": alt, "note": "invert primary guard"}],
                        "when": [{"description": "Hold other guards as appropriate"}],
                    },
                    "expectation": [{"description": "Transition must not occur while guard false"}],
                    "traceability": {"transition": tr_id, "source_evidence": [t.get("source")]},
                    "why_recommended": ["Mandatory condition false branch"],
                    "confidence": "low",
                    "review_required": True,
                    "source": "deterministic_candidate_generator",
                }
            )

    return candidates, trace_rows


def generate_negative_candidates_from_ast(
    logic_blocks: list[dict[str, Any]],
    *,
    start_index: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create NOT-branch review candidates for each NOT node in logic trees."""
    candidates: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    n = start_index

    def walk_not(node: dict[str, Any], block: dict[str, Any]) -> None:
        nonlocal n
        if node.get("type") == "NOT":
            ch = (node.get("children") or [{}])[0]
            nm = ch.get("name", "?")
            n += 1
            cid = f"TC_PM_{n:03d}"
            candidates.append(
                {
                    "id": cid,
                    "status": "candidate",
                    "test_function": "Power mode / shutoff control",
                    "event": "negative_not_branch",
                    "use_case_description": f"Verify behavior when NOT {nm} (negative guard for {block.get('name')})",
                    "precondition": [],
                    "operation": {
                        "given": [{"note": f"NOT {nm} active / guard false"}],
                        "when": [{"description": "Evaluate while NOT condition holds"}],
                    },
                    "expectation": [{"description": f"Must not satisfy {block.get('name')} permission", "review_note": "Refine"}],
                    "traceability": {"logic_block": block.get("id"), "source_evidence": [block.get("source")]},
                    "why_recommended": ["Mandatory NOT branch coverage", "negative_condition_review_required"],
                    "confidence": "low",
                    "review_required": True,
                    "review_status": "pending",
                    "source": "not_branch_generator",
                }
            )
            trace_rows.append(
                {
                    "test_candidate_id": cid,
                    "signals": [],
                    "conditions": [f"NOT {nm}"],
                    "states": {},
                    "outputs": [],
                    "source_evidence": [block.get("source")],
                    "confidence": "low",
                    "review_required": True,
                }
            )
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk_not(ch, block)

    for lb in logic_blocks:
        walk_not(lb.get("tree") or {}, lb)
    return candidates, trace_rows


def generate_candidates_from_resolved_blocks(
    resolved_blocks: list[dict[str, Any]],
    *,
    start_index: int = 0,
    max_expansion_factor: int = 32,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate TCs from gate-resolved logic blocks via MCDC path planner."""
    from src.engine.mcdc_planner import plan_test_paths

    candidates: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    n = start_index

    for rb in resolved_blocks:
        ctrl = str(rb.get("name") or "logic")
        raw_expr = str(rb.get("raw_expression") or "")
        gate = rb.get("gate_status", "needs_engineer")
        blocked = gate != "ready"

        path_specs, meta = plan_test_paths(
            rb, control_name=ctrl, max_expansion_factor=max_expansion_factor
        )
        if meta.get("aborted"):
            n += 1
            cid = f"TC_PM_{n:03d}"
            candidates.append(
                {
                    "id": cid,
                    "status": "blocked",
                    "test_function": "Power mode / control",
                    "event": f"evaluate_{ctrl}_aborted",
                    "use_case_description": meta.get("reason", "Logic too complex"),
                    "precondition": [],
                    "operation": {"given": [], "when": []},
                    "expectation": [],
                    "traceability": {"logic_block": rb.get("id"), "control_name": ctrl},
                    "review_status": "blocked",
                    "block_reason": meta.get("reason"),
                    "source": "mcdc_planner",
                }
            )
            continue

        if not path_specs and blocked:
            continue

        for ps in path_specs:
            n += 1
            cid = f"TC_PM_{n:03d}"
            given = _given_from_path_spec(ps, control_name=ctrl)
            label = ps.get("label", "path")
            candidates.append(
                {
                    "id": cid,
                    "status": "blocked" if blocked else "candidate",
                    "test_function": "Power mode / control",
                    "event": f"evaluate_{ctrl}_{label}",
                    "use_case_description": f"Verify {ctrl}=1 — path {label.replace('_', ' ')}",
                    "precondition": [],
                    "operation": {
                        "given": given,
                        "when": [{"description": "Evaluate control judgment"}],
                    },
                    "expectation": [{"signal": ctrl, "value": "1", "operator": "=="}],
                    "traceability": {
                        "logic_block": rb.get("id"),
                        "control_name": ctrl,
                        "logic_path": ps.get("path_id"),
                        "logic_branch": label,
                        "source_evidence": [rb.get("source")],
                    },
                    "why_recommended": ["MCDC/path planner", f"Path: {label}"],
                    "confidence": "medium" if not blocked else "low",
                    "review_required": True,
                    "review_status": "blocked" if blocked else "pending",
                    "source": "mcdc_planner",
                }
            )
            trace_rows.append(
                {
                    "test_candidate_id": cid,
                    "signals": [g.get("signal") for g in given if g.get("signal")],
                    "conditions": [raw_expr],
                    "states": {},
                    "outputs": [ctrl],
                    "source_evidence": [rb.get("source")],
                    "confidence": "medium",
                    "review_required": True,
                }
            )
    return candidates, trace_rows


def _given_from_path_spec(path_spec: dict[str, Any], *, control_name: str = "") -> list[dict[str, Any]]:
    given: list[dict[str, Any]] = []
    for item in path_spec.get("given_items") or []:
        if item.get("note"):
            given.append({"note": item["note"]})
            continue
        sig = str(item.get("signal") or "")
        if not sig or classify_term(sig, control_name=control_name) == "output_assertion":
            continue
        val = item.get("value")
        if val is None:
            continue
        given.append(
            {
                "signal": sig,
                "value": val,
                "operator": "!=" if item.get("negated") else "==",
                "negated": bool(item.get("negated")),
            }
        )
    return given


def generate_candidates_from_logic_blocks(
    logic_blocks: list[dict[str, Any]],
    *,
    start_index: int = 0,
    condition_definitions: list[dict[str, Any]] | None = None,
    footnote_definitions: list[dict[str, Any]] | None = None,
    resolved_logic_blocks: list[dict[str, Any]] | None = None,
    coverage_mode: str = "legacy",
    max_expansion_factor: int = 32,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if coverage_mode == "mcdc" and resolved_logic_blocks:
        return generate_candidates_from_resolved_blocks(
            resolved_logic_blocks,
            start_index=start_index,
            max_expansion_factor=max_expansion_factor,
        )
    candidates: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    n = start_index
    def_map = _definition_map(condition_definitions or [])
    fn_rules = _footnote_rules_index(footnote_definitions or [])
    for lb in logic_blocks:
        if lb.get("block_type") not in ("two_column_control", "permission", "transition"):
            continue
        blocked = (
            bool(lb.get("unresolved_refs"))
            or lb.get("parse_status") in ("failed", "partial")
            or not lb.get("can_generate_candidates", lb.get("parse_status") == "ok")
        )
        ctrl = str(lb.get("name") or "logic")
        tree = lb.get("tree") or parse_condition_tree(str(lb.get("raw_expression") or ""))
        raw_expr = str(lb.get("raw_expression") or "")

        branch_specs = _logic_block_branch_specs(
            tree,
            ctrl,
            footnote_rules=fn_rules,
            definition_by_name=def_map,
        )
        if not branch_specs:
            branch_specs = [
                {
                    "label": "default",
                    "given": _given_from_tree(
                        tree,
                        raw_expr,
                        control_name=ctrl,
                        footnote_rules=fn_rules,
                        definition_by_name=def_map,
                    ),
                }
            ]

        for spec in branch_specs:
            n += 1
            cid = f"TC_PM_{n:03d}"
            label = spec.get("label", "default")
            given = spec.get("given") or []
            candidates.append(
                {
                    "id": cid,
                    "status": "blocked" if blocked else "candidate",
                    "test_function": "Power mode / shutoff control",
                    "event": f"evaluate_{ctrl}_{label}",
                    "use_case_description": (
                        f"Verify {ctrl}=1 — path {str(label).replace('_', ' ')}"
                    ),
                    "precondition": spec.get("precondition") or [],
                    "operation": {
                        "given": given,
                        "when": [{"description": "Evaluate control judgment"}],
                    },
                    "expectation": [
                        {"signal": ctrl, "value": "1", "operator": "=="},
                    ],
                    "traceability": {
                        "logic_block": lb.get("id"),
                        "control_name": ctrl,
                        "logic_branch": label,
                        "source_evidence": [lb.get("source")],
                    },
                    "why_recommended": [
                        "Derived from two-column control table",
                        f"Branch: {label}",
                    ],
                    "confidence": "low" if blocked else "medium",
                    "review_required": True,
                    "review_status": "blocked" if blocked else "pending",
                    "block_reason": "Unresolved condition references" if blocked else None,
                    "source": "two_column_logic_block",
                }
            )
            trace_rows.append(
                {
                    "test_candidate_id": cid,
                    "signals": [],
                    "conditions": [raw_expr],
                    "states": {},
                    "outputs": [ctrl],
                    "source_evidence": [lb.get("source")],
                    "confidence": "low" if blocked else "medium",
                    "review_required": True,
                }
            )

        for ref in _footnote_refs_in_tree(tree):
            rule = fn_rules.get(ref)
            if not rule or rule.get("otherwise_value") is None:
                continue
            n += 1
            cid = f"TC_PM_{n:03d}"
            given_other = [
                {"note": line, "footnote_ref": ref}
                for line in given_lines_for_footnote_rule(rule, branch="otherwise")
            ]
            if not given_other:
                continue
            var = rule.get("variable", "Lost")
            candidates.append(
                {
                    "id": cid,
                    "status": "candidate",
                    "test_function": "Power mode / shutoff control",
                    "event": f"evaluate_{ctrl}_footnote_otherwise",
                    "use_case_description": (
                        f"Verify {ctrl} with footnote {ref} otherwise branch ({var})"
                    ),
                    "precondition": [],
                    "operation": {
                        "given": given_other,
                        "when": [{"description": "Evaluate control judgment"}],
                    },
                    "expectation": [{"signal": ctrl, "value": "1", "operator": "=="}],
                    "traceability": {
                        "logic_block": lb.get("id"),
                        "control_name": ctrl,
                        "footnote_ref": ref,
                        "source_evidence": [lb.get("source")],
                    },
                    "why_recommended": ["Footnote otherwise branch coverage"],
                    "confidence": "low",
                    "review_required": True,
                    "source": "two_column_logic_block",
                }
            )
    return candidates, trace_rows


def _footnote_refs_in_tree(tree: dict[str, Any]) -> set[str]:
    refs: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        for ref in node.get("footnotes") or []:
            refs.add(str(ref))
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return refs


def _logic_block_branch_specs(
    tree: dict[str, Any],
    control_name: str,
    *,
    footnote_rules: dict[str, dict[str, Any]] | None = None,
    definition_by_name: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One curated TC per top-level OR branch (e.g. OK path vs force path)."""
    if tree.get("type") != "OR":
        return []
    specs: list[dict[str, Any]] = []
    labels = ("ok_path", "force_path", "or_branch_3", "or_branch_4")
    for i, child in enumerate(tree.get("children") or []):
        if not isinstance(child, dict):
            continue
        label = labels[i] if i < len(labels) else f"or_branch_{i + 1}"
        specs.append(
            {
                "label": label,
                "given": _given_from_tree(
                    child,
                    "",
                    control_name=control_name,
                    footnote_rules=footnote_rules,
                    definition_by_name=definition_by_name,
                ),
            }
        )
    return specs


def generate_candidates_from_test_references(
    rows: list[dict[str, Any]],
    *,
    start_index: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build candidates from spec Given/When/Expected tables (Table 8 style)."""
    candidates: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    n = start_index
    for row in rows:
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        n += 1
        cid = rid if rid.upper().startswith("TC") else f"TC_PM_{n:03d}"
        given = str(row.get("given") or "")
        when = str(row.get("when") or "")
        expected = str(row.get("expected") or "")
        candidates.append(
            {
                "id": cid,
                "status": "candidate",
                "test_function": "Power mode / permission",
                "event": when or "evaluate_permission",
                "use_case_description": f"Spec reference {cid}: {given[:120]}",
                "precondition": [{"note": given}],
                "operation": {"given": [{"note": given}], "when": [{"description": when}]},
                "expectation": [{"description": expected}],
                "traceability": {"source_evidence": [row.get("source")]},
                "why_recommended": ["Imported from customer spec test reference table"],
                "confidence": "high",
                "review_required": True,
                "source": "spec_test_reference_table",
            }
        )
        trace_rows.append(
            {
                "test_candidate_id": cid,
                "signals": [],
                "conditions": [given],
                "states": {},
                "outputs": [expected] if expected else [],
                "source_evidence": [row.get("source")],
                "confidence": "high",
                "review_required": True,
            }
        )
    return candidates, trace_rows


def _when_from_tree(tree: dict[str, Any], timing_notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    when: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "timing_condition":
            raw = str(node.get("raw_text") or node.get("value") or "").strip()
            if raw:
                when.append({"timing": raw})
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    if not when and timing_notes:
        tn = timing_notes[0]
        ms = tn.get("value_ms")
        if ms is not None:
            when.append({"timing": f"elapsed_time >= {ms} ms"})
    return when


def _expectation_from_transition(
    transition: dict[str, Any],
    to_state: str | None,
    *,
    tree: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if tree:
        for sig, val in _output_assertions_from_tree(tree).items():
            rows.append({"signal": sig, "value": val, "operator": "=="})
    if to_state:
        rows.append({"description": f"System state = {to_state}"})
    for raw in transition.get("outputs") or []:
        text = str(raw).strip()
        if not text:
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text)
        if m:
            rows.append({"signal": m.group(1), "value": m.group(2).strip()})
        else:
            rows.append({"description": text})
    if not rows and to_state:
        rows.append({"description": f"System state = {to_state}"})
    return rows


def _normalize_condition_signal(name: str) -> tuple[str, str | None]:
    """Split `FORCE_SHUTOFF = 150` into signal name and embedded value."""
    raw = str(name or "").strip()
    raw = re.sub(r"\(\*\d+\)", "", raw).strip()
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw, None


def _default_value_for_signal(signal: str, *, definitions: dict[str, str] | None = None) -> str:
    """Legacy fallback only when comparator not present in token (prefer atom.value)."""
    sig, embedded = _normalize_condition_signal(signal)
    if embedded is not None:
        return embedded
    defn = (definitions or {}).get(sig, "") if definitions else ""
    m = re.search(
        r"(?:==|(?<![<>!=])=)\s*([-+]?\d+(?:\.\d+)?|TRUE|FALSE|ON|OFF)",
        defn,
        re.I,
    )
    if m:
        return m.group(1)
    upper = sig.upper()
    if upper.startswith("NOK_"):
        return "0"
    if upper.startswith("OK_"):
        return "1"
    return "1"


def _output_assertions_from_tree(tree: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node: dict[str, Any]) -> None:
        t = node.get("type")
        if t == "signal_condition":
            sig = str(node.get("signal") or "").strip()
            if sig and classify_term(sig) == "output_assertion":
                out[sig] = str(node.get("value") or "1")
        elif t == "condition":
            sig = str(node.get("name") or "").strip()
            if sig and classify_term(sig) == "output_assertion":
                out[sig] = _default_value_for_signal(sig)
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return out


def _given_from_tree(
    tree: dict[str, Any],
    raw_fallback: str,
    *,
    control_name: str = "",
    footnote_rules: dict[str, dict[str, Any]] | None = None,
    definition_by_name: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    given: list[dict[str, Any]] = []
    ctrl = str(control_name or "").strip()

    def walk(node: dict[str, Any]) -> None:
        t = node.get("type")
        if t == "signal_condition":
            sig = str(node.get("signal") or "").strip()
            if sig and classify_term(sig, control_name=ctrl) != "output_assertion":
                given.append(
                    {
                        "signal": sig,
                        "value": node.get("value"),
                        "operator": node.get("operator"),
                    }
                )
        elif t == "condition":
            atom = node.get("atom") or {}
            raw_name = str(node.get("name") or "").strip()
            sig = str(atom.get("signal") or "").strip() or _normalize_condition_signal(raw_name)[0]
            embedded = atom.get("value")
            if embedded is None:
                _, embedded = _normalize_condition_signal(raw_name)
            if sig and classify_term(sig, control_name=ctrl) != "output_assertion":
                given.append(
                    {
                        "signal": sig,
                        "value": embedded
                        if embedded is not None
                        else _default_value_for_signal(sig, definitions=definition_by_name),
                        "operator": "!=" if atom.get("negated") else "==",
                        "negated": bool(atom.get("negated")),
                    }
                )
            for ref in node.get("footnotes") or []:
                rule = (footnote_rules or {}).get(str(ref))
                if rule:
                    for line in given_lines_for_footnote_rule(rule, branch="when"):
                        given.append({"note": line, "footnote_ref": ref})
        elif t == "timing_condition":
            given.append({"timing": node.get("raw_text") or node.get("value")})
        elif t == "NOT":
            for c in node.get("children") or []:
                if isinstance(c, dict) and c.get("type") == "condition":
                    catom = c.get("atom") or {}
                    sig = str(catom.get("signal") or c.get("name") or "").strip()
                    if sig:
                        val = catom.get("value")
                        if val is None:
                            val = _default_value_for_signal(sig, definitions=definition_by_name)
                        given.append(
                            {
                                "signal": sig,
                                "value": val,
                                "operator": "!=",
                                "negated": True,
                            }
                        )
                elif isinstance(c, dict):
                    walk(c)
        elif t in ("AND", "OR"):
            for c in node.get("children") or []:
                if isinstance(c, dict):
                    walk(c)
        elif t == "opaque":
            given.append({"note": node.get("raw_text")})

    walk(tree)
    if not given and raw_fallback:
        given.append({"note": raw_fallback, "parse_status": "unparsed"})
    return given


def _footnote_rules_index(footnote_definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for row in footnote_definitions:
        ref = str(row.get("ref") or "")
        body = str(row.get("definition") or row.get("raw_text") or "")
        parsed = parse_conditional_footnote(body)
        if parsed and ref:
            rules[ref] = parsed
    return rules


def _definition_map(definitions: list[dict[str, Any]]) -> dict[str, str]:
    return {str(d.get("name") or ""): str(d.get("definition") or "") for d in definitions if d.get("name")}
