"""Parse Copilot-style and legacy project code config YAML."""

from __future__ import annotations

import fnmatch
import re
from typing import Any

import yaml

SIGNAL_RESERVED_KEYS = frozenset(
    {"mappings", "terms", "aliases", "metadata", "version", "notes", "alias"}
)
SIGNAL_ENTRY_FIELDS = frozenset({"setter", "getter", "assertion", "code"})
_API_SECTION_KEYS = frozenset(
    {
        "fixture",
        "core",
        "setters",
        "getter",
        "getters",
        "assertions",
        "timing",
        "mocks",
        "utilities",
        "apis",
        "allowed",
    }
)
_API_NOISE_WORDS = frozenset(
    {
        "for",
        "loop",
        "with",
        "expr",
        "value",
        "direct",
        "variables",
        "variable",
        "and",
        "or",
        "the",
        "a",
        "an",
    }
)
_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_WILDCARD_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_*]*\*[A-Za-z0-9_*]*)\b")
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")


def _normalize_yaml_text(text: str) -> str:
    s = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return s.replace(r"\_", "_")


def _yaml_load_status(text: str) -> tuple[Any, str, str | None]:
    body = _normalize_yaml_text(text)
    if not body.strip():
        return {}, "OK", None
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        return {}, "ERROR", str(exc)
    if data is None:
        return {}, "OK", None
    if not isinstance(data, dict):
        return {}, "WARNING", "YAML root is not a mapping"
    return data, "OK", None


def _coerce_snippet_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _signal_entry_to_code(entry: Any) -> str:
    if entry is None:
        return ""
    if isinstance(entry, str):
        return entry.strip()
    if not isinstance(entry, dict):
        return str(entry).strip()
    parts: list[str] = []
    for field in ("setter", "getter", "assertion", "code"):
        if field not in entry:
            continue
        val = entry[field]
        parts.extend(_coerce_snippet_list(val))
    if not parts:
        for k, v in entry.items():
            if str(k).lower() in SIGNAL_ENTRY_FIELDS:
                continue
            parts.extend(_coerce_snippet_list(v))
    return "\n".join(parts).strip()


def _value_to_flat_string(value: Any) -> str:
    if isinstance(value, dict):
        return _signal_entry_to_code(value)
    if isinstance(value, list):
        return "\n".join(_coerce_snippet_list(value))
    return str(value or "").strip()


def _extract_top_level_blocks(text: str) -> dict[str, str]:
    """Fallback when YAML is invalid: split on top-level SIGNAL: lines."""
    body = _normalize_yaml_text(text)
    blocks: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        m = _TOP_LEVEL_KEY_RE.match(stripped)
        if m:
            key = m.group(1)
            if key.lower() in SIGNAL_RESERVED_KEYS:
                continue
            if current_key:
                blocks[current_key] = "\n".join(current_lines).strip()
            current_key = key
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)
    if current_key:
        blocks[current_key] = "\n".join(current_lines).strip()
    return blocks


def parse_signal_mapping_yaml(text: str) -> dict[str, Any]:
    """Parse signal_mapping.yaml (legacy mappings/terms + Copilot top-level signals)."""
    body = _normalize_yaml_text(text)
    data, yaml_status, yaml_error = _yaml_load_status(body)
    mappings: dict[str, Any] = dict(data.get("mappings") or {}) if isinstance(data, dict) else {}
    terms: dict[str, Any] = dict(data.get("terms") or {}) if isinstance(data, dict) else {}
    signals: dict[str, Any] = {}
    aliases: dict[str, str] = dict(data.get("aliases") or {}) if isinstance(data, dict) else {}
    top_level = False
    reserved_schema = bool(mappings or terms or aliases)
    used_fallback = False

    if isinstance(data, dict):
        for key, value in data.items():
            k = str(key).strip()
            if not k or k.lower() in SIGNAL_RESERVED_KEYS:
                continue
            signals[k] = value
            top_level = True

    if yaml_status == "ERROR" or (not signals and not mappings and not terms):
        for key, block in _extract_top_level_blocks(body).items():
            if key not in signals:
                signals[key] = block
                top_level = True
                used_fallback = True
        if used_fallback and yaml_status == "ERROR":
            yaml_status = "WARNING"

    return {
        "mappings": mappings,
        "terms": terms,
        "signals": signals,
        "aliases": aliases,
        "format": {
            "top_level": top_level,
            "reserved_schema": reserved_schema,
            "fallback_line_parser": used_fallback,
        },
        "keys": sorted(set(mappings) | set(terms) | set(signals) | set(aliases)),
        "yaml_status": yaml_status,
        "yaml_error": yaml_error,
    }


