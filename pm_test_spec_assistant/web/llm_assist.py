"""LLM assist provider abstraction (Ollama default; Copilot optional)."""

from __future__ import annotations

import json
from typing import Any

import requests

from src.utils.feature_flags import feature_enabled


def _resolve_ollama_model(requested: str, available: list[str]) -> str:
    """Map config model name to an installed Ollama tag (e.g. qwen2.5 → qwen2.5:latest)."""
    req = str(requested or "").strip()
    if not available:
        return req or "qwen2.5:latest"
    if req in available:
        return req
    for name in available:
        if name.split(":")[0] == req.split(":")[0]:
            return name
    return available[0]


def ollama_status(cfg: dict[str, Any]) -> dict[str, Any]:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    ollama = assist.get("ollama") if isinstance(assist.get("ollama"), dict) else {}
    base = str(ollama.get("base_url") or cfg.get("llm", {}).get("base_url") or "http://localhost:11434").rstrip(
        "/"
    )
    model = str(ollama.get("model") or cfg.get("llm", {}).get("model") or "qwen2.5")
    try:
        r = requests.get(f"{base}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m.get("name") for m in (r.json().get("models") or []) if m.get("name")]
        resolved = _resolve_ollama_model(model, models)
        return {
            "reachable": True,
            "base_url": base,
            "model": resolved,
            "models": models[:12],
        }
    except (requests.RequestException, OSError) as exc:
        return {
            "reachable": False,
            "base_url": base,
            "model": model,
            "error": str(exc),
        }


def run_ollama_assist(
    prompt: str,
    cfg: dict[str, Any],
    *,
    schema_hint: str = "Respond with JSON only.",
) -> dict[str, Any]:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    ollama = assist.get("ollama") if isinstance(assist.get("ollama"), dict) else {}
    base = str(ollama.get("base_url") or cfg.get("llm", {}).get("base_url") or "http://localhost:11434").rstrip(
        "/"
    )
    model = str(ollama.get("model") or cfg.get("llm", {}).get("model") or "qwen2.5:latest")
    timeout = float(ollama.get("timeout_seconds") or cfg.get("llm", {}).get("timeout_seconds") or 120)
    full_prompt = f"{schema_hint}\n\n{prompt}"
    try:
        tags = requests.get(f"{base}/api/tags", timeout=5)
        tags.raise_for_status()
        available = [m.get("name") for m in (tags.json().get("models") or []) if m.get("name")]
        model = _resolve_ollama_model(model, available)
        r = requests.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False, "options": {"temperature": 0}},
            timeout=timeout,
        )
        r.raise_for_status()
        text = str(r.json().get("response") or "")
        start = text.find("{")
        end = text.rfind("}")
        parsed: dict[str, Any] = {}
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = {"raw": text[:4000]}
        else:
            parsed = {"raw": text[:4000]}
        return {"ok": True, "provider": "ollama", "model": model, "result": parsed}
    except (requests.RequestException, OSError) as exc:
        return {"ok": False, "provider": "ollama", "error": str(exc)}


def default_provider(cfg: dict[str, Any]) -> str:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    return str(assist.get("default_provider") or "ollama")


def copilot_enabled(cfg: dict[str, Any]) -> bool:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    copilot = assist.get("copilot") if isinstance(assist.get("copilot"), dict) else {}
    return bool(copilot.get("enabled", False))


def assist_io_fill_prompt(
    *,
    candidate_id: str,
    expected_input: str,
    expected_output: str,
    issues: list[dict[str, Any]],
    evidence_excerpt: str = "",
) -> str:
    issue_lines = "\n".join(f"- {i.get('code')}: {i.get('message')}" for i in issues[:8])
    return (
        f"Candidate: {candidate_id}\n"
        f"Current Expected input:\n{expected_input}\n\n"
        f"Current Expected output:\n{expected_output}\n\n"
        f"Validation issues:\n{issue_lines or '(none)'}\n\n"
        f"Evidence excerpt:\n{evidence_excerpt[:2000]}\n\n"
        "Return JSON. Rules: one Given/Then per line, SIG=value only, no prose sentences, max 80 chars per line. "
        '{"expected_input": "Given: A=1\\nGiven: B=0", '
        '"expected_output": "Then: C=1"}'
    )


