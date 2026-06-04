"""Per-job project code configuration files (markdown/yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.utils.yaml_utils import load_yaml


def _parse_yaml_text(text: str) -> Any:
    if not (text or "").strip():
        return {}
    try:
        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

CONFIG_DIR_NAME = "code_config"

CONFIG_FILES: dict[str, dict[str, str]] = {
    "project_instruction.md": {
        "description": "Primary Copilot batch instruction (edit this file to add project-specific rules)",
        "default": """Generate Google Test C++ .cc code from the testcase rows.
Follow sample .cc style if provided.
Generate one TEST_F per testcase_id.
Preserve testcase_id in comments.
Use Given/When/Then from testcase.
If unsure, return UNRESOLVED instead of inventing behavior.
Return structured [TESTCASE_CODE] blocks.
""",
    },
    "code_rules.md": {
        "description": "Coding rules, fixture, naming, assertion style, timing, forbidden patterns",
        "default": """# ALEX Project Code Rules

## Fixture
- Use TEST_F with fixture class from harness config.

## Assertions
- Prefer EXPECT_EQ / EXPECT_TRUE for outputs.
- Do not use bare ASSERT unless safety-critical.

## Timing
- When spec includes elapsed_time or Wait, call RunForMs or harness advance_time helper.

## Forbidden
- No markdown ``` fences in saved code
- No TODO in final saved code
- Do not access internal/private harness variables directly
""",
    },
    "signal_mapping.yaml": {
        "description": "Testcase term/signal to setter/getter/assertion paths",
        "default": """# signal -> code path (merged with job code_variable_map)
mappings: {}
terms: {}
""",
    },
    "gtest_template.md": {
        "description": "Reusable GTest snippet template (optional; local gen uses engine skeleton)",
        "default": """# GTest template notes
Local generation uses the deterministic skeleton from spec I/O.
Optional placeholders: {{candidate_id}}, {{fixture_class}}, {{test_name}}
""",
    },
    "api_catalog.yaml": {
        "description": "Allowed harness APIs",
        "default": """apis:
  - SetSignal
  - RunForMs
  - EvaluatePowerMode
  - EXPECT_EQ
  - EXPECT_TRUE
  - EXPECT_FALSE
  - TEST_F
""",
    },
    "ai_review_pack.md": {
        "description": "Template for future Claude/manual batch review",
        "default": """# AI Batch Review Pack Template

Required response sections:
[SUMMARY]
[QUALITY_FINDINGS]
[PATCH_PLAN]
[PATCHES]
[UNRESOLVED_ITEMS]
""",
    },
}


def project_code_config_dir(job_output: Path) -> Path:
    return job_output / "bundle" / CONFIG_DIR_NAME


def list_config_filenames() -> list[str]:
    return list(CONFIG_FILES.keys())


# ---------------------------------------------------------------------------
# Global project_instruction.md (stored in web_data/.alex/)
# ---------------------------------------------------------------------------

def load_global_instruction() -> str | None:
    """Return global project_instruction.md content, or None if not saved yet."""
    from web.alex_storage import global_instruction_path
    path = global_instruction_path()
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def save_global_instruction(content: str) -> Path:
    """Save project_instruction.md to global library (web_data/.alex/)."""
    from web.alex_storage import global_instruction_path, ensure_alex_data_dir
    ensure_alex_data_dir()
    path = global_instruction_path()
    path.write_text(str(content or ""), encoding="utf-8")
    return path


def effective_instruction_for_job(job_output: Path) -> tuple[str, str]:
    """Return (instruction_content, source) for a job.

    source is one of: 'job_override', 'global', 'builtin_default'.
    Does NOT write to disk — caller decides.
    """
    from web.config_bundle_layers import _overrides_dir, _baseline_dir

    # 1. Job-specific override (project_overrides layer)
    override_path = _overrides_dir(job_output) / "project_instruction.md"
    if override_path.exists():
        text = override_path.read_text(encoding="utf-8").strip()
        if text:
            return text, "job_override"

    # 2. Job baseline that differs from built-in default
    baseline_path = _baseline_dir(job_output) / "project_instruction.md"
    builtin_default = (CONFIG_FILES.get("project_instruction.md") or {}).get("default") or ""
    if baseline_path.exists():
        text = baseline_path.read_text(encoding="utf-8").strip()
        if text and text != builtin_default.strip():
            return text, "job_override"

    # 3. Global instruction
    global_content = load_global_instruction()
    if global_content and global_content.strip():
        return global_content, "global"

    # 4. Builtin default
    return builtin_default, "builtin_default"


def load_project_code_config(job_output: Path) -> dict[str, Any]:
    """Load effective config (baseline + overrides + learned) and sync flat files."""
    from web.config_bundle_layers import load_layered_project_code_config

    return load_layered_project_code_config(job_output)


def save_project_code_config_file(
    job_output: Path,
    filename: str,
    content: str,
    *,
    target_layer: str = "project_overrides",
) -> dict[str, Any]:
    if filename not in CONFIG_FILES:
        return {"ok": False, "error": f"Unknown config file: {filename}"}
    from web.config_bundle_layers import save_manual_config_edit

    result = save_manual_config_edit(job_output, filename, content, target_layer=target_layer)
    if not result.get("ok"):
        return result
    root = project_code_config_dir(job_output)
    return {"ok": True, "name": filename, "path": str(root / filename), "version": result.get("version")}


def parse_signal_mapping_yaml(text: str) -> dict[str, Any]:
    from web.config_yaml_parsers import parse_signal_mapping_yaml as _parse

    return _parse(text)


def parse_api_catalog_yaml(text: str) -> set[str]:
    from web.config_yaml_parsers import parse_api_catalog_yaml as _parse

    return _parse(text)


def parse_api_catalog_full(text: str) -> dict[str, Any]:
    from web.config_yaml_parsers import parse_api_catalog_full as _parse

    return _parse(text)


def diagnose_project_code_config_files(
    signal_mapping_text: str,
    api_catalog_text: str,
) -> dict[str, Any]:
    from web.config_yaml_parsers import diagnose_project_code_config as _diag

    return _diag(signal_mapping_text, api_catalog_text)


def parse_forbidden_patterns(code_rules_md: str) -> list[str]:
    patterns: list[str] = []
    for line in (code_rules_md or "").splitlines():
        text = line.strip()
        if text.lower().startswith("forbidden") or text.startswith("#"):
            continue
        if text.startswith("- "):
            pat = text[2:].strip()
            if pat and "no " in pat.lower():
                if "markdown" in pat.lower() and "```" in pat:
                    patterns.append("```")
                if "todo" in pat.lower():
                    patterns.append("TODO")
            if "internal" in pat.lower() and "variable" in pat.lower():
                patterns.append("__")  # heuristic: double underscore private
    if "```" not in patterns:
        patterns.append("```")
    if "TODO" not in patterns:
        patterns.append("TODO")
    return patterns
