"""Unified AI provider router — Microsoft 365 Copilot only."""

from __future__ import annotations

from typing import Any

from src.engine.testcase_reconciliation import build_reconciliation_plan
from web import m365_auth
from web.knowledge_patch_validation import validate_knowledge_patches
from web.knowledge_reconciliation import store_pending_knowledge_apply
from web.knowledge_validation import apply_patches_with_validation, dedupe_only
from web.llm_assist import (
    assist_io_fill_prompt,
    knowledge_apply_prompt,
)
from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload
from web.m365_copilot import (
    M365CopilotNotEntitledError,
    apply_knowledge_via_m365,
    improve_io_via_m365,
)


def _assist_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}


def default_provider(cfg: dict[str, Any]) -> str:
    return str(_assist_cfg(cfg).get("default_provider") or "m365")


def require_m365_login(cfg: dict[str, Any]) -> bool:
    return bool(_assist_cfg(cfg).get("require_m365_login", True))


def allow_ollama_fallback(cfg: dict[str, Any]) -> bool:
    return False


def validation_retries(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("validation_retries", 1))


def knowledge_batch_size(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("knowledge_batch_size", 15))


def normalize_provider_name(name: str) -> str:
    raw = str(name or "auto").strip().lower()
    if raw in ("m365", "m365_api", "microsoft", "auto", "ollama", "copilot", "copilot_cli", "github", "github_copilot"):
        return "m365"
    return "m365"


def _m365_usable(cfg: dict[str, Any]) -> bool:
    if not m365_auth.is_api_ready(cfg):
        return False
    return m365_auth.is_copilot_chat_entitled()


def resolve_knowledge_provider_chain(cfg: dict[str, Any], requested: str = "auto") -> list[str]:
    """Return provider chain — M365 Copilot only when signed in and entitled."""
    normalize_provider_name(requested)
    if _m365_usable(cfg):
        return ["m365"]
    return []


def _apply_knowledge_with_provider(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    provider: str,
    preview_only: bool = True,
) -> dict[str, Any]:
    if provider == "m365":
        return apply_knowledge_m365(
            bundle, cfg, logic_id=logic_id, engineer_note=engineer_note, preview_only=preview_only
        )
    return {"ok": False, "provider": provider, "error": "Only M365 Copilot is supported.", "candidates_updated": 0}


