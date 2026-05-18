"""Unified AI provider router: M365 manual/API, Ollama fallback, validation loop."""

from __future__ import annotations

from typing import Any

from web import m365_auth
from web.knowledge_validation import apply_patches_with_validation, dedupe_only
from web.llm_assist import (
    assist_io_fill_prompt,
    knowledge_apply_prompt,
    llm_enabled_for_assist,
    ollama_status,
    resolve_definition_with_ollama,
    run_assist,
    run_ollama_assist,
    candidates_for_knowledge_apply,
)
from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload
from web.m365_copilot import apply_knowledge_via_m365


def _assist_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}


def default_provider(cfg: dict[str, Any]) -> str:
    return str(_assist_cfg(cfg).get("default_provider") or "m365")


def require_m365_login(cfg: dict[str, Any]) -> bool:
    return bool(_assist_cfg(cfg).get("require_m365_login", True))


def allow_ollama_fallback(cfg: dict[str, Any]) -> bool:
    return bool(_assist_cfg(cfg).get("allow_ollama_fallback", True))


def validation_retries(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("validation_retries", 1))


def knowledge_batch_size(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("knowledge_batch_size", 15))


def _chunk(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        return [items] if items else []
    return [items[i : i + size] for i in range(0, len(items), size)]


def _logic_expression(bundle: dict[str, Any], logic_id: str) -> str:
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            return str(lb.get("raw_expression") or lb.get("expression") or "")
    return ""


def infer_knowledge_patches_ollama(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    candidate_subset: list[dict[str, Any]] | None = None,
    failure_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Single Ollama call for a batch of candidates."""
    candidates = candidate_subset or _candidates_for_knowledge_apply(bundle, logic_id)
    if not candidates:
        return {"ok": True, "patches": []}
    note = engineer_note.strip()
    if failure_context:
        import json

        note += "\n\nFix logic_compliance failures (one value per signal):\n"
        note += json.dumps(failure_context[:25], ensure_ascii=False)[:4000]
    prompt = knowledge_apply_prompt(
        logic_id=logic_id,
        engineer_note=note,
        logic_expression=_logic_expression(bundle, logic_id),
        candidates=candidates,
    )
    out = run_ollama_assist(prompt, cfg)
    if not out.get("ok"):
        return out
    parsed = out.get("result") if isinstance(out.get("result"), dict) else {}
    patches = parsed.get("candidates") if isinstance(parsed.get("candidates"), list) else []
    return {"ok": True, "patches": patches, "model": out.get("model")}


def apply_knowledge_ollama_batched(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
) -> dict[str, Any]:
    """Deterministic orchestrator: batch Ollama calls, then validation loop with one retry."""
    all_candidates = candidates_for_knowledge_apply(bundle, logic_id, limit=200)
    batches = _chunk(all_candidates, knowledge_batch_size(cfg))
    all_patches: list[dict[str, Any]] = []
    model = ""
    for batch in batches:
        out = infer_knowledge_patches_ollama(
            bundle,
            cfg,
            logic_id=logic_id,
            engineer_note=engineer_note,
            candidate_subset=batch,
        )
        if not out.get("ok"):
            return {
                "ok": False,
                "provider": "ollama",
                "error": out.get("error"),
                "candidates_updated": 0,
            }
        all_patches.extend(out.get("patches") or [])
        model = str(out.get("model") or model)

    def retry_infer(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fail_ids = {f.get("candidate_id") for f in failures}
        subset = [c for c in all_candidates if c.get("candidate_id") in fail_ids]
        if not subset:
            return []
        out = infer_knowledge_patches_ollama(
            bundle,
            cfg,
            logic_id=logic_id,
            engineer_note=engineer_note,
            candidate_subset=subset,
            failure_context=failures,
        )
        return out.get("patches") or [] if out.get("ok") else []

    result = apply_patches_with_validation(
        bundle,
        logic_id,
        all_patches,
        source="ollama_knowledge",
        validation_retries=validation_retries(cfg),
        retry_infer=retry_infer if validation_retries(cfg) > 0 else None,
    )
    ai = bundle.setdefault("ai_assists", {})
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": "ollama",
        "model": model,
        "patches": all_patches[:40],
        "batches": len(batches),
        **result,
    }
    return {
        "ok": True,
        "provider": "ollama",
        "model": model,
        "candidates_updated": result.get("candidates_updated", 0),
        "failures_remaining": result.get("failures_remaining", 0),
        "retries_used": result.get("retries_used", 0),
    }


def apply_knowledge_m365(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
) -> dict[str, Any]:
    """Apply knowledge strictly via signed-in M365 Copilot Chat API."""
    if not m365_auth.is_api_ready(cfg):
        return {
            "ok": False,
            "provider": "m365",
            "error": "Sign in to Microsoft 365 Copilot first (Sign in M365 button).",
            "candidates_updated": 0,
        }

    def run_apply(failures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return apply_knowledge_via_m365(
            bundle,
            cfg,
            logic_id=logic_id,
            engineer_note=engineer_note,
            failure_context=failures,
        )

    out = run_apply()
    if not out.get("ok"):
        return {
            "ok": False,
            "provider": "m365",
            "error": out.get("error") or "M365 Copilot request failed",
            "candidates_updated": 0,
        }
    patches = out.get("patches") or []

    def retry_m365(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        retry = run_apply(failures)
        return retry.get("patches") or [] if retry.get("ok") else []

    result = apply_patches_with_validation(
        bundle,
        logic_id,
        patches,
        source="m365_copilot",
        validation_retries=validation_retries(cfg),
        retry_infer=retry_m365 if validation_retries(cfg) > 0 else None,
    )
    ai = bundle.setdefault("ai_assists", {})
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": "m365",
        "patches": patches[:40],
        "definition_updates": out.get("definition_updates") or [],
        **result,
    }
    return {
        "ok": True,
        "provider": "m365",
        "candidates_updated": result.get("candidates_updated", 0),
        "failures_remaining": result.get("failures_remaining", 0),
        "retries_used": result.get("retries_used", 0),
        "definition_updates": len(out.get("definition_updates") or []),
    }


def apply_knowledge(
    bundle: dict[str, Any],
    logic_id: str,
    note: str,
    cfg: dict[str, Any],
    *,
    force_ollama: bool = False,
) -> dict[str, Any]:
    """Apply engineer knowledge — M365 Copilot when signed in (strict procedure)."""
    engineer_note = (note or "").strip()
    if not engineer_note:
        deduped = dedupe_only(bundle, logic_id)
        return {
            "provider": "none",
            "candidates_updated": deduped.get("candidates_updated", 0),
            "failures_remaining": deduped.get("failures_remaining", 0),
        }

    use_ollama = force_ollama and allow_ollama_fallback(cfg) and llm_enabled_for_assist(cfg)
    if use_ollama and ollama_status(cfg).get("reachable"):
        out = apply_knowledge_ollama_batched(bundle, cfg, logic_id=logic_id, engineer_note=engineer_note)
        if out.get("ok"):
            return out

    if require_m365_login(cfg) or default_provider(cfg) in ("m365", "m365_api"):
        return apply_knowledge_m365(bundle, cfg, logic_id=logic_id, engineer_note=engineer_note)

    if allow_ollama_fallback(cfg) and llm_enabled_for_assist(cfg) and ollama_status(cfg).get("reachable"):
        out = apply_knowledge_ollama_batched(bundle, cfg, logic_id=logic_id, engineer_note=engineer_note)
        if out.get("ok"):
            return out

    deduped = dedupe_only(bundle, logic_id)
    return {
        "ok": False,
        "provider": "m365",
        "candidates_updated": deduped.get("candidates_updated", 0),
        "failures_remaining": deduped.get("failures_remaining", 0),
        "error": "Sign in to Microsoft 365 Copilot to apply Knowledge workbench.",
    }


def import_knowledge_patches(
    bundle: dict[str, Any],
    logic_id: str,
    raw_json: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Apply pasted M365 Copilot JSON with validation loop."""
    patches = parse_knowledge_patches_payload(raw_json)

    def retry_infer(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if m365_auth.is_api_ready(cfg):
            retry = apply_knowledge_via_m365(
                bundle,
                cfg,
                logic_id=logic_id,
                engineer_note=str((bundle.get("ai_assists") or {}).get("engineer_notes", {}).get(logic_id) or ""),
                failure_context=failures,
            )
            return retry.get("patches") or [] if retry.get("ok") else []
        if allow_ollama_fallback(cfg) and llm_enabled_for_assist(cfg):
            out = infer_knowledge_patches_ollama(
                bundle,
                cfg,
                logic_id=logic_id,
                engineer_note=str((bundle.get("ai_assists") or {}).get("engineer_notes", {}).get(logic_id) or ""),
                failure_context=failures,
            )
            return out.get("patches") or [] if out.get("ok") else []
        return []

    result = apply_patches_with_validation(
        bundle,
        logic_id,
        patches,
        source="m365_copilot",
        validation_retries=validation_retries(cfg),
        retry_infer=retry_infer if validation_retries(cfg) > 0 else None,
    )
    ai = bundle.setdefault("ai_assists", {})
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": "m365_manual",
        "patches": patches[:40],
        **result,
    }
    return {
        "ok": True,
        "provider": "m365_manual",
        "candidates_updated": result.get("candidates_updated", 0),
        "failures_remaining": result.get("failures_remaining", 0),
        "retries_used": result.get("retries_used", 0),
        "patches_received": len(patches),
    }


def export_m365_brief(bundle: dict[str, Any], logic_id: str, note: str) -> dict[str, Any]:
    text = build_copilot_brief(bundle, logic_id, note)
    return {
        "logic_id": logic_id,
        "format": "markdown",
        "brief": text,
        "byte_size": len(text.encode("utf-8")),
    }


def resolve_definition(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    term: str,
    question: str,
) -> dict[str, Any]:
    if llm_enabled_for_assist(cfg) and ollama_status(cfg).get("reachable"):
        return resolve_definition_with_ollama(
            bundle, cfg, logic_id=logic_id, term=term, question=question
        )
    return {
        "ok": False,
        "error": "No AI available. Use M365 Copilot brief or enable Ollama.",
    }


def improve_io(
    cfg: dict[str, Any],
    *,
    candidate_id: str,
    expected_input: str,
    expected_output: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = assist_io_fill_prompt(
        candidate_id=candidate_id,
        expected_input=expected_input,
        expected_output=expected_output,
        issues=issues,
    )
    return run_assist(cfg, prompt)


def provider_status(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "default_provider": default_provider(cfg),
        "allow_ollama_fallback": allow_ollama_fallback(cfg),
        "validation_retries": validation_retries(cfg),
        "knowledge_batch_size": knowledge_batch_size(cfg),
        "ollama": ollama_status(cfg),
        "require_m365_login": require_m365_login(cfg),
        "m365": m365_auth.m365_status(cfg),
    }
