"""Xiaohongshu branch.

Video: yt-dlp XiaoHongShuIE. Note (l2-xhs-images): fetch the canonical note
page, read window.__INITIAL_STATE__, pick the original image URL from
urlDefault -> infoList WB_DFT -> CRD_WM_WEBP in imageList order, and require
an xsec_token. l1 still owns /parse fields, normalization and truncation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from ..contract import ext_from_url
from ..egress import ytdlp_options
from ..errors import ApiError
from ..session_bridge import CookieExpired, get_cookie

logger = logging.getLogger("renlink.xhs")

NoteParser = Callable[[str, str], Awaitable[Dict[str, Any]]]

_note_parser: Optional[NoteParser] = None

_DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)
_NOTE_PATH = re.compile(r"^/(?:explore|discovery/item)/[^/]+/?$")
_STATE_MARK = "window.__INITIAL_STATE__"

_cache_lock = threading.Lock()
_note_cache: Dict[str, Dict[str, Any]] = {}
_counters: Dict[str, int] = {
    "xhs_note_parse_total{result=ok}": 0,
    "xhs_note_parse_total{result=need_xsec}": 0,
    "xhs_note_parse_total{result=failed}": 0,
    "xhs_note_cache_hit_total": 0,
    "xhs_note_cache_miss_total": 0,
    "xhs_note_images_total": 0,
}


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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def cache_ttl_s() -> int:
    return _env_int("XHS_NOTE_CACHE_TTL_S", 600)


def counters() -> Dict[str, int]:
    """Process-local counters read by l7; AC-010 fixes the names."""
    with _cache_lock:
        return dict(_counters)


def reset_cache() -> None:
    """Test helper: drop cached notes and zero the counters."""
    with _cache_lock:
        _note_cache.clear()
        for name in _counters:
            _counters[name] = 0


def _bump(name: str, amount: int = 1) -> None:
    with _cache_lock:
        if name in _counters:
            _counters[name] += amount


def _cache_key(note_id: str, token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return "xhs:note:v1:{0}:{1}".format(note_id, digest)


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.monotonic()
    with _cache_lock:
        entry = _note_cache.get(key)
        if entry is None:
            return None
        if entry["expires_at"] <= now:
            _note_cache.pop(key, None)
            return None
        return entry["value"]  # immutable by convention: copied on return


def _cache_put(key: str, value: Dict[str, Any], ttl: int) -> None:
    if ttl <= 0 or not key:
        return
    with _cache_lock:
        _note_cache[key] = {
            "value": value,
            "expires_at": time.monotonic() + ttl,
        }


def _copy_note(note: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "note_id": note["note_id"],
        "title": note["title"],
        "xsec_token": note["xsec_token"],
        "items": [dict(item) for item in note["items"]],
    }


def _url_xsec_token(url: str) -> str:
    for value in parse_qs(urlparse(url).query).get("xsec_token") or []:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _log_parse(
    *,
    note_id: str,
    image_count: int,
    token_state: str,
    cache: str,
    cache_state: str,
    started: float,
    code: str,
) -> None:
    logger.info(
        "event=xhs_note_parse note_id=%s image_count=%s xsec_token=%s "
        "cache=%s cache_state=%s elapsed_ms=%s code=%s",
        note_id,
        image_count,
        token_state,
        cache,
        cache_state,
        int((time.perf_counter() - started) * 1000),
        code,
    )


def _skip_ytdlp() -> bool:
    return os.getenv("PARSE_XHS_SKIP_YTDLP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


async def parse(url: str, cookie: Optional[str] = None) -> Dict[str, Any]:
    if cookie is None:
        try:
            cookie = get_cookie("xhs")
        except CookieExpired as exc:
            raise ApiError("COOKIE_EXPIRED") from exc
    info = None
    if not _skip_ytdlp():
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
    note = await _call_note_parser(url, cookie or "")
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
    return await parse_note(url, cookie)


def _env_note_stub(url: str) -> Optional[Dict[str, Any]]:
    """Optional in-memory stub: PARSE_L2_NOTE_STUB='{"items": [...]}'.

    Only for local tests. It never writes to disk.
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


# --- l2 note parsing ---------------------------------------------------------


def _note_id_from_url(url: str) -> str:
    segments = [part for part in (urlparse(url).path or "").split("/") if part]
    return segments[-1] if segments else ""


