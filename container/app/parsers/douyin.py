"""Douyin branch: Argus HTTP for video, f2 for notes. Never a browser.

Douyin must not import ``render`` (Obscura); TC-024 enforces that boundary.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..contract import ext_from_url
from ..egress import f2_proxies, ytdlp_options
from ..errors import ApiError
from ..session_bridge import CookieExpired, get_cookie
from . import douyin_argus

_AWEME_ID = re.compile(r"(?:video|note|gallery|slides)/([0-9]{5,})")


class _QuietLogger:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def detect_content_type(url: str) -> str:
    path = (urlparse(url).path or "").lower()
    if any(part in path for part in ("/note/", "/gallery/", "/slides/")):
        return "note"
    return "video"


def extract_aweme_id(url: str) -> str:
    match = _AWEME_ID.search(urlparse(url).path or "") or _AWEME_ID.search(url)
    if not match:
        raise ApiError("PARSE_FAILED", "抖音链接里找不到 aweme_id")
    return match.group(1)


async def parse(url: str, cookie: Optional[str] = None) -> Dict[str, Any]:
    if cookie is None:
        try:
            cookie = get_cookie("douyin")
        except CookieExpired as exc:
            raise ApiError("COOKIE_EXPIRED") from exc
    content_type = detect_content_type(url)
    if content_type == "note":
        # Notes stay on f2's DouyinHandler; no browser is started here.
        return await asyncio.to_thread(_parse_sync, url, cookie, content_type)
    aweme_id = extract_aweme_id(url)
    try:
        signed = await asyncio.to_thread(douyin_argus.fetch_play_addr, aweme_id, cookie)
    except douyin_argus.ArgusUnavailable as exc:
        # C9/C10: Douyin never falls back to a browser or Obscura.
        raise ApiError("PARSE_FAILED", f"抖音 Argus 直连失败: {exc}") from exc
    return _rendered_payload(signed, content_type)


def _rendered_payload(rendered: Dict[str, Any], content_type: str) -> Dict[str, Any]:
    """Only the resolved play_addr travels on; media is never fetched."""
    return {
        "content_type": content_type,
        "title": str(rendered.get("title") or ""),
        "items": [
            {
                "type": "video",
                "remoteUrl": str(rendered["play_addr"]),
                "ext": "mp4",
                "cover": str(rendered.get("cover") or ""),
                "width": rendered.get("width"),
                "height": rendered.get("height"),
                "needs_transcode": False,
            }
        ],
    }


def _parse_sync(url: str, cookie: str, content_type: str) -> Dict[str, Any]:
    if content_type == "note":
        return _f2_result(url, cookie, content_type)
    info = _ytdlp_info(url, cookie)
    if info:
        video_url = _info_video_url(info)
        if video_url:
            return _video_payload(video_url, info, content_type)
    return _f2_result(url, cookie, content_type)


def _ytdlp_info(url: str, cookie: str) -> Optional[Dict[str, Any]]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise ApiError("PARSE_FAILED", "运行环境缺少 yt-dlp") from exc
    options: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "logger": _QuietLogger(),
    }
    options.update(ytdlp_options())
    if cookie:
        options["http_headers"] = {"Cookie": cookie}
    try:
        with YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _info_video_url(info: Dict[str, Any]) -> str:
    direct = info.get("url")
    if isinstance(direct, str) and direct.startswith(("http://", "https://")):
        return direct
    formats = [f for f in info.get("formats") or [] if isinstance(f, dict)]
    formats = [f for f in formats if f.get("url") and f.get("vcodec") != "none"]
    if not formats:
        return ""
    formats.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0), reverse=True)
    return str(formats[0]["url"])


def _video_payload(
    video_url: str,
    info: Dict[str, Any],
    content_type: str,
) -> Dict[str, Any]:
    return {
        "content_type": content_type,
        "title": str(info.get("title") or info.get("description") or ""),
        "items": [
            {
                "type": "video",
                "remoteUrl": video_url,
                "ext": "mp4",
                "cover": str(info.get("thumbnail") or ""),
                "width": _as_int(info.get("width")),
                "height": _as_int(info.get("height")),
                "needs_transcode": False,
            }
        ],
    }


def _f2_result(url: str, cookie: str, content_type: str) -> Dict[str, Any]:
    """Use f2 as a library. Only fetch_one_video is called; no download."""
    _ensure_f2_logger()
    try:
        from f2.apps.douyin.handler import DouyinHandler
    except ImportError as exc:
        raise ApiError("PARSE_FAILED", "运行环境缺少 f2") from exc
    aweme_id = extract_aweme_id(url)
    # f2 0.0.1.7 requires both keys even when headers is empty.
    kwargs = {"cookie": cookie or "", "headers": {}}
    proxies = f2_proxies()
    if proxies:
        kwargs["proxies"] = proxies
    try:
        handler = DouyinHandler(kwargs)
    except TypeError as exc:
        raise ApiError("PARSE_FAILED", "f2 DouyinHandler 初始化失败") from exc
    try:
        detail = asyncio.run(handler.fetch_one_video(aweme_id))
    except Exception as exc:
        raise ApiError("PARSE_FAILED", f"f2 解析失败: {type(exc).__name__}") from exc
    data = _detail_mapping(detail)
    note = _note_payload(data)
    if note:
        return note
    video_url = _video_url_from_detail(data)
    if video_url:
        return _video_payload(
            video_url,
            {"title": str(data.get("desc") or data.get("title") or ""),
             "width": data.get("width"), "height": data.get("height")},
            content_type,
        )
    raise ApiError("PARSE_FAILED", "f2 返回里没有媒体字段")


def _note_payload(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One item per image, matching f2's images[*].url_list[0] semantics."""
    images = _primary_image_urls(
        data.get("images") or data.get("image_list") or data.get("image_urls")
    )
    if not images:
        return None
    title = str(data.get("desc") or data.get("title") or "")
    cover = _first_url(data.get("cover") or data.get("origin_cover"))
    if not cover:
        video = _as_mapping(data.get("video") or {})
        cover = _first_url(video.get("cover") or video.get("origin_cover"))
    video = _as_mapping(data.get("video") or {})
    width = _as_int(data.get("width") or video.get("width"))
    height = _as_int(data.get("height") or video.get("height"))
    return {
        "content_type": "note",
        "title": title,
        "items": [
            {
                "type": "image",
                "remoteUrl": href,
                "ext": ext_from_url(href),
                "cover": cover,
                "width": width,
                "height": height,
                "needs_transcode": False,
            }
            for href in images
        ],
    }