def flatten_signal_mapping(parsed: dict[str, Any] | None) -> dict[str, str]:
    """Flat term/signal -> code snippet for engine variable_map and legacy merge."""
    parsed = parsed or {}
    out: dict[str, str] = {}
    for key, value in (parsed.get("mappings") or {}).items():
        k = str(key).strip()
        if k:
            out[k] = _value_to_flat_string(value)
    for key, value in (parsed.get("terms") or {}).items():
        k = str(key).strip()
        if k:
            out[k] = _value_to_flat_string(value)
    for key, value in (parsed.get("signals") or {}).items():
        k = str(key).strip()
        if k and k not in out:
            out[k] = _signal_entry_to_code(value)
    for alias, target in (parsed.get("aliases") or {}).items():
        a = str(alias).strip()
        t = str(target).strip()
        if not a:
            continue
        if t in out:
            out[a] = out[t]
        elif t in (parsed.get("signals") or {}):
            out[a] = _signal_entry_to_code((parsed.get("signals") or {})[t])
        else:
            out[a] = t
    return {k: v for k, v in out.items() if v}


def signal_mapping_content_blob(parsed: dict[str, Any] | None) -> dict[str, str]:
    """Searchable text per canonical key (for content-match coverage)."""
    parsed = parsed or {}
    blobs: dict[str, str] = {}
    flat = flatten_signal_mapping(parsed)
    for key, text in flat.items():
        blobs[key] = text
    for key, entry in (parsed.get("signals") or {}).items():
        k = str(key).strip()
        if k:
            blobs.setdefault(k, _signal_entry_to_code(entry))
    for key, entry in (parsed.get("mappings") or {}).items():
        k = str(key).strip()
        if k:
            blobs.setdefault(k, _signal_entry_to_code(entry))
    return blobs


def _extract_api_tokens_from_string(text: str) -> tuple[set[str], list[str]]:
    literals: set[str] = set()
    wildcards: list[str] = []
    s = str(text or "").strip()
    if not s:
        return literals, wildcards
    for m in _WILDCARD_TOKEN_RE.finditer(s):
        wildcards.append(m.group(1))
    if "*" in s and s not in wildcards:
        wildcards.append(s)
    for m in _IDENT_RE.finditer(s):
        tok = m.group(1)
        if "*" in tok:
            if tok not in wildcards:
                wildcards.append(tok)
            continue
        if tok.lower() in _API_NOISE_WORDS:
            continue
        if len(tok) <= 1:
            continue
        literals.add(tok)
    return literals, wildcards


