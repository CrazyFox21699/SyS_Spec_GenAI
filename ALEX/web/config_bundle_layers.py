"""Layered project code config: baseline + overrides + learned → effective files."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from web.config_bundle_copilot import normalize_copilot_markdown_bundle
from web.project_code_config import (
    CONFIG_FILES,
    CONFIG_DIR_NAME,
    list_config_filenames,
    parse_api_catalog_yaml,
    parse_signal_mapping_yaml,
    project_code_config_dir,
)

LAYERS_DIR = "layers"
BASELINE_DIR = "baseline"
OVERRIDES_DIR = "project_overrides"
LEARNED_RULES_FILE = "learned_rules.md"
LEARNED_MAPPINGS_FILE = "learned_mappings.yaml"
VERSIONS_FILE = "config_versions.json"
PENDING_FILE = "pending_bundle_proposal.json"

BUNDLE_MARKDOWN_NAME = "alex_code_config_bundle.md"

SOURCE_BUNDLE_IMPORT = "BUNDLE_IMPORT"
SOURCE_MANUAL_EDIT = "MANUAL_EDIT"
SOURCE_LEARNED_RULE = "LEARNED_RULE"
SOURCE_CHANGE_REQUEST = "CHANGE_REQUEST"
SOURCE_AI_SUGGESTION = "AI_SUGGESTION"

MARKDOWN_CONFIG_FILES = ("code_rules.md", "gtest_template.md", "ai_review_pack.md")
YAML_CONFIG_FILES = ("signal_mapping.yaml", "api_catalog.yaml")

EXPECTED_SECTIONS: tuple[str, ...] = tuple(n for n in CONFIG_FILES.keys() if n != "project_instruction.md")

_CONFIG_NAME_ALT = "|".join(re.escape(n) for n in EXPECTED_SECTIONS)
# ## code_rules.md | ## 1. code_rules.md | ### code_rules.md | # code_rules.md | optional **bold**
_SECTION_HEAD_RE = re.compile(
    rf"^#{{1,3}}\s*(?:\d+[\).\s]+)?\*{{0,2}}(?P<name>{_CONFIG_NAME_ALT})\*{{0,2}}\s*:?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_NUMBERED_SECTION_RE = re.compile(
    rf"^\s*\d+\.\s+\*{{0,2}}(?P<name>{_CONFIG_NAME_ALT})\*{{0,2}}\s*:?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_IMPORT_YAML_NOTE = (
    "YAML validation is not performed during import. "
    "Use Check Mapping Coverage or Generate Local from Template after fixing syntax."
)
_FENCE_FILE_RE = re.compile(
    rf"^```(?:yaml|yml|md|markdown)?\s*(?P<name>{_CONFIG_NAME_ALT})\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_START_MARKER_PATTERNS = (
    "ALEX_CODE_CONFIG_BUNDLE_START",
    "ALEX_CONFIG_BUNDLE_START",
    "alex_code_config_bundle_start",
    "<!-- ALEX_CONFIG_BUNDLE_START",
    "--- ALEX_CONFIG_BUNDLE_START",
    "BEGIN ALEX CODE CONFIG BUNDLE",
)
_END_MARKER_PATTERNS = (
    "ALEX_CODE_CONFIG_BUNDLE_END",
    "ALEX_CONFIG_BUNDLE_END",
    "alex_code_config_bundle_end",
    "<!-- ALEX_CONFIG_BUNDLE_END",
    "--- ALEX_CONFIG_BUNDLE_END",
    "END ALEX CODE CONFIG BUNDLE",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_version_id() -> str:
    return f"cv_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _layers_root(job_output: Path) -> Path:
    return project_code_config_dir(job_output) / LAYERS_DIR


def _baseline_dir(job_output: Path) -> Path:
    return _layers_root(job_output) / BASELINE_DIR


def _overrides_dir(job_output: Path) -> Path:
    return _layers_root(job_output) / OVERRIDES_DIR


def _read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def ensure_config_layers(job_output: Path) -> None:
    """Migrate flat effective files into baseline if layers are empty."""
    root = project_code_config_dir(job_output)
    root.mkdir(parents=True, exist_ok=True)
    baseline = _baseline_dir(job_output)
    baseline.mkdir(parents=True, exist_ok=True)
    _overrides_dir(job_output).mkdir(parents=True, exist_ok=True)

    has_baseline = any((baseline / name).exists() for name in list_config_filenames())
    if not has_baseline:
        from web.project_code_config import load_global_instruction
        global_instruction = load_global_instruction()
        for name in list_config_filenames():
            flat = root / name
            dest = baseline / name
            if flat.exists():
                dest.write_text(flat.read_text(encoding="utf-8"), encoding="utf-8")
            elif name == "project_instruction.md" and global_instruction:
                # Use global instruction as baseline for new jobs
                dest.write_text(global_instruction, encoding="utf-8")
            elif name in CONFIG_FILES:
                dest.write_text(CONFIG_FILES[name]["default"], encoding="utf-8")

    learned = root / LEARNED_RULES_FILE
    if not learned.exists():
        learned.write_text("# Learned rules\n\n## Rules\n\n## Notes\n", encoding="utf-8")

    lm = root / LEARNED_MAPPINGS_FILE
    if not lm.exists():
        lm.write_text("mappings: {}\nterms: {}\n", encoding="utf-8")

    versions_path = root / VERSIONS_FILE
    if not versions_path.exists():
        versions_path.write_text(json.dumps({"versions": [], "current_version_id": None}, indent=2), encoding="utf-8")


def _load_versions(job_output: Path) -> dict[str, Any]:
    ensure_config_layers(job_output)
    path = project_code_config_dir(job_output) / VERSIONS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("versions", [])
    return data


def _save_versions(job_output: Path, data: dict[str, Any]) -> None:
    _write_text(project_code_config_dir(job_output) / VERSIONS_FILE, json.dumps(data, indent=2))


def _layer_text(job_output: Path, layer: str, filename: str) -> str:
    if layer == "baseline":
        return _read_text(_baseline_dir(job_output) / filename)
    if layer == "project_overrides":
        return _read_text(_overrides_dir(job_output) / filename)
    if layer == "learned_rules" and filename in MARKDOWN_CONFIG_FILES:
        if filename == "code_rules.md":
            return _read_text(project_code_config_dir(job_output) / LEARNED_RULES_FILE)
        return ""
    return ""


def _merge_signal_mapping(job_output: Path) -> str:
    from web.config_yaml_parsers import flatten_signal_mapping

    base = parse_signal_mapping_yaml(_layer_text(job_output, "baseline", "signal_mapping.yaml"))
    over = parse_signal_mapping_yaml(_layer_text(job_output, "project_overrides", "signal_mapping.yaml"))
    learned = parse_signal_mapping_yaml(_read_text(project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE))
    flat: dict[str, str] = {}
    for block in (base, learned, over):
        flat.update(flatten_signal_mapping(block))
    return yaml.safe_dump({"mappings": flat, "terms": {}}, sort_keys=False, allow_unicode=True)


def _merge_api_catalog(job_output: Path) -> str:
    apis: set[str] = set()
    for layer in ("baseline", "project_overrides"):
        text = _layer_text(job_output, layer, "api_catalog.yaml")
        apis |= parse_api_catalog_yaml(text)
    learned = parse_api_catalog_yaml(_read_text(project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE))
    apis |= learned
    return yaml.safe_dump({"apis": sorted(apis)}, sort_keys=False, allow_unicode=True)


def _merge_markdown_file(job_output: Path, filename: str) -> str:
    parts: list[str] = []
    for layer in ("baseline", "project_overrides"):
        chunk = _layer_text(job_output, layer, filename).strip()
        if chunk:
            parts.append(chunk)
    if filename == "code_rules.md":
        learned = _read_text(project_code_config_dir(job_output) / LEARNED_RULES_FILE).strip()
        if learned and learned != "# Learned rules":
            parts.append(f"\n\n<!-- learned_rules -->\n\n{learned}")
    return "\n\n".join(parts).strip() + ("\n" if parts else "")


def build_effective_config(job_output: Path) -> dict[str, str]:
    ensure_config_layers(job_output)
    effective: dict[str, str] = {}
    for name in list_config_filenames():
        if name == "signal_mapping.yaml":
            effective[name] = _merge_signal_mapping(job_output)
        elif name == "api_catalog.yaml":
            effective[name] = _merge_api_catalog(job_output)
        elif name in MARKDOWN_CONFIG_FILES:
            effective[name] = _merge_markdown_file(job_output, name)
        else:
            effective[name] = _merge_markdown_file(job_output, name)
    return effective


def write_effective_config_files(job_output: Path) -> dict[str, str]:
    """Rebuild flat effective files used by generation/cache."""
    effective = build_effective_config(job_output)
    root = project_code_config_dir(job_output)
    for name, content in effective.items():
        _write_text(root / name, content)
    return effective


def get_layers_meta(job_output: Path) -> dict[str, Any]:
    versions = _load_versions(job_output)
    current_id = versions.get("current_version_id")
    current = next((v for v in versions.get("versions") or [] if v.get("config_version_id") == current_id), None)
    pending_path = project_code_config_dir(job_output) / PENDING_FILE
    pending = None
    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pending = None
    return {
        "layers": {
            "baseline_config": str(_baseline_dir(job_output)),
            "project_overrides": str(_overrides_dir(job_output)),
            "learned_rules": str(project_code_config_dir(job_output) / LEARNED_RULES_FILE),
            "learned_mappings": str(project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE),
        },
        "current_version_id": current_id,
        "current_version": current,
        "versions": (versions.get("versions") or [])[-20:],
        "pending_proposal": pending is not None,
    }


def load_layered_project_code_config(job_output: Path) -> dict[str, Any]:
    ensure_config_layers(job_output)
    effective = write_effective_config_files(job_output)
    files: dict[str, Any] = {}
    root = project_code_config_dir(job_output)
    for name, meta in CONFIG_FILES.items():
        override_raw = _read_text(_overrides_dir(job_output) / name).strip()
        if override_raw:
            content = override_raw + ("\n" if not override_raw.endswith("\n") else "")
        else:
            content = effective.get(name) or _read_text(root / name, meta["default"])
        files[name] = {
            "name": name,
            "description": meta["description"],
            "content": content,
            "path": str(root / name),
            "exists": True,
        }
    meta = get_layers_meta(job_output)
    return {"ok": True, "config_dir": str(root), "files": files, **meta}


def record_config_version(
    job_output: Path,
    *,
    source: str,
    changed_sections: list[str],
    summary: str,
    changes: list[dict[str, Any]],
    layer_snapshots: dict[str, Any],
) -> dict[str, Any]:
    versions_data = _load_versions(job_output)
    vid = _new_version_id()
    entry = {
        "config_version_id": vid,
        "timestamp": _now_iso(),
        "source": source,
        "changed_sections": changed_sections,
        "summary": summary,
        "changes": changes[:50],
        "layer_snapshots": layer_snapshots,
    }
    versions_data.setdefault("versions", []).append(entry)
    versions_data["versions"] = versions_data["versions"][-50:]
    versions_data["current_version_id"] = vid
    _save_versions(job_output, versions_data)
    return entry


def _capture_layer_snapshots(job_output: Path, filenames: list[str]) -> dict[str, Any]:
    snap: dict[str, Any] = {"baseline": {}, "project_overrides": {}, "learned_rules": "", "learned_mappings": ""}
    for name in filenames:
        snap["baseline"][name] = _read_text(_baseline_dir(job_output) / name)
        snap["project_overrides"][name] = _read_text(_overrides_dir(job_output) / name)
    snap["learned_rules"] = _read_text(project_code_config_dir(job_output) / LEARNED_RULES_FILE)
    snap["learned_mappings"] = _read_text(project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE)
    return snap


def rollback_config_version(job_output: Path, config_version_id: str) -> dict[str, Any]:
    versions_data = _load_versions(job_output)
    entry = next(
        (v for v in versions_data.get("versions") or [] if v.get("config_version_id") == config_version_id),
        None,
    )
    if not entry:
        return {"ok": False, "error": f"Version not found: {config_version_id}"}
    snap = entry.get("layer_snapshots") or {}
    for name, content in (snap.get("baseline") or {}).items():
        _write_text(_baseline_dir(job_output) / name, str(content or ""))
    for name, content in (snap.get("project_overrides") or {}).items():
        path = _overrides_dir(job_output) / name
        if content:
            _write_text(path, str(content))
        elif path.exists():
            path.unlink()
    if "learned_rules" in snap:
        _write_text(project_code_config_dir(job_output) / LEARNED_RULES_FILE, str(snap.get("learned_rules") or ""))
    if "learned_mappings" in snap:
        _write_text(project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE, str(snap.get("learned_mappings") or ""))
    write_effective_config_files(job_output)
    record_config_version(
        job_output,
        source=SOURCE_MANUAL_EDIT,
        changed_sections=list((snap.get("project_overrides") or {}).keys()),
        summary=f"Rollback to {config_version_id}",
        changes=[{"action": "rollback", "config_version_id": config_version_id}],
        layer_snapshots=_capture_layer_snapshots(job_output, list_config_filenames()),
    )
    return {"ok": True, "rolled_back_to": config_version_id}


def _normalize_config_filename(name: str) -> str:
    n = str(name or "").strip().lower()
    if n in CONFIG_FILES:
        return n
    for key in CONFIG_FILES:
        if n == key.replace(".md", "").replace(".yaml", ""):
            return key
    return n


def _strip_fence_wrapper(chunk: str) -> str:
    text = str(chunk or "").strip()
    text = re.sub(r"^```(?:yaml|yml|md|markdown|cpp)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _strip_trailing_bundle_markers(chunk: str) -> str:
    """Remove END marker lines accidentally captured in the last section."""
    lines = str(chunk or "").split("\n")
    while lines:
        st = lines[-1].strip()
        if not st:
            lines.pop()
            continue
        upper = st.upper()
        if any(p.upper() in upper for p in _END_MARKER_PATTERNS):
            lines.pop()
            continue
        if re.match(r"^=+\s*$", st) and "END" in upper:
            lines.pop()
            continue
        break
    body = "\n".join(lines).strip()
    return body + ("\n" if body else "")


def detect_bundle_markers(text: str) -> dict[str, Any]:
    body = normalize_copilot_markdown_bundle(str(text or ""))
    upper = body.upper()
    has_start = any(p.upper() in upper for p in _START_MARKER_PATTERNS)
    has_end = any(p.upper() in upper for p in _END_MARKER_PATTERNS)
    missing: list[str] = []
    if not has_start:
        missing.append("START")
    if not has_end:
        missing.append("END")
    return {"has_start": has_start, "has_end": has_end, "missing_markers": missing}


def _collect_section_header_spans(body: str) -> list[tuple[int, int, str]]:
    """Return (line_start, content_start, filename) for each section header."""
    spans: list[tuple[int, int, str]] = []
    for pattern in (_SECTION_HEAD_RE, _NUMBERED_SECTION_RE):
        for m in pattern.finditer(body):
            name = _normalize_config_filename(m.group("name"))
            if name in CONFIG_FILES:
                spans.append((m.start(), m.end(), name))
    spans.sort(key=lambda item: item[0])
    deduped: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for start, end, name in spans:
        if name in seen:
            continue
        seen.add(name)
        deduped.append((start, end, name))
    return deduped


def _extract_bundle_sections(body: str) -> dict[str, str]:
    """Split normalized bundle body into per-file section text (no YAML validation)."""
    headers = _collect_section_header_spans(body)
    if not headers:
        return {}
    out: dict[str, str] = {}
    for i, (_start, content_start, name) in enumerate(headers):
        content_end = headers[i + 1][0] if i + 1 < len(headers) else len(body)
        chunk = _strip_fence_wrapper(body[content_start:content_end])
        if i + 1 == len(headers):
            chunk = _strip_trailing_bundle_markers(chunk)
        if chunk or name in CONFIG_FILES:
            out[name] = chunk.strip() + ("\n" if chunk.strip() else "")
    return out


def detect_section_headings(text: str) -> list[str]:
    """Return config filenames found as markdown headings (before content parse)."""
    normalized = normalize_copilot_markdown_bundle(str(text or ""))
    return [name for _s, _e, name in _collect_section_header_spans(normalized)]


def extract_bundle_text_from_payload(payload: dict[str, Any] | None) -> tuple[str, list[str]]:
    """Accept bundle / text / content / bundle_markdown keys."""
    payload = payload or {}
    keys_present = [k for k in ("bundle", "text", "content", "bundle_markdown") if payload.get(k)]
    text = str(
        payload.get("bundle")
        or payload.get("text")
        or payload.get("content")
        or payload.get("bundle_markdown")
        or ""
    ).strip()
    return text, keys_present


def bundle_error_payload(
    reason: str,
    *,
    text: str = "",
    payload_keys: list[str] | None = None,
    detected_sections: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    markers = detect_bundle_markers(text)
    detected = detected_sections if detected_sections is not None else detect_section_headings(text)
    missing_sections = [s for s in EXPECTED_SECTIONS if s not in detected]
    body: dict[str, Any] = {
        "ok": False,
        "error": reason,
        "details": {
            "missing_markers": markers.get("missing_markers") or [],
            "has_start_marker": markers.get("has_start"),
            "has_end_marker": markers.get("has_end"),
            "detected_sections": detected,
            "expected_sections": list(EXPECTED_SECTIONS),
            "missing_sections": missing_sections,
            "payload_keys": payload_keys or [],
            "bundle_length": len(text),
        },
    }
    if extra:
        body["details"].update(extra)
    return body


def parse_config_bundle_markdown(text: str) -> dict[str, str]:
    """Parse alex_code_config_bundle.md into per-file sections."""
    return analyze_config_bundle(text).get("sections") or {}


def analyze_config_bundle(text: str) -> dict[str, Any]:
    """Parse bundle text: normalize + split sections only (no YAML validation)."""
    raw = str(text or "")
    body = normalize_copilot_markdown_bundle(raw)
    copilot_normalized = body != raw.strip()
    warnings: list[str] = [_IMPORT_YAML_NOTE]
    errors: list[str] = []
    markers = detect_bundle_markers(body)
    heading_names = detect_section_headings(body)

    if copilot_normalized:
        warnings.append("Copilot escaped Markdown was normalized.")

    if not body:
        return {
            "sections": {},
            "detected_sections": [],
            "missing_sections": list(EXPECTED_SECTIONS),
            "warnings": ["Bundle text is empty"],
            "errors": errors,
            "markers": markers,
            "heading_names": [],
            "copilot_normalized": False,
            "normalized_preview": "",
            "importable": False,
        }

    if markers["missing_markers"] and heading_names:
        warnings.append("Bundle markers missing, but sections were detected.")
    elif markers["missing_markers"]:
        warnings.append(
            f"Bundle START/END markers missing ({', '.join(markers['missing_markers'])}). "
            "Import can still proceed if sections are detected below."
        )

    out = _extract_bundle_sections(body)
    if not out:
        for m in _FENCE_FILE_RE.finditer(body):
            name = _normalize_config_filename(m.group("name"))
            if name not in CONFIG_FILES:
                continue
            start = m.end()
            end_match = re.search(r"^```\s*$", body[start:], re.MULTILINE)
            chunk = body[start : start + end_match.start()] if end_match else body[start:]
            chunk = _strip_fence_wrapper(chunk)
            if chunk:
                out[name] = chunk.strip() + "\n"

    if not out and len(body) > 20 and "code_rules" in body.lower():
        out["code_rules.md"] = body.strip() + "\n"
        warnings.append("No section headings detected; treated entire paste as code_rules.md (raw fallback).")

    detected = list(out.keys())
    missing = [s for s in EXPECTED_SECTIONS if s not in detected]
    if missing:
        warnings.append(
            f"Partial bundle: missing section(s): {', '.join(missing)}. "
            "You can still apply detected sections only."
        )

    return {
        "sections": out,
        "detected_sections": detected,
        "missing_sections": missing,
        "warnings": warnings,
        "errors": errors,
        "markers": markers,
        "heading_names": heading_names,
        "copilot_normalized": copilot_normalized,
        "normalized_preview": body[:500],
        "importable": bool(detected),
    }


def _import_diagnostics(analysis: dict[str, Any]) -> dict[str, Any]:
    detected = analysis.get("detected_sections") or []
    return {
        "detected_count": len(detected),
        "missing_sections": analysis.get("missing_sections") or [],
        "bundle_normalized": bool(analysis.get("copilot_normalized")),
        "yaml_validation": "not_performed",
        "importable": bool(analysis.get("importable")),
    }


def preview_config_bundle(job_output: Path, bundle_markdown: str) -> dict[str, Any]:
    """Dry-run: normalize, split sections, optional diff (never blocks on YAML)."""
    analysis = analyze_config_bundle(bundle_markdown)
    detected = analysis.get("detected_sections") or []
    if not detected:
        err = bundle_error_payload(
            "No config sections found in bundle markdown",
            text=bundle_markdown,
            detected_sections=[],
            extra={
                "warnings": analysis.get("warnings") or [],
                "heading_names": analysis.get("heading_names") or [],
                "normalized_preview": analysis.get("normalized_preview") or "",
            },
        )
        err["errors"] = analysis.get("errors") or []
        return err

    proposed = analysis.get("sections") or {}
    try:
        diff = diff_config_bundle(job_output, proposed)
    except Exception as exc:
        diff = {
            "summary": {},
            "changes": [],
            "warnings": [f"Diff preview skipped: {exc}"],
            "safe_default": "",
        }
        analysis["warnings"] = list(analysis.get("warnings") or []) + [
            "Structural diff could not be computed; section text is still importable."
        ]

    return {
        "ok": True,
        "detected_sections": detected,
        "missing_sections": analysis.get("missing_sections") or [],
        "warnings": analysis.get("warnings") or [],
        "errors": analysis.get("errors") or [],
        "normalized_preview": analysis.get("normalized_preview") or "",
        "copilot_normalized": analysis.get("copilot_normalized", False),
        "sections": proposed,
        "section_texts": proposed,
        "markers": analysis.get("markers") or {},
        "heading_names": analysis.get("heading_names") or [],
        "proposed_files": {k: len(v) for k, v in proposed.items()},
        "diff_summary": diff.get("summary") or {},
        "changes": diff.get("changes") or [],
        "partial_import_allowed": True,
        "import_diagnostics": _import_diagnostics(analysis),
        "safe_default": diff.get("safe_default"),
    }


def apply_bundle_import_sections(
    job_output: Path,
    bundle_markdown: str,
    *,
    selected_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Import bundle as raw section text into project_overrides (no YAML validation)."""
    analysis = analyze_config_bundle(bundle_markdown)
    detected = analysis.get("detected_sections") or []
    if not detected:
        err = bundle_error_payload(
            "No config sections found in bundle markdown",
            text=bundle_markdown,
            detected_sections=[],
            extra={"warnings": analysis.get("warnings") or []},
        )
        return err

    sections = analysis.get("sections") or {}
    allow = set(selected_sections) if selected_sections is not None else None
    ensure_config_layers(job_output)
    snap = _capture_layer_snapshots(job_output, list(sections.keys()))
    applied: list[str] = []
    root = project_code_config_dir(job_output)
    for name, content in sections.items():
        if allow is not None and name not in allow:
            continue
        _write_text(_overrides_dir(job_output) / name, content)
        applied.append(name)
    _write_text(root / BUNDLE_MARKDOWN_NAME, normalize_copilot_markdown_bundle(bundle_markdown))
    write_effective_config_files(job_output)
    for name in applied:
        _write_text(root / name, sections[name])
    ver = record_config_version(
        job_output,
        source=SOURCE_BUNDLE_IMPORT,
        changed_sections=applied,
        summary=f"Imported bundle text for {len(applied)} section(s)",
        changes=[{"section": n, "bytes": len(sections.get(n) or "")} for n in applied],
        layer_snapshots=snap,
    )
    return {
        "ok": True,
        "applied_sections": applied,
        "sections": {n: sections[n] for n in applied},
        "detected_sections": detected,
        "missing_sections": analysis.get("missing_sections") or [],
        "warnings": analysis.get("warnings") or [],
        "import_diagnostics": _import_diagnostics(analysis),
        "version": ver,
    }


