"""AI provider router (M365 Copilot only)."""

from unittest.mock import patch

from web.ai_provider import (
    apply_knowledge,
    default_provider,
    improve_io,
    normalize_provider_name,
    provider_status,
    require_m365_login,
    resolve_knowledge_provider_chain,
)


def test_apply_knowledge_requires_m365_sign_in() -> None:
    cfg = {
        "assist": {
            "default_provider": "m365",
            "require_m365_login": True,
            "allow_ollama_fallback": False,
            "copilot": {"enabled": False},
        },
        "llm": {"enabled": False},
        "features": {},
    }
    bundle = {
        "logic_blocks": [{"id": "LB1", "raw_expression": "A"}],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
            }
        ],
    }
    with patch("web.ai_provider.m365_auth.is_api_ready", return_value=False):
        out = apply_knowledge(bundle, "LB1", "A is equal to 1", cfg, provider="m365")
    assert out.get("provider") == "m365"
    assert out.get("ok") is False
    assert "Sign in" in str(out.get("error") or "")
    assert default_provider(cfg) == "m365"
    assert require_m365_login(cfg) is True


def test_apply_knowledge_m365_applies_patches() -> None:
    cfg = {
        "assist": {
            "default_provider": "m365",
            "require_m365_login": True,
            "allow_ollama_fallback": False,
            "validation_retries": 0,
            "copilot": {"enabled": False},
        },
        "llm": {"enabled": False},
    }
    bundle = {
        "logic_blocks": [{"id": "LB1", "raw_expression": "A"}],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
            }
        ],
    }
    patches = [{"candidate_id": "TC1", "given": [{"signal": "A", "value": "2"}]}]
    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=True),
        patch(
            "web.ai_provider.apply_knowledge_via_m365",
            return_value={"ok": True, "patches": patches, "definition_updates": []},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 2", cfg, provider="m365", preview_only=False)
    assert out.get("ok") is True
    assert out.get("provider") == "m365"
    assert out.get("candidates_updated", 0) >= 1


def test_apply_knowledge_preview_stores_pending_without_mutating() -> None:
    cfg = {
        "assist": {"validation_retries": 0, "copilot": {"enabled": False}},
        "llm": {"enabled": False},
    }
    bundle = {
        "logic_blocks": [{"id": "LB1", "raw_expression": "A"}],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
            }
        ],
    }
    patches = [{"candidate_id": "TC1", "given": [{"signal": "A", "value": "2"}]}]
    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=True),
        patch(
            "web.ai_provider.apply_knowledge_via_m365",
            return_value={"ok": True, "patches": patches, "definition_updates": []},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 2", cfg, provider="m365")
    assert out.get("preview") is True
    assert out.get("pending_patches") == 1
    assert bundle["test_candidates"][0]["operation"]["given"][0]["value"] == "1"


def test_auto_chain_m365_only_when_ready() -> None:
    cfg = {"assist": {"default_provider": "m365"}, "llm": {"enabled": False}}
    with patch("web.ai_provider._m365_usable", return_value=True):
        assert resolve_knowledge_provider_chain(cfg, "auto") == ["m365"]
        assert resolve_knowledge_provider_chain(cfg, "ollama") == ["m365"]
        assert resolve_knowledge_provider_chain(cfg, "copilot") == ["m365"]


def test_auto_chain_empty_when_not_signed_in() -> None:
    cfg = {"assist": {"default_provider": "m365"}, "llm": {"enabled": False}}
    with patch("web.ai_provider._m365_usable", return_value=False):
        assert resolve_knowledge_provider_chain(cfg, "auto") == []


def test_apply_knowledge_no_fallback_when_m365_fails() -> None:
    cfg = {
        "assist": {"default_provider": "m365", "validation_retries": 0},
        "llm": {"enabled": False},
    }
    bundle = {
        "logic_blocks": [{"id": "LB1", "raw_expression": "A"}],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
            }
        ],
    }
    with (
        patch("web.ai_provider._m365_usable", return_value=True),
        patch(
            "web.ai_provider.apply_knowledge_m365",
            return_value={"ok": False, "provider": "m365", "error": "403 Copilot license"},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 3", cfg, provider="auto", compile_constraints_first=False)
    assert out.get("ok") is False
    assert out.get("provider") == "m365"
    assert out.get("providers_tried") == ["m365"]


def test_normalize_provider_name_maps_legacy_to_m365() -> None:
    assert normalize_provider_name("github") == "m365"
    assert normalize_provider_name("ollama") == "m365"
    assert normalize_provider_name("m365_api") == "m365"
    assert normalize_provider_name("") == "m365"


def test_provider_status_m365_only() -> None:
    cfg = {"assist": {"default_provider": "m365"}, "llm": {"enabled": False}}
    with patch("web.ai_provider.m365_auth.m365_status", return_value={"api_ready": False}):
        st = provider_status(cfg, light=True)
    assert st["default_provider"] == "m365"
    assert st["allow_ollama_fallback"] is False
    assert st["providers_available"]["ollama"] is False
    assert st["providers_available"]["copilot"] is False


def test_apply_knowledge_skips_m365_call_when_not_entitled() -> None:
    from web.ai_provider import apply_knowledge_m365

    bundle = {"logic_blocks": [{"id": "LB1"}], "test_candidates": []}
    cfg = {"assist": {}}
    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=False),
        patch("web.ai_provider.apply_knowledge_via_m365") as mocked_call,
    ):
        out = apply_knowledge_m365(bundle, cfg, logic_id="LB1", engineer_note="note")
    mocked_call.assert_not_called()
    assert out["ok"] is False
    assert out["reason"] == "not_entitled"
    assert out["activation_guide"].endswith("README.md")


def test_apply_knowledge_m365_translates_not_entitled_exception() -> None:
    from web.ai_provider import apply_knowledge_m365
    from web.m365_copilot import M365CopilotNotEntitledError

    bundle = {"logic_blocks": [{"id": "LB1"}], "test_candidates": []}
    cfg = {"assist": {}}

    def raise_not_entitled(*args, **kwargs):
        raise M365CopilotNotEntitledError(
            status_code=400, raw_body="no addressUrl", reason="msa"
        )

    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=True),
        patch("web.ai_provider.apply_knowledge_via_m365", side_effect=raise_not_entitled),
    ):
        out = apply_knowledge_m365(bundle, cfg, logic_id="LB1", engineer_note="note")
    assert out["ok"] is False
    assert out["reason"] == "not_entitled"
    assert out["not_entitled_kind"] == "msa"
    assert out["activation_guide"] == "README.md"


def test_improve_io_via_m365_wrapper() -> None:
    cfg = {"assist": {"default_provider": "m365"}, "llm": {"enabled": False}}
    with (
        patch("web.ai_provider._m365_usable", return_value=True),
        patch(
            "web.ai_provider.improve_io_via_m365",
            return_value={"ok": True, "result": {"expected_input": "Given: A=1"}},
        ),
    ):
        out = improve_io(
            cfg,
            candidate_id="TC1",
            expected_input="Given: A=0",
            expected_output="Then: ok",
            issues=[],
        )
    assert out["ok"] is True
    assert out["provider"] == "m365"


def test_improve_io_via_m365_mock() -> None:
    from web.m365_copilot import improve_io_via_m365

    cfg = {"assist": {"m365": {}}}
    with patch(
        "web.m365_copilot.run_copilot_chat_result",
        return_value={"ok": True, "reply": '{"expected_input":"Given: X=1"}'},
    ):
        out = improve_io_via_m365(cfg, "Improve this I/O")
    assert out["ok"] is True
    assert out["result"]["expected_input"] == "Given: X=1"
