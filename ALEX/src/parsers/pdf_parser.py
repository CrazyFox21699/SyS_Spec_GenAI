"""PDF text extraction with embedded-image OCR fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.parsers.ocr_local import analyze_pdf_images


def peek_pdf_text(path: Path, max_chars: int = 8000) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages[:30]:
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    return "\n".join(parts)[:max_chars]


def extract_pdf_text_blocks(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages[:50]):
        pages.append({"index": i + 1, "text": (page.extract_text() or "")[:4000]})
    return {"file": str(path), "pages": pages}


def extract_pdf_document(path: Path) -> dict[str, Any]:
    pages_blob = extract_pdf_text_blocks(path)
    image_analyses = analyze_pdf_images(path)
    condition_definitions: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    state_rules: list[dict[str, Any]] = []
    code_definitions: list[dict[str, Any]] = []
    for row in image_analyses:
        condition_definitions.extend(row.get("condition_definitions", []))
        transitions.extend(row.get("transitions", []))
        state_rules.extend(row.get("state_rules", []))
        code_definitions.extend(row.get("code_definitions", []))
    return {
        **pages_blob,
        "image_analyses": image_analyses,
        "condition_definitions": condition_definitions,
        "transitions": transitions,
        "state_rules": state_rules,
        "code_definitions": code_definitions,
    }
