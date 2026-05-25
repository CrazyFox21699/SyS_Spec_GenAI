"""Team username/password auth — SQLite users and session cookies."""

from __future__ import annotations

import re
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt

_DB_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None
_DB_PATH: Path | None = None

SESSION_COOKIE = "alex_session"
_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,31}$")
_VALID_ROLES = frozenset({"engineer", "admin"})


@dataclass(frozen=True)
class TeamUser:
    user_id: int
    username: str
    role: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cfg_team_auth(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("team_auth")
    return raw if isinstance(raw, dict) else {}


def team_auth_enabled(cfg: dict[str, Any] | None = None) -> bool:
    if cfg is None:
        from src.utils.config_path import get_config_path
        from src.utils.yaml_utils import load_yaml

        cfg_path = get_config_path()
        cfg = load_yaml(cfg_path) if cfg_path.exists() else {}
    return bool(_cfg_team_auth(cfg).get("enabled", False))


def session_hours(cfg: dict[str, Any]) -> int:
    return max(1, int(_cfg_team_auth(cfg).get("session_hours", 12)))


def remember_session_hours(cfg: dict[str, Any]) -> int:
    days = max(1, int(_cfg_team_auth(cfg).get("remember_days", 30)))
    return days * 24


def session_remaining_hours(session_id: str) -> float | None:
    if not session_id:
        return None
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE session_id = ?",
            (session_id.strip(),),
        ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    remaining = (expires - datetime.now(timezone.utc)).total_seconds() / 3600.0
    return max(0.0, remaining)


def touch_session(session_id: str, *, hours: int) -> None:
    if not session_id or hours < 1:
        return
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (expires.isoformat(), session_id.strip()),
        )
        conn.commit()


def cookie_secure(cfg: dict[str, Any]) -> bool:
    return bool(_cfg_team_auth(cfg).get("cookie_secure", False))


def init_user_db(data_root: Path) -> None:
    global _CONN, _DB_PATH
    data_root.mkdir(parents=True, exist_ok=True)
    _DB_PATH = data_root / "alex_users.db"
    _CONN = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    _CONN.row_factory = sqlite3.Row
    with _DB_LOCK:
        _CONN.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'engineer',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            """
        )
        _CONN.commit()


def _require_conn() -> sqlite3.Connection:
    if _CONN is None:
        raise RuntimeError("Team auth DB not initialized")
    return _CONN


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def validate_username(username: str) -> str:
    name = str(username or "").strip().lower()
    if not _USERNAME_RE.match(name):
        raise ValueError("Username must be 3–32 chars: lowercase letter first, then letters, digits, _ . -")
    return name


def validate_role(role: str) -> str:
    r = str(role or "engineer").strip().lower()
    if r not in _VALID_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}")
    return r


def create_user(username: str, password: str, *, role: str = "engineer") -> TeamUser:
    name = validate_username(username)
    role = validate_role(role)
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters")
    conn = _require_conn()
    with _DB_LOCK:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (name, _hash_password(password), role, _now_iso()),
        )
        conn.commit()
        user_id = int(cur.lastrowid)
    return TeamUser(user_id=user_id, username=name, role=role)


def get_user_by_username(username: str) -> TeamUser | None:
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE username = ? COLLATE NOCASE AND is_active = 1",
            (validate_username(username),),
        ).fetchone()
    if not row:
        return None
    return TeamUser(user_id=int(row["id"]), username=str(row["username"]), role=str(row["role"]))


def authenticate(username: str, password: str) -> TeamUser | None:
    conn = _require_conn()
    name = validate_username(username)
    with _DB_LOCK:
        row = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ? COLLATE NOCASE AND is_active = 1",
            (name,),
        ).fetchone()
    if not row or not _verify_password(password, str(row["password_hash"])):
        return None
    return TeamUser(user_id=int(row["id"]), username=str(row["username"]), role=str(row["role"]))


def create_session(user_id: int, *, hours: int = 12) -> str:
    session_id = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, expires.isoformat(), _now_iso()),
        )
        conn.commit()
    return session_id


def delete_session(session_id: str) -> None:
    if not session_id:
        return
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()


def get_user_for_session(session_id: str) -> TeamUser | None:
    if not session_id:
        return None
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.role, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.session_id = ? AND u.is_active = 1
            """,
            (session_id.strip(),),
        ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        delete_session(session_id)
        return None
    if expires <= datetime.now(timezone.utc):
        delete_session(session_id)
        return None
    return TeamUser(user_id=int(row["id"]), username=str(row["username"]), role=str(row["role"]))


def change_password(username: str, old_password: str, new_password: str) -> None:
    user = authenticate(username, old_password)
    if not user:
        raise ValueError("Current password is incorrect")
    if len(new_password or "") < 8:
        raise ValueError("New password must be at least 8 characters")
    conn = _require_conn()
    with _DB_LOCK:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_password(new_password), user.user_id),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user.user_id,))
        conn.commit()


def user_public_dict(user: TeamUser) -> dict[str, Any]:
    return {"username": user.username, "role": user.role}


def user_count() -> int:
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return int(row["n"]) if row else 0


def list_users() -> list[dict[str, Any]]:
    conn = _require_conn()
    with _DB_LOCK:
        rows = conn.execute(
            """
            SELECT username, role, is_active, created_at
            FROM users
            ORDER BY username COLLATE NOCASE
            """
        ).fetchall()
    return [
        {
            "username": str(r["username"]),
            "role": str(r["role"]),
            "is_active": bool(r["is_active"]),
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


def admin_set_password(username: str, new_password: str) -> None:
    name = validate_username(username)
    if len(new_password or "") < 8:
        raise ValueError("Password must be at least 8 characters")
    conn = _require_conn()
    with _DB_LOCK:
        row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (name,)).fetchone()
        if not row:
            raise ValueError(f"User `{name}` not found")
        user_id = int(row["id"])
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_password(new_password), user_id),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()


def set_user_active(username: str, *, active: bool) -> None:
    name = validate_username(username)
    conn = _require_conn()
    with _DB_LOCK:
        cur = conn.execute(
            "UPDATE users SET is_active = ? WHERE username = ? COLLATE NOCASE",
            (1 if active else 0, name),
        )
        if cur.rowcount == 0:
            raise ValueError(f"User `{name}` not found")
        if not active:
            row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (name,)).fetchone()
            if row:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (int(row["id"]),))
        conn.commit()
