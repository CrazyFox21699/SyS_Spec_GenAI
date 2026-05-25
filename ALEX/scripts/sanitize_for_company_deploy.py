#!/usr/bin/env python3
"""Remove local/personal runtime data before packaging ALEX for company deployment.

Deletes OAuth sessions, analysis jobs, uploads, library paths tied to this
machine, and other artifacts that must not travel to another computer.

Usage (from ALEX/):

    python scripts/sanitize_for_company_deploy.py
    python scripts/sanitize_for_company_deploy.py --dry-run

After running, zip or copy the ALEX folder to the company machine. Credentials are
never stored in-repo; see README.md for the full checklist.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web_data"

# Directories wiped entirely (recreated empty). Never ship contents to another org.
WIPE_DIRS = [
    WEB_DATA / "m365",
    WEB_DATA / "output",
    WEB_DATA / "uploads",
    WEB_DATA / "copilot_knowledge",
    WEB_DATA / "library_files",  # copied drop targets from Library tab
]

# Repo hygiene — safe to delete before packaging source.
CLEANUP_GLOBS = [
    ROOT / ".pytest_cache",
    ROOT / ".mypy_cache",
    ROOT / ".ruff_cache",
]

EMPTY_LIBRARY_YAML = """version: '3'
root: ''
focus_id: ''
items: []
links: []
"""

# Fields reset in config.yaml if they look like secrets or personal Azure IDs.
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _log(msg: str, *, dry_run: bool) -> None:
    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}{msg}")


def _rm_path(path: Path, *, dry_run: bool) -> None:
    if not path.exists():
        return
    if path.is_dir():
        _log(f"remove dir:  {path}", dry_run=dry_run)
        if not dry_run:
            shutil.rmtree(path)
    else:
        _log(f"remove file: {path}", dry_run=dry_run)
        if not dry_run:
            path.unlink()


def _wipe_dir_keep_gitkeep(target: Path, *, dry_run: bool) -> None:
    if not target.exists():
        _log(f"mkdir: {target}", dry_run=dry_run)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
        return
    for child in target.iterdir():
        if child.name == ".gitkeep":
            continue
        _rm_path(child, dry_run=dry_run)


def _reset_library_yaml(*, dry_run: bool) -> None:
    lib = WEB_DATA / "library.yaml"
    _log(f"reset: {lib}", dry_run=dry_run)
    if not dry_run:
        WEB_DATA.mkdir(parents=True, exist_ok=True)
        lib.write_text(EMPTY_LIBRARY_YAML, encoding="utf-8")


def _scrub_config_yaml(*, dry_run: bool) -> None:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        return
    text = cfg_path.read_text(encoding="utf-8")
    original = text
    # Blank inline client_id if someone pasted a GUID into config.yaml.
    lines: list[str] = []
    in_m365 = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("m365:"):
            in_m365 = True
        elif in_m365 and stripped and not line.startswith(" ") and not line.startswith("\t"):
            in_m365 = False
        if in_m365 and stripped.startswith("client_id:"):
            val = stripped.split(":", 1)[1].strip().strip("'\"")
            if val and GUID_RE.match(val):
                line = re.sub(r"client_id:\s*.*", 'client_id: ""', line)
        if in_m365 and stripped.startswith("client_secret:"):
            val = stripped.split(":", 1)[1].strip().strip("'\"")
            if val:
                line = re.sub(r"client_secret:\s*.*", 'client_secret: ""', line)
        lines.append(line)
    text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    if text != original:
        _log(f"scrub client_id in {cfg_path}", dry_run=dry_run)
        if not dry_run:
            cfg_path.write_text(text, encoding="utf-8")


def _remove_pycache(*, dry_run: bool) -> None:
    for pyc in ROOT.rglob("__pycache__"):
        _rm_path(pyc, dry_run=dry_run)
    for pyc in ROOT.rglob("*.pyc"):
        _rm_path(pyc, dry_run=dry_run)
    for cache in CLEANUP_GLOBS:
        _rm_path(cache, dry_run=dry_run)
    for ds in ROOT.rglob(".DS_Store"):
        _rm_path(ds, dry_run=dry_run)


def _scan_for_leaks(*, dry_run: bool) -> list[str]:
    """Warn about files that still contain home-directory paths or tokens."""
    warnings: list[str] = []
    home = str(Path.home())
    if not home or home == "/":
        return warnings
    scan_roots = [ROOT / "config.yaml", WEB_DATA / "library.yaml"]
    token_markers = ("access_token", "refresh_token", "device_code", "client_secret")
    for path in scan_roots:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if home in text:
            warnings.append(f"{path}: still contains home path `{home}`")
        for marker in token_markers:
            if marker in text and path.name != "sanitize_for_company_deploy.py":
                warnings.append(f"{path}: contains `{marker}` — review manually")
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitize ALEX before company deployment.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without deleting.")
    parser.add_argument(
        "--keep-venv",
        action="store_true",
        help="Do not remove .venv (default: remove — recipient should create their own venv).",
    )
    args = parser.parse_args(argv)
    dry = args.dry_run

    _log("=== ALEX company deploy sanitizer ===", dry_run=dry)
    _log(f"Project root: {ROOT}", dry_run=dry)

    for d in WIPE_DIRS:
        _wipe_dir_keep_gitkeep(d, dry_run=dry)

    _reset_library_yaml(dry_run=dry)
    _scrub_config_yaml(dry_run=dry)
    _remove_pycache(dry_run=dry)

    venv = ROOT / ".venv"
    if venv.exists() and not args.keep_venv:
        _log(
            "remove .venv (use --keep-venv to retain; company machine should pip install fresh)",
            dry_run=dry,
        )
        if not dry:
            shutil.rmtree(venv)

    if not dry:
        for d in WIPE_DIRS:
            d.mkdir(parents=True, exist_ok=True)
            gitkeep = d / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

    warnings = _scan_for_leaks(dry_run=dry)
    _log("", dry_run=dry)
    _log("=== Outside this folder (manual — not deleted by this script) ===", dry_run=dry)
    for line in [
        "~/.copilot/config.json          GitHub Copilot CLI session",
        "gh auth status                  GitHub CLI login on this Mac",
        "Browser localStorage (job_id)   cleared when using a fresh browser profile",
        "Ollama models                   ~/.ollama — not part of ALEX package",
        "sample_inputs/  optional demo files — omit from zip if customer data",
    ]:
        _log(f"  • {line}", dry_run=dry)

    if warnings:
        _log("", dry_run=dry)
        _log("=== Review these before zipping ===", dry_run=dry)
        for w in warnings:
            _log(f"  ! {w}", dry_run=dry)
        return 1

    _log("", dry_run=dry)
    _log("Done. Safe to zip ALEX/ for company setup.", dry_run=dry)
    _log("See README.md for recipient checklist.", dry_run=dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
