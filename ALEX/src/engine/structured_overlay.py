"""Structured knowledge overlay per logic group (constraints, definitions)."""

from __future__ import annotations

import uuid
from typing import Any


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def empty_overlay() -> dict[str, Any]:
    return {"constraints": [], "definitions": [], "diagram_links": [], "version": "1"}


def get_overlay(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    ai = bundle.get("ai_assists") if isinstance(bundle.get("ai_assists"), dict) else {}
    root = ai.get("structured_overlay") if isinstance(ai.get("structured_overlay"), dict) else {}
    data = root.get(logic_id)
    if isinstance(data, dict):
        out = empty_overlay()
        out.update(data)
        if not isinstance(out.get("constraints"), list):
            out["constraints"] = []
        if not isinstance(out.get("definitions"), list):
            out["definitions"] = []
        if not isinstance(out.get("diagram_links"), list):
            out["diagram_links"] = []
        return out
    return empty_overlay()


def set_overlay(bundle: dict[str, Any], logic_id: str, overlay: dict[str, Any]) -> dict[str, Any]:
    ai = bundle.setdefault("ai_assists", {})
    root = ai.setdefault("structured_overlay", {})
    clean = empty_overlay()
    clean["constraints"] = list(overlay.get("constraints") or [])
    clean["definitions"] = list(overlay.get("definitions") or [])
    clean["diagram_links"] = list(overlay.get("diagram_links") or [])
    root[logic_id] = clean
    return clean


def add_diagram_link(bundle: dict[str, Any], logic_id: str, link: dict[str, Any]) -> dict[str, Any]:
    """Attach a confirmed diagram edge to a logic group's overlay."""
    overlay = get_overlay(bundle, logic_id)
    links = list(overlay.get("diagram_links") or [])
    entry = {
        "id": str(link.get("id") or _new_id("DL")),
        "from_state": str(link.get("from_state") or "").strip(),
        "to_state": str(link.get("to_state") or "").strip(),
        "event": str(link.get("event") or "").strip(),
        "conditions": list(link.get("conditions") or []),
        "edge_key": str(link.get("edge_key") or "").strip(),
        "review_status": str(link.get("review_status") or "accepted"),
        "source": str(link.get("source") or "diagram_graph"),
        "citations": list(link.get("citations") or []),
        "note": str(link.get("note") or "").strip(),
    }
    links = [row for row in links if row.get("edge_key") != entry["edge_key"]]
    links.append(entry)
    overlay["diagram_links"] = links
    set_overlay(bundle, logic_id, overlay)
    return entry


def accepted_constraints(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        c
        for c in overlay.get("constraints") or []
        if isinstance(c, dict) and str(c.get("review_status") or "") == "accepted"
    ]


def normalize_constraint(raw: dict[str, Any]) -> dict[str, Any]:
    kind = str(raw.get("kind") or "range_inclusive").strip()
    signal = str(raw.get("signal") or "").strip().upper()
    if not signal:
        raise ValueError("Constraint signal is required.")
    out: dict[str, Any] = {
        "id": str(raw.get("id") or _new_id("C")),
        "signal": signal,
        "kind": kind,
        "review_status": str(raw.get("review_status") or "draft"),
        "source": str(raw.get("source") or "engineer_form"),
        "citations": list(raw.get("citations") or []),
        "note": str(raw.get("note") or "").strip(),
    }
    if kind == "range_inclusive":
        out["min"] = _num(raw.get("min"))
        out["max"] = _num(raw.get("max"))
        if out["min"] is None or out["max"] is None:
            raise ValueError("Range constraint requires min and max.")
        if out["min"] > out["max"]:
            out["min"], out["max"] = out["max"], out["min"]
    elif kind == "equality":
        out["value"] = str(raw.get("value") if raw.get("value") is not None else "").strip()
        if not out["value"]:
            raise ValueError("Equality constraint requires value.")
    else:
        raise ValueError(f"Unsupported constraint kind: {kind}")
    unit = str(raw.get("unit") or "").strip()
    if unit:
        out["unit"] = unit
    return out


def _num(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
