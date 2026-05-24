"""Unified AI provider router: M365 manual/API, Ollama fallback, validation loop."""

from __future__ import annotations

from typing import Any

from src.engine.testcase_reconciliation import build_reconciliation_plan
from web import m365_auth
from web.knowledge_patch_validation import validate_knowledge_patches
from web.knowledge_reconciliation import store_pending_knowledge_apply
from web.knowledge_validation import apply_patches_with_validation, dedupe_only
from web.copilot_bridge import apply_knowledge_via_copilot, probe_copilot_cli
from web.llm_assist import (
    assist_io_fill_prompt,
    copilot_enabled,
    knowledge_apply_prompt,
    llm_enabled_for_assist,
    ollama_status,
    resolve_definition_with_ollama,
    run_assist,
    run_ollama_assist,
    candidates_for_knowledge_apply,
)
from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload
from web.m365_copilot import M365CopilotNotEntitledError, apply_knowledge_via_m365


def _assist_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}


def default_provider(cfg: dict[str, Any]) -> str:
    return str(_assist_cfg(cfg).get("default_provider") or "ollama")


def require_m365_login(cfg: dict[str, Any]) -> bool:
    return bool(_assist_cfg(cfg).get("require_m365_login", True))


def allow_ollama_fallback(cfg: dict[str, Any]) -> bool:
    return bool(_assist_cfg(cfg).get("allow_ollama_fallback", True))


def validation_retries(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("validation_retries", 1))


def knowledge_batch_size(cfg: dict[str, Any]) -> int:
    return int(_assist_cfg(cfg).get("knowledge_batch_size", 15))


def copilot_cli_ready(cfg: dict[str, Any]) -> bool:
    if not copilot_enabled(cfg):
        return False
    st = probe_copilot_cli()
    return st.get("trust_state") in ("auth_verified", "runtime_verified") or st.get("login_state") == "configured"


def normalize_provider_name(name: str) -> str:
    raw = str(name or "auto").strip().lower()
    if raw in ("m365", "m365_api", "microsoft"):
        return "m365"
    if raw in ("copilot", "copilot_cli", "github", "github_copilot"):
        return "copilot"
    if raw in ("ollama",):
        return "ollama"
    return "auto"


def _m365_usable(cfg: dict[str, Any]) -> bool:
    """True only when the M365 session is ready AND the account can call the Copilot Chat API.

    Personal (MSA) accounts and work accounts without a Microsoft 365 Copilot
    license are signed in fine but the Graph endpoint returns 400/403, so we
    skip the provider from the auto chain to avoid wasting a request.
    """
    if not m365_auth.is_api_ready(cfg):
        return False
    return m365_auth.is_copilot_chat_entitled()


def _ollama_usable(cfg: dict[str, Any]) -> bool:
    return bool(llm_enabled_for_assist(cfg) and ollama_status(cfg).get("reachable"))


def resolve_knowledge_provider_chain(cfg: dict[str, Any], requested: str = "auto") -> list[str]:
    """Return ordered provider ids to try for knowledge apply.

    Auto order: **Ollama → M365 Copilot → GitHub Copilot CLI**.
    """
    req = normalize_provider_name(requested)
    if req != "auto":
        return [req]

    chain: list[str] = []
    if _ollama_usable(cfg):
        chain.append("ollama")
    if _m365_usable(cfg):
        chain.append("m365")
    if copilot_cli_ready(cfg):
        chain.append("copilot")

    if not chain:
        default = default_provider(cfg)
        if default == "ollama" and _ollama_usable(cfg):
            chain.append("ollama")
        elif default == "m365" and _m365_usable(cfg):
            chain.append("m365")
        elif default == "copilot" and copilot_cli_ready(cfg):
            chain.append("copilot")
        elif default in ("m365", "copilot", "ollama"):
            chain.append(default)
    return chain


