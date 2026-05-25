"""Parse signal definition tables (Word/Excel)."""

from __future__ import annotations

import re
from typing import Any

_VALUE_BULLET_RE = re.compile(r"^[•\-\*]?\s*(?P<val>[^:\s]+)\s*:\s*(?P<meaning>.+)$", re.M)


def _col_index(header: list[str], *keys: str) -> int | None:
    for i, h in enumerate(header):
        low = str(h or "").lower()
        if any(k in low for k in keys):
            return i
    return None


def parse_signal_value_map(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _VALUE_BULLET_RE.match(line) or re.match(r"^(?P<val>\d+)\s*:\s*(?P<meaning>.+)$", line)
        if m:
            rows.append({"value": m.group("val").strip(), "meaning": m.group("meaning").strip()})
    return rows


def parse_signal_row(cells: list[str], header: list[str], *, source: dict[str, Any], row_no: int) -> dict[str, Any] | None:
    if not cells or not any(cells):
        return None
    i_name = _col_index(header, "signal", "name", "sig")
    if i_name is None:
        i_name = 0
    name = cells[i_name].strip() if i_name < len(cells) else ""
    if not name or len(name) > 80:
        return None

    i_desc = _col_index(header, "description", "desc")
    i_sender = _col_index(header, "sender")
    i_values = _col_index(header, "possible", "value", "meaning")
    i_initial = _col_index(header, "initial")
    i_failsafe = _col_index(header, "fail")

    desc = cells[i_desc].strip() if i_desc is not None and i_desc < len(cells) else ""
    sender = cells[i_sender].strip() if i_sender is not None and i_sender < len(cells) else ""
    values_text = cells[i_values].strip() if i_values is not None and i_values < len(cells) else ""
    initial = cells[i_initial].strip() if i_initial is not None and i_initial < len(cells) else ""
    fail_safe = cells[i_failsafe].strip() if i_failsafe is not None and i_failsafe < len(cells) else ""

    value_map = parse_signal_value_map(values_text)
    fail_domain = "sentinel" if fail_safe.lower() == "last" else "literal"

    return {
        "name": name,
        "description": desc,
        "sender": sender,
        "direction": "unknown",
        "values": value_map,
        "initial_value": initial,
        "fail_safe_value": fail_safe,
        "fail_safe_domain": fail_domain,
        "definition": values_text or desc,
        "source": {**source, "row": str(row_no)},
        "confidence": "high" if value_map else "medium",
        "review_required": not bool(value_map),
    }


def parse_signal_grid(grid: list[list[str]], source: dict[str, Any]) -> list[dict[str, Any]]:
    if len(grid) < 2:
        return []
    header = [str(c or "").lower() for c in grid[0]]
    if not any(k in " ".join(header) for k in ("signal", "sender", "fail", "initial")):
        return []
    signals: list[dict[str, Any]] = []
    for ri, cells in enumerate(grid[1:101], start=2):
        row = parse_signal_row(cells, header, source=source, row_no=ri)
        if row:
            signals.append(row)
    return signals


def signal_names_for_definitions(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert signal registry rows into condition_definitions-like rows."""
    out: list[dict[str, Any]] = []
    for sig in signals:
        name = str(sig.get("name") or "").strip()
        if not name:
            continue
        parts = []
        if sig.get("description"):
            parts.append(str(sig["description"]))
        for vm in sig.get("values") or []:
            parts.append(f"{vm.get('value')}: {vm.get('meaning')}")
        if sig.get("initial_value"):
            parts.append(f"Initial={sig['initial_value']}")
        if sig.get("fail_safe_value"):
            parts.append(f"FailSafe={sig['fail_safe_value']}")
        out.append(
            {
                "name": name,
                "definition": "; ".join(parts) or name,
                "source": sig.get("source") or {},
                "kind": "signal_registry",
                "signal_meta": sig,
            }
        )
    return out
