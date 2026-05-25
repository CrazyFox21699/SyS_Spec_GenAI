"""API security: token auth, team session auth, rate limits, upload caps."""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from contextvars import ContextVar
from typing import Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)

_current_user: ContextVar[object | None] = ContextVar("alex_team_user", default=None)
_current_request: ContextVar[Request | None] = ContextVar("alex_request", default=None)

_PUBLIC_API_PREFIXES = (
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/logout",
)


def sanitize_resource_id(value: str, *, field: str = "id") -> str:
    v = str(value or "").strip()
    if not v or not _SAFE_ID_RE.match(v) or ".." in v:
        raise HTTPException(400, f"Invalid {field}")
    return v


def verify_api_token(request: Request, *, required: bool = False) -> None:
    token = os.environ.get("ALEX_API_TOKEN", "").strip()
    if not token:
        if required:
            raise HTTPException(401, "ALEX_API_TOKEN not configured on server")
        return
    header = request.headers.get("X-ALEX-Token") or request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        header = header[7:].strip()
    if header != token:
        raise HTTPException(401, "Invalid API token")


def check_rate_limit(client_key: str, *, max_per_minute: int = 120) -> None:
    now = time.time()
    window = _RATE_BUCKETS[client_key]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= max_per_minute:
        raise HTTPException(429, "Rate limit exceeded")
    window.append(now)


def get_current_user():
    """Return logged-in TeamUser when team auth is active; else None."""
    return _current_user.get()


def get_current_request() -> Request | None:
    return _current_request.get()


def parse_if_match_version(request: Request | None = None) -> int | None:
    req = request or get_current_request()
    if not req:
        return None
    raw = req.headers.get("if-match") or req.headers.get("If-Match")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip().strip('"'))
    except ValueError as exc:
        raise HTTPException(400, "Invalid If-Match header") from exc


def require_user():
    """FastAPI dependency — 401 when team auth enabled and no session."""
    from web.team_auth import TeamUser, team_auth_enabled

    user = get_current_user()
    if team_auth_enabled() and not isinstance(user, TeamUser):
        raise HTTPException(401, "Not authenticated")
    return user


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        require_token: bool = False,
        max_upload_mb: int = 50,
        rate_limit_per_minute: int = 120,
    ):
        super().__init__(app)
        self.require_token = require_token
        self.max_upload_bytes = max_upload_mb * 1024 * 1024
        self.rate_limit_per_minute = rate_limit_per_minute

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path.startswith("/api/"):
            verify_api_token(request, required=self.require_token)
            client = request.client.host if request.client else "unknown"
            check_rate_limit(client, max_per_minute=self.rate_limit_per_minute)
            cl = request.headers.get("content-length")
            if cl and int(cl) > self.max_upload_bytes:
                raise HTTPException(413, f"Upload exceeds {self.max_upload_bytes // (1024*1024)} MB limit")
        return await call_next(request)


class TeamAuthMiddleware(BaseHTTPMiddleware):
    """Session cookie auth for multi-user team server."""

    def __init__(self, app, *, cfg: dict | None = None):
        super().__init__(app)
        self._cfg = cfg

    def _cfg_loaded(self) -> dict:
        if self._cfg is not None:
            return self._cfg
        from src.utils.config_path import get_config_path
        from src.utils.yaml_utils import load_yaml

        cfg_path = get_config_path()
        try:
            return load_yaml(cfg_path)
        except OSError:
            return {}

    async def dispatch(self, request: Request, call_next: Callable):
        from web.team_auth import SESSION_COOKIE, get_user_for_session, team_auth_enabled

        cfg = self._cfg_loaded()
        user_token = _current_user.set(None)
        req_token = _current_request.set(request)
        try:
            if team_auth_enabled(cfg):
                session_id = request.cookies.get(SESSION_COOKIE, "")
                user = get_user_for_session(session_id) if session_id else None
                _current_user.set(user)

                path = request.url.path
                if path.startswith("/api/"):
                    if any(path == p or path.startswith(f"{p}/") for p in _PUBLIC_API_PREFIXES):
                        pass
                    elif user is None:
                        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            response = await call_next(request)
            return response
        finally:
            _current_user.reset(user_token)
            _current_request.reset(req_token)
