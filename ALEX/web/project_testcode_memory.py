"""Project Test Code Memory — global reusable markdown for Copilot code generation context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MEMORY_FILENAME = "project_testcode_memory.md"

DEFAULT_MEMORY = """\
# Project Test Code Memory

## Fixture / Test Style

## Input Mock Pattern

## Output Assertion Pattern

## Timing Pattern

## Known Signal Rules

## Allowed APIs / Forbidden APIs

## Reviewer Notes / Learned Fixes

## Temporary Regeneration Notes

## RTE API Map

## Entry Points / Call Order

## Mock Interface

## Mock Binding Pattern

## Fixture / Observable Variables

## Default Mock Behavior

## Representative Test Style

## Constants / Value Map

## Spec Signal to Test Code Map
"""

SECTIONS = [
    "Fixture / Test Style",
    "Input Mock Pattern",
    "Output Assertion Pattern",
    "Timing Pattern",
    "Known Signal Rules",
    "Allowed APIs / Forbidden APIs",
    "Reviewer Notes / Learned Fixes",
    "Temporary Regeneration Notes",
    "RTE API Map",
    "Entry Points / Call Order",
    "Mock Interface",
    "Mock Binding Pattern",
    "Fixture / Observable Variables",
    "Default Mock Behavior",
    "Representative Test Style",
    "Constants / Value Map",
    "Spec Signal to Test Code Map",
]

_SECTION_HEADER_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _global_path() -> Path:
    from web.alex_storage import ensure_alex_data_dir
    return ensure_alex_data_dir() / MEMORY_FILENAME


def _job_memory_path(job_output: Path) -> Path:
    from web.project_code_config import project_code_config_dir
    return project_code_config_dir(job_output) / MEMORY_FILENAME


def load_global_memory() -> str:
    path = _global_path()
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return DEFAULT_MEMORY


def save_global_memory(content: str) -> Path:
    path = _global_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or DEFAULT_MEMORY), encoding="utf-8")
    return path


def load_memory_for_job(job_output: Path) -> str:
    """Load job-local memory; fall back to global if no local copy exists."""
    local = _job_memory_path(job_output)
    if local.exists():
        try:
            return local.read_text(encoding="utf-8")
        except OSError:
            pass
    return load_global_memory()


def save_memory_for_job(job_output: Path, content: str) -> None:
    path = _job_memory_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or DEFAULT_MEMORY), encoding="utf-8")


def copy_global_to_job(job_output: Path) -> str:
    """Copy global memory into job if job has no local copy. Returns effective content."""
    local = _job_memory_path(job_output)
    if local.exists():
        try:
            return local.read_text(encoding="utf-8")
        except OSError:
            pass
    content = load_global_memory()
    save_memory_for_job(job_output, content)
    return content


def append_to_section(memory_content: str, section: str, note: str) -> str:
    """Append a bullet note to the given section. Creates section if missing."""
    content = str(memory_content or DEFAULT_MEMORY)
    note_line = f"- {note.strip()}"

    # Find section header
    pattern = re.compile(rf"^## {re.escape(section)}\s*$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(content)
    if not m:
        content = content.rstrip() + f"\n\n## {section}\n{note_line}\n"
        return content

    # Find insertion point: end of this section (before next ## or EOF)
    after_header = content[m.end():]
    next_section = re.search(r"^## ", after_header, re.MULTILINE)
    if next_section:
        insert_at = m.end() + next_section.start()
        section_body = content[m.end(): insert_at]
        new_body = section_body.rstrip() + f"\n{note_line}\n\n"
        content = content[: m.end()] + new_body + content[insert_at:]
    else:
        content = content.rstrip() + f"\n{note_line}\n"

    return content


def extract_patterns_from_sample(code: str) -> dict[str, Any]:
    """Deterministically extract fixture/mock/assertion/timing patterns from .cc sample."""
    text = str(code or "")

    # Fixture names
    fixtures = list(dict.fromkeys(re.findall(r"\bTEST_F\s*\(\s*(\w+)", text)))[:5]

    # Input mock / EXPECT_CALL patterns — collect unique function names
    expect_call_fns = list(dict.fromkeys(
        re.findall(r"\bEXPECT_CALL\s*\([^,)]+,\s*(\w+)", text)
    ))[:8]
    rte_reads = list(dict.fromkeys(re.findall(r"\bRte_Read_(\w+)", text)))[:8]
    rte_writes = list(dict.fromkeys(re.findall(r"\bRte_Write_(\w+)", text)))[:6]

    # Assertion patterns
    expect_that = list(dict.fromkeys(re.findall(r"\bEXPECT_(?:THAT|EQ|NE|TRUE|FALSE)\b", text)))[:5]
    out_vars = list(dict.fromkeys(re.findall(r"\bout\.(\w+)", text)))[:8]
    in_vars = list(dict.fromkeys(re.findall(r"\bin\.(\w+)", text)))[:8]

    # Timing patterns
    timing_fns = list(dict.fromkeys(
        re.findall(r"\b(RunForMs|WaitMs|igsw_Main_Run|advance_time|AdvanceTime|RunCycles)\b", text)
    ))[:6]
    timing_calls = []
    for fn in timing_fns[:3]:
        for m in re.finditer(rf"\b{re.escape(fn)}\s*\([^)]*\)", text):
            timing_calls.append(m.group(0)[:80])
            break

    # Allowed API calls (non-standard, excluding common builtins)
    _builtins = {"TEST_F", "TEST", "EXPECT_EQ", "EXPECT_NE", "EXPECT_TRUE",
                 "EXPECT_FALSE", "EXPECT_THAT", "EXPECT_CALL", "if", "for",
                 "while", "return", "class", "void", "int", "auto", "bool"}
    all_calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    unique_calls = list(dict.fromkeys(c for c in all_calls if c not in _builtins))[:12]

    return {
        "fixtures": fixtures,
        "expect_call_fns": expect_call_fns,
        "rte_reads": rte_reads,
        "rte_writes": rte_writes,
        "assertion_macros": expect_that,
        "out_vars": out_vars,
        "in_vars": in_vars,
        "timing_fns": timing_fns,
        "timing_calls": timing_calls,
        "api_calls": unique_calls,
    }


def build_proposed_memory(extraction: dict[str, Any], source_file: str = "") -> str:
    """Build proposed memory markdown from extraction result. Does not overwrite — shows additions."""
    ex = extraction
    lines: list[str] = [f"# Project Test Code Memory\n"]
    src_note = f" (extracted from {source_file})" if source_file else ""

    lines.append("## Fixture / Test Style\n")
    for f in ex.get("fixtures") or []:
        lines.append(f"- Fixture class: `{f}`")
    if not ex.get("fixtures"):
        lines.append("- (no TEST_F found in sample)")
    lines.append("")

    lines.append("## Input Mock Pattern\n")
    for fn in ex.get("expect_call_fns") or []:
        lines.append(f"- EXPECT_CALL mock function: `{fn}`")
    for r in ex.get("rte_reads") or []:
        lines.append(f"- RTE read: `Rte_Read_{r}`")
    for w in ex.get("rte_writes") or []:
        lines.append(f"- RTE write: `Rte_Write_{w}`")
    for v in ex.get("in_vars") or []:
        lines.append(f"- Input member: `in.{v}`")
    if not any([ex.get("expect_call_fns"), ex.get("rte_reads"), ex.get("in_vars")]):
        lines.append("- (no EXPECT_CALL or in.* patterns found)")
    lines.append("")

    lines.append("## Output Assertion Pattern\n")
    for macro in ex.get("assertion_macros") or []:
        lines.append(f"- Uses `{macro}` for assertions")
    for v in ex.get("out_vars") or []:
        lines.append(f"- Output member: `out.{v}`")
    if not any([ex.get("assertion_macros"), ex.get("out_vars")]):
        lines.append("- (no assertion patterns found)")
    lines.append("")

    lines.append("## Timing Pattern\n")
    for fn in ex.get("timing_fns") or []:
        lines.append(f"- Timing function: `{fn}`")
    for call in ex.get("timing_calls") or []:
        lines.append(f"- Example call: `{call}`")
    if not any([ex.get("timing_fns"), ex.get("timing_calls")]):
        lines.append("- (no timing patterns found)")
    lines.append("")

    lines.append("## Known Signal Rules\n\n")

    lines.append("## Allowed APIs / Forbidden APIs\n")
    if ex.get("api_calls"):
        lines.append(f"- Known APIs from sample{src_note}: " + ", ".join(f"`{a}`" for a in ex["api_calls"][:10]))
    else:
        lines.append("- (no API calls extracted)")
    lines.append("")

    lines.append("## Reviewer Notes / Learned Fixes\n\n")
    lines.append("## Temporary Regeneration Notes\n")

    return "\n".join(lines)


def merge_proposed_into_memory(existing: str, proposed: str) -> str:
    """Merge proposed memory into existing: append non-empty sections from proposed."""
    existing_content = str(existing or DEFAULT_MEMORY)

    for section in SECTIONS:
        section_re = re.compile(rf"^## {re.escape(section)}\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
        proposed_m = section_re.search(proposed)
        if not proposed_m:
            continue
        proposed_body = proposed_m.group(1).strip()
        if not proposed_body:
            continue
        # Check if existing section is empty
        existing_m = section_re.search(existing_content)
        if existing_m:
            existing_body = existing_m.group(1).strip()
            if not existing_body:
                # Empty section in existing → replace with proposed
                new_section = f"## {section}\n\n{proposed_body}\n\n"
                existing_content = existing_content[:existing_m.start()] + new_section + existing_content[existing_m.end():]
            else:
                # Non-empty section: append proposed bullets as additional notes
                bullets = [l for l in proposed_body.splitlines() if l.strip().startswith("-")]
                for bullet in bullets:
                    if bullet.strip("- ").strip() not in existing_content:
                        existing_content = append_to_section(existing_content, section, bullet.lstrip("- ").strip())
        else:
            existing_content = existing_content.rstrip() + f"\n\n## {section}\n\n{proposed_body}\n"

    return existing_content


def _section_body(content: str, section: str) -> str:
    """Return the body text of a section (between its ## header and the next ## or EOF)."""
    pattern = re.compile(rf"^## {re.escape(section)}\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(str(content or ""))
    return m.group(1).strip() if m else ""


def _bullet_key(bullet: str) -> str:
    """Normalise a bullet line for duplicate detection."""
    return re.sub(r"\s+", " ", bullet.lstrip("-").strip().lower())


def dedupe_memory(content: str) -> str:
    """Remove duplicate bullets within each section."""
    result = str(content or "")
    for section in SECTIONS:
        body = _section_body(result, section)
        if not body:
            continue
        seen: set[str] = set()
        new_lines: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("-"):
                key = _bullet_key(stripped)
                if key in seen:
                    continue
                seen.add(key)
            new_lines.append(line)
        new_body = "\n".join(new_lines).strip()
        # Replace section body
        pattern = re.compile(rf"(^## {re.escape(section)}\s*$)(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
        m = pattern.search(result)
        if m:
            result = result[:m.start()] + m.group(1) + "\n\n" + new_body + "\n\n" + result[m.end():]
    return result


def detect_memory_conflicts(existing: str, proposed: str) -> list[dict[str, Any]]:
    """Return list of conflicts where proposed would overwrite existing non-empty bullets.

    Each conflict: {section, existing_value, proposed_value, conflict_type}.
    """
    conflicts: list[dict[str, Any]] = []
    for section in SECTIONS:
        ex_body = _section_body(existing, section)
        pr_body = _section_body(proposed, section)
        if not ex_body or not pr_body:
            continue
        ex_bullets = {_bullet_key(l): l.strip() for l in ex_body.splitlines() if l.strip().startswith("-")}
        pr_bullets = {_bullet_key(l): l.strip() for l in pr_body.splitlines() if l.strip().startswith("-")}
        # Detect signal/API-specific conflicts: same first token (e.g. signal name) with different value
        for pr_key, pr_line in pr_bullets.items():
            if pr_key in ex_bullets:
                ex_line = ex_bullets[pr_key]
                if ex_line.lower().strip() != pr_line.lower().strip():
                    conflicts.append({
                        "section": section,
                        "existing_value": ex_line,
                        "proposed_value": pr_line,
                        "conflict_type": "value_differs",
                    })
            else:
                # Check if a similar key (signal name) is mapped differently
                # Extract first significant word after "Signal:" or "API:" etc.
                sig_m = re.search(r"Signal:\s*`?(\w+)`?|API:\s*`?(\w+)`?", pr_line, re.IGNORECASE)
                if sig_m:
                    sig = sig_m.group(1) or sig_m.group(2)
                    for ex_key, ex_line in ex_bullets.items():
                        if sig.lower() in ex_key and ex_key != pr_key:
                            conflicts.append({
                                "section": section,
                                "existing_value": ex_line,
                                "proposed_value": pr_line,
                                "conflict_type": "same_signal_different_mapping",
                            })
    return conflicts


def merge_with_conflict_check(existing: str, proposed: str) -> dict[str, Any]:
    """Merge proposed into existing, detecting conflicts before applying.

    Returns: {merged, conflicts, duplicate_count}.
    DOES NOT apply conflicting bullets automatically — caller decides.
    """
    conflicts = detect_memory_conflicts(existing, proposed)
    # Identify which proposed bullets are already in existing (duplicates)
    duplicate_count = 0
    existing_lower = (existing or "").lower()
    for section in SECTIONS:
        pr_body = _section_body(proposed, section)
        for line in pr_body.splitlines():
            if line.strip().startswith("-"):
                key = _bullet_key(line)
                if key in existing_lower:
                    duplicate_count += 1

    # Build merged: skip conflicting and duplicate bullets
    conflict_proposed = {c["proposed_value"].lower().strip() for c in conflicts}
    merged = str(existing or DEFAULT_MEMORY)
    for section in SECTIONS:
        pr_body = _section_body(proposed, section)
        if not pr_body:
            continue
        ex_body = _section_body(merged, section)
        for line in pr_body.splitlines():
            if not line.strip().startswith("-"):
                continue
            key = _bullet_key(line)
            # Skip duplicates and conflicts
            if key in (merged or "").lower():
                continue
            if line.strip().lower() in conflict_proposed:
                continue
            merged = append_to_section(merged, section, line.lstrip("- ").strip())

    merged = dedupe_memory(merged)
    return {
        "merged": merged,
        "conflicts": conflicts,
        "duplicate_count": duplicate_count,
        "conflict_count": len(conflicts),
    }


# ---------------------------------------------------------------------------
# Quick Add rule types — structured bullet generation
# ---------------------------------------------------------------------------

#: Maps rule_type key → (section_name, human_label, fields_spec)
QUICK_ADD_RULE_TYPES: dict[str, dict[str, Any]] = {
    "input_mock": {
        "section": "Input Mock Pattern",
        "label": "Input / Mock Rule",
        "fields": [
            {"key": "signal", "label": "Signal name", "placeholder": "e.g. APOK2", "required": True},
            {"key": "mock_api", "label": "Mock/API pattern", "placeholder": "e.g. Rte_Read_COMRX_APOK2"},
            {"key": "default_value", "label": "Default value (optional)", "placeholder": "e.g. 0"},
        ],
    },
    "output_assertion": {
        "section": "Output Assertion Pattern",
        "label": "Output / Assertion Rule",
        "fields": [
            {"key": "output_var", "label": "Output variable", "placeholder": "e.g. V_PMODE_STS", "required": True},
            {"key": "assertion_pattern", "label": "Assertion pattern", "placeholder": "e.g. EXPECT_THAT(V_PMODE_STS, Eq({expected}))"},
        ],
    },
    "timing": {
        "section": "Timing Pattern",
        "label": "Timing Rule",
        "fields": [
            {"key": "timing_name", "label": "Timing name", "placeholder": "e.g. T7", "required": True},
            {"key": "execution_pattern", "label": "Execution pattern", "placeholder": "e.g. repeated igsw_Main_Run() in for-loop"},
        ],
    },
    "fixture_style": {
        "section": "Fixture / Test Style",
        "label": "Fixture / Test Style Rule",
        "fields": [
            {"key": "fixture_name", "label": "Fixture name", "placeholder": "e.g. TryToChangeOnToOffTest", "required": True},
            {"key": "scope_note", "label": "Scope / note", "placeholder": "e.g. for this testcase group unless specified otherwise"},
        ],
    },
    "signal_mapping": {
        "section": "Spec Signal to Test Code Map",
        "label": "API / Signal Mapping Rule",
        "fields": [
            {"key": "signal", "label": "Spec signal", "placeholder": "e.g. DRDYSTS", "required": True},
            {"key": "rte_api", "label": "RTE API", "placeholder": "e.g. Rte_Read_COMRX_DRDYSTS", "required": True},
            {"key": "direction", "label": "Direction (INPUT/OUTPUT/SERVICE)", "placeholder": "INPUT"},
        ],
    },
    "forbidden_pattern": {
        "section": "Allowed APIs / Forbidden APIs",
        "label": "Forbidden Pattern",
        "fields": [
            {"key": "pattern", "label": "Pattern / API name", "placeholder": "e.g. WaitMs()", "required": True},
            {"key": "reason", "label": "Reason", "placeholder": "e.g. not present in sample code"},
        ],
    },
    "reviewer_note": {
        "section": "Reviewer Notes / Learned Fixes",
        "label": "Reviewer Note / Learned Fix",
        "fields": [
            {"key": "note", "label": "Note", "placeholder": "e.g. If API uncertain, use TODO_REVIEW at missing line", "required": True},
        ],
    },
}


def format_quick_add_rule(rule_type: str, fields: dict[str, str], *, source_tag: bool = True) -> str:
    """Generate a structured bullet string for a given rule type and field values."""
    tag = "[source: quick_add] " if source_tag else ""
    f = {k: str(v or "").strip() for k, v in fields.items()}

    if rule_type == "input_mock":
        sig = f.get("signal") or "SIGNAL"
        api = f.get("mock_api") or f"Rte_Read_COMRX_{sig}"
        val = f.get("default_value") or "{value}"
        return (
            f"{tag}Input signal `{sig}` should be mocked by "
            f"`EXPECT_CALL(rte, {api}(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({val}), Return(RTE_E_OK)))`."
        )

    if rule_type == "output_assertion":
        var = f.get("output_var") or "OUTPUT_VAR"
        pat = f.get("assertion_pattern") or f"EXPECT_THAT({var}, Eq({{expected}}))"
        return f"{tag}Output `{var}` should be asserted by `{pat}`."

    if rule_type == "timing":
        name = f.get("timing_name") or "T"
        pat = f.get("execution_pattern") or "repeated `igsw_Main_Run()` calls in a for-loop"
        return f"{tag}Timing `{name}` should be simulated by {pat}."

    if rule_type == "fixture_style":
        fix = f.get("fixture_name") or "TestFixture"
        scope = f.get("scope_note") or "for this testcase group unless specified otherwise"
        return f"{tag}Use fixture `{fix}` {scope}."

    if rule_type == "signal_mapping":
        sig = f.get("signal") or "SIGNAL"
        api = f.get("rte_api") or f"Rte_Read_{sig}"
        direction = (f.get("direction") or "INPUT").upper()
        return f"{tag}Spec signal `{sig}` maps to RTE API `{api}` as {direction}."

    if rule_type == "forbidden_pattern":
        pat = f.get("pattern") or "unknown_api()"
        reason = f.get("reason") or "not in sample or project memory"
        return f"{tag}Do not use `{pat}`. Reason: {reason}."

    if rule_type == "reviewer_note":
        note = f.get("note") or ""
        return f"{tag}{note}" if note else ""

    # Fallback: generic free-text
    note = " ".join(v for v in f.values() if v)
    return f"{tag}{note}" if note else ""


def rule_type_section(rule_type: str) -> str:
    """Return the target memory section for a rule type."""
    spec = QUICK_ADD_RULE_TYPES.get(rule_type) or {}
    return str(spec.get("section") or "Reviewer Notes / Learned Fixes")


def check_before_append(memory_content: str, section: str, bullet: str) -> dict[str, Any]:
    """Check for duplicates and conflicts before inserting a bullet.

    Returns:
        is_duplicate: bool — exact (normalised) match already exists
        conflicts: list — bullets with same signal/key but different value
        bullet: str — the normalised bullet text
    """
    content = str(memory_content or "")
    normalized = _bullet_key(bullet)
    body = _section_body(content, section)

    # Exact duplicate
    existing_bullets = [l.strip() for l in body.splitlines() if l.strip().startswith("-")]
    is_duplicate = any(_bullet_key(b) == normalized for b in existing_bullets)

    # Conflict: same signal name, different value
    conflicts: list[dict[str, str]] = []
    sig_m = re.search(r"`([A-Za-z_][A-Za-z0-9_]*)`", bullet)
    if sig_m and not is_duplicate:
        target_sig = sig_m.group(1).lower()
        for ex_bullet in existing_bullets:
            ex_sig_m = re.search(r"`([A-Za-z_][A-Za-z0-9_]*)`", ex_bullet)
            if ex_sig_m and ex_sig_m.group(1).lower() == target_sig:
                if _bullet_key(ex_bullet) != normalized:
                    conflicts.append({
                        "existing": ex_bullet,
                        "proposed": bullet,
                        "conflict_type": "same_signal_different_rule",
                    })

    return {
        "is_duplicate": is_duplicate,
        "conflicts": conflicts,
        "bullet": bullet,
        "section": section,
    }


# Priority sections for compact memory output in prompts
PROMPT_PRIORITY_SECTIONS = [
    "Spec Signal to Test Code Map",
    "Input Mock Pattern",
    "Output Assertion Pattern",
    "Timing Pattern",
    "Fixture / Test Style",
    "Reviewer Notes / Learned Fixes",
    "Representative Test Style",
    "RTE API Map",
    "Default Mock Behavior",
    "Entry Points / Call Order",
    "Mock Interface",
    "Mock Binding Pattern",
    "Fixture / Observable Variables",
    "Constants / Value Map",
    "Allowed APIs / Forbidden APIs",
    "Known Signal Rules",
    "Temporary Regeneration Notes",
]


def memory_for_prompt_prioritized(content: str, *, char_limit: int = 3000) -> str:
    """Return memory content for Copilot prompt, ordering high-value sections first.

    Quick-add tagged lines (containing [source: quick_add]) are never trimmed
    before generic prose or extracted content.
    """
    text = str(content or "").strip()
    if not text or text == DEFAULT_MEMORY.strip():
        return ""
    content_lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not content_lines:
        return ""

    # Build prioritized output: ordered sections
    parts: list[str] = []
    seen_sections: set[str] = set()
    for section in PROMPT_PRIORITY_SECTIONS:
        body = _section_body(text, section)
        if body:
            parts.append(f"## {section}\n{body}")
            seen_sections.add(section)
    # Add any remaining sections not in priority list
    for m in re.finditer(r"^## (.+)$", text, re.MULTILINE):
        s = m.group(1).strip()
        if s not in seen_sections:
            body = _section_body(text, s)
            if body:
                parts.append(f"## {s}\n{body}")

    reordered = "# Project Test Code Memory\n\n" + "\n\n".join(parts)
    if len(reordered) <= char_limit:
        return reordered

    # Over budget: keep quick_add lines, trim non-tagged prose
    output_parts: list[str] = []
    remaining = char_limit - 30  # header reserve
    for part in parts:
        if remaining <= 0:
            break
        lines = part.splitlines()
        kept: list[str] = []
        for line in lines:
            if not line.strip():
                kept.append(line)
                continue
            # Always keep quick_add lines and section headers
            if "[source: quick_add]" in line or line.startswith("##"):
                kept.append(line)
            elif remaining > len(line):
                kept.append(line)
                remaining -= len(line)
        block = "\n".join(kept).strip()
        if block and block != part.splitlines()[0]:  # not just a header
            output_parts.append(block)
            remaining -= len(block)

    result = "# Project Test Code Memory\n\n" + "\n\n".join(output_parts)
    return result if result.strip() != "# Project Test Code Memory" else ""


def memory_for_prompt(content: str, *, char_limit: int = 3000) -> str:
    """Return memory clipped for Copilot prompt use. Returns empty if no real content."""
    text = str(content or "").strip()
    if not text or text == DEFAULT_MEMORY.strip():
        return ""
    # Skip if only section headers with no actual content (bullet points or prose)
    content_lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not content_lines:
        return ""
    if len(text) <= char_limit:
        return text
    return text[:char_limit].rstrip() + "\n...[memory trimmed]"
