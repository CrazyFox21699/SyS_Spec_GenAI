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

## Test Group Context
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
    "Test Group Context",
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


def _has_real_content(text: str) -> bool:
    """True if text has at least one non-empty, non-header content line (bullet or prose)."""
    for line in (text or "").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("---") and not s.startswith("==="):
            return True
    return False


def load_memory_for_job(job_output: Path) -> str:
    """Load job-local memory; fall back to global when job file is empty/skeleton."""
    local = _job_memory_path(job_output)
    if local.exists():
        try:
            content = local.read_text(encoding="utf-8")
            if _has_real_content(content):
                return content
        except OSError:
            pass
    return load_global_memory()


def save_memory_for_job(job_output: Path, content: str) -> None:
    path = _job_memory_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or DEFAULT_MEMORY), encoding="utf-8")


def copy_global_to_job(job_output: Path) -> str:
    """Return effective memory for job: job if non-empty, otherwise global.

    When job file is just the default skeleton (section headers, no bullets),
    global memory is used so user-added global rules are immediately available.
    """
    local = _job_memory_path(job_output)
    if local.exists():
        try:
            content = local.read_text(encoding="utf-8")
            if _has_real_content(content):
                return content
        except OSError:
            pass
    global_content = load_global_memory()
    if _has_real_content(global_content):
        save_memory_for_job(job_output, global_content)
    return global_content


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
    "group_context": {
        "section": "Test Group Context",
        "label": "Test Group Context",
        "fields": [
            {"key": "group_name", "label": "Group name (from testcase)", "placeholder": "e.g. Power mode / state behavior", "required": True},
            {"key": "fixture_class", "label": "Fixture class", "placeholder": "e.g. TrytoDo", "required": True},
            {"key": "namespace", "label": "Namespace (optional)", "placeholder": "e.g. PowerMode"},
            {"key": "main_function", "label": "Main function (optional)", "placeholder": "e.g. igsw_Main_Run()"},
            {"key": "note", "label": "Note (optional)", "placeholder": "e.g. State machine group"},
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

    if rule_type == "group_context":
        from web.test_group_context import format_group_context_block
        group_name = f.get("group_name") or ""
        if not group_name:
            return ""
        return format_group_context_block(
            group_name,
            fixture_class=f.get("fixture_class") or "",
            namespace=f.get("namespace") or "",
            main_function=f.get("main_function") or "",
            note=f.get("note") or "",
        )

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
    "Test Design Comment Rule",
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


# ---------------------------------------------------------------------------
# Condition/code entry parser (structured YAML format in memory sections)
# ---------------------------------------------------------------------------

def _strip_md_escapes(text: str) -> str:
    """Remove backslash escapes from markdown source (\\_ → _, \\* → *, etc.)."""
    return re.sub(r"\\([_*`\[\](){}#+\-.!|])", r"\1", str(text or ""))


def parse_condition_code_entries(section_body: str) -> list[dict[str, str]]:
    """Parse condition/code YAML entries from a memory section body.

    Handles entries like:
        * condition: SIGNAL = VALUE
          code: |
            EXPECT_CALL(...)

    Also handles markdown-escaped underscores (WMODE\\_CMD → WMODE_CMD).
    Returns list of {condition, signal, value, code} dicts.
    Signal and value are normalised (UPPER, stripped, de-escaped).
    """
    entries: list[dict[str, str]] = []
    lines = (section_body or "").splitlines()
    # Find bullet start lines (* or -)
    bullet_starts: list[int] = []
    for i, line in enumerate(lines):
        if re.match(r"^[*\-]\s+\S", line):
            bullet_starts.append(i)

    for idx, start in enumerate(bullet_starts):
        end = bullet_starts[idx + 1] if idx + 1 < len(bullet_starts) else len(lines)
        block_lines = lines[start:end]
        block_text = "\n".join(block_lines)

        cond_m = re.search(r"condition:\s*(.+)", block_text, re.I)
        if not cond_m:
            continue

        # De-escape markdown so WMODE\_CMD becomes WMODE_CMD
        condition_raw = cond_m.group(1).strip()
        condition = _strip_md_escapes(condition_raw)
        sig_m = re.match(r"(\w+)\s*=\s*(.*)", condition)
        signal = sig_m.group(1).strip().upper() if sig_m else (condition.split()[0].upper() if condition.split() else "")
        value = _strip_md_escapes(sig_m.group(2).strip()) if sig_m else ""

        # Extract code: collect all lines after "code: |" until next bullet marker or section
        code_lines: list[str] = []
        in_code = False
        code_ref_indent = 0
        for line in block_lines:
            if re.search(r"\bcode:\s*\|", line, re.I):
                in_code = True
                code_ref_indent = len(line) - len(line.lstrip())
                continue
            if re.search(r"\bcode:\s+\S", line, re.I) and not in_code:
                m2 = re.search(r"\bcode:\s+(\S.*)", line, re.I)
                if m2:
                    code_lines.append(m2.group(1).strip())
                break
            if in_code:
                # Stop on next block-level bullet or section header
                if re.match(r"^[*\-]\s", line) or re.match(r"^#+\s", line) or re.match(r"^\*{3,}", line):
                    break
                if re.match(r"\s+\w+:", line) and not code_lines:
                    # Another YAML key at same indent level, stop
                    continue
                code_lines.append(line)

        code = _strip_md_escapes("\n".join(code_lines).strip()) if code_lines else ""

        if signal:
            entries.append({"condition": condition_raw, "signal": signal, "value": value, "code": code})

    return entries


def _signals_in_condition_entries(section_body: str) -> set[str]:
    """Return all signal names (upper, de-escaped) found in condition: entries."""
    sigs: set[str] = set()
    for line in (section_body or "").splitlines():
        # Match both "  condition: ..." and "* condition: ..." bullet forms
        m = re.match(r"[\s*\-]*condition:\s*([\w\\]+)", line, re.I)
        if m:
            sigs.add(_strip_md_escapes(m.group(1)).upper())
    return sigs


# ---------------------------------------------------------------------------
# Confirmed-rule filter (Patch 2 — excludes [alternative]/[disabled]/[pending])
# ---------------------------------------------------------------------------

def _rule_is_confirmed(bullet: str) -> bool:
    lower = bullet.lower()
    return "[alternative]" not in lower and "[disabled]" not in lower and "[pending]" not in lower


def filter_confirmed_rules(content: str) -> str:
    """Remove non-confirmed bullets ([alternative]/[disabled]/[pending]) from memory content."""
    lines: list[str] = []
    for line in str(content or "").splitlines():
        stripped = line.strip()
        if (stripped.startswith("-") or stripped.startswith("*")) and not _rule_is_confirmed(stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-testcase relevant rule extractor (Patch 2 — signal-matched prompt context)
# ---------------------------------------------------------------------------

def extract_relevant_rules_for_testcase(
    memory_content: str,
    expected_input: str,
    expected_output: str,
    *,
    char_limit: int = 1200,
) -> dict[str, Any]:
    """Return matched rules and coverage metadata for this testcase.

    Normalises escaped markdown (WMODE\\_CMD → WMODE_CMD) before any matching.
    Returns dict:
        text: formatted relevant rules block (empty string if none matched)
        fixture_found: True if Fixture / Test Style section has real content
        input_signals_matched: set of input signal names with a matched rule
        output_signals_matched: set of output signal names with a matched rule
    """
    # Normalise markdown escapes once — all downstream code sees plain underscores.
    raw = str(memory_content or "").strip()
    text = filter_confirmed_rules(_strip_md_escapes(raw))
    _empty: dict[str, Any] = {
        "text": "",
        "fixture_found": False,
        "input_signals_matched": set(),
        "output_signals_matched": set(),
    }
    if not _has_real_content(text):
        return _empty

    inp = str(expected_input or "")
    out = str(expected_output or "")

    input_signals: set[str] = {m.upper() for m in re.findall(r"(?:given|when):\s*(\w+)\s*=", inp, re.I)}
    output_signals: set[str] = {m.upper() for m in re.findall(r"then:\s*(\w+)\s*=", out, re.I)}
    input_sv: list[tuple[str, str]] = [
        (m.group(1).upper(), re.sub(r"[u'\" ]+$", "", m.group(2).strip()))
        for m in re.finditer(r"(?:given|when):\s*(\w+)\s*=\s*(\S+)", inp, re.I)
    ]
    output_sv: list[tuple[str, str]] = [
        (m.group(1).upper(), re.sub(r"[u'\" ]+$", "", m.group(2).strip()))
        for m in re.finditer(r"then:\s*(\w+)\s*=\s*(\S+)", out, re.I)
    ]
    all_signals = input_signals | output_signals
    has_timing = bool(re.search(r"(?:elapsed|T\s*=\s*\d+|wait|cycle|\bms\b|step)", inp + " " + out, re.I))

    parts: list[str] = []
    total = 0
    fixture_found = False
    input_signals_matched: set[str] = set()
    output_signals_matched: set[str] = set()

    def _add(block: str) -> None:
        nonlocal total
        b = block.strip()
        if not b or total + len(b) > char_limit:
            return
        parts.append(b)
        total += len(b)

    def _best_matched(
        section_body: str,
        signals: set[str],
        sv_pairs: list[tuple[str, str]],
    ) -> tuple[str, set[str]]:
        """Return (formatted text with condition+code headers, matched signal names).

        Condition/code entries produce:
            condition: SIGNAL = VALUE
            code:
            EXACT_CODE_BLOCK

        Plain bullet fallback returns the raw bullet lines.
        """
        entries = parse_condition_code_entries(section_body)
        if entries:
            seen: set[str] = set()
            blocks: list[str] = []
            # Build lookup: (sig, val) → (condition_display, code)
            sv_map: dict[tuple[str, str], tuple[str, str]] = {}
            sig_map: dict[str, tuple[str, str]] = {}
            for e in entries:
                cond_display = e["condition"]  # already de-escaped by parser
                sv_map[(e["signal"], e["value"])] = (cond_display, e["code"])
                sv_map[(e["signal"], e["value"].rstrip("uU"))] = (cond_display, e["code"])
                if e["signal"] not in sig_map:
                    sig_map[e["signal"]] = (cond_display, e["code"])
            # Exact signal+value match first
            for sig, val in sv_pairs:
                if sig in signals and sig not in seen:
                    hit = sv_map.get((sig, val)) or sv_map.get((sig, val.rstrip("uU")))
                    if hit:
                        cond_display, code = hit
                        entry_text = f"condition: {cond_display}"
                        if code:
                            entry_text += f"\ncode:\n{code}"
                        blocks.append(entry_text)
                        seen.add(sig)
            # Signal-only fallback
            for sig in signals:
                if sig not in seen:
                    hit = sig_map.get(sig)
                    if hit:
                        cond_display, code = hit
                        entry_text = f"condition: {cond_display}"
                        if code:
                            entry_text += f"\ncode:\n{code}"
                        blocks.append(entry_text)
                        seen.add(sig)
            if blocks:
                return "\n\n".join(blocks), seen
        # Plain bullet fallback — signal map is not used here (only in uncovered fallback below)
        relevant = [
            l for l in section_body.splitlines()
            if l.strip() and any(s in l.upper() for s in signals)
        ][:4]
        return "\n".join(relevant), signals if relevant else set()

    # Test Design Comment Rule — always include all bullets (strip HR separators)
    comment_rule_body = _section_body(text, "Test Design Comment Rule")
    if comment_rule_body:
        rule_lines = [
            l.strip() for l in comment_rule_body.splitlines()
            if l.strip()
            and not l.strip().startswith("#")
            and not re.match(r"^[\*\-=]{3,}$", l.strip())
        ]
        if rule_lines:
            _add("Test Design Comment Rule:\n" + "\n".join(rule_lines))

    # Fixture — always include first 2 non-empty lines; fixture_found if section has content
    fixture_body = _section_body(text, "Fixture / Test Style")
    if fixture_body:
        flines = [l for l in fixture_body.splitlines() if l.strip()][:2]
        if flines:
            _add("Fixture:\n" + "\n".join(flines))
            fixture_found = True

    # Input mock rules
    if input_signals:
        in_body = _section_body(text, "Input Mock Pattern")
        if in_body:
            matched_text, matched_sigs = _best_matched(in_body, input_signals, input_sv)
            if matched_text:
                _add("Input Mock Pattern:\n" + matched_text)
                input_signals_matched |= matched_sigs

    # Output assertion rules
    if output_signals:
        out_body = _section_body(text, "Output Assertion Pattern")
        if out_body:
            matched_text, matched_sigs = _best_matched(out_body, output_signals, output_sv)
            if matched_text:
                _add("Output Assertion Pattern:\n" + matched_text)
                output_signals_matched |= matched_sigs

    # Timing
    if has_timing:
        timing_body = _section_body(text, "Timing Pattern")
        if timing_body:
            _add("Timing Pattern:\n" + "\n".join(timing_body.splitlines()[:3]))

    # Signal map — fallback only for signals not yet covered by condition entries
    uncovered = all_signals - input_signals_matched - output_signals_matched
    if uncovered:
        sig_body = _section_body(text, "Spec Signal to Test Code Map")
        if sig_body:
            relevant = [
                l for l in sig_body.splitlines()
                if l.strip() and any(s in l.upper() for s in uncovered)
            ][:4]
            if relevant:
                _add("Spec Signal Map (fallback):\n" + "\n".join(relevant))

    result = "\n\n".join(parts)
    if len(result) > char_limit:
        result = result[:char_limit].rstrip() + "\n...[trimmed]"
    return {
        "text": result,
        "fixture_found": fixture_found,
        "input_signals_matched": input_signals_matched,
        "output_signals_matched": output_signals_matched,
    }


def memory_diagnostics(memory_content: str) -> dict[str, Any]:
    """Return stats about memory content for debug/UI display."""
    text = str(memory_content or "")
    text_norm = _strip_md_escapes(text)
    has_content = _has_real_content(text)
    fixture_body = _section_body(text, "Fixture / Test Style")
    input_body = _section_body(text, "Input Mock Pattern")
    output_body = _section_body(text, "Output Assertion Pattern")

    def _count_bullets(body: str) -> int:
        return sum(1 for l in body.splitlines() if re.match(r"\s*[*\-]\s+\S", l))

    def _count_conditions(body: str) -> int:
        return sum(1 for l in body.splitlines() if re.match(r"\s*condition:", l, re.I))

    in_bullets = _count_bullets(input_body)
    in_conds = _count_conditions(input_body)
    out_bullets = _count_bullets(output_body)
    out_conds = _count_conditions(output_body)

    has_fixture = (
        bool(re.search(r"\bTEST_F\b", text_norm))
        or bool(re.search(r"fixture\s*(class|name)\s*:", text_norm, re.I))
        or bool(re.search(r"use\s+fixture\s+`?\w+`?", text_norm, re.I))
        or (bool(fixture_body) and _count_bullets(fixture_body) > 0)
    )

    return {
        "has_real_content": has_content,
        "chars": len(text),
        "fixture_found": has_fixture,
        "input_rules": in_bullets + in_conds,
        "output_rules": out_bullets + out_conds,
        "preview": text[:200] if text else "",
    }
