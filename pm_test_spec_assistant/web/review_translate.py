"""Ollama translation for final workbook rows (EN → JP overlays)."""

from __future__ import annotations

import json
from typing import Any

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

from web.llm_assist import llm_enabled_for_assist, ollama_status, run_ollama_assist


def _translate_row_prompt(row: dict[str, Any]) -> str:
    return (
        "Translate these automotive test specification fields from English to Japanese.\n"
        "Rules:\n"
        "- Keep line-oriented structure (Given:, Then:, Precondition: prefixes where present).\n"
        "- Keep signal / variable names in ASCII (e.g. OK_SHUTOFF, VEHICLE_STOPPED).\n"
        "- Do not add markdown or commentary.\n"
        "Return JSON only:\n"
        '{"use_case":"...","operation":"...","expected_input":"...","expected_output":"..."}\n\n'
        f"UseCase:\n{row.get('use_case') or ''}\n\n"
        f"Operation:\n{row.get('operation') or ''}\n\n"
        f"Expected input:\n{row.get('expected_input') or ''}\n\n"
        f"Expected output:\n{row.get('expected_output') or ''}\n"
    )


def translate_workbook_with_ollama(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    target_language: str = "JP",
) -> dict[str, Any]:
    target = str(target_language or "JP").upper()
    if target != "JP":
        return {"ok": False, "error": "Only Japanese (JP) translation is supported."}
    if not llm_enabled_for_assist(cfg):
        return {"ok": False, "error": "Ollama assist is disabled in config."}
    if not ollama_status(cfg).get("reachable"):
        return {"ok": False, "error": "Ollama is not reachable. Start Ollama and enable llm/ollama_assist in config."}

    preview = build_customer_testspec_preview(bundle, language="EN")
    rows = preview.get("rows") or []
    if not rows:
        return {"ok": False, "error": "No workbook rows to translate."}

    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    updated = 0
    errors: list[dict[str, str]] = []

    for row in rows:
        cid = str(row.get("candidate_id") or "").strip()
        if not cid:
            continue
        out = run_ollama_assist(_translate_row_prompt(row), cfg)
        if not out.get("ok"):
            errors.append({"candidate_id": cid, "error": str(out.get("error") or "ollama failed")})
            continue
        parsed = out.get("result")
        if not isinstance(parsed, dict):
            try:
                parsed = json.loads(str(parsed))
            except (TypeError, json.JSONDecodeError):
                errors.append({"candidate_id": cid, "error": "invalid JSON from Ollama"})
                continue
        overlay = dict(overlays.get(cid) or {})
        jp = dict(overlay.get("jp") or {})
        changed = False
        for field in ("use_case", "operation", "expected_input", "expected_output"):
            val = parsed.get(field)
            if val is None:
                continue
            text = str(val).strip()
            if text:
                jp[field] = text
                changed = True
        if not changed:
            errors.append({"candidate_id": cid, "error": "empty translation"})
            continue
        overlay["jp"] = jp
        overlay["provider"] = "ollama_translate"
        overlay["translation_target"] = "JP"
        overlays[cid] = overlay
        updated += 1

    return {
        "ok": updated > 0,
        "provider": "ollama",
        "target_language": target,
        "rows_total": len(rows),
        "rows_updated": updated,
        "errors": errors,
    }
