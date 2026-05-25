"""Load testcase style template and golden samples from bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.config_path import get_config_path
from src.utils.yaml_utils import load_yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STYLE_PATH = ROOT / "config" / "testcase_style.yaml"


def load_testcase_style(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    del cfg
    if DEFAULT_STYLE_PATH.exists():
        data = load_yaml(DEFAULT_STYLE_PATH)
        if isinstance(data, dict):
            return data
    return {"name": "alex_default_en", "rules": [], "examples": {}}


def style_reference_for_bundle(bundle: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Template + engineer-uploaded golden rows."""
    ai = bundle.get("ai_assists") or {}
    samples = ai.get("style_samples") or []
    golden_rows = []
    for row in samples[:6]:
        if not isinstance(row, dict):
            continue
        golden_rows.append(
            {
                "label": row.get("label") or "sample",
                "use_case": row.get("use_case") or "",
                "operation": row.get("operation") or "",
                "expected_input": row.get("expected_input") or "",
                "expected_output": row.get("expected_output") or "",
            }
        )
    template = load_testcase_style(cfg)
    return {
        "template": template,
        "golden_rows": golden_rows,
        "golden_count": len(golden_rows),
    }


def save_style_samples(bundle: dict[str, Any], samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Store up to 6 golden workbook rows on the bundle."""
    cleaned: list[dict[str, Any]] = []
    for i, row in enumerate(samples[:6]):
        if not isinstance(row, dict):
            continue
        cleaned.append(
            {
                "label": str(row.get("label") or f"sample_{i + 1}").strip()[:80],
                "use_case": str(row.get("use_case") or "").strip(),
                "operation": str(row.get("operation") or "").strip(),
                "expected_input": str(row.get("expected_input") or "").strip(),
                "expected_output": str(row.get("expected_output") or "").strip(),
            }
        )
    ai = bundle.setdefault("ai_assists", {})
    ai["style_samples"] = cleaned
    return cleaned
