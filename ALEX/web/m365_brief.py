"""Export/import brief for Microsoft 365 Copilot (manual workflow, no auto-upload)."""

from __future__ import annotations

import json
import re
from typing import Any

from src.engine.concrete_test_values import materialize_expected_input, materialize_expected_output
from src.engine.logic_tree_renderer import render_tree_lines
from web.knowledge_validation import compliance_snapshot

BRIEF_CHAR_LIMIT = 24000
_MAX_SOURCE_ROWS = 30
_MAX_ISSUES = 12


def _logic_block(bundle: dict[str, Any], logic_id: str) -> dict[str, Any] | None:
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            return lb
    return None


def _logic_review_item(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    for row in bundle.get("logic_review_items") or []:
        if str(row.get("logic_id") or "") == logic_id:
            return row
    return {}


def _issues_for_logic(bundle: dict[str, Any], logic_id: str, control_name: str) -> list[dict[str, Any]]:
    keys = {logic_id, control_name}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in bundle.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        affected = {str(x) for x in issue.get("affected_items") or []}
        if not (affected & keys):
            continue
        key = str(issue.get("id") or issue.get("message") or issue.get("type") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    item = _logic_review_item(bundle, logic_id)
    for issue in item.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        key = str(issue.get("id") or issue.get("message") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out[:_MAX_ISSUES]


def _missing_definitions(bundle: dict[str, Any], logic_id: str) -> list[str]:
    lb = _logic_block(bundle, logic_id) or {}
    terms = [str(x).strip() for x in lb.get("unresolved_refs") or [] if str(x).strip()]
    item = _logic_review_item(bundle, logic_id)
    for row in item.get("term_trace") or []:
        if not isinstance(row, dict):
            continue
        if row.get("definitions") or row.get("engineer_definitions"):
            continue
        term = str(row.get("term") or "").strip()
        if term and term not in terms:
            terms.append(term)
    return terms[:16]


def _path_intent_label(trace: dict[str, Any]) -> str:
    parts = [
        str(trace.get("path_id") or "").strip(),
        str(trace.get("logic_branch") or "").strip(),
        str(trace.get("mcdc_role") or "").strip(),
    ]
    return " · ".join(p for p in parts if p) or "—"


def _format_issues_section(issues: list[dict[str, Any]]) -> list[str]:
    if not issues:
        return []
    lines = ["## Open issues (do not ignore)", ""]
    for issue in issues:
        sev = str(issue.get("display_severity") or issue.get("severity") or "warning")
        itype = str(issue.get("type") or issue.get("code") or "issue")
        msg = str(issue.get("message") or issue.get("detail") or "").strip()
        reason = str(issue.get("parser_reason") or "").strip()
        line = f"- **{sev}** `{itype}`: {msg}"
        if reason:
            line += f" — _{reason[:160]}_"
        lines.append(line)
    lines.append("")
    return lines


def _format_missing_defs(terms: list[str]) -> list[str]:
    if not terms:
        return []
    lines = ["## Missing definitions", "", "Add `definition_updates` in JSON for these terms:", ""]
    for term in terms:
        lines.append(f"- `{term}`")
    lines.append("")
    return lines


def _format_source_table(item: dict[str, Any]) -> list[str]:
    rows = item.get("table_rows") or []
    if not rows:
        return []
    lines = [
        "## Source table excerpt (authoritative)",
        "",
        "Cite row numbers when explaining Given values. Do not invent structure beyond this table.",
        "",
        "| row | depth | condition | parser |",
        "|-----|-------|-----------|--------|",
    ]
    for row in rows[:_MAX_SOURCE_ROWS]:
        if not isinstance(row, dict):
            continue
        rno = row.get("row_no", "")
        depth = row.get("depth", "")
        cond = str(row.get("raw_condition") or "").replace("|", "\\|").replace("\n", " ")[:120]
        parser = str(row.get("parser_reason") or row.get("detected_type") or "")[:60]
        lines.append(f"| {rno} | {depth} | {cond} | {parser} |")
    if len(rows) > _MAX_SOURCE_ROWS:
        lines.append("")
        lines.append(f"_({len(rows) - _MAX_SOURCE_ROWS} more rows omitted)_")
    lines.append("")
    return lines


def _format_tree_section(item: dict[str, Any], lb: dict[str, Any]) -> list[str]:
    tree_lines = item.get("tree_lines") or []
    if not tree_lines:
        tree = lb.get("tree") or {}
        if tree.get("type") and tree.get("type") != "empty":
            tree_lines = render_tree_lines(tree)
    if not tree_lines:
        return []
    lines = ["## Condition tree (parser view)", "", "```"]
    lines.extend(str(line)[:200] for line in tree_lines[:40])
    lines.append("```")
    lines.append("")
    return lines


def build_copilot_brief(
    bundle: dict[str, Any],
    logic_id: str,
    engineer_note: str,
    *,
    candidate_id: str | None = None,
) -> str:
    """Markdown brief for paste into Word/Teams M365 Copilot."""
    lb = _logic_block(bundle, logic_id) or {}
    item = _logic_review_item(bundle, logic_id)
    expression = str(
        lb.get("raw_expression") or lb.get("expression") or item.get("raw_expression") or item.get("expression") or ""
    )
    control = str(lb.get("name") or item.get("control_name") or logic_id)
    parse_status = str(item.get("parse_status") or lb.get("parse_status") or "unknown")
    snapshot = {r["candidate_id"]: r for r in compliance_snapshot(bundle, logic_id)}

    lines = [
        "# ALEX — M365 Copilot knowledge brief",
        "",
        f"**Logic block:** `{logic_id}` · **Control:** `{control}` · **Parse:** `{parse_status}`",
        "",
        "## Logic expression",
        "```",
        expression[:8000],
        "```",
        "",
    ]
    lines.extend(_format_issues_section(_issues_for_logic(bundle, logic_id, control)))
    lines.extend(_format_missing_defs(_missing_definitions(bundle, logic_id)))
    lines.extend(_format_source_table(item))
    lines.extend(_format_tree_section(item, lb))
    lines.extend(
        [
            "## Engineer knowledge (apply to each test case)",
            engineer_note.strip() or "(none — add signal meanings and ranges in ALEX before copying)",
            "",
            "## Test cases",
            "",
            "Apply engineer knowledge to **each** `candidate_id`. Respect path intent (pass vs fail branch).",
            "",
            "| candidate_id | path intent | logic_comply | missing_signals | current Given | expected output |",
            "|--------------|-------------|--------------|-----------------|---------------|-----------------|",
        ]
    )

    tc_written = 0
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or "")
        if candidate_id and cid != candidate_id:
            continue
        comp = snapshot.get(cid) or {}
        path = _path_intent_label(trace if isinstance(trace, dict) else {})
        given = materialize_expected_input(cand, bundle=bundle).replace("\n", "; ")[:200]
        out = materialize_expected_output(cand).replace("\n", "; ")[:120]
        missing = ", ".join(comp.get("missing_signals") or [])[:80]
        lines.append(
            f"| {cid} | {path} | {comp.get('logic_comply', '')} | {missing} | {given} | {out} |"
        )
        tc_written += 1

    if candidate_id and tc_written == 0:
        lines.append(f"| _none_ | — | — | — | — | candidate `{candidate_id}` not found |")

    lines.extend(
        [
            "",
            "## Required JSON response",
            "",
            "Copy **only** this JSON shape back into ALEX (Import M365 response):",
            "",
            "```json",
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": "TC_PM_xxx",
                            "given": [{"signal": "SIG", "value": "0"}],
                            "note": "short reason citing row or path intent",
                        }
                    ],
                    "definition_updates": [{"name": "TERM", "definition": "plain text or =value"}],
                },
                indent=2,
            ),
            "```",
            "",
            "Rules:",
            "- One value per signal per test case.",
            "- Respect MCDC path intent (do not break branch purpose).",
            "- Apply engineer knowledge (ranges, when X then Y, equalities).",
            "- Use concrete numeric/boolean values only in `given`.",
            "- Cite source table row numbers in `note` when possible.",
            "- If evidence is insufficient, add `open_questions` array instead of guessing.",
            "",
            "## Boundary-value rules (ranges)",
            "",
            "When engineer note says `SIG=100 to 200 km/h` (or similar range):",
            "- For a test case that must **satisfy** the range/guard: use an in-range value (e.g. 101, 150).",
            "- For a test case that must **fail** the upper bound: use just above max (e.g. 201 if max is 200).",
            "- For a test case that must **fail** the lower bound: use just below min (e.g. 99 if min is 100).",
            "- Split across **existing** candidate_id rows by path intent; do not invent new IDs unless asked.",
        ]
    )

    text = "\n".join(lines)
    if len(text) > BRIEF_CHAR_LIMIT:
        text = text[: BRIEF_CHAR_LIMIT - 120].rstrip()
        text += "\n\n---\n_Brief truncated for Copilot size limit. Re-run Copy brief after fixing blockers._"
    return text


def parse_knowledge_patches_payload(raw: str) -> list[dict[str, Any]]:
    """Parse JSON from M365 Copilot paste (fenced or raw)."""
    text = (raw or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in pasted text")
    parsed = json.loads(text[start : end + 1])
    if isinstance(parsed, list):
        return parsed
    candidates = parsed.get("candidates")
    if isinstance(candidates, list):
        return candidates
    raise ValueError("JSON must contain a candidates array")
