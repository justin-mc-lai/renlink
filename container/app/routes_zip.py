"""POST /zip: pack one task's already-staged l3 images into a single zip."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .zipkit import ZipError, export_zip

logger = logging.getLogger("renlink.zip")

router = APIRouter()

_TASK_ID = re.compile(r"^st_[0-9a-f]{24}$")


def _failure(exc: ZipError) -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        },
        status_code=exc.status,
    )


async def _zip(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 - invalid JSON is a 400
        raise ZipError("INVALID_REQUEST", "请求体不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ZipError("INVALID_REQUEST", "请求体必须是 JSON 对象")
    for key in body:
        if str(key).lower() == "cookie":
            raise ZipError("INVALID_REQUEST", "请求体不得包含 cookie 字段")

    task_id = body.get("task_id")
    if not isinstance(task_id, str) or not _TASK_ID.match(task_id):
        raise ZipError("INVALID_REQUEST", "task_id 缺失或格式不正确")
    if "indexes" in body and not isinstance(body["indexes"], list):
        raise ZipError("INVALID_REQUEST", "indexes 必须是数组")
    indexes = body["indexes"] if "indexes" in body else None
    return await export_zip(task_id, indexes)


@router.post("/zip")
async def zip_task(request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _zip(request))
    except ZipError as exc:
        return _failure(exc)
    except Exception:  # noqa: BLE001 - fixed failure envelope
        logger.exception("zip unexpected failure")
        return _failure(ZipError("ZIP_FAILED", "打包失败"))