def _collect_api_from_value(value: Any, literals: set[str], wildcards: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_api_from_value(item, literals, wildcards)
        return
    if isinstance(value, dict):
        for v in value.values():
            _collect_api_from_value(v, literals, wildcards)
        return
    lit, wc = _extract_api_tokens_from_string(str(value or ""))
    literals |= lit
    for w in wc:
        if w not in wildcards:
            wildcards.append(w)


def parse_api_catalog_full(text: str) -> dict[str, Any]:
    """Parse api_catalog.yaml (apis/allowed list + Copilot section lists)."""
    data, yaml_status, yaml_error = _yaml_load_status(text)
    literals: set[str] = set()
    wildcards: list[str] = []
    section_format = False
    list_format = False

    if isinstance(data, dict):
        for key, value in data.items():
            k = str(key).lower()
            if k in ("apis", "allowed"):
                list_format = True
                _collect_api_from_value(value, literals, wildcards)
            elif k in _API_SECTION_KEYS or k not in ("metadata", "version", "notes"):
                section_format = True
                _collect_api_from_value(value, literals, wildcards)

    return {
        "apis": literals,
        "wildcards": wildcards,
        "yaml_status": yaml_status,
        "yaml_error": yaml_error,
        "format": {
            "section": section_format,
            "list": list_format,
        },
        "entries_count": len(literals) + len(wildcards),
    }


def parse_api_catalog_yaml(text: str) -> set[str]:
    """Backward-compatible: literal API names only (no wildcards in set)."""
    full = parse_api_catalog_full(text)
    return set(full.get("apis") or [])


def api_matches_catalog(api_name: str, catalog: dict[str, Any] | None) -> bool:
    """True if api_name is allowed by literals or wildcard patterns."""
    name = str(api_name or "").strip()
    if not name:
        return True
    if name.startswith("EXPECT") or name.startswith("ASSERT"):
        return True
    catalog = catalog or {}
    literals = set(catalog.get("apis") or [])
    if name in literals:
        return True
    for pat in catalog.get("wildcards") or []:
        if fnmatch.fnmatch(name, str(pat)):
            return True
    return False


def build_mapping_match_index(
    gtest_state: dict[str, Any],
    config_files: dict[str, Any],
) -> dict[str, Any]:
    """Index for coverage: keys, aliases, content, code_variable_map."""
    sm = config_files.get("signal_mapping.yaml") or {}
    parsed = parse_signal_mapping_yaml(str(sm.get("content") or ""))
    flat = flatten_signal_mapping(parsed)
    blobs = signal_mapping_content_blob(parsed)
    vmap = dict(gtest_state.get("code_variable_map") or {})

    exact_keys: dict[str, str] = {}
    lower_keys: dict[str, str] = {}
    for key in set(parsed.get("keys") or []) | set(flat) | set(vmap):
        k = str(key).strip()
        if not k:
            continue
        exact_keys[k] = k
        lower_keys[k.lower()] = k

    alias_to_key: dict[str, str] = {}
    for alias, target in (parsed.get("aliases") or {}).items():
        a = str(alias).strip()
        t = str(target).strip()
        canon = exact_keys.get(t) or lower_keys.get(t.lower()) or t
        if a:
            alias_to_key[a] = canon
            alias_to_key[a.lower()] = canon

    return {
        "parsed": parsed,
        "flat": flat,
        "blobs": blobs,
        "vmap": vmap,
        "exact_keys": exact_keys,
        "lower_keys": lower_keys,
        "alias_to_key": alias_to_key,
        "detected_mapping_count": len(
            set(parsed.get("keys") or []) | set(flat.keys()) | set(vmap.keys())
        ),
    }


def resolve_signal_mapping_match(sig: str, index: dict[str, Any]) -> dict[str, Any] | None:
    """Return match info or None. Exact match wins over case-insensitive."""
    s = str(sig or "").strip()
    if not s:
        return None

    exact_keys = index.get("exact_keys") or {}
    lower_keys = index.get("lower_keys") or {}
    alias_to_key = index.get("alias_to_key") or {}
    flat = index.get("flat") or {}
    blobs = index.get("blobs") or {}
    vmap = index.get("vmap") or {}

    if s in exact_keys:
        return {"term": s, "source": "mapping_key", "canonical": s}
    if s in vmap:
        return {"term": s, "source": "code_variable_map", "canonical": s}
    if s in alias_to_key:
        c = alias_to_key[s]
        return {"term": s, "source": "alias", "canonical": c}
    if s.lower() in lower_keys:
        c = lower_keys[s.lower()]
        return {"term": s, "source": "mapping_key", "canonical": c, "case_insensitive": True}
    if s.lower() in alias_to_key:
        c = alias_to_key[s.lower()]
        return {"term": s, "source": "alias", "canonical": c, "case_insensitive": True}

    for key, blob in blobs.items():
        if s in blob or s.lower() in blob.lower():
            return {"term": s, "source": "content_match", "canonical": key}
    for key, val in flat.items():
        if s in val or s.lower() in val.lower():
            return {"term": s, "source": "content_match", "canonical": key}
    for key, val in vmap.items():
        if s in val or s.lower() in val.lower():
            return {"term": s, "source": "code_variable_map", "canonical": key}

    return None


def diagnose_project_code_config(
    signal_mapping_text: str,
    api_catalog_text: str,
) -> dict[str, Any]:
    sm = parse_signal_mapping_yaml(signal_mapping_text)
    api = parse_api_catalog_full(api_catalog_text)
    sm_status = sm.get("yaml_status") or "OK"
    api_status = api.get("yaml_status") or "OK"
    if sm_status == "ERROR" or api_status == "ERROR":
        overall = "ERROR"
    elif sm_status == "WARNING" or api_status == "WARNING":
        overall = "WARNING"
    else:
        overall = "OK"
    return {
        "ok": overall != "ERROR",
        "yaml_parse_status": overall,
        "signal_mapping": {
            "keys_detected": len(sm.get("keys") or []),
            "top_level_format": bool((sm.get("format") or {}).get("top_level")),
            "reserved_schema_format": bool((sm.get("format") or {}).get("reserved_schema")),
            "yaml_status": sm_status,
            "yaml_error": sm.get("yaml_error"),
        },
        "api_catalog": {
            "entries_detected": api.get("entries_count") or 0,
            "literal_apis": len(api.get("apis") or []),
            "wildcard_apis": len(api.get("wildcards") or []),
            "wildcards": list(api.get("wildcards") or [])[:20],
            "section_format": bool((api.get("format") or {}).get("section")),
            "list_format": bool((api.get("format") or {}).get("list")),
            "yaml_status": api_status,
            "yaml_error": api.get("yaml_error"),
        },
    }
