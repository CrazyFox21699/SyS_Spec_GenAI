"""M365 Copilot translation for final workbook rows (EN → JP overlays)."""

from __future__ import annotations

import json
from typing import Any

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

from web import m365_auth
from web.m365_copilot import M365CopilotNotEntitledError, improve_io_via_m365


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


def translate_workbook_with_m365(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    target_language: str = "JP",
) -> dict[str, Any]:
    target = str(target_language or "JP").upper()
    if target != "JP":
        return {"ok": False, "error": "Only Japanese (JP) translation is supported."}
    if not m365_auth.is_api_ready(cfg):
        return {
            "ok": False,
            "error": "Sign in to Microsoft 365 Copilot on the Review tab.",
            "reason": "not_signed_in",
        }
    if not m365_auth.is_copilot_chat_entitled():
        return {
            "ok": False,
            "error": "Microsoft 365 Copilot license required for translation.",
            "reason": "not_entitled",
        }

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
        try:
            out = improve_io_via_m365(cfg, _translate_row_prompt(row))
        except M365CopilotNotEntitledError as exc:
            return {"ok": False, "error": str(exc), "reason": "not_entitled"}
        if not out.get("ok"):
            errors.append({"candidate_id": cid, "error": str(out.get("error") or "M365 translation failed")})
            continue
        parsed = out.get("result")
        if not isinstance(parsed, dict):
            try:
                parsed = json.loads(str(parsed))
            except (TypeError, json.JSONDecodeError):
                errors.append({"candidate_id": cid, "error": "invalid JSON from Copilot"})
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
        overlay["provider"] = "m365_translate"
        overlay["translation_target"] = "JP"
        overlays[cid] = overlay
        updated += 1

    return {
        "ok": updated > 0,
        "provider": "m365",
        "target_language": target,
        "rows_total": len(rows),
        "rows_updated": updated,
        "errors": errors,
    }


# Backward-compatible alias for imports/tests
translate_workbook_with_ollama = translate_workbook_with_m365
