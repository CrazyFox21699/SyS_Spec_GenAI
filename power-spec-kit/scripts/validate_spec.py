#!/usr/bin/env python3
"""
Validate testcase specs (YAML or JSON) describing power-mode triplets.

Python 3.11+. Requires PyYAML for .yaml/.yml inputs (see ../requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_KEYS = frozenset({"description", "given", "expectation", "test_id"})
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokens(s: str) -> set[str]:
    return set(TOKEN_RE.findall(s.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_documents(path: Path) -> Mapping[str, Any]:
    suf = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suf in {".yaml", ".yml"}:
        if yaml is None:
            sys.stderr.write("PyYAML required for YAML files. pip install PyYAML\n")
            raise SystemExit(2)
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Top-level YAML/JSON root must be an object.")
    return data


def collect_testcases(payload: Mapping[str, Any]) -> list[MutableMapping[str, Any]]:
    raw = payload.get("testcases")
    if isinstance(raw, list):
        tc = raw
    else:
        raise ValueError(
            'Expected JSON/YAML object with top-level key "testcases" containing a list.'
        )
    rows: list[MutableMapping[str, Any]] = []
    for idx, obj in enumerate(tc):
        if not isinstance(obj, dict):
            raise ValueError(f"testcases[{idx}] must be object")
        rows.append(dict(obj))
    return rows


def load_condition_index(index_path: Path) -> dict[str, dict[str, Any]]:
    blob = json.loads(index_path.read_text(encoding="utf-8"))
    cons = blob.get("conditions")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(cons, list):
        for c in cons:
            if isinstance(c, dict):
                cid = str(c.get("id", "") or "").strip().upper()
                if cid:
                    out[cid] = c  # canonical keys preserved
    return out


def signals_from_condition(cond: Mapping[str, Any]) -> set[str]:
    preds = cond.get("predicates") or []
    agg: set[str] = set()
    if isinstance(preds, Sequence) and not isinstance(preds, (str, bytes)):
        for p in preds:
            if not isinstance(p, dict):
                continue
            sig = str(p.get("signal", "") or "")
            val = p.get("value")
            if sig.startswith("INGEST_"):
                if isinstance(val, str):
                    agg.update(tokens(val))
                continue

            agg.update(tokens(sig))
            if isinstance(val, str):
                agg.update(tokens(val))
    return agg


def normalize_given(tc: MutableMapping[str, Any]) -> None:
    """Collapse list-valued `given` to a single string for validation."""
    g = tc.get("given")
    if isinstance(g, list):
        parts = [str(x).strip() for x in g if str(x).strip()]
        tc["given"] = "; ".join(parts) if parts else ""
    elif g is None:
        tc["given"] = ""
    elif not isinstance(g, str):
        tc["given"] = str(g)


def classify_cases(testcases: list[MutableMapping[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, tc in enumerate(testcases):
        normalize_given(tc)
        prefix = f"testcases[{i}] ({tc.get('test_id','?')})"
        missing = sorted(REQUIRED_KEYS - set(tc))
        if missing:
            errors.append(f"{prefix}: missing keys {missing}")
            continue

        blank = []
        for k in REQUIRED_KEYS:
            field = tc.get(k)
            if not isinstance(field, str):
                blank.append(k)
                continue
            if not field.strip():
                blank.append(k)
                continue
            # ASCII token heuristic is misleading for Japanese descriptions; skip if CJK present.
            if k != "test_id" and len(tokens(field)) < 2 and not re.search(
                r"[\u3040-\u30ff\u4e00-\u9fff]",
                field,
            ):
                warnings.append(f"{prefix}: `{k}` has very low token density (review readability)")
        if blank:
            errors.append(f"{prefix}: blank or non-string required fields {blank}")

        refs = tc.get("ir_refs")
        if refs is not None:
            if not isinstance(refs, list) or not all(isinstance(x, str) and x.strip() for x in refs):
                errors.append(f"{prefix}: ir_refs must be list of non-empty strings")
    return errors, warnings


def predicate_coverage_warnings(
    testcases: list[MutableMapping[str, Any]],
    index_lookup: Mapping[str, dict[str, Any]],
    threshold: float,
) -> list[str]:
    warnings: list[str] = []
    for i, tc in enumerate(testcases):
        refs = tc.get("ir_refs")
        if not refs or not isinstance(refs, list):
            continue

        agg: set[str] = set()
        missing_ids: list[str] = []
        for rid_raw in refs:
            rid = str(rid_raw).strip().upper()
            cond = index_lookup.get(rid)
            if cond is None:
                missing_ids.append(rid)
            else:
                agg |= signals_from_condition(cond)
        if missing_ids:
            warnings.append(
                f"testcases[{i}] ({tc.get('test_id','?')}): ir_refs not found in index: "
                + ", ".join(missing_ids)
            )
            continue

        gv = tc.get("given")
        if not isinstance(gv, str):
            continue

        gv_tok = tokens(gv)
        if not agg:
            warnings.append(f"testcases[{i}] ({tc.get('test_id','?')}): IR predicates yielded no comparable tokens.")
            continue

        overlap = len(gv_tok & agg) / len(agg)
        if overlap < threshold:
            warnings.append(
                f"testcases[{i}] ({tc.get('test_id','?')}): given vs IR predicate token overlap ratio "
                f"{overlap:.2f} < {threshold:.2f} (predicate tokens ~ {sorted(agg)})"
            )

    return warnings


def dup_description_warnings(testcases: list[MutableMapping[str, Any]], threshold: float) -> list[str]:
    id_to_description: dict[str, str] = {}
    for tc in testcases:
        tid = str(tc.get("test_id", "")).strip()
        desc = tc.get("description")
        if tid and isinstance(desc, str):
            id_to_description[tid] = desc

    uniq_ids = list(id_to_description)
    warns: list[str] = []

    # Pairwise comparisons (pilot-safe for small manifests)
    for i_a in range(len(uniq_ids)):
        for i_b in range(i_a + 1, len(uniq_ids)):
            ida = uniq_ids[i_a]
            idb = uniq_ids[i_b]
            a_desc = id_to_description[ida]
            b_desc = id_to_description[idb]
            jac = jaccard(tokens(a_desc), tokens(b_desc))
            if jac >= threshold:
                warns.append(
                    f"Duplicate-ish descriptions (Jaccard {jac:.2f}) between `{ida}` and `{idb}` "
                    "(distinct test_id but similar wording)."
                )

    return warns


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Validate Description/Given/Expectation testcase blobs.")
    ap.add_argument("spec", type=Path, help="YAML or JSON file")
    ap.add_argument(
        "--ir-index",
        type=Path,
        default=None,
        help="Optional condition_index.json for IR predicate overlap checks",
    )
    ap.add_argument(
        "--overlap-threshold",
        type=float,
        default=0.25,
        help="Warn if fewer than this fraction of IR predicate tokens appears in Given (when ir_refs set).",
    )
    ap.add_argument(
        "--dup-description-threshold",
        type=float,
        default=0.85,
        help="Warn if Jaccard token similarity exceeds this threshold for description pairs.",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    ns = ap.parse_args(list(argv))

    data = load_documents(ns.spec)
    testcases = collect_testcases(data)

    errors, hard_warnings = classify_cases(testcases)
    warnings = list(hard_warnings)

    index_lookup: dict[str, dict[str, Any]] = {}
    if ns.ir_index:
        index_lookup = load_condition_index(ns.ir_index)

    warnings.extend(predicate_coverage_warnings(testcases, index_lookup, ns.overlap_threshold))
    warnings.extend(dup_description_warnings(testcases, ns.dup_description_threshold))

    for e in errors:
        sys.stderr.write(f"ERROR: {e}\n")
    for w in warnings:
        sys.stderr.write(f"WARN : {w}\n")

    if errors:
        sys.stderr.write(f"\nFailures: {len(errors)} error(s).\n")
        code = 1
    else:
        code = 0
        sys.stderr.write("OK: testcase structure validated.\n")

    if warnings and ns.strict:
        code = max(code, 1)
        sys.stderr.write(f"{len(warnings)} warning(s) promoted to failures via --strict.\n")

    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: invalid input: {exc}\n")
        raise SystemExit(1)
