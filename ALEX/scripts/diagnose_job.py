#!/usr/bin/env python3
"""Print parser/Copilot diagnostic summary for an ALEX job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.job_diagnostic import diagnose_job_bundle, load_bundle_for_diagnostic  # noqa: E402


def _resolve_output_dir(job_id: str, output_root: Path | None) -> Path:
    if output_root:
        candidate = output_root / job_id
        if candidate.is_dir():
            return candidate
    from web.alex_storage import WEB_DATA

    data = WEB_DATA
    for base in (data / "output", data):
        for path in base.rglob(job_id):
            if path.is_dir() and (path / "ui_bundle.yaml").exists():
                return path
            bundle_dir = path / "bundle"
            if bundle_dir.is_dir() and (bundle_dir / "manifest.json").exists():
                return path
    raise SystemExit(f"Job output not found for {job_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose ALEX job bundle and parser coverage")
    parser.add_argument("--job-id", required=True, help="Analysis job id (analysis_YYYYMMDD_...)")
    parser.add_argument("--output-root", type=Path, default=None, help="Optional output root directory")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    args = parser.parse_args()

    out_dir = _resolve_output_dir(args.job_id, args.output_root)
    bundle = load_bundle_for_diagnostic(out_dir)
    if not bundle:
        raise SystemExit(f"No bundle in {out_dir}")

    report = diagnose_job_bundle(bundle)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print(f"Job: {args.job_id}")
    print(f"Output: {out_dir}")
    print(f"Bootstrap: {report.get('bootstrap_source')} {report.get('bootstrap_label') or ''}".strip())
    print(f"Test candidates: {report.get('test_candidates', 0)}")
    logic = report.get("logic") or {}
    print(f"Logic blocks: {logic.get('count', 0)} ({logic.get('by_parse_status')})")
    word = report.get("word_tables") or {}
    print(
        f"Word tables: {word.get('tables_total', 0)} total, "
        f"{word.get('tables_matched', 0)} matched, {word.get('tables_unmatched', 0)} unmatched"
    )
    excel = report.get("excel_sheets") or {}
    sheets = excel.get("sheets") or []
    if sheets:
        print("Excel sheets:")
        for row in sheets:
            name = row.get("name", "?")
            extra = row.get("rows_imported", row.get("logic_blocks", ""))
            print(f"  - {name}: {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
