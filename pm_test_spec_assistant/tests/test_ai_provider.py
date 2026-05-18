"""AI provider router (M365 Copilot primary)."""

from unittest.mock import patch

from web.ai_provider import apply_knowledge, default_provider, require_m365_login


def test_apply_knowledge_requires_m365_sign_in() -> None:
    cfg = {
        "assist": {
            "default_provider": "m365",
            "require_m365_login": True,
            "allow_ollama_fallback": False,
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
        out = apply_knowledge(bundle, "LB1", "A is equal to 1", cfg)
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
        out = apply_knowledge(bundle, "LB1", "set A to 2", cfg)
    assert out.get("ok") is True
    assert out.get("provider") == "m365"
    assert out.get("candidates_updated", 0) >= 1
