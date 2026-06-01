"""Provider-neutral generation source identifiers (no external API calls)."""

from __future__ import annotations

COPILOT_WEB = "COPILOT_WEB"
COPILOT_API = "COPILOT_API"
CLAUDE_MANUAL = "CLAUDE_MANUAL"
CLAUDE_API_FUTURE = "CLAUDE_API_FUTURE"
LOCAL_TEMPLATE = "LOCAL_TEMPLATE"
MANUAL = "MANUAL"

ALL_GENERATION_SOURCES = frozenset(
    {
        COPILOT_WEB,
        COPILOT_API,
        CLAUDE_MANUAL,
        CLAUDE_API_FUTURE,
        LOCAL_TEMPLATE,
        MANUAL,
    }
)
