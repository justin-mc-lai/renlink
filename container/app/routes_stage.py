"""POST /stage: download one parsed item, transcode if needed, store, return id."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from . import stage_cache
from .stage_store import StageStore, StoreFailed, StoreNotReady, build_store, store_mode
from .transcode import (
    IMAGE_TYPES,
    TranscodeFailed,
    is_webp,
    magic_head,
    normal_image_ext,
    to_jpeg,
)

logger = logging.getLogger("renlink.stage")

router = APIRouter()

_TASK_ID = re.compile(r"^st_[0-9a-f]{24}$")
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
class StageError(Exception):
    def __init__(self, code: str, message: str, status: int, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        super().__init__(message)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _error(code: str, message: str, status: int, retryable: bool) -> StageError:
    return StageError(code, message, status, retryable)


def _invalid(message: str) -> StageError:
    return _error("INVALID_REQUEST", message, 400, False)


def _response(body: Dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status)


def _failure(exc: StageError) -> JSONResponse:
    return _response(
        {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        },
        status=exc.status,
    )


def _egress_proxy() -> Optional[str]:
    value = os.getenv("EGRESS_PROXY", "").strip()
    return value or None


def _referer(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "douyin" in host:
        return "https://www.douyin.com/"
    if "xhscdn" in host or "xiaohongshu" in host:
        return "https://www.xiaohongshu.com/"
    return ""


async def _download(
    url: str, dest: Path, max_bytes: int, video: bool
) -> int:
    fake_length = os.getenv("STAGE_FAKE_CONTENT_LENGTH", "").strip()
    if fake_length:
        try:
            if int(fake_length) > max_bytes:
                raise _error("TOO_LARGE", "文件超过大小上限", 413, False)
        except ValueError:
            pass
    headers = {"User-Agent": _UA, "Accept": "*/*"}
    referer = _referer(url)
    if referer:
        headers["Referer"] = referer
    total = 0
    try:
        async with httpx.AsyncClient(
            proxy=_egress_proxy(),
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
        ) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code >= 400:
                    raise _error(
                        "STAGE_FAILED",
                        "上游下载返回 {0}".format(response.status_code),
                        502,
                        True,
                    )
                length = response.headers.get("content-length")
                if length:
                    try:
                        if int(length) > max_bytes:
                            raise _error("TOO_LARGE", "文件超过大小上限", 413, False)
                    except ValueError:
                        pass
                with dest.open("wb") as handle:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise _error("TOO_LARGE", "文件超过大小上限", 413, False)
                        handle.write(chunk)
    except StageError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        kind = "视频" if video else "图片"
        raise _error("STAGE_FAILED", "{0}下载失败".format(kind), 502, True) from exc
    if total == 0:
        raise _error("STAGE_FAILED", "上游返回空文件", 502, True)
    return total


async def _run_stage(
    manifest: stage_cache.StageManifest, index: int, item: Dict[str, Any]
) -> Dict[str, Any]:
    store: StageStore = build_store()
    try:
        await store.ready()
    except StoreNotReady as exc:
        raise _error(
            "STAGE_NOT_READY",
            "对象存储未配置或不可用: {0}".format(exc),
            503,
            True,
        ) from exc

    cached = stage_cache.get_object(manifest.platform, manifest.content_id, index)
    if cached and store.exists(cached["fileID"]):
        return {
            "ok": True,
            "fileID": cached["fileID"],
            "kind": cached["kind"],
            "ext": cached["ext"],
            "bytes": cached["bytes"],
        }
    if cached:
        stage_cache.forget_object(manifest.platform, manifest.content_id, index)

    delay_ms = _env_int("STAGE_FAKE_DELAY_MS", 0)
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)

    kind = "video" if item.get("type") == "video" else "image"
    video = kind == "video"
    max_bytes = _env_int(
        "STAGE_MAX_VIDEO_BYTES" if video else "STAGE_MAX_IMAGE_BYTES",
        209715200 if video else 33554432,
    )
    declared = str(item.get("ext") or "").lower()
    needs_transcode = bool(item.get("needs_transcode", False))
    remote_url = str(item.get("remoteUrl") or "")
    if not remote_url.startswith(("http://", "https://")):
        raise _error("STAGE_FAILED", "清单项没有可下载地址", 400, False)

    fd, raw_name = tempfile.mkstemp(prefix="renlink-stage-", dir="/tmp")
    os.close(fd)
    raw_path = Path(raw_name)
    out_path = raw_path
    try:
        size = await asyncio.wait_for(
            _download(remote_url, raw_path, max_bytes, video),
            timeout=max(1.0, _env_int("STAGE_DOWNLOAD_TIMEOUT_S", 45)),
        )
        if video:
            ext = declared if declared in ("mp4", "mov") else "mp4"
            content_type = "video/mp4" if ext == "mp4" else "video/quicktime"
        else:
            head = magic_head(raw_path)
            if needs_transcode or declared == "webp" or is_webp(head):
                out_path = raw_path.with_suffix(".jpg")
                try:
                    await asyncio.to_thread(to_jpeg, raw_path, out_path)
                except TranscodeFailed as exc:
                    raise _error("STAGE_FAILED", "图片转码失败", 502, True) from exc
                ext = "jpg"
                content_type = "image/jpeg"
                size = out_path.stat().st_size
            else:
                ext = normal_image_ext(declared, head)
                content_type = IMAGE_TYPES.get(ext, "application/octet-stream")
        key = "l3/{0}/{1}.{2}".format(manifest.content_id, index, ext)
        try:
            file_id = await store.put(out_path, key, content_type)
        except StoreFailed as exc:
            raise _error("STAGE_FAILED", "对象存储上传失败", 502, True) from exc
        if store.mode == "local":
            local = store.path_for(file_id)  # type: ignore[attr-defined]
            if local is not None and local.is_file():
                size = local.stat().st_size
        stage_cache.put_object(
            manifest.platform,
            manifest.content_id,
            index,
            file_id,
            kind,
            ext,
            size,
        )
        logger.info(
            "stage ok platform=%s content_id=%s index=%s kind=%s ext=%s bytes=%s",
            manifest.platform,
            manifest.content_id,
            index,
            kind,
            ext,
            size,
        )
        return {
            "ok": True,
            "fileID": file_id,
            "kind": kind,
            "ext": ext,
            "bytes": size,
        }
    finally:
        for path in {raw_path, out_path}:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning("stage temp cleanup failed")


async def _stage(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 - invalid JSON is a 400
        raise _invalid("请求体不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise _invalid("请求体必须是 JSON 对象")
    for key in body:
        if str(key).lower() == "cookie":
            raise _invalid("请求体不得包含 cookie 字段")

    task_id = body.get("task_id")
    if not isinstance(task_id, str) or not _TASK_ID.match(task_id):
        raise _invalid("task_id 缺失或格式不正确")
    index = body.get("index")
    if isinstance(index, bool) or not isinstance(index, int):
        raise _invalid("index 必须是整数")
    if index < 0:
        raise _error("STAGE_FAILED", "index 不能小于 0", 400, False)

    manifest = stage_cache.get_task(task_id)
    if manifest is None:
        raise _error("STAGE_EXPIRED", "清单缓存已过期，请重新解析", 410, False)
    item = manifest.item_at(index)
    if item is None:
        raise _error("STAGE_FAILED", "清单中不存在这个 index", 400, False)

    budget = _env_int("STAGE_TIMEOUT_S", 60)
    started = time.perf_counter()
    timeout = max(0.1, budget - (time.perf_counter() - started))
    result = await asyncio.wait_for(_run_stage(manifest, index, item), timeout=timeout)
    return _response(result)


@router.post("/stage")
async def stage_item(request: Request) -> JSONResponse:
    try:
        return await _stage(request)
    except asyncio.TimeoutError:
        return _failure(_error("TIMEOUT", "单请求超过 60 秒", 504, True))
    except StageError as exc:
        return _failure(exc)
    except Exception:  # noqa: BLE001 - fixed failure envelope
        logger.exception("stage unexpected failure")
        return _failure(_error("STAGE_FAILED", "转存失败", 502, True))



@router.get("/stage/file")
async def stage_file(file_id: str = Query(..., alias="file_id")) -> Any:
    """Stream a previously staged object so H5/PC can download it directly."""
    if not file_id.startswith("cloud://"):
        return _failure(_error("INVALID_REQUEST", "file_id 必须是 cloud:// 对象", 400, False))
    store = build_store()
    try:
        await store.ready()
    except StoreNotReady as exc:
        return _failure(_error("STAGE_NOT_READY", str(exc), 503, True))
    fd, tmp_name = tempfile.mkstemp(prefix="renlink-serve-")
    os.close(fd)
    dest = Path(tmp_name)
    try:
        await asyncio.to_thread(store.fetch_sync, file_id, dest)
    except StoreFailed as exc:
        dest.unlink(missing_ok=True)
        return _failure(_error("STAGE_FAILED", str(exc), 502, True))
    ext = file_id.rsplit(".", 1)[-1].lower()
    media = {
        "mp4": "video/mp4",
        "m4a": "audio/mp4",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return FileResponse(dest, media_type=media, filename=f"renlink.{ext}", background=BackgroundTask(dest.unlink))

@router.get("/stage/mode")
async def stage_mode() -> JSONResponse:
    """Operational probe: which store adapter is active (no secrets)."""
    return JSONResponse({"ok": True, "store": store_mode()})
