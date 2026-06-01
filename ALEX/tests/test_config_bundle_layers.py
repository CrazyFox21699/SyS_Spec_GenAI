"""Tests for layered config bundle propose/apply."""

from __future__ import annotations

from pathlib import Path

from web.config_bundle_layers import (
    add_learned_mapping,
    apply_config_bundle_proposal,
    build_effective_config,
    diff_config_bundle,
    export_effective_config_bundle,
    parse_config_bundle_markdown,
    propose_config_bundle,
    save_manual_config_edit,
)


def _bundle_md(extra_mapping: str = "") -> str:
    return f"""# ALEX Config Bundle

## code_rules.md

# Rules
- Use TEST_F

## signal_mapping.yaml

```yaml
mappings: {{}}
terms:
  SIG_NEW: SetSignal(SIG_NEW, 1)
{extra_mapping}
```

## api_catalog.yaml

```yaml
apis:
  - EXPECT_EQ
  - TEST_F
  - SetSignal
```

## gtest_template.md

Template notes

## ai_review_pack.md

[SUMMARY]
"""


def test_parse_bundle_sections() -> None:
    parsed = parse_config_bundle_markdown(_bundle_md())
    assert "code_rules.md" in parsed
    assert "SIG_NEW" in parsed["signal_mapping.yaml"]


def test_propose_does_not_overwrite_effective(tmp_path: Path) -> None:
    save_manual_config_edit(tmp_path, "code_rules.md", "# Baseline rules\n", target_layer="baseline")
    before = build_effective_config(tmp_path)["code_rules.md"]
    result = propose_config_bundle(tmp_path, _bundle_md())
    assert result["ok"]
    after = build_effective_config(tmp_path)["code_rules.md"]
    assert before == after
    assert any(c["kind"] == "mapping_added" for c in result.get("changes") or [])


def test_apply_safe_mapping_add(tmp_path: Path) -> None:
    propose_config_bundle(tmp_path, _bundle_md())
    applied = apply_config_bundle_proposal(tmp_path, mode="apply_all", allow_removals=False)
    assert applied["ok"]
    effective = build_effective_config(tmp_path)["signal_mapping.yaml"]
    assert "SIG_NEW" in effective


def test_learned_mapping_and_export(tmp_path: Path) -> None:
    add_learned_mapping(tmp_path, "PMODE_STS", "EXPECT_EQ(GetPmodeSts(), 1)")
    effective = build_effective_config(tmp_path)["signal_mapping.yaml"]
    assert "PMODE_STS" in effective
    exported = export_effective_config_bundle(tmp_path)
    assert exported["ok"]
    assert "code_rules.md" in exported["content"]


def test_diff_detects_mapping_conflict(tmp_path: Path) -> None:
    save_manual_config_edit(
        tmp_path,
        "signal_mapping.yaml",
        "mappings: {}\nterms:\n  SIG_A: override_code\n",
        target_layer="project_overrides",
    )
    md = _bundle_md().replace("SIG_NEW", "SIG_A").replace("SetSignal(SIG_NEW, 1)", "imported_code")
    md = md.replace(
        "terms:\n  SIG_A: SetSignal(SIG_NEW, 1)",
        "terms:\n  SIG_A: imported_code",
    )
    diff = diff_config_bundle(tmp_path, parse_config_bundle_markdown(md))
    conflicts = [c for c in diff["changes"] if c.get("conflict")]
    assert conflicts or any(c.get("kind") == "mapping_modified" for c in diff["changes"])
