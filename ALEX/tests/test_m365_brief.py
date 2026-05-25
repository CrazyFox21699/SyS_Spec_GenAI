"""M365 brief export/import parsing."""

from web.m365_brief import build_copilot_brief, parse_knowledge_patches_payload


def test_parse_knowledge_patches_from_fenced_json() -> None:
    raw = """Here is the result:
```json
{"candidates": [{"candidate_id": "TC1", "given": [{"signal": "A", "value": "1"}]}]}
```
"""
    patches = parse_knowledge_patches_payload(raw)
    assert len(patches) == 1
    assert patches[0]["candidate_id"] == "TC1"


def test_build_copilot_brief_includes_logic_id() -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1", "name": "CTRL", "raw_expression": "A AND B"}],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "path_id": "branch_1"},
                "operation": {"given": [{"signal": "A", "value": "0", "operator": "=="}]},
            }
        ],
    }
    text = build_copilot_brief(bundle, "LB1", "A = 1 when B = 0")
    assert "LB1" in text
    assert "TC1" in text
    assert "candidates" in text
