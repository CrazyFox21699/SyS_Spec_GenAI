"""Normalize Copilot-escaped bundle markdown and repair YAML config sections."""

from __future__ import annotations

import re
from typing import Any

import yaml

YAML_CONFIG_SECTIONS = frozenset({"signal_mapping.yaml", "api_catalog.yaml"})
_KNOWN_NESTED_FIELDS = frozenset({"setter", "getter", "assertion", "code"})
_TOP_LEVEL_DICT_KEYS = frozenset({"mappings", "terms", "apis", "allowed", "fixture"})
_TOP_SIGNAL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")
_FIELD_LINE = re.compile(r"^(setter|getter|assertion|code):\s*(.*)$", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\\?-\s+(.*)$")
_SECTION_HEAD_IN_YAML = re.compile(
    r"^(mappings|terms|apis|allowed|fixture)\s*:\s*$",
    re.IGNORECASE,
)


def normalize_copilot_markdown_bundle(text: str) -> str:
    """Unescape Copilot markdown/YAML artifacts while keeping C++ snippets intact."""
    s = str(text or "")
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")

    stripped = s.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:markdown|md|yaml|yml)?\s*\n?", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\n?```\s*$", "", stripped)

    s = stripped
    s = re.sub(r"^\\(=+)", r"\1", s, flags=re.MULTILINE)
    s = s.replace(r"\_", "_")
    s = re.sub(r"(?<![\\])\\\*", "*", s)
    s = re.sub(r"^\\-", "-", s, flags=re.MULTILINE)
    s = re.sub(r"^\\\.", ".", s, flags=re.MULTILINE)
    s = re.sub(r"\\#", "#", s)
    s = re.sub(r"\\:", ":", s)
    s = re.sub(r"\\`", "`", s)
    s = re.sub(r"\\([\[\]])", r"\1", s)
    return s.strip()


