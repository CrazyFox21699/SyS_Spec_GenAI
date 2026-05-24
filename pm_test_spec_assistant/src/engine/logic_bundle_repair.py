"""Repair logic blocks corrupted by older merge-grid parsing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.engine.timer_qualifier_parser import enrich_logic_blocks
from src.parsers.word_parser import extract_word_document
from src.utils.feature_flags import feature_enabled

_CORRUPT_OR_RE = re.compile(r"^\(\s*OR(?:\s+OR)+\s*\)$", re.I)
_GATE_TOKENS = frozenset({"OR", "AND", "NOT"})


def is_corrupt_or_only_expression(expr: str) -> bool:
    """Detect expressions like (OR OR OR OR) from broken merge-grid parse."""
    text = str(expr or "").strip()
    if not text:
        return False
    if "(OR OR" in text.upper():
        return True
    if _CORRUPT_OR_RE.match(text):
        return True
    return False


def _normalize_expr(expr: str) -> str:
    return re.sub(r"\s+", " ", str(expr or "").strip().upper())


def _collect_condition_leaves(node: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    if node.get("type") == "condition":
        return [node]
    leaves: list[dict[str, Any]] = []
    for child in node.get("children") or []:
        if isinstance(child, dict):
            leaves.extend(_collect_condition_leaves(child))
    return leaves


def is_broken_gate_tree(tree: dict[str, Any] | None) -> bool:
    """Detect trees where gate tokens were parsed as conditions (all OR leaves)."""
    if not isinstance(tree, dict) or not tree:
        return False
    leaves = _collect_condition_leaves(tree)
    if not leaves:
        return tree.get("type") in _GATE_TOKENS
    gate_leaf_names = [
        str(leaf.get("name") or leaf.get("raw_text") or "").strip().upper()
        for leaf in leaves
    ]
    if gate_leaf_names and all(name in _GATE_TOKENS for name in gate_leaf_names if name):
        return True
    return False


def needs_block_repair(stored: dict[str, Any], fresh: dict[str, Any] | None) -> bool:
    stored_expr = str(stored.get("raw_expression") or "")
    if is_corrupt_or_only_expression(stored_expr):
        return True
    if is_broken_gate_tree(stored.get("tree") if isinstance(stored.get("tree"), dict) else None):
        return True
    if not fresh:
        return False
    fresh_expr = str(fresh.get("raw_expression") or "")
    if fresh_expr and _normalize_expr(stored_expr) != _normalize_expr(fresh_expr):
        return True
    return False


def _file_index(bundle: dict[str, Any]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for row in bundle.get("classified_files") or []:
        raw = str(row.get("file") or row.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        index[path.name] = path
        index[path.name.lower()] = path
    for block in bundle.get("logic_blocks") or []:
        src = block.get("source") if isinstance(block.get("source"), dict) else {}
        raw = str(src.get("file") or src.get("document") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.suffix.lower() == ".docx":
            index.setdefault(path.name, path)
            index.setdefault(path.name.lower(), path)
    return index


def _docx_paths(bundle: dict[str, Any]) -> list[Path]:
    index = _file_index(bundle)
    seen: set[str] = set()
    paths: list[Path] = []
    for path in index.values():
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.suffix.lower() == ".docx" and path.exists():
            paths.append(path)
    return paths


def _index_fresh_blocks(blocks: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for block in blocks:
        bid = str(block.get("id") or "")
        bname = str(block.get("name") or "")
        if bid:
            by_id[bid] = block
        if bname:
            by_name[bname] = block
    return by_id, by_name


def repair_word_logic_blocks(bundle: dict[str, Any], cfg: dict[str, Any] | None = None) -> tuple[dict[str, Any], bool]:
    """
    Re-extract Word logic blocks when stored expressions/trees differ from a fresh parse.
    Returns (bundle, repaired_flag).
    """
    cfg = cfg or {}
    blocks = list(bundle.get("logic_blocks") or [])
    if not blocks:
        return bundle, False

    fresh_by_id: dict[str, dict[str, Any]] = {}
    fresh_by_name: dict[str, dict[str, Any]] = {}
    repaired_any = False

    for path in _docx_paths(bundle):
        wd = extract_word_document(path, cfg=cfg)
        fresh_blocks = list(wd.get("logic_blocks") or [])
        if feature_enabled(cfg, "formal_logic_ir_v2", default=True):
            enrich_logic_blocks(fresh_blocks, wd.get("condition_definitions") or [])
        if not fresh_blocks:
            continue
        by_id, by_name = _index_fresh_blocks(fresh_blocks)
        fresh_by_id.update(by_id)
        fresh_by_name.update(by_name)

    if not fresh_by_id and not fresh_by_name:
        return bundle, False

    out_blocks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for block in blocks:
        bid = str(block.get("id") or "")
        bname = str(block.get("name") or "")
        fresh = fresh_by_id.get(bid) or fresh_by_name.get(bname)
        if fresh and needs_block_repair(block, fresh):
            replacement = fresh
            repaired_any = True
        else:
            replacement = block
        rid = str(replacement.get("id") or bid)
        if rid and rid in seen_ids:
            continue
        out_blocks.append(replacement)
        if rid:
            seen_ids.add(rid)

    for block in fresh_by_id.values():
        bid = str(block.get("id") or "")
        if bid and bid not in seen_ids:
            out_blocks.append(block)
            seen_ids.add(bid)
            repaired_any = True

    if not repaired_any:
        return bundle, False

    out = dict(bundle)
    out["logic_blocks"] = out_blocks
    out.pop("logic_review_items", None)
    return out, True
