"""Resolve Copilot/exemplar batch targets from imported groups only — no similarity regrouping."""

from __future__ import annotations

from typing import Any

IMPORT_GROUP_FIELD = "test_group"
LOGIC_GROUP_FIELD = "logic_id"


def import_group_key(row: dict[str, Any]) -> str:
    """Existing group from imported Excel (Test Group column)."""
    return str(row.get(IMPORT_GROUP_FIELD) or "").strip()


def logic_group_key(row: dict[str, Any]) -> str:
    return str(row.get(LOGIC_GROUP_FIELD) or "").strip()


def ordered_preview_rows(bundle: dict[str, Any], *, language: str = "EN") -> list[dict[str, Any]]:
    """Testcase rows in import / Excel order (preview enumeration order)."""
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    return list(preview.get("rows") or [])


def sort_candidate_ids_by_preview_order(
    candidate_ids: list[str],
    ordered_rows: list[dict[str, Any]],
) -> list[str]:
    order_index: dict[str, int] = {}
    for i, row in enumerate(ordered_rows):
        cid = str(row.get("candidate_id") or "").strip()
        if cid:
            order_index[cid] = i
    return sorted(
        [c for c in candidate_ids if c],
        key=lambda c: order_index.get(c, 10_000_000),
    )


def row_matches_import_group(row: dict[str, Any], group_key: str, *, field: str = IMPORT_GROUP_FIELD) -> bool:
    if not group_key:
        return False
    if field == LOGIC_GROUP_FIELD:
        return logic_group_key(row) == group_key
    return import_group_key(row) == group_key


def resolve_batch_targets(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    scope: str = "filter",
    group_key: str = "",
    group_field: str = IMPORT_GROUP_FIELD,
    exclude_candidate_ids: list[str] | None = None,
    skip_saved: bool = False,
) -> dict[str, Any]:
    """
    Resolve batch target candidate_ids only from existing import structure.

    scope:
      - all: every imported testcase in Excel order (optional skip_saved)
      - filter: use candidate_ids (client applies UI workflow filter first)
      - group: all rows in group_key for group_field (test_group or logic_id)
      - selected: use candidate_ids (must be explicit selection, typically one TC)
    """
    ordered = ordered_preview_rows(bundle, language=language)
    row_by_id = {
        str(r.get("candidate_id") or ""): r
        for r in ordered
        if str(r.get("candidate_id") or "").strip()
    }
    exclude = set(exclude_candidate_ids or [])
    scope_norm = str(scope or "filter").strip().lower()

    if scope_norm == "all":
        pool = [cid for cid in row_by_id if cid not in exclude]
        group_label = ""
    elif scope_norm == "group":
        gk = str(group_key or "").strip()
        if not gk:
            return {
                "ok": False,
                "error": "No import group selected — select a testcase that belongs to a Test Group.",
                "candidate_ids": [],
                "ordered_rows": ordered,
            }
        pool = [
            cid
            for cid, row in row_by_id.items()
            if row_matches_import_group(row, gk, field=group_field) and cid not in exclude
        ]
        group_label = gk
    elif scope_norm == "selected":
        pool = [c for c in (candidate_ids or []) if c in row_by_id and c not in exclude]
        if not pool:
            return {
                "ok": False,
                "error": "No testcase selected — pick a row in the testcase list.",
                "candidate_ids": [],
                "ordered_rows": ordered,
            }
        group_label = ""
    else:
        if candidate_ids is not None:
            pool = [c for c in candidate_ids if c in row_by_id and c not in exclude]
        else:
            pool = [cid for cid in row_by_id if cid not in exclude]
        group_label = ""

    if skip_saved:
        drafts = gtest_state.get("drafts") or {}
        pool = [
            c
            for c in pool
            if str((drafts.get(c) or {}).get("code_status") or "").upper() != "SAVED"
        ]

    pool = sort_candidate_ids_by_preview_order(pool, ordered)

    return {
        "ok": bool(pool),
        "candidate_ids": pool,
        "target_count": len(pool),
        "scope": scope_norm,
        "group_key": group_label,
        "group_field": group_field if scope_norm == "group" else "",
        "ordered_rows": ordered,
        "error": "" if pool else "No testcases match the current selection.",
    }


def group_keys_present(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct import test_group values in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        gk = import_group_key(row)
        if gk and gk not in seen:
            seen.add(gk)
            out.append(gk)
    return out
