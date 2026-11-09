"""FastAPI assembly for the parse-only l1 container."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from urllib.parse import urlparse

from . import __version__
from .contract import encode_payload
from .errors import ApiError, error_envelope
from .parsers import douyin_argus, render
from .routes_parse import router as parse_router
from .routes_stage import router as stage_router
from .routes_zip import router as zip_router
from .egress import mode as egress_mode
from .session_bridge import health_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("renlink")

# Signed query values in upstream URLs must never reach container stdout.
_SENSITIVE_QUERY = re.compile(
    r"(?i)(msToken|a_bogus|X-Bogus|X-Amz-Signature|verifyFp|fp|signtime|signature)=([^&\s'\"<>]+)"
)
_REDACTED = r"\1=[REDACTED]"


def _install_log_redaction() -> None:
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        original_get_message = record.getMessage

        def get_message() -> str:
            return _SENSITIVE_QUERY.sub(_REDACTED, original_get_message())

        record.getMessage = get_message  # type: ignore[method-assign]
        return record

    logging.setLogRecordFactory(factory)


_install_log_redaction()

app = FastAPI(title="Renlink l1 parser core", version=__version__)

# H5 / PWA callers are cross-origin in dev and on separate hosts in prod.
# Default to the local dev ports; override with CORS_ALLOW_ORIGINS (comma separated).
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]
if _cors_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", "x-request-id"],
    )

app.include_router(parse_router)
app.include_router(stage_router)
app.include_router(zip_router)


@app.on_event("startup")
async def _prewarm_renderer() -> None:
    """Connect to Obscura before serving so cold start stays out of the 12s budget.

    A failure is logged and does not stop the app: the renderer stays optional.
    """
    if render.enabled() and await render.prewarm_html():
        logger.info("obscura renderer prewarmed cdp=%s", render.cdp_endpoint())


class RateLimiter:
    """In-memory per-IP limiter. One instance per worker/process."""

    def __init__(self) -> None:
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and now - bucket[0] >= 60.0:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_limiter = RateLimiter()


@app.middleware("http")
async def guard(request: Request, call_next):
    request.state.started = time.perf_counter()
    if request.url.path == "/parse" and request.method == "POST":
        try:
            limit = int(os.getenv("PARSE_RATE_LIMIT_PER_MIN", "20") or "20")
        except ValueError:
            limit = 20
        client = request.client.host if request.client else "unknown"
        if limit > 0 and not _limiter.allow(client, limit):
            body = error_envelope("RATE_LIMITED", elapsed_ms=0)
            return Response(
                content=encode_payload(body),
                status_code=429,
                media_type="application/json",
            )
    return await call_next(request)


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> Response:
    started = getattr(request.state, "started", time.perf_counter())
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    payload = error_envelope(exc.code, exc.message, elapsed_ms=elapsed_ms)
    return Response(
        content=encode_payload(payload),
        status_code=exc.http_status,
        media_type="application/json",
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> Response:
    started = getattr(request.state, "started", time.perf_counter())
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.error("unexpected error type=%s", type(exc).__name__)
    payload = error_envelope("PARSE_FAILED", elapsed_ms=elapsed_ms)
    return Response(
        content=encode_payload(payload),
        status_code=502,
        media_type="application/json",
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "version": __version__,
            "platforms": health_snapshot(),
            "egress_proxy": egress_mode(),
            "argus": douyin_argus.stats(),
            "render": render.stats(),
        }
    )


@app.get("/render/probe")
async def render_probe(url: str = Query(default="")) -> JSONResponse:
    """Operational probe for the optional renderer (TC-023).

    Only reachable while ENABLE_OBSCURA=1, and only for render-capable
    platforms. Douyin is rejected here on purpose: its pages never go through
    Obscura.
    """
    if not render.enabled():
        raise HTTPException(status_code=404, detail="renderer disabled")
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not (host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")):
        raise HTTPException(status_code=400, detail="render probe only supports xhs pages")
    try:
        result = await render.render_html(url)
    except render.RenderTimeout as exc:
        logger.warning("render probe timeout: %s", exc)
        return JSONResponse(
            {"ok": False, "error": {"code": "TIMEOUT", "message": str(exc), "retryable": True}},
            status_code=504,
        )
    except render.RenderUnavailable as exc:
        logger.warning("render probe failed: %s", exc)
        return JSONResponse(
            {"ok": False, "error": {"code": "PARSE_FAILED", "message": str(exc), "retryable": True}},
            status_code=502,
        )
    return JSONResponse({"ok": True, **result, "obscura_alive": render.obscura_alive()})
