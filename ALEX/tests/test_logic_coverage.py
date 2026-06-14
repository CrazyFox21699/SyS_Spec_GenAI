"""Tests for src/engine/logic_coverage.py — deterministic branch model."""

from __future__ import annotations

import pytest

from src.engine.logic_coverage import (
    _atoms_from_subtree,
    _build_branches,
    _is_bad_tree_lines,
    _resolved_status,
    build_logic_coverage_item,
    build_logic_coverage_list,
)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _cond(name: str, *, neg: bool = False) -> dict:
    """Minimal condition AST node."""
    return {
        "type": "condition",
        "name": name,
        "raw_text": name,
        "atom": {"signal": name, "value": "1", "operator": "==", "negated": neg},
    }


def _and(*children) -> dict:
    return {"type": "AND", "children": list(children)}


def _or(*children) -> dict:
    return {"type": "OR", "children": list(children)}


def _not(child) -> dict:
    return {"type": "NOT", "children": [child]}


def _signal_cond(sig: str, op: str = "==", val: str = "1") -> dict:
    return {"type": "signal_condition", "signal": sig, "operator": op, "value": val}


def _item(logic_id: str, tree: dict, *, unresolved=None, table_rows=None, visual_source=None) -> dict:
    d = {
        "logic_id": logic_id,
        "control_name": logic_id,
        "tree_model": tree,
        "unresolved_refs": list(unresolved or []),
        "table_rows": list(table_rows or []),
    }
    if visual_source is not None:
        d["visual_source"] = visual_source
    return d


def _vs(title: str, rows: list) -> dict:
    """Build a minimal visual_source dict for testing."""
    return {"kind": "logic_table", "title": title, "rows": rows}


def _vr(row_no: int, cells: list) -> dict:
    """Build a visual_source row dict."""
    return {"row_no": row_no, "cells": cells}


# ---------------------------------------------------------------------------
# _atoms_from_subtree
# ---------------------------------------------------------------------------

def test_atoms_single_condition():
    node = _cond("SIG_A")
    atoms = _atoms_from_subtree(node)
    assert len(atoms) == 1
    assert atoms[0]["signal"] == "SIG_A"
    assert atoms[0]["negated"] is False


def test_atoms_not_flips_negation():
    node = _not(_cond("SIG_B"))
    atoms = _atoms_from_subtree(node)
    assert len(atoms) == 1
    assert atoms[0]["signal"] == "SIG_B"
    assert atoms[0]["negated"] is True


def test_atoms_and_collects_all():
    node = _and(_cond("A"), _cond("B"), _cond("C"))
    atoms = _atoms_from_subtree(node)
    signals = [a["signal"] for a in atoms]
    assert "A" in signals
    assert "B" in signals
    assert "C" in signals


def test_atoms_or_collects_all_leaves():
    node = _or(_cond("X"), _cond("Y"))
    atoms = _atoms_from_subtree(node)
    assert {a["signal"] for a in atoms} == {"X", "Y"}


def test_atoms_signal_condition_node():
    node = _signal_cond("PWR_STATE", ">=", "2")
    atoms = _atoms_from_subtree(node)
    assert len(atoms) == 1
    assert atoms[0]["signal"] == "PWR_STATE"
    assert atoms[0]["operator"] == ">="
    assert atoms[0]["value"] == "2"


def test_atoms_not_double_negation():
    node = _not(_not(_cond("SIG_C")))
    atoms = _atoms_from_subtree(node)
    assert atoms[0]["negated"] is False


# ---------------------------------------------------------------------------
# _build_branches — single branch (AND / pure condition)
# ---------------------------------------------------------------------------

def test_single_and_branch():
    tree = _and(_cond("A"), _cond("B"))
    branches = _build_branches(tree, "CTRL", frozenset())
    assert len(branches) == 3  # N01 (normal) + A01 + A02 (abnormal per child)
    br = branches[0]
    assert br["branch_id"] == "N01"
    assert "A" in br["required_conditions"]
    assert "B" in br["required_conditions"]
    assert br["auto_generatable"] is True
    assert br["unresolved_terms"] == []
    assert br["suggested_testcase"] is not None