def _mapping_dict_from_effective(job_output: Path) -> tuple[dict[str, str], dict[str, str]]:
    text = build_effective_config(job_output).get("signal_mapping.yaml") or ""
    parsed = parse_signal_mapping_yaml(text)
    m = {str(k): str(v) for k, v in (parsed.get("mappings") or {}).items()}
    t = {str(k): str(v) for k, v in (parsed.get("terms") or {}).items()}
    return m, t


def _api_set_from_effective(job_output: Path) -> set[str]:
    text = build_effective_config(job_output).get("api_catalog.yaml") or ""
    return parse_api_catalog_yaml(text)


def _text_changed(before: str, after: str) -> bool:
    return (before or "").strip() != (after or "").strip()


def diff_config_bundle(job_output: Path, proposed: dict[str, str]) -> dict[str, Any]:
    ensure_config_layers(job_output)
    effective = build_effective_config(job_output)
    cur_map, cur_terms = _mapping_dict_from_effective(job_output)
    cur_apis = _api_set_from_effective(job_output)

    changes: list[dict[str, Any]] = []
    summary = {
        "added_rules": 0,
        "modified_mappings": 0,
        "added_mappings": 0,
        "removed_mappings": 0,
        "new_apis": 0,
        "removed_apis": 0,
        "template_changes": 0,
        "conflicts": 0,
    }

    prop_map: dict[str, str] = {}
    prop_terms: dict[str, str] = {}
    if "signal_mapping.yaml" in proposed:
        p = parse_signal_mapping_yaml(proposed["signal_mapping.yaml"])
        if not (p.get("mappings") or p.get("terms")) and proposed["signal_mapping.yaml"].strip():
            try:
                raw = yaml.safe_load(proposed["signal_mapping.yaml"])
                if isinstance(raw, dict):
                    p = parse_signal_mapping_yaml(proposed["signal_mapping.yaml"])
            except yaml.YAMLError:
                pass
        prop_map = {str(k): str(v) for k, v in (p.get("mappings") or {}).items()}
        prop_terms = {str(k): str(v) for k, v in (p.get("terms") or {}).items()}
    all_keys = set(cur_map) | set(cur_terms) | set(prop_map) | set(prop_terms)

    for key in sorted(all_keys):
        cur_val = cur_terms.get(key) or cur_map.get(key) or ""
        new_val = prop_terms.get(key) or prop_map.get(key) or ""
        in_cur = key in cur_terms or key in cur_map
        in_new = key in prop_terms or key in prop_map
        if in_new and not in_cur and new_val:
            cid = f"map_add_{key}"
            changes.append(
                {
                    "id": cid,
                    "section": "signal_mapping.yaml",
                    "kind": "mapping_added",
                    "key": key,
                    "new_value": new_val,
                    "safe": True,
                    "selected_default": True,
                }
            )
            summary["added_mappings"] += 1
        elif in_cur and not in_new:
            cid = f"map_remove_{key}"
            changes.append(
                {
                    "id": cid,
                    "section": "signal_mapping.yaml",
                    "kind": "mapping_removed",
                    "key": key,
                    "previous_value": cur_val,
                    "safe": False,
                    "selected_default": False,
                    "warning": "Removal requires explicit confirmation",
                }
            )
            summary["removed_mappings"] += 1
        elif in_cur and in_new and cur_val != new_val and new_val:
            over = parse_signal_mapping_yaml(_layer_text(job_output, "project_overrides", "signal_mapping.yaml"))
            override_val = (over.get("terms") or {}).get(key) or (over.get("mappings") or {}).get(key)
            conflict = bool(override_val and override_val != new_val)
            cid = f"map_mod_{key}"
            changes.append(
                {
                    "id": cid,
                    "section": "signal_mapping.yaml",
                    "kind": "mapping_modified",
                    "key": key,
                    "previous_value": cur_val,
                    "new_value": new_val,
                    "safe": not conflict,
                    "conflict": conflict,
                    "selected_default": not conflict,
                    "warning": "project_overrides wins over baseline" if conflict else None,
                }
            )
            summary["modified_mappings"] += 1
            if conflict:
                summary["conflicts"] += 1

    if "api_catalog.yaml" in proposed:
        prop_apis = parse_api_catalog_yaml(proposed["api_catalog.yaml"])
        for api in sorted(prop_apis - cur_apis):
            changes.append(
                {
                    "id": f"api_add_{api}",
                    "section": "api_catalog.yaml",
                    "kind": "api_added",
                    "key": api,
                    "safe": True,
                    "selected_default": True,
                }
            )
            summary["new_apis"] += 1
        for api in sorted(cur_apis - prop_apis):
            changes.append(
                {
                    "id": f"api_remove_{api}",
                    "section": "api_catalog.yaml",
                    "kind": "api_removed",
                    "key": api,
                    "safe": False,
                    "selected_default": False,
                    "warning": "Removal requires explicit confirmation",
                }
            )
            summary["removed_apis"] += 1

    for fname in MARKDOWN_CONFIG_FILES:
        if fname not in proposed:
            continue
        before = effective.get(fname) or ""
        after = proposed[fname]
        if _text_changed(before, after):
            kind = "rules_changed" if fname == "code_rules.md" else "template_changed"
            if fname == "code_rules.md":
                summary["added_rules"] += 1
            else:
                summary["template_changes"] += 1
            changes.append(
                {
                    "id": f"text_{fname}",
                    "section": fname,
                    "kind": kind,
                    "previous_value": before[:2000],
                    "new_value": after[:2000],
                    "safe": False,
                    "selected_default": False,
                    "warning": "Markdown section merge appends to project_overrides unless Save as baseline",
                }
            )

    return {
        "ok": True,
        "proposed_files": list(proposed.keys()),
        "changes": changes,
        "summary": summary,
        "safe_default": "Apply selected safe changes only; overrides are not deleted automatically.",
    }


