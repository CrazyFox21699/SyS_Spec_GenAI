"""Mine Given/Then fingerprints and build 1-to-N / N-to-1 verification matrices."""

from __future__ import annotations

import re
from typing import Any

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

_GIVEN_RE = re.compile(r"(?im)^\s*Given:\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.+)$")
_THEN_SIG_RE = re.compile(r"(?im)^\s*Then:\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.+)$")
_THEN_STATE_RE = re.compile(r"(?im)^\s*Then:\s*System state\s*=\s*(.+)$")


def _given_fingerprint(text: str) -> str:
    pairs: list[str] = []
    for line in str(text or "").splitlines():
        m = _GIVEN_RE.match(line.strip())
        if m:
            pairs.append(f"{m.group(1).upper()}={m.group(2).strip()}")
    return "|".join(sorted(pairs))


def _then_fingerprint(text: str) -> str:
    pairs: list[str] = []
    for line in str(text or "").splitlines():
        line = line.strip()
        m = _THEN_SIG_RE.match(line)
        if m:
            pairs.append(f"{m.group(1).upper()}={m.group(2).strip()}")
            continue
        m_state = _THEN_STATE_RE.match(line)
        if m_state:
            pairs.append(f"SYSTEM_STATE={m_state.group(1).strip()}")
    return "|".join(sorted(pairs))


def _then_signals(text: str) -> list[str]:
    signals: list[str] = []
    for line in str(text or "").splitlines():
        m = _THEN_SIG_RE.match(line.strip())
        if m:
            signals.append(m.group(1).upper())
        elif _THEN_STATE_RE.match(line.strip()):
            signals.append("SYSTEM_STATE")
    return sorted(set(signals))


def build_verification_matrix(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    preview = build_customer_testspec_preview(bundle, language=language)
    rows: list[dict[str, Any]] = []
    for row in preview.get("rows") or []:
        if str(row.get("logic_id") or "") != logic_id:
            continue
        given_fp = _given_fingerprint(row.get("expected_input") or "")
        then_fp = _then_fingerprint(row.get("expected_output") or "")
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "given_fingerprint": given_fp,
                "then_fingerprint": then_fp,
                "then_signals": _then_signals(row.get("expected_output") or ""),
            }
        )

    input_to_outputs: dict[str, list[dict[str, Any]]] = {}
    output_to_inputs: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        gfp = row["given_fingerprint"] or "(empty)"
        tfp = row["then_fingerprint"] or "(empty)"
        input_to_outputs.setdefault(gfp, [])
        if not any(x["then_fingerprint"] == tfp for x in input_to_outputs[gfp]):
            input_to_outputs[gfp].append(
                {
                    "then_fingerprint": tfp,
                    "then_signals": row["then_signals"],
                    "candidate_ids": [row["candidate_id"]],
                }
            )
        else:
            for item in input_to_outputs[gfp]:
                if item["then_fingerprint"] == tfp and row["candidate_id"] not in item["candidate_ids"]:
                    item["candidate_ids"].append(row["candidate_id"])

        output_to_inputs.setdefault(tfp, [])
        if not any(x["given_fingerprint"] == gfp for x in output_to_inputs[tfp]):
            output_to_inputs[tfp].append(
                {"given_fingerprint": gfp, "candidate_ids": [row["candidate_id"]]}
            )
        else:
            for item in output_to_inputs[tfp]:
                if item["given_fingerprint"] == gfp and row["candidate_id"] not in item["candidate_ids"]:
                    item["candidate_ids"].append(row["candidate_id"])

    one_to_many = [
        {"given_fingerprint": gfp, "variants": variants}
        for gfp, variants in input_to_outputs.items()
        if len(variants) > 1
    ]
    many_to_one = [
        {"then_fingerprint": tfp, "variants": variants}
        for tfp, variants in output_to_inputs.items()
        if len(variants) > 1
    ]

    ambiguous: list[dict[str, Any]] = []
    for gfp, variants in input_to_outputs.items():
        signals_seen: dict[str, set[str]] = {}
        for v in variants:
            for sig in v.get("then_signals") or []:
                for part in (v.get("then_fingerprint") or "").split("|"):
                    if not part.startswith(f"{sig}="):
                        continue
                    val = part.split("=", 1)[-1]
                    signals_seen.setdefault(sig, set()).add(val)
        for sig, vals in signals_seen.items():
            if len(vals) > 1:
                ambiguous.append({"given_fingerprint": gfp, "signal": sig, "values": sorted(vals)})

    partial_assert: list[dict[str, Any]] = []
    for gfp, variants in input_to_outputs.items():
        if len(variants) != 1:
            continue
        variant = variants[0]
        all_signals: set[str] = set()
        for other in rows:
            if other["given_fingerprint"] == gfp:
                all_signals.update(other["then_signals"])
        missing = sorted(all_signals - set(variant.get("then_signals") or []))
        if missing:
            partial_assert.append(
                {
                    "given_fingerprint": gfp,
                    "candidate_ids": variant.get("candidate_ids") or [],
                    "missing_then_signals": missing,
                }
            )

    return {
        "logic_id": logic_id,
        "row_count": len(rows),
        "one_to_many_count": len(one_to_many),
        "many_to_one_count": len(many_to_one),
        "one_to_many": one_to_many[:20],
        "many_to_one": many_to_one[:20],
        "ambiguous": ambiguous[:20],
        "partial_assert_count": len(partial_assert),
        "partial_assert": partial_assert[:20],
        "input_to_outputs": {k: v for k, v in list(input_to_outputs.items())[:30]},
    }
