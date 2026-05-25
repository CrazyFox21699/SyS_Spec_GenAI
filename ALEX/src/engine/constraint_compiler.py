"""Deterministic compiler: accepted constraints + MCDC path intent → Given patches."""

from __future__ import annotations

from typing import Any

from src.engine.coverage_intent import path_coverage_intent
from src.engine.structured_overlay import accepted_constraints


def _satisfy_pool(constraint: dict[str, Any]) -> list[str]:
    kind = constraint.get("kind")
    unit = str(constraint.get("unit") or "").strip()
    suffix = f" {unit}" if unit else ""

    if kind == "equality":
        return [str(constraint.get("value"))]

    lo = float(constraint["min"])
    hi = float(constraint["max"])
    if lo == int(lo) and hi == int(hi):
        mid = int((lo + hi) // 2) if (lo + hi) % 2 == 0 else int(round((lo + hi) / 2))
        pool = [mid, int(lo), int(hi)]
        extra = int(lo) + 1 if int(lo) + 1 < int(hi) else None
        if extra is not None and extra not in pool:
            pool.append(extra)
        return [f"{v}{suffix}".strip() for v in pool]

    mid = round((lo + hi) / 2, 2)
    return [f"{mid}{suffix}".strip(), f"{lo}{suffix}".strip(), f"{hi}{suffix}".strip()]


def _violate_pool(constraint: dict[str, Any]) -> list[str]:
    kind = constraint.get("kind")
    unit = str(constraint.get("unit") or "").strip()
    suffix = f" {unit}" if unit else ""

    if kind == "equality":
        base = str(constraint.get("value"))
        try:
            n = float(base)
            below = n - 1 if n == int(n) else round(n * 0.5, 2)
            above = n + 1 if n == int(n) else round(n * 1.5, 2)
            return [str(below), str(above)]
        except ValueError:
            return ["0", "1"]

    lo = float(constraint["min"])
    hi = float(constraint["max"])
    step = 1 if lo == int(lo) and hi == int(hi) else max(0.01, (hi - lo) * 0.01)
    below = lo - step
    above = hi + step
    if lo == int(lo) and hi == int(hi):
        return [f"{int(below)}{suffix}".strip(), f"{int(above)}{suffix}".strip()]
    return [f"{below}{suffix}".strip(), f"{above}{suffix}".strip()]


def _pick(pool: list[str], index: int) -> str:
    if not pool:
        return "0"
    return pool[index % len(pool)]


def compile_constraints_to_patches(
    bundle: dict[str, Any],
    logic_id: str,
    overlay: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build candidate Given patches from accepted structured constraints."""
    constraints = accepted_constraints(overlay)
    if not constraints:
        return []

    satisfy_idx: dict[str, int] = {c["id"]: 0 for c in constraints}
    violate_idx: dict[str, int] = {c["id"]: 0 for c in constraints}
    satisfy_pools = {c["id"]: _satisfy_pool(c) for c in constraints}
    violate_pools = {c["id"]: _violate_pool(c) for c in constraints}

    patches: list[dict[str, Any]] = []
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if not cid:
            continue
        intent = path_coverage_intent(cand)
        given_rows: list[dict[str, Any]] = []
        for constraint in constraints:
            cid_key = constraint["id"]
            if intent == "violate":
                val = _pick(violate_pools[cid_key], violate_idx[cid_key])
                violate_idx[cid_key] += 1
            else:
                val = _pick(satisfy_pools[cid_key], satisfy_idx[cid_key])
                satisfy_idx[cid_key] += 1
            given_rows.append(
                {
                    "signal": constraint["signal"],
                    "value": val,
                    "note": f"constraint_compiler:{intent}",
                }
            )
        patches.append(
            {
                "candidate_id": cid,
                "given": given_rows,
                "note": f"compiled from {len(constraints)} constraint(s); path intent={intent}",
            }
        )
    return patches