def _quote_yaml_scalar(val: str) -> str:
    v = str(val or "").strip()
    if not v:
        return '""'
    if (len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'"):
        return v
    escaped = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _is_top_level_mapping_key(line: str, *, prev_blank: bool, prev_was_field: bool) -> bool:
    st = line.strip()
    if not st or st.startswith("#"):
        return False
    if line[0] in " \t":
        return False
    if _SECTION_HEAD_IN_YAML.match(st):
        return False
    if _FIELD_LINE.match(st):
        return False
    if st.startswith("- "):
        return False
    if ":" not in st:
        return False
    key, _, rest = st.partition(":")
    key = key.strip()
    if key.lower() in _KNOWN_NESTED_FIELDS or key.lower() in _TOP_LEVEL_DICT_KEYS:
        return False
    if rest.strip():
        return False
    return bool(_TOP_SIGNAL_KEY.match(st) or (key and rest == ""))


def repair_yaml_config_section(text: str, section_name: str = "") -> tuple[str, list[str], str | None]:
    """Light repair for Copilot YAML; returns (text_for_editor, warnings, parse_error)."""
    warnings: list[str] = []
    body = normalize_copilot_markdown_bundle(text)
    if not body.strip():
        return body, warnings, None

    lines = body.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _SECTION_HEAD_IN_YAML.match(stripped):
            out.append(stripped if stripped.endswith(":") else f"{stripped}:")
            i += 1
            while i < len(lines):
                ln = lines[i]
                st = ln.strip()
                if st == "":
                    out.append("")
                    i += 1
                    continue
                if _SECTION_HEAD_IN_YAML.match(st) or _is_top_level_mapping_key(ln, prev_blank=False, prev_was_field=False):
                    break
                lm = _LIST_ITEM.match(st) or (st.startswith("- ") and re.match(r"^-\s+(.*)$", st))
                if lm:
                    item = lm.group(1) if hasattr(lm, "group") else st[2:].strip()
                    out.append(f"  - {_quote_yaml_scalar(item)}")
                    i += 1
                    continue
                if ":" in st and not ln.startswith(" "):
                    out.append(f"  {st}" if not st.startswith("-") else st)
                    i += 1
                    continue
                out.append(ln)
                i += 1
            continue

        if _is_top_level_mapping_key(line, prev_blank=not out or out[-1].strip() == "", prev_was_field=False):
            key = stripped[:-1].strip()
            out.append(f"{key}:")
            i += 1
            while i < len(lines):
                inner = lines[i]
                st = inner.strip()
                if st == "":
                    out.append("")
                    i += 1
                    if i < len(lines) and _is_top_level_mapping_key(lines[i], prev_blank=True, prev_was_field=False):
                        break
                    continue
                if _is_top_level_mapping_key(inner, prev_blank=False, prev_was_field=False):
                    break
                if _SECTION_HEAD_IN_YAML.match(st):
                    break
                fm = _FIELD_LINE.match(st)
                if fm:
                    field = fm.group(1).lower()
                    val = fm.group(2).strip()
                    if val:
                        out.append(f"  {field}: {_quote_yaml_scalar(val)}")
                        i += 1
                    else:
                        out.append(f"  {field}:")
                        i += 1
                        while i < len(lines):
                            li = lines[i]
                            lst = li.strip()
                            if lst == "":
                                break
                            if _is_top_level_mapping_key(lines[i], prev_blank=False, prev_was_field=True):
                                break
                            if _FIELD_LINE.match(lst):
                                break
                            mli = _LIST_ITEM.match(lst)
                            if mli:
                                out.append(f"    - {_quote_yaml_scalar(mli.group(1))}")
                                i += 1
                                continue
                            if lst.startswith("- "):
                                out.append(f"    - {_quote_yaml_scalar(lst[2:].strip())}")
                                i += 1
                                continue
                            break
                    continue
                if st.startswith("* "):
                    out.append(f"  - {_quote_yaml_scalar(st[2:].strip())}")
                    i += 1
                    continue
                if st.startswith("- "):
                    out.append(f"  - {_quote_yaml_scalar(st[2:].strip())}")
                    i += 1
                    continue
                mli = _LIST_ITEM.match(st)
                if mli:
                    out.append(f"  - {_quote_yaml_scalar(mli.group(1))}")
                    i += 1
                    continue
                if ":" in st and not inner.startswith(" "):
                    parts = st.split(":", 1)
                    out.append(f"  {parts[0].strip()}: {_quote_yaml_scalar(parts[1])}")
                    i += 1
                    continue
                out.append(inner)
                i += 1
            continue

        fm = _FIELD_LINE.match(stripped)
        if fm and not line.startswith(" "):
            field = fm.group(1).lower()
            val = fm.group(2).strip()
            out.append(f"{field}: {_quote_yaml_scalar(val)}" if val else f"{field}:")
            i += 1
            continue

        out.append(line)
        i += 1

    repaired = "\n".join(out).strip()
    if repaired and not repaired.endswith("\n"):
        repaired += "\n"

    parse_error: str | None = None
    try:
        data = yaml.safe_load(repaired or "{}")
        if data is None:
            data = {}
        if not isinstance(data, dict) and section_name == "api_catalog.yaml":
            warnings.append("api_catalog.yaml: expected mapping root; kept repaired text.")
        elif not isinstance(data, dict) and section_name == "signal_mapping.yaml":
            warnings.append("signal_mapping.yaml: expected mapping root; kept repaired text.")
    except yaml.YAMLError as exc:
        parse_error = str(exc)
        warnings.append(
            f"YAML parse failed for {section_name or 'section'}, imported as raw text. "
            "Mapping coverage may not work until YAML is fixed."
        )
        repaired = body if body else repaired

    if repaired != body:
        warnings.append(f"{section_name or 'YAML'}: indentation/quotes repaired for import.")

    return repaired, warnings, parse_error


def process_yaml_section_content(text: str, section_name: str) -> dict[str, Any]:
    """Process a YAML section for bundle import."""
    repaired, warns, err = repair_yaml_config_section(text, section_name)
    return {
        "content": repaired,
        "warnings": warns,
        "yaml_error": err,
        "parse_ok": err is None,
    }