def propose_config_bundle(job_output: Path, bundle_markdown: str) -> dict[str, Any]:
    """Store pending proposal for legacy diff-based apply (optional)."""
    preview = preview_config_bundle(job_output, bundle_markdown)
    if not preview.get("ok"):
        return preview
    proposed = preview.get("sections") or preview.get("section_texts") or {}
    payload = {
        "proposed": proposed,
        "diff": {
            "summary": preview.get("diff_summary") or {},
            "changes": preview.get("changes") or [],
        },
        "imported_at": _now_iso(),
        "bundle_name": BUNDLE_MARKDOWN_NAME,
        "detected_sections": preview.get("detected_sections") or [],
        "missing_sections": preview.get("missing_sections") or [],
        "warnings": preview.get("warnings") or [],
    }
    _write_text(project_code_config_dir(job_output) / PENDING_FILE, json.dumps(payload, indent=2))
    return {**preview, "proposed": {k: len(v) for k, v in proposed.items()}}


def _apply_mapping_change(job_output: Path, change: dict[str, Any], *, target: str) -> None:
    key = str(change.get("key") or "")
    if not key:
        return
    kind = change.get("kind") or ""
    if target == "learned":
        path = project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE
        data = parse_signal_mapping_yaml(_read_text(path))
    else:
        path = _overrides_dir(job_output) / "signal_mapping.yaml"
        data = parse_signal_mapping_yaml(_read_text(path))

    terms = dict(data.get("terms") or {})
    mappings = dict(data.get("mappings") or {})

    if kind in ("mapping_added", "mapping_modified"):
        val = str(change.get("new_value") or "")
        terms[key] = val
    elif kind == "mapping_removed":
        terms.pop(key, None)
        mappings.pop(key, None)

    _write_text(path, yaml.safe_dump({"mappings": mappings, "terms": terms}, sort_keys=False))


