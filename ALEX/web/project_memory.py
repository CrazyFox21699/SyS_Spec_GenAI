"""Project memory — IO maps, shared preconditions, verification patterns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.yaml_utils import load_yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_PATH = ROOT / "config" / "project_memory.yaml"
from web.alex_storage import load_yaml_file, project_memory_path as alex_project_memory_path


def default_project_memory() -> dict[str, Any]:
    return {
        "io_variable_map": {},
        "signal_roles": {},
        "shared_preconditions": [],
        "verification_patterns": [],
        "copilot_hints": {"prefer_reuse_patterns": True, "max_patterns_in_prompt": 5},
    }


def load_default_memory() -> dict[str, Any]:
    if not DEFAULT_MEMORY_PATH.exists():
        return default_project_memory()
    try:
        data = load_yaml(DEFAULT_MEMORY_PATH)
    except (OSError, ValueError, TypeError):
        return default_project_memory()
    if not isinstance(data, dict):
        return default_project_memory()
    base = default_project_memory()
    pm = data.get("project_memory") if "project_memory" in data else data
    if not isinstance(pm, dict):
        return base
    base["io_variable_map"] = dict(pm.get("io_variable_map") or {})
    base["signal_roles"] = dict(pm.get("signal_roles") or {})
    base["shared_preconditions"] = list(pm.get("shared_preconditions") or [])
    base["verification_patterns"] = list(pm.get("verification_patterns") or [])
    hints = dict(base["copilot_hints"])
    hints.update(pm.get("copilot_hints") or {})
    base["copilot_hints"] = hints
    return base


def library_memory_path(library_root: Path | None = None) -> Path:
    """Project memory file — always under ALEX/web_data/.alex."""
    del library_root
    return alex_project_memory_path()


def load_library_memory(library_root: Path | None = None) -> dict[str, Any]:
    del library_root
    path = alex_project_memory_path()
    if not path.exists():
        return default_project_memory()
    data = load_yaml_file(path)
    if not isinstance(data, dict):
        return default_project_memory()
    pm = data.get("project_memory") if "project_memory" in data else data
    if not isinstance(pm, dict):
        return default_project_memory()
    base = default_project_memory()
    base["io_variable_map"] = dict(pm.get("io_variable_map") or {})
    base["signal_roles"] = dict(pm.get("signal_roles") or {})
    base["shared_preconditions"] = list(pm.get("shared_preconditions") or [])
    base["verification_patterns"] = list(pm.get("verification_patterns") or [])
    return base


def merge_project_memory(
    *,
    library_root: Path | None = None,
    bundle: dict[str, Any] | None = None,
    gtest_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del library_root
    merged = load_default_memory()
    lib = load_library_memory()
    merged["io_variable_map"] = {**merged["io_variable_map"], **lib.get("io_variable_map", {})}
    merged["signal_roles"] = {**merged["signal_roles"], **lib.get("signal_roles", {})}
    merged["shared_preconditions"] = list(lib.get("shared_preconditions") or []) or merged["shared_preconditions"]
    merged["verification_patterns"] = list(lib.get("verification_patterns") or []) or merged["verification_patterns"]

    if bundle:
        ai = bundle.get("ai_assists") or {}
        override = ai.get("project_memory") or {}
        if override.get("io_variable_map"):
            merged["io_variable_map"].update(override["io_variable_map"])
        if override.get("signal_roles"):
            merged["signal_roles"].update(override["signal_roles"])
        if override.get("shared_preconditions"):
            merged["shared_preconditions"] = list(override["shared_preconditions"])
        if override.get("verification_patterns"):
            merged["verification_patterns"] = list(override["verification_patterns"])

    if gtest_state and gtest_state.get("code_variable_map"):
        merged["io_variable_map"] = {
            **merged["io_variable_map"],
            **dict(gtest_state.get("code_variable_map") or {}),
        }

    return merged


def save_bundle_memory(bundle: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    ai = bundle.setdefault("ai_assists", {})
    ai["project_memory"] = {
        "io_variable_map": dict(memory.get("io_variable_map") or {}),
        "signal_roles": dict(memory.get("signal_roles") or {}),
        "shared_preconditions": list(memory.get("shared_preconditions") or []),
        "verification_patterns": list(memory.get("verification_patterns") or []),
    }
    return ai["project_memory"]


def export_library_memory(memory: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "alex_project_memory", "project_memory": memory}


def import_library_memory(preset: dict[str, Any]) -> dict[str, Any]:
    pm = preset.get("project_memory") if isinstance(preset, dict) else None
    if not isinstance(pm, dict):
        return default_project_memory()
    base = default_project_memory()
    base["io_variable_map"] = dict(pm.get("io_variable_map") or {})
    base["signal_roles"] = dict(pm.get("signal_roles") or {})
    base["shared_preconditions"] = list(pm.get("shared_preconditions") or [])
    base["verification_patterns"] = list(pm.get("verification_patterns") or [])
    return base


def patterns_for_logic(memory: dict[str, Any], logic_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in memory.get("verification_patterns") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("logic_id") or "") in ("", logic_id):
            out.append(row)
    return out[: int((memory.get("copilot_hints") or {}).get("max_patterns_in_prompt") or 5)]


def remember_io_from_text(
    memory: dict[str, Any],
    *,
    expected_input: str,
    expected_output: str,
    harness_inputs: str = "in",
    harness_outputs: str = "out",
) -> dict[str, str]:
    """Extract spec signal names from Given/Then and propose default code paths."""
    import re

    io_map = dict(memory.get("io_variable_map") or {})
    given_re = re.compile(r"(?im)^\s*Given:\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=")
    then_re = re.compile(r"(?im)^\s*Then:\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=")
    for line in str(expected_input or "").splitlines():
        m = given_re.match(line.strip())
        if m:
            sig = m.group(1).upper()
            io_map.setdefault(sig, f"{harness_inputs}.{sig}")
    for line in str(expected_output or "").splitlines():
        m = then_re.match(line.strip())
        if m:
            sig = m.group(1).upper()
            io_map.setdefault(sig, f"{harness_outputs}.{sig}")
    return io_map


def promote_verification_pattern(
    memory: dict[str, Any],
    *,
    logic_id: str,
    given_fingerprint: str,
    then_signals: list[str],
    candidate_ids: list[str] | None = None,
    label: str = "",
) -> dict[str, Any]:
    """Append engineer-approved verification pattern (dedupe by given_fingerprint + logic_id)."""
    patterns = list(memory.get("verification_patterns") or [])
    gfp = str(given_fingerprint or "").strip()
    lid = str(logic_id or "").strip()
    if not gfp or not lid:
        raise ValueError("logic_id and given_fingerprint required")
    for row in patterns:
        if str(row.get("logic_id") or "") == lid and str(row.get("given_fingerprint") or "") == gfp:
            existing_ids = set(row.get("example_candidate_ids") or [])
            existing_ids.update(candidate_ids or [])
            row["example_candidate_ids"] = sorted(existing_ids)
            if then_signals:
                row["then_signals"] = sorted(set(row.get("then_signals") or []) | set(then_signals))
            if label:
                row["label"] = label
            memory["verification_patterns"] = patterns
            return row
    pattern_id = f"VP_{lid}_{len(patterns) + 1:02d}"[:32]
    row = {
        "id": pattern_id,
        "logic_id": lid,
        "label": label or pattern_id,
        "given_fingerprint": gfp,
        "then_signals": sorted(set(then_signals or [])),
        "example_candidate_ids": sorted(set(candidate_ids or [])),
    }
    patterns.append(row)
    memory["verification_patterns"] = patterns
    return row


def promote_shared_precondition(
    memory: dict[str, Any],
    *,
    label: str,
    expected_input: str,
    logic_id: str = "",
) -> dict[str, Any]:
    """Append shared precondition block (dedupe by label)."""
    preconds = list(memory.get("shared_preconditions") or [])
    text = str(label or "").strip()
    body = str(expected_input or "").strip()
    if not text or not body:
        raise ValueError("label and expected_input required")
    for row in preconds:
        if str(row.get("label") or "") == text:
            row["expected_input"] = body
            if logic_id:
                row["logic_id"] = logic_id
            memory["shared_preconditions"] = preconds
            return row
    pre_id = f"PRE_{len(preconds) + 1:02d}"
    row = {
        "id": pre_id,
        "label": text,
        "expected_input": body,
        "logic_id": logic_id or "",
    }
    preconds.append(row)
    memory["shared_preconditions"] = preconds
    return row