def test_single_condition_branch():
    tree = _cond("WMODE_CMD")
    branches = _build_branches(tree, "CTRL", frozenset())
    assert len(branches) == 2  # N01 (normal) + A01 (abnormal)
    assert branches[0]["auto_generatable"] is True


# ---------------------------------------------------------------------------
# _build_branches — OR split
# ---------------------------------------------------------------------------

def test_or_split_creates_two_branches():
    tree = _or(_cond("A"), _cond("B"))
    branches = _build_branches(tree, "CTRL", frozenset())
    assert len(branches) == 3  # N01, N02 (normal) + A01 (combined false)
    assert branches[0]["branch_id"] == "N01"
    assert branches[1]["branch_id"] == "N02"
    assert branches[0]["required_conditions"] == ["A"]
    assert branches[1]["required_conditions"] == ["B"]


def test_shutoff_like_or_split():
    """SHUTOFF_DECISION: OR of three AND sub-trees."""
    tree = _or(
        _and(_cond("WMODE_CMD"), _cond("PWR_STATE")),
        _and(_cond("EMERGENCY"), _cond("OVERRIDE")),
        _cond("FALLBACK"),
    )
    branches = _build_branches(tree, "SHUTOFF_DECISION", frozenset())
    assert len(branches) == 4  # N01, N02, N03 (normal) + A01 (combined OR false)
    branch_ids = [b["branch_id"] for b in branches]
    assert branch_ids[:3] == ["N01", "N02", "N03"]
    # First branch must include both AND conditions
    assert "WMODE_CMD" in branches[0]["required_conditions"]
    assert "PWR_STATE" in branches[0]["required_conditions"]
    # All auto-generatable (no unresolved)
    assert all(b["auto_generatable"] for b in branches)


def test_or_three_branches_all_auto():
    tree = _or(_cond("C1"), _cond("C2"), _cond("C3"))
    branches = _build_branches(tree, "X", frozenset())
    assert len(branches) == 4  # N01-N03 (normal) + A01 (all-false combined)
    assert all(b["auto_generatable"] for b in branches)


# ---------------------------------------------------------------------------
# _build_branches — unresolved refs block auto_generatable
# ---------------------------------------------------------------------------

def test_unresolved_ref_blocks_branch():
    tree = _or(_cond("KNOWN"), _cond("UNKNOWN_SIG"))
    branches = _build_branches(tree, "CTRL", frozenset({"UNKNOWN_SIG"}))
    # branch_1 = KNOWN → auto-generatable
    assert branches[0]["auto_generatable"] is True
    assert branches[0]["unresolved_terms"] == []
    # branch_2 = UNKNOWN_SIG → blocked
    assert branches[1]["auto_generatable"] is False
    assert "UNKNOWN_SIG" in branches[1]["unresolved_terms"]
    assert branches[1]["suggested_testcase"] is None


def test_fully_unresolved_or_split():
    tree = _or(_cond("MISS_A"), _cond("MISS_B"))
    branches = _build_branches(tree, "CTRL", frozenset({"MISS_A", "MISS_B"}))
    assert all(not b["auto_generatable"] for b in branches)


def test_and_branch_with_one_unresolved():
    """AND branch is blocked if any member is unresolved."""
    tree = _and(_cond("GOOD"), _cond("BAD"))
    branches = _build_branches(tree, "CTRL", frozenset({"BAD"}))
    assert len(branches) == 3  # N01 (blocked) + A01 (GOOD=F, auto) + A02 (BAD=F, blocked)
    assert branches[0]["auto_generatable"] is False
    assert "BAD" in branches[0]["unresolved_terms"]


# ---------------------------------------------------------------------------
# _build_branches — NOT
# ---------------------------------------------------------------------------

def test_not_condition_preserved():
    tree = _not(_cond("SIG"))
    branches = _build_branches(tree, "CTRL", frozenset())
    assert len(branches) == 2  # N01 (NOT SIG = normal) + A01 (SIG = TRUE = abnormal)
    conds = branches[0]["required_conditions"]
    assert conds == ["NOT SIG"]


