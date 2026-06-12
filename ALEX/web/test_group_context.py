"""Group-level test context: per-named-group fixture/namespace/main function lookup."""

from __future__ import annotations

import re
from typing import Any

SECTION_HEADER = "## Test Group Context"


def normalize_group_key(group_name: str) -> str:
    s = str(group_name or "").strip().lower()
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def parse_group_context(memory_content: str) -> dict[str, dict[str, str]]:
    """Parse ## Test Group Context section into {normalized_key: context_dict}.

    Each context_dict: {group_name, fixture_class, namespace, main_function, note}.
    """
    text = str(memory_content or "")
    section_m = re.search(
        r"^## Test Group Context\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not section_m:
        return {}
    body = section_m.group(1)
    result: dict[str, dict[str, str]] = {}
    group_blocks = re.split(r"^### Group:\s*", body, flags=re.MULTILINE)
    for block in group_blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        group_name = lines[0].strip()
        ctx: dict[str, str] = {
            "group_name": group_name,
            "fixture_class": "",
            "namespace": "",
            "main_function": "",
            "note": "",
        }
        for line in lines[1:]:
            m = re.match(
                r"^\s*-\s*(Fixture class|Namespace|Main function|Note):\s*(.*)",
                line, re.IGNORECASE
            )
            if m:
                key_raw = m.group(1).strip().lower().replace(" ", "_")
                if key_raw in ctx:
                    ctx[key_raw] = m.group(2).strip()
        key = normalize_group_key(group_name)
        result[key] = ctx
    return result


def get_group_context_for_row(row: dict, memory_content: str) -> dict[str, str] | None:
    """Return the group context dict for this row's test_group, or None if not found."""
    group_name = str(row.get("test_group") or "").strip()
    if not group_name:
        return None
    groups = parse_group_context(memory_content)
    return groups.get(normalize_group_key(group_name))


def format_group_context_block(
    group_name: str,
    fixture_class: str = "",
    namespace: str = "",
    main_function: str = "",
    note: str = "",
) -> str:
    """Return the ### Group: markdown block for a given context entry."""
    lines = [f"### Group: {group_name}"]
    if fixture_class.strip():
        lines.append(f"- Fixture class: {fixture_class.strip()}")
    if namespace.strip():
        lines.append(f"- Namespace: {namespace.strip()}")
    if main_function.strip():
        lines.append(f"- Main function: {main_function.strip()}")
    if note.strip():
        lines.append(f"- Note: {note.strip()}")
    return "\n".join(lines)


def upsert_group_context(
    memory_content: str,
    *,
    group_name: str,
    fixture_class: str = "",
    namespace: str = "",
    main_function: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Upsert a group context entry in ## Test Group Context section.

    Returns diagnostics: content, merged_rule_added, merged_rule_updated,
    duplicate_detected, normalized_group_key.
    """
    content = str(memory_content or "")
    key = normalize_group_key(group_name)

    existing_groups = parse_group_context(content)
    existing = existing_groups.get(key)

    new_block = format_group_context_block(
        group_name, fixture_class=fixture_class, namespace=namespace,
        main_function=main_function, note=note
    )

    merged_rule_added = False
    merged_rule_updated = False
    duplicate_detected = False

    if existing:
        same = (
            existing.get("fixture_class", "").strip() == fixture_class.strip()
            and existing.get("namespace", "").strip() == namespace.strip()
            and existing.get("main_function", "").strip() == main_function.strip()
        )
        if same:
            duplicate_detected = True
        else:
            merged_rule_updated = True
    else:
        merged_rule_added = True

    if not duplicate_detected:
        if existing:
            # Replace existing group block (match by existing group_name to handle case differences)
            escaped_name = re.escape(existing["group_name"])
            group_m = re.search(
                rf"^### Group:\s*{escaped_name}\s*$(.*?)(?=^###\s|^##\s|\Z)",
                content, re.MULTILINE | re.DOTALL
            )
            if group_m:
                content = content[: group_m.start()] + new_block + "\n" + content[group_m.end():]
            else:
                content = _append_to_group_context_section(content, new_block)
        else:
            content = _append_to_group_context_section(content, new_block)

    return {
        "content": content,
        "merged_rule_added": merged_rule_added,
        "merged_rule_updated": merged_rule_updated,
        "duplicate_detected": duplicate_detected,
        "normalized_group_key": key,
    }


def _append_to_group_context_section(content: str, new_block: str) -> str:
    """Append a new ### Group: block inside ## Test Group Context, creating section if missing."""
    section_m = re.search(r"^## Test Group Context\s*$", content, re.MULTILINE)
    if not section_m:
        return content.rstrip() + f"\n\n{SECTION_HEADER}\n\n{new_block}\n"
    after = content[section_m.end():]
    next_section = re.search(r"^## ", after, re.MULTILINE)
    if next_section:
        insert_at = section_m.end() + next_section.start()
        body = content[section_m.end(): insert_at]
        new_body = body.rstrip() + f"\n\n{new_block}\n\n"
        content = content[: section_m.end()] + new_body + content[insert_at:]
    else:
        content = content.rstrip() + f"\n\n{new_block}\n"
    return content
