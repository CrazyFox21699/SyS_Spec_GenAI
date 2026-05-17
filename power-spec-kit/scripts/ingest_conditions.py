#!/usr/bin/env python3
"""
Build condition_index.json from Excel CSV export or a plain-text Word dump.

Designed for Python 3.11+; uses stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1


def norm_header(h: str) -> str:
    h = unicodedata.normalize("NFKC", (h or "").strip())
    key = "".join(ch.lower() if ch.isascii() else ch for ch in h)
    replacements = {" ": "", "_": "", "-": "", "　": ""}
    for old, new in replacements.items():
        key = key.replace(old, new)
    return key


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "条件", "要件名", "condition", "名前", "name"),
    "applies_to": ("applies_to", "appliesto", "scope", "適用", "variant", "ecu"),
    "raw_givens": ("givens", "predicate", "predicates", "signals", "条件式", "前提", "入力"),
    "dependencies": ("deps", "dependencies", "依存", "prereq", "前提条件id"),
    "evidence_file": ("source", "ファイル", "file", "evidencefile", "doc"),
    "evidence_location": ("location", "箇所", "section", "sheet", "page", "clause"),
    "quote": ("quote", "引用", "抜粋", "snippet"),
    "references": ("references", "refs", "参照", "see", "備考参照"),
}


REF_FUZZY_PATTERNS = [
    re.compile(
        r"\b(?:see|refer(?:\s+to)?|cf\.)\b[^\n.。]{2,140}",
        re.IGNORECASE,
    ),
    re.compile(r"詳細(?:は|について)[^\n。]{2,120}"),
    re.compile(r"別紙[^\n。]{2,80}"),
    re.compile(r"添付[^\n。]{2,80}"),
    re.compile(r"仕様書\s*[^\s、,]{3,80}"),
]
DOC_TOKEN = re.compile(
    r"\b(?:DOC|SPEC|SWR|IDB|REQ|TBD)[_-]?\w+\b|\bREV[-_]?\d+\b|\b\S+\.(?:docx?|pdf|xlsx?)\b",
    re.IGNORECASE,
)


@dataclass
class CSVRowParts:
    title: str
    applies_to: str
    raw_givens: str
    dependencies: str
    evidence_file: str
    evidence_location: str
    quote: str
    references: str


def sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter  # type: ignore[union-attr]
    except csv.Error:
        return ","


def extract_unresolved(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in REF_FUZZY_PATTERNS:
        hits.extend(m.group(0).strip() for m in pat.finditer(blob))
    for m in DOC_TOKEN.finditer(blob):
        token = m.group(0).strip()
        if token not in hits:
            hits.append(token)
    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for h in hits:
        norm = " ".join(h.split())
        if norm not in seen:
            seen.add(norm)
            uniq.append(norm)
    return uniq[:200]


def parse_dependencies_blob(blob: str) -> list[str]:
    if not blob.strip():
        return []
    ids: list[str] = []
    for part in re.split(r"[,;、／/|\s]+", blob):
        p = part.strip()
        if re.fullmatch(r"COND_\d+", p.upper()):
            ids.append(p.upper())
    return ids


def try_parse_predicate_clauses(blob: str) -> list[dict[str, Any]] | None:
    """If blob looks like structured clauses (SIG==x; SIG>=y), return IR predicates."""
    if (
        "==" not in blob
        and "!=" not in blob
        and "=" not in blob
        and not re.search(r"[<>]", blob)
    ):
        return None
    parts = [p.strip() for p in blob.split(";") if p.strip()]
    if not parts:
        return None
    out: list[dict[str, Any]] = []
    for part in parts:
        m = re.match(
            r"^([A-Za-z0-9_.]+)\s*(==|!=|<=|>=|<|>|=)\s*(.+)$",
            part,
        )
        if not m:
            return None
        signal, comparator, raw_val = m.group(1), m.group(2), m.group(3).strip()
        if comparator == "=":
            comparator = "=="
        value: Any
        low = raw_val.lower()
        if low in ("true", "false"):
            value = low == "true"
        else:
            try:
                value = float(raw_val) if "." in raw_val else int(raw_val)
            except ValueError:
                value = raw_val.strip("\"'")
        out.append({"signal": signal, "comparator": comparator, "value": value})
    return out or None


def resolve_field_index(norm_to_idx: dict[str, int], field: str) -> int | None:
    aliases = HEADER_ALIASES.get(field, ())
    seq = (field,) + aliases
    for name in seq:
        nk = norm_header(name)
        if nk and nk in norm_to_idx:
            return norm_to_idx[nk]
    return None


def build_field_map(header_row: Sequence[str]) -> dict[str, int]:
    norm_to_idx: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        nk = norm_header(cell)
        if nk:
            norm_to_idx.setdefault(nk, i)

    mh: dict[str, int] = {}
    for key in HEADER_ALIASES:
        idx = resolve_field_index(norm_to_idx, key)
        if idx is not None:
            mh[key] = idx
    return mh


def row_get(row: list[str], idx: int | None) -> str:
    if idx is None:
        return ""
    if idx < 0 or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def ingest_csv_rows(rows: Iterable[list[str]]) -> tuple[list[Any], list[dict[str, Any]]]:
    it = iter(rows)
    header = next(it, None)
    if not header:
        return [], []

    mh = build_field_map(header)
    conditions: list[dict[str, Any]] = []
    unresolved_pool: dict[str, dict[str, Any]] = {}

    title_idx = mh.get("title") if mh.get("title") is not None else (0 if len(header) > 0 else None)
    for offset, cells in enumerate(it, start=2):
        if not cells or all(not (c or "").strip() for c in cells):
            continue
        parts = CSVRowParts(
            title=row_get(list(cells), title_idx),
            applies_to=row_get(list(cells), mh.get("applies_to")),
            raw_givens=row_get(list(cells), mh.get("raw_givens")),
            dependencies=row_get(list(cells), mh.get("dependencies")),
            evidence_file=row_get(list(cells), mh.get("evidence_file")),
            evidence_location=row_get(list(cells), mh.get("evidence_location")),
            quote=row_get(list(cells), mh.get("quote")),
            references=row_get(list(cells), mh.get("references")),
        )
        if not parts.title and not parts.raw_givens:
            continue
        cid = f"COND_{len(conditions)+1:03d}"
        joined = "\n".join(
            filter(
                None,
                [
                    parts.title,
                    parts.applies_to,
                    parts.raw_givens,
                    parts.dependencies,
                    parts.references,
                    parts.quote,
                ],
            )
        )

        preds: list[dict[str, Any]] = []
        if parts.raw_givens:
            structured = try_parse_predicate_clauses(parts.raw_givens)
            if structured:
                preds.extend(structured)
            else:
                preds.append(
                    {
                        "signal": "INGEST_NATURAL_LANGUAGE",
                        "comparator": "==",
                        "value": parts.raw_givens,
                    }
                )
        elif parts.title:
            preds.append(
                {
                    "signal": "INGEST_TITLE_ONLY_ROW",
                    "comparator": "==",
                    "value": "__NEEDS_SIGNAL_DETAIL__",
                }
            )

        evid: list[dict[str, str]] = []
        if parts.evidence_file or parts.evidence_location or parts.quote:
            ev: dict[str, str] = {"file": parts.evidence_file or "UNKNOWN_SOURCE"}
            if parts.evidence_location:
                ev["location"] = parts.evidence_location
            if parts.quote:
                ev["quote"] = parts.quote
            evid.append(ev)
        else:
            evid.append({"file": "UNKNOWN_SOURCE"})

        for hint in extract_unresolved(joined):
            if hint not in unresolved_pool:
                unresolved_pool[hint] = {"text": hint, "seen_in_rows": [offset]}
            else:
                unresolved_pool[hint]["seen_in_rows"].append(offset)

        cond: dict[str, Any] = {
            "id": cid,
            "title": parts.title or "(untitled)",
            "applies_to": parts.applies_to or "__UNSPECIFIED_SCOPE__",
            "predicates": preds,
            "dependencies": parse_dependencies_blob(parts.dependencies),
            "source_evidence": evid,
            "source_row_csv": offset,
            "references_raw": parts.references or "",
        }
        conditions.append(cond)

    unresolved = sorted(
        unresolved_pool.values(),
        key=lambda x: (min(x["seen_in_rows"]), x["text"]),
    )
    return conditions, unresolved


def read_csv(path: Path) -> Iterable[list[str]]:
    raw_head = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]
    delim = sniff_delimiter(raw_head)
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        for row in reader:
            yield row


def read_text_dump(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    segments = [s.strip() for s in re.split(r"\n{3,}|={4,}|_{4,}|-{4,}", text) if s.strip()]
    pairs: list[tuple[dict[str, Any], list[str]]] = []
    for i, block in enumerate(segments, start=1):
        title_line = block.splitlines()[0].strip()[:200]
        cid = f"COND_{len(pairs)+1:03d}"
        unresolved = extract_unresolved(block)
        cond = {
            "id": cid,
            "title": title_line or f"Paragraph block {i}",
            "applies_to": "__FROM_TEXT_DUMP__",
            "predicates": [
                {
                    "signal": "INGEST_NATURAL_LANGUAGE",
                    "comparator": "==",
                    "value": block,
                }
            ],
            "dependencies": parse_dependencies_blob(block),
            "source_evidence": [{"file": str(path), "location": f"block_{i}"}],
            "source_row_csv": None,
            "references_raw": "",
            "notes": ["plain_text_word_export"],
        }
        pairs.append((cond, unresolved))
    flat_unresolved: dict[str, dict[str, Any]] = {}
    for cond, unr in pairs:
        for u in unr:
            if u not in flat_unresolved:
                flat_unresolved[u] = {"text": u, "seen_in_rows": ["text_dump"]}

    simplified = [c for c, _ in pairs]
    return simplified, sorted(flat_unresolved.values(), key=lambda x: x["text"])


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Ingest-condition rows into condition_index.json")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=Path, help="CSV export from Excel (UTF-8 or UTF-8-SIG)")
    src.add_argument("--text-word-dump", type=Path, help="Plain text export from Word (blocks separated by blank lines)")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("condition_index.json"),
        help="Output path (default: ./condition_index.json)",
    )
    ap.add_argument(
        "--meta-source-label",
        default="",
        help="Optional label describing document batch (e.g. project phase)",
    )
    args = ap.parse_args(list(argv))

    if args.csv:
        conditions, unresolved = ingest_csv_rows(read_csv(args.csv))
        meta = {"kind": "csv", "path": str(args.csv.resolve())}
    else:
        conds, unresolved = read_text_dump(args.text_word_dump)
        conditions = conds
        meta = {"kind": "text_word_dump", "path": str(args.text_word_dump.resolve())}

    doc = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            **meta,
            "label": args.meta_source_label or None,
            "warnings": [],
        },
        "conditions": conditions,
        "unresolved_references": unresolved,
    }
    if not conditions:
        doc["metadata"]["warnings"].append("no_conditions_detected_review_headers_or_input")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sys.stderr.write(
        f"Wrote {len(conditions)} condition(s); {len(unresolved)} unresolved ref hint(s).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
