"""MCDC-oriented test path planner from resolved logic trees (dynamic complexity)."""

from __future__ import annotations

import itertools
from typing import Any

from src.engine.logic_atom import collect_atoms_from_tree
from src.engine.term_role_classifier import classify_term


def estimate_complexity(tree: dict[str, Any], *, footnote_variant_count: int = 0) -> dict[str, Any]:
    or_paths = enumerate_or_paths(tree)
    leaf_count = len(collect_atoms_from_tree(tree))
    factor = max(1, len(or_paths)) * max(1, 2**min(footnote_variant_count, 4))
    return {
        "or_path_count": len(or_paths),
        "leaf_count": leaf_count,
        "footnote_factor": footnote_variant_count,
        "estimated_tc_count": len(or_paths) * max(1, footnote_variant_count or 1),
        "expansion_factor": factor,
    }


def enumerate_or_paths(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Each OR branch → one path spec with atoms to satisfy."""
    if tree.get("type") != "OR":
        atoms = _leaf_atoms_under(tree)
        if atoms:
            return [{"path_id": "path_1", "label": "default", "atoms": atoms}]
        return []

    paths: list[dict[str, Any]] = []
    children = [c for c in tree.get("children") or [] if isinstance(c, dict)]
    for i, child in enumerate(children):
        path_id = f"path_{i + 1}"
        label = f"branch_{i + 1}"
        paths.append(
            {
                "path_id": path_id,
                "label": label,
                "atoms": _leaf_atoms_under(child),
            }
        )
    return paths


def _leaf_atoms_under(node: dict[str, Any]) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []

    def walk(n: dict[str, Any], negated: bool = False) -> None:
        t = n.get("type")
        if t == "condition" and n.get("atom"):
            atom = dict(n["atom"])
            if negated:
                atom["negated"] = not atom.get("negated", False)
            atoms.append(atom)
        elif t == "NOT":
            for ch in n.get("children") or []:
                if isinstance(ch, dict):
                    walk(ch, not negated)
        elif t in ("AND", "OR"):
            for ch in n.get("children") or []:
                if isinstance(ch, dict):
                    walk(ch, negated)
        for ch in n.get("children") or []:
            if isinstance(ch, dict) and t not in ("AND", "OR", "NOT", "condition"):
                walk(ch, negated)

    walk(node)
    return atoms


def plan_test_paths(
    resolved_block: dict[str, Any],
    *,
    control_name: str = "",
    max_expansion_factor: int = 32,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (path_specs, planner_meta).
    path_spec: {path_id, label, given_items[], footnote_branch?}
    """
    tree = resolved_block.get("tree") or {}
    foot_variants = resolved_block.get("footnote_variants") or []
    fn_count = max(1, len(foot_variants)) if foot_variants else 1

    complexity = estimate_complexity(tree, footnote_variant_count=len(foot_variants))
    if complexity["expansion_factor"] > max_expansion_factor:
        return [], {
            **complexity,
            "aborted": True,
            "reason": (
                f"Logic expansion factor {complexity['expansion_factor']} exceeds "
                f"max {max_expansion_factor} — engineer must clarify or narrow scope"
            ),
        }

    base_paths = enumerate_or_paths(tree)
    specs: list[dict[str, Any]] = []

    if not foot_variants:
        for bp in base_paths:
            specs.append(_path_to_spec(bp, control_name))
    else:
        for bp in base_paths:
            for fv in foot_variants:
                spec = _path_to_spec(bp, control_name)
                spec["footnote_branch"] = fv.get("branch")
                spec["footnote_ref"] = fv.get("footnote_ref")
                spec["path_id"] = f"{bp['path_id']}_{fv.get('branch', 'fn')}"
                spec["label"] = f"{bp['label']}_{fv.get('branch', 'fn')}"
                extra = fv.get("atoms") or []
                spec["given_items"] = _merge_given(spec["given_items"], extra)
                specs.append(spec)

    # MCDC: add negation variant for first leaf per path (optional, bounded)
    mcdc_extra: list[dict[str, Any]] = []
    for bp in base_paths[:4]:
        atoms = bp.get("atoms") or []
        if not atoms:
            continue
        primary = atoms[0]
        if primary.get("signal") and classify_term(str(primary["signal"]), control_name=control_name) != "output_assertion":
            neg_spec = _path_to_spec(bp, control_name)
            neg_spec["path_id"] = f"{bp['path_id']}_mcdc_neg"
            neg_spec["label"] = f"{bp['label']}_guard_false"
            neg_spec["mcdc"] = "negate_primary"
            neg_items = []
            for item in neg_spec["given_items"]:
                if item.get("signal") == primary.get("signal"):
                    item = dict(item)
                    item["negated"] = True
                    item["value"] = _negated_value(item.get("value"))
                neg_items.append(item)
            neg_spec["given_items"] = neg_items
            mcdc_extra.append(neg_spec)

    all_specs = specs + mcdc_extra
    if len(all_specs) > max_expansion_factor:
        all_specs = all_specs[:max_expansion_factor]
        meta = {**complexity, "aborted": False, "truncated": True}
    else:
        meta = {**complexity, "aborted": False, "truncated": False}

    meta["path_count"] = len(all_specs)
    return all_specs, meta


def _path_to_spec(path: dict[str, Any], control_name: str) -> dict[str, Any]:
    given: list[dict[str, Any]] = []
    for atom in path.get("atoms") or []:
        sig = str(atom.get("signal") or "")
        if not sig or classify_term(sig, control_name=control_name) == "output_assertion":
            continue
        given.append(
            {
                "signal": sig,
                "value": atom.get("value"),
                "operator": atom.get("operator", "=="),
                "negated": atom.get("negated", False),
            }
        )
    return {
        "path_id": path.get("path_id", "path_1"),
        "label": path.get("label", "default"),
        "given_items": given,
    }


def _merge_given(base: list[dict[str, Any]], extra_atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sig = {g["signal"]: g for g in base if g.get("signal")}
    for atom in extra_atoms:
        sig = atom.get("signal")
        if sig and sig not in by_sig:
            by_sig[sig] = {
                "signal": sig,
                "value": atom.get("value"),
                "operator": "=",
                "negated": False,
                "note": f"Given: {sig}={atom.get('value')}",
            }
    return list(by_sig.values())


def _negated_value(val: Any) -> str:
    if val is None:
        return "0"
    s = str(val).strip().upper()
    if s in ("1", "TRUE", "ON"):
        return "0"
    if s in ("0", "FALSE", "OFF"):
        return "1"
    return "0"
