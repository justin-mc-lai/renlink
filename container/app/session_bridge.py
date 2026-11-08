"""l4-session-egress seam.

This round is a stub: the cookie pool is read from environment variables.
Replace `get_cookie` / `cookie_status` with the frozen l4 client once l4 ships.
Cookie values are never logged or returned to callers.
"""

from __future__ import annotations

import os
from typing import Optional

PLATFORMS = ("douyin", "xhs")


class CookieExpired(Exception):
    """Raised by the l4 seam when the operator cookie is stale."""


def _env_name(platform: str, suffix: str) -> str:
    return f"{platform.upper()}_{suffix}"


def _stub_expired(platform: str) -> bool:
    raw = os.getenv("PARSE_STUB_COOKIE_EXPIRED", "").strip().lower()
    values = {token.strip() for token in raw.replace(";", ",").split(",") if token.strip()}
    if values & {"1", "true", "all", "*"}:
        return True
    if platform in values:
        return True
    return os.getenv(f"PARSE_STUB_{platform.upper()}_COOKIE_EXPIRED", "") == "1"


def get_cookie(platform: str) -> str:
    """Return the operator cookie header for a platform (l4 seam)."""
    if platform not in PLATFORMS:
        return ""
    if _stub_expired(platform):
        raise CookieExpired(f"{platform} cookie expired (stub)")
    cookie = os.getenv(_env_name(platform, "COOKIE"), "").strip()
    if not cookie:
        # The operator pool is the only source; a missing cookie is unusable.
        raise CookieExpired(f"{platform} cookie missing (stub)")
    return cookie


def cookie_status(platform: str) -> str:
    """Return fresh / expired / missing without exposing the cookie value."""
    if platform not in PLATFORMS:
        return "unknown"
    if _stub_expired(platform):
        return "expired"
    return "fresh" if os.getenv(_env_name(platform, "COOKIE"), "").strip() else "missing"


def last_refresh(platform: str) -> str:
    return os.getenv(_env_name(platform, "COOKIE_LAST_REFRESH"), "")


def redact(value: Optional[str]) -> str:
    """Log-safe representation. Never reveal more than a short prefix."""
    if not value:
        return ""
    return f"{value[:4]}***" if len(value) > 4 else "***"
