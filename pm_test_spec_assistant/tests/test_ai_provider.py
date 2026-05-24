"""AI provider router (M365 Copilot primary)."""

from unittest.mock import patch

from web.ai_provider import (
    apply_knowledge,
    default_provider,
    normalize_provider_name,
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


def test_auto_chain_order_ollama_m365_copilot() -> None:
    cfg = {
        "assist": {
            "default_provider": "ollama",
            "copilot": {"enabled": True},
            "allow_ollama_fallback": True,
        },
        "llm": {"enabled": True},
    }
    with (
        patch("web.ai_provider._ollama_usable", return_value=True),
        patch("web.ai_provider._m365_usable", return_value=True),
        patch("web.ai_provider.copilot_cli_ready", return_value=True),
    ):
        chain = resolve_knowledge_provider_chain(cfg, "auto")
    assert chain == ["ollama", "m365", "copilot"]


def test_auto_falls_back_from_ollama_to_m365() -> None:
    cfg = {
        "assist": {
            "default_provider": "ollama",
            "require_m365_login": False,
            "allow_ollama_fallback": True,
            "validation_retries": 0,
            "copilot": {"enabled": True},
        },
        "llm": {"enabled": True},
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
        patch("web.ai_provider._ollama_usable", return_value=True),
        patch("web.ai_provider._m365_usable", return_value=True),
        patch("web.ai_provider.copilot_cli_ready", return_value=False),
        patch(
            "web.ai_provider.apply_knowledge_ollama_batched",
            return_value={"ok": False, "provider": "ollama", "error": "offline"},
        ),
        patch(
            "web.ai_provider.apply_knowledge_m365",
            return_value={"ok": True, "provider": "m365", "candidates_updated": 1, "failures_remaining": 0},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 3", cfg, provider="auto", compile_constraints_first=False)
    assert out.get("ok") is True
    assert out.get("provider") == "m365"
    assert "ollama" in (out.get("providers_tried") or [])


def test_auto_falls_back_from_m365_to_copilot() -> None:
    cfg = {
        "assist": {
            "default_provider": "m365",
            "require_m365_login": False,
            "allow_ollama_fallback": False,
            "validation_retries": 0,
            "copilot": {"enabled": True},
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
    patches = [{"candidate_id": "TC1", "given": [{"signal": "A", "value": "3"}]}]
    with (
        patch("web.ai_provider._ollama_usable", return_value=False),
        patch("web.ai_provider._m365_usable", return_value=True),
        patch("web.ai_provider.copilot_cli_ready", return_value=True),
        patch(
            "web.ai_provider.apply_knowledge_m365",
            return_value={"ok": False, "provider": "m365", "error": "403 Copilot license"},
        ),
        patch(
            "web.ai_provider.apply_knowledge_copilot",
            return_value={"ok": True, "provider": "copilot", "candidates_updated": 1, "failures_remaining": 0},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 3", cfg, provider="auto", compile_constraints_first=False)
    assert out.get("ok") is True
    assert out.get("provider") == "copilot"
    assert "m365" in (out.get("providers_tried") or [])


def test_normalize_provider_name() -> None:
    assert normalize_provider_name("github") == "copilot"
    assert normalize_provider_name("m365_api") == "m365"
    assert normalize_provider_name("") == "auto"


def test_resolve_chain_explicit_copilot() -> None:
    cfg = {"assist": {"copilot": {"enabled": True}, "default_provider": "m365"}}
    assert resolve_knowledge_provider_chain(cfg, "copilot") == ["copilot"]


def test_resolve_chain_drops_m365_when_msa() -> None:
    cfg = {
        "assist": {
            "default_provider": "ollama",
            "copilot": {"enabled": True},
            "allow_ollama_fallback": True,
        },
        "llm": {"enabled": False},
    }
    with (
        patch("web.ai_provider._ollama_usable", return_value=False),
        patch("web.ai_provider._m365_usable", return_value=False),
        patch("web.ai_provider.copilot_cli_ready", return_value=True),
    ):
        chain = resolve_knowledge_provider_chain(cfg, "auto")
    assert "m365" not in chain
    assert chain[0] == "copilot"


def test_apply_knowledge_skips_m365_call_when_not_entitled() -> None:
    """apply_knowledge_m365 must not make an HTTP call when the session is MSA / unlicensed."""
    from web.ai_provider import apply_knowledge_m365

    bundle = {"logic_blocks": [{"id": "LB1"}], "test_candidates": []}
    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=False),
        patch("web.ai_provider.apply_knowledge_via_m365") as mocked_call,
    ):
        out = apply_knowledge_m365({}, {}, logic_id="LB1", engineer_note="note")
    mocked_call.assert_not_called()
    assert out["ok"] is False
    assert out["reason"] == "not_entitled"
    assert out["activation_guide"].endswith("M365_COPILOT_ACTIVATION_GUIDE.md")


def test_apply_knowledge_m365_translates_not_entitled_exception() -> None:
    """Typed not-entitled errors raised mid-call become structured responses."""
    from web.ai_provider import apply_knowledge_m365
    from web.m365_copilot import M365CopilotNotEntitledError

    def raise_not_entitled(*args, **kwargs):
        raise M365CopilotNotEntitledError(
            status_code=400, raw_body="no addressUrl", reason="msa"
        )

    with (
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
        patch("web.ai_provider.m365_auth.is_copilot_chat_entitled", return_value=True),
        patch("web.ai_provider.apply_knowledge_via_m365", side_effect=raise_not_entitled),
    ):
        out = apply_knowledge_m365({}, {}, logic_id="LB1", engineer_note="note")
    assert out["ok"] is False
    assert out["reason"] == "not_entitled"
    assert out["not_entitled_kind"] == "msa"
    assert "M365_COPILOT_ACTIVATION_GUIDE" in out["activation_guide"]
