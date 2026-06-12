"""Explicit mechanical text replace — no natural-language parsing."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.parsers.code_parser import import_blocks_to_draft_map, index_alex_blocks, wrap_alex_block

_INCLUDE_RE = re.compile(r"^\s*#include\s+[<\"][^>\"]+[>\"]\s*$")
_ALEX_MARKER_RE = re.compile(
    r"^\s*//\s*@alex:(?:begin|end|spec_hash)\b[^\n]*\n?",
    re.MULTILINE,
)


def _strip_alex_markers(text: str) -> tuple[str, int]:
    """Strip // @alex:begin / @alex:spec_hash / @alex:end lines from exported code.

    Returns (cleaned_text, count_stripped). Only removes internal tracker lines;
    ALEX_REVIEW comments and user comments are preserved.
    """
    matches = _ALEX_MARKER_RE.findall(text)
    cleaned = _ALEX_MARKER_RE.sub("", text)
    return cleaned.strip(), len(matches)


def apply_text_replace(text: str, *, src: str, dst: str) -> tuple[str, int]:
    """Replace all occurrences; return (new_text, count)."""
    if not src:
        return text, 0
    count = text.count(src)
    if count == 0:
        return text, 0
    return text.replace(src, dst), count


def _split_snippet(full: str) -> tuple[str, str]:
    body_start = full.find("TEST_F(")
    if body_start > 0:
        return full[:body_start].strip(), full[body_start:].strip()
    if body_start == 0:
        return "", full.strip()
    return full.strip(), ""


def _merge_snippet(spec_block: str, code_body: str) -> str:
    parts = [p for p in (spec_block.strip(), code_body.strip()) if p]
    return "\n".join(parts)


def apply_replace_to_draft(draft: dict[str, Any], *, src: str, dst: str) -> tuple[dict[str, Any], int]:
    """Apply replace across full_snippet, spec_comment_block, and code_body."""
    total = 0
    out = dict(draft)
    full = str(out.get("full_snippet") or "").strip()
    spec = str(out.get("spec_comment_block") or "").strip()
    body = str(out.get("code_body") or "").strip()

    if full:
        new_full, n = apply_text_replace(full, src=src, dst=dst)
        if n:
            total += n
            out["full_snippet"] = new_full
            spec, body = _split_snippet(new_full)
            out["spec_comment_block"] = spec
            out["code_body"] = body
    else:
        if spec:
            new_spec, n = apply_text_replace(spec, src=src, dst=dst)
            if n:
                total += n
                out["spec_comment_block"] = new_spec
                spec = new_spec
        if body:
            new_body, n = apply_text_replace(body, src=src, dst=dst)
            if n:
                total += n
                out["code_body"] = new_body
                body = new_body
        if spec or body:
            out["full_snippet"] = _merge_snippet(spec, body)

    return out, total


def apply_replace_to_gtest_state(
    gtest_state: dict[str, Any],
    *,
    src: str,
    dst: str,
    candidate_ids: list[str] | None = None,
    current_snippet: str = "",
    current_candidate_id: str = "",
) -> dict[str, Any]:
    """Batch-apply explicit find/replace to saved drafts."""
    drafts = dict(gtest_state.get("drafts") or {})
    targets = list(candidate_ids or [])
    if current_candidate_id and current_candidate_id not in targets:
        targets.append(current_candidate_id)

    per_candidate: list[dict[str, Any]] = []
    total_replacements = 0
    touched = 0

    for cid in targets:
        draft = dict(drafts.get(cid) or {})
        if cid == current_candidate_id and current_snippet.strip():
            draft = {**draft, "full_snippet": current_snippet.strip()}
        if not (draft.get("full_snippet") or draft.get("code_body") or draft.get("spec_comment_block")):
            per_candidate.append({"candidate_id": cid, "ok": True, "replacements": 0, "skipped": True})
            continue
        updated, count = apply_replace_to_draft(draft, src=src, dst=dst)
        if count:
            touched += 1
            total_replacements += count
            full = str(updated.get("full_snippet") or "").strip()
            if full:
                spec, body = _split_snippet(full)
                updated["spec_comment_block"] = spec
                updated["code_body"] = body
            drafts[cid] = {**updated, "source_kind": updated.get("source_kind") or "local_replace"}
        per_candidate.append({"candidate_id": cid, "ok": True, "replacements": count, "skipped": count == 0})

    gtest_state["drafts"] = drafts
    return {
        "ok": True,
        "provider": "local_replace",
        "from": src,
        "to": dst,
        "touched": touched,
        "total_replacements": total_replacements,
        "results": per_candidate,
        "current_draft": drafts.get(current_candidate_id) if current_candidate_id else None,
    }


def apply_replace_to_bundle(
    bundle: dict[str, Any],
    *,
    src: str,
    dst: str,
    candidate_ids: list[str] | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """Apply explicit find/replace to workbench I/O overlays (en + jp)."""
    ai = bundle.setdefault("ai_assists", {})
    overlays = dict(ai.get("candidate_overlays") or {})
    targets = set(candidate_ids or [])
    per_candidate: list[dict[str, Any]] = []
    total_replacements = 0
    touched = 0

    all_ids = targets if targets else {str(c.get("id") or "") for c in (bundle.get("test_candidates") or [])}
    for cid in sorted(x for x in all_ids if x):
        overlay = dict(overlays.get(cid) or {})
        count = 0
        for lang_key in ("en", "jp"):
            lang = dict(overlay.get(lang_key) or {})
            for field in ("expected_input", "expected_output", "use_case", "operation"):
                val = str(lang.get(field) or "")
                if not val or src not in val:
                    continue
                new_val, n = apply_text_replace(val, src=src, dst=dst)
                count += n
                if not preview and new_val != val:
                    lang[field] = new_val
            if lang:
                overlay[lang_key] = lang
        if count:
            touched += 1
            total_replacements += count
            if not preview:
                overlays[cid] = overlay
        per_candidate.append({"candidate_id": cid, "replacements": count, "skipped": count == 0})

    if not preview:
        ai["candidate_overlays"] = overlays
        bundle["ai_assists"] = ai

    return {
        "ok": True,
        "provider": "local_replace",
        "preview": preview,
        "from": src,
        "to": dst,
        "touched": touched,
        "total_replacements": total_replacements,
        "results": per_candidate,
    }


def preview_replace(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    src: str,
    dst: str,
    candidate_ids: list[str] | None = None,
    current_snippet: str = "",
    current_candidate_id: str = "",
) -> dict[str, Any]:
    """Count replacements without persisting — requires explicit from/to."""
    if not src or not dst or src == dst:
        return {"ok": False, "error": "from_text and to_text are required."}
    io = apply_replace_to_bundle(
        bundle,
        src=src,
        dst=dst,
        candidate_ids=candidate_ids,
        preview=True,
    )
    drafts = dict(gtest_state.get("drafts") or {})
    draft_hits = 0
    for cid in candidate_ids or []:
        draft = dict(drafts.get(cid) or {})
        if cid == current_candidate_id and current_snippet.strip():
            draft = {**draft, "full_snippet": current_snippet.strip()}
        _, n = apply_replace_to_draft(draft, src=src, dst=dst)
        draft_hits += n
    return {
        "ok": True,
        "from": src,
        "to": dst,
        "io_replacements": io.get("total_replacements", 0),
        "draft_replacements": draft_hits,
        "total_replacements": (io.get("total_replacements") or 0) + draft_hits,
    }


def _inner_snippet(full: str, candidate_id: str) -> str:
    text = str(full or "").strip()
    begin = f"// @alex:begin {candidate_id}"
    end = f"// @alex:end {candidate_id}"
    if begin in text and end in text:
        start = text.find(begin)
        end_pos = text.rfind(end)
        if end_pos > start:
            inner = text[start + len(begin) : end_pos].strip()
            if inner.startswith("// @alex:spec_hash"):
                inner = "\n".join(inner.splitlines()[1:]).strip()
            return inner
    return text


def wrap_draft_markers(candidate_id: str, draft: dict[str, Any], *, spec_hash: str = "") -> dict[str, Any]:
    cid = str(candidate_id or "").strip()
    out = dict(draft)
    full = str(out.get("full_snippet") or "").strip()
    if not full:
        spec = str(out.get("spec_comment_block") or "").strip()
        body = str(out.get("code_body") or "").strip()
        full = _merge_snippet(spec, body)
    inner = _inner_snippet(full, cid) if f"// @alex:begin {cid}" in full else full
    sh = spec_hash or str(out.get("spec_hash") or "")
    out["full_snippet"] = wrap_alex_block(cid, inner, spec_hash=sh)
    out["spec_hash"] = sh
    spec, body = _split_snippet(inner)
    out["spec_comment_block"] = spec
    out["code_body"] = body
    return out


def delete_drafts(gtest_state: dict[str, Any], candidate_ids: list[str]) -> dict[str, Any]:
    drafts = dict(gtest_state.get("drafts") or {})
    index = dict(gtest_state.get("tc_code_index") or {})
    deleted: list[str] = []
    for cid in candidate_ids:
        if cid in drafts:
            del drafts[cid]
            deleted.append(cid)
        index.pop(cid, None)
    gtest_state["drafts"] = drafts
    gtest_state["tc_code_index"] = index
    return {"ok": True, "deleted": deleted, "count": len(deleted)}


def import_monolith_to_drafts(gtest_state: dict[str, Any], text: str) -> dict[str, Any]:
    draft_map = import_blocks_to_draft_map(text)
    drafts = dict(gtest_state.get("drafts") or {})
    index = dict(gtest_state.get("tc_code_index") or {})
    imported: list[str] = []
    for cid, draft in draft_map.items():
        drafts[cid] = {**draft, "updated_at": draft.get("updated_at") or ""}
        block = next((b for b in index_alex_blocks(text) if b["candidate_id"] == cid), None)
        if block:
            index[cid] = {
                "line_start": block["line_start"],
                "line_end": block["line_end"],
                "spec_hash": block.get("spec_hash") or "",
            }
        imported.append(cid)
    gtest_state["drafts"] = drafts
    gtest_state["tc_code_index"] = index
    return {"ok": True, "imported": imported, "count": len(imported)}


def merge_drafts_to_monolith(
    gtest_state: dict[str, Any],
    bundle: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
) -> str:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    rows = preview.get("rows") or []
    order = {str(r.get("candidate_id") or ""): int(r.get("no") or 0) if str(r.get("no") or "").isdigit() else 999999 for r in rows}
    drafts = gtest_state.get("drafts") or {}
    ids = list(candidate_ids) if candidate_ids else sorted(drafts.keys(), key=lambda c: (order.get(c, 999999), c))
    parts: list[str] = []
    for cid in ids:
        draft = drafts.get(cid)
        if not draft:
            continue
        full = str(draft.get("full_snippet") or "").strip()
        if not full:
            continue
        if f"// @alex:begin {cid}" not in full:
            sh = str(draft.get("spec_hash") or "")
            full = wrap_alex_block(cid, full, spec_hash=sh)
        parts.append(full)
    return "\n\n".join(parts) + ("\n" if parts else "")


def _dedupe_includes_merge(parts: list[str]) -> str:
    seen: set[str] = set()
    include_lines: list[str] = []
    bodies: list[str] = []
    for part in parts:
        body_lines: list[str] = []
        for line in part.splitlines():
            stripped = line.strip()
            if _INCLUDE_RE.match(stripped):
                if stripped not in seen:
                    seen.add(stripped)
                    include_lines.append(stripped)
            else:
                body_lines.append(line)
        bodies.append("\n".join(body_lines).strip())
    bodies = [b for b in bodies if b]
    chunks: list[str] = []
    if include_lines:
        chunks.append("\n".join(include_lines))
    if bodies:
        chunks.append("\n\n".join(bodies))
    return "\n".join(chunks) + ("\n" if chunks else "")


_TEST_SIG_RE = re.compile(r"\bTEST(?:_F)?\s*\([^)]+\)")


def _merge_skip_reason(
    draft: dict[str, Any],
    sync_status: str,
    *,
    require_engineer_approved: bool = False,
) -> str:
    full = str(draft.get("full_snippet") or draft.get("code_body") or "").strip()
    if not full:
        return "NO_CODE"
    code_status = str(draft.get("code_status") or "").upper()
    if code_status == "ERROR":
        return "ERROR"
    # Explicitly confirmed/exportable drafts bypass both code_status and sync staleness checks.
    # User confirmation is explicit approval — staleness does not block export.
    is_exportable = bool(draft.get("exportable"))
    approval_status = str(draft.get("approval_status") or "").upper()
    is_confirmed = approval_status in {"CONFIRMED", "APPROVED"}
    if not is_exportable and not is_confirmed:
        if code_status != "SAVED":
            if code_status == "MODIFIED_UNSAVED":
                return "MODIFIED_UNSAVED"
            if code_status == "NEEDS_REVIEW":
                return "NEEDS_REVIEW"
            return "DRAFT_NOT_SAVED"
        if sync_status in ("stale_comment", "stale_body", "orphan_code"):
            return "NEEDS_REVIEW"
    if require_engineer_approved and not draft.get("engineer_approved"):
        return "NOT_APPROVED"
    return "SAVED"


def merge_export_filename(job_id: str, *, timestamp: str | None = None) -> str:
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_job = re.sub(r"[^A-Za-z0-9_-]+", "_", str(job_id or "job"))[:48]
    return f"ALEX_GTest_{safe_job}_{ts}.cc"


def _block_body_signature(part: str) -> str:
    lines: list[str] = []
    for line in part.splitlines():
        stripped = line.strip()
        if stripped.startswith("// @alex:"):
            continue
        if _INCLUDE_RE.match(stripped):
            continue
        if stripped:
            lines.append(stripped)
    return re.sub(r"\s+", " ", "\n".join(lines).strip())


def _dedupe_test_blocks(parts: list[str]) -> tuple[list[str], list[str]]:
    seen_bodies: set[str] = set()
    seen_sigs: set[str] = set()
    kept: list[str] = []
    warnings: list[str] = []
    for part in parts:
        signature = _block_body_signature(part)
        if signature and signature in seen_bodies:
            warnings.append("Duplicate identical TEST block skipped during merge.")
            continue
        sigs = _TEST_SIG_RE.findall(part)
        dup_names = [s for s in sigs if s in seen_sigs]
        if dup_names:
            warnings.append(f"Duplicate test function name: {dup_names[0]}")
        for sig in sigs:
            seen_sigs.add(sig)
        if signature:
            seen_bodies.add(signature)
        kept.append(part)
    return kept, warnings


def merge_saved_code_preview(
    gtest_state: dict[str, Any],
    bundle: dict[str, Any],
    *,
    language: str = "EN",
    sync_map: dict[str, str] | None = None,
    timestamp: str | None = None,
    require_engineer_approved: bool = False,
    job_id: str = "",
) -> dict[str, Any]:
    """Merge drafts with code_status SAVED (and optionally engineer_approved) in import order."""
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    rows = preview.get("rows") or []
    ordered_ids = [
        str(r.get("candidate_id") or "")
        for r in sorted(
            rows,
            key=lambda r: (
                int(r.get("no") or 0) if str(r.get("no") or "").isdigit() else 999999,
                str(r.get("candidate_id") or ""),
            ),
        )
        if str(r.get("candidate_id") or "")
    ]
    drafts = gtest_state.get("drafts") or {}
    sync_map = sync_map or {}
    included: list[str] = []
    skipped: list[dict[str, str]] = []
    warnings: list[str] = []
    code_parts: list[str] = []
    code_field_used: dict[str, str] = {}

    for cid in ordered_ids:
        draft = drafts.get(cid) or {}
        sync_status = str(sync_map.get(cid) or "no_code")
        reason = _merge_skip_reason(
            draft, sync_status, require_engineer_approved=require_engineer_approved
        )
        if reason != "SAVED":
            skipped.append({"candidate_id": cid, "reason": reason})
            code_field_used[cid] = "full_snippet" if draft.get("full_snippet") else ("code_body" if draft.get("code_body") else "none")
            continue
        full = str(draft.get("full_snippet") or "").strip()
        if not full:
            body = str(draft.get("code_body") or "").strip()
            if body:
                spec = str(draft.get("spec_comment_block") or "").strip()
                full = _merge_snippet(spec, body)
                code_field_used[cid] = "code_body"
            else:
                code_field_used[cid] = "none"
        else:
            code_field_used[cid] = "full_snippet"
        if not full:
            skipped.append({"candidate_id": cid, "reason": "NO_CODE"})
            continue
        if f"// @alex:begin {cid}" not in full:
            sh = str(draft.get("spec_hash") or "")
            full = wrap_alex_block(cid, full, spec_hash=sh)
        full, _ = _strip_alex_markers(full)
        code_parts.append(full)
        included.append(cid)

    saved_quality_pass = 0
    saved_quality_warning = 0
    for cid in included:
        draft = drafts.get(cid) or {}
        qs = str(draft.get("quality_summary") or "PASS").upper()
        if qs == "WARNING":
            saved_quality_warning += 1
            rr = str(draft.get("review_reason") or "quality warnings")[:120]
            warnings.append(f"{cid}: SAVED with unresolved quality WARNING — {rr}")
        else:
            saved_quality_pass += 1

    code_parts, dedupe_warnings = _dedupe_test_blocks(code_parts)
    warnings.extend(dedupe_warnings)
    if skipped and included:
        warnings.append("Some testcases are not saved or have no code. Merge includes only SAVED code.")
    if saved_quality_warning:
        warnings.append(
            f"{saved_quality_warning} saved testcase(s) have quality WARNING; review before shipping merged file."
        )
    if not included:
        warnings.append("No saved testcase code available to merge.")

    confirmed_but_not_saved = [
        cid for cid in ordered_ids
        if str((drafts.get(cid) or {}).get("approval_status") or "").upper() in {"CONFIRMED", "APPROVED"}
        and str((drafts.get(cid) or {}).get("code_status") or "").upper() != "SAVED"
    ]
    exportable_cids = [
        cid for cid, d in drafts.items()
        if isinstance(d, dict) and d.get("exportable")
    ]
    confirmed_cids = [
        cid for cid, d in drafts.items()
        if isinstance(d, dict)
        and str(d.get("approval_status") or "").upper() in {"CONFIRMED", "APPROVED"}
    ]
    skipped_empty_code_cids = [s["candidate_id"] for s in skipped if s["reason"] == "NO_CODE"]
    skipped_not_confirmed_cids = [s["candidate_id"] for s in skipped if s["reason"] != "NO_CODE"]
    non_empty_code_count = sum(
        1 for d in drafts.values()
        if isinstance(d, dict) and str(d.get("full_snippet") or d.get("code_body") or "").strip()
    )
    approval_status_by_testcase = {
        cid: str((drafts.get(cid) or {}).get("approval_status") or "")
        for cid in ordered_ids
    }
    exportable_by_testcase = {
        cid: bool((drafts.get(cid) or {}).get("exportable"))
        for cid in ordered_ids
    }

    # Count total @alex markers stripped across all included code parts
    stripped_alex_marker_count = sum(
        len(_ALEX_MARKER_RE.findall(p)) for p in code_parts
    )

    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        "/*\n"
        " * generated by ALEX\n"
        f" * timestamp: {ts}\n"
        f" * confirmed testcase count: {len(included)}\n"
        f" * skipped testcase count: {len(skipped)}\n"
        " */\n"
    )
    merged = header + _dedupe_includes_merge(code_parts)
    export_name = merge_export_filename(job_id)
    return {
        "ok": True,
        "content": merged,
        "included": included,
        "skipped": skipped,
        "warnings": warnings,
        "total_count": len(ordered_ids),
        "total_drafts": len(drafts),
        "non_empty_code_count": non_empty_code_count,
        "saved_count": len(included),
        "skipped_count": len(skipped),
        "warning_count": len(warnings),
        "timestamp": ts,
        "export_filename": export_name,
        "require_engineer_approved": require_engineer_approved,
        "export_included_count": len(included),
        "exportable_count": len(exportable_cids),
        "confirmed_count": len(confirmed_cids),
        "included_testcases": included,
        "skipped_empty_code": skipped_empty_code_cids,
        "skipped_not_confirmed": skipped_not_confirmed_cids,
        "stripped_alex_marker_count": stripped_alex_marker_count,
        "skipped_reason_by_testcase": {s["candidate_id"]: s["reason"] for s in skipped},
        "code_field_used_by_testcase": code_field_used,
        "approval_status_by_testcase": approval_status_by_testcase,
        "exportable_by_testcase": exportable_by_testcase,
        "confirmed_but_not_saved_count": len(confirmed_but_not_saved),
        "merge_readiness": {
            "saved_quality_pass": saved_quality_pass,
            "saved_quality_warning": saved_quality_warning,
            "saved_total": len(included),
            "skipped_count": len(skipped),
        },
    }
