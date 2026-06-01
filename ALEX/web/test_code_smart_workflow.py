"""Simplified Test Code workflow: infer context, propose mappings, smart generation."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from web.code_style_samples import _api_calls_from_cpp, load_code_style_samples
from web.config_bundle_layers import (
    _capture_layer_snapshots,
    _overrides_dir,
    _read_text,
    _write_text,
    add_learned_mapping,
    ensure_config_layers,
    record_config_version,
    write_effective_config_files,
)
from web.config_yaml_parsers import flatten_signal_mapping, parse_signal_mapping_yaml
from web.local_template_codegen import (
    batch_generate_local_template,
    check_mapping_coverage,
    check_candidate_mapping,
)
from web.project_code_config import CONFIG_FILES, load_project_code_config, project_code_config_dir

_RTE_READ_RE = re.compile(
    r"EXPECT_CALL\s*\(\s*rte\s*,\s*(Rte_Read_[A-Za-z0-9_]+)\s*\(",
    re.I,
)
_TEST_F_RE = re.compile(r"TEST_F\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", re.I)
_EXPECT_THAT_VAR_RE = re.compile(
    r"EXPECT_THAT\s*\(\s*([A-Za-z_][A-Za-z0-9_]+)",
    re.I,
)
_GIVEN_SIG_RE = re.compile(r"^Given:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)
_THEN_SIG_RE = re.compile(r"^Then:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)
_AUTO_ACCEPT_CONFIDENCE = 0.9


def _collect_cpp_corpus(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    extra_snippets: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Merge sample snippets + drafts + code_references into one searchable corpus."""
    parts: list[str] = []
    sources: list[dict[str, Any]] = []

    for row in load_code_style_samples(bundle):
        snip = str(row.get("snippet") or "")
        if snip:
            parts.append(snip)
            sources.append({"kind": "code_style_sample", "label": row.get("label") or ""})

    for ref in bundle.get("code_references") or []:
        if not isinstance(ref, dict):
            continue
        for block in ref.get("test_blocks") or []:
            snip = str(block.get("snippet") or block.get("code_body") or "")
            if snip:
                parts.append(snip)
                sources.append({"kind": "code_reference", "label": ref.get("file") or ""})
        prev = str(ref.get("snippet_preview") or "")
        if prev:
            parts.append(prev)

    for cid, draft in (gtest_state.get("drafts") or {}).items():
        snip = str(draft.get("full_snippet") or draft.get("code_body") or "")
        if snip:
            parts.append(snip)
            sources.append({"kind": "saved_draft", "label": cid})

    for snip in extra_snippets or []:
        if snip.strip():
            parts.append(snip.strip())
            sources.append({"kind": "pasted_sample", "label": "paste"})

    return "\n\n".join(parts), sources


def _signals_from_workbook(bundle: dict[str, Any], *, language: str = "EN") -> set[str]:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    names: set[str] = set()
    preview = build_customer_testspec_preview(bundle, language=language)
    for row in preview.get("rows") or []:
        for line in str(row.get("expected_input") or "").splitlines():
            m = _GIVEN_SIG_RE.match(line.strip())
            if m:
                names.add(m.group("sig"))
        for line in str(row.get("expected_output") or "").splitlines():
            m = _THEN_SIG_RE.match(line.strip())
            if m:
                names.add(m.group("sig"))
    return names


def _rte_read_suffix(fn: str) -> str:
    m = re.match(r"Rte_Read_(.+)$", fn, re.I)
    return m.group(1) if m else ""


def _index_keys_for_rte_suffix(suffix: str) -> set[str]:
    """Index full suffix, each segment, and contiguous multi-segment keys (e.g. WMODE_CMD)."""
    parts = [p for p in suffix.split("_") if p]
    keys: set[str] = set()
    if suffix:
        keys.add(suffix)
    keys.update(parts)
    for i in range(len(parts)):
        for j in range(i + 1, len(parts) + 1):
            keys.add("_".join(parts[i:j]))
    return keys