def _ensure_f2_logger() -> None:
    """f2 writes ./logs on import. A NullHandler makes log_setup skip it."""
    logger = logging.getLogger("f2")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())


def _as_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    for attr in ("model_dump", "dict", "to_dict", "_to_raw", "_to_dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                result = method()
                if isinstance(result, dict):
                    return result
            except TypeError:
                continue
    try:
        return {key: val for key, val in vars(value).items() if not key.startswith("_")}
    except TypeError:
        return {}


def _detail_mapping(value: Any) -> Dict[str, Any]:
    """Unwrap f2's PostDetailFilter into the aweme_detail dict."""
    raw_method = getattr(value, "_to_raw", None)
    if callable(raw_method):
        try:
            raw = raw_method()
        except Exception:
            raw = None
        if isinstance(raw, dict):
            detail = raw.get("aweme_detail")
            return detail if isinstance(detail, dict) else raw
    return _as_mapping(value)


def _first_url(value: Any) -> str:
    urls = _image_urls(value)
    return urls[0] if urls else ""


def _primary_image_urls(value: Any) -> List[str]:
    """One URL per image entry, mirroring f2's images[*].url_list[0].

    A dict with url_list contributes exactly its first usable http(s) entry;
    sibling CDN mirrors must not become extra items. Plain string entries are
    taken as-is. Duplicates across different images are dropped.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.startswith(("http://", "https://")) else []
    if isinstance(value, (list, tuple, set)):
        found: List[str] = []
        for entry in value:
            found.extend(_primary_image_urls(entry))
        seen = set()
        unique: List[str] = []
        for href in found:
            if href not in seen:
                seen.add(href)
                unique.append(href)
        return unique
    mapping = _as_mapping(value)
    url_list = mapping.get("url_list")
    if isinstance(url_list, (list, tuple)):
        for entry in url_list:
            if isinstance(entry, str) and entry.startswith(("http://", "https://")):
                return [entry]
        return []
    for key in ("url", "download_url", "src"):
        candidate = mapping.get(key)
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            return [candidate]
    return []


def _image_urls(value: Any) -> List[str]:
    """Recursively collect http(s) URLs from f2 filter objects."""
    found: List[str] = []
    if value is None:
        return found
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            found.append(value)
        return found
    if isinstance(value, (list, tuple, set)):
        for entry in value:
            found.extend(_image_urls(entry))
        return found
    mapping = _as_mapping(value)
    for key in ("url_list", "url", "download_url", "src"):
        if key in mapping:
            found.extend(_image_urls(mapping[key]))
    if not found:
        for key, entry in mapping.items():
            if key in {"url_list", "url", "download_url", "src"}:
                continue
            found.extend(_image_urls(entry))
    # Preserve order, drop duplicates.
    seen = set()
    unique = []
    for href in found:
        if href not in seen:
            seen.add(href)
            unique.append(href)
    return unique


def _video_url_from_detail(data: Dict[str, Any]) -> str:
    video = data.get("video") or {}
    mapping = _as_mapping(video)
    for key in ("play_addr", "download_addr", "play_addr_h264", "bit_rate"):
        urls = _image_urls(mapping.get(key))
        if urls:
            return urls[0]
    return ""


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
