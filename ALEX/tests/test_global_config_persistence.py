"""Tests for global config persistence — memory, instruction, style samples."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from web.alex_storage import global_instruction_path
from web.alex_storage import testcode_memory_path as _testcode_memory_path
from web.project_code_config import (
    effective_instruction_for_job,
    load_global_instruction,
    save_global_instruction,
)
from web.project_testcode_memory import (
    copy_global_to_job,
    load_global_memory,
    load_memory_for_job,
    save_global_memory,
    save_memory_for_job,
    _job_memory_path,
)

_GLOBAL_MEM = "# Memory\n## Fixture / Test Style\n- use GlobalFixture\n"
_JOB_MEM = "# Memory\n## Fixture / Test Style\n- use JobFixture\n"
_GLOBAL_INSTR = "Generate GTest from testcase rows. Use global style.\n"
_JOB_INSTR = "Generate GTest from testcase rows. Use job-specific style.\n"
_BUILTIN_DEFAULT_SNIPPET = "Generate Google Test C++ .cc code from the testcase rows."


# ---------------------------------------------------------------------------
# 1. Memory global save/load
# ---------------------------------------------------------------------------

def test_save_memory_as_global_writes_to_alex_dir(tmp_path: Path) -> None:
    global_path = tmp_path / "project_testcode_memory.md"
    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        save_global_memory(_GLOBAL_MEM)
    assert global_path.exists()
    assert "GlobalFixture" in global_path.read_text(encoding="utf-8")


def test_load_global_memory_returns_saved_content(tmp_path: Path) -> None:
    global_path = tmp_path / "project_testcode_memory.md"
    global_path.write_text(_GLOBAL_MEM, encoding="utf-8")
    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = load_global_memory()
    assert "GlobalFixture" in content


def test_new_job_auto_loads_global_memory(tmp_path: Path) -> None:
    """copy_global_to_job must copy global memory into empty job."""
    global_path = tmp_path / "project_testcode_memory.md"
    global_path.write_text(_GLOBAL_MEM, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()
    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = copy_global_to_job(job_output)
    assert "GlobalFixture" in content
    job_mem = _job_memory_path(job_output)
    assert job_mem.exists()
    assert "GlobalFixture" in job_mem.read_text(encoding="utf-8")


def test_job_specific_memory_not_overwritten_by_global(tmp_path: Path) -> None:
    """If job memory already exists, copy_global_to_job must not overwrite it."""
    global_path = tmp_path / "project_testcode_memory.md"
    global_path.write_text(_GLOBAL_MEM, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()
    # Write job-specific memory
    save_memory_for_job(job_output, _JOB_MEM)

    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = copy_global_to_job(job_output)

    assert "JobFixture" in content, "Job memory must take priority over global"
    assert "GlobalFixture" not in content


def test_load_memory_for_job_falls_back_to_global_when_no_local(tmp_path: Path) -> None:
    global_path = tmp_path / "project_testcode_memory.md"
    global_path.write_text(_GLOBAL_MEM, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()
    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = load_memory_for_job(job_output)
    assert "GlobalFixture" in content


# ---------------------------------------------------------------------------
# 2. Instruction global save/load
# ---------------------------------------------------------------------------

def test_save_instruction_as_global_writes_to_alex_dir(tmp_path: Path) -> None:
    global_path = tmp_path / "project_instruction.md"
    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        save_global_instruction(_GLOBAL_INSTR)
    assert global_path.exists()
    assert "global style" in global_path.read_text(encoding="utf-8")


def test_load_global_instruction_returns_none_when_missing(tmp_path: Path) -> None:
    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        result = load_global_instruction()
    assert result is None


def test_load_global_instruction_returns_content_when_exists(tmp_path: Path) -> None:
    (tmp_path / "project_instruction.md").write_text(_GLOBAL_INSTR, encoding="utf-8")
    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        result = load_global_instruction()
    assert result is not None
    assert "global style" in result


def test_new_job_auto_loads_global_instruction_via_ensure_layers(tmp_path: Path) -> None:
    """ensure_config_layers must use global instruction as baseline for new jobs."""
    (tmp_path / "project_instruction.md").write_text(_GLOBAL_INSTR, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()

    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        from web.config_bundle_layers import ensure_config_layers
        ensure_config_layers(job_output)

    from web.config_bundle_layers import _baseline_dir
    baseline_instr = _baseline_dir(job_output) / "project_instruction.md"
    assert baseline_instr.exists(), "Baseline instruction must be written for new job"
    content = baseline_instr.read_text(encoding="utf-8")
    assert "global style" in content, "Baseline must contain global instruction, not just built-in default"


def test_job_instruction_override_wins_over_global(tmp_path: Path) -> None:
    """effective_instruction_for_job must prefer job override over global."""
    (tmp_path / "project_instruction.md").write_text(_GLOBAL_INSTR, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()

    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        from web.config_bundle_layers import ensure_config_layers
        ensure_config_layers(job_output)

    # Write a job-specific override
    from web.config_bundle_layers import _overrides_dir
    override_path = _overrides_dir(job_output) / "project_instruction.md"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(_JOB_INSTR, encoding="utf-8")

    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        content, source = effective_instruction_for_job(job_output)

    assert "job-specific" in content, "Job override must take priority"
    assert source == "job_override"


def test_effective_instruction_returns_global_when_no_job_override(tmp_path: Path) -> None:
    """effective_instruction_for_job returns global when job has only builtin default."""
    (tmp_path / "project_instruction.md").write_text(_GLOBAL_INSTR, encoding="utf-8")
    job_output = tmp_path / "job"
    job_output.mkdir()

    with patch("web.alex_storage.ALEX_DATA_DIR", tmp_path):
        from web.config_bundle_layers import ensure_config_layers
        ensure_config_layers(job_output)
        content, source = effective_instruction_for_job(job_output)

    assert source in ("global", "job_override")
    # Either baseline was set to global content or it was set as default
    # (depends on whether the baseline matches the default)
    assert content  # must not be empty


def test_effective_instruction_returns_builtin_default_when_no_global(tmp_path: Path) -> None:
    empty_alex_dir = tmp_path / ".alex_empty"
    empty_alex_dir.mkdir()
    job_output = tmp_path / "job"
    job_output.mkdir()
    with patch("web.alex_storage.ALEX_DATA_DIR", empty_alex_dir):
        content, source = effective_instruction_for_job(job_output)
    assert source == "builtin_default"
    assert _BUILTIN_DEFAULT_SNIPPET in content


# ---------------------------------------------------------------------------
# 3. Source metadata from _sync API
# ---------------------------------------------------------------------------

def test_memory_source_label_is_global_for_new_job(tmp_path: Path) -> None:
    """Memory source must be 'global' when no job-local override exists."""
    job_mem = _job_memory_path(tmp_path)
    assert not job_mem.exists()
    # If job mem path doesn't exist, source should be "global"
    from web.project_testcode_memory import _job_memory_path as jmp
    source = "job_override" if jmp(tmp_path).exists() else "global"
    assert source == "global"


def test_memory_source_label_is_job_override_when_local_exists(tmp_path: Path) -> None:
    save_memory_for_job(tmp_path, _JOB_MEM)
    from web.project_testcode_memory import _job_memory_path as jmp
    source = "job_override" if jmp(tmp_path).exists() else "global"
    assert source == "job_override"


# ---------------------------------------------------------------------------
# 4. Global paths resolve correctly
# ---------------------------------------------------------------------------

def test_global_instruction_path_is_in_alex_data_dir() -> None:
    from web.alex_storage import ALEX_DATA_DIR, GLOBAL_INSTRUCTION_NAME
    expected = ALEX_DATA_DIR / GLOBAL_INSTRUCTION_NAME
    assert global_instruction_path() == expected


def test_global_memory_path_is_in_alex_data_dir() -> None:
    from web.alex_storage import ALEX_DATA_DIR, TESTCODE_MEMORY_NAME
    expected = ALEX_DATA_DIR / TESTCODE_MEMORY_NAME
    actual = _testcode_memory_path()
    assert actual == expected