def _append_api_override(job_output: Path, api: str) -> None:
    path = _overrides_dir(job_output) / "api_catalog.yaml"
    data = parse_signal_mapping_yaml(_read_text(path)) if False else {}
    apis = parse_api_catalog_yaml(_read_text(path))
    apis.add(api)
    _write_text(path, yaml.safe_dump({"apis": sorted(apis)}, sort_keys=False))


def _append_markdown_override(job_output: Path, filename: str, new_text: str) -> None:
    path = _overrides_dir(job_output) / filename
    existing = _read_text(path).strip()
    merged = f"{existing}\n\n<!-- bundle import -->\n\n{new_text.strip()}" if existing else new_text.strip()
    _write_text(path, merged + "\n")


def apply_config_bundle_proposal(
    job_output: Path,
    *,
    mode: str,
    selected_ids: list[str] | None = None,
    allow_removals: bool = False,
) -> dict[str, Any]:
    pending_path = project_code_config_dir(job_output) / PENDING_FILE
    if not pending_path.exists():
        return {"ok": False, "error": "No pending bundle proposal — import bundle first"}
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "error": "Invalid pending proposal"}

    if mode == "ignore":
        pending_path.unlink(missing_ok=True)
        return {"ok": True, "ignored": True}

    proposed: dict[str, str] = pending.get("proposed") or {}
    diff = pending.get("diff") or {}
    changes: list[dict[str, Any]] = diff.get("changes") or []
    selected = set(selected_ids or [])

    if mode == "apply_all":
        to_apply = [c for c in changes if c.get("safe") or (allow_removals and c.get("kind", "").endswith("_removed"))]
    elif mode == "apply_selected":
        to_apply = [c for c in changes if c.get("id") in selected]
    elif mode == "save_as_baseline":
        snap = _capture_layer_snapshots(job_output, list(proposed.keys()))
        for name, content in proposed.items():
            _write_text(_baseline_dir(job_output) / name, content)
        write_effective_config_files(job_output)
        pending_path.unlink(missing_ok=True)
        ver = record_config_version(
            job_output,
            source=SOURCE_BUNDLE_IMPORT,
            changed_sections=list(proposed.keys()),
            summary="Saved imported bundle as new baseline",
            changes=[{"action": "save_as_baseline", "files": list(proposed.keys())}],
            layer_snapshots=snap,
        )
        return {"ok": True, "mode": mode, "version": ver}
    elif mode == "apply_as_overrides":
        to_apply = [
            c
            for c in changes
            if c.get("safe") or c.get("id") in selected or (allow_removals and str(c.get("kind", "")).endswith("_removed"))
        ]
    else:
        return {"ok": False, "error": f"Unknown mode: {mode}"}

    snap = _capture_layer_snapshots(
        job_output,
        list({c.get("section") for c in to_apply if c.get("section")}),
    )
    applied: list[str] = []
    skipped: list[str] = []

    for change in changes:
        cid = change.get("id")
        if change not in to_apply:
            continue
        kind = change.get("kind") or ""
        if kind.endswith("_removed") and not allow_removals:
            skipped.append(cid or kind)
            continue
        if kind.startswith("mapping_"):
            _apply_mapping_change(job_output, change, target="project_overrides")
            applied.append(cid or kind)
        elif kind == "api_added":
            _append_api_override(job_output, str(change.get("key") or ""))
            applied.append(cid or kind)
        elif kind in ("rules_changed", "template_changed"):
            _append_markdown_override(job_output, str(change.get("section") or ""), str(change.get("new_value") or ""))
            applied.append(cid or kind)
        elif kind == "api_removed":
            skipped.append(cid or kind)

    write_effective_config_files(job_output)
    pending_path.unlink(missing_ok=True)
    ver = record_config_version(
        job_output,
        source=SOURCE_BUNDLE_IMPORT,
        changed_sections=sorted({c.get("section") for c in to_apply if c.get("section")}),
        summary=f"Applied bundle proposal ({mode}): {len(applied)} change(s)",
        changes=[{"id": a, "action": "applied"} for a in applied],
        layer_snapshots=snap,
    )
    return {"ok": True, "mode": mode, "applied": applied, "skipped": skipped, "version": ver}


