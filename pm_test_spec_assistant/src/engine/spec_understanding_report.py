"""Build a deterministic 'how well we understand the spec' report — no LLM logic."""

from __future__ import annotations

from typing import Any

COPILOT_RULES = [
    "Use only source text and tool-exported Excel/YAML — do not invent logic gates or conditions.",
    "Do not change AND/OR/NOT structure; only explain ambiguous wording or missing definitions.",
    "If the source does not state it, answer: not stated in specification.",
    "Mark every suggestion as draft until the engineer confirms.",
    "Copilot output must not auto-approve test candidates or clear tool issues.",
]


def _gap(
    gid: str,
    category: str,
    what_we_know: str,
    what_is_vague: str,
    source: dict[str, Any],
    *,
    copilot_question: str,
) -> dict[str, Any]:
    raw = source.get("raw_text") or what_is_vague
    return {
        "id": gid,
        "category": category,
        "what_we_know": what_we_know,
        "what_is_vague": what_is_vague,
        "source": source,
        "copilot_question": copilot_question,
        "copilot_prompt": _strict_copilot_prompt(raw, what_is_vague, copilot_question),
        "for_copilot_only": True,
        "must_not": "Do not infer logic structure or values not present in the source.",
    }


def _strict_copilot_prompt(raw_text: str, gap: str, question: str) -> str:
    return (
        "You assist an automotive test engineer. Follow these rules strictly:\n"
        "1. Use ONLY the source excerpt below — no invented conditions or states.\n"
        "2. Do NOT propose a final logic tree; the tool owns structure.\n"
        "3. If the source is silent, say: not stated in specification.\n\n"
        f"Source excerpt:\n{raw_text[:1200]}\n\n"
        f"Tool gap:\n{gap}\n\n"
        f"Question (answer from source only):\n{question}\n"
    )


def build_spec_understanding_report(
    *,
    classified_files: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
    condition_definitions: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
    two_column_tables: list[dict[str, Any]],
    ingest_skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize extraction coverage and gaps for engineer + Copilot clarification."""
    controls = [lb for lb in logic_blocks if lb.get("block_type") == "two_column_control"]
    ok_controls = [lb for lb in controls if lb.get("parse_status") == "ok"]
    partial_controls = [lb for lb in controls if lb.get("parse_status") == "partial"]
    failed_controls = [lb for lb in controls if lb.get("parse_status") == "failed"]

    n_ctrl = len(controls) or 1
    logic_score = int(100 * len(ok_controls) / n_ctrl)

    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]

    penalty = min(40, len(errors) * 5 + len(partial_controls) * 8 + len(failed_controls) * 15)
    overall_pct = max(0, min(100, logic_score - penalty))

    if overall_pct >= 75 and not errors:
        status = "good"
        headline = "Most control logic was read with clear structure. Review remaining warnings before export."
    elif overall_pct >= 45:
        status = "partial"
        headline = "The tool extracted useful structure but important areas need your review or Copilot clarification."
    else:
        status = "low"
        headline = "Understanding is limited — resolve gaps below before trusting test candidates."

    gaps: list[dict[str, Any]] = []
    n = 0

    for lb in partial_controls + failed_controls:
        n += 1
        gaps.append(
            _gap(
                f"GAP_{n:03d}",
                "logic_parse_incomplete",
                f"Control `{lb.get('name')}` was detected.",
                lb.get("raw_expression") or "Could not build a complete logic tree from the table.",
                lb.get("source") if isinstance(lb.get("source"), dict) else {},
                copilot_question=(
                    f"Using the Word/Excel table for `{lb.get('name')}`, "
                    "describe the intended AND/OR/NOT structure in plain language. "
                    "Quote row text only."
                ),
            )
        )

    for iss in errors[:25]:
        n += 1
        gaps.append(
            _gap(
                f"GAP_{n:03d}",
                iss.get("type", "issue"),
                iss.get("reason", iss.get("message", ""))[:200],
                iss.get("message", ""),
                iss.get("source_ref") if isinstance(iss.get("source_ref"), dict) else {},
                copilot_question=(
                    "Where in the specification is this defined? "
                    "Provide exact table/section text — do not infer."
                ),
            )
        )

    for u in unresolved_items[:15]:
        n += 1
        gaps.append(
            _gap(
                f"GAP_{n:03d}",
                u.get("type", "unresolved"),
                "Referenced in extracted logic.",
                u.get("reason", u.get("raw_text", "")),
                u.get("source") if isinstance(u.get("source"), dict) else {},
                copilot_question=f"Provide the definition for `{u.get('raw_text', '')}` from the spec.",
            )
        )

    copilot_brief = (
        "# Copilot clarification brief (strict)\n\n"
        "ALEX has read the selected files deterministically. "
        "Copilot must **not** replace or bypass the tool's logic trees.\n\n"
        "## Rules\n"
        + "\n".join(f"- {r}" for r in COPILOT_RULES)
        + "\n\n## What the tool extracted\n"
        f"- Files analyzed: {len(classified_files)}\n"
        f"- Control conditions parsed: {len(ok_controls)} ok, {len(partial_controls)} partial, {len(failed_controls)} failed\n"
        f"- Condition definitions: {len(condition_definitions)}\n"
        f"- Two-column tables: {len(two_column_tables)}\n"
        f"- Blocking issues: {len(errors)}\n\n"
        "## Gaps to clarify (use prompts below in Copilot)\n"
        + "\n".join(
            f"- **{g['id']}** ({g['category']}): {g['what_is_vague'][:100]}"
            for g in gaps[:12]
        )
    )

    return {
        "overall": {
            "understanding_percent": overall_pct,
            "status": status,
            "headline": headline,
            "logic_controls_ok": len(ok_controls),
            "logic_controls_partial": len(partial_controls),
            "logic_controls_failed": len(failed_controls),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "extracted": {
            "files": len(classified_files),
            "logic_controls": len(controls),
            "condition_definitions": len(condition_definitions),
            "two_column_tables": len(two_column_tables),
            "ingest_skipped": len(ingest_skipped),
        },
        "gaps": gaps,
        "copilot_rules": COPILOT_RULES,
        "copilot_brief": copilot_brief,
    }
