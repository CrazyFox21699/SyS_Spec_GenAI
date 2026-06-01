"""Parser tolerance tests for alex_code_config_bundle.md imports."""

from __future__ import annotations

from pathlib import Path

from web.config_bundle_layers import (
    analyze_config_bundle,
    bundle_error_payload,
    extract_bundle_text_from_payload,
    parse_config_bundle_markdown,
    preview_config_bundle,
    propose_config_bundle,
)


def _sections_body() -> str:
    return """## code_rules.md

# Rules
- Use TEST_F

## signal_mapping.yaml

```yaml
terms:
  SIG_A: code_a
```

## api_catalog.yaml

```yaml
apis:
  - EXPECT_EQ
```
"""


def test_exact_marker_format_optional() -> None:
    md = f"""<!-- ALEX_CONFIG_BUNDLE_START -->
{_sections_body()}
<!-- ALEX_CONFIG_BUNDLE_END -->
"""
    a = analyze_config_bundle(md)
    assert "code_rules.md" in a["detected_sections"]
    assert "Bundle markers missing" not in " ".join(a["warnings"])


def test_missing_start_end_markers_with_sections() -> None:
    a = analyze_config_bundle(_sections_body())
    assert "code_rules.md" in a["detected_sections"]
    assert any("markers missing" in w.lower() for w in a["warnings"])


def test_numbered_headings() -> None:
    md = """## 1. code_rules.md

rule one

## 2. signal_mapping.yaml

```yaml
terms:
  X: y
```
"""
    parsed = parse_config_bundle_markdown(md)
    assert "code_rules.md" in parsed
    assert "signal_mapping.yaml" in parsed


def test_triple_hash_headings() -> None:
    md = """### code_rules.md

content

### api_catalog.yaml

```yaml
apis:
  - Foo
```
"""
    parsed = parse_config_bundle_markdown(md)
    assert "code_rules.md" in parsed
    assert "api_catalog.yaml" in parsed


def test_single_hash_heading() -> None:
    md = """# code_rules.md

only rules
"""
    parsed = parse_config_bundle_markdown(md)
    assert "code_rules.md" in parsed


def test_payload_keys_bundle_text_content() -> None:
    text = "## code_rules.md\n\nhello\n"
    for key in ("bundle", "text", "content", "bundle_markdown"):
        extracted, keys = extract_bundle_text_from_payload({key: text})
        assert extracted == text.strip()
        assert key in keys


def test_missing_sections_warning_not_crash(tmp_path: Path) -> None:
    md = "## code_rules.md\n\n# Only rules\n"
    preview = preview_config_bundle(tmp_path, md)
    assert preview["ok"]
    assert preview["detected_sections"] == ["code_rules.md"]
    assert "signal_mapping.yaml" in preview["missing_sections"]
    assert any("Partial bundle" in w for w in preview["warnings"])


def test_invalid_text_clear_error(tmp_path: Path) -> None:
    preview = preview_config_bundle(tmp_path, "   \n\nno sections here\n")
    assert preview["ok"] is False
    assert preview["error"]
    assert preview["details"]["detected_sections"] == []


def test_completely_invalid_payload_keys_in_error() -> None:
    err = bundle_error_payload("empty", text="", payload_keys=["foo"])
    assert err["details"]["payload_keys"] == ["foo"]


def test_preview_endpoint_partial_sections(tmp_path: Path) -> None:
    md = "## gtest_template.md\n\ntemplate body\n"
    preview = preview_config_bundle(tmp_path, md)
    assert preview["ok"]
    assert preview["partial_import_allowed"] is True
    assert "gtest_template.md" in preview["detected_sections"]


def test_propose_accepts_numbered_copilot_format(tmp_path: Path) -> None:
    md = """## 1. code_rules.md

- rule

## 2. signal_mapping.yaml

```yaml
terms:
  NEW: x
```
"""
    result = propose_config_bundle(tmp_path, md)
    assert result["ok"]
    assert "code_rules.md" in result.get("detected_sections", [])