def _infer_rte_read_by_signal(corpus: str) -> dict[str, list[str]]:
    """Map signal token -> list of Rte_Read_* function names seen near that signal."""
    out: dict[str, list[str]] = {}
    for m in _RTE_READ_RE.finditer(corpus):
        fn = m.group(1)
        suffix = _rte_read_suffix(fn)
        if not suffix:
            continue
        for key in _index_keys_for_rte_suffix(suffix):
            out.setdefault(key, [])
            if fn not in out[key]:
                out[key].append(fn)
    for sig in re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", corpus):
        if sig.startswith("Rte_") or sig in ("TRUE", "FALSE", "OK", "NOT", "TEST", "EXPECT"):
            continue
        for m in _RTE_READ_RE.finditer(corpus):
            fn = m.group(1)
            if sig in fn or sig in _rte_read_suffix(fn):
                out.setdefault(sig, [])
                if fn not in out[sig]:
                    out[sig].append(fn)
    return out


def _build_signal_mapping_yaml(
    rte_by_sig: dict[str, list[str]],
    workbook_signals: set[str],
    direct_vars: set[str],
) -> str:
    lines: list[str] = ["# Inferred from project samples — edit in Advanced if needed", ""]
    keys = sorted(set(rte_by_sig) | workbook_signals)
    for sig in keys:
        reads = rte_by_sig.get(sig) or []
        if reads:
            fn = reads[0]
            lines.append(f"{sig}:")
            if len(reads) == 1:
                lines.append(
                    f'  setter: EXPECT_CALL(rte, {fn}(NotNull())).WillRepeatedly(Return(RTE_E_OK))'
                )
            else:
                lines.append("  setter:")
                for fn in reads[:5]:
                    lines.append(
                        f'    - EXPECT_CALL(rte, {fn}(NotNull())).WillRepeatedly(Return(RTE_E_OK))'
                    )
        elif sig in direct_vars:
            lines.append(f"{sig}:")
            lines.append("  getter: direct_variable")
            lines.append(f'  assertion: EXPECT_THAT({sig}, Eq({{expected}}))')
        else:
            lines.append(f"{sig}:")
            lines.append(f"  # TODO: infer setter for {sig}")
    lines.append("")
    lines.append("MAIN_STEP:")
    lines.append("  code: igsw_Main_Run()")
    lines.append("")
    lines.append("T_WAIT:")
    lines.append("  code: |")
    lines.append("    for (int t = 0; t < {time}; ++t) {")
    lines.append("      igsw_Main_Run();")
    lines.append("    }")
    return "\n".join(lines) + "\n"


def _build_code_rules_md(
    *,
    fixture: str,
    apis: set[str],
    has_expect_call: bool,
    has_expect_that: bool,
    sample_count: int,
) -> str:
    fix = fixture or "RteDefaultAction"
    return f"""# Inferred project code rules (from {sample_count} sample(s))

### Fixture rule
* Use `TEST_F(<FixtureClass>, <TestName>)`
* Fixture: `{fix}`

### Input setup rule
* Mock inputs via `EXPECT_CALL(rte, Rte_Read_*(NotNull()))` when applicable

### Output assertion rule
* Prefer `EXPECT_THAT(variable, Eq(expected))` for outputs
* Use direct globals when observed in samples

### Timing rule
* Use loop with `igsw_Main_Run()` for elapsed time

### Observed APIs in samples
{chr(10).join(f'* `{a}`' for a in sorted(apis)[:30])}

### Patterns detected
* EXPECT_CALL: {"yes" if has_expect_call else "no"}
* EXPECT_THAT: {"yes" if has_expect_that else "no"}
"""


def _build_api_catalog_yaml(apis: set[str], wildcards: set[str]) -> str:
    core = sorted(a for a in apis if a.startswith("igsw_") or a == "igsw_Main_Run")
    mocks = sorted(a for a in apis if "EXPECT" in a or a in ("WillRepeatedly", "WillOnce", "DoAll", "NotNull", "Return"))
    lines = [
        "# Inferred API catalog",
        "fixture:",
        "  - RteDefaultAction",
        "core:",
    ]
    for a in core[:15]:
        lines.append(f"  - {a}()")
    lines.append("setters:")
    for w in sorted(wildcards):
        lines.append(f"  - {w}")
    lines.append("mocks:")
    for a in mocks[:20]:
        lines.append(f"  - {a}")
    lines.append("utilities:")
    lines.append("  - NotNull()")
    lines.append("  - Return()")
    return "\n".join(lines) + "\n"


def _build_gtest_template_md(fixture: str) -> str:
    fix = fixture or "RteDefaultAction"
    return f"""# Inferred GTest template

```cpp
TEST_F({fix}, {{test_name}})
{{
    // ===== GIVEN =====
    {{given_code}}

    igsw_Main_Run();

    // ===== WHEN =====
    {{when_code}}

    // ===== THEN =====
    {{assertion_code}}
}}
```
"""