def test_not_generates_zero_input_line():
    tree = _not(_cond("SIG"))
    branches = _build_branches(tree, "CTRL", frozenset())
    tc = branches[0]["suggested_testcase"]
    assert "SIG = 0" in tc["expected_input"]


# ---------------------------------------------------------------------------
# _build_branches — empty/no tree
# ---------------------------------------------------------------------------

def test_empty_tree_produces_no_branches():
    assert _build_branches({}, "X", frozenset()) == []
    assert _build_branches({"type": "empty"}, "X", frozenset()) == []
    assert _build_branches({"type": "empty", "children": []}, "X", frozenset()) == []


# ---------------------------------------------------------------------------
# _resolved_status
# ---------------------------------------------------------------------------

def test_resolved_status_no_terms():
    assert _resolved_status("", frozenset()) == "no_terms"
    assert _resolved_status("  ", frozenset()) == "no_terms"


def test_resolved_status_all_resolved():
    assert _resolved_status("SIG_A = 1", frozenset()) == "resolved"
    assert _resolved_status("SIG_A = 1", frozenset({"OTHER"})) == "resolved"


def test_resolved_status_unresolved_hit():
    assert _resolved_status("SIG_A = 1", frozenset({"SIG_A"})) == "unresolved"


# ---------------------------------------------------------------------------
# build_logic_coverage_item
# ---------------------------------------------------------------------------

def test_coverage_item_status_ok():
    item = _item(
        "CTRL",
        _and(_cond("SIG_A"), _cond("SIG_B")),
        table_rows=[{"row_no": 1, "control": "CTRL", "raw_condition": "SIG_A = 1", "depth": 0, "detected_type": "AND"}],
    )
    result = build_logic_coverage_item(item)
    assert result["logic_id"] == "CTRL"
    assert result["status"] == "ok"
    assert result["branch_count"] == 3  # N01 + A01 + A02 from AND(SIG_A, SIG_B)
    assert result["unresolved_count"] == 0
    assert len(result["source_detected"]) == 1
    assert result["source_detected"][0]["resolved_status"] == "resolved"
    assert result["source_detected"][0]["gate"] == "AND"


def test_coverage_item_status_needs_definition():
    item = _item("CTRL", _cond("MISS"), unresolved=["MISS"])
    result = build_logic_coverage_item(item)
    assert result["status"] == "unresolved"
    assert result["unresolved_count"] == 1


def test_coverage_item_status_no_tree():
    item = _item("CTRL", {})
    result = build_logic_coverage_item(item)
    assert result["status"] == "source_missing"
    assert result["branch_count"] == 0


def test_coverage_item_branch_count_for_or():
    tree = _or(_cond("A"), _cond("B"), _cond("C"))
    item = _item("CTRL", tree)
    result = build_logic_coverage_item(item)
    assert result["branch_count"] == 4  # N01-N03 + A01 (combined OR false)


def test_coverage_item_suggested_testcase_fields():
    tree = _and(_cond("SIG_IN"), _signal_cond("SIG_VAL", ">=", "5"))
    item = _item("MY_CTRL", tree)
    result = build_logic_coverage_item(item)
    tc = result["branches"][0]["suggested_testcase"]
    assert tc is not None
    assert tc["test_function"] == "MY_CTRL"
    assert tc["test_group"] == "MY_CTRL"
    assert "SIG_IN" in tc["expected_input"]
    assert "SIG_VAL" in tc["expected_input"]
    assert tc["expected_output"] == "MY_CTRL = TRUE"


def test_coverage_item_source_detected_gate_types():
    rows = [
        {"row_no": 1, "raw_condition": "A = 1", "depth": 0, "detected_type": "AND"},
        {"row_no": 2, "raw_condition": "B = 1", "depth": 1, "detected_type": "OR"},
        {"row_no": 3, "raw_condition": "C = 1", "depth": 2, "detected_type": "condition"},
    ]
    item = _item("X", _cond("A"), table_rows=rows)
    result = build_logic_coverage_item(item)
    gates = [r["gate"] for r in result["source_detected"]]
    assert gates == ["AND", "OR", ""]