def save_manual_config_edit(
    job_output: Path,
    filename: str,
    content: str,
    *,
    target_layer: str = "project_overrides",
) -> dict[str, Any]:
    if filename not in CONFIG_FILES:
        return {"ok": False, "error": f"Unknown file: {filename}"}
    ensure_config_layers(job_output)
    snap = _capture_layer_snapshots(job_output, [filename])
    if target_layer == "baseline":
        _write_text(_baseline_dir(job_output) / filename, content)
    else:
        _write_text(_overrides_dir(job_output) / filename, content)
    write_effective_config_files(job_output)
    ver = record_config_version(
        job_output,
        source=SOURCE_MANUAL_EDIT,
        changed_sections=[filename],
        summary=f"Manual edit: {filename}",
        changes=[{"file": filename, "previous": (snap.get("project_overrides") or {}).get(filename, "")[:500], "new": content[:500]}],
        layer_snapshots=snap,
    )
    return {"ok": True, "version": ver}


def add_learned_mapping(job_output: Path, term: str, code: str, *, use_project_override: bool = False) -> dict[str, Any]:
    ensure_config_layers(job_output)
    snap = _capture_layer_snapshots(job_output, ["signal_mapping.yaml"])
    term = str(term or "").strip()
    code = str(code or "").strip()
    if not term or not code:
        return {"ok": False, "error": "term and code are required"}

    if use_project_override:
        path = _overrides_dir(job_output) / "signal_mapping.yaml"
        data = parse_signal_mapping_yaml(_read_text(path))
        terms = dict(data.get("terms") or {})
        terms[term] = code
        _write_text(path, yaml.safe_dump({"mappings": data.get("mappings") or {}, "terms": terms}, sort_keys=False))
        source = SOURCE_MANUAL_EDIT
    else:
        path = project_code_config_dir(job_output) / LEARNED_MAPPINGS_FILE
        data = parse_signal_mapping_yaml(_read_text(path))
        terms = dict(data.get("terms") or {})
        terms[term] = code
        _write_text(path, yaml.safe_dump({"mappings": data.get("mappings") or {}, "terms": terms}, sort_keys=False))
        source = SOURCE_LEARNED_RULE

    gtest_state_map_note = term
    write_effective_config_files(job_output)
    ver = record_config_version(
        job_output,
        source=source,
        changed_sections=["signal_mapping.yaml"],
        summary=f"Added mapping: {term} → {code[:80]}",
        changes=[{"term": term, "code": code}],
        layer_snapshots=snap,
    )
    return {"ok": True, "term": term, "code": code, "version": ver, "gtest_state_map_note": gtest_state_map_note}


