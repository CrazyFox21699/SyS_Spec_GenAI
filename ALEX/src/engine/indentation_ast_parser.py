"""Generic indentation / multi-column path → AST (deterministic, no sample-specific names).

Algorithm (spec-format agnostic)
--------------------------------
1. Each table row becomes a *path* — one token per nested Condition column (depth = column index).
2. Merged cells repeat the same gate token on every row at that column; that token is a *scope*
   marker, not a per-row nested gate. We detect scope when column 0 is the same LOGIC_OP on all rows.
3. After stripping scope, sibling rows are grouped: consecutive rows sharing the same inner gate
   prefix (e.g. AND) become one branch; a lone leaf row becomes a direct branch.
4. Single-path remainder uses column-depth parsing (token index = nesting level).
"""

from __future__ import annotations

import uuid
from typing import Any

from src.parsers.two_column_table_parser import FOOTNOTE_RE

LOGIC_OPS = frozenset({"AND", "OR", "NOT"})


def _new_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _reason(text: str) -> dict[str, str]:
    return {"parser_reason": text}


def _is_logic_token(token: str) -> bool:
    return str(token or "").strip().upper() in LOGIC_OPS


def _split_not(token: str) -> tuple[str, str]:
    t = token.strip()
    if t.upper().startswith("NOT "):
        return "NOT", t[4:].strip()
    return "", t


def _make_op(op: str, source: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": _new_id("op"),
        "type": op.upper(),
        "children": [],
        "raw_text": op.upper(),
        "source": source,
        "confidence": "high",
        "review_status": "parsed",
        "issue_status": "ok",
        **_reason(reason),
    }


def _make_condition(token: str, source: dict[str, Any], reason: str) -> dict[str, Any]:
    op, rest = _split_not(token)
    if op == "NOT":
        return {
            "id": _new_id("not"),
            "type": "NOT",
            "children": [
                {
                    "id": _new_id("ref"),
                    "type": "condition",
                    "name": rest,
                    "raw_text": token,
                    "footnotes": FOOTNOTE_RE.findall(token),
                    "source": source,
                    "confidence": "medium",
                    "review_status": "pending",
                    "issue_status": "ok",
                    **_reason("Detected as NOT condition because token starts with NOT."),
                }
            ],
            "raw_text": token,
            "source": source,
            "confidence": "medium",
            "review_status": "pending",
            "issue_status": "ok",
            **_reason("Detected as NOT gate because row text starts with NOT."),
        }
    return {
        "id": _new_id("ref"),
        "type": "condition",
        "name": token.strip(),
        "raw_text": token,
        "footnotes": FOOTNOTE_RE.findall(token),
        "source": source,
        "confidence": "medium",
        "review_status": "pending",
        "issue_status": "ok",
        **_reason("Detected as condition reference from row path leaf token."),
    }


def _empty(source: dict[str, Any], status: str = "failed", error: str = "") -> dict[str, Any]:
    return {
        "id": _new_id("empty"),
        "type": "empty",
        "children": [],
        "source": source,
        "parse_status": status,
        "parse_error": error,
        **_reason(error or "No parseable paths"),
    }


def _clean_paths(paths: list[list[str]]) -> list[list[str]]:
    return [[p.strip() for p in path if p and p.strip()] for path in paths if path]


