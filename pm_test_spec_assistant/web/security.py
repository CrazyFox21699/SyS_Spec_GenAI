"""API security: token auth, rate limits, upload caps."""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)


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
