"""Xiaohongshu branch.

Video: yt-dlp XiaoHongShuIE. Note: delegated to l2-xhs-images `parse_note`;
this round only ships the seam and an injectable stub. l1 never parses
__INITIAL_STATE__ itself and never rewrites the webp image URL.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..contract import ext_from_url
from ..egress import ytdlp_options
from ..errors import ApiError
from ..session_bridge import CookieExpired, get_cookie

NoteParser = Callable[[str, str], Awaitable[Dict[str, Any]]]

_note_parser: Optional[NoteParser] = None


class _QuietLogger:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def configure_note_parser(parser: Optional[NoteParser]) -> None:
    """Test/DI hook: replace the l2 parse_note seam."""
    global _note_parser
    _note_parser = parser


async def parse(url: str, cookie: Optional[str] = None) -> Dict[str, Any]:
    if cookie is None:
        try:
            cookie = get_cookie("xhs")
        except CookieExpired as exc:
            raise ApiError("COOKIE_EXPIRED") from exc
    info = await asyncio.to_thread(_ytdlp_info, url, cookie)
    video_url = _info_video_url(info) if info else ""
    if video_url:
        return {
            "content_type": "video",
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
    note = await _call_note_parser(url, cookie)
    return _note_payload(note)


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


async def _call_note_parser(url: str, cookie: str) -> Dict[str, Any]:
    if _note_parser is not None:
        return await _note_parser(url, cookie)
    stub = _env_note_stub(url)
    if stub is not None:
        return stub
    raise ApiError(
        "PARSE_FAILED",
        "l2-xhs-images 的 parse_note 尚未冻结，l1 仅保留接缝",
    )


def _env_note_stub(url: str) -> Optional[Dict[str, Any]]:
    """Optional in-memory stub: PARSE_L2_NOTE_STUB='{"items": [...]}'.

    Only for local tests. It never writes to disk and the real l2 module will
    replace this path once l2 is frozen.
    """
    raw = os.getenv("PARSE_L2_NOTE_STUB", "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError("PARSE_FAILED", "PARSE_L2_NOTE_STUB 不是合法 JSON") from exc
    if isinstance(payload, dict) and "items" in payload:
        payload.setdefault("title", "")
        return payload
    if isinstance(payload, dict) and url in payload:
        entry = payload[url]
    else:
        entry = payload
    if not isinstance(entry, dict) or "items" not in entry:
        raise ApiError("PARSE_FAILED", "PARSE_L2_NOTE_STUB 缺少 items")
    return entry


def _note_payload(note: Dict[str, Any]) -> Dict[str, Any]:
    raw_items = note.get("items")
    if raw_items is None:
        raw_items = note.get("images") or note.get("imageList") or []
    items: List[Dict[str, Any]] = []
    for raw in raw_items:
        if isinstance(raw, str):
            href = raw
            extra: Dict[str, Any] = {}
        elif isinstance(raw, dict):
            href = str(raw.get("remoteUrl") or raw.get("url") or "")
            extra = raw
        else:
            continue
        if not href.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "type": "image",
                "remoteUrl": href,  # keep the original webp address
                "ext": str(extra.get("ext") or ext_from_url(href, "webp")),
                "cover": str(extra.get("cover") or ""),
                "width": _as_int(extra.get("width")),
                "height": _as_int(extra.get("height")),
                "needs_transcode": True,
            }
        )
    if not items:
        raise ApiError("PARSE_FAILED", "l2 parse_note 没有返回可用的图片地址")
    return {
        "content_type": "note",
        "title": str(note.get("title") or note.get("desc") or ""),
        "items": items,
    }


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
