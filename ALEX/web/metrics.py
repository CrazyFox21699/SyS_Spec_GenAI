"""Simple Prometheus-style metrics for production."""

from __future__ import annotations

import time
from typing import Any

_COUNTERS: dict[str, int] = {
    "alex_analyze_started_total": 0,
    "alex_analyze_completed_total": 0,
    "alex_analyze_failed_total": 0,
    "alex_footnote_unresolved_total": 0,
    "alex_gate_needs_engineer_total": 0,
}
_GAUGES: dict[str, float] = {
    "alex_queue_depth": 0,
}
_HISTOGRAMS: list[tuple[str, float]] = []


def inc(name: str, amount: int = 1) -> None:
    if name in _COUNTERS:
        _COUNTERS[name] += amount


def set_gauge(name: str, value: float) -> None:
    _GAUGES[name] = value


def observe_analyze_duration(seconds: float) -> None:
    _HISTOGRAMS.append((time.time(), seconds))
    if len(_HISTOGRAMS) > 500:
        del _HISTOGRAMS[:250]


def record_bundle_gate_summary(resolved_blocks: list[dict[str, Any]]) -> None:
    for rb in resolved_blocks:
        gate = rb.get("gate_status", "")
        if gate == "needs_engineer":
            inc("alex_gate_needs_engineer_total")
        for gap in rb.get("gaps") or []:
            if gap.get("kind") == "footnote_unresolved":
                inc("alex_footnote_unresolved_total")


def render_prometheus() -> str:
    lines: list[str] = []
    for k, v in _COUNTERS.items():
        lines.append(f"# TYPE {k} counter")
        lines.append(f"{k} {v}")
    for k, v in _GAUGES.items():
        lines.append(f"# TYPE {k} gauge")
        lines.append(f"{k} {v}")
    if _HISTOGRAMS:
        lines.append("# TYPE alex_analyze_duration_seconds summary")
        durations = [h[1] for h in _HISTOGRAMS]
        lines.append(f"alex_analyze_duration_seconds_count {len(durations)}")
        if durations:
            lines.append(f"alex_analyze_duration_seconds_sum {sum(durations)}")
    return "\n".join(lines) + "\n"
