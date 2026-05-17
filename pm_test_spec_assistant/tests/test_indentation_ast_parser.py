"""Unit tests for generic two-column / indentation AST parser."""

from __future__ import annotations

from src.engine.indentation_ast_parser import ast_to_expression, paths_to_ast


def _expr(paths: list[list[str]]) -> str:
    ast, _ = paths_to_ast(paths, {"file": "test"})
    return ast_to_expression(ast)


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
    expr = _expr(paths)
    assert "X" in expr and "Y" in expr
    assert "P" in expr and "Q" in expr


def test_not_condition():
    paths = [["OR", "AND", "NOT NOK"]]
    ast, _ = paths_to_ast(paths, {})
    expr = ast_to_expression(ast)
    assert "NOT" in expr
    assert "NOK" in expr


def test_mixed_paths_fail_closed():
    paths = [["OR", "A"], ["AND", "B"]]
    ast, notes = paths_to_ast(paths, {})
    assert ast.get("type") == "empty" or ast.get("parse_status") == "failed"
    assert any(n.get("type") == "unsupported_logic_format" for n in notes)


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
