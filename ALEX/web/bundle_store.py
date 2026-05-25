"""Split bundle persistence with overlay versioning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.yaml_utils import dump_yaml, load_yaml

MANIFEST_NAME = "manifest.json"
CANDIDATES_NAME = "candidates.json"
LOGIC_BLOCKS_NAME = "logic_blocks.json"
RESOLVED_NAME = "resolved_logic_blocks.json"
OVERLAYS_NAME = "overlays.json"
GTEST_NAME = "gtest.json"


def bundle_dir(job_output: Path) -> Path:
    d = job_output / "bundle"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_split_bundle(job_output: Path, bundle: dict[str, Any]) -> int:
    """Write split artifacts; return new bundle_version."""
    bdir = bundle_dir(job_output)
    manifest_path = bdir / MANIFEST_NAME
    version = 1
    if manifest_path.exists():
        try:
            version = int(json.loads(manifest_path.read_text(encoding="utf-8")).get("version", 0)) + 1
        except (json.JSONDecodeError, ValueError):
            version = 1

    manifest = {
        "version": version,
        "product": bundle.get("product"),
        "strict_mode": bundle.get("strict_mode"),
        "summary": bundle.get("summary"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    (bdir / CANDIDATES_NAME).write_text(
        json.dumps(bundle.get("test_candidates") or [], indent=2), encoding="utf-8"
    )
    (bdir / LOGIC_BLOCKS_NAME).write_text(
        json.dumps(bundle.get("logic_blocks") or [], indent=2), encoding="utf-8"
    )
    (bdir / RESOLVED_NAME).write_text(
        json.dumps(bundle.get("resolved_logic_blocks") or [], indent=2), encoding="utf-8"
    )

    overlays = (bundle.get("ai_assists") or {}).get("candidate_overlays") or {}
    overlay_path = bdir / OVERLAYS_NAME
    overlay_data: dict[str, Any] = {}
    if overlay_path.exists():
        try:
            overlay_data = json.loads(overlay_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            overlay_data = {}
    overlay_data.update(overlays)
    overlay_data["_version"] = version
    overlay_path.write_text(json.dumps(overlay_data, indent=2), encoding="utf-8")

    gtest = (bundle.get("ai_assists") or {}).get("gtest_bundle") or {}
    if not gtest:
        gtest = {
            "harness": (bundle.get("ai_assists") or {}).get("gtest_harness") or {},
            "code_variable_map": (bundle.get("ai_assists") or {}).get("code_variable_map") or {},
            "drafts": (bundle.get("ai_assists") or {}).get("gtest_drafts") or {},
        }
    if gtest.get("harness") or gtest.get("code_variable_map") or gtest.get("drafts"):
        (bdir / GTEST_NAME).write_text(json.dumps(gtest, indent=2), encoding="utf-8")

    dump_yaml(job_output / "ui_bundle.yaml", bundle)
    return version


def load_split_bundle(job_output: Path) -> dict[str, Any] | None:
    """Load full bundle from ui_bundle.yaml or reassemble from split."""
    legacy = job_output / "ui_bundle.yaml"
    if legacy.exists():
        return load_yaml(legacy)
    bdir = job_output / "bundle"
    if not (bdir / MANIFEST_NAME).exists():
        return None
    bundle: dict[str, Any] = {}
    try:
        bundle["product"] = json.loads((bdir / MANIFEST_NAME).read_text(encoding="utf-8")).get("product")
        bundle["test_candidates"] = json.loads((bdir / CANDIDATES_NAME).read_text(encoding="utf-8"))
        bundle["logic_blocks"] = json.loads((bdir / LOGIC_BLOCKS_NAME).read_text(encoding="utf-8"))
        if (bdir / RESOLVED_NAME).exists():
            bundle["resolved_logic_blocks"] = json.loads((bdir / RESOLVED_NAME).read_text(encoding="utf-8"))
        ov = json.loads((bdir / OVERLAYS_NAME).read_text(encoding="utf-8"))
        bundle["ai_assists"] = {"candidate_overlays": {k: v for k, v in ov.items() if not k.startswith("_")}}
        if (bdir / GTEST_NAME).exists():
            gtest = json.loads((bdir / GTEST_NAME).read_text(encoding="utf-8"))
            bundle.setdefault("ai_assists", {})
            bundle["ai_assists"]["gtest_harness"] = gtest.get("harness") or {}
            bundle["ai_assists"]["code_variable_map"] = gtest.get("code_variable_map") or {}
            bundle["ai_assists"]["gtest_drafts"] = gtest.get("drafts") or {}
    except (json.JSONDecodeError, OSError):
        return None
    return bundle


def update_overlay(
    job_output: Path,
    candidate_id: str,
    overlay: dict[str, Any],
    *,
    expected_version: int | None = None,
) -> int:
    """Merge one candidate overlay with optimistic version check."""
    bdir = bundle_dir(job_output)
    overlay_path = bdir / OVERLAYS_NAME
    data: dict[str, Any] = {}
    if overlay_path.exists():
        data = json.loads(overlay_path.read_text(encoding="utf-8"))
    current_version = int(data.get("_version", 0))
    if expected_version is not None and expected_version != current_version:
        raise ValueError(f"Overlay version conflict: expected {expected_version}, got {current_version}")
    data[candidate_id] = overlay
    data["_version"] = current_version + 1
    overlay_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    manifest_path = bdir / MANIFEST_NAME
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = data["_version"]
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass
    return data["_version"]