def normalize_control_paths(
    paths: list[list[str]],
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Prepend root operator when continuation rows omit it (merged-cell pattern)."""
    notes: list[dict[str, Any]] = []
    cleaned = _clean_paths(paths)
    if not cleaned:
        return [], notes

    root_op: str | None = None
    if cleaned[0] and _is_logic_token(cleaned[0][0]):
        root_op = cleaned[0][0].upper()

    out: list[list[str]] = []
    for i, path in enumerate(cleaned):
        if (
            i > 0
            and root_op
            and path
            and _is_logic_token(path[0])
            and path[0].upper() != root_op
        ):
            out.append([root_op] + path)
            notes.append(
                {
                    "type": "path_continuation_inferred",
                    "severity": "info",
                    "message": (
                        f"Prepended `{root_op}` to path beginning with `{path[0]}` "
                        "because the control block root operator was already established."
                    ),
                    "parser_reason": (
                        "Row continued under the same control without repeating the root "
                        f"operator `{root_op}` (typical merged-cell continuation)."
                    ),
                }
            )
        else:
            out.append(path)
    return out, notes


def infer_merged_scope_operator(
    paths: list[list[str]],
) -> tuple[str | None, list[list[str]], list[dict[str, Any]]]:
    """
    When every row shares the same gate at column 0, treat it as a merged-cell scope prefix.
    Returns (scope_op, relative_paths_without_prefix, notes).
    """
    notes: list[dict[str, Any]] = []
    if not paths or not all(paths):
        return None, paths, notes

    first_tokens = [path[0].upper() for path in paths if path]
    if not first_tokens or not all(_is_logic_token(t) for t in first_tokens):
        return None, paths, notes
    if len(set(first_tokens)) != 1:
        return None, paths, notes

    scope_op = first_tokens[0]
    relative = [path[1:] for path in paths]
    notes.append(
        {
            "type": "merged_scope_inferred",
            "severity": "info",
            "message": (
                f"All rows repeat `{scope_op}` in the first condition column; "
                "interpreted as merged-cell scope, not per-row nesting."
            ),
            "parser_reason": (
                f"Column 0 is `{scope_op}` on every row — typical Word/Excel merged gate cell."
            ),
        }
    )
    return scope_op, relative, notes


def _group_sibling_branch_paths(relative_paths: list[list[str]]) -> list[list[list[str]]]:
    """
    Partition scope-relative paths into sibling branch groups.
    Consecutive rows with the same leading inner gate belong to one group.
    """
    groups: list[list[list[str]]] = []
    i = 0
    while i < len(relative_paths):
        path = relative_paths[i]
        if not path:
            i += 1
            continue
        if _is_logic_token(path[0]):
            inner = path[0].upper()
            batch: list[list[str]] = []
            while i < len(relative_paths):
                candidate = relative_paths[i]
                if candidate and candidate[0].upper() == inner:
                    batch.append(candidate)
                    i += 1
                else:
                    break
            groups.append(batch)
        else:
            groups.append([path])
            i += 1
    return groups


def _path_to_ast(path: list[str], source: dict[str, Any]) -> dict[str, Any]:
    """Parse one path using column index as nesting depth."""
    cleaned = [p.strip() for p in path if p and p.strip()]
    if not cleaned:
        return _empty(source)
    if len(cleaned) == 1:
        return _make_condition(cleaned[0], source, "Single-token path interpreted as condition reference.")
    return _column_path_to_ast(cleaned, source, 0)


def _is_single_leaf_inner_row(path: list[str], inner_op: str) -> bool:
    return len(path) == 2 and path[0].upper() == inner_op and not _is_logic_token(path[1])


def _split_inner_batches_by_branch_group(
    batch: list[list[str]],
    branch_groups: list[str] | None,
    batch_start: int = 0,
) -> list[list[list[str]]]:
    """Split a consecutive inner-gate batch using merge-derived branch_group keys."""
    if not batch or not branch_groups:
        return [batch]
    groups: list[list[list[str]]] = []
    current: list[list[str]] = []
    current_key: str | None = None
    for i, path in enumerate(batch):
        key = branch_groups[batch_start + i] if batch_start + i < len(branch_groups) else ""
        if current and key != current_key:
            groups.append(current)
            current = []
        current.append(path)
        current_key = key
    if current:
        groups.append(current)
    return groups


def _split_inner_batches_for_scope(
    scope_op: str,
    inner_op: str,
    batch: list[list[str]],
    branch_groups: list[str] | None = None,
    batch_start: int = 0,
) -> list[list[list[str]]]:
    """
    Under disjunctive (OR) scope, group inner-gate rows by merge branch_group when available;
    otherwise fall back to pairing consecutive single-leaf AND rows.
    """
    if branch_groups:
        split = _split_inner_batches_by_branch_group(batch, branch_groups, batch_start)
        if len(split) > 1 or (split and len(split[0]) != len(batch)):
            return split
    if scope_op != "OR" or inner_op != "AND":
        return [batch]
    if not batch or not all(_is_single_leaf_inner_row(p, inner_op) for p in batch):
        return [batch]
    pairs: list[list[list[str]]] = []
    i = 0
    while i < len(batch):
        if i + 1 < len(batch):
            pairs.append([batch[i], batch[i + 1]])
            i += 2
        else:
            pairs.append([batch[i]])
            i += 1
    return pairs


def _build_inner_gate_group(
    inner_op: str,
    group_paths: list[list[str]],
    source: dict[str, Any],
    *,
    scope_op: str | None = None,
) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    for path in group_paths:
        rest = path[1:] if path and path[0].upper() == inner_op else path
        child = _path_to_ast(rest, source)
        if child.get("type") != "empty":
            children.append(child)
    if not children:
        return _empty(source, error=f"empty_{inner_op.lower()}_group")
    if len(children) == 1:
        return children[0]
    node = _make_op(
        inner_op,
        source,
        (
            f"Grouped {len(children)} consecutive rows sharing `{inner_op}` "
            "after merged-cell scope stripping."
        ),
    )
    node["children"] = children
    return node


def _build_scope_tree(
    scope_op: str,
    relative_paths: list[list[str]],
    source: dict[str, Any],
    *,
    branch_groups: list[str] | None = None,
    scope_stripped: int = 1,
) -> dict[str, Any]:
    branch_group_paths = _group_sibling_branch_paths(relative_paths)
    children: list[dict[str, Any]] = []
    row_cursor = 0
    for group in branch_group_paths:
        if not group:
            continue
        group_start = row_cursor
        row_cursor += len(group)
        group_branch = branch_groups[group_start:row_cursor] if branch_groups else None
        if len(group) == 1:
            children.append(_path_to_ast(group[0], source))
            continue
        inner_op = group[0][0].upper()
        for sub_batch in _split_inner_batches_for_scope(
            scope_op,
            inner_op,
            group,
            branch_groups=branch_groups,
            batch_start=group_start,
        ):
            if len(sub_batch) == 1 and not _is_logic_token(sub_batch[0][0]):
                children.append(_path_to_ast(sub_batch[0], source))
            else:
                children.append(_build_inner_gate_group(inner_op, sub_batch, source, scope_op=scope_op))

    children = [c for c in children if c.get("type") != "empty"]
    if not children:
        return _empty(source, error="empty_scope")
    if len(children) == 1:
        return children[0]

    node = _make_op(
        scope_op,
        source,
        (
            f"Merged-cell `{scope_op}` scope groups {len(children)} sibling branches "
            "from multi-row condition table."
        ),
    )
    node["children"] = children
    return node


def _column_path_to_ast(cells: list[str], source: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Parse one table row where list index = nesting depth (multi-column Word/Excel layout)."""
    while depth < len(cells) and not (cells[depth] or "").strip():
        depth += 1
    if depth >= len(cells):
        return _empty(source)

    tok = cells[depth].strip()
    upper = tok.upper()

    if upper in LOGIC_OPS:
        node = _make_op(
            upper,
            source,
            f"Detected `{upper}` gate at column depth {depth} (nesting level {depth}).",
        )
        if (
            depth + 1 < len(cells)
            and (cells[depth + 1] or "").strip()
            and not _is_logic_token(cells[depth + 1])
            and depth + 2 < len(cells)
            and _is_logic_token(cells[depth + 2])
        ):
            cond = _make_condition(
                cells[depth + 1].strip(),
                source,
                f"Condition at depth {depth + 1} is a direct child of `{upper}`.",
            )
            rest = _column_path_to_ast(cells, source, depth + 2)
            node["children"] = [c for c in [cond, rest] if c.get("type") != "empty"]
            return node

        child = _column_path_to_ast(cells, source, depth + 1)
        if child.get("type") != "empty":
            node["children"] = [child]
        return node

    cond = _make_condition(
        tok,
        source,
        f"Condition reference at column depth {depth}.",
    )
    if depth + 1 < len(cells) and _is_logic_token(cells[depth + 1]):
        rest = _column_path_to_ast(cells, source, depth + 1)
        and_node = _make_op(
            "AND",
            source,
            "Condition followed by operator at deeper column; grouped under implicit AND.",
        )
        and_node["children"] = [c for c in [cond, rest] if c.get("type") != "empty"]
        return and_node
    return cond


def paths_to_ast(
    paths: list[list[str]],
    source: dict[str, Any],
    *,
    branch_groups: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build AST from row paths. Fails closed when structure cannot be determined safely."""
    normalized, notes = normalize_control_paths(paths)
    if not normalized:
        return _empty(source, error="no_paths"), notes

    scope_op, relative, scope_notes = infer_merged_scope_operator(normalized)
    notes.extend(scope_notes)
    rel_branch = branch_groups
    if scope_op and branch_groups and len(branch_groups) == len(normalized):
        rel_branch = branch_groups
    if scope_op:
        ast = _build_scope_tree(scope_op, relative, source, branch_groups=rel_branch)
        ast["parse_status"] = "ok" if ast.get("type") != "empty" else "failed"
        return ast, notes

    if len(normalized) == 1:
        ast = _path_to_ast(normalized[0], source)
        ast["parse_status"] = "ok" if ast.get("type") != "empty" else "failed"
        return ast, notes

    notes.append(
        {
            "type": "unsupported_logic_format",
            "severity": "error",
            "message": "Mixed row path shapes — cannot build logic tree without engineer review.",
            "parser_reason": (
                "Rows do not share a merged scope operator in column 0 and are not a single path."
            ),
        }
    )
    return _empty(source, status="failed", error="unsupported_mixed_paths"), notes


def ast_to_expression(node: dict[str, Any], depth: int = 0) -> str:
    if depth > 24:
        return "..."
    t = node.get("type", "")
    if t == "condition":
        return node.get("name") or node.get("raw_text", "")
    if t == "NOT":
        ch = node.get("children") or []
        inner = ast_to_expression(ch[0], depth + 1) if ch else "?"
        return f"NOT {inner}"
    if t in ("AND", "OR"):
        parts = [ast_to_expression(c, depth + 1) for c in node.get("children") or []]
        parts = [p for p in parts if p]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return "(" + f" {t} ".join(parts) + ")"
    return node.get("raw_text", "")