def test_coverage_item_source_detected_unresolved_status():
    rows = [{"row_no": 1, "raw_condition": "MISS_SIG = 1", "depth": 0, "detected_type": "condition"}]
    item = _item("X", _cond("MISS_SIG"), unresolved=["MISS_SIG"], table_rows=rows)
    result = build_logic_coverage_item(item)
    assert result["source_detected"][0]["resolved_status"] == "unresolved"


# ---------------------------------------------------------------------------
# build_logic_coverage_list
# ---------------------------------------------------------------------------

def test_coverage_list_empty_bundle():
    result = build_logic_coverage_list({})
    assert result == []


def test_coverage_list_multiple_items():
    bundle = {
        "logic_review_items": [
            _item("A", _cond("X")),
            _item("B", _or(_cond("P"), _cond("Q"))),
        ]
    }
    result = build_logic_coverage_list(bundle)
    assert len(result) == 2
    assert result[0]["logic_id"] == "A"
    assert result[1]["branch_count"] == 3  # OR(P,Q): N01+N02+A01


def test_coverage_list_shutoff_decision_branch_count():
    """SHUTOFF_DECISION-like: OR of 3 paths → branch_count == 3."""
    tree = _or(
        _and(_cond("WMODE_CMD"), _cond("SHUTOFF_STATUS")),
        _and(_cond("EMERGENCY_FLAG")),
        _cond("MANUAL_OVERRIDE"),
    )
    bundle = {
        "logic_review_items": [_item("SHUTOFF_DECISION", tree)]
    }
    result = build_logic_coverage_list(bundle)
    assert result[0]["branch_count"] == 4  # N01-N03 + A01 (combined OR false)
    # All auto-generatable since no unresolved refs
    assert all(b["auto_generatable"] for b in result[0]["branches"])


def test_coverage_list_partial_unresolved():
    """Mix: one group ok, one needs_definition."""
    tree_ok = _cond("KNOWN")
    tree_partial = _or(_cond("KNOWN"), _cond("UNKNOWN"))
    bundle = {
        "logic_review_items": [
            _item("OK_CTRL", tree_ok),
            _item("PARTIAL_CTRL", tree_partial, unresolved=["UNKNOWN"]),
        ]
    }
    result = build_logic_coverage_list(bundle)
    statuses = {r["logic_id"]: r["status"] for r in result}
    assert statuses["OK_CTRL"] == "ok"
    assert statuses["PARTIAL_CTRL"] == "unresolved"
    # OK group: N01(auto) + A01(auto) = 2 auto; PARTIAL group: N01(auto) + N02(blocked) + A01(blocked)
    ok_auto = [b for b in result[0]["branches"] if b["auto_generatable"]]
    partial_auto = [b for b in result[1]["branches"] if b["auto_generatable"]]
    assert len(ok_auto) == 2
    assert len(partial_auto) == 1  # only KNOWN normal branch is auto


# ---------------------------------------------------------------------------
# Signal condition input format
# ---------------------------------------------------------------------------

def test_signal_condition_op_value_in_input():
    tree = _signal_cond("SPEED", ">=", "100")
    branches = _build_branches(tree, "CTRL", frozenset())
    tc = branches[0]["suggested_testcase"]
    assert "SPEED >= 100" in tc["expected_input"]


# ---------------------------------------------------------------------------
# Patch 3A.1 — visual_source fallback / bad-line detection
# ---------------------------------------------------------------------------

