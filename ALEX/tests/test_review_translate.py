from unittest.mock import patch

from web.review_translate import translate_workbook_with_ollama


def test_translate_requires_ollama() -> None:
    bundle = {"test_candidates": [{"id": "C1"}], "ai_assists": {}}
    cfg = {"llm": {"enabled": False}, "features": {}}
    with patch("web.review_translate.ollama_status", return_value={"reachable": False}):
        with patch("web.review_translate.llm_enabled_for_assist", return_value=True):
            out = translate_workbook_with_ollama(bundle, cfg)
    assert out["ok"] is False
