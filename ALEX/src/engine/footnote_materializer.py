"""Materialize cross-file footnote logic onto source controls."""

from __future__ import annotations

from typing import Any


def link_footnotes_to_logic_blocks(bundle: dict[str, Any]) -> int:
    """Set logic_id on footnote rows from table control / condition_name match."""
    logic_blocks = bundle.get("logic_blocks") or []
    by_name = {str(lb.get("name") or "").upper(): lb for lb in logic_blocks if lb.get("name")}
    by_id = {str(lb.get("id") or ""): lb for lb in logic_blocks if lb.get("id")}
    linked = 0
    for foot in bundle.get("footnote_definitions") or []:
        if foot.get("logic_id"):
            continue
        control = str(foot.get("control") or "").strip()
        cond = str(foot.get("condition_name") or "").strip()
        src = foot.get("source") if isinstance(foot.get("source"), dict) else {}
        table_id = str(src.get("table_id") or src.get("table") or "")
        logic_id = ""
        if table_id:
            candidate = f"TC2_{table_id}" if not str(table_id).startswith("TC2_") else str(table_id)
            if candidate in by_id:
                logic_id = candidate
        if not logic_id and control:
            for lb in logic_blocks:
                src_lb = lb.get("source") if isinstance(lb.get("source"), dict) else {}
                if str(src_lb.get("control") or lb.get("name") or "").upper() == control.upper():
                    logic_id = str(lb.get("id") or "")
                    break
        if not logic_id and cond:
            lb = by_name.get(cond.upper())
            if lb:
                logic_id = str(lb.get("id") or "")
        if logic_id:
            foot["logic_id"] = logic_id
            linked += 1
    return linked


def _materialized_excerpt(target_lb: dict[str, Any]) -> dict[str, Any]:
    src = target_lb.get("source") if isinstance(target_lb.get("source"), dict) else {}
    return {
        "logic_id": target_lb.get("id"),
        "control_name": target_lb.get("name"),
        "raw_expression": (target_lb.get("raw_expression") or "")[:500],
        "parse_status": target_lb.get("parse_status"),
        "source": src,
        "tree_summary": _tree_summary(target_lb.get("tree") or {}),
    }


def _tree_summary(tree: dict[str, Any], depth: int = 0) -> list[str]:
    lines: list[str] = []
    if depth > 6:
        return lines
    t = tree.get("type")
    if t in ("AND", "OR", "NOT"):
        lines.append(f"{'  ' * depth}{t}")
        for ch in tree.get("children") or []:
            if isinstance(ch, dict):
                lines.extend(_tree_summary(ch, depth + 1))
    else:
        label = tree.get("raw_text") or tree.get("signal") or tree.get("name") or t
        lines.append(f"{'  ' * depth}{label}")
    return lines[:24]


def materialize_footnote_attachments(
    bundle: dict[str, Any],
    *,
    logic_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Attach target logic blocks referenced by footnotes onto source logic_blocks.

    Stores ``attached_logic[]`` on each source block and ``footnote_materializations`` summary.
    """
    from src.engine.cross_file_resolver import resolve_footnote_cross_refs

    link_footnotes_to_logic_blocks(bundle)
    resolve_footnote_cross_refs(bundle)

    logic_blocks = bundle.get("logic_blocks") or []
    by_id = {str(lb.get("id") or ""): lb for lb in logic_blocks if lb.get("id")}
    by_name = {str(lb.get("name") or "").upper(): lb for lb in logic_blocks if lb.get("name")}
    target_ids = {str(x) for x in logic_ids} if logic_ids else None

    materialized = 0
    attachments: list[dict[str, Any]] = []

    for foot in bundle.get("footnote_definitions") or []:
        source_logic_id = str(foot.get("logic_id") or "").strip()
        if not source_logic_id:
            continue
        if target_ids is not None and source_logic_id not in target_ids:
            continue
        source_lb = by_id.get(source_logic_id)
        if not source_lb:
            continue

        cross_targets = list(foot.get("target_logic_ids") or [])
        for ref in foot.get("cross_refs") or []:
            cross_targets.extend(ref.get("target_logic_ids") or [])

        attached_for_foot: list[dict[str, Any]] = []
        for tid in sorted(set(str(x) for x in cross_targets if x)):
            if tid == source_logic_id:
                continue
            target_lb = by_id.get(tid)
            if not target_lb:
                continue
            entry = {
                "source_footnote": foot.get("ref") or foot.get("footnote_num"),
                "from_file": (target_lb.get("source") or {}).get("file"),
                "logic_id": tid,
                "control_name": target_lb.get("name"),
                "materialized_excerpt": _materialized_excerpt(target_lb),
                "review_status": "pending",
                "citations": [
                    {
                        "kind": "footnote",
                        "ref": foot.get("ref"),
                        "file": (foot.get("source") or {}).get("file"),
                    },
                    {
                        "kind": "logic_block",
                        "logic_id": tid,
                        "file": (target_lb.get("source") or {}).get("file"),
                    },
                ],
            }
            attached_for_foot.append(entry)
            attachments.append({**entry, "source_logic_id": source_logic_id})
            materialized += 1

        # Condition-group refs without explicit logic_id
        for cname in foot.get("target_condition_names") or []:
            target_lb = by_name.get(str(cname).upper())
            if not target_lb:
                continue
            tid = str(target_lb.get("id") or "")
            if tid == source_logic_id or any(a.get("logic_id") == tid for a in attached_for_foot):
                continue
            entry = {
                "source_footnote": foot.get("ref") or foot.get("footnote_num"),
                "from_file": (target_lb.get("source") or {}).get("file"),
                "logic_id": tid,
                "control_name": target_lb.get("name"),
                "materialized_excerpt": _materialized_excerpt(target_lb),
                "review_status": "pending",
                "via_condition_name": cname,
                "citations": [
                    {"kind": "footnote", "ref": foot.get("ref")},
                    {"kind": "condition_group", "name": cname},
                ],
            }
            attached_for_foot.append(entry)
            attachments.append({**entry, "source_logic_id": source_logic_id})
            materialized += 1

        if attached_for_foot:
            existing = list(source_lb.get("attached_logic") or [])
            seen_keys = {(a.get("logic_id"), a.get("source_footnote")) for a in existing}
            for entry in attached_for_foot:
                key = (entry.get("logic_id"), entry.get("source_footnote"))
                if key not in seen_keys:
                    existing.append(entry)
                    seen_keys.add(key)
            source_lb["attached_logic"] = existing

    bundle["footnote_materializations"] = {
        "count": materialized,
        "attachments": attachments,
    }
    return {"materialized_count": materialized, "attachments": attachments}