def test_cnd_safe_group_source_structure_uses_leaf_conditions():
    """CND_SAFE_GROUP-like: visual_source builds readable hierarchy, not 'CTRL: AND' repetitions."""
    vs = _vs("CND_SAFE_GROUP", [
        _vr(2, ["CND_SAFE_GROUP", "AND", "VEHICLE_STOPPED (*1)"]),
        _vr(3, ["CND_SAFE_GROUP", "AND", "DRIVER_SAFE (*2)"]),
        _vr(4, ["CND_SAFE_GROUP", "AND", "OR", "PROCESS_IDLE (*3)"]),
        _vr(5, ["CND_SAFE_GROUP", "AND", "OR", "PROCESS_PREPARED (*4)"]),
        _vr(6, ["CND_SAFE_GROUP", "AND", "NOT SAFETY_LOCKED (*5)"]),
    ])
    item = _item("CND_SAFE_GROUP", {}, visual_source=vs)
    result = build_logic_coverage_item(item)

    joined = "\n".join(result["tree_lines"])
    assert "VEHICLE_STOPPED (*1)" in joined
    assert "DRIVER_SAFE (*2)" in joined
    assert "PROCESS_IDLE (*3)" in joined
    assert "PROCESS_PREPARED (*4)" in joined
    assert "NOT SAFETY_LOCKED (*5)" in joined
    assert "CND_SAFE_GROUP: AND" not in joined
    # N01/N02 (normal via each OR alt) + A01/A02/A03 (each mandatory false) + A04 (all OR false) = 6
    assert result["branch_count"] == 6
    assert result["status"] == "needs_review"
    assert result["source_structure_note"]
    # Verify normal/abnormal split
    normals = [b for b in result["branches"] if b["branch_type"] == "normal"]
    abnormals = [b for b in result["branches"] if b["branch_type"] == "abnormal"]
    assert len(normals) == 2
    assert len(abnormals) == 4


def test_repeated_control_and_gate_lines_are_rejected_as_bad_source():
    """_is_bad_tree_lines detects the repeated 'CTRL: AND' useless pattern."""
    bad = ["CND_SAFE_GROUP: AND", "CND_SAFE_GROUP: AND", "CND_SAFE_GROUP: AND"]
    assert _is_bad_tree_lines(bad, "CND_SAFE_GROUP") is True

    good = [
        "CND_SAFE_GROUP",
        "AND",
        "  VEHICLE_STOPPED (*1)",
        "  OR",
        "    PROCESS_IDLE (*2)",
    ]
    assert _is_bad_tree_lines(good, "CND_SAFE_GROUP") is False

    assert _is_bad_tree_lines([], "CTRL") is True


def test_table_row_fallback_preserves_not_condition():
    """NOT X leaf in visual_source must appear in N01 required_conditions; A01/A02 as abnormal."""
    vs = _vs("CTRL", [
        _vr(1, ["CTRL", "AND", "COND_A"]),
        _vr(2, ["CTRL", "AND", "NOT COND_B"]),
    ])
    item = _item("CTRL", {}, visual_source=vs)
    result = build_logic_coverage_item(item)

    # N01 (all mandatory true) + A01 (COND_A false) + A02 (NOT COND_B false = COND_B true)
    assert result["branch_count"] == 3
    n01 = result["branches"][0]
    assert n01["branch_type"] == "normal"
    assert n01["branch_id"] == "N01"
    conds = n01["required_conditions"]
    assert "COND_A" in conds
    assert "NOT COND_B" in conds
    abnormals = [b for b in result["branches"] if b["branch_type"] == "abnormal"]
    assert len(abnormals) == 2


def test_table_row_fallback_preserves_footnote_markers():
    """Footnote markers (*1) must survive through conditions and suggested expected_input."""
    vs = _vs("MY_CTRL", [
        _vr(1, ["MY_CTRL", "AND", "VEHICLE_STOPPED = 2(*1)"]),
        _vr(2, ["MY_CTRL", "AND", "DRIVER_SAFE (*2)"]),
    ])
    item = _item("MY_CTRL", {}, visual_source=vs)
    result = build_logic_coverage_item(item)

    conds = result["branches"][0]["required_conditions"]
    assert any("(*1)" in c for c in conds)
    assert any("(*2)" in c for c in conds)
    tc = result["branches"][0]["suggested_testcase"]
    assert tc is not None
    assert "(*1)" in tc["expected_input"]
    assert "(*2)" in tc["expected_input"]


