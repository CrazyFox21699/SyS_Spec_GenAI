"""Build the per-job document relationship graph.

Nodes are the files that were ingested for a job. Edges describe how those files
relate to each other (footnote references, aliases, diagram links, role-based
relationships, code references, and engineer-defined links).

This module is read-only on the bundle. It returns a fresh ``document_graph``
section that callers persist back into the bundle.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from typing import Any, Iterable

_PREVIEW_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
    ".pdf",
    ".xlsx", ".xlsm", ".xls",
    ".docx",
    ".cpp", ".cc", ".cxx", ".h", ".hpp", ".c", ".py", ".md", ".txt",
}

_KIND_LABEL = {
    "alias": "alias of",
    "footnote_ref": "footnote references",
    "diagram_link": "diagram link",
    "test_derived_from": "test derived from",
    "code_implements": "implements signals",
    "reconciles": "reconciles with",
    "user_defined": "linked by engineer",
}

_SHEET_HINT_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]{3,})\b")


def _basename(path: str) -> str:
    if not path:
        return ""
    return os.path.basename(str(path))


def _node_id(path: str) -> str:
    """Stable short id for a file path."""
    key = (path or "").strip()
    if not key:
        return "DOC_UNKNOWN"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"DOC_{digest}"


def _previewable(name: str) -> bool:
    ext = os.path.splitext(name or "")[1].lower()
    return ext in _PREVIEW_EXTS


def _edge_id(source_id: str, target_id: str, kind: str, suffix: str = "") -> str:
    raw = f"{source_id}|{target_id}|{kind}|{suffix}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"EDG_{digest}"


def _file_from_source(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("file") or source.get("document") or "")
    if isinstance(source, str):
        return source
    return ""


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _control_set(bundle: dict[str, Any]) -> set[str]:
    controls: set[str] = set()
    for lb in bundle.get("logic_blocks") or []:
        name = str(lb.get("name") or "").strip()
        if name:
            controls.add(name.upper())
    for cd in bundle.get("condition_definitions") or []:
        name = str(cd.get("name") or "").strip()
        if name:
            controls.add(name.upper())
    return controls


def _build_node_index(
    classified_files: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return (nodes, lookup_by_path)."""
    nodes: list[dict[str, Any]] = []
    by_path: dict[str, str] = {}
    seen: set[str] = set()
    for row in classified_files or []:
        path = str(row.get("file") or row.get("path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        name = _basename(path)
        node_id = _node_id(path)
        nodes.append(
            {
                "id": node_id,
                "file": path,
                "name": name,
                "role": row.get("role") or "",
                "file_type": row.get("file_type") or "",
                "file_type_label": row.get("file_type_label") or "",
                "selected": bool(row.get("selected", True)),
                "previewable": _previewable(name),
                "artifact_counts": {
                    "logic_blocks": 0,
                    "footnotes": 0,
                    "transitions": 0,
                    "diagrams": 0,
                    "code_refs": 0,
                    "alias_rows": 0,
                    "two_column_tables": 0,
                    "test_reference_rows": 0,
                },
            }
        )
        by_path[path] = node_id
    return nodes, by_path


def _fill_artifact_counts(
    bundle: dict[str, Any],
    nodes: list[dict[str, Any]],
    by_path: dict[str, str],
) -> None:
    node_by_id = {n["id"]: n for n in nodes}

    def _bump(path: str, key: str, amount: int = 1) -> None:
        if not path:
            return
        node_id = by_path.get(path)
        if not node_id:
            return
        node_by_id[node_id]["artifact_counts"][key] += amount

    for lb in bundle.get("logic_blocks") or []:
        _bump(_file_from_source(lb.get("source")), "logic_blocks")
    for foot in bundle.get("footnote_definitions") or []:
        _bump(_file_from_source(foot.get("source")), "footnotes")
    for tr in bundle.get("transitions") or []:
        _bump(_file_from_source(tr.get("source")), "transitions")
    for d in bundle.get("diagrams") or []:
        path = str(d.get("file") or d.get("path") or "")
        _bump(path, "diagrams")
    for code in bundle.get("code_references") or []:
        path = str(code.get("file") or code.get("path") or "")
        _bump(path, "code_refs")
    for alias in bundle.get("alias_map") or []:
        _bump(_file_from_source(alias.get("source")), "alias_rows")
    for tbl in bundle.get("two_column_tables") or []:
        _bump(_file_from_source(tbl.get("source")), "two_column_tables")
    for row in bundle.get("test_reference_rows") or []:
        _bump(_file_from_source(row.get("source")), "test_reference_rows")


def _filename_tokens(by_path: dict[str, str]) -> list[tuple[str, str, str]]:
    """Yield (lower_basename, lower_stem, node_id) for fuzzy text matching."""
    out: list[tuple[str, str, str]] = []
    for path, node_id in by_path.items():
        name = _basename(path).lower()
        stem = os.path.splitext(name)[0]
        if name:
            out.append((name, stem, node_id))
    return out


def _sheet_to_node(bundle: dict[str, Any], by_path: dict[str, str]) -> dict[str, str]:
    """Map lower-cased Excel sheet name -> node id (best-effort)."""
    out: dict[str, str] = {}
    for tbl in bundle.get("two_column_tables") or []:
        src = tbl.get("source") or {}
        sheet = str(src.get("sheet") or "").strip()
        path = _file_from_source(src)
        if not sheet or not path:
            continue
        node_id = by_path.get(path)
        if node_id:
            out.setdefault(sheet.lower(), node_id)
    for tr in bundle.get("transitions") or []:
        src = tr.get("source") or {}
        sheet = str(src.get("sheet") or "").strip()
        path = _file_from_source(src)
        if not sheet or not path:
            continue
        node_id = by_path.get(path)
        if node_id:
            out.setdefault(sheet.lower(), node_id)
    return out


def _resolve_text_ref(
    text: str,
    self_node: str | None,
    filename_tokens: list[tuple[str, str, str]],
    sheet_index: dict[str, str],
) -> tuple[str | None, str]:
    """Return (target_node_id, hint_text) when text mentions a known file/sheet."""
    if not text:
        return None, ""
    low = text.lower()
    for name, stem, node_id in filename_tokens:
        if node_id == self_node:
            continue
        if name and name in low:
            return node_id, name
        if stem and len(stem) >= 4 and stem in low:
            return node_id, stem
    for sheet, node_id in sheet_index.items():
        if node_id == self_node:
            continue
        if sheet and len(sheet) >= 4 and sheet in low:
            return node_id, sheet
    return None, ""


def _make_edge(
    *,
    source_id: str,
    target_id: str,
    kind: str,
    label: str = "",
    confidence: str = "auto",
    evidence: list[dict[str, Any]] | None = None,
    suffix: str = "",
) -> dict[str, Any]:
    return {
        "id": _edge_id(source_id, target_id, kind, suffix),
        "source": source_id,
        "target": target_id,
        "kind": kind,
        "label": label or _KIND_LABEL.get(kind, kind),
        "confidence": confidence,
        "evidence": evidence or [],
    }


def _alias_edges(
    bundle: dict[str, Any],
    by_path: dict[str, str],
    filename_tokens: list[tuple[str, str, str]],
    sheet_index: dict[str, str],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for alias in bundle.get("alias_map") or []:
        src = alias.get("source") or {}
        src_path = _file_from_source(src)
        node_id = by_path.get(src_path)
        if not node_id:
            continue
        text = " ".join(
            str(alias.get(k) or "")
            for k in ("raw_text", "target", "alias")
        )
        target, hint = _resolve_text_ref(text, node_id, filename_tokens, sheet_index)
        if not target or target == node_id:
            continue
        edges.append(
            _make_edge(
                source_id=node_id,
                target_id=target,
                kind="alias",
                label=f"alias {alias.get('alias') or ''} → {alias.get('target') or ''}".strip(),
                evidence=[{"file": src_path, "row": src.get("row"), "excerpt": alias.get("raw_text", "")[:160], "match": hint}],
                suffix=str(alias.get("alias") or hint),
            )
        )
    return edges


def _footnote_edges(
    bundle: dict[str, Any],
    by_path: dict[str, str],
    filename_tokens: list[tuple[str, str, str]],
    sheet_index: dict[str, str],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for foot in bundle.get("footnote_definitions") or []:
        src = foot.get("source") or {}
        src_path = _file_from_source(src)
        node_id = by_path.get(src_path)
        if not node_id:
            continue
        body = str(foot.get("definition") or foot.get("raw_text") or "")
        if not body:
            continue
        # Cross-ref stubs emitted by the parser take priority, fall back to text scan.
        cross_refs = foot.get("cross_refs") or []
        if cross_refs:
            for ref in cross_refs:
                if not isinstance(ref, dict):
                    continue
                target = ref.get("resolved_node") or None
                hint = ref.get("text") or ""
                if not target:
                    target, hint = _resolve_text_ref(hint, node_id, filename_tokens, sheet_index)
                if not target or target == node_id:
                    continue
                edges.append(
                    _make_edge(
                        source_id=node_id,
                        target_id=target,
                        kind="footnote_ref",
                        label=f"footnote {foot.get('ref') or ''} → {hint}".strip(),
                        evidence=[
                            {
                                "file": src_path,
                                "paragraph": src.get("paragraph"),
                                "row": src.get("row"),
                                "excerpt": body[:200],
                                "ref": foot.get("ref"),
                            }
                        ],
                        suffix=str(foot.get("ref") or "") + ":" + hint,
                    )
                )
            continue
        # Generic text scan for "refer", "see sheet", filenames
        lowered = body.lower()
        if not any(token in lowered for token in ("refer", "see ", "sheet", ".docx", ".xlsx", ".pdf")):
            continue
        target, hint = _resolve_text_ref(body, node_id, filename_tokens, sheet_index)
        if not target or target == node_id:
            continue
        edges.append(
            _make_edge(
                source_id=node_id,
                target_id=target,
                kind="footnote_ref",
                label=f"footnote {foot.get('ref') or ''} → {hint}".strip(),
                evidence=[
                    {
                        "file": src_path,
                        "paragraph": src.get("paragraph"),
                        "row": src.get("row"),
                        "excerpt": body[:200],
                        "ref": foot.get("ref"),
                    }
                ],
                suffix=str(foot.get("ref") or "") + ":" + hint,
            )
        )
    return edges


def _diagram_edges(
    bundle: dict[str, Any],
    by_path: dict[str, str],
    filename_tokens: list[tuple[str, str, str]],
    sheet_index: dict[str, str],
) -> list[dict[str, Any]]:
    diagram_nodes = [
        by_path[str(d.get("file") or d.get("path") or "")]
        for d in bundle.get("diagrams") or []
        if (d.get("file") or d.get("path")) and (d.get("file") or d.get("path")) in by_path
    ]
    edges: list[dict[str, Any]] = []
    for tr in bundle.get("transitions") or []:
        link = str(tr.get("diagram_link") or "").strip()
        if not link:
            continue
        src = tr.get("source") or {}
        src_path = _file_from_source(src)
        node_id = by_path.get(src_path)
        if not node_id:
            continue
        target, hint = _resolve_text_ref(link, node_id, filename_tokens, sheet_index)
        if not target and diagram_nodes:
            # No file-name match: link to the first diagram asset in the same job.
            target = diagram_nodes[0]
            hint = link[:80]
        if not target or target == node_id:
            continue
        edges.append(
            _make_edge(
                source_id=node_id,
                target_id=target,
                kind="diagram_link",
                label=f"{tr.get('from_state') or '?'} → {tr.get('to_state') or '?'}",
                evidence=[
                    {
                        "file": src_path,
                        "sheet": src.get("sheet"),
                        "row": src.get("row"),
                        "excerpt": link[:200],
                    }
                ],
                suffix=str(tr.get("id") or hint),
            )
        )
    return edges


def _role_edges(
    nodes: list[dict[str, Any]],
    controls: set[str],
    bundle: dict[str, Any],
    by_path: dict[str, str],
) -> list[dict[str, Any]]:
    """Heuristic edges from role: test_spec/reference → system_spec; code → system_spec."""
    spec_nodes = [n for n in nodes if n.get("role") == "system_spec"]
    if not spec_nodes:
        return []
    edges: list[dict[str, Any]] = []
    spec_ids = [n["id"] for n in spec_nodes]
    # Test spec / reference → first system spec.
    for n in nodes:
        role = n.get("role") or ""
        if role in {"test_spec_reference", "test_spec"}:
            target = spec_ids[0]
            edges.append(
                _make_edge(
                    source_id=n["id"],
                    target_id=target,
                    kind="test_derived_from",
                    label=f"{n.get('name')} derived from {spec_nodes[0].get('name')}",
                    confidence="auto",
                    evidence=[{"reason": "Test spec inferred from same job as system spec"}],
                    suffix=n["id"],
                )
            )
    # Code → system spec only if a code reference mentions a known control.
    code_files_with_controls: dict[str, list[str]] = defaultdict(list)
    for code in bundle.get("code_references") or []:
        path = str(code.get("file") or code.get("path") or "")
        if not path or path not in by_path:
            continue
        hints = " ".join(str(h) for h in (code.get("hints") or [])).upper()
        for control in controls:
            if control and control in hints:
                code_files_with_controls[by_path[path]].append(control)
    for code_node_id, control_hits in code_files_with_controls.items():
        target = spec_ids[0]
        edges.append(
            _make_edge(
                source_id=code_node_id,
                target_id=target,
                kind="code_implements",
                label=f"implements {', '.join(sorted(set(control_hits))[:3])}",
                evidence=[{"controls": sorted(set(control_hits))}],
                suffix=code_node_id,
            )
        )
    return edges


def _reconcile_edges(
    bundle: dict[str, Any],
    by_path: dict[str, str],
) -> list[dict[str, Any]]:
    """Surface logic_reconciler mismatches as file↔file edges when sources differ."""
    edges: list[dict[str, Any]] = []
    # logic_blocks may carry "superseded_by_formula" (id pointing at canonical block)
    canon_by_id: dict[str, dict[str, Any]] = {
        str(b.get("id") or ""): b for b in bundle.get("logic_blocks") or []
    }
    for block in bundle.get("logic_blocks") or []:
        canon_id = str(block.get("superseded_by_formula") or "")
        if not canon_id:
            continue
        canon = canon_by_id.get(canon_id)
        if not canon:
            continue
        src_path = _file_from_source(block.get("source"))
        target_path = _file_from_source(canon.get("source"))
        src_node = by_path.get(src_path)
        target_node = by_path.get(target_path)
        if not src_node or not target_node or src_node == target_node:
            continue
        edges.append(
            _make_edge(
                source_id=src_node,
                target_id=target_node,
                kind="reconciles",
                label=f"{block.get('name')} aligns with paragraph formula",
                evidence=[
                    {
                        "table_block": block.get("id"),
                        "canonical_block": canon.get("id"),
                    }
                ],
                suffix=str(block.get("id") or ""),
            )
        )
    return edges


def _dedupe_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for edge in edges:
        key = edge.get("id") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


def build_document_graph(bundle: dict[str, Any]) -> dict[str, Any]:
    """Build the document graph section from a parsed bundle.

    User-defined edges already on the bundle are preserved untouched and
    merged into the returned ``user_edges`` list. Auto edges are recomputed
    every call so they stay in sync with the latest analysis.
    """
    classified_files = bundle.get("classified_files") or []
    nodes, by_path = _build_node_index(classified_files)
    _fill_artifact_counts(bundle, nodes, by_path)

    if not nodes:
        return {
            "version": "1",
            "nodes": [],
            "edges": [],
            "user_edges": list(((bundle.get("document_graph") or {}).get("user_edges")) or []),
            "summary": {"node_count": 0, "edge_count": 0, "user_edge_count": 0, "unresolved_refs": 0},
        }

    filename_tokens = _filename_tokens(by_path)
    sheet_index = _sheet_to_node(bundle, by_path)
    controls = _control_set(bundle)

    auto_edges: list[dict[str, Any]] = []
    auto_edges.extend(_alias_edges(bundle, by_path, filename_tokens, sheet_index))
    auto_edges.extend(_footnote_edges(bundle, by_path, filename_tokens, sheet_index))
    auto_edges.extend(_diagram_edges(bundle, by_path, filename_tokens, sheet_index))
    auto_edges.extend(_role_edges(nodes, controls, bundle, by_path))
    auto_edges.extend(_reconcile_edges(bundle, by_path))
    auto_edges = _dedupe_edges(auto_edges)

    previous = bundle.get("document_graph") or {}
    user_edges = list(previous.get("user_edges") or [])

    node_ids = {n["id"] for n in nodes}
    user_edges = [
        e
        for e in user_edges
        if isinstance(e, dict) and e.get("source") in node_ids and e.get("target") in node_ids
    ]

    unresolved = 0
    for foot in bundle.get("footnote_definitions") or []:
        for ref in foot.get("cross_refs") or []:
            if isinstance(ref, dict) and not ref.get("resolved_node"):
                unresolved += 1

    return {
        "version": "1",
        "nodes": nodes,
        "edges": auto_edges,
        "user_edges": user_edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(auto_edges),
            "user_edge_count": len(user_edges),
            "unresolved_refs": unresolved,
        },
    }


def add_user_edge(
    graph: dict[str, Any],
    *,
    source_id: str,
    target_id: str,
    label: str = "",
    kind: str = "user_defined",
    note: str = "",
) -> dict[str, Any]:
    """Append a user edge to ``graph``. Raises ``ValueError`` if invalid."""
    if not graph:
        raise ValueError("Document graph not built yet")
    node_ids = {n["id"] for n in graph.get("nodes") or []}
    if source_id not in node_ids or target_id not in node_ids:
        raise ValueError("source/target must reference known document nodes")
    if source_id == target_id:
        raise ValueError("source and target must differ")
    edge = _make_edge(
        source_id=source_id,
        target_id=target_id,
        kind=kind or "user_defined",
        label=label or _KIND_LABEL.get("user_defined", "linked by engineer"),
        confidence="user",
        evidence=[{"note": note}] if note else [],
        suffix=f"user:{label}:{note}",
    )
    user_edges = list(graph.get("user_edges") or [])
    if any(e.get("id") == edge["id"] for e in user_edges):
        raise ValueError("Identical user edge already exists")
    user_edges.append(edge)
    graph["user_edges"] = user_edges
    summary = dict(graph.get("summary") or {})
    summary["user_edge_count"] = len(user_edges)
    graph["summary"] = summary
    return edge


def update_user_edge(
    graph: dict[str, Any],
    edge_id: str,
    *,
    label: str | None = None,
    kind: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    user_edges = list(graph.get("user_edges") or [])
    for edge in user_edges:
        if edge.get("id") != edge_id:
            continue
        if label is not None:
            edge["label"] = label
        if kind is not None:
            edge["kind"] = kind or "user_defined"
        if note is not None:
            edge["evidence"] = [{"note": note}] if note else []
        graph["user_edges"] = user_edges
        return edge
    raise KeyError(f"User edge not found: {edge_id}")


def delete_user_edge(graph: dict[str, Any], edge_id: str) -> None:
    user_edges = [e for e in (graph.get("user_edges") or []) if e.get("id") != edge_id]
    if len(user_edges) == len(graph.get("user_edges") or []):
        raise KeyError(f"User edge not found: {edge_id}")
    graph["user_edges"] = user_edges
    summary = dict(graph.get("summary") or {})
    summary["user_edge_count"] = len(user_edges)
    graph["summary"] = summary


def node_detail(bundle: dict[str, Any], graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Build a per-node detail panel: artifact excerpts + edges (in/out)."""
    nodes = graph.get("nodes") or []
    node = next((n for n in nodes if n.get("id") == node_id), None)
    if not node:
        raise KeyError(f"Document node not found: {node_id}")

    path = node.get("file") or ""

    def _matches(source: Any) -> bool:
        return _file_from_source(source) == path

    logic_blocks = [
        {
            "id": lb.get("id"),
            "name": lb.get("name"),
            "raw_expression": lb.get("raw_expression"),
            "source": lb.get("source") or {},
            "parse_status": lb.get("parse_status"),
        }
        for lb in (bundle.get("logic_blocks") or [])
        if _matches(lb.get("source"))
    ]
    footnotes = [
        {
            "ref": foot.get("ref"),
            "condition_name": foot.get("condition_name"),
            "definition": (foot.get("definition") or foot.get("raw_text") or "")[:240],
            "source": foot.get("source") or {},
            "cross_refs": foot.get("cross_refs") or [],
        }
        for foot in (bundle.get("footnote_definitions") or [])
        if _matches(foot.get("source"))
    ]
    transitions = [
        {
            "id": tr.get("id"),
            "from_state": tr.get("from_state"),
            "to_state": tr.get("to_state"),
            "event": tr.get("event"),
            "diagram_link": tr.get("diagram_link"),
            "source": tr.get("source") or {},
        }
        for tr in (bundle.get("transitions") or [])
        if _matches(tr.get("source"))
    ]
    diagrams = [
        {
            "file": d.get("file") or d.get("path"),
            "kind": d.get("kind"),
            "ocr_text": (d.get("ocr_text") or d.get("text") or "")[:280],
        }
        for d in (bundle.get("diagrams") or [])
        if str(d.get("file") or d.get("path") or "") == path
    ]
    code_refs = [
        {
            "file": c.get("file") or c.get("path"),
            "hints": c.get("hints") or [],
            "length_chars": c.get("length_chars"),
        }
        for c in (bundle.get("code_references") or [])
        if str(c.get("file") or c.get("path") or "") == path
    ]

    all_edges = list(graph.get("edges") or []) + list(graph.get("user_edges") or [])
    outgoing = [e for e in all_edges if e.get("source") == node_id]
    incoming = [e for e in all_edges if e.get("target") == node_id]

    return {
        "node": node,
        "logic_blocks": logic_blocks,
        "footnotes": footnotes,
        "transitions": transitions,
        "diagrams": diagrams,
        "code_refs": code_refs,
        "outgoing_edges": outgoing,
        "incoming_edges": incoming,
    }
