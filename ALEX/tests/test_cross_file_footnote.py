from __future__ import annotations

from src.engine.cross_file_resolver import resolve_cross_ref, resolve_footnote_cross_refs
from src.engine.footnote_materializer import link_footnotes_to_logic_blocks, materialize_footnote_attachments


def test_resolve_cross_ref_sheet_to_logic_blocks() -> None:
    bundle = {
        "classified_files": [{"file": "GPT_GenLogic.xlsx"}],
        "logic_blocks": [
            {
                "id": "TC2_SHEET1_CTRL",
                "name": "SYS_SHUTOFF",
                "source": {"file": "GPT_GenLogic.xlsx", "sheet": "Test_Power_State_Spec"},
            }
        ],
        "condition_definitions": [],
    }
    ref = resolve_cross_ref(
        {"type": "sheet", "text": "Test_Power_State_Spec"},
        classified_files=bundle["classified_files"],
        logic_blocks=bundle["logic_blocks"],
        condition_definitions=bundle["condition_definitions"],
    )
    assert ref["resolved"] is True
    assert "TC2_SHEET1_CTRL" in ref["target_logic_ids"]


def test_materialize_footnote_attaches_target_logic() -> None:
    bundle = {
        "classified_files": [{"file": "main.docx"}, {"file": "GPT_GenLogic.xlsx"}],
        "logic_blocks": [
            {
                "id": "TC2_MAIN",
                "name": "OK_SHUTOFF",
                "raw_expression": "REQ_GROUP (*1)",
                "source": {"file": "main.docx", "control": "OK_SHUTOFF"},
            },
            {
                "id": "TC2_REF",
                "name": "PWR_REQ_GROUP",
                "raw_expression": "PWR_REQ = 1 AND T_REQ_STABLE elapsed",
                "source": {"file": "GPT_GenLogic.xlsx", "sheet": "Test_Power_State_Spec"},
            },
        ],
        "footnote_definitions": [
            {
                "ref": "(*1)",
                "logic_id": "TC2_MAIN",
                "definition": "Refer to sheet Test_Power_State_Spec for PWR_REQ_GROUP logic",
                "cross_refs": [
                    {
                        "type": "sheet",
                        "text": "Test_Power_State_Spec",
                        "resolved_file": None,
                        "resolved_node": None,
                    }
                ],
            }
        ],
        "condition_definitions": [],
    }
    resolve_footnote_cross_refs(bundle)
    result = materialize_footnote_attachments(bundle)
    assert result["materialized_count"] >= 1
    main = next(lb for lb in bundle["logic_blocks"] if lb["id"] == "TC2_MAIN")
    attached = main.get("attached_logic") or []
    assert any(a.get("logic_id") == "TC2_REF" for a in attached)


def test_link_footnotes_sets_logic_id_from_table() -> None:
    bundle = {
        "logic_blocks": [{"id": "TC2_TBL1", "name": "CTRL_A", "source": {"control": "CTRL_A"}}],
        "footnote_definitions": [
            {
                "ref": "(*2)",
                "control": "CTRL_A",
                "source": {"table_id": "TBL1"},
            }
        ],
    }
    linked = link_footnotes_to_logic_blocks(bundle)
    assert linked == 1
    assert bundle["footnote_definitions"][0]["logic_id"] == "TC2_TBL1"
