"""Persist per-logic reasoning sessions for AI-assisted review."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from web.m365_brief import build_copilot_brief
from web.reasoning_guardrails import validate_reasoning_hypothesis


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_logic_id(logic_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(logic_id or "logic"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def session_path(output_dir: Path, logic_id: str) -> Path:
    return output_dir / "reasoning" / _safe_logic_id(logic_id) / "session.json"


def load_session(output_dir: Path, logic_id: str) -> dict[str, Any]:
    path = session_path(output_dir, logic_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_session(output_dir: Path, logic_id: str, session: dict[str, Any]) -> dict[str, Any]:
    path = session_path(output_dir, logic_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    return session


def create_session(
    output_dir: Path,
    bundle: dict[str, Any],
    *,
    logic_id: str,
    engineer_note: str = "",
    provider: str = "auto",
) -> dict[str, Any]:
    brief = build_copilot_brief(bundle, logic_id, engineer_note)
    existing = load_session(output_dir, logic_id)
    session = {
        "logic_id": logic_id,
        "provider": provider,
        "status": existing.get("status") or "open",
        "created_at": existing.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
        "engineer_note": engineer_note,
        "brief_hash": _hash_text(brief),
        "evidence_hash": _hash_text(
            json.dumps(
                {
                    "logic_blocks": bundle.get("logic_blocks") or [],
                    "logic_review_items": [
                        row
                        for row in bundle.get("logic_review_items") or []
                        if str(row.get("logic_id") or "") == logic_id
                    ],
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
        ),
        "turns": existing.get("turns") or [],
        "open_questions": existing.get("open_questions") or [],
        "hypotheses": existing.get("hypotheses") or [],
    }
    return save_session(output_dir, logic_id, session)


def append_turn(
    output_dir: Path,
    *,
    logic_id: str,
    role: str,
    content: str,
    provider: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = load_session(output_dir, logic_id)
    if not session:
        session = {
            "logic_id": logic_id,
            "provider": provider or "auto",
            "status": "open",
            "created_at": _now_iso(),
            "turns": [],
            "open_questions": [],
            "hypotheses": [],
        }
    turn = {
        "role": role,
        "content": content,
        "provider": provider or session.get("provider") or "auto",
        "created_at": _now_iso(),
        "metadata": metadata or {},
    }
    session.setdefault("turns", []).append(turn)
    session["updated_at"] = _now_iso()
    return save_session(output_dir, logic_id, session)


def append_hypothesis(
    output_dir: Path,
    *,
    logic_id: str,
    hypothesis: dict[str, Any],
    provider: str = "auto",
) -> dict[str, Any]:
    session = load_session(output_dir, logic_id)
    if not session:
        session = {
            "logic_id": logic_id,
            "provider": provider,
            "status": "open",
            "created_at": _now_iso(),
            "turns": [],
            "open_questions": [],
            "hypotheses": [],
        }
    validation = validate_reasoning_hypothesis(hypothesis, logic_id=logic_id)
    row = {
        "provider": provider or session.get("provider") or "auto",
        "created_at": _now_iso(),
        "hypothesis": hypothesis,
        "validation": validation,
        "review_required": True,
    }
    session.setdefault("hypotheses", []).append(row)
    if not validation.get("ok"):
        session.setdefault("open_questions", []).extend(
            {"question": err, "reason": "guardrail_validation", "citations": []}
            for err in validation.get("errors") or []
        )
    session["updated_at"] = _now_iso()
    return save_session(output_dir, logic_id, session)
