"""ALEX runtime data — presets, project memory, code samples (always under ALEX/web_data/.alex)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.utils.yaml_utils import dump_yaml, load_yaml

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web_data"
ALEX_DATA_DIR = WEB_DATA / ".alex"

GTEST_PRESET_NAME = "gtest_harness_preset.yaml"
PROJECT_MEMORY_NAME = "project_memory.yaml"
CODE_STYLE_SAMPLES_NAME = "code_style_samples.yaml"

LEGACY_MARKERS = ("pm_test_spec_assistant",)


def ensure_alex_data_dir() -> Path:
    ALEX_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return ALEX_DATA_DIR


def default_library_root() -> Path:
    """Folder for spec files on the Library canvas (not ALEX config)."""
    for candidate in (
        ROOT / "sample_inputs" / "input",
        ROOT / "sample_inputs",
        ROOT / "input",
    ):
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    return ROOT / "sample_inputs" / "input"


def normalize_library_root(raw: str) -> str:
    """Re-point stale pm_test_spec_assistant paths to ALEX/sample_inputs."""
    text = str(raw or "").strip()
    if not text:
        return str(default_library_root())
    if any(marker in text.replace("\\", "/") for marker in LEGACY_MARKERS):
        return str(default_library_root())
    path = Path(text).expanduser()
    if not path.is_absolute():
        return str(default_library_root())
    return str(path.resolve())


def gtest_preset_path() -> Path:
    return ensure_alex_data_dir() / GTEST_PRESET_NAME


def project_memory_path() -> Path:
    return ensure_alex_data_dir() / PROJECT_MEMORY_NAME


def code_style_samples_path() -> Path:
    return ensure_alex_data_dir() / CODE_STYLE_SAMPLES_NAME


def _legacy_alex_dir(library_root: Path | None) -> Path | None:
    if not library_root:
        return None
    legacy = library_root / ".alex"
    return legacy if legacy.is_dir() else None


def migrate_legacy_alex_data(library_root: Path | None = None) -> list[str]:
    """Copy presets from old library_root/.alex into web_data/.alex (once per file)."""
    migrated: list[str] = []
    legacy = _legacy_alex_dir(library_root)
    if not legacy:
        return migrated
    ensure_alex_data_dir()
    mapping = {
        GTEST_PRESET_NAME: gtest_preset_path(),
        PROJECT_MEMORY_NAME: project_memory_path(),
        CODE_STYLE_SAMPLES_NAME: code_style_samples_path(),
    }
    for name, dest in mapping.items():
        src = legacy / name
        if src.is_file() and not dest.exists():
            shutil.copy2(src, dest)
            migrated.append(name)
    return migrated


def load_yaml_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = load_yaml(path)
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def save_project_memory_file(memory: dict[str, Any]) -> Path:
    from web.project_memory import export_library_memory

    path = project_memory_path()
    ensure_alex_data_dir()
    dump_yaml(path, export_library_memory(memory))
    return path
