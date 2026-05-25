"""Tests for ALEX centralized storage paths."""

from __future__ import annotations

from pathlib import Path

from web.alex_storage import (
    migrate_legacy_alex_data,
    normalize_library_root,
)


def test_normalize_library_root_rejects_legacy() -> None:
    fixed = normalize_library_root("/old/pm_test_spec_assistant/input")
    assert "pm_test_spec_assistant" not in fixed
    assert "ALEX" in fixed


def test_alex_data_under_web_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("web.alex_storage.WEB_DATA", tmp_path / "web_data")
    monkeypatch.setattr("web.alex_storage.ALEX_DATA_DIR", tmp_path / "web_data" / ".alex")
    from web.alex_storage import ensure_alex_data_dir, gtest_preset_path

    ensure_alex_data_dir()
    assert gtest_preset_path().parent.name == ".alex"
    assert "web_data" in str(gtest_preset_path())


def test_migrate_legacy_alex_data(tmp_path: Path, monkeypatch) -> None:
    legacy = tmp_path / "input" / ".alex"
    legacy.mkdir(parents=True)
    (legacy / "gtest_harness_preset.yaml").write_text("kind: alex_gtest_preset\n", encoding="utf-8")
    monkeypatch.setattr("web.alex_storage.WEB_DATA", tmp_path / "web_data")
    monkeypatch.setattr("web.alex_storage.ALEX_DATA_DIR", tmp_path / "web_data" / ".alex")
    from web.alex_storage import gtest_preset_path

    names = migrate_legacy_alex_data(tmp_path / "input")
    assert "gtest_harness_preset.yaml" in names
    assert gtest_preset_path().exists()
