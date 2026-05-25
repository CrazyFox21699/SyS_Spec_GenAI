"""Resolve footnote cross-references to files, sheets, and logic blocks."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_SHEET_NORMALIZE_RE = re.compile(r"[^a-z0-9_]+")


def _basename(name: str) -> str:
    return os.path.basename(str(name or "").strip()).lower()


def _norm_sheet(name: str) -> str:
    return _SHEET_NORMALIZE_RE.sub("", str(name or "").lower())


def _index_classified_files(classified_files: list[dict[str, Any]]) -> dict[str, str]:
    """Map normalized basename -> original file path/name."""
    out: dict[str, str] = {}
    for row in classified_files or []:
        file_name = str(row.get("file") or row.get("path") or "").strip()
        if not file_name:
            continue
        base = _basename(file_name)
        out[base] = file_name
        stem = Path(base).stem.lower()
        if stem and stem not in out:
            out[stem] = file_name
    return out


def _logic_blocks_by_file_sheet(
    logic_blocks: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_file: dict[str, list[dict[str, Any]]] = {}
    by_sheet: dict[str, list[dict[str, Any]]] = {}
    for lb in logic_blocks or []:
        src = lb.get("source") if isinstance(lb.get("source"), dict) else {}
        file_name = _basename(str(src.get("file") or ""))
        sheet = _norm_sheet(str(src.get("sheet") or src.get("table") or ""))
        if file_name:
            by_file.setdefault(file_name, []).append(lb)
        if sheet:
            by_sheet.setdefault(sheet, []).append(lb)
    return by_file, by_sheet


def _condition_names_from_blocks(blocks: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for lb in blocks:
        for nm in (lb.get("name"), lb.get("id")):
            val = str(nm or "").strip()
            if val:
                names.add(val)
        raw = str(lb.get("raw_expression") or "")
        for m in re.finditer(r"\b([A-Z][A-Z0-9_]{2,})\b", raw):
            names.add(m.group(1))
    return sorted(names)


def resolve_cross_ref(
    ref: dict[str, Any],
    *,
    classified_files: list[dict[str, Any]] | None = None,
    logic_blocks: list[dict[str, Any]] | None = None,
    condition_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enrich one cross_ref stub with resolved targets."""
    kind = str(ref.get("type") or "").strip()
    text = str(ref.get("text") or "").strip()
    resolved = dict(ref)
    file_index = _index_classified_files(classified_files or [])
    blocks_by_file, blocks_by_sheet = _logic_blocks_by_file_sheet(logic_blocks or [])

    target_logic_ids: list[str] = []
    target_condition_names: list[str] = []
    resolved_file: str | None = None
    resolved_sheet: str | None = None

    if kind == "file":
        base = _basename(text)
        resolved_file = file_index.get(base) or file_index.get(Path(base).stem.lower())
        if resolved_file:
            for lb in blocks_by_file.get(_basename(resolved_file), []):
                lid = str(lb.get("id") or "").strip()
                if lid:
                    target_logic_ids.append(lid)
    elif kind == "sheet":
        sheet_key = _norm_sheet(text)
        resolved_sheet = text
        for lb in blocks_by_sheet.get(sheet_key, []):
            lid = str(lb.get("id") or "").strip()
            if lid:
                target_logic_ids.append(lid)
        for row in condition_definitions or []:
            src = row.get("source") if isinstance(row.get("source"), dict) else {}
            if _norm_sheet(str(src.get("sheet") or src.get("table") or "")) == sheet_key:
                nm = str(row.get("name") or "").strip()
                if nm:
                    target_condition_names.append(nm)
    elif kind == "condition_group":
        needle = text.lower()
        for lb in logic_blocks or []:
            name = str(lb.get("name") or "").lower()
            if needle in name or name in needle:
                lid = str(lb.get("id") or "").strip()
                if lid:
                    target_logic_ids.append(lid)
        for row in condition_definitions or []:
            nm = str(row.get("name") or "").strip()
            if nm and (needle in nm.lower() or nm.lower() in needle):
                target_condition_names.append(nm)

    # Deduplicate while preserving order
    seen_lids: set[str] = set()
    unique_logic_ids: list[str] = []
    for lid in target_logic_ids:
        if lid not in seen_lids:
            seen_lids.add(lid)
            unique_logic_ids.append(lid)

    resolved["resolved_file"] = resolved_file
    resolved["resolved_sheet"] = resolved_sheet
    resolved["target_logic_ids"] = unique_logic_ids
    resolved["target_condition_names"] = sorted(set(target_condition_names))
    resolved["resolved"] = bool(unique_logic_ids or target_condition_names or resolved_file)
    if unique_logic_ids:
        resolved["resolved_node"] = {
            "kind": "logic_blocks",
            "logic_ids": unique_logic_ids,
            "file": resolved_file,
            "sheet": resolved_sheet,
        }
    elif resolved_file:
        resolved["resolved_node"] = {"kind": "file", "file": resolved_file}
    elif resolved_sheet:
        resolved["resolved_node"] = {"kind": "sheet", "sheet": resolved_sheet}
    return resolved


def resolve_footnote_cross_refs(bundle: dict[str, Any]) -> dict[str, Any]:
    """Resolve cross_refs on all footnote_definitions; mutates bundle in place."""
    classified = bundle.get("classified_files") or []
    logic_blocks = bundle.get("logic_blocks") or []
    condition_defs = bundle.get("condition_definitions") or []
    resolved_count = 0
    for foot in bundle.get("footnote_definitions") or []:
        refs = foot.get("cross_refs") or []
        if not refs:
            body = str(foot.get("definition") or foot.get("raw_text") or "")
            from src.parsers.paragraph_extractor import _extract_cross_refs

            refs = _extract_cross_refs(body)
        enriched: list[dict[str, Any]] = []
        target_logic_ids: list[str] = []
        target_condition_names: list[str] = []
        for ref in refs:
            er = resolve_cross_ref(
                ref,
                classified_files=classified,
                logic_blocks=logic_blocks,
                condition_definitions=condition_defs,
            )
            enriched.append(er)
            if er.get("resolved"):
                resolved_count += 1
            target_logic_ids.extend(er.get("target_logic_ids") or [])
            target_condition_names.extend(er.get("target_condition_names") or [])
        foot["cross_refs"] = enriched
        if target_logic_ids:
            foot["target_logic_ids"] = sorted(set(str(x) for x in target_logic_ids if x))
        if target_condition_names:
            foot["target_condition_names"] = sorted(set(str(x) for x in target_condition_names if x))
    bundle["cross_file_resolution"] = {
        "footnote_count": len(bundle.get("footnote_definitions") or []),
        "resolved_ref_count": resolved_count,
    }
    return {"resolved_ref_count": resolved_count}
