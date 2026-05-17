"""Understanding gate: ready | needs_llm | needs_engineer per logic block."""

from __future__ import annotations

from typing import Any

from src.engine.footnote_resolver import build_footnote_registry
from src.engine.logic_atom import _normalize_footnote_ref
from src.engine.logic_atom import (
    atom_signal_names,
    collect_atoms_from_tree,
    enrich_tree_with_atoms,
    is_atom_self_resolved,
)
from src.parsers.two_column_table_parser import FOOTNOTE_RE


def evaluate_logic_block_gate(
    logic_block: dict[str, Any],
    *,
    footnote_definitions: list[dict[str, Any]] | None = None,
    known_definitions: set[str] | None = None,
    alias_targets: set[str] | None = None,
) -> dict[str, Any]:
    """
    Returns gate_status, gaps[], atoms[], footnote_variants[].
    """
    tree = logic_block.get("tree") or {}
    if not tree or tree.get("type") == "empty":
        return {
            "gate_status": "needs_engineer",
            "gaps": [{"kind": "parse_failed", "message": "Logic tree empty or failed"}],
            "atoms": [],
            "footnote_variants": [],
        }

    enriched = enrich_tree_with_atoms(dict(tree))
    atoms = collect_atoms_from_tree(enriched)
    registry = build_footnote_registry(footnote_definitions or [])
    known = known_definitions or set()
    aliases = alias_targets or set()

    gaps: list[dict[str, Any]] = []
    footnote_variants: list[dict[str, Any]] = []

    for atom in atoms:
        sig = str(atom.get("signal") or "")
        refs = atom.get("footnote_refs") or []
        if refs:
            ref = _normalize_footnote_ref(str(refs[0]))
            entry = registry.get(ref) or registry.get(str(refs[0])) or {}
            if entry.get("parsed_rule"):
                from src.engine.footnote_resolver import expand_footnote_variants

                footnote_variants.extend(expand_footnote_variants(registry, ref))
                atom["resolution"] = "resolved"
            else:
                gaps.append(
                    {
                        "kind": "footnote_unresolved",
                        "term": sig,
                        "ref": ref,
                        "message": f"Footnote {ref} has no definition body",
                    }
                )
                atom["resolution"] = "needs_llm"
        elif is_atom_self_resolved(atom):
            atom["resolution"] = "resolved"
        elif sig in known or sig in aliases:
            atom["resolution"] = "resolved"
        else:
            gaps.append(
                {
                    "kind": "missing_definition",
                    "term": sig,
                    "message": f"No definition for signal `{sig}`",
                }
            )
            atom["resolution"] = "needs_engineer"

    if logic_block.get("parse_status") in ("failed", "partial"):
        gaps.append(
            {
                "kind": "parse_partial",
                "message": f"Parse status: {logic_block.get('parse_status')}",
            }
        )

    for ref in logic_block.get("unresolved_refs") or []:
        base = FOOTNOTE_RE.sub("", str(ref)).strip()
        sig_only = base.split("=")[0].strip() if "=" in base else base
        if not any(a.get("signal") == sig_only for a in atoms):
            gaps.append({"kind": "legacy_unresolved", "term": ref, "message": f"Unresolved ref: {ref}"})

    statuses = {a.get("resolution") for a in atoms}
    if any(g.get("kind") == "parse_failed" for g in gaps) or logic_block.get("parse_status") == "failed":
        gate = "needs_engineer"
    elif "needs_engineer" in statuses or any(g["kind"] == "missing_definition" for g in gaps):
        gate = "needs_engineer"
    elif "needs_llm" in statuses or any(g["kind"] == "footnote_unresolved" for g in gaps):
        gate = "needs_llm"
    elif gaps and logic_block.get("parse_status") == "partial":
        gate = "needs_engineer"
    else:
        gate = "ready"

    return {
        "gate_status": gate,
        "gaps": gaps,
        "atoms": atoms,
        "footnote_variants": footnote_variants,
        "tree": enriched,
        "atom_signals": atom_signal_names(enriched),
    }


def build_resolved_logic_blocks(
    logic_blocks: list[dict[str, Any]],
    *,
    footnote_definitions: list[dict[str, Any]] | None = None,
    condition_definitions: list[dict[str, Any]] | None = None,
    alias_map: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    known: set[str] = set()
    for d in condition_definitions or []:
        if d.get("name"):
            known.add(str(d["name"]))
    targets = {str(a.get("target", "")) for a in alias_map or [] if a.get("target")}
    aliases = {str(a.get("alias", "")) for a in alias_map or [] if a.get("alias")}

    resolved: list[dict[str, Any]] = []
    for lb in logic_blocks:
        ev = evaluate_logic_block_gate(
            lb,
            footnote_definitions=footnote_definitions,
            known_definitions=known,
            alias_targets=targets | aliases,
        )
        resolved.append(
            {
                "id": lb.get("id"),
                "name": lb.get("name"),
                "raw_expression": lb.get("raw_expression"),
                "gate_status": ev["gate_status"],
                "gaps": ev["gaps"],
                "atoms": ev["atoms"],
                "footnote_variants": ev["footnote_variants"],
                "tree": ev["tree"],
                "parse_status": lb.get("parse_status"),
                "can_generate_candidates": ev["gate_status"] == "ready",
                "source": lb.get("source"),
            }
        )
    return resolved
