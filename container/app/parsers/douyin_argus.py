"""Douyin main branch: signed HTTP detail call with Argus headers.

The server-side 403 is ``Blocked by ArgusSecurityPlugin``. The gateway needs a
matched set of header and query values:

* headers: ``x-tt-argus`` (any non-empty value) and ``uifid``
* query: ``uifid``, ``verifyFp=<s_v_web_id>``, ``fp=<s_v_web_id>``
* a fresh ``a_bogus`` over the whole parameter string

``curl_cffi(impersonate="chrome")`` with that set returns the detail JSON and
its ``play_addr``. ``webid`` must be omitted: f2's freshly generated webid is
rejected with an empty 200, while omitting it returns the normal payload.
This module only reads that address; it never downloads media.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from ..egress import curl_cffi_proxies

logger = logging.getLogger("renlink.douyin.argus")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
DEFAULT_TTL_S = 600.0
DEFAULT_TIMEOUT_S = 6.0

# Parameter order matters: a_bogus is computed over this exact string.
_COMMON_PARAMS: Tuple[Tuple[str, str], ...] = (
    ("device_platform", "webapp"),
    ("aid", "6383"),
    ("channel", "channel_pc_web"),
    ("request_source", "600"),
    ("origin_type", "video_page"),
    ("update_version_code", "170400"),
    ("pc_client_type", "1"),
    ("pc_libra_divert", "Mac"),
    ("support_h265", "0"),
    ("support_dash", "0"),
    ("cpu_core_num", "10"),
    ("version_code", "190500"),
    ("version_name", "19.5.0"),
    ("cookie_enabled", "true"),
    ("screen_width", "1280"),
    ("screen_height", "720"),
    ("browser_language", "zh-CN"),
    ("browser_platform", "MacIntel"),
    ("browser_name", "Chrome"),
    ("browser_version", "149.0.0.0"),
    ("browser_online", "true"),
    ("engine_name", "Blink"),
    ("engine_version", "149.0.0.0"),
    ("os_name", "Mac OS"),
    ("os_version", "10.15.7"),
    ("device_memory", "32"),
    ("platform", "PC"),
    ("downlink", "9.6"),
    ("effective_type", "4g"),
    ("round_trip_time", "0"),
)

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()
_stats = {
    "argus_requests": 0,
    "cache_hits": 0,
    "argus_failures": 0,
    "dropped_argus_header": 0,
}


class ArgusUnavailable(Exception):
    """The signed HTTP call did not yield a play_addr."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or str(default))
    except ValueError:
        return default


def cache_ttl_s() -> float:
    return _env_float("RENLINK_PLAY_ADDR_TTL_S", DEFAULT_TTL_S)


def stats() -> Dict[str, Any]:
    with _cache_lock:
        size = len(_cache)
    return {**_stats, "cache_entries": size, "cache_ttl_s": int(cache_ttl_s())}


def cache_get(aweme_id: str) -> Optional[Dict[str, Any]]:
    if os.getenv("RENLINK_DISABLE_CACHE", "").strip() == "1":
        return None
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(aweme_id)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _cache.pop(aweme_id, None)
            return None
        return dict(value)


