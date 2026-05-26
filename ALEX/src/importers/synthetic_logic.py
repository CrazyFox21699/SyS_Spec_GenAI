"""Synthetic logic groups for import/bootstrap workflows."""

from __future__ import annotations

import re
from typing import Any


def slug(text: str, *, max_len: int = 48) -> str:
    slugged = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip()).strip("_")
    return (slugged or "imported")[:max_len]


def synthetic_logic_block(
    logic_id: str,
    name: str,
    *,
    source: dict[str, Any] | None = None,
    parse_status: str = "imported",
) -> dict[str, Any]:
    return {
        "id": logic_id,
        "name": name,
        "raw_expression": name,
        "expression": name,
        "tree": {
            "type": "leaf",
            "signal": name,
            "value": "",
            "parse_status": parse_status,
        },
        "source": source or {"kind": "import_bootstrap"},
        "parse_status": parse_status,
        "decision_mode": "imported",
        "gate_status": "imported",
        "issues": [],
        "unresolved_refs": [],
        "can_generate_candidates": True,
    }
