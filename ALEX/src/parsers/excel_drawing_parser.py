"""Parse Excel drawing XML for state/transition semantics."""

from __future__ import annotations

import math
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from src.parsers.paragraph_extractor import extract_from_paragraphs

_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _target(base: str, rel_target: str) -> str:
    rel_target = str(rel_target or "").lstrip("/")
    if rel_target.startswith("xl/"):
        return posixpath.normpath(rel_target)
    parts = Path(base).parent / rel_target
    return posixpath.normpath(str(parts.as_posix()).replace("//", "/"))


def _read_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        data = zf.read(name)
    except KeyError:
        return None
    return ET.fromstring(data)


def _sheet_map(zf: zipfile.ZipFile) -> dict[str, str]:
    workbook = _read_xml(zf, "xl/workbook.xml")
    rels = _read_xml(zf, "xl/_rels/workbook.xml.rels")
    if workbook is None or rels is None:
        return {}
    rid_to_target = {
        rel.get("Id"): _target("xl/workbook.xml", rel.get("Target", ""))
        for rel in rels.findall("pr:Relationship", _NS)
        if rel.get("Id") and rel.get("Target")
    }
    out: dict[str, str] = {}
    for sheet in workbook.findall("main:sheets/main:sheet", _NS):
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        name = sheet.get("name") or ""
        target = rid_to_target.get(rid or "")
        if name and target:
            out[target] = name
    return out


def _anchor_box(anchor: ET.Element) -> dict[str, int]:
    from_node = anchor.find("xdr:from", _NS)
    to_node = anchor.find("xdr:to", _NS)
    if from_node is not None and to_node is not None:
        col_from = int(from_node.findtext("xdr:col", default="0", namespaces=_NS))
        row_from = int(from_node.findtext("xdr:row", default="0", namespaces=_NS))
        col_to = int(to_node.findtext("xdr:col", default=str(col_from + 1), namespaces=_NS))
        row_to = int(to_node.findtext("xdr:row", default=str(row_from + 1), namespaces=_NS))
        return {
            "col_start": col_from + 1,
            "row_start": row_from + 1,
            "col_end": col_to + 1,
            "row_end": row_to + 1,
        }
    one = anchor.find("xdr:from", _NS)
    ext = anchor.find("xdr:ext", _NS)
    if one is not None:
        col_from = int(one.findtext("xdr:col", default="0", namespaces=_NS))
        row_from = int(one.findtext("xdr:row", default="0", namespaces=_NS))
        return {
            "col_start": col_from + 1,
            "row_start": row_from + 1,
            "col_end": col_from + 2,
            "row_end": row_from + 2,
        }
    return {"col_start": 1, "row_start": 1, "col_end": 1, "row_end": 1}


def _box_area(box: dict[str, int]) -> int:
    return max(1, box["col_end"] - box["col_start"] + 1) * max(1, box["row_end"] - box["row_start"] + 1)


def _center(box: dict[str, int]) -> tuple[float, float]:
    return ((box["col_start"] + box["col_end"]) / 2.0, (box["row_start"] + box["row_end"]) / 2.0)


def _contains(outer: dict[str, int], inner: dict[str, int]) -> bool:
    return (
        outer["col_start"] <= inner["col_start"] <= inner["col_end"] <= outer["col_end"]
        and outer["row_start"] <= inner["row_start"] <= inner["row_end"] <= outer["row_end"]
    )