def cache_put(aweme_id: str, value: Dict[str, Any]) -> None:
    if os.getenv("RENLINK_DISABLE_CACHE", "").strip() == "1":
        return
    with _cache_lock:
        _cache[aweme_id] = (time.monotonic() + cache_ttl_s(), dict(value))


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def parse_cookie(cookie: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def fetch_play_addr(aweme_id: str, cookie: str) -> Dict[str, Any]:
    """Return ``{play_addr, title, cover, width, height}`` for one aweme."""
    cached = cache_get(aweme_id)
    if cached is not None:
        _stats["cache_hits"] += 1
        logger.info("argus cache hit aweme_id=%s", aweme_id)
        return cached

    cookie_map = parse_cookie(cookie)
    uifid = cookie_map.get("UIFID") or cookie_map.get("UIFID_TEMP") or ""
    verify = cookie_map.get("s_v_web_id") or ""
    if not uifid or not verify:
        raise ArgusUnavailable("cookie missing UIFID or s_v_web_id")

    started = time.monotonic()
    try:
        payload = _request_detail(aweme_id, cookie_map, uifid, verify)
    except ArgusUnavailable:
        _stats["argus_failures"] += 1
        raise
    except Exception as exc:  # network / signing failure
        _stats["argus_failures"] += 1
        logger.warning("argus error aweme_id=%s type=%s", aweme_id, type(exc).__name__)
        raise ArgusUnavailable(f"argus error: {type(exc).__name__}") from exc

    data = _payload_from_detail(payload)
    if not data:
        _stats["argus_failures"] += 1
        raise ArgusUnavailable("detail returned no play_addr")
    cache_put(aweme_id, data)
    logger.info(
        "argus ok aweme_id=%s elapsed_ms=%s",
        aweme_id,
        int((time.monotonic() - started) * 1000),
    )
    return data


def _request_detail(
    aweme_id: str,
    cookie_map: Dict[str, str],
    uifid: str,
    verify: str,
) -> Dict[str, Any]:
    _ensure_f2_logger()
    from f2.apps.douyin.api import DouyinAPIEndpoints
    from f2.apps.douyin.utils import ABogusManager
    from curl_cffi import requests as cffi_requests

    user_agent = os.getenv("RENLINK_DOUYIN_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    params: "OrderedDict[str, str]" = OrderedDict(_COMMON_PARAMS)
    params["aweme_id"] = aweme_id
    params["uifid"] = uifid
    endpoint = ABogusManager.model_2_endpoint(
        user_agent, DouyinAPIEndpoints.POST_DETAIL, dict(params)
    )
    endpoint += (
        f"&verifyFp={quote(verify, safe='')}&fp={quote(verify, safe='')}"
        f"&timestamp={int(time.time())}"
    )

    headers = {
        "User-Agent": user_agent,
        "Referer": f"https://www.douyin.com/video/{aweme_id}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"',
        "sec-ch-ua-platform": '"macOS"',
        "sec-ch-ua-mobile": "?0",
        "uifid": uifid,
    }
    if os.getenv("RENLINK_DROP_ARGUS_HEADER", "").strip() == "1":
        _stats["dropped_argus_header"] += 1
        logger.warning("x-tt-argus dropped by RENLINK_DROP_ARGUS_HEADER aweme_id=%s", aweme_id)
    else:
        headers["x-tt-argus"] = "1"

    _stats["argus_requests"] += 1
    response = cffi_requests.get(
        endpoint,
        headers=headers,
        cookies=cookie_map,
        impersonate="chrome",
        proxies=curl_cffi_proxies(),
        timeout=_env_float("RENLINK_ARGUS_TIMEOUT_S", DEFAULT_TIMEOUT_S),
    )
    body = response.content or b""
    if response.status_code != 200:
        raise ArgusUnavailable(
            f"upstream HTTP {response.status_code}: {body[:80].decode('utf-8', 'replace')}"
        )
    if not body:
        raise ArgusUnavailable("upstream returned an empty 200")
    try:
        payload = response.json()
    except Exception as exc:
        raise ArgusUnavailable("upstream returned non-JSON") from exc
    if not isinstance(payload, dict) or not payload.get("aweme_detail"):
        status_code = payload.get("status_code") if isinstance(payload, dict) else None
        raise ArgusUnavailable(f"upstream status_code={status_code}")
    return payload


def _payload_from_detail(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    detail = payload.get("aweme_detail") or {}
    video = detail.get("video") or {}
    addr = video.get("play_addr") or {}
    urls = addr.get("url_list") or []
    play_addr = next(
        (str(url) for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))),
        "",
    )
    if not play_addr:
        return None
    cover_urls = (video.get("cover") or {}).get("url_list") or []
    cover = next(
        (str(url) for url in cover_urls if isinstance(url, str) and url.startswith(("http://", "https://"))),
        "",
    )
    return {
        "play_addr": play_addr,
        "title": str(detail.get("desc") or ""),
        "cover": cover,
        "width": _as_int(video.get("width")),
        "height": _as_int(video.get("height")),
    }


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _ensure_f2_logger() -> None:
    """f2 sets up ./logs on import; a NullHandler keeps it quiet."""
    logger_f2 = logging.getLogger("f2")
    if not logger_f2.handlers:
        logger_f2.addHandler(logging.NullHandler())
