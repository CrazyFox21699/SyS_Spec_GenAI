"""Local OCR helpers for images, embedded document media, and scanned diagrams."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.parsers.diagram_parser import extract_diagram_transitions
from src.parsers.paragraph_extractor import extract_from_paragraphs

try:
    from PIL import Image, ImageOps
except Exception:  # noqa: BLE001
    Image = None
    ImageOps = None

_TESSERACT = shutil.which("tesseract")
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


def local_ocr_available() -> bool:
    return bool(_TESSERACT)


def _paragraphs(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _confidence_from_text(text: str) -> str:
    clean = " ".join(_paragraphs(text))
    if len(clean) >= 240:
        return "medium"
    if len(clean) >= 60:
        return "low"
    return "low"


def _preprocess_image(path: Path) -> Path:
    if Image is None or ImageOps is None:
        return path
    with Image.open(path) as image:
        img = image.convert("L")
        img = ImageOps.autocontrast(img)
        width, height = img.size
        scale = 1
        if max(width, height) < 1600:
            scale = 2
        if scale > 1:
            img = img.resize((width * scale, height * scale))
        tmp = Path(tempfile.mkstemp(suffix=".png")[1])
        img.save(tmp)
        return tmp


def _run_tesseract(path: Path, *, lang: str = "eng", psm: int = 6) -> str:
    if not _TESSERACT:
        return ""
    cmd = [_TESSERACT, str(path), "stdout", "-l", lang, "--psm", str(psm)]
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    if cp.returncode != 0:
        return ""
    return (cp.stdout or "").strip()


def _analysis_from_text(text: str, *, source_file: str, source_kind: str) -> dict[str, Any]:
    paragraphs = _paragraphs(text)
    para_data = extract_from_paragraphs(paragraphs, source_file)
    transitions = extract_diagram_transitions(paragraphs, source_file)
    for row in para_data.get("condition_definitions", []):
        row.setdefault("source", {})
        row["source"]["kind"] = source_kind
    for row in para_data.get("state_rules", []):
        row.setdefault("source", {})
        row["source"]["kind"] = source_kind
    for row in para_data.get("code_definitions", []):
        row.setdefault("source", {})
        row["source"]["kind"] = source_kind
    for row in transitions:
        row.setdefault("source", {})
        row["source"]["kind"] = source_kind
    return {
        "ocr_text": "\n".join(paragraphs),
        "ocr_confidence": _confidence_from_text(text),
        "condition_definitions": para_data.get("condition_definitions", []),
        "code_definitions": para_data.get("code_definitions", []),
        "state_rules": para_data.get("state_rules", []),
        "transitions": transitions,
    }


def analyze_ocr_text(text: str, *, source_file: str, source_kind: str = "ocr_text") -> dict[str, Any]:
    return _analysis_from_text(text, source_file=source_file, source_kind=source_kind)


def analyze_image_with_ocr(path: Path, *, source_file: str | None = None, source_kind: str = "diagram_image_ocr") -> dict[str, Any]:
    source_file = source_file or path.name
    stat = path.stat()
    meta: dict[str, Any] = {
        "file": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "ocr_available": local_ocr_available(),
        "review_required": True,
    }
    if not local_ocr_available():
        meta["note"] = "Local OCR is not available; install tesseract to read this image."
        meta["confidence"] = "low"
        return meta

    temp_path = None
    try:
        temp_path = _preprocess_image(path)
        text = _run_tesseract(temp_path)
    finally:
        if temp_path and temp_path != path:
            temp_path.unlink(missing_ok=True)

    analysis = _analysis_from_text(text, source_file=source_file, source_kind=source_kind)
    meta.update(analysis)
    meta["confidence"] = analysis["ocr_confidence"]
    meta["note"] = (
        "OCR text extracted locally from image; review transitions and definitions before final approval."
        if text
        else "Image OCR did not produce usable text."
    )
    return meta


def analyze_docx_embedded_images(path: Path, *, max_images: int = 10) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path) as zf:
            image_names = [name for name in zf.namelist() if name.startswith("word/media/")]
            for image_name in image_names[:max_images]:
                suffix = Path(image_name).suffix.lower() or ".bin"
                if suffix not in _IMAGE_EXTS:
                    continue
                data = zf.read(image_name)
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(data)
                    tmp_path = Path(tmp.name)
                try:
                    analysis = analyze_image_with_ocr(
                        tmp_path,
                        source_file=path.name,
                        source_kind="docx_embedded_image_ocr",
                    )
                    analysis["embedded_name"] = Path(image_name).name
                    analysis["parent_document"] = path.name
                    analyses.append(analysis)
                finally:
                    tmp_path.unlink(missing_ok=True)
    except Exception:
        return []
    return analyses


def analyze_pdf_images(path: Path, *, max_pages: int = 8, max_images_per_page: int = 3) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return analyses

    for page_index, page in enumerate(reader.pages[:max_pages], start=1):
        try:
            images = list(page.images)
        except Exception:
            images = []
        for image_index, image in enumerate(images[:max_images_per_page], start=1):
            suffix = Path(getattr(image, "name", "")).suffix.lower() or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(image.data)
                tmp_path = Path(tmp.name)
            try:
                analysis = analyze_image_with_ocr(
                    tmp_path,
                    source_file=path.name,
                    source_kind="pdf_embedded_image_ocr",
                )
                analysis["page"] = page_index
                analysis["embedded_name"] = getattr(image, "name", f"page_{page_index}_image_{image_index}")
                analysis["parent_document"] = path.name
                analyses.append(analysis)
            finally:
                tmp_path.unlink(missing_ok=True)
    return analyses
