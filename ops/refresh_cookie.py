#!/usr/bin/env python3
"""Operator cookie-pool refresh (l4 seam, local).

Opens each platform in headless Chromium with the current jar, waits for the
security cookies (UIFID / UIFID_TEMP for Douyin, web_session for XHS), then
rewrites ~/.config/renlink/cookies.env with the full jar (mode 0600).

Cookies are never printed. Run it again whenever /health reports expired.

Usage:
  .venv/bin/python ops/refresh_cookie.py            # both platforms
  .venv/bin/python ops/refresh_cookie.py douyin     # one platform
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ENV_PATH = Path.home() / ".config" / "renlink" / "cookies.env"

PLATFORMS = {
    "douyin": {
        "url": "https://www.douyin.com/",
        "domain": "douyin.com",
        "need": ("UIFID|UIFID_TEMP", "s_v_web_id"),
    },
    "xhs": {
        "url": "https://www.xiaohongshu.com/",
        "domain": "xiaohongshu.com",
        "need": ("web_session",),
    },
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip("'\"")
    return out


def jar_to_header(cookies: list[dict], domain: str) -> str:
    pairs = [
        f"{c['name']}={c['value']}"
        for c in cookies
        if c.get("value") and domain in (c.get("domain") or "")
    ]
    return "; ".join(pairs)


def main() -> int:
    targets = sys.argv[1:] or list(PLATFORMS)
    unknown = [t for t in targets if t not in PLATFORMS]
    if unknown:
        print(f"unknown platform: {unknown}", file=sys.stderr)
        return 2

    env = load_env()
    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        for name in targets:
            spec = PLATFORMS[name]
            ctx = browser.new_context(user_agent=UA, locale="zh-CN")
            seed = []
            for pair in env.get(f"{name.upper()}_COOKIE", "").split(";"):
                if "=" not in pair:
                    continue
                key, value = pair.strip().split("=", 1)
                if not key or not value:
                    continue
                seed.append({
                    "name": key,
                    "value": value,
                    "domain": "." + spec["domain"],
                    "path": "/",
                    "expires": -1,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                })
            if seed:
                try:
                    ctx.add_cookies(seed)
                except Exception as exc:  # noqa: BLE001 - stale jar is not fatal
                    print(f"{name}: seed skipped ({type(exc).__name__})")
            page = ctx.new_page()
            try:
                page.goto(spec["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(9000)
            except Exception as exc:  # noqa: BLE001 - network variance is expected
                print(f"{name}: goto failed ({type(exc).__name__})")
            all_cookies = ctx.cookies()
            header = jar_to_header(all_cookies, spec["domain"])
            names = {part.strip().split("=", 1)[0] for part in header.split(";") if "=" in part}
            missing = [n for n in spec["need"] if not any(alt in names for alt in n.split("|"))]
            if missing or not header:
                failed.append(name)
                print(f"{name}: missing {missing or 'all cookies'}")
            else:
                env[f"{name.upper()}_COOKIE"] = header
                print(f"{name}: ok ({len(names)} cookies)")
            ctx.close()
        browser.close()

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as fh:
        for key in ("DOUYIN_COOKIE", "XHS_COOKIE"):
            if key in env:
                fh.write(f"{key}={env[key]!r}\n")
    os.chmod(ENV_PATH, 0o600)
    print(f"wrote {ENV_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
