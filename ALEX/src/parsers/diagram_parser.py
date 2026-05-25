"""Extract state-machine hints from diagram captions and narrative (no OCR in v0.1)."""

from __future__ import annotations

import re
from typing import Any

TRANSITION_LINE_RE = re.compile(
    r"(\w+)\s*(?:→|->)\s*(\w+)",
    re.I,
)
STATE_RULE_RE = re.compile(
    r"([A-Z][A-Z0-9_]+)\s*=\s*(TRUE|FALSE|.+)",
    re.I,
)


def extract_diagram_transitions(
    paragraphs: list[str],
    source_file: str,
    *,
    image_meta: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    in_diagram_section = False

    for pi, raw in enumerate(paragraphs):
        line = raw.strip()
        low = line.lower()
        if "state transition" in low or "transition diagram" in low:
            in_diagram_section = True
            continue
        if in_diagram_section and line and line[0].isdigit() and "." in line[:4]:
            in_diagram_section = False

        src = {"file": source_file, "paragraph": pi + 1, "kind": "diagram_narrative"}

        for m in TRANSITION_LINE_RE.finditer(line):
            transitions.append(
                {
                    "id": f"SM_D_{len(transitions)+1:03d}",
                    "from_state": m.group(1).upper(),
                    "to_state": m.group(2).upper(),
                    "event": "diagram_transition",
                    "raw_condition": m.group(0),
                    "source": src,
                    "confidence": "low",
                    "review_required": True,
                    "derivation": "diagram_text",
                }
            )

        rm = STATE_RULE_RE.match(line)
        if rm and in_diagram_section:
            name = rm.group(1).upper()
            val = rm.group(2)
            to_st = "SHUT_OFF" if "TRUE" in val.upper() and "FALSE" not in val.upper() else "NORMAL"
            if "NOK" in name or "RESET" in name:
                to_st = "NORMAL"
            transitions.append(
                {
                    "id": f"SM_D_{len(transitions)+1:03d}",
                    "from_state": "NORMAL",
                    "to_state": to_st,
                    "event": name,
                    "raw_condition": line,
                    "source": src,
                    "confidence": "medium",
                    "review_required": True,
                    "derivation": "diagram_state_rule",
                }
            )

    for img in image_meta or []:
        transitions.append(
            {
                "id": f"SM_IMG_{len(transitions)+1:03d}",
                "from_state": None,
                "to_state": None,
                "event": "diagram_image",
                "raw_condition": f"Image: {img.get('file', '')} — requires engineer review (no OCR in v0.1)",
                "source": {"file": img.get("file"), "kind": "diagram_image"},
                "confidence": "low",
                "review_required": True,
                "derivation": "diagram_image_metadata",
            }
        )

    return transitions