def _check_note_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not (host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")):
        raise ApiError("PARSE_FAILED", "没有落到小红书规范域名")
    if not _NOTE_PATH.match(parsed.path or ""):
        raise ApiError("PARSE_FAILED", "没有落到笔记规范页")


def _stub_path() -> str:
    return os.getenv("XHS_NOTE_HTTP_STUB", "").strip()


def _load_stub() -> Dict[str, Any]:
    path = _stub_path()
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError("PARSE_FAILED", "XHS_NOTE_HTTP_STUB 不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ApiError("PARSE_FAILED", "XHS_NOTE_HTTP_STUB 必须是 JSON 对象")
    if isinstance(data.get("responses"), dict):
        data = data["responses"]
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def _stub_body(entry: Dict[str, Any]) -> str:
    inline = entry.get("body")
    if isinstance(inline, str):
        return inline
    name = entry.get("body_file")
    if not isinstance(name, str) or not name:
        raise ApiError("PARSE_FAILED", "构造桩缺少页面内容")
    path = Path(name)
    if not path.is_absolute():
        stub = _stub_path()
        path = Path(stub).parent / path if stub else path
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ApiError("PARSE_FAILED", "构造桩页面读取失败") from exc


async def _stub_fetch(url: str, max_hops: int, timeout_s: float) -> tuple:
    responses = _load_stub()
    current = url
    hops = 0
    while True:
        entry = responses.get(current)
        if entry is None:
            raise ApiError("PARSE_FAILED", "构造桩没有覆盖这个 URL")
        delay_ms = 0
        try:
            delay_ms = int(entry.get("delay_ms") or 0)
        except (TypeError, ValueError):
            delay_ms = 0
        if delay_ms > 0:
            try:
                await asyncio.wait_for(
                    asyncio.sleep(delay_ms / 1000.0), timeout=timeout_s
                )
            except asyncio.TimeoutError as exc:
                raise ApiError("TIMEOUT", "小红书图文抓取超时") from exc
        status = int(entry.get("status") or 200)
        location = str(entry.get("location") or "")
        if location or status in (301, 302, 303, 307, 308):
            hops += 1
            if hops > max_hops:
                raise ApiError("PARSE_FAILED", "重定向超过 {0} 跳".format(max_hops))
            if not location:
                raise ApiError("PARSE_FAILED", "重定向缺少 Location")
            current = urljoin(current, location)
            continue
        if status >= 400:
            raise ApiError("PARSE_FAILED", "构造桩页面返回 {0}".format(status))
        return _stub_body(entry), current


async def _fetch_note(url: str, cookie: str) -> tuple:
    timeout_s = float(_env_int("XHS_NOTE_TIMEOUT_S", 8) or 8)
    max_bytes = _env_int("XHS_NOTE_MAX_BYTES", 5242880) or 5242880
    max_hops = _env_int("XHS_NOTE_MAX_HOPS", 3)
    if _stub_path():
        html, final_url = await _stub_fetch(url, max_hops, timeout_s)
    else:
        headers = {
            "User-Agent": os.getenv("XHS_NOTE_UA", "").strip() or _DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml",
        }
        if cookie:
            headers["Cookie"] = cookie
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=httpx.Timeout(timeout_s)
            ) as client:
                response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ApiError("TIMEOUT", "小红书图文抓取超时") from exc
        except httpx.HTTPError as exc:
            raise ApiError("PARSE_FAILED", "小红书图文抓取失败") from exc
        if len(response.history) > max_hops:
            raise ApiError("PARSE_FAILED", "重定向超过 {0} 跳".format(max_hops))
        if response.status_code >= 400:
            raise ApiError(
                "PARSE_FAILED",
                "小红书页面返回 {0}".format(response.status_code),
            )
        html, final_url = response.text, str(response.url)
    if len(html.encode("utf-8")) > max_bytes:
        raise ApiError("PARSE_FAILED", "小红书页面超过大小上限")
    _check_note_url(final_url)
    return html, final_url


def _tolerant_json(text: str) -> str:
    """Quote bare keys and turn JS undefined into null, skipping strings."""
    out: List[str] = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if text.startswith("undefined", index):
            out.append("null")
            index += len("undefined")
            continue
        if char in "{,":
            out.append(char)
            index += 1
            while index < length and text[index] in " \t\r\n":
                out.append(text[index])
                index += 1
            key_start = index
            if key_start < length and (text[key_start].isalpha() or text[key_start] in "_$"):
                cursor = key_start
                while cursor < length and (
                    text[cursor].isalnum() or text[cursor] in "_$"
                ):
                    cursor += 1
                after = cursor
                while after < length and text[after] in " \t\r\n":
                    after += 1
                if after < length and text[after] == ":":
                    out.append('"' + text[key_start:cursor] + '"')
                    index = cursor
                    continue
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _extract_state(html: str) -> Dict[str, Any]:
    marker = html.find(_STATE_MARK)
    if marker < 0:
        raise ApiError("PARSE_FAILED", "页面没有 window.__INITIAL_STATE__")
    start = html.find("{", marker)
    if start < 0:
        raise ApiError("PARSE_FAILED", "初始状态没有对象")
    blob = html[start:]
    decoder = json.JSONDecoder()
    state: Any = None
    for candidate in (blob, _tolerant_json(blob)):
        try:
            decoded, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            state = decoded
            break
    if state is None:
        raise ApiError("PARSE_FAILED", "初始状态 JSON 解析失败")
    return state


def _note_from_state(state: Dict[str, Any], note_id: str) -> Dict[str, Any]:
    # AC-004: note.noteDetailMap[note_id].note first (single entry as fallback),
    # then noteData.data.noteData whose noteId must match the URL note_id.
    note: Any = None
    holder = state.get("note")
    detail_map = holder.get("noteDetailMap") if isinstance(holder, dict) else None
    if isinstance(detail_map, dict) and detail_map:
        entry = detail_map.get(note_id)
        if entry is None and len(detail_map) == 1:
            entry = next(iter(detail_map.values()))
        if isinstance(entry, dict):
            note = entry.get("note")
    if not isinstance(note, dict):
        holder = state.get("noteData")
        data = holder.get("data") if isinstance(holder, dict) else None
        candidate = data.get("noteData") if isinstance(data, dict) else None
        if isinstance(candidate, dict) and str(candidate.get("noteId") or "") == note_id:
            note = candidate
    if not isinstance(note, dict):
        raise ApiError("PARSE_FAILED", "两种结构都取不到目标笔记")
    return note


def _image_url(raw: Dict[str, Any]) -> str:
    direct = raw.get("urlDefault")
    if isinstance(direct, str) and direct.startswith(("http://", "https://")):
        return direct
    info = raw.get("infoList")
    if isinstance(info, list):
        for scene in ("WB_DFT", "CRD_WM_WEBP"):
            for entry in info:
                if not isinstance(entry, dict) or entry.get("imageScene") != scene:
                    continue
                url = entry.get("url")
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    return url
    return ""


def _note_items(note: Dict[str, Any]) -> List[Dict[str, Any]]:
    image_list = note.get("imageList")
    if not isinstance(image_list, list) or not image_list:
        raise ApiError("PARSE_FAILED", "imageList 为空或不是数组")
    items: List[Dict[str, Any]] = []
    for raw in image_list:
        if not isinstance(raw, dict):
            continue
        remote_url = _image_url(raw)
        if not remote_url:
            continue
        items.append(
            {
                "index": len(items),
                "type": "image",
                "remoteUrl": remote_url,
                "ext": ext_from_url(remote_url, "webp"),
                "cover": "",
                "width": _as_int(raw.get("width")),
                "height": _as_int(raw.get("height")),
                "needs_transcode": True,
            }
        )
    if not items:
        raise ApiError("PARSE_FAILED", "imageList 没有可用的原图地址")
    return items


def _xsec_token(final_url: str, note: Dict[str, Any], state: Dict[str, Any]) -> str:
    values = parse_qs(urlparse(final_url).query).get("xsec_token") or []
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    for candidate in (note.get("xsecToken"), state.get("xsecToken")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ApiError("NEED_XSEC_TOKEN")


async def parse_note(url: str, cookie: str) -> Dict[str, Any]:
    """l2 seam: canonical note page -> ordered original image items."""
    started = time.perf_counter()
    note_id = _note_id_from_url(url)
    ttl = cache_ttl_s()
    url_token = _url_xsec_token(url)
    key = _cache_key(note_id, url_token) if url_token else ""
    cache_state = "disabled" if ttl <= 0 else "enabled"
    if ttl > 0 and key:
        hit = _cache_get(key)
        if hit is not None:
            _bump("xhs_note_cache_hit_total")
            _bump("xhs_note_parse_total{result=ok}")
            _bump("xhs_note_images_total", len(hit["items"]))
            _log_parse(
                note_id=hit["note_id"],
                image_count=len(hit["items"]),
                token_state="present",
                cache="hit",
                cache_state=cache_state,
                started=started,
                code="ok",
            )
            return _copy_note(hit)
    if ttl > 0:
        _bump("xhs_note_cache_miss_total")
    try:
        html, final_url = await _fetch_note(url, cookie)
        note_id = _note_id_from_url(final_url) or note_id
        state = _extract_state(html)
        note = _note_from_state(state, note_id)
        token = _xsec_token(final_url, note, state)
        items = _note_items(note)
    except ApiError as exc:
        if exc.code == "NEED_XSEC_TOKEN":
            _bump("xhs_note_parse_total{result=need_xsec}")
        else:
            _bump("xhs_note_parse_total{result=failed}")
        _log_parse(
            note_id=note_id,
            image_count=0,
            token_state="missing" if exc.code == "NEED_XSEC_TOKEN" else "present",
            cache="miss",
            cache_state=cache_state,
            started=started,
            code=exc.code,
        )
        raise
    result = {
        "note_id": note_id,
        "title": str(note.get("title") or note.get("desc") or ""),
        "xsec_token": token,
        "items": items,
    }
    _cache_put(key or _cache_key(note_id, token), result, ttl)
    _bump("xhs_note_parse_total{result=ok}")
    _bump("xhs_note_images_total", len(items))
    _log_parse(
        note_id=note_id,
        image_count=len(items),
        token_state="present",
        cache="miss",
        cache_state=cache_state,
        started=started,
        code="ok",
    )
    return _copy_note(result)


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
