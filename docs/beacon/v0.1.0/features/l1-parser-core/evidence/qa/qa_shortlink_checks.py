#!/usr/bin/env python3
"""Independent QA check for shortlink: 3-hop cap, HEAD-first, GET header fallback."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(ROOT / "container"))

from app.errors import ApiError  # noqa: E402
from app.parsers import shortlink  # noqa: E402

calls: list[str] = []


class FakeResponse:
    def __init__(self, status_code: int = 302, location: str | None = None):
        self.status_code = status_code
        self.headers = {"location": location} if location else {}


class FakeStream:
    def __init__(self, response: FakeResponse):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        return False


class FakeClient:
    HEAD: dict[str, FakeResponse] = {}
    GET: dict[str, FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def head(self, url, headers=None):
        calls.append(f"HEAD {url}")
        return self.HEAD[url]

    def stream(self, method, url, headers=None):
        calls.append(f"{method} {url}")
        return FakeStream(self.GET[url])


shortlink.httpx.AsyncClient = FakeClient  # type: ignore[assignment]

failures: list[str] = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


# Chain A: exactly 3 redirects, lands on canonical page -> allowed.
FakeClient.HEAD = {
    "https://v.douyin.com/a/": FakeResponse(302, "https://v.douyin.com/b/"),
    "https://v.douyin.com/b/": FakeResponse(302, "https://v.douyin.com/c/"),
    "https://v.douyin.com/c/": FakeResponse(302, "https://www.douyin.com/video/1234567890"),
}
calls.clear()
resolved = asyncio.run(shortlink.expand_shortlink("https://v.douyin.com/a/"))
check("3 hops allowed", resolved == "https://www.douyin.com/video/1234567890", resolved)
check("HEAD requested first at every hop", calls and all(c.startswith("HEAD") for c in calls), "; ".join(calls))

# Chain B: 4 redirects, still a shortlink after 3 hops -> SHORTLINK_FAIL.
FakeClient.HEAD = {
    "https://v.douyin.com/a/": FakeResponse(302, "https://v.douyin.com/b/"),
    "https://v.douyin.com/b/": FakeResponse(302, "https://v.douyin.com/c/"),
    "https://v.douyin.com/c/": FakeResponse(302, "https://v.douyin.com/d/"),
}
calls.clear()
try:
    asyncio.run(shortlink.expand_shortlink("https://v.douyin.com/a/"))
    check("4 hops rejected", False, "no error raised")
except ApiError as exc:
    check("4 hops rejected", exc.code == "SHORTLINK_FAIL", exc.code)

# Chain C: HEAD answers 405 without Location -> GET header fallback is used.
FakeClient.HEAD = {"https://v.douyin.com/e/": FakeResponse(405)}
FakeClient.GET = {
    "https://v.douyin.com/e/": FakeResponse(302, "https://www.douyin.com/note/9876543210"),
}
calls.clear()
resolved = asyncio.run(shortlink.expand_shortlink("https://v.douyin.com/e/"))
check("HEAD 405 falls back to GET headers", resolved == "https://www.douyin.com/note/9876543210", " | ".join(calls))

print(f"SUMMARY failures={len(failures)}")
sys.exit(1 if failures else 0)
