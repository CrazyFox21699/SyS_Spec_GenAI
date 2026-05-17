"""Collect issues and unresolved items — nothing is silently skipped."""

from __future__ import annotations

import re
from typing import Any


def _issue(
    iid: str,
    severity: str,
    itype: str,
    message: str,
    source_ref: dict[str, Any] | None = None,
    affected: list[str] | None = None,
    required_action: str = "",
    can_export: bool = True,
    *,
    raw_text: str = "",
    reason: str = "",
    impact: str = "",
) -> dict[str, Any]:
    return {
        "id": iid,
        "severity": severity,
        "type": itype,
        "message": message,
        "raw_text": raw_text or message,
        "source_ref": source_ref or {},
        "source": source_ref or {},
        "affected_items": affected or [],
        "affected_logic": [a for a in (affected or []) if a],
        "affected_test_candidates": [],
        "reason": reason or message,
        "impact": impact or ("Blocks safe export" if not can_export else "Review recommended"),
        "required_action": required_action or "Review required",
        "can_export": can_export,
    }


def _walk_tree_refs(tree: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    if tree.get("type") == "reference":
        refs.append(str(tree.get("name", "")))
    for ch in tree.get("children") or []:
        if isinstance(ch, dict):
            refs.extend(_walk_tree_refs(ch))
    return [r for r in refs if r]


def collect_issues(
    *,
    classified: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    condition_entries: list[dict[str, Any]],
    timing: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    diagrams: list[dict[str, Any]],
    japanese: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]] | None = None,
    ingest_skipped: list[dict[str, Any]] | None = None,
    two_column_tables: list[dict[str, Any]] | None = None,
    diagram_transitions: list[dict[str, Any]] | None = None,
    strict_mode: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    n = 0

    for sk in ingest_skipped or []:
        n += 1
        issues.append(
            _issue(
                f"ERR_SKIP_{n:03d}",
                "warning",
                "file_skipped",
                f"Skipped file: {sk.get('file')} — {sk.get('reason')}",
                required_action="Remove lock/temp file or close Office app",
            )
        )

    docx_count = sum(
        1
        for c in classified
        if str(c.get("file", "")).lower().endswith((".docx", ".xlsx", ".xlsm"))
    )
    if docx_count and not logic_blocks and not signals and not transitions:
        n += 1
        issues.append(
            _issue(
                f"ERR_EMPTY_{n:03d}",
                "error",
                "extraction_empty",
                "Files were classified but no logic, signals, or transitions were extracted.",
                required_action="Check file is not a lock file (~$), re-upload, or run CLI analyze for details",
                can_export=False,
            )
        )

    for tbl in two_column_tables or []:
        for row in tbl.get("rows") or []:
            if row.get("issue_status") == "review_required":
                n += 1
                issues.append(
                    _issue(
                        f"ERR_TC_{n:03d}",
                        "warning",
                        "ambiguous_constant_value",
                        f"Constant `{row.get('control')}` needs review: {row.get('condition_raw', '')[:80]}",
                        affected=[row.get("control", "")],
                        required_action="Confirm value and unit in engineer review",
                    )
                )

    for dt in diagram_transitions or []:
        if dt.get("derivation") == "diagram_image_metadata":
            n += 1
            issues.append(
                _issue(
                    f"ERR_DG_{n:03d}",
                    "warning",
                    "diagram_interpretation_review_required",
                    dt.get("raw_condition", "Diagram image requires manual review"),
                    source_ref=dt.get("source") if isinstance(dt.get("source"), dict) else {},
                    required_action="Review diagram image and confirm transitions",
                )
            )

    for lb in logic_blocks or []:
        for sub in lb.get("issues") or []:
            n += 1
            issues.append(
                _issue(
                    f"ERR_LB_{n:03d}",
                    sub.get("severity", "warning"),
                    sub.get("type", "logic_block_issue"),
                    sub.get("message", ""),
                    source_ref=lb.get("source") if isinstance(lb.get("source"), dict) else {},
                    affected=[lb.get("id", lb.get("name", ""))],
                    required_action="Review two-column logic interpretation",
                )
            )
        for ref in lb.get("unresolved_refs") or []:
            n += 1
            issues.append(
                _issue(
                    f"ERR_REF_{n:03d}",
                    "error",
                    "unresolved_condition",
                    f"Referenced condition `{ref}` has no definition in spec tables",
                    affected=[lb.get("id", ""), ref],
                    required_action="Add definition or alias mapping before approval",
                    can_export=not strict_mode,
                )
            )
            unresolved.append(
                {
                    "type": "unresolved_condition",
                    "raw_text": ref,
                    "reason": f"No definition for {ref}",
                    "required_action": "Add to condition definition or alias table",
                }
            )
        if lb.get("parse_status") == "failed" or (lb.get("tree") or {}).get("type") == "empty":
            n += 1
            issues.append(
                _issue(
                    f"ERR_LB_{n:03d}",
                    "error",
                    "logic_block_parse_failed",
                    f"Logic block `{lb.get('name')}` could not be fully parsed",
                    source_ref=lb.get("source") if isinstance(lb.get("source"), dict) else {},
                    affected=[str(lb.get("id"))],
                )
            )

    # Defined condition names from transitions (expanded definitions in raw text)
    defined_conditions: set[str] = set()
    for ce in condition_entries:
        raw = str(ce.get("raw_condition", ""))
        for m in re.finditer(r"Condition_[A-Za-z0-9]+", raw, re.I):
            defined_conditions.add(m.group(0))
        tree = ce.get("tree") or {}
        for ref in _walk_tree_refs(tree):
            if ref.startswith("Condition_") or ref.startswith("Cond"):
                defined_conditions.add(ref)

    referenced: set[str] = set()
    for ce in condition_entries:
        tree = ce.get("tree") or {}
        for ref in _walk_tree_refs(tree):
            if re.match(r"^Condition_[A-Za-z0-9_]+$", ref, re.I):
                referenced.add(ref)

    for ref in sorted(referenced):
        if ref not in defined_conditions:
            n += 1
            ce_match = next((c for c in condition_entries if ref in str(c.get("raw_condition", ""))), None)
            src = ce_match.get("source") if ce_match else {}
            item = {
                "type": "referenced_condition_not_found",
                "raw_text": ref,
                "source": src,
                "reason": f"{ref} is referenced but no standalone definition was extracted",
                "impact": "Cannot fully validate condition tree",
                "required_action": "Add source definition or manually confirm",
            }
            unresolved.append(item)
            issues.append(
                _issue(
                    f"ERR_COND_{n:03d}",
                    "error",
                    "referenced_condition_not_found",
                    item["reason"],
                    source_ref=src if isinstance(src, dict) else {},
                    affected=[ref],
                    required_action=item["required_action"],
                    can_export=not strict_mode,
                )
            )

    for i, ce in enumerate(condition_entries):
        tree = ce.get("tree") or {}
        if tree.get("type") == "empty" or tree.get("parse_status") == "failed":
            n += 1
            unresolved.append(
                {
                    "type": "condition_parse_failed",
                    "raw_text": ce.get("raw_condition", ""),
                    "source": ce.get("source"),
                    "reason": "Unsupported or ambiguous logic format",
                    "impact": "Cannot safely generate final test spec for this transition",
                    "required_action": "Engineer review required",
                }
            )
            issues.append(
                _issue(
                    f"ERR_PARSE_{n:03d}",
                    "error",
                    "condition_parse_failed",
                    "Condition parse failed",
                    source_ref=ce.get("source") if isinstance(ce.get("source"), dict) else {},
                    affected=[str(ce.get("transition_id"))],
                    required_action="Engineer review required",
                    can_export=not strict_mode,
                )
            )
        for ref in _walk_tree_refs(tree):
            if tree.get("type") == "opaque" or (isinstance(tree, dict) and tree.get("type") == "opaque"):
                pass
        raw = str(ce.get("raw_condition", ""))
        if "INGEST_" in raw or tree.get("type") == "opaque":
            n += 1
            issues.append(
                _issue(
                    f"WARN_OPAQUE_{n:03d}",
                    "warning",
                    "condition_partially_parsed",
                    "Some condition text could not be structured",
                    source_ref=ce.get("source") if isinstance(ce.get("source"), dict) else {},
                    affected=[str(ce.get("transition_id"))],
                )
            )

    for s in signals:
        src = s.get("source") or {}
        if not src.get("file") or src.get("file") in ("UNKNOWN", "UNKNOWN_SOURCE"):
            n += 1
            issues.append(
                _issue(
                    f"ERR_SIG_{n:03d}",
                    "warning",
                    "missing_source_evidence",
                    f"Signal `{s.get('name')}` lacks traceable source",
                    affected=[str(s.get("name"))],
                    required_action="Link signal to system spec row",
                )
            )
        if s.get("review_required"):
            n += 1
            issues.append(
                _issue(
                    f"INFO_SIG_REV_{n:03d}",
                    "info",
                    "review_required",
                    f"Signal `{s.get('name')}` marked review_required",
                    source_ref=src if isinstance(src, dict) else {},
                    affected=[str(s.get("name"))],
                )
            )

    for tn in timing:
        if tn.get("review_required"):
            n += 1
            issues.append(
                _issue(
                    f"WARN_TIME_{n:03d}",
                    "warning",
                    "timing_ambiguity",
                    f"Timing `{tn.get('raw_text')}` → `{tn.get('interpreted_as')}` needs confirmation",
                    required_action="Approve or change timing interpretation",
                )
            )

    for d in diagrams:
        n += 1
        has_ocr = bool(str(d.get("ocr_text") or "").strip())
        issues.append(
            _issue(
                f"WARN_DIAG_{n:03d}",
                "warning",
                "diagram_review_required",
                (
                    f"Diagram `{d.get('file', d.get('name'))}` has OCR text and semantic hints, but still needs engineer review"
                    if has_ocr
                    else f"Diagram `{d.get('file', d.get('name'))}` still has no readable OCR text"
                ),
                required_action=(
                    "Review semantic edges and confirm transitions"
                    if has_ocr
                    else "Attach a clearer diagram or provide equivalent logic in Word/Excel"
                ),
            )
        )

    for j in japanese:
        if j.get("source") == "llm_generated" or j.get("review_required"):
            n += 1
            issues.append(
                _issue(
                    f"WARN_JP_{n:03d}",
                    "warning",
                    "llm_interpretation_requires_review",
                    "Japanese/LLM interpretation is not final truth",
                    required_action="Comtor and engineer review",
                )
            )

    for cf in classified:
        if cf.get("confidence") == "low" or cf.get("role") == "unknown":
            n += 1
            issues.append(
                _issue(
                    f"WARN_FILE_{n:03d}",
                    "warning",
                    "classification_uncertain",
                    f"File role uncertain: {cf.get('file')}",
                    required_action="Confirm or change role in Source Selection",
                )
            )

    # Block candidates when strict and errors exist
    error_ids = {i["id"] for i in issues if i["severity"] in ("error", "blocker")}
    for c in candidates:
        if c.get("status") == "blocked":
            continue
        op = c.get("operation") or {}
        given = op.get("given") or []
        if any(g.get("parse_status") == "unparsed" for g in given if isinstance(g, dict)):
            c["status"] = "blocked"
            c["block_reason"] = "Condition logic not fully parsed"
            c["required_action"] = "Resolve parse issues before approval"
            n += 1
            issues.append(
                _issue(
                    f"ERR_TC_{n:03d}",
                    "error",
                    "test_candidate_blocked",
                    f"Candidate {c.get('id')} blocked due to unparsed guards",
                    affected=[str(c.get("id"))],
                    can_export=False,
                )
            )

    if strict_mode and any(i["severity"] == "error" for i in issues):
        for c in candidates:
            if c.get("status") not in ("blocked", "approved"):
                c.setdefault("strict_mode_note", "Unresolved errors exist — export not approved")

    return issues, unresolved


def enrich_review_fields(items: list[dict[str, Any]], item_type: str) -> list[dict[str, Any]]:
    out = []
    for i, it in enumerate(items):
        row = dict(it)
        row.setdefault("id", f"{item_type}_{i+1:04d}")
        row.setdefault("type", item_type)
        row.setdefault("review_status", "pending")
        row.setdefault("review_required", bool(it.get("review_required", True)))
        src = it.get("source") or it.get("source_evidence")
        if isinstance(src, list) and src:
            src = src[0]
        if isinstance(src, dict) and src.get("file"):
            row["source_status"] = "present"
            row["source_refs"] = [src]
        else:
            row["source_status"] = "missing"
            row["source_refs"] = []
            row["review_required"] = True
            row.setdefault("confidence", "low")
        row.setdefault("issues", [])
        out.append(row)
    return out
