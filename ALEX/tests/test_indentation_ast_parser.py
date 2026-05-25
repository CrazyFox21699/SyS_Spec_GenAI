"""Unit tests for generic two-column / indentation AST parser."""

from __future__ import annotations

from src.engine.indentation_ast_parser import (
    ast_to_expression,
    infer_merged_scope_operator,
    paths_to_ast,
)


def _expr(paths: list[list[str]]) -> str:
    ast, _ = paths_to_ast(paths, {"file": "test"})
    return ast_to_expression(ast)


def _ast(paths: list[list[str]]):
    ast, notes = paths_to_ast(paths, {"file": "test"})
    return ast, notes


def test_infer_merged_scope_operator_all_rows_share_column_zero():
    paths = [["OR", "A"], ["OR", "B"]]
    scope, relative, notes = infer_merged_scope_operator(paths)
    assert scope == "OR"
    assert relative == [["A"], ["B"]]
    assert any(n.get("type") == "merged_scope_inferred" for n in notes)


def test_or_with_two_and_branches():
    paths = [
        ["OR", "AND", "A"],
        ["OR", "AND", "NOT B"],
        ["OR", "AND", "C"],
        ["OR", "AND", "D"],
    ]
    expr = _expr(paths)
    assert "A" in expr and "B" in expr and "C" in expr and "D" in expr
    assert "OR" in expr or "or" in expr.lower()


def test_and_with_nested_or_columns():
    paths = [
        ["AND", "X"],
        ["AND", "Y"],
        ["AND", "OR", "P"],
        ["AND", "OR", "Q"],
    ]
    ast, _ = _ast(paths)
    assert ast.get("type") == "AND"
    children = ast.get("children") or []
    assert any(ch.get("type") == "OR" for ch in children)
    expr = ast_to_expression(ast)
    assert "X" in expr and "Y" in expr
    assert "P" in expr and "Q" in expr


def test_not_condition():
    paths = [["OR", "AND", "NOT NOK"]]
    ast, _ = paths_to_ast(paths, {})
    expr = ast_to_expression(ast)
    assert "NOT" in expr
    assert "NOK" in expr


def test_mixed_paths_fail_closed():
    paths = [["OR", "A"], ["FOO", "B"]]
    ast, notes = paths_to_ast(paths, {})
    assert ast.get("type") == "empty" or ast.get("parse_status") == "failed"
    assert any(n.get("type") == "unsupported_logic_format" for n in notes)


def test_merged_scope_or_with_leaf_and_and_branches():
    """Merged OR cell + direct leaf branch + AND row pairs (no hardcoded control names)."""
    paths = [
        ["OR", "HUY = OK"],
        ["OR", "AND", "OK_SHUTOFF = 1"],
        ["OR", "AND", "NOT NOK_SHUTOFF = (*1)"],
        ["OR", "AND", "FORCE_SHUTOFF = 150"],
        ["OR", "AND", "CND_FORCE_ALLOWED = 0"],
    ]
    ast, notes = paths_to_ast(paths, {})
    assert ast.get("type") == "OR"
    assert ast.get("parse_status") == "ok"
    assert any(n.get("type") == "merged_scope_inferred" for n in notes)
    assert not any(n.get("type") == "unsupported_logic_format" for n in notes)
    children = ast.get("children") or []
    assert children[0].get("type") == "condition"
    assert children[0].get("name") == "HUY = OK"
    assert all(ch.get("type") == "AND" for ch in children[1:])
    expr = ast_to_expression(ast)
    assert "HUY = OK" in expr
    assert "OK_SHUTOFF = 1" in expr
    assert "FORCE_SHUTOFF = 150" in expr


def test_merged_scope_or_with_only_leaf_branches():
    paths = [["OR", "A = 1"], ["OR", "B = 0"], ["OR", "C = 2"]]
    ast, _ = _ast(paths)
    assert ast.get("type") == "OR"
    children = ast.get("children") or []
    assert len(children) == 3
    assert all(ch.get("type") == "condition" for ch in children)


def test_merged_scope_and_groups_inner_or():
    paths = [["AND", "REQ = 1"], ["AND", "SAFE = 1"], ["AND", "OR", "ROUTE_A"], ["AND", "OR", "ROUTE_B"]]
    ast, _ = _ast(paths)
    assert ast.get("type") == "AND"
    expr = ast_to_expression(ast)
    assert "REQ = 1" in expr and "SAFE = 1" in expr
    assert "ROUTE_A" in expr and "ROUTE_B" in expr


def test_single_path():
    expr = _expr([["AND", "COND_A"]])
    assert "COND_A" in expr


def test_path_continuation_inferred():
    paths = [
        ["AND", "A"],
        ["OR", "B", "AND", "C"],
    ]
    ast, notes = paths_to_ast(paths, {})
    assert any(n.get("type") == "path_continuation_inferred" for n in notes)
    assert ast.get("type") != "empty"


def test_no_redundant_inner_or_for_merged_scope_leaf():
    paths = [["OR", "SIG_A = OK"], ["OR", "AND", "X = 1"], ["OR", "AND", "Y = 2"]]
    ast, _ = _ast(paths)
    first = (ast.get("children") or [])[0]
    assert first.get("type") == "condition"
    assert first.get("name") == "SIG_A = OK"
