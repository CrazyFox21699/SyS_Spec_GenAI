"""M365 Copilot strict procedure (mocked Graph)."""

from unittest.mock import patch

from web.m365_copilot import apply_knowledge_via_m365


def test_apply_knowledge_via_m365_parses_json() -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1"}],
        "test_candidates": [{"id": "TC1", "traceability": {"logic_block": "LB1"}, "operation": {"given": []}}],
    }
    cfg = {"assist": {"m365": {"timezone": "UTC"}}}
    reply = '{"candidates":[{"candidate_id":"TC1","given":[{"signal":"SPD","value":"101"}]}],"definition_updates":[{"name":"SPD","definition":"=101 km/h"}]}'
    with (
        patch("web.m365_copilot.m365_auth.require_api_token", return_value="token"),
        patch("web.m365_copilot._create_conversation", return_value="conv-1"),
        patch("web.m365_copilot._chat", return_value=reply),
    ):
        out = apply_knowledge_via_m365(bundle, cfg, logic_id="LB1", engineer_note="speed 101")
    assert out["ok"] is True
    assert len(out["patches"]) == 1
    assert out["patches"][0]["candidate_id"] == "TC1"
    defs = bundle["ai_assists"]["engineer_definitions"]
    assert defs["SPD"]["definition"] == "=101 km/h"
