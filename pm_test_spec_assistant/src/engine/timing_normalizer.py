"""Normalize timing phrases; document interpretation for review."""

from __future__ import annotations

import re
from typing import Any


def normalize_timing_expressions(raw_text: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    timing_cfg = cfg.get("timing", {})
    default_op = timing_cfg.get("default_interpret_equal_time_as", ">=")
    review_equal = timing_cfg.get("review_required_for_equal_time", True)
    patterns = timing_cfg.get("patterns", [])
    out: list[dict[str, Any]] = []

    for pat in patterns:
        try:
            rx = re.compile(pat, re.IGNORECASE)
        except re.error:
            continue
        for m in rx.finditer(raw_text or ""):
            span = m.group(0)
            item: dict[str, Any] = {
                "raw_text": span,
                "source": "deterministic",
                "confidence": "medium",
                "review_required": True,
            }
            eq_ms = re.search(r"=\s*(\d+)\s*ms", span, re.I)
            ge_ms = re.search(r">=\s*(\d+)\s*ms", span, re.I)
            if eq_ms:
                ms = int(eq_ms.group(1))
                item["interpreted_as"] = f"elapsed_time {default_op} {ms}ms"
                item["timer"] = re.search(r"(T\d*|T_trans|T5)", span, re.I)
                if item["timer"]:
                    item["timer"] = item["timer"].group(1)
                item["operator"] = default_op
                item["value_ms"] = ms
                item["reason"] = [
                    "Equality-style timing in requirements often maps to threshold crossing in tests.",
                    f"Configured default_interpret_equal_time_as: {default_op}",
                ]
                item["review_required"] = bool(review_equal)
            elif ge_ms:
                ms = int(ge_ms.group(1))
                item["interpreted_as"] = f"elapsed_time >= {ms}ms"
                item["operator"] = ">="
                item["value_ms"] = ms
                item["reason"] = ["Explicit '>=' timing."]
            else:
                item["interpreted_as"] = span
                item["reason"] = ["Pattern matched; manual interpretation needed."]
            out.append(item)
    return out