def _config_is_sparse(job_output: Path) -> bool:
    root = project_code_config_dir(job_output)
    sm = _read_text(root / "signal_mapping.yaml")
    parsed = parse_signal_mapping_yaml(sm)
    return len(parsed.get("keys") or []) < 3


def analyze_project_context(
    job_output: Path,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    language: str = "EN",
    extra_snippets: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Infer config from samples/testcases; write to project_overrides when sparse or force."""
    ensure_config_layers(job_output)
    if not force and not _config_is_sparse(job_output):
        config = load_project_code_config(job_output)
        reason = "Config already populated — use force=true to re-infer"
        return {
            "ok": True,
            "skipped": True,
            "reason": reason,
            "summary": reason,
            "config": config,
        }

    corpus, sources = _collect_cpp_corpus(bundle, gtest_state, extra_snippets=extra_snippets)
    if not corpus.strip():
        return {"ok": False, "error": "No sample C++ code found — upload or paste a sample first"}

    fixtures = _TEST_F_RE.findall(corpus)
    fixture = Counter(fixtures).most_common(1)[0][0] if fixtures else "RteDefaultAction"
    apis = _api_calls_from_cpp(corpus)
    wildcards: set[str] = set()
    if any("Rte_Read" in c for c in corpus):
        wildcards.add("Rte_Read_*")

    direct_vars = set(_EXPECT_THAT_VAR_RE.findall(corpus))
    wb_signals = _signals_from_workbook(bundle, language=language)
    rte_by_sig = _infer_rte_read_by_signal(corpus)
    for sig in wb_signals:
        rte_by_sig.setdefault(sig, [])

    inferred = {
        "code_rules.md": _build_code_rules_md(
            fixture=fixture,
            apis=apis,
            has_expect_call="EXPECT_CALL" in corpus,
            has_expect_that="EXPECT_THAT" in corpus,
            sample_count=len(sources),
        ),
        "signal_mapping.yaml": _build_signal_mapping_yaml(rte_by_sig, wb_signals, direct_vars),
        "api_catalog.yaml": _build_api_catalog_yaml(apis, wildcards),
        "gtest_template.md": _build_gtest_template_md(fixture),
    }

    changed: list[str] = []
    for name, content in inferred.items():
        path = _overrides_dir(job_output) / name
        existing = _read_text(path).strip()
        default = (CONFIG_FILES.get(name) or {}).get("default", "").strip()
        if force or not existing or existing == default or "Inferred" not in existing and len(existing) < 80:
            _write_text(path, content)
            changed.append(name)

    write_effective_config_files(job_output)
    if changed:
        record_config_version(
            job_output,
            source="CONTEXT_ANALYZE",
            changed_sections=changed,
            summary=f"Inferred project context from {len(sources)} source(s)",
            changes=[{"file": n, "bytes": len(inferred[n])} for n in changed],
            layer_snapshots=_capture_layer_snapshots(job_output, changed),
        )

    config = load_project_code_config(job_output)
    flat = flatten_signal_mapping(parse_signal_mapping_yaml(inferred["signal_mapping.yaml"]))
    summary = (
        f"Inferred {len(flat)} mapping keys, fixture `{fixture}`, "
        f"{len(apis)} API pattern(s) from {len(sources)} source(s)"
    )
    return {
        "ok": True,
        "skipped": False,
        "changed_sections": changed,
        "inferred": {k: len(v) for k, v in inferred.items()},
        "mapping_keys_inferred": len(flat),
        "fixture_inferred": fixture,
        "apis_inferred": len(apis),
        "summary": summary,
        "sources": sources[:20],
        "config": config,
    }


def propose_missing_mappings(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Path,
    *,
    language: str = "EN",
    extra_snippets: list[str] | None = None,
) -> dict[str, Any]:
    """Propose mappings for missing coverage terms (not auto-applied except smart-mode high conf)."""
    coverage = check_mapping_coverage(bundle, gtest_state, job_output, language=language)
    missing = list(coverage.get("missing_terms") or [])
    if not missing:
        gtest_state["mapping_proposals"] = {"proposals": [], "updated_at": ""}
        return {"ok": True, "proposals": [], "coverage": coverage}

    corpus, _sources = _collect_cpp_corpus(bundle, gtest_state, extra_snippets=extra_snippets)
    rte_by_sig = _infer_rte_read_by_signal(corpus)
    direct_vars = set(_EXPECT_THAT_VAR_RE.findall(corpus))

    affected_count: dict[str, int] = {}
    for case in coverage.get("cases") or []:
        for term in case.get("missing_terms") or []:
            affected_count[term] = affected_count.get(term, 0) + 1

    proposals: list[dict[str, Any]] = []
    for term in sorted(set(missing)):
        proposal = _propose_one_mapping(term, rte_by_sig, direct_vars, corpus)
        proposal["affected_testcase_count"] = affected_count.get(term, 0)
        proposals.append(proposal)

    gtest_state["mapping_proposals"] = {
        "proposals": proposals,
        "coverage_snapshot": {
            "ready": coverage.get("ready_for_local_generation"),
            "missing": coverage.get("missing_mapping_count"),
        },
    }
    return {"ok": True, "proposals": proposals, "coverage": coverage}


def _propose_one_mapping(
    term: str,
    rte_by_sig: dict[str, list[str]],
    direct_vars: set[str],
    corpus: str,
) -> dict[str, Any]:
    sig = str(term or "").strip()
    reads = list(rte_by_sig.get(sig) or [])
    if not reads and sig.split("_")[-1] in rte_by_sig:
        reads = list(rte_by_sig.get(sig.split("_")[-1]) or [])
    if not reads:
        for fn in {fn for fns in rte_by_sig.values() for fn in fns}:
            if sig in fn or sig == _rte_read_suffix(fn):
                reads.append(fn)
        reads = list(dict.fromkeys(reads))

    if reads:
        fn = reads[0]
        code = f"EXPECT_CALL(rte, {fn}(NotNull())).WillRepeatedly(Return(RTE_E_OK))"
        return {
            "signal": sig,
            "proposed_code": code,
            "confidence": 0.92 if len(reads) == 1 else 0.85,
            "source": "sample_rte_read",
            "evidence": f"Found {fn} in sample code",
        }
    if sig in direct_vars or re.search(rf"\b{re.escape(sig)}\b", corpus):
        code = f"EXPECT_THAT({sig}, Eq({{expected}}))"
        return {
            "signal": sig,
            "proposed_code": code,
            "confidence": 0.8,
            "source": "direct_variable",
            "evidence": f"Variable {sig} used in EXPECT_THAT in samples",
        }
    if re.search(rf"Rte_Read_[A-Za-z0-9_]*{re.escape(sig.split('_')[-1])}", corpus, re.I):
        code = f"EXPECT_CALL(rte, Rte_Read_{sig}(NotNull())).WillRepeatedly(Return(RTE_E_OK))"
        return {
            "signal": sig,
            "proposed_code": code,
            "confidence": 0.55,
            "source": "heuristic_rte_read",
            "evidence": f"Partial name match for {sig} in Rte_Read_* pattern",
        }
    return {
        "signal": sig,
        "proposed_code": "",
        "confidence": 0.2,
        "source": "unknown",
        "evidence": "No matching Rte_Read or EXPECT_THAT pattern in samples — use Copilot or edit manually",
    }


def accept_proposed_mappings(
    job_output: Path,
    gtest_state: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    use_project_override: bool = False,
) -> dict[str, Any]:
    """Apply user-accepted proposals to learned mappings (never silent for low confidence)."""
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    for item in items:
        if not item.get("accept"):
            rejected.append(str(item.get("signal") or ""))
            continue
        sig = str(item.get("signal") or "").strip()
        code = str(item.get("proposed_code") or item.get("code") or "").strip()
        if not sig or not code:
            rejected.append(sig or "?")
            continue
        conf = float(item.get("confidence") or 0)
        if conf < 0.5 and not item.get("force"):
            rejected.append(sig)
            continue
        add_learned_mapping(job_output, sig, code, use_project_override=use_project_override)
        cmap = dict(gtest_state.get("code_variable_map") or {})
        cmap[sig] = code
        gtest_state["code_variable_map"] = cmap
        accepted.append({"signal": sig, "code": code, "confidence": conf})

    remaining = []
    stored = (gtest_state.get("mapping_proposals") or {}).get("proposals") or []
    acc_sigs = {a["signal"] for a in accepted}
    for p in stored:
        if p.get("signal") not in acc_sigs and p.get("signal") not in rejected:
            remaining.append(p)
    gtest_state["mapping_proposals"] = {
        "proposals": remaining,
        "last_accepted": accepted,
    }
    return {"ok": True, "accepted": accepted, "rejected": rejected, "remaining_count": len(remaining)}


def smart_generate_code(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Path,
    *,
    language: str = "EN",
    candidate_ids: list[str] | None = None,
    auto_accept_high_confidence: bool = True,
    analyze_if_sparse: bool = True,
    use_api_for_hard: bool = False,
    cfg: dict[str, Any] | None = None,
    library_root: Path | None = None,
) -> dict[str, Any]:
    """Orchestrate: optional analyze → propose → auto-accept high conf → local gen → flag rest."""
    steps: list[str] = []
    if analyze_if_sparse and _config_is_sparse(job_output):
        ar = analyze_project_context(job_output, bundle, gtest_state, language=language)
        if ar.get("ok") and not ar.get("skipped"):
            steps.append("analyzed_project_context")

    prop = propose_missing_mappings(bundle, gtest_state, job_output, language=language)
    steps.append("proposed_mappings")
    if auto_accept_high_confidence:
        to_accept = [
            {
                "signal": p["signal"],
                "proposed_code": p["proposed_code"],
                "confidence": p["confidence"],
                "accept": True,
            }
            for p in prop.get("proposals") or []
            if (p.get("proposed_code") and float(p.get("confidence") or 0) >= _AUTO_ACCEPT_CONFIDENCE)
        ]
        if to_accept:
            acc = accept_proposed_mappings(job_output, gtest_state, to_accept)
            steps.append(f"auto_accepted_{len(acc.get('accepted') or [])}")

    coverage = check_mapping_coverage(bundle, gtest_state, job_output, language=language)
    steps.append("coverage_checked")

    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    all_ids = [str(r.get("candidate_id") or "") for r in preview.get("rows") or [] if r.get("candidate_id")]
    targets = [c for c in (candidate_ids or all_ids) if c in all_ids]

    ready_ids = {c["candidate_id"] for c in coverage.get("cases") or [] if c.get("ready")}
    pending_prop = {p["signal"]: p for p in (gtest_state.get("mapping_proposals") or {}).get("proposals") or []}

    local_ids = [cid for cid in targets if cid in ready_ids]
    batch_result = batch_generate_local_template(
        bundle,
        gtest_state,
        job_output,
        candidate_ids=local_ids if local_ids else None,
        language=language,
    )
    steps.append("local_template_batch")

    review_cases: list[dict[str, Any]] = []
    api_queued: list[str] = []

    config = load_project_code_config(job_output)
    for cid in targets:
        if cid in ready_ids:
            continue
        one = check_candidate_mapping(bundle, gtest_state, cid, config=config, language=language)
        missing = one.get("missing_terms") or []
        if missing and any(m in pending_prop for m in missing):
            review_cases.append(
                {
                    "candidate_id": cid,
                    "reason": "pending_mapping_proposal",
                    "missing_terms": missing,
                    "proposals": [pending_prop[m] for m in missing if m in pending_prop],
                }
            )
            continue
        if use_api_for_hard and cfg and library_root is not None:
            api_queued.append(cid)
            continue
        review_cases.append(
            {
                "candidate_id": cid,
                "reason": "missing_mapping" if missing else "not_ready",
                "missing_terms": missing,
            }
        )

    api_results: list[dict[str, Any]] = []
    if api_queued and cfg and library_root is not None:
        from web.copilot_code_orchestrator import run_copilot_code_generate

        for cid in api_queued[:10]:
            try:
                one = run_copilot_code_generate(
                    bundle,
                    gtest_state,
                    candidate_id=cid,
                    cfg=cfg,
                    library_root=library_root,
                    language=language,
                    use_baseline=True,
                )
                api_results.append({"candidate_id": cid, **one})
            except Exception as exc:
                api_results.append({"candidate_id": cid, "ok": False, "error": str(exc)})
        steps.append(f"api_generate_{len(api_queued)}")

    return {
        "ok": True,
        "steps": steps,
        "coverage": coverage,
        "batch_summary": batch_result.get("summary") or {},
        "batch_results": batch_result.get("results") or [],
        "review_cases": review_cases,
        "api_results": api_results,
        "mapping_proposals": (gtest_state.get("mapping_proposals") or {}).get("proposals") or [],
    }


def record_smart_workflow_run(gtest_state: dict[str, Any], event: str, data: dict[str, Any] | None = None) -> None:
    """Persist last smart-workflow event metadata for run reports (does not change generation)."""
    payload = dict(data or {})
    run = dict(gtest_state.get("smart_workflow_run") or {})
    run["last_event"] = event
    run["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    history = list(run.get("events") or [])
    history.append({"event": event, "at": run["updated_at"], **payload})
    run["events"] = history[-25:]
    if event == "analyze_project_context":
        run["analyze"] = {
            "skipped": payload.get("skipped"),
            "fixture_inferred": payload.get("fixture_inferred"),
            "apis_inferred": payload.get("apis_inferred"),
            "mapping_keys_inferred": payload.get("mapping_keys_inferred"),
            "summary": payload.get("summary") or payload.get("reason"),
        }
    elif event in ("mapping_coverage", "propose_missing_mappings", "accept_proposed_mappings"):
        run["coverage"] = payload.get("coverage") or payload.get("mapping_coverage")
    elif event == "smart_generate":
        steps = payload.get("steps") or []
        auto_n = 0
        for step in steps:
            if isinstance(step, str) and step.startswith("auto_accepted_"):
                try:
                    auto_n = int(step.rsplit("_", 1)[-1])
                except ValueError:
                    pass
        run["last_smart_generate"] = {
            "steps": steps,
            "batch_summary": payload.get("batch_summary") or {},
            "auto_accepted_count": auto_n,
        }
    gtest_state["smart_workflow_run"] = run


def _workflow_status_counts(gtest_state: dict[str, Any]) -> dict[str, int]:
    counts = Counter()
    for draft in (gtest_state.get("drafts") or {}).values():
        if not isinstance(draft, dict):
            continue
        st = str(draft.get("code_status") or "NO_CODE").upper()
        if st not in ("SAVED", "NEEDS_REVIEW", "ERROR", "DRAFT", "NO_CODE"):
            st = "DRAFT"
        counts[st] += 1
    return {
        "SAVED": counts.get("SAVED", 0),
        "NEEDS_REVIEW": counts.get("NEEDS_REVIEW", 0),
        "ERROR": counts.get("ERROR", 0),
        "DRAFT": counts.get("DRAFT", 0),
        "NO_CODE": counts.get("NO_CODE", 0),
    }


def _aggregate_quality_issues(
    gtest_state: dict[str, Any], *, top_n: int = 10
) -> tuple[list[dict[str, Any]], list[str]]:
    issue_counts: Counter[str] = Counter()
    unknown_apis: set[str] = set()
    for cid, draft in (gtest_state.get("drafts") or {}).items():
        if not isinstance(draft, dict):
            continue
        for check in draft.get("quality_results") or []:
            if not isinstance(check, dict):
                continue
            name = str(check.get("name") or "issue")
            sev = str(check.get("severity") or "")
            if sev in ("PASS", ""):
                continue
            msg = str(check.get("message") or name).strip()
            key = f"{name}: {msg[:160]}"
            issue_counts[key] += 1
            if name == "unknown_api":
                for part in re.split(r"[,;]", msg):
                    token = part.replace("API not in catalog or sample:", "").strip()
                    if token:
                        unknown_apis.add(token)
    top_issues = [
        {"issue": k, "count": v}
        for k, v in issue_counts.most_common(top_n)
    ]
    return top_issues, sorted(unknown_apis)[:30]


def _duplicate_test_names(gtest_state: dict[str, Any]) -> list[dict[str, Any]]:
    by_name: dict[str, list[str]] = {}
    for cid, draft in (gtest_state.get("drafts") or {}).items():
        if not isinstance(draft, dict):
            continue
        tn = str(draft.get("test_name") or "").strip()
        if not tn:
            continue
        by_name.setdefault(tn, []).append(str(cid))
    return [
        {"test_name": name, "candidate_ids": ids, "count": len(ids)}
        for name, ids in sorted(by_name.items())
        if len(ids) > 1
    ]


def _fixture_and_api_patterns(job_output: Path, gtest_state: dict[str, Any]) -> tuple[str, list[str]]:
    run = gtest_state.get("smart_workflow_run") or {}
    analyze = run.get("analyze") or {}
    fixture = str(analyze.get("fixture_inferred") or "").strip()
    api_patterns: list[str] = []
    if analyze.get("apis_inferred"):
        api_patterns.append(f"{analyze['apis_inferred']} API call(s) from last analyze")
    config = load_project_code_config(job_output)
    rules = str((config.get("files") or {}).get("code_rules.md", {}).get("content") or "")
    m = re.search(r"fixture[:\s]+`?([A-Za-z_][A-Za-z0-9_]*)`?", rules, re.I)
    if m and not fixture:
        fixture = m.group(1)
    if not fixture:
        tmpl = str((config.get("files") or {}).get("gtest_template.md", {}).get("content") or "")
        fm = _TEST_F_RE.search(tmpl)
        if fm:
            fixture = fm.group(1)
    catalog = str((config.get("files") or {}).get("api_catalog.yaml", {}).get("content") or "")
    for line in catalog.splitlines():
        s = line.strip()
        if s.startswith("- ") and len(api_patterns) < 12:
            api_patterns.append(s[2:].strip())
    return fixture or "—", api_patterns[:12]


def build_smart_workflow_run_report(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Path,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    """Aggregate concise usability report from current job state."""
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
    from web.code_text_transform import merge_saved_code_preview
    from web.gtest_workspace import classify_sync_status
    from web.local_template_codegen import check_mapping_coverage

    preview = build_customer_testspec_preview(bundle, language=language)
    total = len(preview.get("rows") or [])
    coverage = gtest_state.get("mapping_coverage") or check_mapping_coverage(
        bundle, gtest_state, job_output, language=language
    )
    run = gtest_state.get("smart_workflow_run") or {}
    analyze = run.get("analyze") or {}
    proposals = (gtest_state.get("mapping_proposals") or {}).get("proposals") or []
    if not proposals and isinstance(gtest_state.get("mapping_proposals"), list):
        proposals = gtest_state.get("mapping_proposals") or []

    mapping_candidates = int(coverage.get("detected_mapping_count") or 0)
    if not mapping_candidates:
        config = load_project_code_config(job_output)
        sm = (config.get("files") or {}).get("signal_mapping.yaml") or {}
        flat = flatten_signal_mapping(parse_signal_mapping_yaml(str(sm.get("content") or "")))
        mapping_candidates = len(flat)

    auto_accepted = int((run.get("last_smart_generate") or {}).get("auto_accepted_count") or 0)
    last_accepted = (gtest_state.get("mapping_proposals") or {}).get("last_accepted") or []
    if last_accepted:
        auto_accepted = max(auto_accepted, len(last_accepted))

    mappings_review = [
        p for p in proposals
        if float(p.get("confidence") or 0) < _AUTO_ACCEPT_CONFIDENCE and p.get("proposed_code")
    ]
    wf = _workflow_status_counts(gtest_state)
    top_issues, unknown_apis = _aggregate_quality_issues(gtest_state)
    dupes = _duplicate_test_names(gtest_state)
    fixture, api_patterns = _fixture_and_api_patterns(job_output, gtest_state)

    sync = classify_sync_status(bundle, gtest_state, language=language)
    sync_map = {str(r.get("candidate_id") or ""): str(r.get("status") or "") for r in sync.get("rows") or []}
    merge_preview = merge_saved_code_preview(
        gtest_state, bundle, language=language, sync_map=sync_map
    )

    analyzed_summary = str(analyze.get("summary") or "").strip()
    if not analyzed_summary:
        if analyze.get("skipped"):
            analyzed_summary = str(analyze.get("reason") or "Config already present — analyze skipped")
        elif analyze.get("mapping_keys_inferred"):
            analyzed_summary = (
                f"Inferred {analyze.get('mapping_keys_inferred')} mapping keys from project samples"
            )
        else:
            analyzed_summary = "Not analyzed yet — run Analyze Project Context"

    batch = (run.get("last_smart_generate") or {}).get("batch_summary") or {}
    usable = (
        wf["SAVED"] > 0
        and coverage.get("missing_mapping_count", 0) == 0
        and wf["ERROR"] == 0
    )

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_event": run.get("last_event") or "none",
        "usable": usable,
        "verdict": (
            "Ready to merge saved code"
            if usable and merge_preview.get("included_count", len(merge_preview.get("included") or [])) > 0
            else "Review mappings and issues before merge"
        ),
        "total_testcase_count": total,
        "analyzed_context_summary": analyzed_summary,
        "fixture_detected": fixture,
        "api_patterns_detected": api_patterns,
        "mapping_candidates_detected": mapping_candidates,
        "coverage_ready_count": int(coverage.get("ready_for_local_generation") or 0),
        "missing_mapping_count": int(coverage.get("missing_mapping_count") or 0),
        "auto_accepted_mapping_count": auto_accepted,
        "mappings_requiring_review_count": len(mappings_review),
        "generated_saved_count": wf["SAVED"],
        "needs_review_count": wf["NEEDS_REVIEW"],
        "error_count": wf["ERROR"],
        "draft_count": wf["DRAFT"],
        "no_code_count": wf["NO_CODE"],
        "top_repeated_issues": top_issues,
        "top_missing_signals": list(coverage.get("top_missing_terms") or [])[:10],
        "unknown_apis": unknown_apis,
        "duplicate_test_names": dupes[:10],
        "mergeable_testcase_count": len(merge_preview.get("included") or []),
        "smart_batch_summary": batch,
        "coverage_warnings": list(coverage.get("warnings") or [])[:5],
    }
    gtest_state["smart_workflow_run_report"] = report
    return report


def format_smart_workflow_run_report_markdown(report: dict[str, Any], *, job_id: str = "") -> str:
    """Export run report as Markdown for engineers."""
    lines = [
        "# ALEX Smart Workflow Run Report",
        "",
        f"- **Generated:** {report.get('generated_at', '—')}",
        f"- **Job:** `{job_id or '—'}`",
        f"- **Last event:** {report.get('last_event', '—')}",
        f"- **Verdict:** {report.get('verdict', '—')}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total testcases | {report.get('total_testcase_count', 0)} |",
        f"| Context analyzed | {report.get('analyzed_context_summary', '—')} |",
        f"| Fixture detected | `{report.get('fixture_detected', '—')}` |",
        f"| Mapping candidates | {report.get('mapping_candidates_detected', 0)} |",
        f"| Coverage ready | {report.get('coverage_ready_count', 0)} |",
        f"| Missing mappings | {report.get('missing_mapping_count', 0)} |",
        f"| Auto-accepted mappings | {report.get('auto_accepted_mapping_count', 0)} |",
        f"| Mappings needing review | {report.get('mappings_requiring_review_count', 0)} |",
        f"| Generated SAVED | {report.get('generated_saved_count', 0)} |",
        f"| NEEDS_REVIEW | {report.get('needs_review_count', 0)} |",
        f"| ERROR | {report.get('error_count', 0)} |",
        f"| Mergeable (SAVED) | {report.get('mergeable_testcase_count', 0)} |",
        "",
    ]
    apis = report.get("api_patterns_detected") or []
    if apis:
        lines.append("## API patterns detected")
        lines.append("")
        for a in apis:
            lines.append(f"- {a}")
        lines.append("")

    missing = report.get("top_missing_signals") or []
    if missing:
        lines.append("## Top missing signals")
        lines.append("")
        for s in missing:
            lines.append(f"- `{s}`")
        lines.append("")

    issues = report.get("top_repeated_issues") or []
    if issues:
        lines.append("## Top repeated issues")
        lines.append("")
        for row in issues:
            lines.append(f"- ({row.get('count', 0)}×) {row.get('issue', '')}")
        lines.append("")

    unknown = report.get("unknown_apis") or []
    if unknown:
        lines.append("## Unknown APIs")
        lines.append("")
        for u in unknown:
            lines.append(f"- `{u}`")
        lines.append("")

    dupes = report.get("duplicate_test_names") or []
    if dupes:
        lines.append("## Duplicate test names")
        lines.append("")
        for d in dupes:
            lines.append(f"- `{d.get('test_name')}` — {d.get('count')} cases: {', '.join(d.get('candidate_ids') or [])}")
        lines.append("")

    warns = report.get("coverage_warnings") or []
    if warns:
        lines.append("## Coverage warnings")
        lines.append("")
        for w in warns:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by ALEX Test Code smart workflow*")
    return "\n".join(lines)


def build_copilot_mapping_prompt(proposals: list[dict[str, Any]], *, sample_excerpt: str = "") -> str:
    """Compact prompt for Copilot to infer missing signal mappings."""
    lines = [
        "Infer C++ mock/setter snippets for these testcase signals.",
        "Return YAML only, top-level keys per signal, with setter/getter/assertion fields.",
        "",
        "Signals:",
    ]
    for p in proposals[:40]:
        lines.append(f"- {p.get('signal')}: {p.get('evidence') or 'unknown'}")
    if sample_excerpt:
        lines.append("")
        lines.append("Sample code excerpt:")
        lines.append("```cpp")
        lines.append(sample_excerpt[:6000])
        lines.append("```")
    return "\n".join(lines)
