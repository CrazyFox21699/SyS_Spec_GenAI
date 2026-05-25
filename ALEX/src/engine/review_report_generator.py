"""Write human-readable review markdown from structured YAML artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def write_review_package(
    output_dir: Path,
    classified: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    state_doc: dict[str, Any],
    condition_trees: list[dict[str, Any]],
    timing: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    questions: list[str],
    *,
    logic_blocks: list[dict[str, Any]] | None = None,
    condition_definitions: list[dict[str, Any]] | None = None,
    test_reference_rows: list[dict[str, Any]] | None = None,
    ingest_skipped: list[dict[str, Any]] | None = None,
) -> None:
    review = output_dir / "review"
    review.mkdir(parents=True, exist_ok=True)

    (review / "01_file_classification.md").write_text(
        _md_file_classification(classified, ingest_skipped or []), encoding="utf-8"
    )
    (review / "02_extracted_signals.md").write_text(_md_signals(signals), encoding="utf-8")
    (review / "03_state_machine_review.md").write_text(_md_states(state_doc), encoding="utf-8")
    (review / "04_condition_tree_review.md").write_text(_md_conditions(condition_trees), encoding="utf-8")
    (review / "04b_logic_blocks.md").write_text(_md_logic_blocks(logic_blocks or []), encoding="utf-8")
    (review / "04c_condition_definitions.md").write_text(
        _md_condition_definitions(condition_definitions or []), encoding="utf-8"
    )
    (review / "05_timing_review.md").write_text(_md_timing(timing), encoding="utf-8")
    (review / "06_traceability_review.md").write_text(_md_trace(traceability, candidates), encoding="utf-8")
    (review / "07_test_scenario_candidates.md").write_text(_md_candidates(candidates), encoding="utf-8")
    (review / "08_test_reference_rows.md").write_text(
        _md_test_reference(test_reference_rows or []), encoding="utf-8"
    )
    (review / "review_questions.md").write_text(_md_questions(questions), encoding="utf-8")


def _md_file_classification(
    rows: list[dict[str, Any]], ingest_skipped: list[dict[str, Any]]
) -> str:
    lines = ["# File classification", "", "| File | Role | Confidence | User confirm? | Reasons |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        rs = "<br>".join(r.get("reason", [])[:6])
        lines.append(
            f"| `{r.get('file','')}` | {r.get('role')} | {r.get('confidence')} | "
            f"{'yes' if r.get('user_confirmation_suggested') else 'no'} | {rs} |"
        )
    if ingest_skipped:
        lines.extend(["", "## Skipped at ingest (not silently ignored)", ""])
        for s in ingest_skipped:
            lines.append(f"- `{s.get('file')}` — {s.get('reason', 'skipped')}")
    lines.extend(["", "## Notes", "- Roles are heuristic in v0.1; confirm especially for `unknown` or low confidence."])
    return "\n".join(lines) + "\n"


def _md_logic_blocks(blocks: list[dict[str, Any]]) -> str:
    lines = ["# Logic blocks (tables + paragraph formulas)", ""]
    for b in blocks:
        lines.append(f"## `{b.get('name')}` ({b.get('id')})")
        lines.append(f"- Type: {b.get('block_type')} | parse: {b.get('parse_status')}")
        if b.get("canonical"):
            lines.append("- **Canonical paragraph formula**")
        if b.get("superseded_by_formula"):
            lines.append(f"- Table differs from formula — prefer `{b.get('superseded_by_formula')}`")
        if b.get("matches_formula"):
            lines.append("- Matches paragraph formula")
        lines.append("")
        lines.append("**Expression:**")
        lines.append("```")
        lines.append(str(b.get("raw_expression", "")))
        lines.append("```")
        for w in b.get("table_warnings") or []:
            lines.append(f"- Warning: {w}")
        src = b.get("source") or {}
        lines.append(f"- Source: {src.get('file')} {src.get('table', src.get('kind', ''))}")
        lines.append("")
    if not blocks:
        lines.append("_No logic blocks extracted._\n")
    return "\n".join(lines)


def _md_condition_definitions(defs: list[dict[str, Any]]) -> str:
    lines = ["# Condition definitions", "", "| Condition | Definition | Source |", "| --- | --- | --- |"]
    for d in defs:
        src = d.get("source") or {}
        lines.append(
            f"| `{d.get('name')}` | {str(d.get('definition', ''))[:80]} | "
            f"{src.get('file', '')} {src.get('table', '')} row {src.get('row', '')} |"
        )
    if not defs:
        lines.append("| — | _none_ | — |")
    lines.append("")
    return "\n".join(lines)


def _md_test_reference(rows: list[dict[str, Any]]) -> str:
    lines = ["# Test reference rows (from spec tables)", "", "| ID | Given | When | Expected |", "| --- | --- | --- | --- |"]
    for r in rows:
        lines.append(
            f"| {r.get('id', '')} | {str(r.get('given', ''))[:60]} | "
            f"{str(r.get('when', ''))[:40]} | {str(r.get('expected', ''))[:60]} |"
        )
    if not rows:
        lines.append("| — | _none_ | — | — |")
    lines.append("")
    return "\n".join(lines)


def _md_signals(signals: list[dict[str, Any]]) -> str:
    lines = ["# Extracted signals (candidates)", ""]
    for s in signals:
        lines.append(f"## `{s.get('name','?')}`")
        lines.append(f"- Direction: {s.get('direction')}")
        lines.append(f"- Initial: {s.get('initial_value')}")
        lines.append(f"- Fail-safe: {s.get('fail_safe_value')}")
        lines.append(f"- Confidence: {s.get('confidence')} — review_required: {s.get('review_required')}")
        src = s.get("source") or {}
        lines.append(f"- Source: {src.get('file')} / {src.get('table') or src.get('section') or ''} row {src.get('row','')}")
        lines.append("")
    if not signals:
        lines.append("_No signals extracted; add Word/PDF tables or tune keywords._\n")
    return "\n".join(lines)


def _md_states(doc: dict[str, Any]) -> str:
    lines = ["# State machine review (candidates)", "", f"Source files: {', '.join(doc.get('source_files', []))}", ""]
    semantics = doc.get("diagram_semantics") or {}
    summary = semantics.get("summary") or {}
    if semantics.get("graph_built"):
        lines.append(
            f"Semantic graph: {summary.get('states_total', 0)} states, {summary.get('edges_total', 0)} edges "
            f"({summary.get('explicit_edges', 0)} explicit, {summary.get('rule_inferred_edges', 0)} rule-inferred)"
        )
        lines.append("")
    for st in doc.get("states", []):
        lines.append(f"- **{st.get('name')}** — {st.get('description','')} (mode: {st.get('mode')})")
    lines.append("")
    lines.append("## Transitions (raw extraction)")
    for t in doc.get("transitions", [])[:200]:
        lines.append(
            f"- `{t.get('id')}` {t.get('from_state')} → {t.get('to_state')} — cond: `{t.get('raw_condition','')[:120]}`"
        )
    if semantics.get("edges"):
        lines.append("")
        lines.append("## Semantic edges")
        for edge in semantics.get("edges", [])[:120]:
            lines.append(
                f"- {edge.get('from_state')} → {edge.get('to_state')} | event={edge.get('event')} "
                f"| type={edge.get('semantic_type')} | evidence={'; '.join(edge.get('evidence_refs', [])[:2])}"
            )
    return "\n".join(lines) + "\n"


def _md_conditions(items: list[dict[str, Any]]) -> str:
    lines = ["# Condition tree review", ""]
    for it in items:
        lines.append(f"## Transition `{it.get('transition_id','?')}`")
        lines.append("")
        lines.append("**Raw condition:**")
        lines.append("```")
        lines.append(str(it.get("raw_condition", "")))
        lines.append("```")
        lines.append("")
        lines.append("**Parsed tree (deterministic parser):**")
        lines.append("```yaml")
        lines.append(yaml.safe_dump(it.get("tree", {}), allow_unicode=True).strip())
        lines.append("```")
        lines.append("")
        if it.get("timing_normalizations"):
            lines.append("**Timing normalizations:**")
            for tn in it["timing_normalizations"]:
                lines.append(f"- `{tn.get('raw_text')}` → `{tn.get('interpreted_as')}` (review: {tn.get('review_required')})")
                reasons = tn.get("reason") or []
                if isinstance(reasons, str):
                    reasons = [reasons]
                for r in reasons:
                    lines.append(f"  - {r}")
        lines.append("")
    if not items:
        lines.append("_No condition trees; behavior workbook may lack parseable rows._\n")
    return "\n".join(lines)


def _md_timing(items: list[dict[str, Any]]) -> str:
    lines = ["# Timing review", ""]
    for t in items:
        lines.append(f"- **Raw:** `{t.get('raw_text')}`  → **Interpreted:** `{t.get('interpreted_as')}`")
        lines.append(f"  - confidence: {t.get('confidence')} | review_required: {t.get('review_required')}")
    if not items:
        lines.append("_No timing patterns matched._")
    lines.append("")
    return "\n".join(lines)


def _md_trace(trace: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    lines = ["# Traceability review", ""]
    for tr in trace:
        if "test_candidate_id" in tr:
            lines.append(f"## {tr.get('test_candidate_id')}")
            lines.append(f"- Signals: {tr.get('signals')}")
            lines.append(f"- Conditions: {tr.get('conditions')}")
            lines.append(f"- States: {tr.get('states')}")
            lines.append(f"- Outputs: {tr.get('outputs')}")
            lines.append(f"- Confidence: {tr.get('confidence')} | review: {tr.get('review_required')}")
            lines.append("")
    if not any("test_candidate_id" in tr for tr in trace):
        for c in candidates[:50]:
            lines.append(f"## {c.get('id')}")
            lines.append(f"- Why: {c.get('why_recommended')}")
            lines.append(f"- Trace: {c.get('traceability')}")
            lines.append("")
    return "\n".join(lines)


def _md_candidates(cands: list[dict[str, Any]]) -> str:
    lines = [
        "# Test scenario candidates",
        "",
        "| ID | Event | Description | Review |",
        "| --- | --- | --- | --- |",
    ]
    for c in cands:
        lines.append(
            f"| {c.get('id')} | {c.get('event')} | {str(c.get('use_case_description',''))[:120]} | "
            f"{'yes' if c.get('review_required') else 'no'} |"
        )
    lines.append("")
    for c in cands[:30]:
        lines.append(f"### {c.get('id')}")
        lines.append(f"- **Operation:** `{c.get('operation')}`")
        lines.append(f"- **Expectation:** `{c.get('expectation')}`")
        lines.append("")
    return "\n".join(lines)


def _md_questions(qs: list[str]) -> str:
    body = "\n".join(f"{i+1}. {q}" for i, q in enumerate(qs)) if qs else "_No auto-generated questions._"
    return "# Review questions\n\n" + body + "\n"