def _distance(a: dict[str, int], b: dict[str, int]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _shape_text(shape: ET.Element) -> str:
    texts = [node.text or "" for node in shape.findall(".//a:t", _NS)]
    lines = [text.strip() for text in texts if (text or "").strip()]
    return "\n".join(lines).strip()


def _shape_geom(shape: ET.Element) -> str:
    geom = shape.find(".//a:prstGeom", _NS)
    return geom.get("prst", "") if geom is not None else ""


def _shape_name(shape: ET.Element) -> str:
    node = shape.find(".//xdr:cNvPr", _NS)
    return node.get("name", "") if node is not None else ""


def _parse_state_outputs(text: str, *, source: dict[str, Any]) -> list[dict[str, Any]]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    parsed = extract_from_paragraphs(paragraphs, source.get("file", "excel_drawing"))
    rows = parsed.get("state_rules", []) + parsed.get("code_definitions", []) + parsed.get("condition_definitions", [])
    explicit_assignments = []
    for line in paragraphs:
        m = re.match(r"^([A-Z][A-Z0-9_ ]+)\s*=\s*(.+)$", line, re.I)
        if not m:
            continue
        explicit_assignments.append(
            {
                "name": m.group(1).strip().upper().replace(" ", "_"),
                "expression": m.group(2).strip(),
                "source": {**source, "kind": "excel_drawing_shape"},
            }
        )
    rows.extend(explicit_assignments)
    for row in rows:
        row.setdefault("source", {})
        row["source"].update(source)
        row["source"]["kind"] = "excel_drawing_shape"
    return rows


def extract_excel_drawing_semantics(path: Path) -> dict[str, Any]:
    sheet_targets = {}
    shapes: list[dict[str, Any]] = []
    connectors: list[dict[str, Any]] = []
    diagrams: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    state_rules: list[dict[str, Any]] = []
    drawing_count = 0

    try:
        with zipfile.ZipFile(path) as zf:
            sheet_targets = _sheet_map(zf)
            for sheet_target, sheet_name in sheet_targets.items():
                rel_path = str(Path(sheet_target).parent / "_rels" / (Path(sheet_target).name + ".rels")).replace("\\", "/")
                rels = _read_xml(zf, rel_path)
                if rels is None:
                    continue
                drawing_targets = []
                for rel in rels.findall("pr:Relationship", _NS):
                    rel_type = rel.get("Type", "")
                    if rel_type.endswith("/drawing") and rel.get("Target"):
                        drawing_targets.append(_target(sheet_target, rel.get("Target", "")))
                for drawing_target in drawing_targets:
                    root = _read_xml(zf, drawing_target)
                    if root is None:
                        continue
                    drawing_count += 1
                    for idx, anchor in enumerate(root.findall("xdr:twoCellAnchor", _NS) + root.findall("xdr:oneCellAnchor", _NS), start=1):
                        box = _anchor_box(anchor)
                        sp = anchor.find("xdr:sp", _NS)
                        cxn = anchor.find("xdr:cxnSp", _NS)
                        if sp is not None:
                            text = _shape_text(sp)
                            row = {
                                "file": str(path),
                                "name": _shape_name(sp) or f"shape_{idx}",
                                "sheet": sheet_name,
                                "source_kind": "excel_drawing_shape",
                                "geom": _shape_geom(sp),
                                "text": text,
                                "box": box,
                            }
                            shapes.append(row)
                        elif cxn is not None:
                            connectors.append(
                                {
                                    "file": str(path),
                                    "name": _shape_name(cxn) or f"connector_{idx}",
                                    "sheet": sheet_name,
                                    "source_kind": "excel_drawing_connector",
                                    "geom": _shape_geom(cxn),
                                    "box": box,
                                }
                            )
    except zipfile.BadZipFile:
        return {
            "drawing_shapes": [],
            "drawing_connectors": [],
            "diagram_meta": [],
            "transition_candidates": [],
            "state_rules": [],
        }

    by_sheet: dict[str, list[dict[str, Any]]] = {}
    for shape in shapes:
        by_sheet.setdefault(shape["sheet"], []).append(shape)

    state_containers: list[dict[str, Any]] = []
    output_boxes: list[dict[str, Any]] = []
    label_boxes: list[dict[str, Any]] = []

    for shape in shapes:
        text = str(shape.get("text") or "").strip()
        area = _box_area(shape["box"])
        is_output = "=" in text and "\n" in text
        short_lines = [line.strip() for line in text.splitlines() if line.strip()]
        looks_state = bool(short_lines) and len(short_lines) <= 2 and all("=" not in line for line in short_lines) and area >= 12
        if looks_state:
            state_name = short_lines[0].upper().replace(" ", "_")
            state_containers.append({**shape, "state_name": state_name})
        elif is_output:
            output_boxes.append(shape)
        elif text:
            label_boxes.append(shape)

    for state in state_containers:
        contained_outputs = [row for row in output_boxes if row["sheet"] == state["sheet"] and _contains(state["box"], row["box"])]
        state_text = [state["state_name"], *[row["text"] for row in contained_outputs if row.get("text")]]
        diagrams.append(
            {
                "file": str(path),
                "parent_document": path.name,
                "name": state["name"],
                "sheet": state["sheet"],
                "source_kind": "excel_drawing_text",
                "ocr_text": "\n".join(part for part in state_text if part).strip(),
                "box": state["box"],
                "state_name": state["state_name"],
                "output_boxes": [row["text"] for row in contained_outputs if row.get("text")],
                "shape_count": 1 + len(contained_outputs),
            }
        )
        for output in contained_outputs:
            state_rules.extend(
                _parse_state_outputs(
                    output.get("text", ""),
                    source={
                        "file": path.name,
                        "sheet": state["sheet"],
                        "shape": output.get("name"),
                        "state": state["state_name"],
                    },
                )
            )

    connector_id = 0
    for connector in connectors:
        same_sheet_states = [state for state in state_containers if state["sheet"] == connector["sheet"]]
        if len(same_sheet_states) < 2:
            continue
        cx, cy = _center(connector["box"])
        left_candidates = [state for state in same_sheet_states if _center(state["box"])[0] <= cx]
        right_candidates = [state for state in same_sheet_states if _center(state["box"])[0] >= cx]
        if left_candidates and right_candidates:
            from_state = min(left_candidates, key=lambda row: _distance(row["box"], connector["box"]))
            to_state = min(right_candidates, key=lambda row: _distance(row["box"], connector["box"]))
        else:
            ordered = sorted(same_sheet_states, key=lambda row: _distance(row["box"], connector["box"]))
            if len(ordered) < 2:
                continue
            from_state, to_state = ordered[:2]
        nearby_labels = [
            label for label in label_boxes
            if label["sheet"] == connector["sheet"] and _distance(label["box"], connector["box"]) <= 8
        ]
        event = nearby_labels[0]["text"].splitlines()[0].strip() if nearby_labels else "excel_drawing_transition"
        raw_condition = event if nearby_labels else connector.get("name", "Excel drawing connector")
        connector_id += 1
        transitions.append(
            {
                "id": f"SM_XL_{connector_id:03d}",
                "from_state": from_state["state_name"],
                "to_state": to_state["state_name"],
                "event": event,
                "raw_condition": raw_condition,
                "source": {
                    "file": path.name,
                    "sheet": connector["sheet"],
                    "kind": "excel_drawing_connector",
                    "shape": connector.get("name"),
                },
                "confidence": "medium" if nearby_labels else "low",
                "review_required": True,
                "derivation": "excel_drawing_connector",
            }
        )

    summary_text = []
    for state in state_containers:
        summary_text.append(state["state_name"])
    for label in label_boxes:
        if label.get("text"):
            summary_text.append(label["text"])
    if summary_text:
        diagrams.append(
            {
                "file": str(path),
                "parent_document": path.name,
                "name": "excel_drawing_summary",
                "sheet": next(iter(by_sheet.keys()), ""),
                "source_kind": "excel_drawing_text",
                "ocr_text": "\n".join(summary_text),
                "shape_count": len(shapes),
                "connector_count": len(connectors),
                "drawing_count": drawing_count,
            }
        )

    return {
        "drawing_shapes": shapes,
        "drawing_connectors": connectors,
        "diagram_meta": diagrams,
        "transition_candidates": transitions,
        "state_rules": state_rules,
    }