def _finalize_knowledge_patches(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    provider: str,
    cfg: dict[str, Any],
    source: str,
    preview_only: bool = True,
    definition_updates: list[dict[str, Any]] | None = None,
    retry_infer=None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store pending preview or apply patches immediately after validation."""
    schema = validate_knowledge_patches(patches, bundle, logic_id, cfg)
    if preview_only:
        if not schema.get("ok"):
            return {
                "ok": False,
                "preview": False,
                "provider": provider,
                "schema_errors": schema.get("errors") or [],
                "schema_warnings": schema.get("warnings") or [],
                "error": "; ".join(schema.get("errors") or []) or "Patch validation failed.",
                "candidates_updated": 0,
            }
        out = store_pending_knowledge_apply(
            bundle,
            logic_id,
            patches,
            provider=provider,
            source=source,
            definition_updates=definition_updates,
            cfg=cfg,
            schema_validation=schema,
        )
        if extra_meta:
            entry = (bundle.get("ai_assists") or {}).get("knowledge_apply", {}).get(logic_id) or {}
            entry.update(extra_meta)
        return out

    result = apply_patches_with_validation(
        bundle,
        logic_id,
        patches,
        source=source,
        validation_retries=validation_retries(cfg),
        retry_infer=retry_infer if validation_retries(cfg) > 0 else None,
    )
    ai = bundle.setdefault("ai_assists", {})
    reconciliation = build_reconciliation_plan(bundle, logic_id, patches, provider=provider)
    entry = {
        "provider": provider,
        "source": source,
        "status": "applied",
        "patches": patches[:80],
        "reconciliation": reconciliation,
        "definition_updates": definition_updates or [],
        **result,
    }
    if extra_meta:
        entry.update(extra_meta)
    ai.setdefault("knowledge_apply", {})[logic_id] = entry
    return {
        "ok": True,
        "preview": False,
        "provider": provider,
        "candidates_updated": result.get("candidates_updated", 0),
        "failures_remaining": result.get("failures_remaining", 0),
        "retries_used": result.get("retries_used", 0),
        "reconciliation": reconciliation,
    }


def apply_knowledge_m365(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    preview_only: bool = True,
) -> dict[str, Any]:
    """Apply knowledge strictly via signed-in M365 Copilot Chat API."""
    if not m365_auth.is_api_ready(cfg):
        return {
            "ok": False,
            "provider": "m365",
            "error": "Sign in to Microsoft 365 Copilot first (Review tab → Sign in).",
            "reason": "not_signed_in",
            "candidates_updated": 0,
        }
    if not m365_auth.is_copilot_chat_entitled():
        return {
            "ok": False,
            "provider": "m365",
            "error": (
                "Microsoft 365 Copilot Chat API is not available for this account. "
                "Sign in with a work account that has the Microsoft 365 Copilot license."
            ),
            "reason": "not_entitled",
            "activation_guide": "README.md",
            "candidates_updated": 0,
        }

    def run_apply(failures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        try:
            return apply_knowledge_via_m365(
                bundle,
                cfg,
                logic_id=logic_id,
                engineer_note=engineer_note,
                failure_context=failures,
            )
        except M365CopilotNotEntitledError as exc:
            return {
                "ok": False,
                "error": str(exc),
                "reason": "not_entitled",
                "not_entitled_kind": exc.reason,
                "graph_status": exc.status_code,
                "graph_body": exc.raw_body,
                "activation_guide": "README.md",
            }
        except (RuntimeError, ValueError, PermissionError) as exc:
            return {"ok": False, "error": str(exc) or "M365 Copilot request failed"}

    out = run_apply()
    if not out.get("ok"):
        return {
            "ok": False,
            "provider": "m365",
            "error": out.get("error") or "M365 Copilot request failed",
            "reason": out.get("reason"),
            "not_entitled_kind": out.get("not_entitled_kind"),
            "activation_guide": out.get("activation_guide"),
            "candidates_updated": 0,
        }
    patches = out.get("patches") or []

    def retry_m365(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        retry = run_apply(failures)
        return retry.get("patches") or [] if retry.get("ok") else []

    result = _finalize_knowledge_patches(
        bundle,
        logic_id,
        patches,
        provider="m365",
        cfg=cfg,
        source="m365_copilot",
        preview_only=preview_only,
        definition_updates=out.get("definition_updates") or [],
        retry_infer=retry_m365 if validation_retries(cfg) > 0 else None,
    )
    result["definition_updates"] = len(out.get("definition_updates") or [])
    return result


def apply_knowledge(
    bundle: dict[str, Any],
    logic_id: str,
    note: str,
    cfg: dict[str, Any],
    *,
    force_ollama: bool = False,
    provider: str = "auto",
    compile_constraints_first: bool = True,
    preview_only: bool = True,
) -> dict[str, Any]:
    """Apply engineer knowledge: compile accepted constraints, then M365 Copilot."""
    del force_ollama
    engineer_note = (note or "").strip()
    if not engineer_note and not compile_constraints_first:
        deduped = dedupe_only(bundle, logic_id)
        return {
            "provider": "none",
            "candidates_updated": deduped.get("candidates_updated", 0),
            "failures_remaining": deduped.get("failures_remaining", 0),
        }

    if compile_constraints_first:
        from src.engine.structured_overlay import accepted_constraints, get_overlay
        from web.structured_knowledge import compile_accepted_constraints

        overlay = get_overlay(bundle, logic_id)
        if accepted_constraints(overlay):
            compiled = compile_accepted_constraints(bundle, logic_id, cfg)
            if compiled.get("ok"):
                compiled["providers_tried"] = ["constraint_compiler"]
                return compiled

    if not engineer_note:
        deduped = dedupe_only(bundle, logic_id)
        return {
            "provider": "none",
            "candidates_updated": deduped.get("candidates_updated", 0),
            "failures_remaining": deduped.get("failures_remaining", 0),
        }

    chain = resolve_knowledge_provider_chain(cfg, provider)
    if not chain:
        return {
            "ok": False,
            "provider": "m365",
            "candidates_updated": 0,
            "failures_remaining": 0,
            "error": "Sign in to Microsoft 365 Copilot on the Review tab, or use Apply locally for simple patterns.",
            "reason": "not_signed_in" if not m365_auth.is_api_ready(cfg) else "not_entitled",
            "activation_guide": "README.md",
            "hint": "M365 Copilot sign-in required. Use Apply locally when AI is unavailable.",
        }

    last_out = _apply_knowledge_with_provider(
        bundle,
        cfg,
        logic_id=logic_id,
        engineer_note=engineer_note,
        provider="m365",
        preview_only=preview_only,
    )
    if last_out.get("ok"):
        return last_out

    deduped = dedupe_only(bundle, logic_id)
    hint = ""
    if last_out.get("reason") == "not_entitled":
        hint = "Microsoft 365 Copilot license required. Use Apply locally or ask IT for Copilot SKU."
    return {
        "ok": False,
        "provider": "m365",
        "candidates_updated": deduped.get("candidates_updated", 0),
        "failures_remaining": deduped.get("failures_remaining", 0),
        "error": last_out.get("error") or "M365 Copilot request failed.",
        "providers_tried": ["m365"],
        "activation_guide": last_out.get("activation_guide") or "",
        "hint": hint,
    }


def import_knowledge_patches(
    bundle: dict[str, Any],
    logic_id: str,
    raw_json: str,
    cfg: dict[str, Any],
    *,
    preview_only: bool = True,
) -> dict[str, Any]:
    """Apply pasted Copilot JSON with validation loop (M365 retry only)."""
    patches = parse_knowledge_patches_payload(raw_json)

    def retry_infer(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        note = str((bundle.get("ai_assists") or {}).get("engineer_notes", {}).get(logic_id) or "")
        if not _m365_usable(cfg):
            return []
        retry = apply_knowledge_via_m365(
            bundle,
            cfg,
            logic_id=logic_id,
            engineer_note=note,
            failure_context=failures,
        )
        if retry.get("ok"):
            return retry.get("patches") or []
        return []

    result = _finalize_knowledge_patches(
        bundle,
        logic_id,
        patches,
        provider="m365_manual",
        cfg=cfg,
        source="m365_manual",
        preview_only=preview_only,
        retry_infer=retry_infer if validation_retries(cfg) > 0 else None,
    )
    result["patches_received"] = len(patches)
    if schema := result.get("schema_validation"):
        result["schema_errors"] = schema.get("errors") or []
        result["schema_warnings"] = schema.get("warnings") or []
    return result


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
    if not _m365_usable(cfg):
        return {
            "ok": False,
            "error": "Sign in to Microsoft 365 Copilot on the Review tab.",
        }
    prompt = knowledge_apply_prompt(
        logic_id=logic_id,
        engineer_note=f"Define term {term}: {question}",
        logic_expression="",
        candidates=[],
    )
    out = improve_io_via_m365(cfg, prompt)
    if not out.get("ok"):
        return out
    return {"ok": True, "result": out.get("result"), "provider": "m365"}


def improve_io(
    cfg: dict[str, Any],
    *,
    candidate_id: str,
    expected_input: str,
    expected_output: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    if not _m365_usable(cfg):
        return {
            "ok": False,
            "error": "Sign in to Microsoft 365 Copilot on the Review tab.",
        }
    prompt = assist_io_fill_prompt(
        candidate_id=candidate_id,
        expected_input=expected_input,
        expected_output=expected_output,
        issues=issues,
    )
    out = improve_io_via_m365(cfg, prompt)
    if out.get("ok"):
        out["provider"] = "m365"
    return out


def provider_status(cfg: dict[str, Any], *, light: bool = False) -> dict[str, Any]:
    m365_ready = _m365_usable(cfg)
    base = {
        "default_provider": "m365",
        "allow_ollama_fallback": False,
        "require_m365_login": require_m365_login(cfg),
        "m365": m365_auth.m365_status(cfg),
        "providers_available": {
            "m365": m365_ready,
            "ollama": False,
            "copilot": False,
        },
    }
    if light:
        return base
    return {
        **base,
        "validation_retries": validation_retries(cfg),
        "knowledge_batch_size": knowledge_batch_size(cfg),
        "ollama": {"reachable": False, "skipped": True},
        "copilot": {"enabled": False, "ready": False, "trust_state": "disabled", "login_state": "disabled"},
    }
