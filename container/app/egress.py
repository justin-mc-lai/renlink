"""Single egress switch for every outbound parse/download client.

``EGRESS_PROXY`` empty (or ``direct``) means direct. A non-empty value is
injected into curl_cffi, f2, yt-dlp and httpx. ``/health`` only exposes the
mode, never the proxy string.
"""

from __future__ import annotations

import os
from typing import Dict, Optional


def proxy() -> Optional[str]:
    value = os.getenv("EGRESS_PROXY", "").strip()
    if not value or value.lower() == "direct":
        return None
    return value


def mode() -> str:
    return "direct" if proxy() is None else "proxy"


def curl_cffi_proxies() -> Optional[Dict[str, str]]:
    value = proxy()
    return {"http": value, "https": value} if value else None


def f2_proxies() -> Optional[Dict[str, str]]:
    """f2's Douyin crawler reads ``proxies['http://']``; keep both spellings."""
    value = proxy()
    if not value:
        return None
    return {"http://": value, "https://": value, "http": value, "https": value}


def ytdlp_options() -> Dict[str, str]:
    value = proxy()
    return {"proxy": value} if value else {}


def httpx_proxy() -> Optional[str]:
    return proxy()
