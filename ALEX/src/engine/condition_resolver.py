"""Multi-source condition lookup for a single term."""

from __future__ import annotations

import re
from typing import Any

from src.engine.term_role_classifier import classify_term

_LOGIC_OPS = frozenset({"AND", "OR", "NOT", "TRUE", "FALSE"})


def build_condition_index(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index term -> list of hits from all structured sources."""
    index: dict[str, list[dict[str, Any]]] = {}

    def add(term: str, hit: dict[str, Any]) -> None:
        key = str(term or "").strip()
        if not key or key.upper() in _LOGIC_OPS:
            return
        index.setdefault(key, []).append(hit)
        index.setdefault(key.upper(), []).append(hit)

    for d in bundle.get("condition_definitions") or []:
        nm = str(d.get("name") or "")
        if nm:
            add(
                nm,
                {
                    "kind": "condition_definition",
                    "definition": d.get("definition"),
                    "source": d.get("source"),
                    "role": classify_term(nm, definition=str(d.get("definition") or "")),
                },
            )

    for foot in bundle.get("footnote_definitions") or []:
        ref = str(foot.get("ref") or "")
        cond = str(foot.get("condition_name") or "")
        body = str(foot.get("definition") or foot.get("raw_text") or "")
        if cond:
            add(
                cond,
                {
                    "kind": "footnote",
                    "ref": ref,
                    "definition": body,
                    "source": foot.get("source"),
                    "role": classify_term(cond, definition=body),
                },
            )
        if ref and body:
            add(ref, {"kind": "footnote_ref", "definition": body, "condition_name": cond})

    for lb in bundle.get("logic_blocks") or []:
        ctrl = str(lb.get("name") or "")
        if ctrl:
            add(
                ctrl,
                {
                    "kind": "logic_block",
                    "logic_id": lb.get("id"),
                    "definition": lb.get("raw_expression"),
                    "role": "output_assertion",
                    "source": lb.get("source"),
                },
            )

    for t in bundle.get("transitions") or []:
        raw = str(t.get("raw_condition") or "")
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", raw):
            term = m.group(1)
            if term.upper() in _LOGIC_OPS:
                continue
            add(
                term,
                {
                    "kind": "transition",
                    "transition_id": t.get("id"),
                    "definition": raw,
                    "source": t.get("source"),
                    "role": classify_term(term),
                },
            )

    for code in bundle.get("code_definitions") or []:
        nm = str(code.get("name") or "")
        if nm:
            add(
                nm,
                {
                    "kind": "code_definition",
                    "definition": code.get("definition"),
                    "source": code.get("source"),
                    "role": classify_term(nm, definition=str(code.get("definition") or "")),
                },
            )

    canonical = (bundle.get("ai_assists") or {}).get("canonical_definitions") or {}
    for term, body in canonical.items():
        add(term, {"kind": "canonical", "definition": body, "role": classify_term(term, definition=str(body))})

    return index


def resolve_condition(
    bundle: dict[str, Any],
    term: str,
    *,
    logic_id: str = "",
) -> dict[str, Any]:
    """Return ranked hits for a condition term."""
    query = str(term or "").strip()
    if not query:
        return {"term": "", "hits": []}

    index = build_condition_index(bundle)
    hits = list(index.get(query) or index.get(query.upper()) or [])

    if logic_id:
        filtered = [h for h in hits if h.get("logic_id") in (logic_id, "", None)]
        if filtered:
            hits = filtered + [h for h in hits if h not in filtered]

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for h in hits:
        key = f"{h.get('kind')}:{h.get('definition', '')[:80]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)

    roles = bundle.get("term_roles") or {}
    role_entry = roles.get(query) or roles.get(query.upper()) or {}

    return {
        "term": query,
        "role": role_entry.get("role") or classify_term(query),
        "hits": unique[:20],
        "hit_count": len(unique),
    }
