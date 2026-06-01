#!/usr/bin/env python3
"""Import alex_code_config_bundle.md into a job's project code config (CLI)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.config_bundle_layers import (  # noqa: E402
    apply_bundle_import_sections,
    preview_config_bundle,
)


def _resolve_job_output(job_id: str, output_root: Path | None) -> Path:
    if output_root:
        candidate = output_root / job_id
        if candidate.is_dir():
            return candidate
    default = ROOT / "web_data" / "output" / job_id
    if default.is_dir():
        return default
    raise SystemExit(f"Job output not found: {job_id} (tried {default})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Copilot config bundle into ALEX job")
    parser.add_argument("job_id", help="e.g. analysis_20260601_112120_245a66")
    parser.add_argument(
        "bundle_path",
        nargs="?",
        default=str(ROOT / "tests" / "fixtures" / "copilot_config_bundle_real.md"),
        help="Path to alex_code_config_bundle.md (default: PM Copilot fixture)",
    )
    parser.add_argument("--output-root", type=Path, default=None, help="Override web_data/output parent")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    args = parser.parse_args()

    bundle_path = Path(args.bundle_path)
    if not bundle_path.is_file():
        raise SystemExit(f"Bundle file not found: {bundle_path}")

    text = bundle_path.read_text(encoding="utf-8")
    job_output = _resolve_job_output(args.job_id, args.output_root)

    preview = preview_config_bundle(job_output, text)
    print(json.dumps(
        {
            "ok": preview.get("ok"),
            "detected_sections": preview.get("detected_sections"),
            "missing_sections": preview.get("missing_sections"),
            "warnings": preview.get("warnings"),
            "import_diagnostics": preview.get("import_diagnostics"),
        },
        indent=2,
    ))
    if not preview.get("ok"):
        return 1
    if args.dry_run:
        print("Dry run — no files written.")
        return 0

    result = apply_bundle_import_sections(job_output, text)
    print(json.dumps(
        {
            "ok": result.get("ok"),
            "applied_sections": result.get("applied_sections"),
            "version": result.get("version", {}).get("config_version_id"),
            "config_dir": str(job_output / "bundle" / "code_config"),
        },
        indent=2,
    ))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
