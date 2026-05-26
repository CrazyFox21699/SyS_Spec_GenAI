"""Create analysis jobs from imported bundles or TestSpec workbooks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.exporters.customer_testspec_exporter import derive_module_name
from src.importers.customer_testspec_importer import import_customer_testspec_workbook
from src.importers.synthetic_logic import slug, synthetic_logic_block


def _ensure_synthetic_logic_groups(bundle: dict[str, Any]) -> None:
    """Ensure every testcase logic_id has a logic block."""
    existing = {str(b.get("id") or "") for b in bundle.get("logic_blocks") or []}
    groups: dict[str, str] = {}
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        logic_id = str(trace.get("logic_id") or trace.get("logic_block") or "").strip()
        control = str(
            trace.get("control_name")
            or cand.get("test_function")
            or logic_id
            or "Imported tests"
        ).strip()
        if not logic_id:
            key = slug(control)
            logic_id = f"imported_{key}"
            trace["logic_id"] = logic_id
            trace.setdefault("control_name", control)
            cand["traceability"] = trace
        if logic_id not in groups:
            groups[logic_id] = control
    overlays = (bundle.get("ai_assists") or {}).get("candidate_overlays") or {}
    for cid, ov in overlays.items():
        logic_id = str(ov.get("logic_id") or "").strip()
        control = str(ov.get("control_name") or "").strip()
        if logic_id and logic_id not in groups:
            groups[logic_id] = control or logic_id
        elif not logic_id and control:
            logic_id = f"imported_{slug(control)}"
            ov["logic_id"] = logic_id
            overlays[cid] = ov
            groups.setdefault(logic_id, control)

    blocks = list(bundle.get("logic_blocks") or [])
    for logic_id, control in groups.items():
        if logic_id in existing:
            continue
        blocks.append(
            synthetic_logic_block(
                logic_id,
                control,
                source={"kind": "import_bootstrap", "logic_id": logic_id},
            )
        )
        existing.add(logic_id)
    bundle["logic_blocks"] = blocks
    if not bundle.get("resolved_logic_blocks"):
        bundle["resolved_logic_blocks"] = [dict(b) for b in blocks]


def minimal_bundle(*, source: str = "imported", label: str = "") -> dict[str, Any]:
    return {
        "version": "0.2",
        "product": {"name": "ALEX", "display_name": "ALEX", "version": "0.2"},
        "strict_mode": False,
        "bootstrap_source": source,
        "bootstrap_label": label,
        "classified_files": [],
        "logic_blocks": [],
        "resolved_logic_blocks": [],
        "test_candidates": [],
        "issues": [],
        "unresolved_items": [],
        "signals": [],
        "states": [],
        "transitions": [],
        "condition_definitions": [],
        "summary": {
            "logic_blocks": 0,
            "test_candidates": 0,
            "bootstrap_source": source,
        },
        "ai_assists": {"candidate_overlays": {}},
    }


def _finalize_import_bundle(bundle: dict[str, Any], *, source: str, label: str = "") -> dict[str, Any]:
    bundle.setdefault("version", "0.2")
    bundle.setdefault("product", {"name": "ALEX", "display_name": "ALEX", "version": "0.2"})
    bundle["bootstrap_source"] = source
    if label:
        bundle["bootstrap_label"] = label
    _ensure_synthetic_logic_groups(bundle)
    tc_count = len(bundle.get("test_candidates") or [])
    lb_count = len(bundle.get("logic_blocks") or [])
    summary = dict(bundle.get("summary") or {})
    summary.update(
        {
            "test_candidates": tc_count,
            "logic_blocks": lb_count,
            "logic_groups": lb_count,
            "bootstrap_source": source,
        }
    )
    bundle["summary"] = summary
    return bundle


def bootstrap_from_bundle_dict(
    bundle: dict[str, Any],
    *,
    source: str = "imported_yaml",
    label: str = "",
) -> dict[str, Any]:
    merged = minimal_bundle(source=source, label=label)
    merged.update(bundle)
    merged.setdefault("ai_assists", {})
    merged["ai_assists"].setdefault("candidate_overlays", {})
    if bundle.get("ai_assists"):
        for key, val in bundle["ai_assists"].items():
            if key == "candidate_overlays" and isinstance(val, dict):
                merged["ai_assists"]["candidate_overlays"].update(val)
            else:
                merged["ai_assists"][key] = val
    return _finalize_import_bundle(merged, source=source, label=label)


def bootstrap_from_testspec_xlsx(
    path: Path,
    *,
    language: str = "EN",
    module_name: str = "",
) -> dict[str, Any]:
    imported = import_customer_testspec_workbook(path, language=language)
    label = module_name or derive_module_name(imported) or path.stem
    bundle = minimal_bundle(source="imported_testspec", label=label)
    bundle["classified_files"] = [
        {
            "file": str(path),
            "name": path.name,
            "role": "test_reference",
            "file_type": "excel",
        }
    ]
    bundle["test_candidates"] = imported.get("test_candidates") or []
    bundle["ai_assists"]["candidate_overlays"] = imported.get("candidate_overlays") or {}
    bundle["logic_blocks"] = imported.get("logic_blocks") or []
    if imported.get("sheet_summary"):
        bundle["excel_import"] = {"sheets": imported["sheet_summary"]}
    return _finalize_import_bundle(bundle, source="imported_testspec", label=label)
