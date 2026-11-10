"""POST /parse: validate, expand, dispatch, cap, and serialize."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import Response

from .contract import (
    MAX_URL_LENGTH,
    ParseResult,
    finalize_success,
    normalize_items,
)
from . import stage_cache
from .errors import ApiError
from .parsers import douyin, xhs
from .parsers.shortlink import expand_shortlink, is_shortlink
from .session_bridge import CookieExpired, get_cookie

logger = logging.getLogger("renlink.parse")

router = APIRouter()

PARSE_TIMEOUT_S = 12.0
ALLOWED_DOMAINS = (
    "douyin.com",
    "iesdouyin.com",
    "xiaohongshu.com",
    "xhslink.com",
    "xhslink.cn",
)
_DOUYIN_CANONICAL = re.compile(r"^/(?:video|note|gallery|slides)/[0-9]+")
_XHS_CANONICAL = re.compile(r"^/(?:explore|discovery/item)/[^/]+")


def _allowed_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def _platform_for(host: str) -> Optional[str]:
    host = (host or "").lower()
    if host == "douyin.com" or host.endswith(".douyin.com"):
        return "douyin"
    if host == "iesdouyin.com" or host.endswith(".iesdouyin.com"):
        return "douyin"
    if host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com"):
        return "xhs"
    if host == "xhslink.com" or host.endswith(".xhslink.com"):
        return "xhs"
    if host == "xhslink.cn" or host.endswith(".xhslink.cn"):
        return "xhs"
    return None


def _is_canonical(url: str, platform: str) -> bool:
    path = urlparse(url).path or ""
    if platform == "douyin":
        return bool(_DOUYIN_CANONICAL.match(path))
    if platform == "xhs":
        return bool(_XHS_CANONICAL.match(path))
    return False


def _validate_request(body: Any) -> str:
    if not isinstance(body, dict):
        raise ApiError("INVALID_REQUEST", "请求体必须是 JSON 对象")
    # C6: user cookies are forbidden, even as an extra field.
    for key in body:
        if str(key).lower() == "cookie":
            raise ApiError("INVALID_REQUEST", "请求体不得包含 cookie 字段")
    if "url" not in body:
        raise ApiError("INVALID_URL")
    url = body.get("url")
    if not isinstance(url, str):
        raise ApiError("INVALID_REQUEST", "url 字段必须是字符串")
    if not url.strip():
        raise ApiError("INVALID_URL")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ApiError("INVALID_URL", "url 长度超过 2048")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ApiError("INVALID_URL")
    if not parsed.hostname:
        raise ApiError("INVALID_URL")
    if not _allowed_host(parsed.hostname):
        raise ApiError("UNSUPPORTED_PLATFORM")
    return url


async def _parse_pipeline(source_url: str, started: float) -> Response:
    resolved_url = source_url
    if is_shortlink(source_url):
        resolved_url = await expand_shortlink(source_url)
        target = urlparse(resolved_url)
        if not target.hostname or not _allowed_host(target.hostname):
            raise ApiError("UNSUPPORTED_PLATFORM", "短链展开后不在白名单域名内")
        if not _is_canonical(resolved_url, _platform_for((target.hostname or "").lower()) or ""):
            raise ApiError("SHORTLINK_FAIL", "短链没有落到内容规范页")

    host = (urlparse(resolved_url).hostname or "").lower()
    platform = _platform_for(host)
    if platform is None:
        raise ApiError("UNSUPPORTED_PLATFORM")

    try:
        cookie = get_cookie(platform)
    except CookieExpired as exc:
        raise ApiError("COOKIE_EXPIRED") from exc

    delay_ms = 0
    try:
        delay_ms = int(os.getenv("PARSE_UPSTREAM_DELAY_MS", "0") or "0")
    except ValueError:
        delay_ms = 0
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)

    if platform == "douyin":
        parsed = await douyin.parse(resolved_url, cookie)
    else:
        parsed = await xhs.parse(resolved_url, cookie)

    content_type = parsed.get("content_type")
    if content_type not in ("video", "note"):
        raise ApiError("PARSE_FAILED", "解析器没有返回 content_type")
    raw_items = parsed.get("items") or []
    items, truncated = normalize_items(raw_items, platform, content_type)
    if not items:
        raise ApiError("PARSE_FAILED", "解析结果没有可用的媒体地址")
    if truncated and len(items) > 100:
        items = items[:100]

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = ParseResult(
        ok=True,
        platform=platform,
        content_type=content_type,
        source_url=source_url,
        resolved_url=resolved_url,
        title=str(parsed.get("title") or ""),
        item_count=len(items),
        elapsed_ms=elapsed_ms,
        items=items,
    )
    data, payload = finalize_success(result)
    if truncated:
        payload["truncated"] = True
        payload["item_count"] = len(payload["items"])
    task_id = stage_cache.remember(payload)
    payload["task_id"] = task_id
    from .contract import encode_payload

    data = encode_payload(payload)
    logger.info(
        "parse ok platform=%s content_type=%s items=%s elapsed_ms=%s host=%s",
        platform,
        content_type,
        payload["item_count"],
        elapsed_ms,
        host,
    )
    return Response(content=data, media_type="application/json")


@router.post("/parse")
async def parse_url(request: Request) -> Response:
    started = getattr(request.state, "started", time.perf_counter())
    try:
        body = await request.json()
    except Exception as exc:
        raise ApiError("INVALID_REQUEST", "请求体不是合法 JSON") from exc
    source_url = _validate_request(body)
    try:
        return await asyncio.wait_for(_parse_pipeline(source_url, started), timeout=PARSE_TIMEOUT_S)
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise ApiError("TIMEOUT") from exc
