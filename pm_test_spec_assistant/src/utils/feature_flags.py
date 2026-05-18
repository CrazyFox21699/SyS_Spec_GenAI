"""Read optional feature flags from config (additive upgrades; default off)."""

from __future__ import annotations

from typing import Any


def feature_enabled(cfg: dict[str, Any], name: str, *, default: bool = False) -> bool:
    features = cfg.get("features")
    if not isinstance(features, dict):
        return default
    return bool(features.get(name, default))


def app_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Subset exposed to the web UI."""
    features = cfg.get("features") if isinstance(cfg.get("features"), dict) else {}
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    test_gen = cfg.get("test_generation") if isinstance(cfg.get("test_generation"), dict) else {}
    export_cfg = cfg.get("export") if isinstance(cfg.get("export"), dict) else {}
    return {
        "features": {
            "validator": bool(features.get("validator", False)),
            "add_clone_tc": bool(features.get("add_clone_tc", False)),
            "source_index": bool(features.get("source_index", False)),
            "term_roles": bool(features.get("term_roles", False)),
            "ollama_assist": bool(features.get("ollama_assist", False)),
            "atom_model": bool(features.get("atom_model", False)),
            "understanding_gate": bool(features.get("understanding_gate", False)),
            "evidence_registry": bool(features.get("evidence_registry", True)),
        },
        "deployment": {
            "mode": str((cfg.get("deployment") or {}).get("mode", "local")),
        },
        "llm": {
            "enabled": bool((cfg.get("llm") or {}).get("enabled", False)),
        },
        "test_generation": {"mode": str(test_gen.get("mode", "legacy"))},
        "export": {"strict": bool(export_cfg.get("strict", False))},
        "assist": {
            "default_provider": str(assist.get("default_provider", "m365")),
            "require_m365_login": bool(assist.get("require_m365_login", True)),
            "allow_ollama_fallback": bool(assist.get("allow_ollama_fallback", False)),
            "copilot_enabled": bool((assist.get("copilot") or {}).get("enabled", False)),
            "m365_enabled": bool((assist.get("m365") or {}).get("enabled", False)),
        },
    }
