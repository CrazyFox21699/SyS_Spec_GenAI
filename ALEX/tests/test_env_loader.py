from __future__ import annotations

import os
from pathlib import Path

from src.utils.env_loader import load_dotenv


def test_load_dotenv_sets_missing_vars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("M365_CLIENT_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nM365_CLIENT_SECRET=secret-from-file\nM365_CLIENT_ID=from-env\n",
        encoding="utf-8",
    )
    assert load_dotenv(env_file) is True
    assert os.environ["M365_CLIENT_SECRET"] == "secret-from-file"
    assert os.environ["M365_CLIENT_ID"] == "from-env"


def test_load_dotenv_does_not_override_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("M365_CLIENT_SECRET", "already-set")
    env_file = tmp_path / ".env"
    env_file.write_text("M365_CLIENT_SECRET=from-file\n", encoding="utf-8")
    load_dotenv(env_file)
    assert os.environ["M365_CLIENT_SECRET"] == "already-set"


def test_load_dotenv_missing_file(tmp_path: Path) -> None:
    assert load_dotenv(tmp_path / "missing.env") is False