def test_gate_only_rows_not_counted_as_branches():
    """table_rows whose raw_condition is only a gate keyword (AND/OR) must not become branches."""
    gate_rows = [
        {"row_no": 1, "control": "CTRL", "raw_condition": "AND", "depth": 0, "detected_type": "AND"},
        {"row_no": 2, "control": "CTRL", "raw_condition": "OR",  "depth": 1, "detected_type": "OR"},
        {"row_no": 3, "control": "CTRL", "raw_condition": "AND", "depth": 0, "detected_type": "AND"},
    ]
    item = _item("CTRL", {}, table_rows=gate_rows)
    result = build_logic_coverage_item(item)

    assert result["branch_count"] == 0
    assert result["status"] == "needs_review"


# ---------------------------------------------------------------------------
# N/A normal+abnormal model (Patch 3C)
# ---------------------------------------------------------------------------

def test_normal_abnormal_cnd_req_group_example():
    """CND_REQ_GROUP spec example: AND(REQ_MAIN_OK, OR(REQ_SRC_A, REQ_SRC_B), REQ_STABLE)
    Expected: N01, N02 (normal), A01, A02, A03 (abnormal) = 5 branches.
    """
    from src.engine.logic_coverage import _build_normal_abnormal_from_visual_source
    vs = _vs("CND_REQ_GROUP", [
        _vr(1, ["CND_REQ_GROUP", "AND", "REQ_MAIN_OK"]),
        _vr(2, ["CND_REQ_GROUP", "AND", "OR", "REQ_SRC_A_VALID"]),
        _vr(3, ["CND_REQ_GROUP", "AND", "OR", "REQ_SRC_B_VALID"]),
        _vr(4, ["CND_REQ_GROUP", "AND", "REQ_STABLE"]),
    ])
    branches = _build_normal_abnormal_from_visual_source("CND_REQ_GROUP", vs, frozenset())

    n_branches = [b for b in branches if b["branch_type"] == "normal"]
    a_branches = [b for b in branches if b["branch_type"] == "abnormal"]

    assert len(n_branches) == 2
    assert len(a_branches) == 3

    # N01: via SRC_A
    assert "REQ_MAIN_OK" in n_branches[0]["required_conditions"]
    assert "REQ_SRC_A_VALID" in n_branches[0]["required_conditions"]
    assert "REQ_STABLE" in n_branches[0]["required_conditions"]
    assert n_branches[0]["expected_result"] == "TRUE"
    assert n_branches[0]["suggested_testcase"]["expected_output"] == "CND_REQ_GROUP = TRUE"
    assert n_branches[0]["branch_id"] == "N01"

    # N02: via SRC_B
    assert "REQ_SRC_B_VALID" in n_branches[1]["required_conditions"]
    assert n_branches[1]["branch_id"] == "N02"

    # A01: REQ_MAIN_OK false
    assert a_branches[0]["false_condition"] == "REQ_MAIN_OK"
    assert a_branches[0]["expected_result"] == "FALSE"
    assert "FALSE" in a_branches[0]["suggested_testcase"]["expected_input"]
    assert a_branches[0]["suggested_testcase"]["expected_output"] == "CND_REQ_GROUP = FALSE"

    # A02: REQ_STABLE false
    assert a_branches[1]["false_condition"] == "REQ_STABLE"

    # A03: all OR alternatives false
    assert "REQ_SRC_A_VALID" in a_branches[2]["false_condition"]
    assert "REQ_SRC_B_VALID" in a_branches[2]["false_condition"]


def test_normal_abnormal_pure_and_no_or():
    """Pure AND (no OR group): one normal + one abnormal per mandatory."""
    from src.engine.logic_coverage import _build_normal_abnormal_from_visual_source
    vs = _vs("SIMPLE_CTRL", [
        _vr(1, ["SIMPLE_CTRL", "AND", "SIG_A"]),
        _vr(2, ["SIMPLE_CTRL", "AND", "SIG_B"]),
    ])
    branches = _build_normal_abnormal_from_visual_source("SIMPLE_CTRL", vs, frozenset())

    n = [b for b in branches if b["branch_type"] == "normal"]
    a = [b for b in branches if b["branch_type"] == "abnormal"]
    assert len(n) == 1  # N01: SIG_A AND SIG_B
    assert len(a) == 2  # A01: SIG_A=FALSE, A02: SIG_B=FALSE
    assert set(n[0]["required_conditions"]) == {"SIG_A", "SIG_B"}
    assert a[0]["false_condition"] == "SIG_A"
    assert a[1]["false_condition"] == "SIG_B"


