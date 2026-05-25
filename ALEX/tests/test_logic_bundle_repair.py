"""Tests for auto-repair of stale Word logic blocks in persisted bundles."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.engine.logic_bundle_repair import is_corrupt_or_only_expression, repair_word_logic_blocks
from web.bundle_helpers import ensure_enriched_bundle

SHUTOFF = (
    Path(__file__).resolve().parents[1]
    / "sample_inputs"
    / "input"
    / "edited_Shutoff_Condition_Spec.docx"
)


def test_corrupt_or_only_detection():
    assert is_corrupt_or_only_expression("(OR OR OR OR OR)")
    assert not is_corrupt_or_only_expression("(HUY = OK OR OK_SHUTOFF = 1)")


def test_repair_stale_shutoff_bundle_from_disk():
    if not SHUTOFF.exists():
        return
    stale = {
        "classified_files": [{"file": str(SHUTOFF)}],
        "logic_blocks": [
            {
                "id": "WD1_01",
                "name": "SHUTOFF_DECISION",
                "raw_expression": "((OK_SHUTOFF = 1 AND NOT NOK_SHUTOFF = (*1)) OR (FORCE_SHUTOFF = 150 AND CND_FORCE_ALLOWED = 0))",
                "source": {"file": SHUTOFF.name},
                "tree": {"type": "OR", "children": []},
            }
        ],
    }
    repaired, flag = repair_word_logic_blocks(stale)
    assert flag is True
    block = next(b for b in repaired["logic_blocks"] if b["name"] == "SHUTOFF_DECISION")
    expr = str(block.get("raw_expression") or "")
    assert "HUY = OK" in expr
    assert "(OR OR OR" not in expr


def test_repair_corrupt_or_only_bundle():
    if not SHUTOFF.exists():
        return
    corrupt = {
        "classified_files": [{"file": str(SHUTOFF)}],
        "logic_blocks": [
            {
                "id": "WD1_01",
                "name": "SHUTOFF_DECISION",
                "raw_expression": "(OR OR OR OR OR OR OR OR OR)",
                "source": {"file": SHUTOFF.name},
                "tree": {
                    "type": "OR",
                    "children": [{"type": "condition", "name": "OR"} for _ in range(5)],
                },
                "unresolved_refs": ["OR"],
            }
        ],
        "logic_review_items": [{"logic_id": "WD1_01", "expression": "(OR OR OR OR OR OR OR OR OR)"}],
    }
    enriched = ensure_enriched_bundle(corrupt)
    block = next(b for b in enriched["logic_blocks"] if b["name"] == "SHUTOFF_DECISION")
    expr = str(block.get("raw_expression") or "")
    assert "HUY = OK" in expr
    item = next(i for i in enriched["logic_review_items"] if i.get("control_name") == "SHUTOFF_DECISION")
    assert "OR" not in (item.get("unresolved_refs") or [])
    assert "HUY = OK" in str(item.get("expression") or "")


def test_repair_job_bundle_yaml_on_disk():
    bundle_path = (
        Path(__file__).resolve().parents[1]
        / "web_data"
        / "output"
        / "analysis_20260523_070254_be658b"
        / "ui_bundle.yaml"
    )
    if not bundle_path.exists():
        return
    bundle = yaml.safe_load(bundle_path.read_text(encoding="utf-8"))
    before = next(b for b in bundle["logic_blocks"] if b.get("name") == "SHUTOFF_DECISION")
    assert "HUY = OK" not in str(before.get("raw_expression") or "")
    enriched = ensure_enriched_bundle(bundle)
    after = next(b for b in enriched["logic_blocks"] if b.get("name") == "SHUTOFF_DECISION")
    assert "HUY = OK" in str(after.get("raw_expression") or "")
