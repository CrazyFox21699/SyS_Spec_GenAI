"""Image / diagram registration with optional local OCR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.parsers.ocr_local import analyze_image_with_ocr


def extract_image_metadata(path: Path) -> dict[str, Any]:
    return analyze_image_with_ocr(path, source_file=path.name, source_kind="diagram_image_ocr")
