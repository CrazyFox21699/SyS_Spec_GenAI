"""Export/import brief for Microsoft 365 Copilot (manual workflow, no auto-upload)."""

from __future__ import annotations

import json
import re
from typing import Any

from src.engine.concrete_test_values import materialize_expected_input, materialize_expected_output
from web.knowledge_validation import compliance_snapshot


def _logic_block(bundle: dict[str, Any], logic_id: str) -> dict[str, Any] | None:
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            return lb
    return None


def build_copilot_brief(
    bundle: dict[str, Any],
    logic_id: str,
    engineer_note: str,
) -> str:
    """Markdown brief for paste into Word/Teams M365 Copilot."""
    lb = _logic_block(bundle, logic_id) or {}
    expression = str(lb.get("raw_expression") or lb.get("expression") or "")
    control = str(lb.get("name") or logic_id)
    snapshot = {r["candidate_id"]: r for r in compliance_snapshot(bundle, logic_id)}
    lines = [
        "# ALEX — M365 Copilot knowledge brief",
        "",
        f"**Logic block:** `{logic_id}` · **Control:** `{control}`",
        "",
        "## Logic expression",
        "```",
        expression[:8000],
        "```",
        "",
        "## Engineer knowledge (apply to each test case)",
        engineer_note.strip() or "(none)",
        "",
        "## Test cases",
        "",
        "| candidate_id | path | logic_comply | missing_signals | current Given | expected output |",
        "|--------------|------|--------------|-----------------|---------------|-----------------|",
    ]
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or "")
        comp = snapshot.get(cid) or {}
        path = str(trace.get("path_id") or trace.get("logic_branch") or "")
        given = materialize_expected_input(cand, bundle=bundle).replace("\n", "; ")[:200]
        out = materialize_expected_output(cand).replace("\n", "; ")[:120]
        missing = ", ".join(comp.get("missing_signals") or [])[:80]
        lines.append(
            f"| {cid} | {path} | {comp.get('logic_comply', '')} | {missing} | {given} | {out} |"
        )
    lines.extend(
        [
            "",
            "## Required JSON response",
            "",
            "Copy **only** this JSON shape back into ALEX (Import M365 response):",
            "",
            "```json",
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": "TC_PM_xxx",
                            "given": [{"signal": "SIG", "value": "0"}],
                            "note": "short reason",
                        }
                    ]
                },
                indent=2,
            ),
            "```",
            "",
            "Rules:",
            "- One value per signal per test case.",
            "- Respect MCDC path intent (do not break branch purpose).",
            "- Apply engineer knowledge (ranges, when X then Y, equalities).",
            "- Use concrete numeric/boolean values only in `given`.",
            "",
            "## Boundary-value rules (ranges)",
            "",
            "When engineer note says `SIG=100 to 200 km/h` (or similar range):",
            "- For a test case that must **satisfy** the range/guard: use an in-range value (e.g. 101, 150).",
            "- For a test case that must **fail** the upper bound: use just above max (e.g. 201 if max is 200).",
            "- For a test case that must **fail** the lower bound: use just below min (e.g. 99 if min is 100).",
            "- Split across **existing** candidate_id rows by path intent; do not invent new IDs unless asked.",
            "",
            "Example engineer constraints (interpret and map to each candidate's Given):",
            "- RESET_SHUTOFF=TRUE, req.main=TRUE",
            "- source=SRC_A && req.auth==PASS",
            "- VEHICLE_STOPPED between 100 and 200 km/h → pick 101 / 200 / 201 per pass vs fail intent",
            "- DRIVER_SAFE between 3 and 5",
            "- SAFETY_LOCKED=YES, PROCESS_IDLE=YES, PROCESS_PREPARED=PREPARED",
        ]
    )
    return "\n".join(lines)


def parse_knowledge_patches_payload(raw: str) -> list[dict[str, Any]]:
    """Parse JSON from M365 Copilot paste (fenced or raw)."""
    text = (raw or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in pasted text")
    parsed = json.loads(text[start : end + 1])
    if isinstance(parsed, list):
        return parsed
    candidates = parsed.get("candidates")
    if isinstance(candidates, list):
        return candidates
    raise ValueError("JSON must contain a candidates array")