def add_learned_rule(job_output: Path, rule_text: str, *, context: str = "") -> dict[str, Any]:
    ensure_config_layers(job_output)
    snap = _capture_layer_snapshots(job_output, ["code_rules.md"])
    path = project_code_config_dir(job_output) / LEARNED_RULES_FILE
    existing = _read_text(path)
    line = f"- {rule_text.strip()}"
    if context:
        line += f"  <!-- {context.strip()[:120]} -->"
    if "## Rules" in existing:
        existing = existing.replace("## Rules", f"## Rules\n{line}", 1)
    else:
        existing = (existing.rstrip() + f"\n\n## Rules\n{line}\n").strip() + "\n"
    _write_text(path, existing)
    write_effective_config_files(job_output)
    ver = record_config_version(
        job_output,
        source=SOURCE_LEARNED_RULE,
        changed_sections=["learned_rules.md", "code_rules.md"],
        summary=f"Learned rule: {rule_text[:100]}",
        changes=[{"rule": rule_text, "context": context}],
        layer_snapshots=snap,
    )
    return {"ok": True, "version": ver}


def export_effective_config_bundle(job_output: Path) -> dict[str, Any]:
    effective = build_effective_config(job_output)
    meta = get_layers_meta(job_output)
    lines = [
        "# ALEX Effective Code Config Bundle",
        f"# exported_at: {_now_iso()}",
        f"# current_version_id: {meta.get('current_version_id') or '—'}",
        "",
        "Export of baseline + project_overrides + learned_rules (effective merge).",
        "",
    ]
    for name in list_config_filenames():
        lines.append(f"## {name}")
        lines.append("")
        lines.append("```yaml" if name.endswith(".yaml") else "```markdown")
        lines.append(effective.get(name) or "")
        lines.append("```")
        lines.append("")
    content = "\n".join(lines)
    return {"ok": True, "filename": BUNDLE_MARKDOWN_NAME, "content": content, "metadata": meta}


