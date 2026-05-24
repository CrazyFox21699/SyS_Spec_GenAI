"""End-to-end analyze pipeline for v0.1."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from src.engine.description_improver import suggest_description_improvement
from src.engine.issue_collector import collect_issues, enrich_review_fields
from src.engine.logic_reconciler import reconcile_logic_blocks

from src.classifiers.file_classifier import classify_input_dir
from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.review_report_generator import write_review_package
from src.engine.test_candidate_generator import (
    generate_candidates,
    generate_candidates_from_logic_blocks,
    generate_candidates_from_test_references,
    generate_negative_candidates_from_ast,
)
from src.engine.timing_normalizer import normalize_timing_expressions
from src.engine.logic_tree_renderer import flatten_ast_to_rows, render_tree_lines
from src.engine.traceability_builder import build_traceability
from src.engine.traceability_matrix_builder import build_logic_path_coverage, build_traceability_matrix
from src.engine.candidate_safety import apply_candidate_safety
from src.engine.diagram_semantic_builder import build_diagram_semantic_graph
from src.engine.logic_review_builder import build_logic_review_items
from src.engine.evidence_registry import build_evidence_registry
from src.engine.source_index import build_source_index
from src.engine.term_role_classifier import build_term_role_index
from src.engine.memory_semantics_parser import enrich_condition_definitions
from src.engine.timer_qualifier_parser import enrich_logic_blocks
from src.engine.spec_understanding_report import build_spec_understanding_report
from src.engine.logic_atom import (
    atom_signal_names,
    collect_atoms_from_tree,
    enrich_tree_with_atoms,
    is_atom_self_resolved,
)
from src.engine.understanding_gate import build_resolved_logic_blocks
from src.engine.two_column_logic_parser import collect_condition_names
from src.exporters.excel_exporter import export_all_excel
from src.llm.ollama_client import interpret_japanese_block
from src.parsers.code_parser import extract_code_reference
from src.parsers.excel_parser import extract_excel_workbook
from src.parsers.image_parser import extract_image_metadata
from src.parsers.pdf_parser import extract_pdf_document
from src.parsers.word_parser import extract_word_document, peek_word_text
from src.parsers.two_column_table_parser import FOOTNOTE_RE
from src.engine.lifecycle_transition_builder import lifecycle_to_transitions
from src.engine.transition_logic_linker import infer_transition_logic_links
from src.engine.diagram_edge_classifier import enrich_transition_with_edge_role
from src.parsers.signal_table_parser import signal_names_for_definitions
from src.utils.file_filters import is_ingestible_file, skip_reason
from src.utils.feature_flags import feature_enabled
from src.utils.io_utils import backup_output_files
from src.utils.text_utils import contains_japanese
from src.utils.yaml_utils import dump_yaml, load_yaml


OUTPUT_ARTIFACTS = [
    "classified_files.yaml",
    "extracted_signals.yaml",
    "state_machine.yaml",
    "condition_trees.yaml",
    "timing_constraints.yaml",
    "traceability.yaml",
    "generated_test_spec.yaml",
    "generated_test_spec.md",
    "generated_test_spec.xlsx",
    "review_package.xlsx",
    "logic_traceability.xlsx",
    "issue_list.xlsx",
    "japanese_interpretations.yaml",
]


def _dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in signals:
        n = str(s.get("name", "")).strip()
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(s)
    return out


def _signals_from_pdf_heuristic(pdf_path: Path, text: str) -> list[dict[str, Any]]:
    """Very loose: tokens that look like Mode_cmd / OEM_xxx."""
    sigs: list[dict[str, Any]] = []
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9_]{2,40})\b", text):
        name = m.group(1)
        if name in {"The", "And", "For", "When", "Then", "Page"}:
            continue
        sigs.append(
            {
                "name": name,
                "description": "",
                "direction": "unknown",
                "data_length": None,
                "sender": None,
                "receiver": None,
                "values": [],
                "initial_value": None,
                "fail_safe_value": None,
                "source": {"file": pdf_path.name, "section": None, "table": None, "row": None},
                "confidence": "low",
                "review_required": True,
                "note": "Heuristic token from PDF text layer",
            }
        )
        if len(sigs) >= 80:
            break
    return _dedupe_signals(sigs)


def _progress(cb: Callable[[str, int], None] | None, step: str, pct: int) -> None:
    if cb:
        cb(step, pct)


def run_analyze(
    input_dir: Path,
    output_dir: Path,
    config_path: Path,
    *,
    force: bool = False,
    selected_files: set[str] | None = None,
    progress: Callable[[str, int], None] | None = None,
    strict_mode: bool | None = None,
    enable_llm: bool | None = None,
) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    if enable_llm is not None:
        cfg.setdefault("llm", {})["enabled"] = enable_llm
    if strict_mode is None:
        strict_mode = bool(cfg.get("ui", {}).get("strict_mode", False))

    if not input_dir.is_dir():
        raise SystemExit(f"Input not a directory: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    if cfg.get("output", {}).get("backup_existing_files", True) and not force:
        backup_output_files(output_dir, OUTPUT_ARTIFACTS)

    state_patterns = cfg.get("classification", {}).get("state_name_patterns", [])

    _progress(progress, "Classifying selected files", 5)
    classified_objs = classify_input_dir(input_dir, cfg)
    if selected_files is not None:
        sel = {str(Path(p).resolve()) for p in selected_files}
        sel |= {str(Path(p).name) for p in selected_files}
        classified_objs = [
            o
            for o in classified_objs
            if str(Path(o.file).resolve()) in sel or Path(o.file).name in sel
        ]
    classified_rows = [
        {
            "file": o.file,
            "file_type": o.file_type,
            "file_type_label": o.file_type_label,
            "role": o.role,
            "reason": o.reason,
            "user_confirmation_suggested": o.user_confirmation_suggested,
        }
        for o in classified_objs
    ]
    dump_yaml(output_dir / "classified_files.yaml", {"classified_files": classified_rows})

    _progress(progress, "Extracting signals", 15)
    signals: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    logic_blocks: list[dict[str, Any]] = []
    condition_definitions: list[dict[str, Any]] = []
    test_reference_rows: list[dict[str, Any]] = []
    two_column_tables: list[dict[str, Any]] = []
    alias_map: list[dict[str, Any]] = []
    footnote_definitions: list[dict[str, Any]] = []
    code_definitions: list[dict[str, Any]] = []
    state_rules: list[dict[str, Any]] = []
    state_machines: list[dict[str, Any]] = []
    diagram_meta: list[dict[str, Any]] = []
    code_refs: list[dict[str, Any]] = []
    japanese_blocks: list[dict[str, Any]] = []
    ingest_skipped: list[dict[str, Any]] = []
    merged_cell_evidence: list[dict[str, Any]] = []
    review_annotations: list[dict[str, Any]] = []
    retention_rules: list[dict[str, Any]] = []
    spec_profiles: list[dict[str, Any]] = []

    for o in classified_objs:
        p = Path(o.file)
        if not p.exists():
            continue
        if not is_ingestible_file(p):
            reason = skip_reason(p)
            ingest_skipped.append({"file": str(p), "reason": reason})
            continue
        role = o.role
        if p.suffix.lower() == ".docx":
            wd = extract_word_document(p, cfg=cfg)
            if wd.get("error"):
                ingest_skipped.append({"file": str(p), "reason": wd.get("message", "invalid docx")})
                continue
            signals.extend(wd.get("signals", []))
            logic_blocks.extend(wd.get("logic_blocks", []))
            transitions.extend(wd.get("transitions", []))
            condition_definitions.extend(wd.get("condition_definitions", []))
            test_reference_rows.extend(wd.get("test_reference_rows", []))
            two_column_tables.extend(wd.get("two_column_tables", []))
            alias_map.extend(wd.get("alias_map", []))
            footnote_definitions.extend(wd.get("footnote_definitions", []))
            code_definitions.extend(wd.get("code_definitions", []))
            state_rules.extend(wd.get("state_rules", []))
            state_machines.extend(wd.get("state_machines", []))
            diagram_meta.extend(wd.get("embedded_image_analysis", []))
            merged_cell_evidence.extend(wd.get("merged_cell_evidence", []))
            retention_rules.extend(wd.get("retention_rules", []))
            profile = wd.get("spec_profile")
            if isinstance(profile, dict) and profile:
                spec_profiles.append(profile)
        elif role == "system_spec" and p.suffix.lower() == ".pdf":
            blob = extract_pdf_document(p)
            text = "\n".join(pg["text"] for pg in blob.get("pages", []))
            signals.extend(_signals_from_pdf_heuristic(p, text))
            condition_definitions.extend(blob.get("condition_definitions", []))
            transitions.extend(blob.get("transitions", []))
            state_rules.extend(blob.get("state_rules", []))
            code_definitions.extend(blob.get("code_definitions", []))
            diagram_meta.extend(blob.get("image_analyses", []))
        elif p.suffix.lower() in {".xlsx", ".xlsm"}:
            ex = extract_excel_workbook(
                p,
                state_patterns,
                include_comments=feature_enabled(cfg, "excel_annotations", default=True),
            )
            logic_blocks.extend(ex.get("logic_blocks", []))
            signals.extend(ex.get("signals") or [])
            condition_definitions.extend(ex.get("condition_definitions", []))
            transitions.extend(ex.get("transition_candidates", []))
            state_rules.extend(ex.get("state_rules", []))
            diagram_meta.extend(ex.get("diagram_meta", []))
            merged_cell_evidence.extend(ex.get("merged_cell_evidence", []))
            review_annotations.extend(ex.get("review_annotations", []))
        elif role == "diagram":
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
                img_meta = extract_image_metadata(p)
                diagram_meta.append(img_meta)
                condition_definitions.extend(img_meta.get("condition_definitions", []))
                transitions.extend(img_meta.get("transitions", []))
                state_rules.extend(img_meta.get("state_rules", []))
                code_definitions.extend(img_meta.get("code_definitions", []))
            elif p.suffix.lower() == ".pdf":
                blob = extract_pdf_document(p)
                text = "\n".join(pg["text"] for pg in blob.get("pages", []))
                if contains_japanese(text):
                    japanese_blocks.append({"file": p.name, "snippet": text[:800]})
                condition_definitions.extend(blob.get("condition_definitions", []))
                transitions.extend(blob.get("transitions", []))
                state_rules.extend(blob.get("state_rules", []))
                code_definitions.extend(blob.get("code_definitions", []))
                diagram_meta.extend(blob.get("image_analyses", []))
        elif role == "code_reference":
            code_refs.append(extract_code_reference(p))

    signals = _dedupe_signals(signals)
    condition_definitions.extend(signal_names_for_definitions(signals))
    lifecycle_trans = lifecycle_to_transitions(state_machines)
    if lifecycle_trans:
        transitions.extend(lifecycle_trans)
    transitions = [enrich_transition_with_edge_role(dict(t)) for t in transitions]
    transitions = infer_transition_logic_links(transitions, logic_blocks)
    _progress(progress, "Extracting states and transitions", 30)

    # Collect Japanese snippets from Word/Excel peeks
    for o in classified_objs:
        p = Path(o.file)
        if not p.exists():
            continue
        if p.suffix.lower() == ".docx":
            t = peek_word_text(p, 4000)
            if contains_japanese(t):
                japanese_blocks.append({"file": p.name, "snippet": t[:1200]})

    jp_interpretations: list[dict[str, Any]] = []
    for block in japanese_blocks[:15]:
        snip = block["snippet"]
        if cfg.get("llm", {}).get("enabled"):
            interp = interpret_japanese_block(snip, cfg)
            if interp:
                jp_interpretations.append(interp)
        else:
            jp_interpretations.append(
                {
                    "raw_source_text": snip,
                    "ai_translation_en": "",
                    "ai_technical_interpretation": {"given": [], "when": [], "then": []},
                    "confidence": "low",
                    "review_required": {"comtor": True, "engineer": True},
                    "source": "not_translated_llm_disabled",
                }
            )
    dump_yaml(output_dir / "japanese_interpretations.yaml", {"japanese_interpretations": jp_interpretations})

    states_set: dict[str, dict[str, Any]] = {}
    for t in transitions:
        for key in ("from_state", "to_state"):
            name = t.get(key)
            if isinstance(name, str) and name.strip():
                states_set.setdefault(name.strip(), {"name": name.strip(), "mode": None, "description": None})

    diagram_semantics = build_diagram_semantic_graph(
        transitions=transitions,
        diagrams=diagram_meta,
        state_rules=state_rules,
    )
    for st in diagram_semantics.get("states", []):
        name = str(st.get("state") or "").strip()
        if not name:
            continue
        states_set.setdefault(
            name,
            {
                "name": name,
                "mode": None,
                "description": "",
                "semantic_labels": st.get("labels", []),
                "source_types": st.get("source_types", []),
            },
        )

    state_machine_doc = {
        "states": list(states_set.values()),
        "transitions": transitions,
        "diagram_semantics": diagram_semantics,
        "source_files": [o["file"] for o in classified_rows],
    }
    dump_yaml(output_dir / "state_machine.yaml", state_machine_doc)
    dump_yaml(output_dir / "extracted_signals.yaml", {"signals": signals})

    _progress(progress, "Reconciling logic tables and formulas", 42)
    logic_blocks, logic_reconcile_issues = reconcile_logic_blocks(logic_blocks)
    if feature_enabled(cfg, "formal_logic_ir_v2", default=True):
        enrich_logic_blocks(logic_blocks, condition_definitions)
    if feature_enabled(cfg, "memory_semantics_parser", default=True):
        enrich_condition_definitions(condition_definitions)
    dump_yaml(output_dir / "logic_blocks.yaml", {"logic_blocks": logic_blocks})

    _progress(progress, "Building condition trees", 45)
    # Build condition_definitions index for reference resolution
    def_index = {d["name"]: d for d in condition_definitions if d.get("name")}

    condition_entries: list[dict[str, Any]] = []
    timing_all: list[dict[str, Any]] = []

    for lb in logic_blocks:
        raw = str(lb.get("raw_expression", ""))
        tree = lb.get("tree") or parse_condition_tree(raw)
        norms = normalize_timing_expressions(raw, cfg)
        timing_all.extend(norms)
        condition_entries.append(
            {
                "transition_id": lb.get("id"),
                "name": lb.get("name"),
                "raw_condition": raw,
                "tree": tree,
                "timing_normalizations": norms,
                "source": lb.get("source"),
                "block_type": lb.get("block_type"),
                "parse_status": lb.get("parse_status", tree.get("parse_status")),
            }
        )

    for t in transitions:
        raw = str(t.get("raw_condition", ""))
        tree = t.get("condition_tree") or parse_condition_tree(raw)
        norms = normalize_timing_expressions(raw, cfg)
        timing_all.extend(norms)
        condition_entries.append(
            {
                "transition_id": t.get("id"),
                "raw_condition": raw,
                "tree": tree,
                "timing_normalizations": norms,
                "source": t.get("source"),
            }
        )
    dump_yaml(output_dir / "condition_trees.yaml", {"condition_trees": condition_entries})

    # Dedupe timing list by raw_text
    seen_t = set()
    timing_unique: list[dict[str, Any]] = []
    for tn in timing_all:
        key = tn.get("raw_text", str(tn))
        if key in seen_t:
            continue
        seen_t.add(key)
        timing_unique.append(tn)
    dump_yaml(output_dir / "timing_constraints.yaml", {"timing_constraints": timing_unique})

    _progress(progress, "Building traceability", 60)
    trans_trace = build_traceability(signals, transitions, [])
    candidates, cand_trace = generate_candidates(
        transitions,
        signals,
        timing_unique,
        condition_definitions=condition_definitions,
        footnote_definitions=footnote_definitions,
    )
    resolved_logic_blocks: list[dict[str, Any]] = []
    if feature_enabled(cfg, "atom_model", default=False) or feature_enabled(
        cfg, "understanding_gate", default=False
    ):
        for lb in logic_blocks:
            if lb.get("tree"):
                lb["tree"] = enrich_tree_with_atoms(dict(lb.get("tree") or {}))
        resolved_logic_blocks = build_resolved_logic_blocks(
            logic_blocks,
            footnote_definitions=footnote_definitions,
            condition_definitions=condition_definitions,
            alias_map=alias_map,
        )
        for lb, rb in zip(logic_blocks, resolved_logic_blocks):
            lb["gate_status"] = rb.get("gate_status")
            lb["can_generate_candidates"] = rb.get("can_generate_candidates", False)
            lb["understanding_gaps"] = rb.get("gaps", [])

    test_gen = cfg.get("test_generation") if isinstance(cfg.get("test_generation"), dict) else {}
    coverage_mode = str(test_gen.get("coverage", "legacy"))
    if feature_enabled(cfg, "atom_model", default=False) and coverage_mode != "legacy":
        coverage_mode = "mcdc"
    max_expansion = int(test_gen.get("max_expansion_factor", 32))

    lb_cands, lb_trace = generate_candidates_from_logic_blocks(
        logic_blocks,
        start_index=len(candidates),
        condition_definitions=condition_definitions,
        footnote_definitions=footnote_definitions,
        resolved_logic_blocks=resolved_logic_blocks or None,
        coverage_mode=coverage_mode,
        max_expansion_factor=max_expansion,
    )
    candidates.extend(lb_cands)
    cand_trace.extend(lb_trace)
    ref_cands, ref_trace = generate_candidates_from_test_references(
        test_reference_rows, start_index=len(candidates)
    )
    candidates.extend(ref_cands)
    cand_trace.extend(ref_trace)
    neg_cands, neg_trace = generate_negative_candidates_from_ast(
        logic_blocks, start_index=len(candidates)
    )
    candidates.extend(neg_cands)
    cand_trace.extend(neg_trace)

    known_conditions: set[str] = set()
    for d in condition_definitions:
        if d.get("name"):
            known_conditions.add(str(d["name"]))
    for sig in signals:
        if sig.get("name"):
            known_conditions.add(str(sig["name"]))
    for cd in code_definitions:
        if cd.get("name"):
            known_conditions.add(str(cd["name"]))
    known_targets = {a.get("target", "") for a in alias_map}
    known_aliases = {a.get("alias", "") for a in alias_map}

    for lb in logic_blocks:
        lb["unresolved_refs"] = []
        tree = lb.get("tree") or {}
        if feature_enabled(cfg, "atom_model", default=False):
            atoms_by_sig = {a.get("signal"): a for a in collect_atoms_from_tree(tree)}
            for sig in atom_signal_names(tree):
                atom = atoms_by_sig.get(sig) or {}
                if is_atom_self_resolved(atom):
                    continue
                if sig not in known_conditions and sig not in known_targets and sig not in known_aliases:
                    lb["unresolved_refs"].append(sig)
        else:
            for nm in collect_condition_names(tree):
                base = FOOTNOTE_RE.sub("", nm).strip()
                sig_only = base.split("=")[0].strip() if "=" in base else base
                if (
                    sig_only
                    and sig_only not in known_conditions
                    and sig_only not in known_targets
                    and sig_only not in known_aliases
                ):
                    if not any(op in base.upper() for op in (" AND ", " OR ")):
                        lb.setdefault("unresolved_refs", []).append(sig_only)

    for c in candidates:
        c.setdefault("review_status", "pending")
        c.setdefault("status", "candidate")
        imp = suggest_description_improvement(c)
        if imp:
            c["improvement_suggestion"] = imp

    _progress(progress, "Detecting unresolved logic", 75)
    issues, unresolved_items = collect_issues(
        classified=classified_rows,
        signals=signals,
        transitions=transitions,
        condition_entries=condition_entries,
        timing=timing_unique,
        candidates=candidates,
        diagrams=diagram_meta,
        japanese=jp_interpretations,
        logic_blocks=logic_blocks,
        ingest_skipped=ingest_skipped,
        two_column_tables=two_column_tables,
        diagram_transitions=[t for t in transitions if t.get("derivation", "").startswith("diagram")],
        strict_mode=strict_mode,
    )
    issues.extend(logic_reconcile_issues)
    candidates = apply_candidate_safety(candidates, logic_blocks, issues, strict_mode=strict_mode)

    trace_yaml = {
        "transition_context": trans_trace,
        "test_traceability": cand_trace,
    }
    dump_yaml(output_dir / "traceability.yaml", trace_yaml)

    test_spec = {
        "version": "0.1-candidate",
        "test_cases": [
            {
                "id": c["id"],
                "test_function": c.get("test_function"),
                "event": c.get("event"),
                "use_case_description": c.get("use_case_description"),
                "precondition": c.get("precondition"),
                "operation": c.get("operation"),
                "expectation": c.get("expectation"),
                "traceability": c.get("traceability"),
                "confidence": c.get("confidence"),
                "review_required": c.get("review_required"),
                "status": "candidate_not_approved",
            }
            for c in candidates
        ],
    }
    dump_yaml(output_dir / "generated_test_spec.yaml", test_spec)

    md_lines = [
        "# Generated test specification (candidates only)",
        "",
        "| No | Test Function | Event | Use Case / Description | Operation | Expectation | Review Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in candidates:
        op = str(c.get("operation", "")).replace("|", "\\|")[:200]
        ex = str(c.get("expectation", "")).replace("|", "\\|")[:200]
        md_lines.append(
            f"| {c.get('id')} | {c.get('test_function')} | {c.get('event')} | "
            f"{str(c.get('use_case_description',''))[:80].replace('|','/')} | {op} | {ex} | candidate — review required |"
        )
    (output_dir / "generated_test_spec.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    questions: list[str] = []
    for tn in timing_unique:
        if tn.get("review_required"):
            questions.append(
                f"Confirm timing interpretation: raw `{tn.get('raw_text')}` interpreted as `{tn.get('interpreted_as')}` — correct?"
            )
    for s in signals[:20]:
        if s.get("confidence") == "low":
            questions.append(f"Confirm signal `{s.get('name')}` extracted from `{s.get('source',{}).get('file')}` — correct?")
    for o in classified_objs:
        if o.user_confirmation_suggested:
            questions.append(
                f"Confirm file type for `{o.file}`: proposed `{o.file_type_label}`."
            )

    logic_ast_rows: list[dict[str, Any]] = []
    logic_tree_views: list[dict[str, Any]] = []
    for lb in logic_blocks:
        tid = lb.get("id", lb.get("name", ""))
        tree = lb.get("tree") or {}
        logic_ast_rows.extend(flatten_ast_to_rows(tid, tree))
        logic_tree_views.append(
            {
                "tree_id": tid,
                "name": lb.get("name"),
                "expression": lb.get("raw_expression"),
                "lines": render_tree_lines(tree),
                "issues": lb.get("issues", []),
            }
        )

    traceability_matrix = build_traceability_matrix(
        candidates, logic_blocks, issues, timing=timing_unique
    )
    logic_path_coverage = build_logic_path_coverage(candidates, logic_blocks)

    description_improvements = []
    for c in candidates:
        imp = c.get("improvement_suggestion")
        if imp:
            description_improvements.append(
                {
                    "test_case_id": c.get("id"),
                    "current_description": c.get("use_case_description"),
                    "suggested_description": imp.get("suggested_description"),
                    "reason": imp.get("reason"),
                    "missing_information": imp.get("missing_information") or imp.get("missing_in_current"),
                    "added_information": imp.get("added_information"),
                    "added_information": imp.get("added_information"),
                    "source_evidence": imp.get("source_evidence"),
                    "confidence": imp.get("confidence"),
                    "review_status": c.get("review_status", "pending"),
                }
            )

    _progress(progress, "Exporting Excel workbooks", 88)
    review_questions_list = questions + [i["message"] for i in issues if i["severity"] == "error"]

    _progress(progress, "Generating review package", 90)
    classified_for_review = classified_rows
    write_review_package(
        output_dir,
        classified_for_review,
        signals,
        state_machine_doc,
        condition_entries,
        timing_unique,
        cand_trace,
        candidates,
        review_questions_list,
        logic_blocks=logic_blocks,
        condition_definitions=condition_definitions,
        test_reference_rows=test_reference_rows,
        ingest_skipped=ingest_skipped,
    )

    product_cfg = cfg.get("product") or {}
    evidence_registry = build_evidence_registry(
        merged_cell_evidence=merged_cell_evidence,
        footnote_definitions=footnote_definitions,
        alias_map=alias_map,
        logic_blocks=logic_blocks,
        condition_definitions=condition_definitions,
        diagram_meta=diagram_meta,
    )

    term_roles = build_term_role_index(
        {
            "logic_blocks": logic_blocks,
            "condition_definitions": condition_definitions,
            "states": state_machine_doc.get("states", []),
            "footnote_definitions": footnote_definitions,
        }
    )
    source_index = build_source_index(
        {
            "transitions": transitions,
            "logic_blocks": logic_blocks,
            "diagrams": diagram_meta,
            "states": state_machine_doc.get("states", []),
            "diagram_semantics": diagram_semantics,
            "footnote_definitions": footnote_definitions,
        }
    ) if feature_enabled(cfg, "source_index", default=False) else {}

    ui_bundle = {
        "version": "0.2",
        "product": {
            "name": product_cfg.get("name", "ALEX"),
            "display_name": product_cfg.get("display_name", "ALEX"),
            "version": product_cfg.get("version", "0.2"),
        },
        "strict_mode": strict_mode,
        "evidence_registry": evidence_registry,
        "classified_files": classified_rows,
        "ingest_skipped": ingest_skipped,
        "signals": enrich_review_fields(signals, "signal"),
        "states": enrich_review_fields(state_machine_doc.get("states", []), "state"),
        "transitions": enrich_review_fields(transitions, "transition"),
        "logic_blocks": logic_blocks,
        "resolved_logic_blocks": resolved_logic_blocks,
        "condition_definitions": condition_definitions,
        "test_reference_rows": test_reference_rows,
        "condition_trees": condition_entries,
        "timing_constraints": enrich_review_fields(timing_unique, "timing"),
        "outputs": [],
        "japanese_interpretations": jp_interpretations,
        "traceability": trace_yaml,
        "test_candidates": candidates,
        "issues": issues,
        "unresolved_items": unresolved_items,
        "diagrams": diagram_meta,
        "code_references": code_refs,
        "two_column_tables": two_column_tables,
        "alias_map": alias_map,
        "footnote_definitions": footnote_definitions,
        "term_roles": term_roles,
        "source_index": source_index,
        "code_definitions": code_definitions,
        "state_rules": state_rules,
        "state_machines": state_machines,
        "retention_rules": retention_rules,
        "review_annotations": review_annotations,
        "spec_profiles": spec_profiles,
        "diagram_semantics": diagram_semantics,
        "traceability_matrix": traceability_matrix,
        "logic_ast_rows": logic_ast_rows,
        "logic_tree_views": logic_tree_views,
        "logic_path_coverage": logic_path_coverage,
        "description_improvements": description_improvements,
        "logic_review_items": build_logic_review_items(
            logic_blocks,
            two_column_tables,
            candidates,
            issues,
            condition_definitions,
            alias_map,
            footnote_definitions,
            [],
            [],
            resolved_logic_blocks=resolved_logic_blocks,
        ),
        "review_questions": review_questions_list,
        "summary": {},
    }
    from src.engine.cross_file_resolver import resolve_footnote_cross_refs
    from src.engine.footnote_materializer import link_footnotes_to_logic_blocks, materialize_footnote_attachments
    from src.engine.path_tc_matrix import build_path_tc_matrix, enrich_candidate_coverage

    link_footnotes_to_logic_blocks(ui_bundle)
    resolve_footnote_cross_refs(ui_bundle)
    materialize_footnote_attachments(ui_bundle)
    path_tc_matrices: dict[str, Any] = {}
    for lb in logic_blocks:
        lid = str(lb.get("id") or "")
        if lid:
            path_tc_matrices[lid] = build_path_tc_matrix(ui_bundle, lid)
    ui_bundle["path_tc_matrices"] = path_tc_matrices
    enrich_candidate_coverage(ui_bundle)
    spec_understanding = build_spec_understanding_report(
        classified_files=classified_rows,
        logic_blocks=logic_blocks,
        condition_definitions=condition_definitions,
        issues=issues,
        unresolved_items=unresolved_items,
        two_column_tables=two_column_tables,
        ingest_skipped=ingest_skipped,
    )
    ui_bundle["spec_understanding"] = spec_understanding
    if feature_enabled(cfg, "document_map", default=True):
        from src.engine.document_graph_builder import build_document_graph
        ui_bundle["document_graph"] = build_document_graph(ui_bundle)
    ui_bundle["summary"] = {
        "files_selected": len(classified_rows),
        "signals": len(signals),
        "states": len(state_machine_doc.get("states", [])),
        "transitions": len(transitions),
        "diagram_semantic_edges": diagram_semantics.get("summary", {}).get("edges_total", 0),
        "logic_blocks": len(logic_blocks),
        "condition_definitions": len(condition_definitions),
        "ingest_skipped": len(ingest_skipped),
        "test_candidates": len(candidates),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "review_required": sum(1 for c in candidates if c.get("review_required")),
        "understanding_percent": spec_understanding["overall"]["understanding_percent"],
        "understanding_status": spec_understanding["overall"]["status"],
        "evidence_refs_total": evidence_registry.get("total", 0),
        "document_graph_nodes": (ui_bundle.get("document_graph") or {}).get("summary", {}).get("node_count", 0),
        "document_graph_edges": (
            (ui_bundle.get("document_graph") or {}).get("summary", {}).get("edge_count", 0)
            + (ui_bundle.get("document_graph") or {}).get("summary", {}).get("user_edge_count", 0)
        ),
    }
    dump_yaml(output_dir / "ui_bundle.yaml", ui_bundle)
    try:
        excel_paths = export_all_excel(output_dir, ui_bundle)
        ui_bundle["excel_exports"] = excel_paths
        dump_yaml(output_dir / "ui_bundle.yaml", ui_bundle)
    except Exception as exc:  # noqa: BLE001
        issues.append(
            {
                "id": "ERR_XLSX_001",
                "severity": "warning",
                "type": "excel_export_failed",
                "message": f"Excel export failed: {exc}",
                "required_action": "Check openpyxl / disk permissions",
                "can_export": True,
            }
        )
    _progress(progress, "Ready for review", 100)
    return ui_bundle