def apply_knowledge_copilot(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
    preview_only: bool = True,
) -> dict[str, Any]:
    """Apply knowledge via GitHub Copilot CLI."""

    def run_apply(failures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return apply_knowledge_via_copilot(
            bundle,
            logic_id=logic_id,
            engineer_note=engineer_note,
            failure_context=failures,
        )

    out = run_apply()
    if not out.get("ok"):
        return {
            "ok": False,
            "provider": "copilot",
            "error": out.get("error") or "GitHub Copilot CLI request failed",
            "candidates_updated": 0,
        }
    patches = out.get("patches") or []

    def retry_copilot(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        retry = run_apply(failures)
        return retry.get("patches") or [] if retry.get("ok") else []

    result = _finalize_knowledge_patches(
        bundle,
        logic_id,
        patches,
        provider="copilot",
        cfg=cfg,
        source="copilot_cli_knowledge",
        preview_only=preview_only,
        definition_updates=out.get("definition_updates") or [],
        retry_infer=retry_copilot if validation_retries(cfg) > 0 else None,
    )
    result["definition_updates"] = len(out.get("definition_updates") or [])
    return result


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
    if provider == "copilot":
        return apply_knowledge_copilot(
            bundle, cfg, logic_id=logic_id, engineer_note=engineer_note, preview_only=preview_only
        )
    if provider == "ollama":
        return apply_knowledge_ollama_batched(
            bundle, cfg, logic_id=logic_id, engineer_note=engineer_note, preview_only=preview_only
        )
    return {"ok": False, "provider": provider, "error": f"Unknown provider: {provider}", "candidates_updated": 0}


def _chunk(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        return [items] if items else []
    return [items[i : i + size] for i in range(0, len(items), size)]


def _logic_expression(bundle: dict[str, Any], logic_id: str) -> str:
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            return str(lb.get("raw_expression") or lb.get("expression") or "")
    return ""


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
    candidates = candidate_subset or candidates_for_knowledge_apply(bundle, logic_id)
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
    preview_only: bool = True,
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

    result = _finalize_knowledge_patches(
        bundle,
        logic_id,
        all_patches,
        provider="ollama",
        cfg=cfg,
        source="ollama_knowledge",
        preview_only=preview_only,
        retry_infer=retry_infer if validation_retries(cfg) > 0 else None,
        extra_meta={"model": model, "batches": len(batches)},
    )
    result["model"] = model
    return result


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
            "error": "Sign in to Microsoft 365 Copilot first (Sign in M365 button).",
            "reason": "not_signed_in",
            "candidates_updated": 0,
        }
    if not m365_auth.is_copilot_chat_entitled():
        # Account is signed in but cannot reach Microsoft.CopilotChat (MSA or
        # missing Microsoft 365 Copilot license). Return a structured error
        # so the auto chain continues with the next provider and the UI shows
        # the activation guide hint instead of a stack trace.
        return {
            "ok": False,
            "provider": "m365",
            "error": (
                "Microsoft 365 Copilot Chat API is not available for this account. "
                "See docs/M365_COPILOT_ACTIVATION_GUIDE.md."
            ),
            "reason": "not_entitled",
            "activation_guide": "docs/M365_COPILOT_ACTIVATION_GUIDE.md",
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
                "activation_guide": "docs/M365_COPILOT_ACTIVATION_GUIDE.md",
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
    """Apply engineer knowledge: compile accepted constraints, then AI chain (Ollama → M365 → GitHub)."""
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

    if force_ollama and allow_ollama_fallback(cfg) and llm_enabled_for_assist(cfg):
        if ollama_status(cfg).get("reachable"):
            return apply_knowledge_ollama_batched(
                bundle, cfg, logic_id=logic_id, engineer_note=engineer_note, preview_only=preview_only
            )
        return {
            "ok": False,
            "provider": "ollama",
            "error": "Ollama is not reachable.",
            "candidates_updated": 0,
        }

    chain = resolve_knowledge_provider_chain(cfg, provider)
    attempts: list[dict[str, Any]] = []
    last_out: dict[str, Any] = {}
    for prov in chain:
        last_out = _apply_knowledge_with_provider(
            bundle,
            cfg,
            logic_id=logic_id,
            engineer_note=engineer_note,
            provider=prov,
            preview_only=preview_only,
        )
        if last_out.get("ok"):
            if len(chain) > 1 or provider == "auto":
                last_out["providers_tried"] = [a["provider"] for a in attempts] + [prov]
            return last_out
        attempts.append(
            {
                "provider": prov,
                "error": last_out.get("error"),
                "reason": last_out.get("reason"),
            }
        )

    deduped = dedupe_only(bundle, logic_id)
    err = last_out.get("error") if last_out else "No AI provider available."
    if attempts and provider == "auto":
        err = "; ".join(f"{a['provider']}: {a['error']}" for a in attempts if a.get("error")) or err
    activation_guide = ""
    for entry in attempts:
        if entry.get("provider") == "m365" and entry.get("reason") == "not_entitled":
            activation_guide = "docs/M365_COPILOT_ACTIVATION_GUIDE.md"
            break
    if not activation_guide and last_out.get("activation_guide"):
        activation_guide = last_out["activation_guide"]
    hint = ""
    if activation_guide:
        hint = (
            "M365 Copilot Chat API is not entitled for this account. "
            "See docs/M365_COPILOT_ACTIVATION_GUIDE.md, or use the 'Paste from Copilot Web' button."
        )
    return {
        "ok": False,
        "provider": last_out.get("provider") or (chain[0] if chain else "none"),
        "candidates_updated": deduped.get("candidates_updated", 0),
        "failures_remaining": deduped.get("failures_remaining", 0),
        "error": err,
        "providers_tried": [a["provider"] for a in attempts],
        "activation_guide": activation_guide,
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
    """Apply pasted M365 Copilot JSON with validation loop."""
    patches = parse_knowledge_patches_payload(raw_json)

    def retry_infer(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        note = str((bundle.get("ai_assists") or {}).get("engineer_notes", {}).get(logic_id) or "")
        if _ollama_usable(cfg):
            out = infer_knowledge_patches_ollama(
                bundle,
                cfg,
                logic_id=logic_id,
                engineer_note=note,
                failure_context=failures,
            )
            if out.get("ok"):
                return out.get("patches") or []
        if m365_auth.is_api_ready(cfg) and m365_auth.is_copilot_chat_entitled():
            retry = apply_knowledge_via_m365(
                bundle,
                cfg,
                logic_id=logic_id,
                engineer_note=note,
                failure_context=failures,
            )
            if retry.get("ok"):
                return retry.get("patches") or []
        if copilot_cli_ready(cfg):
            retry = apply_knowledge_via_copilot(
                bundle,
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
    cp = probe_copilot_cli()
    return {
        "default_provider": default_provider(cfg),
        "allow_ollama_fallback": allow_ollama_fallback(cfg),
        "validation_retries": validation_retries(cfg),
        "knowledge_batch_size": knowledge_batch_size(cfg),
        "ollama": ollama_status(cfg),
        "require_m365_login": require_m365_login(cfg),
        "m365": m365_auth.m365_status(cfg),
        "copilot": {
            "enabled": copilot_enabled(cfg),
            "ready": copilot_cli_ready(cfg),
            "trust_state": cp.get("trust_state"),
            "login_state": cp.get("login_state"),
        },
        "providers_available": {
            "m365": m365_auth.is_api_ready(cfg),
            "copilot": copilot_cli_ready(cfg),
            "ollama": bool(llm_enabled_for_assist(cfg) and ollama_status(cfg).get("reachable")),
        },
    }
