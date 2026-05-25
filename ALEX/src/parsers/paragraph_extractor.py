"""Extract definitions, footnotes, code-style defs, and state rules from Word paragraphs."""

from __future__ import annotations

import re
from typing import Any

from src.engine.footnote_conditional import extract_footnote_lines_from_paragraphs, parse_conditional_footnote

FOOTNOTE_MARK_RE = re.compile(r"\(\*(\d+)\)")
FOOTNOTE_LINE_RE = re.compile(r"^\(\*(\d+)\)\s+(.+)$", re.I)
_CROSS_REF_FILENAME_RE = re.compile(r"([A-Za-z0-9_\-]+\.(?:docx|xlsx|xlsm|xls|pdf|csv|md|txt))", re.I)
_CROSS_REF_SHEET_RE = re.compile(
    r"(?:see|refer(?:\s+to)?|in|on)\s+sheet\s+[\"']?([A-Za-z][A-Za-z0-9_\-]{2,})[\"']?",
    re.I,
)
_CROSS_REF_REFER_RE = re.compile(
    r"refer(?:\s+to)?\s+(?:logic|lower|upper|condition)?\s*([A-Za-z][A-Za-z0-9_\- ]{2,})",
    re.I,
)


def _extract_cross_refs(text: str) -> list[dict[str, Any]]:
    """Detect file/sheet/refer-to stubs in a paragraph or footnote body."""
    if not text:
        return []
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, value: str) -> None:
        value = value.strip().strip(".,;:")
        if not value or len(value) < 3:
            return
        key = (kind, value.lower())
        if key in seen:
            return
        seen.add(key)
        refs.append({"type": kind, "text": value, "resolved_file": None, "resolved_node": None})

    for match in _CROSS_REF_FILENAME_RE.finditer(text):
        _add("file", match.group(1))
    for match in _CROSS_REF_SHEET_RE.finditer(text):
        _add("sheet", match.group(1))
    for match in _CROSS_REF_REFER_RE.finditer(text):
        candidate = match.group(1).strip()
        # Avoid duplicating filenames already captured above.
        if not any(candidate.lower() in r["text"].lower() for r in refs):
            _add("condition_group", candidate)
    return refs
CODE_DEF_LINE_RE = re.compile(
    r"^([A-Z][A-Z0-9_]+)\s*:\s*(.+)$",
)
WORD_DEF_LINE_RE = re.compile(
    r"^([A-Z][A-Z0-9_]+)\s*:\s*(.+)$",
)
STATE_RULE_RE = re.compile(
    r"^([A-Z][A-Z0-9_]+)\s*=\s*(.+)$",
    re.I,
)
GROUP_HEADER_RE = re.compile(
    r"^(\d*)([A-Z][A-Z0-9_]+)\s+Definition\s*$",
    re.I,
)


