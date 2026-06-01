"""Build AI batch review pack text (no external API calls)."""

from __future__ import annotations

from typing import Any

from web.project_code_config import CONFIG_FILES


def build_ai_batch_review_pack(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str],
    config: dict[str, Any],
    change_request: str = "",
    language: str = "EN",
) -> dict[str, Any]:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    files = config.get("files") or {}
    preview = build_customer_testspec_preview(bundle, language=language)
    row_by_id = {str(r.get("candidate_id") or ""): r for r in preview.get("rows") or []}
    drafts = gtest_state.get("drafts") or {}
    lines: list[str] = [
        "# ALEX AI Batch Review Pack",
        "",
        "Do not apply patches automatically. Respond using the sections below only.",
        "",
        "## Required output format",
        "",
    ]
    template = str((files.get("ai_review_pack.md") or {}).get("content") or CONFIG_FILES["ai_review_pack.md"]["default"])
    lines.append(template.strip())
    lines.append("")
    lines.append("## code_rules.md (summary)")
    lines.append("```")
    lines.append(str((files.get("code_rules.md") or {}).get("content") or "")[:4000])
    lines.append("```")
    lines.append("")
    lines.append("## api_catalog.yaml (summary)")
    lines.append("```")
    lines.append(str((files.get("api_catalog.yaml") or {}).get("content") or "")[:2000])
    lines.append("```")
    lines.append("")
    if change_request.strip():
        lines.append("## Batch Change Request")
        lines.append(change_request.strip())
        lines.append("")

    lines.append("## Testcases")
    for cid in candidate_ids:
        row = row_by_id.get(cid) or {}
        draft = drafts.get(cid) or {}
        lines.append(f"\n### {cid} — {row.get('event') or row.get('test_function') or ''}")
        lines.append(f"- workflow: {draft.get('code_status') or 'NO_CODE'}")
        lines.append(f"- quality: {draft.get('quality_summary') or '—'}")
        lines.append(f"- source: {draft.get('generation_source') or '—'}")
        if draft.get("review_reason"):
            lines.append(f"- review_reason: {draft.get('review_reason')}")
        if draft.get("mapping_missing"):
            lines.append(f"- missing_mapping: {', '.join(draft.get('mapping_missing') or [])}")
        lines.append("")
        lines.append("#### Spec I/O")
        lines.append("```")
        lines.append(str(row.get("expected_input") or "")[:2000])
        lines.append(str(row.get("expected_output") or "")[:2000])
        lines.append("```")
        lines.append("")
        code = str(draft.get("full_snippet") or draft.get("code_body") or "").strip()
        if code:
            lines.append("#### Generated code")
            lines.append("```cpp")
            lines.append(code[:12000])
            lines.append("```")
        qchecks = draft.get("quality_results") or []
        warns = [c for c in qchecks if c.get("severity") in ("WARNING", "FAIL")]
        if warns:
            lines.append("#### Quality warnings")
            for c in warns[:20]:
                lines.append(f"- [{c.get('severity')}] {c.get('check_name')}: {c.get('message')}")
        lines.append("")

    text = "\n".join(lines)
    return {"ok": True, "content": text, "testcase_count": len(candidate_ids), "char_count": len(text)}
