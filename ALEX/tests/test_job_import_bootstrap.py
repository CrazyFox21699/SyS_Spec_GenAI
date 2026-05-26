from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from src.importers.customer_testspec_importer import import_customer_testspec_workbook
from src.importers.job_bootstrap import bootstrap_from_bundle_dict, bootstrap_from_testspec_xlsx
from src.exporters.customer_testspec_exporter import CUSTOMER_TESTSPEC_HEADERS
from web.copilot_errors import classify_copilot_error


def _write_sample_testspec(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "System Test Spec"
    ws.append(CUSTOMER_TESTSPEC_HEADERS)
    ws.append(
        [
            1,
            "Garage mode",
            "GRMD_EIG",
            "Verify GRMD_EIG ON when in garage mode",
            "Given: GRMD_IFU=ON\nWhen: evaluate garage mode",
            "Given: GRMD_IFU=ON",
            "Then: GRMD_EIG=1",
            "",
            "",
            "",
            "",
            "medium",
            "review_required",
            "yes",
            "",
        ]
    )
    wb.save(path)


def test_import_testspec_workbook_creates_candidates(tmp_path: Path) -> None:
    xlsx = tmp_path / "TestSpec_Module_EN.xlsx"
    _write_sample_testspec(xlsx)
    imported = import_customer_testspec_workbook(xlsx, language="EN")
    assert len(imported["test_candidates"]) == 1
    assert imported["test_candidates"][0]["test_function"] == "Garage mode"
    assert imported["candidate_overlays"]
    assert len(imported["logic_blocks"]) == 1
    assert imported["logic_blocks"][0]["parse_status"] == "imported"


def test_bootstrap_from_testspec_xlsx(tmp_path: Path) -> None:
    xlsx = tmp_path / "TestSpec_Module_EN.xlsx"
    _write_sample_testspec(xlsx)
    bundle = bootstrap_from_testspec_xlsx(xlsx)
    assert bundle["bootstrap_source"] == "imported_testspec"
    assert len(bundle["test_candidates"]) == 1
    assert len(bundle["logic_blocks"]) >= 1
    assert bundle["summary"]["test_candidates"] == 1


def test_bootstrap_from_bundle_dict_adds_synthetic_logic() -> None:
    bundle = bootstrap_from_bundle_dict(
        {
            "test_candidates": [
                {
                    "id": "TC_001",
                    "test_function": "KCC signal",
                    "traceability": {"logic_id": "imported_KCC_signal", "control_name": "KCC signal"},
                    "operation": {"given": [], "when": []},
                    "expectation": [],
                    "status": "candidate",
                }
            ]
        },
        source="imported_yaml",
    )
    assert bundle["bootstrap_source"] == "imported_yaml"
    assert any(b.get("id") == "imported_KCC_signal" for b in bundle["logic_blocks"])


def test_copilot_error_taxonomy_no_context() -> None:
    err = classify_copilot_error(has_context_pack=False, has_logic_id=True)
    assert err["error_category"] == "no_context"
    assert "Build context" in err["error"]
