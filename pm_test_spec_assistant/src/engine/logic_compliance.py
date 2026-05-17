"""Check workbook Given lines against logic evidence."""

from __future__ import annotations

import re
from typing import Any

from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.term_role_classifier import build_term_role_index


def _clean_signal_name(name: str) -> str:
    raw = re.sub(r"\(\*\d+\)", "", str(name or "")).strip()
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", raw)
    return m.group(1) if m else raw


def _subtree_for_logic_branch(tree: dict[str, Any], branch_label: str) -> dict[str, Any]:
    if not branch_label or tree.get("type") != "OR":
        return tree
    base_label = str(branch_label).split("_footnote_")[0].split("_mcdc_")[0].split("_guard_")[0]
    m = re.match(r"^branch_(\d+)$", base_label)
    children = [c for c in tree.get("children") or [] if isinstance(c, dict)]
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(children):
            return children[idx]
    labels = ("ok_path", "force_path", "or_branch_3", "or_branch_4")
    for i, child in enumerate(children):
        label = labels[i] if i < len(labels) else f"or_branch_{i + 1}"
        if label == branch_label or label == base_label:
            return child
    return tree


def _signals_in_tree(tree: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        t = node.get("type")
        if t == "signal_condition":
            sig = _clean_signal_name(str(node.get("signal") or ""))
            if sig:
                out.add(sig)
        elif t == "condition":
            sig = _clean_signal_name(str(node.get("name") or ""))
            if sig:
                out.add(sig)
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return out


def check_logic_compliance(
    candidate: dict[str, Any],
    bundle: dict[str, Any],
    *,
    expected_input: str = "",
) -> dict[str, Any]:
    """Return logic_comply: pass | partial | fail + missing_signals + misplaced_roles."""
    text = expected_input or ""
    given_sigs = {
        m.group(1).strip()
        for m in re.finditer(r"(?im)^\s*Given:\s*([A-Za-z_][A-Za-z0-9_.]*)", text)
    }
    roles = bundle.get("term_roles") or build_term_role_index(bundle)
    misplaced: list[str] = []
    for sig in given_sigs:
        role = (roles.get(sig) or roles.get(sig.upper()) or {}).get("role", "")
        if role == "output_assertion":
            misplaced.append(sig)

    trace = candidate.get("traceability") or {}
    transition_id = trace.get("transition")
    logic_block_id = trace.get("logic_block")
    expected: set[str] = set()

    if transition_id:
        for t in bundle.get("transitions") or []:
            if t.get("id") == transition_id:
                raw = str(t.get("raw_condition") or "")
                tree = parse_condition_tree(raw)
                expected |= _signals_in_tree(tree)
                break
    elif logic_block_id:
        branch = str(trace.get("logic_branch") or "")
        for lb in bundle.get("logic_blocks") or []:
            if lb.get("id") == logic_block_id:
                tree = lb.get("tree") or parse_condition_tree(str(lb.get("raw_expression") or ""))
                if branch:
                    tree = _subtree_for_logic_branch(tree, branch)
                expected |= _signals_in_tree(tree)
                ctrl = str(lb.get("name") or "")
                if ctrl:
                    expected.discard(ctrl)
                break

    missing = sorted(expected - given_sigs) if expected else []
    if misplaced:
        status = "fail"
    elif missing:
        status = "partial"
    else:
        status = "pass" if expected or given_sigs else "partial"

    return {
        "logic_comply": status,
        "missing_signals": missing[:12],
        "misplaced_in_given": misplaced,
        "expected_signals": sorted(expected)[:20],
    }
