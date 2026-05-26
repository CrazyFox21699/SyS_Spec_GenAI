"""M365 Copilot strict procedure (mocked Graph)."""

from unittest.mock import patch

from web.m365_copilot import (
    M365CopilotNotEntitledError,
    apply_knowledge_via_m365,
    probe_copilot_api,
    run_copilot_chat_result,
)


def test_apply_knowledge_via_m365_parses_json() -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1"}],
        "test_candidates": [{"id": "TC1", "traceability": {"logic_block": "LB1"}, "operation": {"given": []}}],
    }
    cfg = {"assist": {"m365": {"timezone": "UTC"}}}
    reply = '{"candidates":[{"candidate_id":"TC1","given":[{"signal":"SPD","value":"101"}]}],"definition_updates":[{"name":"SPD","definition":"=101 km/h"}]}'
    with patch(
        "web.m365_copilot.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply, "conversation_id": "conv-1"},
    ):
        out = apply_knowledge_via_m365(bundle, cfg, logic_id="LB1", engineer_note="speed 101")
    assert out["ok"] is True
    assert len(out["patches"]) == 1
    assert out["patches"][0]["candidate_id"] == "TC1"
    defs = bundle["ai_assists"]["engineer_definitions"]
    assert defs["SPD"]["definition"] == "=101 km/h"


def test_apply_knowledge_via_m365_structured_error() -> None:
    bundle = {"logic_blocks": [{"id": "LB1"}], "test_candidates": []}
    cfg = {"assist": {"m365": {"timezone": "UTC"}}}
    with patch(
        "web.m365_copilot.run_copilot_chat_result",
        return_value={"ok": False, "error": "no license", "error_category": "m365_not_entitled"},
    ):
        out = apply_knowledge_via_m365(bundle, cfg, logic_id="LB1", engineer_note="")
    assert out["ok"] is False
    assert out["error_category"] == "m365_not_entitled"


def test_run_copilot_chat_result_not_entitled() -> None:
    with patch(
        "web.m365_copilot.m365_auth.require_api_token",
        return_value="token",
    ), patch(
        "web.m365_copilot._create_conversation",
        side_effect=M365CopilotNotEntitledError(status_code=403, raw_body="no license", reason="no_license"),
    ):
        out = run_copilot_chat_result({}, "ping")
    assert out["ok"] is False
    assert out["error_category"] == "m365_not_entitled"


def test_run_copilot_chat_result_missing_scopes() -> None:
    from web.m365_copilot import M365CopilotMissingScopesError

    with patch(
        "web.m365_copilot.m365_auth.require_api_token",
        return_value="token",
    ), patch(
        "web.m365_copilot._create_conversation",
        side_effect=M365CopilotMissingScopesError(
            status_code=403,
            raw_body='{"error":{"message":"Required scopes = [Sites.Read.All]"}}',
        ),
    ):
        out = run_copilot_chat_result({}, "ping")
    assert out["ok"] is False
    assert out["error_category"] == "m365_missing_scopes"


def test_probe_copilot_api_ok() -> None:
    cfg = {"assist": {"m365": {"timezone": "UTC"}}}
    with patch(
        "web.m365_copilot.run_copilot_chat_result",
        return_value={"ok": True, "reply": "ALEX probe OK", "conversation_id": "c1"},
    ), patch("web.m365_copilot.m365_auth.record_copilot_api_probe") as rec:
        out = probe_copilot_api(cfg, user_id="u1")
    assert out["ok"] is True
    assert out["chat_ok"] is True
    rec.assert_called_once()
