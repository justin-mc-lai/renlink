"""l3 manifest/object cache and the deterministic task_id algorithm.

The l1 /parse response schema is frozen (additionalProperties=false), so the
stage task_id is a hash of the parse payload itself. /parse remembers the
manifest under that id; /stage only consumes it.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

_CONTENT_ID = re.compile(
    r"/(?:video|note|gallery|slides|explore|discovery/item)/([A-Za-z0-9_-]+)"
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def task_ttl_s() -> int:
    return _env_int("STAGE_TASK_TTL_S", 600)


def object_ttl_s() -> int:
    return _env_int("STAGE_OBJECT_TTL_S", 86400)


def content_id_from_url(url: str) -> str:
    path = urlparse(url or "").path or ""
    match = _CONTENT_ID.search(path)
    if match:
        return match.group(1)
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()[:16]


def task_id_for(payload: Dict[str, Any]) -> str:
    """v1|platform|content_type|resolved_url + one line per returned item."""
    platform = str(payload.get("platform") or "")
    content_type = str(payload.get("content_type") or "")
    resolved_url = str(payload.get("resolved_url") or "")
    lines: List[str] = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(
            "{index}:{type}:{ext}:{url}".format(
                index=item.get("index"),
                type=item.get("type"),
                ext=item.get("ext"),
                url=item.get("remoteUrl"),
            )
        )
    material = "v1|" + platform + "|" + content_type + "|" + resolved_url + "\n" + "\n".join(lines)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return "st_" + digest


@dataclass(frozen=True)
class StageManifest:
    task_id: str
    platform: str
    content_type: str
    resolved_url: str
    content_id: str
    items: Tuple[Dict[str, Any], ...]
    expires_at: float

    def item_at(self, index: int) -> Optional[Dict[str, Any]]:
        for item in self.items:
            if int(item.get("index", -1)) == index:
                return item
        return None


_lock = threading.Lock()
_tasks: Dict[str, StageManifest] = {}
_objects: Dict[str, Dict[str, Any]] = {}


def remember(payload: Dict[str, Any]) -> str:
    """Store the /parse manifest under its deterministic task_id."""
    task_id = task_id_for(payload)
    items: List[Dict[str, Any]] = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "index": int(item.get("index", len(items))),
                "type": str(item.get("type") or ""),
                "ext": str(item.get("ext") or "").lower(),
                "remoteUrl": str(item.get("remoteUrl") or ""),
                "needs_transcode": bool(item.get("needs_transcode", False)),
            }
        )
    manifest = StageManifest(
        task_id=task_id,
        platform=str(payload.get("platform") or ""),
        content_type=str(payload.get("content_type") or ""),
        resolved_url=str(payload.get("resolved_url") or ""),
        content_id=content_id_from_url(str(payload.get("resolved_url") or "")),
        items=tuple(items),
        expires_at=time.monotonic() + task_ttl_s(),
    )
    with _lock:
        _purge_tasks_locked()
        _tasks[task_id] = manifest
    return task_id


def get_task(task_id: str) -> Optional[StageManifest]:
    if not task_id:
        return None
    with _lock:
        _purge_tasks_locked()
        return _tasks.get(task_id)


def object_key(platform: str, content_id: str, index: int) -> str:
    return "{0}:{1}:{2}".format(platform, content_id, index)


def get_object(platform: str, content_id: str, index: int) -> Optional[Dict[str, Any]]:
    key = object_key(platform, content_id, index)
    now = time.monotonic()
    with _lock:
        _purge_objects_locked(now)
        entry = _objects.get(key)
        if not entry:
            return None
        return dict(entry)


def put_object(
    platform: str,
    content_id: str,
    index: int,
    file_id: str,
    kind: str,
    ext: str,
    size: int,
) -> None:
    key = object_key(platform, content_id, index)
    with _lock:
        _objects[key] = {
            "fileID": file_id,
            "kind": kind,
            "ext": ext,
            "bytes": int(size),
            "expires_at": time.monotonic() + object_ttl_s(),
        }


def forget_object(platform: str, content_id: str, index: int) -> None:
    with _lock:
        _objects.pop(object_key(platform, content_id, index), None)


def _purge_tasks_locked() -> None:
    now = time.monotonic()
    expired = [key for key, value in _tasks.items() if value.expires_at <= now]
    for key in expired:
        _tasks.pop(key, None)


def _purge_objects_locked(now: float) -> None:
    expired = [key for key, value in _objects.items() if value["expires_at"] <= now]
    for key in expired:
        _objects.pop(key, None)


def clear() -> None:
    """Test hook: drop every manifest and object id."""
    with _lock:
        _tasks.clear()
        _objects.clear()
