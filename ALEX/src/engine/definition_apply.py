"""Apply accepted engineer definitions onto logic-block test candidates."""

from __future__ import annotations

from typing import Any

from src.engine.coverage_intent import path_coverage_intent
from src.engine.engineer_rules import dedupe_given_by_signal
from src.engine.given_value_resolver import definition_to_concrete_value, sanitize_given_item
from src.engine.term_role_classifier import classify_term


def apply_engineer_definitions_to_candidates(bundle: dict[str, Any], logic_id: str) -> int:
    """Refresh Given values from engineer_definitions; guard inputs only (not outputs)."""
    ai = bundle.get("ai_assists") or {}
    defs_by_sig: dict[str, dict[str, Any]] = {}
    for name, meta in (ai.get("engineer_definitions") or {}).items():
        if not isinstance(meta, dict):
            continue
        lid = str(meta.get("logic_id") or "")
        if lid and lid != logic_id:
            continue
        defs_by_sig[str(name).strip().upper()] = meta

    if not defs_by_sig:
        return 0

    updated = 0
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        ctrl = str(trace.get("control_name") or "")
        intent = path_coverage_intent(cand)
        op = dict(cand.get("operation") or {})
        given_out: list[dict[str, Any]] = []

        for item in op.get("given") or []:
            if not isinstance(item, dict):
                given_out.append(item)
                continue
            sig = str(item.get("signal") or "").strip()
            if not sig:
                given_out.append(item)
                continue
            if classify_term(sig, control_name=ctrl) == "output_assertion":
                continue
            row = sanitize_given_item(item, path_intent=intent)
            meta = defs_by_sig.get(sig.upper())
            if meta:
                concrete = definition_to_concrete_value(
                    sig,
                    str(meta.get("definition") or ""),
                    negated=bool(item.get("negated")),
                    path_intent=intent,
                )
                if concrete is not None:
                    row = {
                        **row,
                        "signal": sig.upper(),
                        "value": concrete,
                        "operator": "==",
                        "negated": False,
                        "source": "engineer_definition",
                    }
            given_out.append(row)

        op["given"] = dedupe_given_by_signal(given_out)
        cand["operation"] = op
        updated += 1
    return updated
