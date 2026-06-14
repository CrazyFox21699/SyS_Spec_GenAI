"""Deterministic logic coverage model — no AI, built from existing parsed bundle data.

Produces one coverage record per logic group with:
- source table rows (resolved/unresolved status)
- OR-split branches (AND stays in same branch, NOT preserved with negation)
- suggested_testcase rows for auto-generatable branches
"""

from __future__ import annotations

import re
from typing import Any

_TERM_RE = re.compile(r"\b[A-Z][A-Z0-9_]+\b")
_GATE_TYPES = frozenset({"AND", "OR", "NOT"})
_PURE_GATES = frozenset({"AND", "OR"})          # cells that are structural gates only
_GATE_ONLY_TOKENS = frozenset({"AND", "OR", "NOT"})  # standalone tokens, not leaf conditions
_LEAF_TYPES = frozenset({
    "condition",
    "signal_condition",
    "boolean_predicate",
    "timing_condition",
    "edge_event",
})


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _sanitize_name(name: str) -> str:
    """Sanitize a control name to uppercase alphanumeric + underscore for ID use."""
    sanitized = re.sub(r"[^A-Z0-9]", "_", str(name or "").upper().strip())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized[:20]


def _gate_label(detected_type: str) -> str:
    t = str(detected_type or "").strip().upper()
    return t if t in _GATE_TYPES else ""


# ---------------------------------------------------------------------------
# Atom extraction
# ---------------------------------------------------------------------------

def _atom_from_leaf(node: dict[str, Any], negated: bool) -> dict[str, Any] | None:
    t = node.get("type", "")
    if t in ("condition", "edge_event"):
        inner = node.get("atom") or {}
        signal = str(inner.get("signal") or node.get("name") or node.get("raw_text") or "").strip()
        if not signal:
            return None
        inner_neg = bool(inner.get("negated", False))
        return {
            "signal": signal,
            "value": str(inner.get("value") or "1"),
            "operator": str(inner.get("operator") or "=="),
            "negated": negated != inner_neg,
        }
    if t in ("signal_condition", "boolean_predicate", "timing_condition"):
        signal = str(node.get("signal") or node.get("name") or "").strip()
        if not signal:
            return None
        return {
            "signal": signal,
            "value": str(node.get("value") or "1"),
            "operator": str(node.get("operator") or "=="),
            "negated": negated,
        }
    return None


def _atoms_from_subtree(node: dict[str, Any], negated: bool = False) -> list[dict[str, Any]]:
    """Recursively collect leaf atoms; OR/AND recurse flat; NOT flips negation."""
    t = node.get("type", "")
    if t in _LEAF_TYPES:
        atom = _atom_from_leaf(node, negated)
        return [atom] if atom else []
    if t == "NOT":
        result: list[dict[str, Any]] = []
        for ch in node.get("children") or []:
            result.extend(_atoms_from_subtree(ch, not negated))
        return result
    if t in ("AND", "OR"):
        result = []
        for ch in node.get("children") or []:
            result.extend(_atoms_from_subtree(ch, negated))
        return result
    # opaque / unknown — try raw_text for an ALL_CAPS signal name
    text = str(node.get("name") or node.get("raw_text") or "").strip()
    if text:
        terms = _TERM_RE.findall(text)
        if terms and terms[0] not in _GATE_TYPES:
            return [{"signal": terms[0], "value": "1", "operator": "==", "negated": negated}]
    return []


def _dedupe_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in atoms:
        sig = str(a.get("signal") or "")
        if sig and sig not in seen:
            seen.add(sig)
            out.append(a)
    return out or atoms


# ---------------------------------------------------------------------------
# Condition string helpers
# ---------------------------------------------------------------------------

def _atom_to_condition_str(atom: dict[str, Any]) -> str:
    sig = str(atom.get("signal") or "")
    op = str(atom.get("operator") or "==")
    val = str(atom.get("value") or "1")
    if atom.get("negated"):
        return f"NOT {sig}"
    if op in ("==", "=") and val in ("1", "TRUE", "true"):
        return sig
    return f"{sig} {op} {val}"


