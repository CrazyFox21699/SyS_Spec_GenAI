"""Optional Ollama client for Japanese interpretation (never authoritative)."""

from __future__ import annotations

import json
from typing import Any

import requests


def interpret_japanese_block(
    raw_text: str,
    cfg: dict[str, Any],
) -> dict[str, Any] | None:
    llm = cfg.get("llm", {})
    if not llm.get("enabled"):
        return None
    base = llm.get("base_url", "http://localhost:11434").rstrip("/")
    model = llm.get("model", "qwen2.5")
    timeout = float(llm.get("timeout_seconds", 60))
    prompt = (
        "You are assisting automotive software requirements review. "
        "Translate the following Japanese technical fragment to English, "
        "and propose structured given/when/then bullets as hypotheses only.\n\n"
        f"TEXT:\n{raw_text}\n\n"
        "Respond as JSON with keys: ai_translation_en (string), "
        "ai_technical_interpretation (object with given, when, then as string arrays)."
    )
    try:
        r = requests.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        r.raise_for_status()
        body = r.json()
        text = body.get("response", "")
        try:
            parsed = json.loads(text[text.find("{") : text.rfind("}") + 1])
        except (json.JSONDecodeError, ValueError):
            parsed = {"ai_translation_en": text[:2000], "ai_technical_interpretation": {"given": [], "when": [], "then": []}}
        return {
            "raw_source_text": raw_text,
            "ai_translation_en": parsed.get("ai_translation_en", ""),
            "ai_technical_interpretation": parsed.get("ai_technical_interpretation", {}),
            "confidence": "medium",
            "review_required": {"comtor": True, "engineer": True},
            "source": "llm_generated",
        }
    except (requests.RequestException, OSError):
        return {
            "raw_source_text": raw_text,
            "ai_translation_en": "",
            "ai_technical_interpretation": {},
            "confidence": "low",
            "review_required": {"comtor": True, "engineer": True},
            "source": "llm_generated",
            "error": "ollama_unreachable",
        }
