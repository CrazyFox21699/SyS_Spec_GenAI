"""Classify uploads into four engineer-facing types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.parsers.code_parser import scan_code_hints
from src.utils.file_filters import is_ingestible_file
from src.parsers.excel_parser import peek_excel_text
from src.parsers.pdf_parser import peek_pdf_text
from src.parsers.word_parser import peek_word_text

# Display labels (UI)
FILE_TYPE_LABELS = {
    "system_spec": "System Spec",
    "test_spec": "Test Spec",
    "sample_code": "Sample Code",
    "test_code": "Test Code",
}

# Internal pipeline role (ingest routing)
PIPELINE_ROLE_BY_FILE_TYPE = {
    "system_spec": "system_spec",
    "test_spec": "test_spec_reference",
    "sample_code": "code_reference",
    "test_code": "code_reference",
}


@dataclass
class ClassificationResult:
    file: str
    file_type: str  # system_spec | test_spec | sample_code | test_code
    role: str  # pipeline ingest role
    reason: list[str] = field(default_factory=list)
    user_confirmation_suggested: bool = False

    @property
    def file_type_label(self) -> str:
        return FILE_TYPE_LABELS.get(self.file_type, "System Spec")

    # Legacy fields for YAML / older bundle readers
    @property
    def confidence(self) -> str:
        return "n/a"


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            out.append(re.compile(p, re.IGNORECASE))
        except re.error:
            continue
    return out


def classify_file(path: Path, cfg: dict[str, Any]) -> ClassificationResult:
    reasons: list[str] = []
    ext = path.suffix.lower()
    c = cfg.get("classification", {})

    state_pats = _compile_patterns(c.get("state_name_patterns", []))
    beh_kw = [k.lower() for k in c.get("behavior_keywords", [])]
    sig_kw = [k.lower() for k in c.get("signal_keywords", [])]
    tst_kw = [k.lower() for k in c.get("test_spec_keywords", [])]

    sample = ""
    sheet_names: list[str] = []

    if ext in {".xlsx", ".xlsm", ".xls"}:
        sample, sheet_names = peek_excel_text(path, max_chars=12000)
    elif ext == ".docx":
        sample = peek_word_text(path, max_chars=12000)
    elif ext == ".pdf":
        sample = peek_pdf_text(path, max_chars=12000)
    elif ext in {".cpp", ".cc", ".cxx", ".h", ".hpp", ".c"}:
        sample = path.read_text(encoding="utf-8", errors="replace")[:16000]

    sample_l = sample.lower()
    code_hints = scan_code_hints(path) if ext in {".cpp", ".cc", ".cxx", ".h", ".hpp", ".c"} else {}

    scores: dict[str, int] = {
        "system_spec": 0,
        "test_spec": 0,
        "sample_code": 0,
        "test_code": 0,
    }

    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
        scores["system_spec"] += 8
        reasons.append("Diagram or image (supporting system specification)")

    if ext in {".cpp", ".cc", ".cxx", ".h", ".hpp", ".c"}:
        if code_hints.get("has_gtest"):
            scores["test_code"] += 10
            reasons.append("C/C++ source with test framework macros")
        else:
            scores["sample_code"] += 8
            reasons.append("C/C++ reference / sample implementation")

    if ext in {".xlsx", ".xlsm", ".xls"}:
        joined_sheets = " ".join(sheet_names).lower()
        if re.search(r"\bgiven\b", sample_l) and re.search(r"\bexpected\b", sample_l):
            scores["test_spec"] += 10
            reasons.append("Spreadsheet with test-case columns (Given / Expected)")
        for kw in tst_kw:
            if kw in sample_l or kw in joined_sheets:
                scores["test_spec"] += 2
        if re.search(r"\blogic\b", sample_l) and re.search(r"\bcondition\b", sample_l):
            scores["system_spec"] += 6
            reasons.append("Control / condition logic table")
        for kw in beh_kw:
            if kw in sample_l or kw in joined_sheets:
                scores["system_spec"] += 2
        if not reasons:
            scores["system_spec"] += 3
            reasons.append("Excel workbook (default: system specification data)")

    if ext == ".docx":
        scores["system_spec"] += 5
        if re.search(r"\blogic\b", sample_l) and re.search(r"\bcondition\b", sample_l):
            scores["system_spec"] += 4
            reasons.append("Word control / condition tables")
        if re.search(r"\bgiven\b", sample_l) and re.search(r"\bexpected\b", sample_l):
            scores["test_spec"] += 5
            reasons.append("Word document contains test reference tables")
        for kw in sig_kw:
            if kw in sample_l:
                scores["system_spec"] += 2

    if ext == ".pdf":
        scores["system_spec"] += 4
        reasons.append("PDF specification or diagram document")

    if ext in {".md", ".txt"}:
        scores["system_spec"] += 3
        reasons.append("Text specification notes")

    for pat in state_pats:
        if pat.search(sample) or any(pat.search(s) for s in sheet_names):
            scores["system_spec"] += 3
            reasons.append("State-machine style naming in content")

    file_type = max(scores, key=lambda k: scores[k])
    if scores[file_type] == 0:
        file_type = "system_spec"
        reasons.append("Default classification")

    role = PIPELINE_ROLE_BY_FILE_TYPE.get(file_type, "system_spec")
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
        role = "diagram"

    return ClassificationResult(
        file=str(path),
        file_type=file_type,
        role=role,
        reason=reasons[:6],
        user_confirmation_suggested=False,
    )


def classify_input_dir(input_dir: Path, cfg: dict[str, Any]) -> list[ClassificationResult]:
    results: list[ClassificationResult] = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or not is_ingestible_file(path) or path.name == ".gitkeep":
            continue
        if path.suffix.lower() not in {
            ".docx", ".pdf", ".xlsx", ".xlsm", ".xls",
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
            ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".md", ".txt",
        }:
            continue
        results.append(classify_file(path, cfg))
    return results