def _atom_to_input_line(atom: dict[str, Any]) -> str:
    sig = str(atom.get("signal") or "")
    op = str(atom.get("operator") or "==")
    val = str(atom.get("value") or "1")
    if atom.get("negated"):
        return f"{sig} = 0"
    if op in ("==", "="):
        return f"{sig} = {val}"
    return f"{sig} {op} {val}"


# ---------------------------------------------------------------------------
# Generic boolean planner
# ---------------------------------------------------------------------------

_MAX_TRUE_BRANCHES = 20  # combinatorial explosion guard


def _atom_to_bool_str(atom: dict[str, Any]) -> str:
    """Format atom as 'SIG = TRUE/FALSE' for abnormal branch display."""
    sig = str(atom.get("signal") or "")
    op = str(atom.get("operator") or "==")
    val = str(atom.get("value") or "1")
    if atom.get("negated"):
        if op in ("==", "=") and val in ("1", "TRUE", "true"):
            return f"{sig} = FALSE"
        return f"NOT ({sig} {op} {val})"
    if op in ("==", "=") and val in ("1", "TRUE", "true"):
        return f"{sig} = TRUE"
    return f"{sig} {op} {val}"


def _true_atoms(node: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Return list of atom-sets where each set is a minimal TRUE scenario.

    AND: cartesian product of children's TRUE branches.
    OR: union of children's TRUE branches.
    NOT: invert atoms of child.
    leaf: single atom-set.
    """
    if not node:
        return []
    t = node.get("type", "")
    if t == "empty":
        return []
    if t == "AND":
        children = [c for c in (node.get("children") or []) if isinstance(c, dict) and c.get("type") != "empty"]
        if not children:
            return []
        result: list[list[dict[str, Any]]] = [[]]
        for child in children:
            child_sets = _true_atoms(child)
            if not child_sets:
                return []
            new_result = [a + b for a in result for b in child_sets]
            if len(new_result) > _MAX_TRUE_BRANCHES:
                new_result = new_result[:_MAX_TRUE_BRANCHES]
            result = new_result
        return result
    if t == "OR":
        children = [c for c in (node.get("children") or []) if isinstance(c, dict) and c.get("type") != "empty"]
        result = []
        for child in children:
            result.extend(_true_atoms(child))
            if len(result) > _MAX_TRUE_BRANCHES:
                return result[:_MAX_TRUE_BRANCHES]
        return result
    if t == "NOT":
        ch_list = [c for c in (node.get("children") or []) if isinstance(c, dict)]
        if not ch_list:
            return []
        atoms = _atoms_from_subtree(ch_list[0], negated=True)
        return [atoms] if atoms else []
    atoms = _atoms_from_subtree(node, negated=False)
    return [atoms] if atoms else []


def _false_atoms(node: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Return list of atom-sets where each set is a minimal FALSE scenario.

    AND: one false branch per child (each child's simplest false set).
    OR: all children false together (combined into one branch).
    NOT(A): A must be TRUE → atoms with normal polarity.
    leaf: invert atom polarity.
    """
    if not node:
        return []
    t = node.get("type", "")
    if t == "empty":
        return []
    if t == "AND":
        children = [c for c in (node.get("children") or []) if isinstance(c, dict) and c.get("type") != "empty"]
        result: list[list[dict[str, Any]]] = []
        for child in children:
            result.extend(_false_atoms(child))
        return result
    if t == "OR":
        children = [c for c in (node.get("children") or []) if isinstance(c, dict) and c.get("type") != "empty"]
        combined: list[dict[str, Any]] = []
        for child in children:
            child_false = _false_atoms(child)
            if not child_false:
                return []
            combined.extend(child_false[0])
        return [combined] if combined else []
    if t == "NOT":
        ch_list = [c for c in (node.get("children") or []) if isinstance(c, dict)]
        if not ch_list:
            return []
        atoms = _atoms_from_subtree(ch_list[0], negated=False)
        return [atoms] if atoms else []
    atoms = _atoms_from_subtree(node, negated=False)
    if atoms:
        return [[{**a, "negated": not a.get("negated", False)} for a in atoms]]
    return []


def _plan_branches(
    tree: dict[str, Any],
    control_name: str,
    unresolved: frozenset[str],
) -> list[dict[str, Any]]:
    """Generic N/A planner: produces normal (TRUE) + abnormal (FALSE) branches from AST."""
    if not tree or tree.get("type") in ("empty", None):
        return []

    ctrl_slug = _sanitize_name(control_name)
    branches: list[dict[str, Any]] = []

    def _make_branch(idx: int, btype: str, raw_atoms: list[dict[str, Any]]) -> dict[str, Any]:
        atoms = _dedupe_atoms(raw_atoms)
        unresolved_terms = [
            str(a.get("signal") or "")
            for a in atoms
            if str(a.get("signal") or "") in unresolved
        ]
        auto_gen = bool(atoms) and not unresolved_terms
        bid = f"N{idx:02d}" if btype == "normal" else f"A{idx:02d}"
        cid = f"TC_{ctrl_slug}_{bid}"

        if btype == "normal":
            required_conditions = [_atom_to_condition_str(a) for a in atoms]
            false_cond: str | None = None
            expected_result = "TRUE"
            path_summary = " AND ".join(required_conditions) or f"branch {idx}"
            expected_input = "; ".join(_atom_to_input_line(a) for a in atoms)
            expected_output = f"{control_name} = TRUE"
            event = f"{bid} - {path_summary[:100]}"
        else:
            required_conditions = []
            parts = [_atom_to_bool_str(a) for a in atoms]
            false_cond = "; ".join(parts)
            expected_result = "FALSE"
            path_summary = false_cond or f"abnormal {idx}"
            expected_input = false_cond
            expected_output = f"{control_name} = FALSE"
            event = f"{bid} - {false_cond[:100]}"

        return {
            "branch_id": bid,
            "branch_type": btype,
            "path_summary": path_summary,
            "expected_result": expected_result,
            "required_conditions": required_conditions,
            "false_condition": false_cond,
            "unresolved_terms": unresolved_terms,
            "auto_generatable": auto_gen,
            "suggested_testcase": {
                "candidate_id": cid,
                "test_function": control_name,
                "test_group": control_name,
                "event": event,
                "use_case": "Logic branch coverage",
                "operation": "",
                "expected_input": expected_input,
                "expected_output": expected_output,
            } if auto_gen else None,
        }

    for n_idx, atom_set in enumerate(_true_atoms(tree), start=1):
        branches.append(_make_branch(n_idx, "normal", atom_set))

    for a_idx, atom_set in enumerate(_false_atoms(tree), start=1):
        branches.append(_make_branch(a_idx, "abnormal", atom_set))

    return branches


# ---------------------------------------------------------------------------
# Branch builder
# ---------------------------------------------------------------------------

def _build_branches(
    tree: dict[str, Any],
    control_name: str,
    unresolved: frozenset[str],
) -> list[dict[str, Any]]:
    """Delegates to _plan_branches for generic N/A boolean branch planning."""
    return _plan_branches(tree, control_name, unresolved)


# ---------------------------------------------------------------------------
# Source row classification
# ---------------------------------------------------------------------------

def _resolved_status(raw_condition: str, unresolved: frozenset[str]) -> str:
    terms = set(_TERM_RE.findall(str(raw_condition or "")))
    if not terms:
        return "no_terms"
    if terms & unresolved:
        return "unresolved"
    return "resolved"


# ---------------------------------------------------------------------------
# Table-row fallback builders (for groups with no parse tree)
# ---------------------------------------------------------------------------

def _tree_lines_from_table_rows(table_rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in table_rows:
        ctrl = str(row.get("control") or "").strip()
        cond = str(row.get("raw_condition") or "").strip()
        depth = int(row.get("depth") or 0)
        indent = "  " * depth
        if cond:
            label = f"{ctrl}: {cond}" if ctrl else cond
            lines.append(f"{indent}{label}")
    return lines


def _branches_from_table_rows(
    control_name: str,
    table_rows: list[dict[str, Any]],
    unresolved: frozenset[str],
) -> list[dict[str, Any]]:
    branches: list[dict[str, Any]] = []
    ctrl_slug = _sanitize_name(control_name)
    idx = 0
    for row in table_rows:
        cond = str(row.get("raw_condition") or "").strip()
        if not cond or cond.upper() in _GATE_ONLY_TOKENS:
            continue
        idx += 1
        terms = _TERM_RE.findall(cond)
        unresolved_terms = [t for t in terms if t in unresolved]
        auto_gen = bool(terms) and not unresolved_terms
        suggested: dict[str, Any] | None = (
            {
                "candidate_id": f"TC_{ctrl_slug}_N{idx:02d}",
                "test_function": control_name,
                "test_group": control_name,
                "event": f"N{idx:02d} - {cond[:100]}",
                "use_case": "Logic branch coverage",
                "operation": "",
                "expected_input": cond,
                "expected_output": f"{control_name} = TRUE",
            }
            if auto_gen
            else None
        )
        branches.append({
            "branch_id": f"N{idx:02d}",
            "branch_type": "normal",
            "path_summary": cond,
            "expected_result": "TRUE",
            "required_conditions": [cond],
            "false_condition": None,
            "unresolved_terms": unresolved_terms,
            "auto_generatable": auto_gen,
            "suggested_testcase": suggested,
        })
    return branches


# ---------------------------------------------------------------------------
# Visual-source helpers (multi-column table fallback)
# ---------------------------------------------------------------------------

def _parse_visual_row(
    control_name: str, row: dict[str, Any]
) -> tuple[list[str], str]:
    """Parse one visual_source row into (gate_path, leaf_text).

    Multi-column tables store each row as cells=[ctrl, gate, gate, ..., leaf].
    Returns the list of gate keywords and the leaf condition string.
    Returns ([], "") for gate-only rows.
    """
    cells = [str(c or "").strip() for c in row.get("cells") or []]
    if not cells:
        return [], ""
    # Skip leading control-name cell
    start = 1 if cells[0].upper() == control_name.upper() else 0
    remaining = cells[start:]

    gate_path: list[str] = []
    leaf = ""
    for cell in remaining:
        if not leaf and cell.upper() in _PURE_GATES:
            gate_path.append(cell.upper())
        elif cell:
            leaf = cell
            break

    return gate_path, leaf


def _visual_source_has_leaf_conditions(
    control_name: str, visual_source: dict[str, Any]
) -> bool:
    """True if at least one row has a non-gate leaf condition."""
    for row in visual_source.get("rows") or []:
        _, leaf = _parse_visual_row(control_name, row)
        if leaf and leaf.upper() not in _GATE_ONLY_TOKENS:
            return True
    return False


def _is_bad_tree_lines(lines: list[str], control_name: str) -> bool:
    """Detect the 'CONTROL: AND' repeated pattern that carries no real content."""
    if not lines:
        return True
    ctrl_lower = control_name.lower()
    bad = 0
    total = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        total += 1
        if ":" in stripped:
            lhs, _, rhs = stripped.lower().partition(":")
            if lhs.strip() == ctrl_lower and rhs.strip() in {"and", "or", "not", ""}:
                bad += 1
    return total > 0 and bad >= max(1, total * 0.5)


def _tree_lines_from_visual_source(
    control_name: str, visual_source: dict[str, Any]
) -> list[str]:
    """Build a readable indented hierarchy from multi-column visual_source rows."""
    visual_rows = visual_source.get("rows") or []
    if not visual_rows:
        return []

    lines: list[str] = [control_name]
    prev_gates: list[str] = []

    for row in visual_rows:
        gate_path, leaf = _parse_visual_row(control_name, row)

        # Emit any new or changed gate levels
        for i, gate in enumerate(gate_path):
            prev_at_i = prev_gates[i] if i < len(prev_gates) else None
            if prev_at_i != gate:
                lines.append("  " * i + gate)
                prev_gates = prev_gates[:i] + [gate]  # invalidate deeper levels

        if leaf:
            lines.append("  " * len(gate_path) + leaf)

    return lines


def _false_input_for_leaf(leaf: str) -> str:
    """For an abnormal branch, compute the expected_input when a leaf condition is false."""
    stripped = leaf.strip()
    if stripped.upper().startswith("NOT "):
        # NOT COND → false means COND is present/true
        sig = _TERM_RE.search(stripped[4:])
        return f"{sig.group(0) if sig else stripped[4:]} = TRUE"
    sig = _TERM_RE.search(stripped)
    return f"{sig.group(0) if sig else stripped} = FALSE"


def _build_normal_abnormal_from_visual_source(
    control_name: str,
    visual_source: dict[str, Any],
    unresolved: frozenset[str],
) -> list[dict[str, Any]]:
    """Build minimal normal + abnormal branch coverage from multi-column visual_source.

    Normal branches:  mandatory_leaves + each OR alternative → control = TRUE
    Abnormal branches: each mandatory false, all OR alts false → control = FALSE
    """
    visual_rows = visual_source.get("rows") or []
    if not visual_rows:
        return []

    ctrl_slug = _sanitize_name(control_name)

    # Parse all leaf rows
    parsed: list[tuple[list[str], str, int]] = []
    for idx, row in enumerate(visual_rows):
        gate_path, leaf = _parse_visual_row(control_name, row)
        if leaf and leaf.upper() not in _GATE_ONLY_TOKENS:
            parsed.append((gate_path, leaf, int(row.get("row_no") or idx)))

    if not parsed:
        return []

    # Separate mandatory (AND-only) from OR alternatives
    shared_ordered: list[str] = []
    seen_shared: set[str] = set()
    or_alts: list[str] = []

    for gate_path, leaf, _row_no in sorted(parsed, key=lambda x: x[2]):
        if "OR" in gate_path:
            or_alts.append(leaf)
        else:
            if leaf not in seen_shared:
                seen_shared.add(leaf)
                shared_ordered.append(leaf)

    def _check_unresolved(leaves: list[str]) -> list[str]:
        terms: set[str] = set()
        for lf in leaves:
            for t in _TERM_RE.findall(lf.upper()):
                if t not in _GATE_TYPES:
                    terms.add(t)
        return sorted(t for t in terms if t in unresolved)

    branches: list[dict[str, Any]] = []
    n_idx = 0
    a_idx = 0

    # Normal branches
    if or_alts:
        for alt in or_alts:
            n_idx += 1
            normal_leaves = shared_ordered + [alt]
            unres = _check_unresolved(normal_leaves)
            auto_gen = not unres
            cid = f"TC_{ctrl_slug}_N{n_idx:02d}"
            expected_input = "; ".join(normal_leaves)
            path_summary = " AND ".join(normal_leaves)
            event = f"N{n_idx:02d} - normal path via {alt[:60]}"
            branches.append({
                "branch_id": f"N{n_idx:02d}",
                "branch_type": "normal",
                "path_summary": path_summary,
                "expected_result": "TRUE",
                "required_conditions": normal_leaves,
                "false_condition": None,
                "unresolved_terms": unres,
                "auto_generatable": auto_gen,
                "suggested_testcase": {
                    "candidate_id": cid,
                    "test_function": control_name,
                    "test_group": control_name,
                    "event": event,
                    "use_case": "Logic branch coverage",
                    "operation": "",
                    "expected_input": expected_input,
                    "expected_output": f"{control_name} = TRUE",
                } if auto_gen else None,
            })
    elif shared_ordered:
        n_idx += 1
        unres = _check_unresolved(shared_ordered)
        auto_gen = not unres
        cid = f"TC_{ctrl_slug}_N{n_idx:02d}"
        expected_input = "; ".join(shared_ordered)
        path_summary = " AND ".join(shared_ordered)
        branches.append({
            "branch_id": f"N{n_idx:02d}",
            "branch_type": "normal",
            "path_summary": path_summary,
            "expected_result": "TRUE",
            "required_conditions": shared_ordered,
            "false_condition": None,
            "unresolved_terms": unres,
            "auto_generatable": auto_gen,
            "suggested_testcase": {
                "candidate_id": cid,
                "test_function": control_name,
                "test_group": control_name,
                "event": f"N{n_idx:02d} - all conditions met",
                "use_case": "Logic branch coverage",
                "operation": "",
                "expected_input": expected_input,
                "expected_output": f"{control_name} = TRUE",
            } if auto_gen else None,
        })

    # Abnormal: each mandatory leaf false
    for mandatory in shared_ordered:
        a_idx += 1
        unres = _check_unresolved([mandatory])
        auto_gen = not unres
        cid = f"TC_{ctrl_slug}_A{a_idx:02d}"
        false_inp = _false_input_for_leaf(mandatory)
        event = f"A{a_idx:02d} - {false_inp}"
        branches.append({
            "branch_id": f"A{a_idx:02d}",
            "branch_type": "abnormal",
            "path_summary": false_inp,
            "expected_result": "FALSE",
            "required_conditions": [],
            "false_condition": mandatory,
            "unresolved_terms": unres,
            "auto_generatable": auto_gen,
            "suggested_testcase": {
                "candidate_id": cid,
                "test_function": control_name,
                "test_group": control_name,
                "event": event[:120],
                "use_case": "Logic branch coverage",
                "operation": "",
                "expected_input": false_inp,
                "expected_output": f"{control_name} = FALSE",
            } if auto_gen else None,
        })

    # Abnormal: all OR alternatives false
    if or_alts:
        a_idx += 1
        unres = _check_unresolved(or_alts)
        auto_gen = not unres
        cid = f"TC_{ctrl_slug}_A{a_idx:02d}"
        all_false_inp = "; ".join(_false_input_for_leaf(alt) for alt in or_alts)
        false_cond = "; ".join(or_alts)
        event = f"A{a_idx:02d} - all OR alternatives false"
        branches.append({
            "branch_id": f"A{a_idx:02d}",
            "branch_type": "abnormal",
            "path_summary": all_false_inp,
            "expected_result": "FALSE",
            "required_conditions": [],
            "false_condition": false_cond,
            "unresolved_terms": unres,
            "auto_generatable": auto_gen,
            "suggested_testcase": {
                "candidate_id": cid,
                "test_function": control_name,
                "test_group": control_name,
                "event": event,
                "use_case": "Logic branch coverage",
                "operation": "",
                "expected_input": all_false_inp,
                "expected_output": f"{control_name} = FALSE",
            } if auto_gen else None,
        })

    return branches


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_logic_coverage_item(item: dict[str, Any]) -> dict[str, Any]:
    """Build a coverage record for one logic_review_item dict."""
    logic_id = str(item.get("logic_id") or "")
    control_name = str(item.get("control_name") or logic_id)
    unresolved: frozenset[str] = frozenset(
        str(x) for x in (item.get("unresolved_refs") or [])
    )
    tree = item.get("tree_model") or {}
    table_rows = item.get("table_rows") or []
    visual_source = item.get("visual_source") or {}

    source_detected = [
        {
            "row_no": row.get("row_no"),
            "control": row.get("control") or control_name,
            "raw_condition": str(row.get("raw_condition") or ""),
            "normalized_condition": _normalize_ws(row.get("raw_condition") or ""),
            "depth": row.get("depth"),
            "gate": _gate_label(row.get("detected_type") or ""),
            "condition_type": str(row.get("detected_type") or ""),
            "resolved_status": _resolved_status(
                str(row.get("raw_condition") or ""), unresolved
            ),
        }
        for row in table_rows
    ]

    has_tree = bool(tree) and tree.get("type") not in ("empty", None)
    branches = _build_branches(tree, control_name, unresolved) if has_tree else []
    tree_lines = list(item.get("tree_lines") or [])
    source_structure_note = ""

    if not has_tree:
        if visual_source.get("rows") and _visual_source_has_leaf_conditions(control_name, visual_source):
            # Multi-column visual source with real leaf conditions — best fallback
            status = "needs_review"
            branches = _build_normal_abnormal_from_visual_source(control_name, visual_source, unresolved)
            tree_lines = _tree_lines_from_visual_source(control_name, visual_source)
            source_structure_note = "Source structure rebuilt from document table rows."
        elif table_rows:
            # Plain table_rows fallback — may only have gate keywords
            status = "needs_review"
            branches = _branches_from_table_rows(control_name, table_rows, unresolved)
            raw_lines = _tree_lines_from_table_rows(table_rows)
            if _is_bad_tree_lines(raw_lines, control_name):
                tree_lines = []
                source_structure_note = "Source structure unavailable — table rows contain only gate keywords."
            else:
                tree_lines = raw_lines
                source_structure_note = "Source structure rebuilt from raw table rows."
        else:
            status = "source_missing"
    elif unresolved:
        status = "unresolved"
    else:
        status = "ok"

    return {
        "logic_id": logic_id,
        "control_name": control_name,
        "status": status,
        "branch_count": len(branches),
        "unresolved_count": len(unresolved),
        "expression": str(item.get("expression") or item.get("raw_expression") or ""),
        "tree_lines": tree_lines,
        "source_detected": source_detected,
        "branches": branches,
        "source_structure_note": source_structure_note,
    }


_LOGIC_KINDS = frozenset({"logic_control", "logic", ""})


def build_logic_coverage_list(
    bundle: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build coverage records for all logic groups in a bundle.

    Deduplicates by normalized control_name (keeps first).
    Filters out non-logic items (alias tables, constant tables, etc.)
    """
    items = bundle.get("logic_review_items") or []
    raw_count = len(items)
    seen_names: set[str] = set()
    result: list[dict[str, Any]] = []
    dropped_dupe = 0
    dropped_non_logic = 0
    dropped_reasons: dict[str, str] = {}

    for item in items:
        name_key = str(item.get("control_name") or "").strip().upper()
        kind = str(item.get("control_kind") or "").strip().lower()

        if kind and kind not in _LOGIC_KINDS:
            dropped_non_logic += 1
            dropped_reasons[name_key or f"_unnamed_{dropped_non_logic}"] = f"non_logic_kind:{kind}"
            continue

        from_state = str(item.get("from_state") or "").strip()
        to_state = str(item.get("to_state") or "").strip()
        if from_state or to_state:
            dropped_non_logic += 1
            dropped_reasons[name_key or f"_state_{dropped_non_logic}"] = "state_transition"
            continue

        if name_key and name_key in seen_names:
            dropped_dupe += 1
            dropped_reasons[name_key] = "duplicate"
            continue

        if name_key:
            seen_names.add(name_key)
        result.append(build_logic_coverage_item(item))

    if diagnostics is not None:
        diagnostics["raw_group_count"] = raw_count
        diagnostics["deduped_group_count"] = len(result)
        diagnostics["dropped_duplicate_count"] = dropped_dupe
        diagnostics["dropped_non_logic_count"] = dropped_non_logic
        diagnostics["dropped_reasons_by_control"] = dropped_reasons

    return result
