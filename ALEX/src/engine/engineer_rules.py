"""Apply structured Given patches to test candidates (no regex rule parsing)."""

from __future__ import annotations

from typing import Any

from src.engine.given_value_resolver import sanitize_given_item


def dedupe_given_by_signal(given: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one entry per signal; later items win. Preserve note-only rows."""
    notes: list[dict[str, Any]] = []
    by_sig: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in given or []:
        if not isinstance(item, dict):
            continue
        sig = str(item.get("signal") or "").strip().upper()
        if not sig:
            if item.get("note"):
                notes.append(item)
            continue
        if sig not in order:
            order.append(sig)
        by_sig[sig] = item
    out = notes[:]
    out.extend(by_sig[sig] for sig in order)
    return out


def given_rows_from_patch(rows: list[dict[str, Any]], *, source: str = "ollama_knowledge") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        sig = str(row.get("signal") or "").strip().upper()
        if not sig:
            continue
        val = row.get("value")
        if val is None:
            continue
        clean = sanitize_given_item(
            {
                "signal": sig,
                "value": str(val).strip(),
                "operator": row.get("operator") or "==",
                "negated": row.get("negated"),
            },
            path_intent="satisfy",
        )
        out.append(
            {
                "signal": sig,
                "value": clean.get("value"),
                "operator": "==",
                "negated": False,
                "source": source,
            }
        )
    return dedupe_given_by_signal(out)


def apply_given_patches_to_bundle(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    source: str = "ollama_knowledge",
) -> int:
    """Merge Ollama Given patches onto candidates for a logic block."""
    by_id = {
        str(p.get("candidate_id") or "").strip(): p
        for p in patches
        if str(p.get("candidate_id") or "").strip()
    }
    updated = 0
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        op = dict(cand.get("operation") or {})
        patch = by_id.get(cid)
        if patch:
            rows = patch.get("given") if isinstance(patch.get("given"), list) else []
            patch_given = given_rows_from_patch(rows, source=source)
            existing = list(op.get("given") or [])
            # Patch rows override matching signals; keep unrelated Given entries.
            op["given"] = dedupe_given_by_signal(existing + patch_given)
            cand["operation"] = op
            updated += 1
        else:
            before = list(op.get("given") or [])
            after = dedupe_given_by_signal(before)
            if after != before:
                op["given"] = after
                cand["operation"] = op
                updated += 1
    return updated


def dedupe_logic_block_given(bundle: dict[str, Any], logic_id: str) -> int:
    """Remove duplicate signals in Given without changing values."""
    return apply_given_patches_to_bundle(bundle, logic_id, [])
