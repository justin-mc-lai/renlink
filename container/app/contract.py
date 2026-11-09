"""Request/response models and the 100-item / 1024000-byte caps."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict

MAX_ITEMS = 100
MAX_RESPONSE_BYTES = 1024000
MAX_URL_LENGTH = 2048

_HTTP_URL = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
_EXT_MAP = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "webp": "webp",
    "gif": "gif",
    "heic": "heic",
    "avif": "avif",
    "mp4": "mp4",
    "mov": "mov",
}


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class ParseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    type: Literal["video", "image"]
    remoteUrl: str
    ext: str
    cover: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    needs_transcode: bool = False


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    platform: Literal["douyin", "xhs"]
    content_type: Literal["video", "note"]
    source_url: str
    resolved_url: str
    title: str = ""
    item_count: int
    elapsed_ms: int
    task_id: str = ""
    items: List[ParseItem]


def is_http_url(value: Any) -> bool:
    return isinstance(value, str) and bool(_HTTP_URL.match(value.strip()))


def ext_from_url(url: str, default: str = "jpeg") -> str:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    tail = path.rsplit("/", 1)[-1]
    if "." not in tail:
        return default
    suffix = tail.rsplit(".", 1)[-1]
    return _EXT_MAP.get(suffix, default)


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def normalize_items(
    raw_items: Iterable[Dict[str, Any]],
    platform: str,
    content_type: str,
) -> Tuple[List[ParseItem], bool]:
    """Reindex items, drop invalid URLs, enforce the 100-item cap."""
    items: List[ParseItem] = []
    valid_count = 0
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        remote_url = str(raw.get("remoteUrl") or raw.get("url") or "").strip()
        if not is_http_url(remote_url):
            continue
        item_type = raw.get("type") or ("video" if content_type == "video" else "image")
        if item_type not in ("video", "image"):
            item_type = "image"
        ext = str(raw.get("ext") or "").strip().lower()
        if not ext:
            ext = ext_from_url(remote_url, "mp4" if item_type == "video" else "jpeg")
        needs_transcode = bool(raw.get("needs_transcode", False))
        if platform == "xhs" and item_type == "image":
            # C5: keep the original webp URL, mark it for l3 transcoding.
            needs_transcode = True
        valid_count += 1
        if len(items) >= MAX_ITEMS:
            continue
        items.append(
            ParseItem(
                index=len(items),
                type=item_type,  # type: ignore[arg-type]
                remoteUrl=remote_url,
                ext=ext,
                cover=str(raw.get("cover") or ""),
                width=_coerce_int(raw.get("width")),
                height=_coerce_int(raw.get("height")),
                needs_transcode=needs_transcode,
            )
        )
    return items, valid_count > MAX_ITEMS


def encode_payload(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def finalize_success(result: ParseResult) -> Tuple[bytes, Dict[str, Any]]:
    """Serialize, then shrink until the body fits 1024000 bytes."""
    payload = result.model_dump(mode="json")
    if result.item_count > MAX_ITEMS or len(payload["items"]) > MAX_ITEMS:
        payload["items"] = payload["items"][:MAX_ITEMS]
        payload["truncated"] = True
    payload["item_count"] = len(payload["items"])
    data = encode_payload(payload)
    while len(data) > MAX_RESPONSE_BYTES and payload["items"]:
        payload["items"] = payload["items"][:-1]
        payload["item_count"] = len(payload["items"])
        payload["truncated"] = True
        data = encode_payload(payload)
    if len(data) > MAX_RESPONSE_BYTES:
        payload["title"] = payload.get("title", "")[:512]
        data = encode_payload(payload)
    return data, payload
