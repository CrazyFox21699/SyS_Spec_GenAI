"""Evidence reference model for trace-first ALEX workflow."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

EvidenceKind = Literal[
    "table_cell",
    "table_merged_region",
    "word_paragraph",
    "excel_shape",
    "pdf_region",
    "image_ocr",
    "footnote",
    "external_doc",
    "engineer_note",
    "alias",
]

Provenance = Literal["deterministic", "copilot_suggested", "engineer_confirmed"]
ReviewStatus = Literal["pending", "approved", "rejected"]
Confidence = Literal["high", "medium", "low"]


def new_evidence_id(prefix: str = "EVD") -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def format_locator(source: dict[str, Any] | None) -> str:
    """Build a human-readable locator from a source dict."""
    if not source:
        return ""
    parts: list[str] = []
    file_name = source.get("file") or source.get("document")
    if file_name:
        parts.append(str(file_name))
    sheet = source.get("sheet")
    if sheet:
        parts.append(f"sheet {sheet}")
    section = source.get("section")
    if section:
        parts.append(f"section {section}")
    table = source.get("table") or source.get("table_id")
    if table:
        parts.append(str(table))
    row = source.get("row") or source.get("row_hint")
    if row is not None:
        parts.append(f"row {row}")
    col = source.get("column")
    if col is not None:
        parts.append(f"col {col}")
    paragraph = source.get("paragraph")
    if paragraph is not None:
        parts.append(f"paragraph {paragraph}")
    merge_range = source.get("merge_range")
    if merge_range:
        parts.append(str(merge_range))
    shape_id = source.get("shape_id")
    if shape_id:
        parts.append(f"shape {shape_id}")
    page = source.get("page")
    if page is not None:
        parts.append(f"page {page}")
    return " / ".join(parts)


def make_evidence_ref(
    *,
    kind: EvidenceKind,
    file: str,
    locator: str = "",
    source: dict[str, Any] | None = None,
    excerpt: str = "",
    derives_from: list[str] | None = None,
    confidence: Confidence = "medium",
    review_required: bool = True,
    review_status: ReviewStatus = "pending",
    provenance: Provenance = "deterministic",
    evidence_id: str | None = None,
    linked_logic_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a normalized evidence reference dict for ui_bundle storage."""
    src = dict(source or {})
    if file and "file" not in src:
        src["file"] = file
    if locator and "locator" not in src:
        src["locator"] = locator
    loc = locator or format_locator(src)
    return {
        "id": evidence_id or new_evidence_id(),
        "kind": kind,
        "source": src,
        "locator": loc,
        "excerpt": (excerpt or "")[:500],
        "derives_from": list(derives_from or []),
        "confidence": confidence,
        "review_required": review_required,
        "review_status": review_status,
        "provenance": provenance,
        "linked_logic_ids": list(linked_logic_ids or []),
    }
