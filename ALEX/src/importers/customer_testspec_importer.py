"""Reverse-import customer TestSpec workbooks into bundle candidates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from src.exporters.customer_testspec_exporter import CUSTOMER_TESTSPEC_HEADERS
from src.importers.synthetic_logic import slug, synthetic_logic_block
from web.candidate_mutations import sanitize_id

_HEADER_ALIASES: dict[str, str] = {
    "no": "No",
    "test function": "Test Function",
    "event": "Event",
    "usecase": "UseCase",
    "use case": "UseCase",
    "operation": "Operation",
    "expected value for input": "Expected value for input",
    "expected value for output": "Expected value for output",
    "candidate id": "Candidate ID",
    "source evidence": "Source Evidence",
    "ai provider": "AI Provider",
    "ai touched fields": "AI Touched Fields",
    "confidence": "Confidence",
    "review status": "Review Status",
    "engineer confirmation required": "Engineer Confirmation Required",
    "open questions": "Open Questions",
}


def _norm_header(cell: Any) -> str:
    text = str(cell or "").strip().lower()
    return _HEADER_ALIASES.get(text, str(cell or "").strip())


def _header_map(header_row: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        canonical = _norm_header(cell)
        if canonical in CUSTOMER_TESTSPEC_HEADERS:
            mapping[canonical] = idx
    return mapping


def _cell(row: list[Any], colmap: dict[str, int], key: str) -> str:
    idx = colmap.get(key)
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx] or "").strip()


def _parse_given_when(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    given: list[dict[str, Any]] = []
    when: list[dict[str, Any]] = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("given:"):
            given.append({"description": line[6:].strip() or line})
        elif lower.startswith("when:"):
            when.append({"description": line[5:].strip() or line})
        elif lower.startswith("precondition:"):
            given.append({"note": line[13:].strip() or line})
        else:
            when.append({"description": line})
    return given, when


def _parse_then(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("then:"):
            out.append({"description": line[5:].strip() or line})
        else:
            out.append({"description": line})
    return out


def _candidate_from_row(
    row: list[Any],
    colmap: dict[str, int],
    *,
    sheet_name: str,
    row_no: int,
    language: str,
    existing_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    test_function = _cell(row, colmap, "Test Function") or "Imported test"
    event = _cell(row, colmap, "Event") or "imported"
    use_case = _cell(row, colmap, "UseCase")
    operation_text = _cell(row, colmap, "Operation")
    expected_input = _cell(row, colmap, "Expected value for input")
    expected_output = _cell(row, colmap, "Expected value for output")
    candidate_id = _cell(row, colmap, "Candidate ID")
    review_status = _cell(row, colmap, "Review Status") or "review_required"
    confidence = _cell(row, colmap, "Confidence") or "medium"
    open_questions = _cell(row, colmap, "Open Questions")
    source_evidence = _cell(row, colmap, "Source Evidence")
    ai_provider = _cell(row, colmap, "AI Provider") or "imported_workbook"
    changed_fields_raw = _cell(row, colmap, "AI Touched Fields")
    changed_fields = [f.strip() for f in changed_fields_raw.split(",") if f.strip()]

    logic_key = slug(test_function)
    logic_id = f"imported_{logic_key}"

    if candidate_id:
        try:
            cid = sanitize_id(candidate_id, field="candidate_id")
        except ValueError:
            cid = ""
    else:
        cid = ""
    if not cid or cid in existing_ids:
        n = 1
        while True:
            cid = f"TC_IMP_{n:03d}"
            if cid not in existing_ids:
                break
            n += 1
    existing_ids.add(cid)

    given, when = _parse_given_when(operation_text)
    if expected_input and not given:
        given = [{"description": expected_input}]
    expectation = _parse_then(expected_output)

    cand: dict[str, Any] = {
        "id": cid,
        "status": "candidate",
        "source": "imported_workbook",
        "test_function": test_function,
        "event": event,
        "use_case_description": use_case or operation_text,
        "precondition": [],
        "operation": {"given": given, "when": when},
        "expectation": expectation,
        "traceability": {
            "logic_id": logic_id,
            "control_name": test_function,
            "source": "imported_workbook",
            "source_evidence": [source_evidence] if source_evidence else [f"{sheet_name} / row {row_no}"],
        },
        "why_recommended": ["Imported from existing TestSpec workbook"],
        "confidence": confidence,
        "review_required": "review" in review_status.lower() or review_status.lower() in {"", "pending"},
        "review_status": review_status or "review_required",
    }

    lang_key = "jp" if language.upper().startswith("J") else "en"
    overlay: dict[str, Any] = {
        "provider": ai_provider,
        "logic_id": logic_id,
        "control_name": test_function,
        "changed_fields": changed_fields or ["UseCase", "Operation", "ExpectedInput", "ExpectedOutput"],
        "open_questions": [q.strip() for q in re.split(r"[;\n]", open_questions) if q.strip()],
        "confidence": confidence,
        "review_required": cand["review_required"],
        lang_key: {
            "use_case": use_case,
            "operation": operation_text,
            "expected_input": expected_input,
            "expected_output": expected_output,
        },
    }
    if lang_key == "en":
        overlay["jp"] = {"use_case": "", "operation": "", "expected_input": "", "expected_output": ""}
    else:
        overlay["en"] = {"use_case": "", "operation": "", "expected_input": "", "expected_output": ""}

    return cand, overlay, logic_id


_CUSTOMER_TESTSPEC_REQUIRED = ("Test Function", "UseCase", "Operation")
_CUSTOMER_TESTSPEC_OPTIONAL = tuple(h for h in CUSTOMER_TESTSPEC_HEADERS if h not in _CUSTOMER_TESTSPEC_REQUIRED)


def preview_testspec_workbook(path: Path) -> dict[str, Any]:
    """Check whether workbook headers match ALEX Final TestSpec export layout."""
    wb = load_workbook(path, data_only=True, read_only=True)
    sheets: list[dict[str, Any]] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(max_row=1, values_only=True))
        if not rows:
            sheets.append({"name": sheet_name, "ok": False, "reason": "empty", "headers_found": []})
            continue
        raw_header = [str(c or "").strip() for c in rows[0]]
        colmap = _header_map(list(rows[0]))
        missing = [h for h in _CUSTOMER_TESTSPEC_REQUIRED if h not in colmap]
        sheets.append(
            {
                "name": sheet_name,
                "ok": not missing and ("Test Function" in colmap or "UseCase" in colmap),
                "headers_found": raw_header[:20],
                "mapped_columns": sorted(colmap.keys()),
                "missing_required": missing,
            }
        )
    wb.close()
    ok_sheets = [s for s in sheets if s.get("ok")]
    return {
        "ok": bool(ok_sheets),
        "sheets": sheets,
        "required_columns": list(_CUSTOMER_TESTSPEC_REQUIRED),
        "supported_columns": list(CUSTOMER_TESTSPEC_HEADERS),
        "hint": (
            "Import expects the same column headers as ALEX Final TestSpec export "
            "(Test Function, Event, UseCase, Operation, Expected value for input/output, …). "
            "Custom team templates may need column rename or a mapping config."
        ),
    }


def import_customer_testspec_workbook(
    path: Path,
    *,
    language: str = "EN",
    sheet_names: list[str] | None = None,
) -> dict[str, Any]:
    wb = load_workbook(path, data_only=True)
    targets = sheet_names or wb.sheetnames
    candidates: list[dict[str, Any]] = []
    overlays: dict[str, dict[str, Any]] = {}
    logic_groups: dict[str, str] = {}
    sheet_summary: list[dict[str, Any]] = []
    existing_ids: set[str] = set()

    for sheet_name in targets:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            sheet_summary.append({"name": sheet_name, "rows_imported": 0, "skipped": "empty"})
            continue
        colmap = _header_map(list(rows[0]))
        if "Test Function" not in colmap and "UseCase" not in colmap:
            sheet_summary.append({"name": sheet_name, "rows_imported": 0, "skipped": "header_mismatch"})
            continue
        imported = 0
        for row_no, row in enumerate(rows[1:], start=2):
            if not any(str(c or "").strip() for c in row):
                continue
            if not (_cell(list(row), colmap, "Test Function") or _cell(list(row), colmap, "UseCase")):
                continue
            cand, overlay, logic_id = _candidate_from_row(
                list(row),
                colmap,
                sheet_name=sheet_name,
                row_no=row_no,
                language=language,
                existing_ids=existing_ids,
            )
            candidates.append(cand)
            overlays[cand["id"]] = overlay
            logic_groups[logic_id] = cand["test_function"]
            imported += 1
        sheet_summary.append({"name": sheet_name, "rows_imported": imported})

    logic_blocks = [
        synthetic_logic_block(
            logic_id,
            control,
            source={"file": path.name, "sheet": sheet_name, "kind": "imported_testspec"},
        )
        for logic_id, control in logic_groups.items()
    ]

    return {
        "test_candidates": candidates,
        "candidate_overlays": overlays,
        "logic_blocks": logic_blocks,
        "sheet_summary": sheet_summary,
    }