def run_assist(
    cfg: dict[str, Any],
    prompt: str,
    *,
    schema_hint: str = "Respond with JSON only.",
) -> dict[str, Any]:
    provider = default_provider(cfg)
    if provider == "copilot" and copilot_enabled(cfg):
        return {"ok": False, "provider": "copilot", "error": "copilot_assist_use_bridge_endpoint"}
    return run_ollama_assist(prompt, cfg, schema_hint=schema_hint)


def llm_enabled_for_assist(cfg: dict[str, Any]) -> bool:
    return feature_enabled(cfg, "ollama_assist", default=False) or bool(cfg.get("llm", {}).get("enabled"))


def build_definition_context(bundle: dict[str, Any], *, logic_id: str = "", term: str = "") -> str:
    """Clipped context for Ollama definition / I/O assist (no full Word file)."""
    parts: list[str] = ["# ALEX assist context"]
    if logic_id:
        for lb in bundle.get("logic_blocks") or []:
            if lb.get("id") == logic_id:
                parts.append(f"## Logic block {lb.get('name')}")
                parts.append(str(lb.get("raw_expression") or ""))
                break
    if term:
        parts.append(f"## Focus term\n{term}")
    for foot in bundle.get("footnote_definitions") or []:
        body = str(foot.get("definition") or foot.get("raw_text") or "")
        if term and term.split("=")[0].strip() in body or term in str(foot.get("condition_name") or ""):
            parts.append(f"## Footnote {foot.get('ref')}\n{body}")
    for d in (bundle.get("condition_definitions") or [])[:40]:
        nm = str(d.get("name") or "")
        if term and (nm in term or term.startswith(nm)):
            parts.append(f"## Definition {nm}\n{d.get('definition', '')}")
    return "\n\n".join(parts)[:8000]


def definition_query_prompt(*, term: str, question: str, context: str) -> str:
    return (
        f"{context}\n\n"
        "You help automotive test engineers resolve a missing spec term.\n"
        f"Focus term: {term}\n"
        f"Engineer note: {question}\n\n"
        "Return JSON only:\n"
        '{"term":"...", "answer":"plain definition", "definitions":[{"name":"SIGNAL", "definition":"= value or prose"}], '
        '"suggested_matches":[{"name":"...", "reason":"...", "confidence":"low|medium|high"}], '
        '"follow_up_questions":[], "evidence_refs":[], '
        '"role":"guard_input|system_state|output_assertion", '
        '"given_lines":["Given: SIG=value"], "definition_body":"for engineer_definitions"}'
    )


def resolve_definition_with_ollama(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    term: str,
    question: str,
) -> dict[str, Any]:
    ctx = build_definition_context(bundle, logic_id=logic_id, term=term)
    prompt = definition_query_prompt(term=term, question=question, context=ctx)
    out = run_ollama_assist(prompt, cfg)
    if not out.get("ok"):
        return out
    parsed = out.get("result") if isinstance(out.get("result"), dict) else {}
    entry = {
        "term": parsed.get("term") or term,
        "question": question.strip(),
        "answer": parsed.get("answer", ""),
        "suggested_matches": parsed.get("suggested_matches") or [],
        "follow_up_questions": parsed.get("follow_up_questions") or [],
        "evidence_refs": parsed.get("evidence_refs") or [],
        "role": parsed.get("role", ""),
        "given_lines": parsed.get("given_lines") or [],
        "definition_body": parsed.get("definition_body", ""),
        "provider": "ollama",
    }
    ai = bundle.setdefault("ai_assists", {})
    query_rows = ai.setdefault("definition_queries", {}).setdefault(logic_id, [])
    query_rows.append(entry)
    eng = ai.setdefault("engineer_definitions", {})
    bulk_defs = parsed.get("definitions") if isinstance(parsed.get("definitions"), list) else []
    if bulk_defs:
        for row in bulk_defs:
            if not isinstance(row, dict):
                continue
            nm = str(row.get("name") or "").strip()
            df = str(row.get("definition") or "").strip()
            if nm and df:
                eng[nm] = {
                    "name": nm,
                    "definition": df,
                    "logic_id": logic_id,
                    "source": "ollama_assist",
                }
    body = str(parsed.get("definition_body") or parsed.get("answer") or "").strip()
    if body:
        eng[term.split("=")[0].strip()] = {
            "name": term.split("=")[0].strip(),
            "definition": body,
            "logic_id": logic_id,
            "source": "ollama_assist",
        }
    from web.ai_provider import apply_knowledge

    apply_out = apply_knowledge(
        bundle, logic_id, question.strip(), cfg, force_ollama=True
    )
    return {
        "ok": True,
        "provider": "ollama",
        "entry": entry,
        "applied_definitions": list(eng.keys()),
        "candidates_updated": int(apply_out.get("candidates_updated") or 0),
        "knowledge_apply": apply_out,
    }


