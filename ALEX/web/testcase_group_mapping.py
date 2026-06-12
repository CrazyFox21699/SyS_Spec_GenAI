"""Testcase group mapping: auto-build group_id and suggested namespace from workbench rows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_MAPPING_FILENAME = "testcase_group_mapping.json"

_NAMESPACE_STOP_WORDS = frozenset({
    "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "the", "a", "an",
    "in", "on", "to", "of", "for", "by", "at", "it", "its",
    "will", "would", "could", "should", "have", "has", "had",
    "make", "makes", "made", "this", "that", "which", "with",
    "from", "about", "when", "where", "how", "what", "happened",
})


def normalize_group_key(test_function: str, test_group: str) -> str:
    """Normalized lookup key for (test_function, test_group) pair."""
    combined = str(test_function or "").strip() + " / " + str(test_group or "").strip()
    s = combined.lower()
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def suggest_namespace(test_group: str, event: str = "", operation: str = "") -> str:
    """Suggest TryToPascalCase namespace. Event is primary; Test Group is fallback if Event is empty.

    Filters stop words and limits to 3 content tokens so output stays short.
    Examples:
        event="Power is ON and the accident happened make it to reset" → TryToPowerOnReset
        test_group="Power will be reset to off"                       → TryToPowerResetOff
        test_group="timing_boundary"                                  → TryToTimingBoundary
        test_group="Evaluate NOK"                                     → TryToEvaluateNok
    """
    # Event is primary; Test Group is fallback
    primary = str(event or "").strip() or str(test_group or "").strip()
    tokens: list[str] = []
    for t in re.split(r"[\s_\-/]+", primary):
        t_clean = re.sub(r"[^A-Za-z0-9]", "", t)
        if not t_clean or re.fullmatch(r"\d+", t_clean):
            continue
        if t_clean.lower() in _NAMESPACE_STOP_WORDS:
            continue
        tokens.append(t_clean)
        if len(tokens) >= 3:
            break
    if not tokens:
        # Last resort: take first 3 tokens without stop-word filter
        for t in re.split(r"[\s_\-/]+", primary):
            t_clean = re.sub(r"[^A-Za-z0-9]", "", t)
            if t_clean and not re.fullmatch(r"\d+", t_clean):
                tokens.append(t_clean)
                if len(tokens) >= 3:
                    break

    # PascalCase each token
    pascal = [t[0].upper() + t[1:].lower() if len(t) > 1 else t.upper() for t in tokens]
    base = "".join(pascal)

    # Optional "by X" suffix from operation
    by_m = re.search(r"\bby\s+([A-Za-z][A-Za-z0-9]*)", str(operation or ""), re.IGNORECASE)
    suffix = ""
    if by_m:
        w = by_m.group(1)
        suffix = "By" + w[0].upper() + (w[1:].lower() if len(w) > 1 else "")

    name = "TryTo" + base + suffix
    return name if len(name) > 5 else "TryToUnknown"


def build_group_mapping(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build group mapping from workbench rows.

    Each unique (test_function, event) pair becomes a group.
    Groups are assigned group_id G001, G002, ... in first-appearance order.

    Returns dict with:
        groups: {group_id: group_dict}
        key_to_group_id: {normalized_key: group_id}
        total_groups: int
        diagnostics: {...}
        sample_group_mapping: first-3-group subset
    """
    groups: dict[str, dict[str, Any]] = {}
    key_to_group_id: dict[str, str] = {}
    counter = 0

    rows_with_test_function = 0
    rows_with_test_group = 0
    rows_with_event = 0
    rows_with_operation = 0
    rows_with_expected_input = 0
    rows_with_expected_output = 0

    for row in rows or []:
        tf = str(row.get("test_function") or "").strip()
        tg = str(row.get("test_group") or "").strip()
        event = str(row.get("event") or "").strip()
        operation = str(row.get("operation") or "").strip()
        cid = str(row.get("candidate_id") or "").strip()

        if tf:
            rows_with_test_function += 1
        if tg:
            rows_with_test_group += 1
        if event:
            rows_with_event += 1
        if operation:
            rows_with_operation += 1
        if str(row.get("expected_input") or "").strip():
            rows_with_expected_input += 1
        if str(row.get("expected_output") or "").strip():
            rows_with_expected_output += 1

        key = normalize_group_key(tf, tg)

        if key not in key_to_group_id:
            counter += 1
            group_id = f"G{counter:03d}"
            key_to_group_id[key] = group_id
            ns = suggest_namespace(tg, event, operation)
            raw_name = (tf + " / " + tg).strip(" /")
            groups[group_id] = {
                "group_id": group_id,
                "group_name": raw_name,
                "test_function": tf,
                "test_group": tg,
                "event": event,
                "normalized_key": key,
                "tc_count": 0,
                "candidate_ids": [],
                "suggested_namespace": ns,
                "suggested_fixture_class": ns,
                "default_main_function": "igsw_Main_Run()",
            }

        gid = key_to_group_id[key]
        groups[gid]["tc_count"] += 1
        if cid:
            groups[gid]["candidate_ids"].append(cid)

    sample_keys = list(groups.keys())[:3]
    sample = {k: groups[k] for k in sample_keys}

    return {
        "groups": groups,
        "key_to_group_id": key_to_group_id,
        "total_groups": len(groups),
        "diagnostics": {
            "total_rows": len(rows or []),
            "rows_with_test_function": rows_with_test_function,
            "rows_with_test_group": rows_with_test_group,
            "rows_with_event": rows_with_event,
            "rows_with_operation": rows_with_operation,
            "rows_with_expected_input": rows_with_expected_input,
            "rows_with_expected_output": rows_with_expected_output,
        },
        "sample_group_mapping": sample,
    }


def enrich_rows_with_group_id(
    rows: list[dict[str, Any]], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return a copy of each row with group_id added from the mapping."""
    key_to_gid = mapping.get("key_to_group_id") or {}
    enriched = []
    for row in rows or []:
        tf = str(row.get("test_function") or "").strip()
        tg = str(row.get("test_group") or "").strip()
        key = normalize_group_key(tf, tg)
        gid = key_to_gid.get(key, "")
        enriched.append({**row, "group_id": gid})
    return enriched


def _mapping_path(job_output: Path) -> Path:
    from web.project_code_config import project_code_config_dir
    d = project_code_config_dir(job_output)
    d.mkdir(parents=True, exist_ok=True)
    return d / _MAPPING_FILENAME


def save_group_mapping(job_output: Path, mapping: dict[str, Any]) -> None:
    """Persist group mapping as JSON. Conflict-safe: no bundle-version check."""
    try:
        path = _mapping_path(job_output)
        path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_group_mapping(job_output: Path) -> dict[str, Any]:
    """Load persisted group mapping, or return empty dict if not found."""
    try:
        path = _mapping_path(job_output)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}