def build_config_improvement_prompt(
    job_output: Path,
    gtest_state: dict[str, Any],
    *,
    change_request: str = "",
    bundle: dict[str, Any] | None = None,
    language: str = "EN",
) -> dict[str, Any]:
    from web.local_template_codegen import check_mapping_coverage

    effective = build_effective_config(job_output)
    cov = gtest_state.get("mapping_coverage") or {}
    if bundle and not cov:
        cov = check_mapping_coverage(bundle, gtest_state, job_output, language=language)

    warn_counts: dict[str, int] = {}
    for draft in (gtest_state.get("drafts") or {}).values():
        for check in draft.get("quality_results") or []:
            if check.get("severity") in ("WARNING", "FAIL"):
                name = str(check.get("check_name") or "other")
                warn_counts[name] = warn_counts.get(name, 0) + 1

    lines = [
        "# ALEX Config Improvement Request",
        "",
        "Please return an updated `alex_code_config_bundle.md` with sections:",
        "code_rules.md, signal_mapping.yaml, gtest_template.md, api_catalog.yaml, ai_review_pack.md",
        "",
        "Use patch-style updates: prefer additions; flag breaking removals explicitly.",
        "Do not remove project-specific overrides unless clearly obsolete.",
        "",
    ]
    if change_request.strip():
        lines.extend(["## User change request", change_request.strip(), ""])
    lines.extend(
        [
            "## Mapping coverage",
            f"- ready: {cov.get('ready_for_local_generation', '—')}",
            f"- missing: {cov.get('missing_mapping_count', '—')}",
            f"- missing terms: {', '.join((cov.get('missing_terms') or [])[:30])}",
            "",
            "## Repeated quality warnings",
        ]
    )
    for name, count in sorted(warn_counts.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"- {name}: {count}")
    if not warn_counts:
        lines.append("- (none recorded)")
    lines.extend(["", "## Current effective config", ""])
    for name in list_config_filenames():
        text = effective.get(name) or ""
        lines.append(f"### {name}")
        lines.append("```")
        lines.append(text[:6000])
        lines.append("```")
        lines.append("")

    content = "\n".join(lines)
    return {"ok": True, "content": content, "char_count": len(content)}
