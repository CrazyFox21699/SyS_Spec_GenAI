"""Merge newly attached reference files into an existing job bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.engine.footnote_materializer import materialize_footnote_attachments
from src.engine.cross_file_resolver import resolve_footnote_cross_refs
from src.parsers.excel_parser import extract_excel_workbook
from src.parsers.word_parser import extract_word_document
from src.parsers.pdf_parser import extract_pdf_document
from src.utils.config_path import get_config_path
from src.utils.yaml_utils import load_yaml

CONFIG_PATH = get_config_path()


def _dedupe_definitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        src = row.get("source") if isinstance(row.get("source"), dict) else {}
        file_name = str(src.get("file") or "")
        key = (name.upper(), file_name.lower())
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _dedupe_logic_blocks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        lid = str(row.get("id") or "").strip()
        if not lid or lid in seen:
            continue
        seen.add(lid)
        out.append(row)
    return out


def extract_reference_file(path: Path) -> dict[str, Any]:
    """Parse one reference file for incremental merge."""
    ext = path.suffix.lower()
    cfg = load_yaml(CONFIG_PATH)
    state_patterns = cfg.get("classification", {}).get("state_name_patterns", [])
    if ext in {".xlsx", ".xlsm"}:
        return extract_excel_workbook(path, state_patterns)
    if ext == ".docx":
        return extract_word_document(path)
    if ext == ".pdf":
        return extract_pdf_document(path)
    return {"error": f"Unsupported reference file type: {ext}"}


def merge_reference_extract(
    bundle: dict[str, Any],
    extracted: dict[str, Any],
    *,
    source_logic_id: str,
    file_name: str,
) -> dict[str, Any]:
    """Merge parsed extract into bundle without full re-analyze."""
    if extracted.get("error"):
        return {"ok": False, "reason": extracted.get("error")}

    merged_defs = 0
    merged_logic = 0
    merged_footnotes = 0

    for row in extracted.get("condition_definitions") or []:
        src = dict(row.get("source") or {})
        src.setdefault("file", file_name)
        src["reference_for"] = source_logic_id
        row = dict(row)
        row["source"] = src
        row.setdefault("logic_id", source_logic_id)
        bundle.setdefault("condition_definitions", []).append(row)
        merged_defs += 1

    ref_blocks: list[dict[str, Any]] = []
    for lb in extracted.get("logic_blocks") or []:
        block = dict(lb)
        block["reference_only"] = True
        block["reference_for"] = source_logic_id
        src = dict(block.get("source") or {})
        src.setdefault("file", file_name)
        block["source"] = src
        ref_blocks.append(block)
        merged_logic += 1
    if ref_blocks:
        existing = list(bundle.get("reference_logic_blocks") or [])
        existing.extend(ref_blocks)
        bundle["reference_logic_blocks"] = _dedupe_logic_blocks(existing)
        bundle.setdefault("logic_blocks", []).extend(ref_blocks)

    for foot in extracted.get("footnote_definitions") or []:
        row = dict(foot)
        row["logic_id"] = source_logic_id
        src = dict(row.get("source") or {})
        src.setdefault("file", file_name)
        row["source"] = src
        bundle.setdefault("footnote_definitions", []).append(row)
        merged_footnotes += 1

    bundle["condition_definitions"] = _dedupe_definitions(bundle.get("condition_definitions") or [])

    classified = list(bundle.get("classified_files") or [])
    if not any(str(c.get("file") or "").endswith(file_name) for c in classified):
        classified.append(
            {
                "file": file_name,
                "role": "reference_attachment",
                "file_type_label": "reference",
                "reference_for": source_logic_id,
            }
        )
        bundle["classified_files"] = classified

    resolve_footnote_cross_refs(bundle)
    mat = materialize_footnote_attachments(bundle, logic_ids=[source_logic_id])

    return {
        "ok": True,
        "merged_definitions": merged_defs,
        "merged_logic_blocks": merged_logic,
        "merged_footnotes": merged_footnotes,
        "materialized_count": mat.get("materialized_count", 0),
    }
