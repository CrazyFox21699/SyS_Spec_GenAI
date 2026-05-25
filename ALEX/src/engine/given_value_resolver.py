"""Role-aware concrete Given values — boolean guards stay discrete; analog signals may use boundaries."""

from __future__ import annotations

import re
from typing import Any

_UNIT_RE = re.compile(r"\b(km/h|kph|m/s|rpm|%|ms|s)\b", re.I)
_RANGE_RE = re.compile(r"range\s+inclusive\s+(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)", re.I)
_EXCLUSIVE_RANGE_RE = re.compile(r"range\s+exclusive\s+(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)", re.I)
_COMPARISON_RE = re.compile(
    r"^(.+?)\s*(>=|<=|!=|==|=|>|<)\s*(.+)$",
    re.I,
)
_DISCRETE_PREFIXES = ("OK_", "NOK_", "CND_", "REQ_", "RESET_", "FORCE_", "EN_", "IGN_", "MODE_")


def is_discrete_guard_signal(signal: str, definition: str = "") -> bool:
    """Boolean / flag-like guards must not get analog boundary values (e.g. 1.01)."""
    upper = str(signal or "").strip().upper()
    defn = str(definition or "")
    if _UNIT_RE.search(defn) or _RANGE_RE.search(defn) or _EXCLUSIVE_RANGE_RE.search(defn):
        return False
    if re.search(r"[<>]=?\s*\d", defn) and not upper.startswith(("OK_", "NOK_")):
        return False
    if any(upper.startswith(p) for p in _DISCRETE_PREFIXES):
        return True
    return bool(re.fullmatch(r"(TRUE|FALSE|ON|OFF|0|1)", defn.strip(), re.I))


def normalize_discrete_value(
    value: str,
    *,
    negated: bool = False,
    path_intent: str = "satisfy",
) -> str:
    raw = str(value or "").strip()
    upper = raw.upper()
    if upper in ("TRUE", "ON"):
        base = "1"
    elif upper in ("FALSE", "OFF"):
        base = "0"
    elif upper in ("0", "1"):
        base = upper
    else:
        base = raw or "1"

    violate = path_intent == "violate" or negated
    if violate:
        return "0" if base == "1" else "1"
    return base


def definition_to_concrete_value(
    signal: str,
    definition: str,
    *,
    negated: bool = False,
    path_intent: str = "satisfy",
) -> str | None:
    """Turn engineer/spec definition text into one concrete test value."""
    defn = str(definition or "").strip()
    if not defn:
        return None
    if defn.startswith("="):
        defn = defn.lstrip("= ").strip()

    sig = str(signal or "").strip().upper()
    violate = path_intent == "violate" or negated

    if is_discrete_guard_signal(sig, defn):
        others = {
            m.group(1).upper()
            for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", defn)
        }
        if others - {sig}:
            return None
        m = re.search(r"(?:==|(?<![<>!=])=)\s*(TRUE|FALSE|ON|OFF|0|1)", defn, re.I)
        if m:
            return normalize_discrete_value(m.group(1), path_intent=path_intent, negated=negated)
        if re.fullmatch(r"(TRUE|FALSE|ON|OFF|0|1)", defn, re.I):
            return normalize_discrete_value(defn, path_intent=path_intent, negated=negated)
        if re.search(r"\b(active|true|enabled|on)\b", defn, re.I):
            return normalize_discrete_value("1", path_intent=path_intent, negated=negated)
        if re.search(r"\b(inactive|false|disabled|off)\b", defn, re.I):
            return normalize_discrete_value("0", path_intent=path_intent, negated=negated)
        if sig.startswith("OK_"):
            return "0" if violate else "1"
        if sig.startswith("NOK_"):
            return "1" if violate else "0"
        return "0" if violate else "1"

    rm = _RANGE_RE.search(defn)
    if rm:
        lo = float(rm.group(1))
        hi = float(rm.group(2))
        if violate:
            return str(int(lo - 1) if lo == int(lo) else round(lo - 0.01, 2))
        mid = int((lo + hi) // 2) if lo == int(lo) and hi == int(hi) else round((lo + hi) / 2, 2)
        return str(int(mid) if mid == int(mid) else mid)

    ex = _EXCLUSIVE_RANGE_RE.search(defn)
    if ex:
        lo = float(ex.group(1))
        hi = float(ex.group(2))
        if violate:
            return str(int(lo) if lo == int(lo) else lo)
        inner_lo = lo + 1 if lo == int(lo) else lo + 0.01
        inner_hi = hi - 1 if hi == int(hi) else hi - 0.01
        mid = (inner_lo + inner_hi) / 2
        return str(int(mid) if mid == int(mid) else round(mid, 2))

    cm = _COMPARISON_RE.match(defn)
    if cm:
        lhs = cm.group(1).strip().upper()
        if lhs != sig:
            return None
        op = cm.group(2).strip()
        if op == "=":
            op = "=="
        rhs = cm.group(3).strip()
        if op in (">", ">=", "<", "<=", "!="):
            from src.engine.concrete_test_values import infer_boundary_value

            if violate:
                return infer_boundary_value(op, rhs)
            num = re.search(r"[-+]?\d*\.?\d+", rhs.replace(",", ""))
            return num.group() if num else rhs.split()[0]
        return rhs.split()[0]

    bare = re.match(r"^(>=|<=|!=|==|=|>|<)\s*(.+)$", defn)
    if bare and not is_discrete_guard_signal(sig, defn):
        op = bare.group(1).strip()
        if op == "=":
            op = "=="
        rhs = bare.group(2).strip()
        from src.engine.concrete_test_values import infer_boundary_value

        if violate and op in (">", ">=", "<", "<=", "!="):
            return infer_boundary_value(op, rhs)
        num = re.search(r"[-+]?\d*\.?\d+", rhs.replace(",", ""))
        return num.group() if num else rhs.split()[0]

    if re.match(r"^[-+]?\d", defn):
        return defn.split()[0]
    return None


def sanitize_given_item(item: dict[str, Any], *, path_intent: str = "satisfy") -> dict[str, Any]:
    """Normalize a structured Given row before materialization."""
    if not isinstance(item, dict) or not item.get("signal"):
        return item
    sig = str(item["signal"]).strip()
    op = str(item.get("operator") or "==").strip()
    negated = bool(item.get("negated"))
    val = item.get("value")

    if is_discrete_guard_signal(sig):
        concrete = normalize_discrete_value(str(val or "1"), negated=negated, path_intent=path_intent)
        return {**item, "value": concrete, "operator": "==", "negated": False}

    if op in (">", ">=", "<", "<=") and val is not None:
        from src.engine.concrete_test_values import infer_boundary_value

        if path_intent == "violate" or negated:
            rendered = infer_boundary_value(op, str(val))
        else:
            rendered = str(val).strip()
        return {**item, "value": rendered, "operator": "==", "negated": False}
    return item