def test_normal_abnormal_candidate_ids():
    """Candidate IDs follow TC_CTRL_N01 / TC_CTRL_A01 scheme."""
    from src.engine.logic_coverage import _build_normal_abnormal_from_visual_source
    vs = _vs("MY_LOGIC", [
        _vr(1, ["MY_LOGIC", "AND", "COND_X"]),
        _vr(2, ["MY_LOGIC", "AND", "OR", "OPT_A"]),
        _vr(3, ["MY_LOGIC", "AND", "OR", "OPT_B"]),
    ])
    branches = _build_normal_abnormal_from_visual_source("MY_LOGIC", vs, frozenset())
    cids = [b["suggested_testcase"]["candidate_id"] for b in branches if b["suggested_testcase"]]
    assert "TC_MY_LOGIC_N01" in cids
    assert "TC_MY_LOGIC_N02" in cids
    assert "TC_MY_LOGIC_A01" in cids  # COND_X false
    assert "TC_MY_LOGIC_A02" in cids  # all OR false


def test_tree_model_branches_use_n_naming():
    """Tree-model _build_branches now produces N01/N02 branch_ids."""
    tree = _or(_cond("PATH_A"), _cond("PATH_B"))
    branches = _build_branches(tree, "CTRL", frozenset())
    assert branches[0]["branch_id"] == "N01"
    assert branches[1]["branch_id"] == "N02"
    assert branches[0]["branch_type"] == "normal"
    assert branches[0]["suggested_testcase"]["candidate_id"] == "TC_CTRL_N01"
    assert branches[0]["suggested_testcase"]["expected_output"] == "CTRL = TRUE"


# ---------------------------------------------------------------------------
# Patch 3D — generic boolean planner
# ---------------------------------------------------------------------------

def test_generic_and_or_true_branches():
    """AND(A, OR(B, C)) TRUE branches = cartesian product: [A+B] and [A+C]."""
    tree = _and(_cond("A"), _or(_cond("B"), _cond("C")))
    branches = _build_branches(tree, "CTRL", frozenset())
    normals = [b for b in branches if b["branch_type"] == "normal"]
    assert len(normals) == 2
    cond_sets = [set(b["required_conditions"]) for b in normals]
    assert {"A", "B"} in cond_sets
    assert {"A", "C"} in cond_sets


def test_generic_and_or_false_minimal_branches():
    """AND(A, OR(B, C)) FALSE branches: A=F or (B=F AND C=F)."""
    tree = _and(_cond("A"), _or(_cond("B"), _cond("C")))
    branches = _build_branches(tree, "CTRL", frozenset())
    abnormals = [b for b in branches if b["branch_type"] == "abnormal"]
    assert len(abnormals) == 2  # A=F branch + combined B=F,C=F branch


def test_generic_not_true_false_inversion():
    """NOT(SIG): TRUE branch uses SIG=0; FALSE branch means SIG=TRUE."""
    tree = _not(_cond("SIG"))
    branches = _build_branches(tree, "CTRL", frozenset())
    normals = [b for b in branches if b["branch_type"] == "normal"]
    abnormals = [b for b in branches if b["branch_type"] == "abnormal"]
    assert len(normals) == 1
    assert len(abnormals) == 1
    assert "NOT SIG" in normals[0]["required_conditions"]
    assert "SIG = TRUE" in abnormals[0]["suggested_testcase"]["expected_input"]


