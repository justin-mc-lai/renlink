"""Optional Obscura rendering fallback over CDP (TASK-022 / TASK-023).

Obscura is a general-purpose renderer for platforms that need JavaScript (xhs
and future ones). It is disabled unless ``ENABLE_OBSCURA=1``. While disabled
this module never imports Playwright, never starts a process and never opens a
connection.

Connection rules (truth C9 / chg_42c00bf71013):

* connect with ``playwright.chromium.connect_over_cdp(PLAYWRIGHT_CDP)``
* create a fresh ``new_context()`` per render
* close only the context - never ``browser.close()``, which would stop the
  obscura server process as well

The Playwright driver and the CDP browser are process-wide singletons living on
one dedicated thread (Playwright's sync API is greenlet/thread bound). Every
request only creates a new context, so warm renders skip the driver + CDP
handshake cost. A disconnect invalidates the singleton and the next render
reconnects.

Readiness is polled instead of a fixed settle: under a 1-CPU quota a nominal
``wait_for_timeout(1000)`` can stretch to several seconds. The poll checks the
document title (and ``xsec_token`` for xhs pages) every ~120ms and returns as
soon as the note shell is real. The frozen 12s total budget still applies.

The douyin branch never imports this module; that boundary is checked by
``ops/smoke.py`` TC-024.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
import socket
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger("renlink.render")

DEFAULT_CDP = "ws://127.0.0.1:9222"
DEFAULT_WAIT_MS = 8000
TOTAL_BUDGET_S = 12.0
# Leave a little room for the HTTP response so the client-observed wall clock
# stays inside the frozen 12s budget.
_DEADLINE_S = TOTAL_BUDGET_S - 0.15
_POLL_S = 0.12
# Subresources that never change the server-rendered title or xsec_token.
# Skipping them cuts CPU and bandwidth on a 1-CPU box; scripts still run.
_SKIP_RESOURCES = {"image", "media", "font", "stylesheet"}
# Navigation starts in the background after this probe timeout; polling below
# takes over immediately instead of waiting the full 8s for a commit event that
# can arrive late under CPU starvation.
_GOTO_PROBE_MS = 2000

_lock = threading.Lock()
_stats: Dict[str, Any] = {
    "renders": 0,
    "failures": 0,
    "cdp_connects": 0,
    "browser_launches": 0,
    "reconnects": 0,
    "prewarms": 0,
    "last_url_host": "",
    "last_ms": 0,
    "last_error": "",
}

# One owner thread for Playwright's sync API. Never share its objects with the
# asyncio/threadpool threads.
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()
_pw = None
_browser = None


class RenderUnavailable(Exception):
    """Obscura is disabled, unreachable, or the render did not complete."""


class RenderTimeout(RenderUnavailable):
    """The render exceeded the 8s wait / 12s total budget (C10)."""


def enabled() -> bool:
    return os.getenv("ENABLE_OBSCURA", "").strip() == "1"


def cdp_endpoint() -> str:
    return os.getenv("PLAYWRIGHT_CDP", "").strip() or DEFAULT_CDP


def render_wait_ms() -> int:
    try:
        value = int(os.getenv("RENLINK_RENDER_WAIT_MS", str(DEFAULT_WAIT_MS)) or DEFAULT_WAIT_MS)
    except ValueError:
        return DEFAULT_WAIT_MS
    return max(500, min(value, 8000))


def stats() -> Dict[str, Any]:
    with _lock:
        return {
            "enabled": enabled(),
            "cdp": cdp_endpoint(),
            "wait_ms": render_wait_ms(),
            **_stats,
        }


def _record_failure(message: str) -> None:
    with _lock:
        _stats["failures"] += 1
        _stats["last_error"] = message[:200]


def _host_port(endpoint: str) -> tuple:
    parsed = urlparse(endpoint if "://" in endpoint else "ws://" + endpoint)
    return parsed.hostname or "127.0.0.1", parsed.port or 9222


def obscura_alive(timeout: float = 0.5) -> bool:
    """True while the CDP endpoint still accepts connections.

    This is the check that catches an accidental ``browser.close()``: the
    render call returns, but the obscura server port is gone.
    """
    host, port = _host_port(cdp_endpoint())
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _artifacts_dirs() -> set:
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "playwright-artifacts-*")))


def _cleanup_artifacts(before: set) -> None:
    for path in _artifacts_dirs() - before:
        shutil.rmtree(path, ignore_errors=True)


def _worker() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="obscura-render")
        return _executor


def _reset_browser() -> None:
    """Drop the CDP connection. Never calls ``browser.close()``.

    For a browser obtained through ``connect_over_cdp`` Playwright does not own
    the process; stopping the driver only detaches the client.
    """
    global _pw, _browser
    _browser = None
    playwright, _pw = _pw, None
    if playwright is not None:
        try:
            playwright.stop()
        except Exception:  # noqa: BLE001 - driver already gone
            pass


def _remaining_ms(deadline: float, cap_ms: int) -> int:
    return max(1, min(cap_ms, int((deadline - time.monotonic()) * 1000)))


def _ensure_browser(deadline: float):
    """Return the singleton browser, connecting once per process (or after a drop)."""
    global _pw, _browser
    if _browser is not None:
        try:
            if _browser.is_connected():
                return _browser
        except Exception:  # noqa: BLE001 - treat as dropped
            pass
        with _lock:
            _stats["reconnects"] += 1
        _reset_browser()

    try:
        from playwright.sync_api import sync_playwright  # lazy: disabled mode has no import
    except ImportError as exc:  # pragma: no cover - image without the client
        _record_failure("playwright client missing")
        raise RenderUnavailable("playwright 客户端未安装") from exc

    if _pw is None:
        _pw = sync_playwright().start()
    with _lock:
        _stats["cdp_connects"] += 1
    try:
        _browser = _pw.chromium.connect_over_cdp(cdp_endpoint(), timeout=_remaining_ms(deadline, 8000))
    except Exception as exc:  # noqa: BLE001 - upstream/CDP failure
        _reset_browser()
        _record_failure(f"connect: {type(exc).__name__}: {str(exc)[:120]}")
        if type(exc).__name__ == "TimeoutError":
            raise RenderTimeout("Obscura CDP 连接超时") from exc
        raise RenderUnavailable(f"Obscura CDP 连接失败: {type(exc).__name__}") from exc
    return _browser


def _page_title(page) -> str:
    try:
        return page.title() or ""
    except Exception:  # noqa: BLE001 - navigation swapped the context
        return ""


def _skip_heavy(route) -> None:
    try:
        if route.request.resource_type in _SKIP_RESOURCES:
            route.abort()
        else:
            route.continue_()
    except Exception:  # noqa: BLE001 - navigation already moved on
        pass


def _wait_ready(page, deadline: float, need_token: bool):
    """Poll title (and xsec_token) until the real note shell is ready."""
    last_title = ""
    while time.monotonic() < deadline:
        title = _page_title(page)
        if title:
            last_title = title
        if title and not title.lower().startswith("loading"):
            try:
                html = page.content() or ""
            except Exception:  # noqa: BLE001 - context still swapping
                html = ""
            if html and (not need_token or "xsec_token" in html):
                return title, html
        time.sleep(_POLL_S)
    if last_title.lower().startswith("loading"):
        raise RenderUnavailable("页面仍停留在 loading shell")
    raise RenderTimeout("Obscura 渲染超过 12s 总预算")


def _render_page(url: str, wait_ms: Optional[int] = None) -> Dict[str, Any]:
    """Render one page through Obscura and return title/url/HTML metadata."""
    if not enabled():
        raise RenderUnavailable("ENABLE_OBSCURA!=1")

    budget_ms = max(500, min(int(wait_ms or render_wait_ms()), 8000))
    started = time.monotonic()
    deadline = started + _DEADLINE_S
    host = (urlparse(url).hostname or "").lower()
    need_token = host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")

    browser = _ensure_browser(deadline)
    context = None
    try:
        # Fresh context only. Do not call browser.close(): obscura is the server.
        context = browser.new_context()
        page = context.new_page()
        try:
            page.route("**/*", _skip_heavy)
        except Exception:  # noqa: BLE001 - routing is an optimization only
            logger.debug("page.route unavailable")
        nav_error: Optional[Exception] = None
        try:
            # ``commit`` returns when the document response starts; waiting for
            # load/networkidle would burn the whole budget on analytics.
            page.goto(
                url,
                wait_until="commit",
                timeout=min(_GOTO_PROBE_MS, budget_ms, _remaining_ms(deadline, budget_ms)),
            )
        except Exception as exc:  # noqa: BLE001 - late commit is common on 1 CPU
            nav_error = exc
        title, html = _wait_ready(page, deadline, need_token)
        if time.monotonic() >= deadline:
            # A blocking CDP call can land just past the poll boundary.
            raise RenderTimeout("Obscura 渲染超过 12s 总预算")
        final_url = page.url or url
        body = html.encode("utf-8")
        if nav_error is not None and len(body) < 2000:
            raise nav_error
    except (RenderTimeout, RenderUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - navigation/render failure
        _record_failure(f"render: {type(exc).__name__}: {str(exc)[:160]}")
        if type(exc).__name__ == "TimeoutError":
            raise RenderTimeout("Obscura 渲染超时") from exc
        raise RenderUnavailable(f"Obscura 渲染失败: {type(exc).__name__}") from exc
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:  # noqa: BLE001 - context already gone
                pass

    elapsed_ms = int((time.monotonic() - started) * 1000)
    with _lock:
        _stats["renders"] += 1
        _stats["last_url_host"] = host
        _stats["last_ms"] = elapsed_ms
        _stats["last_error"] = ""
    return {
        "title": title,
        "final_url": final_url,
        "html_bytes": len(body),
        "has_xsec_token": "xsec_token" in html,
        "elapsed_ms": elapsed_ms,
        "wait_ms": budget_ms,
    }


def render_page(url: str, wait_ms: Optional[int] = None) -> Dict[str, Any]:
    """Serialized render on the single Playwright owner thread."""
    if not enabled():
        raise RenderUnavailable("ENABLE_OBSCURA!=1")
    before = _artifacts_dirs()
    future = _worker().submit(_render_page, url, wait_ms)
    try:
        # Allow the internal 12s deadline plus the context/artifact cleanup;
        # timing out earlier leaves the worker busy and cascades into the next
        # request's budget.
        return future.result(timeout=TOTAL_BUDGET_S + 3.0)
    except FuturesTimeout as exc:
        _record_failure("render: total budget exceeded (queue)")
        raise RenderTimeout("Obscura 渲染超过 12s 总预算") from exc
    finally:
        _cleanup_artifacts(before)


def prewarm() -> bool:
    """Start the driver and CDP connection before the first request.

    Called from the app startup hook when ``ENABLE_OBSCURA=1``. Startup cost
    must not land inside the first render's 12s budget.
    """
    if not enabled():
        return False
    deadline = time.monotonic() + max(3.0, TOTAL_BUDGET_S - 2.0)
    try:
        future = _worker().submit(_ensure_browser, deadline)
        future.result(timeout=max(3.0, TOTAL_BUDGET_S - 1.0))
    except Exception as exc:  # noqa: BLE001 - startup stays alive, request retries
        logger.warning("obscura prewarm failed: %s", type(exc).__name__)
        return False
    with _lock:
        _stats["prewarms"] += 1
    return True


async def render_html(url: str, wait_ms: Optional[int] = None) -> Dict[str, Any]:
    """Async wrapper; the blocking render runs off the event loop."""
    return await asyncio.to_thread(render_page, url, wait_ms)


async def prewarm_html() -> bool:
    return await asyncio.to_thread(prewarm)