def candidates_for_knowledge_apply(bundle: dict[str, Any], logic_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    from src.engine.concrete_test_values import materialize_expected_output

    rows: list[dict[str, Any]] = []
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        op = cand.get("operation") or {}
        given = [
            {"signal": str(g.get("signal")), "value": str(g.get("value"))}
            for g in op.get("given") or []
            if isinstance(g, dict) and g.get("signal") is not None
        ]
        rows.append(
            {
                "candidate_id": str(cand.get("id") or ""),
                "use_case": str(cand.get("description") or cand.get("use_case") or "")[:240],
                "path": str(trace.get("path_id") or trace.get("branch") or "")[:120],
                "current_given": given[:16],
                "expected_output": materialize_expected_output(cand)[:240],
            }
        )
        if len(rows) >= limit:
            break
    return rows


def knowledge_apply_prompt(
    *,
    logic_id: str,
    engineer_note: str,
    logic_expression: str,
    candidates: list[dict[str, Any]],
) -> str:
    import json

    return (
        f"Logic block: {logic_id}\n"
        f"Expression:\n{logic_expression[:2000]}\n\n"
        f"Engineer knowledge (natural language, any format):\n{engineer_note[:4000]}\n\n"
        "Test cases to update (one concrete value per signal per case):\n"
        f"{json.dumps(candidates, ensure_ascii=False)[:12000]}\n\n"
        "Apply the engineer knowledge to each test case's inputs. "
        "Respect each case's path/branch intent (MCDC). "
        "Handle ranges, equalities, and conditional rules (e.g. when A=B then C=1). "
        "Never emit two values for the same signal in one case.\n\n"
        "Return JSON only:\n"
        '{"candidates":[{"candidate_id":"TC_...", "given":[{"signal":"SIG","value":"0"}], '
        '"note":"short reason"}]}'
    )


def apply_engineer_knowledge_with_ollama(
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str,
) -> dict[str, Any]:
    note = (engineer_note or "").strip()
    if not note:
        from src.engine.engineer_rules import dedupe_logic_block_given

        return {"ok": True, "candidates_updated": dedupe_logic_block_given(bundle, logic_id), "skipped": "empty_note"}

    logic_expression = ""
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            logic_expression = str(lb.get("raw_expression") or lb.get("expression") or "")
            break

    candidates = candidates_for_knowledge_apply(bundle, logic_id)
    if not candidates:
        return {"ok": True, "candidates_updated": 0, "skipped": "no_candidates"}

    prompt = knowledge_apply_prompt(
        logic_id=logic_id,
        engineer_note=note,
        logic_expression=logic_expression,
        candidates=candidates,
    )
    out = run_ollama_assist(prompt, cfg)
    if not out.get("ok"):
        return out

    parsed = out.get("result") if isinstance(out.get("result"), dict) else {}
    patches = parsed.get("candidates") if isinstance(parsed.get("candidates"), list) else []
    from src.engine.engineer_rules import apply_given_patches_to_bundle

    updated = apply_given_patches_to_bundle(bundle, logic_id, patches)
    ai = bundle.setdefault("ai_assists", {})
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": "ollama",
        "model": out.get("model"),
        "patches": patches[:40],
        "candidates_updated": updated,
    }
    return {"ok": True, "provider": "ollama", "candidates_updated": updated, "patches": len(patches)}