def test_generic_or_false_requires_all_children_false():
    """OR(A, B, C) FALSE: single branch with all children false together."""
    tree = _or(_cond("A"), _cond("B"), _cond("C"))
    branches = _build_branches(tree, "CTRL", frozenset())
    abnormals = [b for b in branches if b["branch_type"] == "abnormal"]
    assert len(abnormals) == 1
    inp = abnormals[0]["suggested_testcase"]["expected_input"]
    assert "A = FALSE" in inp
    assert "B = FALSE" in inp
    assert "C = FALSE" in inp


def test_generic_and_false_one_branch_per_child():
    """AND(A, B, C) FALSE: three minimal branches, one per child."""
    tree = _and(_cond("A"), _cond("B"), _cond("C"))
    branches = _build_branches(tree, "CTRL", frozenset())
    abnormals = [b for b in branches if b["branch_type"] == "abnormal"]
    assert len(abnormals) == 3
    false_inputs = [b["suggested_testcase"]["expected_input"] for b in abnormals]
    assert any("A = FALSE" in s for s in false_inputs)
    assert any("B = FALSE" in s for s in false_inputs)
    assert any("C = FALSE" in s for s in false_inputs)


def test_tree_model_path_generates_abnormal_when_complete():
    """Tree-model path now produces both normal and abnormal branches."""
    tree = _and(_cond("X"), _cond("Y"))
    branches = _build_branches(tree, "CTRL", frozenset())
    assert any(b["branch_type"] == "normal" for b in branches)
    assert any(b["branch_type"] == "abnormal" for b in branches)
    n = next(b for b in branches if b["branch_type"] == "normal")
    a = next(b for b in branches if b["branch_type"] == "abnormal")
    assert n["suggested_testcase"]["expected_output"] == "CTRL = TRUE"
    assert a["suggested_testcase"]["expected_output"] == "CTRL = FALSE"


def test_visual_source_path_still_generates_expected_branches():
    """Visual source path (_build_normal_abnormal_from_visual_source) is unaffected."""
    from src.engine.logic_coverage import _build_normal_abnormal_from_visual_source
    vs = _vs("CTRL", [
        _vr(1, ["CTRL", "AND", "COND_A"]),
        _vr(2, ["CTRL", "AND", "COND_B"]),
    ])
    branches = _build_normal_abnormal_from_visual_source("CTRL", vs, frozenset())
    assert len(branches) == 3  # N01 + A01 (COND_A=F) + A02 (COND_B=F)
    assert branches[0]["branch_type"] == "normal"
    assert branches[1]["branch_type"] == "abnormal"
    assert branches[2]["branch_type"] == "abnormal"


def test_cleanup_does_not_remove_manual_or_confirmed_rows():
    """_is_safe_to_archive returns False for manually edited or confirmed rows."""
    from web.main import _is_safe_to_archive
    base = {"id": "TC_CTRL_N01", "source": "logic_branch_generator"}
    assert _is_safe_to_archive(base, {}) is True  # baseline auto row is safe
    assert _is_safe_to_archive({**base, "status": "confirmed"}, {}) is False
    assert _is_safe_to_archive({**base, "review_status": "approved"}, {}) is False
    assert _is_safe_to_archive({**base, "user_notes": "checked"}, {}) is False
    assert _is_safe_to_archive({**base, "exported_at": "2024-01-01"}, {}) is False
    assert _is_safe_to_archive({**base, "manually_edited": True}, {}) is False
    assert _is_safe_to_archive({**base, "test_code_ref": "some_ref"}, {}) is False


def test_old_tc_branch_rows_removed_only_when_safe():
    """_is_safe_to_archive identifies old TC_BRANCH/TC_PM pattern rows as safe."""
    from web.main import _is_safe_to_archive
    old_auto = {"id": "TC_BRANCH_001", "source": "unknown"}
    assert _is_safe_to_archive(old_auto, {}) is True  # old ID pattern → safe
    old_pm = {"id": "TC_PM_042", "source": ""}
    assert _is_safe_to_archive(old_pm, {}) is True
    protected = {"id": "TC_BRANCH_001", "source": "unknown", "status": "approved"}
    assert _is_safe_to_archive(protected, {}) is False  # approved → never remove
