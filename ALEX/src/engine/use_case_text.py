"""Short, readable use-case lines for workbook (no truncated raw logic pasted)."""

from __future__ import annotations

import re
from typing import Any

_OLD_TRUNCATED_RE = re.compile(
    r"^Verify\s+(?P<ctrl>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\s*\(\s*(?P<label>[^;]+)\s*;\s*",
    re.I,
)


def compact_use_case_description(candidate: dict[str, Any]) -> str:
    """Replace legacy 'Verify CTRL=1 (branch; RAW_EXPR…' blobs with a short label."""
    desc = str(candidate.get("use_case_description") or "").strip()
    if not desc:
        return desc

    trace = candidate.get("traceability") or {}
    ctrl = str(trace.get("control_name") or "").strip()
    branch = str(trace.get("logic_branch") or trace.get("logic_path") or "").strip()

    m = _OLD_TRUNCATED_RE.match(desc)
    if m:
        ctrl = m.group("ctrl") or ctrl
        branch = m.group("label") or branch

    needs_fix = (
        "; (" in desc
        or "(*" in desc
        or (len(desc) > 72 and "(" in desc and "=" in desc)
    )
    if not needs_fix:
        return desc

    if not ctrl:
        m2 = re.match(r"^Verify\s+([A-Za-z_][A-Za-z0-9_]*)", desc, re.I)
        if m2:
            ctrl = m2.group(1)

    if not branch:
        event = str(candidate.get("event") or "")
        if event.startswith("evaluate_"):
            branch = event.replace("evaluate_", "", 1)
            if ctrl and branch.startswith(ctrl + "_"):
                branch = branch[len(ctrl) + 1 :]

    label = str(branch).replace("_", " ").strip() or "default path"
    if ctrl:
        return f"Verify {ctrl}=1 — path {label}"
    return desc.split("(")[0].strip() or desc[:72]


def sanitize_candidates_use_cases(bundle: dict[str, Any]) -> dict[str, Any]:
    cands = bundle.get("test_candidates")
    if not isinstance(cands, list):
        return bundle
    changed = False
    out: list[dict[str, Any]] = []
    for cand in cands:
        if not isinstance(cand, dict):
            out.append(cand)
            continue
        row = dict(cand)
        new_desc = compact_use_case_description(row)
        if new_desc != row.get("use_case_description"):
            row["use_case_description"] = new_desc
            changed = True
        out.append(row)
    if not changed:
        return bundle
    bundle = dict(bundle)
    bundle["test_candidates"] = out
    return bundle
