"""Normalize condition tokens into LogicAtom records (spec-driven, no sample names)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.logic_keywords import parse_edge_event
from src.engine.memory_semantics_parser import classify_value_domain
from src.parsers.two_column_table_parser import FOOTNOTE_RE

_COMPARATOR_RE = re.compile(
    r"^(?P<neg>NOT\s+)?(?P<sig>.+?)\s*(?P<op>=|==|>=|<=|>|<)\s*(?P<val>.+)$",
    re.I,
)
_SIGNAL_ONLY_RE = re.compile(r"^(?P<neg>NOT\s+)?(?P<sig>[A-Za-z_][A-Za-z0-9_]*)\s*$", re.I)
_LOGIC_OPS = frozenset({"AND", "OR", "NOT", "TRUE", "FALSE"})


def parse_token_to_atom(token: str, *, source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse a table leaf token into a LogicAtom dict."""
    raw = str(token or "").strip()
    footnote_refs = []
    for n in FOOTNOTE_RE.findall(raw):
        footnote_refs.append(f"(*{n})" if not str(n).startswith("(") else str(n))
    clean = FOOTNOTE_RE.sub("", raw).strip()
    negated = bool(re.match(r"^NOT\s+", clean, re.I))
    if negated:
        clean = re.sub(r"^NOT\s+", "", clean, flags=re.I).strip()

    m = _COMPARATOR_RE.match(clean)
    if m:
        sig = m.group("sig").strip()
        op = m.group("op").replace("==", "=").strip()
        val = m.group("val").strip()
        if val.upper() in _LOGIC_OPS:
            val = None
        return _atom(
            signal=sig,
            operator=op,
            value=val,
            negated=negated or bool(m.group("neg")),
            footnote_refs=footnote_refs,
            raw_text=raw,
            source=source,
            resolution="resolved" if val and not footnote_refs else ("needs_llm" if footnote_refs else "resolved"),
            value_domain=classify_value_domain(val) if val else "literal",
        )

    m2 = _SIGNAL_ONLY_RE.match(clean)
    if m2:
        sig = m2.group("sig").strip()
        return _atom(
            signal=sig,
            operator="==",
            value=None,
            negated=negated or bool(m2.group("neg")),
            footnote_refs=footnote_refs,
            raw_text=raw,
            source=source,
            resolution="needs_llm" if footnote_refs else "needs_engineer",
        )

    sig_m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", clean)
    sig = sig_m.group(1) if sig_m else clean[:64]
    return _atom(
        signal=sig,
        operator="==",
        value=None,
        negated=negated,
        footnote_refs=footnote_refs,
        raw_text=raw,
        source=source,
        resolution="needs_engineer",
    )


def _atom(
    *,
    signal: str,
    operator: str,
    value: str | None,
    negated: bool,
    footnote_refs: list[str],
    raw_text: str,
    source: dict[str, Any] | None,
    resolution: str,
    value_domain: str = "literal",
) -> dict[str, Any]:
    out = {
        "signal": signal,
        "operator": operator,
        "value": value,
        "negated": negated,
        "footnote_refs": footnote_refs,
        "raw_text": raw_text,
        "source": source or {},
        "resolution": resolution,
    }
    if value_domain != "literal":
        out["value_domain"] = value_domain
    return out


def _normalize_footnote_ref(ref: str) -> str:
    r = str(ref or "").strip()
    if not r:
        return r
    if r.isdigit():
        return f"(*{r})"
    if not r.startswith("("):
        m = re.match(r"\*?(\d+)", r)
        if m:
            return f"(*{m.group(1)})"
    return r


def _merge_node_footnotes(atom: dict[str, Any], node: dict[str, Any]) -> None:
    refs = list(atom.get("footnote_refs") or [])
    for fn in node.get("footnotes") or []:
        nr = _normalize_footnote_ref(str(fn))
        if nr and nr not in refs:
            refs.append(nr)
    if refs:
        atom["footnote_refs"] = refs
        if atom.get("value") is None:
            atom["resolution"] = "needs_llm"


def _attach_atom_to_condition(node: dict[str, Any], *, negate: bool = False) -> None:
    if node.get("atom"):
        return
    token = str(node.get("name") or node.get("raw_text") or "")
    edge = parse_edge_event(token)
    if edge:
        node["type"] = "edge_event"
        node["atom_kind"] = "edge_event"
        node["from_state"] = edge.get("from_state", "")
        node["to_state"] = edge.get("to_state", "")
        node["raw_text"] = token
        node["atom"] = {
            "signal": edge.get("from_state") or token[:32],
            "operator": "edge",
            "value": edge.get("to_state"),
            "negated": negate,
            "footnote_refs": [],
            "raw_text": token,
            "source": node.get("source") or {},
            "resolution": "resolved",
            "atom_kind": "edge_event",
        }
        return
    atom = parse_token_to_atom(token, source=node.get("source"))
    _merge_node_footnotes(atom, node)
    if negate:
        atom["negated"] = not atom.get("negated", False)
    node["atom"] = atom
    node["name"] = atom["signal"]
    if atom.get("value") is not None:
        node["comparator_value"] = atom["value"]


def enrich_tree_with_atoms(tree: dict[str, Any]) -> dict[str, Any]:
    """Walk AST and attach typed atoms on condition / edge_event nodes."""
    return _enrich_tree_with_atoms_impl(tree)


def enrich_table_ast_with_atoms(tree: dict[str, Any]) -> dict[str, Any]:
    """Post-pass for table-derived AST leaves (edge events, signal conditions)."""
    return enrich_tree_with_atoms(tree)


def _enrich_tree_with_atoms_impl(tree: dict[str, Any]) -> dict[str, Any]:

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "condition":
            _attach_atom_to_condition(node)
        elif node.get("type") == "edge_event" and not node.get("atom"):
            _attach_atom_to_condition(node)
        elif node.get("type") == "NOT":
            for ch in node.get("children") or []:
                if isinstance(ch, dict) and ch.get("type") == "condition":
                    _attach_atom_to_condition(ch, negate=True)
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return tree


def collect_atoms_from_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> None:
        if (node.get("type") in ("condition", "edge_event")) and node.get("atom"):
            out.append(node["atom"])
        for ch in node.get("children") or []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return out


def atom_signal_names(tree: dict[str, Any]) -> list[str]:
    """Unique signal names from atoms (for unresolved checks)."""
    seen: set[str] = set()
    names: list[str] = []
    for atom in collect_atoms_from_tree(tree):
        sig = str(atom.get("signal") or "").strip()
        if sig and sig not in seen:
            seen.add(sig)
            names.append(sig)
    return names


def is_atom_self_resolved(atom: dict[str, Any]) -> bool:
    """Inline comparator from spec counts as resolved without definition row."""
    if atom.get("resolution") == "resolved":
        return True
    if atom.get("value") is not None and not atom.get("footnote_refs"):
        return True
    return False
