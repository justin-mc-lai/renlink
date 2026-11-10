"""Shortlink expansion: at most 3 hops, HEAD first, GET headers fallback."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from ..egress import httpx_proxy
from ..errors import ApiError

MAX_HOPS = 3
SHORTLINK_HOSTS = ("v.douyin.com", "xhslink.com", "xhslink.cn")
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def is_shortlink(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in SHORTLINK_HOSTS)


def _next_hop(response: httpx.Response, current: str) -> Optional[str]:
    location = response.headers.get("location")
    if not location:
        return None
    return urljoin(current, location.strip())


async def expand_shortlink(url: str, timeout_s: float = 3.0) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
    current = url
    try:
        async with httpx.AsyncClient(
            proxy=httpx_proxy(),
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_s),
        ) as client:
            for _ in range(MAX_HOPS):
                if not is_shortlink(current):
                    return _normalize_resolved(current)
                # GET-only: v.douyin.com answers HEAD with 404 and only
                # redirects on GET (verified 2026-11-08). Body is never read.
                nxt = await _get_location(client, current, headers)
                if not nxt:
                    raise ApiError("SHORTLINK_FAIL")
                current = nxt
            if is_shortlink(current):
                raise ApiError("SHORTLINK_FAIL")
            return _normalize_resolved(current)
    except ApiError:
        raise
    except httpx.HTTPError as exc:
        raise ApiError("SHORTLINK_FAIL", f"短链展开失败: {type(exc).__name__}") from exc


def _normalize_resolved(url: str) -> str:
    """Map the share host onto the canonical content URL.

    v.douyin.com 302s to www.iesdouyin.com/share/video/<id>; the parser and
    the canonical-path check expect www.douyin.com/<kind>/<id>.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host == "iesdouyin.com" or host.endswith(".iesdouyin.com"):
        seg = (parsed.path or "").strip("/").split("/")
        if len(seg) >= 3 and seg[0] == "share" and seg[1] in {
            "video",
            "note",
            "slides",
            "gallery",
        } and seg[2].isdigit():
            return f"https://www.douyin.com/{seg[1]}/{seg[2]}"
    return url


async def _get_location(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
) -> Optional[str]:
    """Read only the response headers; the body is never consumed."""
    try:
        async with client.stream("GET", url, headers=headers) as response:
            return _next_hop(response, url)
    except httpx.HTTPError:
        return None