def extract_from_paragraphs(paragraphs: list[str], source_file: str) -> dict[str, Any]:
    """Parse paragraph list into structured definitions and transitions."""
    condition_definitions: list[dict[str, Any]] = []
    footnote_definitions: list[dict[str, Any]] = []
    code_definitions: list[dict[str, Any]] = []
    state_rules: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    footnote_map: dict[str, str] = {}
    footnote_map.update(extract_footnote_lines_from_paragraphs(paragraphs))
    current_group: str | None = None
    in_definition_block = False

    for pi, raw in enumerate(paragraphs):
        line = raw.strip()
        if not line:
            in_definition_block = False
            continue

        src = {"file": source_file, "paragraph": pi + 1, "kind": "paragraph"}

        fn_line = FOOTNOTE_LINE_RE.match(line)
        if fn_line:
            ref = f"(*{fn_line.group(1)})"
            body = fn_line.group(2).strip()
            footnote_map[ref] = body
            parsed_cond = parse_conditional_footnote(body)
            footnote_definitions.append(
                {
                    "ref": ref,
                    "footnote_num": fn_line.group(1),
                    "definition": body,
                    "raw_text": body,
                    "parsed_conditional": parsed_cond,
                    "source": {**src, "kind": "footnote_paragraph"},
                    "review_required": parsed_cond is None,
                    "cross_refs": _extract_cross_refs(body),
                }
            )
            continue

        gm = GROUP_HEADER_RE.match(line)
        if gm:
            current_group = gm.group(2)
            in_definition_block = True
            condition_definitions.append(
                {
                    "name": current_group,
                    "definition": f"Composite condition group (members defined below)",
                    "group": current_group,
                    "source": {**src, "kind": "group_header"},
                }
            )
            continue

        if line.lower().startswith("refer ") or line.lower().startswith("refer logic"):
            in_definition_block = True
            continue

        if "state transition" in line.lower():
            in_definition_block = False
            current_group = None
            continue

        cm = CODE_DEF_LINE_RE.match(line)
        if cm and ("==" in line or "&&" in line or ">=" in line or ".main" in line):
            name = cm.group(1).strip()
            body = cm.group(2).strip()
            code_definitions.append(
                {
                    "name": name,
                    "definition": body,
                    "group": current_group,
                    "source": {**src, "kind": "code_definition"},
                    "review_required": False,
                }
            )
            condition_definitions.append(
                {
                    "name": name,
                    "definition": body,
                    "group": current_group,
                    "source": {**src, "kind": "code_definition"},
                }
            )
            for fn in FOOTNOTE_MARK_RE.findall(name):
                footnote_map[f"(*{fn})"] = body
            continue

        wm = WORD_DEF_LINE_RE.match(line)
        if wm and "==" not in line:
            name = wm.group(1).strip()
            body = wm.group(2).strip()
            if name not in {d["name"] for d in condition_definitions}:
                condition_definitions.append(
                    {
                        "name": name,
                        "definition": body,
                        "group": current_group,
                        "source": {**src, "kind": "word_definition"},
                    }
                )
            continue

        sm = STATE_RULE_RE.match(line)
        if sm and ("TRUE" in line.upper() or "FALSE" in line.upper() or " or " in line.lower()):
            name = sm.group(1).strip().upper()
            expr = sm.group(2).strip()
            state_rules.append(
                {
                    "name": name,
                    "expression": expr,
                    "source": {**src, "kind": "state_rule"},
                }
            )
            transitions.append(
                {
                    "id": f"SM_P_{len(transitions)+1:03d}",
                    "from_state": None,
                    "to_state": None,
                    "event": name,
                    "raw_condition": f"{name} = {expr}",
                    "source": src,
                    "confidence": "low",
                    "review_required": True,
                    "derivation": "paragraph_state_rule",
                    "parser_reason": "State rule from paragraph; states must be confirmed in review.",
                }
            )
            continue

    return {
        "condition_definitions": condition_definitions,
        "footnote_definitions": footnote_definitions,
        "code_definitions": code_definitions,
        "state_rules": state_rules,
        "transitions": transitions,
        "footnote_map": footnote_map,
    }


def link_footnotes(
    footnote_refs: list[dict[str, Any]],
    footnote_map: dict[str, str],
    condition_definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach definition text to footnote refs from paragraph map and condition names."""
    def_by_name: dict[str, str] = {}
    for d in condition_definitions:
        nm = str(d.get("name", "")).strip()
        if nm:
            def_by_name[nm] = d.get("definition", "")
            stripped = FOOTNOTE_MARK_RE.sub("", nm).strip()
            if stripped:
                def_by_name[stripped] = d.get("definition", "")
    logic_ops = frozenset({"AND", "OR", "NOT"})
    out: list[dict[str, Any]] = []
    for ref in footnote_refs:
        key = ref.get("ref", "")
        definition = footnote_map.get(key)
        cond_name = (ref.get("condition_name") or "").strip()
        if not definition and cond_name:
            definition = def_by_name.get(cond_name)
        if not definition and ref.get("raw_text"):
            for m in re.finditer(r"([A-Z][A-Z0-9_]+)", ref.get("raw_text", "")):
                name = m.group(1)
                if name in logic_ops:
                    continue
                if name in def_by_name:
                    definition = def_by_name[name]
                    break
        body_for_refs = definition or ref.get("raw_text") or ""
        existing_refs = ref.get("cross_refs") or []
        merged_cross_refs = list(existing_refs)
        if not merged_cross_refs:
            merged_cross_refs = _extract_cross_refs(body_for_refs)
        out.append(
            {
                **ref,
                "definition": definition,
                "review_required": definition is None,
                "cross_refs": merged_cross_refs,
            }
        )
    return out
