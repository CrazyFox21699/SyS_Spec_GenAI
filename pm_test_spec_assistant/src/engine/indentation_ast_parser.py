"""Generic indentation / multi-column path → AST (deterministic, no sample-specific names)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.parsers.two_column_table_parser import FOOTNOTE_RE

LOGIC_OPS = frozenset({"AND", "OR", "NOT"})


def _new_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _reason(text: str) -> dict[str, str]:
    return {"parser_reason": text}


def _split_not(token: str) -> tuple[str, str]:
    t = token.strip()
    if t.upper().startswith("NOT "):
        return "NOT", t[4:].strip()
    return "", t


def _make_op(op: str, raw: str, source: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": _new_id("op"),
        "type": op.upper(),
        "children": [],
        "raw_text": raw,
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


def normalize_control_paths(
    paths: list[list[str]],
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Prepend root operator when continuation rows omit it (merged-cell pattern)."""
    notes: list[dict[str, Any]] = []
    cleaned = [[p.strip() for p in path if p and p.strip()] for path in paths if path]
    if not cleaned:
        return [], notes

    root_op: str | None = None
    if cleaned[0] and cleaned[0][0].upper() in LOGIC_OPS:
        root_op = cleaned[0][0].upper()

    out: list[list[str]] = []
    for i, path in enumerate(cleaned):
        if (
            i > 0
            and root_op
            and path
            and path[0].upper() in LOGIC_OPS
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


def _is_or_and_row(path: list[str]) -> bool:
    return len(path) >= 3 and path[0].upper() == "OR" and path[1].upper() == "AND"


def _path_to_subtree(path: list[str], source: dict[str, Any]) -> dict[str, Any]:
    """Convert one row path (after optional leading AND stripped) to a subtree."""
    if not path:
        return _empty(source)
    if len(path) == 1:
        return _make_condition(path[0], source, "Single-token path interpreted as condition reference.")
    tok = path[0].upper()
    if tok in LOGIC_OPS:
        child = _path_to_subtree(path[1:], source)
        node = _make_op(
            tok,
            path[0],
            source,
            f"Detected `{tok}` gate from path token at nesting depth.",
        )
        if child.get("type") != "empty":
            node["children"] = [child]
        return node
    return _make_condition(path[0], source, "Leaf condition token in row path.")


def _build_or_and_pair_rows(paths: list[list[str]], source: dict[str, Any]) -> dict[str, Any]:
    """Rows shaped OR → AND → leaf: consecutive pairs become AND branches under OR."""
    and_branches: list[dict[str, Any]] = []
    i = 0
    while i < len(paths):
        if (
            _is_or_and_row(paths[i])
            and i + 1 < len(paths)
            and _is_or_and_row(paths[i + 1])
            and paths[i][:2] == paths[i + 1][:2]
        ):
            leaves = [paths[i][2], paths[i + 1][2]]
            and_branches.append(
                {
                    "id": _new_id("and"),
                    "type": "AND",
                    "children": [
                        _make_condition(
                            lv,
                            source,
                            "Grouped pair of consecutive OR/AND rows into one AND branch.",
                        )
                        for lv in leaves
                    ],
                    "source": source,
                    "confidence": "high",
                    "review_status": "parsed",
                    "issue_status": "ok",
                    **_reason(
                        "Two consecutive rows share OR/AND prefix; combined leaves under AND."
                    ),
                }
            )
            i += 2
        elif _is_or_and_row(paths[i]):
            and_branches.append(
                {
                    "id": _new_id("and"),
                    "type": "AND",
                    "children": [
                        _make_condition(
                            paths[i][2],
                            source,
                            "Single OR/AND row without pair — AND branch with one leaf.",
                        )
                    ],
                    "source": source,
                    "confidence": "medium",
                    "review_status": "pending",
                    "issue_status": "review_required",
                    **_reason("Incomplete OR/AND row pair — review required."),
                }
            )
            i += 1
        else:
            and_branches.append(_path_to_subtree(paths[i], source))
            i += 1
    if len(and_branches) == 1:
        return and_branches[0]
    return {
        "id": _new_id("or"),
        "type": "OR",
        "children": and_branches,
        "source": source,
        "confidence": "high",
        "review_status": "parsed",
        "issue_status": "ok",
        **_reason(
            "Multiple OR/AND row branches detected; combined as OR of AND groups."
        ),
    }


def _column_path_to_ast(cells: list[str], source: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """
    Parse one table row where list index = nesting depth (multi-column Word/Excel layout).
    """
    while depth < len(cells) and not (cells[depth] or "").strip():
        depth += 1
    if depth >= len(cells):
        return _empty(source)

    tok = cells[depth].strip()
    upper = tok.upper()

    if upper in LOGIC_OPS:
        node = _make_op(
            upper,
            tok,
            source,
            f"Detected `{upper}` gate at column depth {depth} (nesting level {depth}).",
        )
        # Pattern: OR | condition | AND | …  → OR(condition, AND(…))
        if (
            depth + 1 < len(cells)
            and (cells[depth + 1] or "").strip()
            and cells[depth + 1].strip().upper() not in LOGIC_OPS
            and depth + 2 < len(cells)
            and (cells[depth + 2] or "").strip().upper() in LOGIC_OPS
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
    if depth + 1 < len(cells) and (cells[depth + 1] or "").strip().upper() in LOGIC_OPS:
        rest = _column_path_to_ast(cells, source, depth + 1)
        return {
            "id": _new_id("and"),
            "type": "AND",
            "children": [c for c in [cond, rest] if c.get("type") != "empty"],
            "source": source,
            "confidence": "medium",
            "review_status": "pending",
            "issue_status": "ok",
            **_reason(
                "Condition followed by operator at deeper column; grouped under implicit AND."
            ),
        }
    return cond


def paths_to_ast(paths: list[list[str]], source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build AST from row paths. Fails closed when structure cannot be determined safely."""
    normalized, notes = normalize_control_paths(paths)
    if not normalized:
        return _empty(source, error="no_paths"), notes

    # Mode A: all rows are OR → AND → leaf (pair consecutive rows)
    if all(_is_or_and_row(p) for p in normalized):
        ast = _build_or_and_pair_rows(normalized, source)
        ast["parse_status"] = "ok"
        return ast, notes

    # Mode B: all rows start with AND — multi-column depth parsing per row
    if all(p and p[0].upper() == "AND" for p in normalized):
        children = [
            _column_path_to_ast(p[1:], source, 0)
            for p in normalized
        ]
        children = [c for c in children if c.get("type") != "empty"]
        if not children:
            return _empty(source, error="no_and_children"), notes
        if len(children) > 1:
            or_branches = [c for c in children if c.get("type") == "OR"]
            other = [c for c in children if c.get("type") != "OR"]
            if len(or_branches) >= 2:
                merged_children: list[dict[str, Any]] = []
                for ob in or_branches:
                    merged_children.extend(ob.get("children") or [ob])
                children = other + [
                    {
                        "id": _new_id("or"),
                        "type": "OR",
                        "children": merged_children,
                        "source": source,
                        "confidence": "high",
                        "review_status": "parsed",
                        "issue_status": "ok",
                        **_reason(
                            "Multiple table rows share OR at the same nesting depth; "
                            "merged into one OR group under AND."
                        ),
                    }
                ]

        if len(children) == 1:
            ast = children[0]
        else:
            ast = {
                "id": _new_id("and"),
                "type": "AND",
                "children": children,
                "source": source,
                "confidence": "high",
                "review_status": "parsed",
                "issue_status": "ok",
                **_reason(
                    "All rows begin with AND; each row parsed by column depth and combined under AND."
                ),
            }
        ast["parse_status"] = "ok"
        return ast, notes

    # Mode C: single path only
    if len(normalized) == 1:
        ast = _path_to_subtree(normalized[0], source)
        ast["parse_status"] = "ok" if ast.get("type") != "empty" else "failed"
        return ast, notes

    notes.append(
        {
            "type": "unsupported_logic_format",
            "severity": "error",
            "message": "Mixed row path shapes — cannot build logic tree without engineer review.",
            "parser_reason": (
                "Row paths use incompatible nesting patterns (not all OR/AND rows and not all AND-root rows)."
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
