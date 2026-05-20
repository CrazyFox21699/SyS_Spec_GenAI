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
        patch(
            "web.ai_provider.apply_knowledge_via_m365",
            return_value={"ok": True, "patches": patches, "definition_updates": []},
        ),
    ):
        out = apply_knowledge(bundle, "LB1", "set A to 2", cfg, provider="m365")
    assert out.get("ok") is True
    assert out.get("provider") == "m365"
    assert out.get("candidates_updated", 0) >= 1


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
        patch("web.ai_provider.m365_auth.is_api_ready", return_value=True),
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
        out = apply_knowledge(bundle, "LB1", "set A to 3", cfg, provider="auto")
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
