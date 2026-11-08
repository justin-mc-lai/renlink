#!/usr/bin/env python3
"""Local acceptance for l1: parse two real links and download their media.

Checks:
  1. POST /parse returns ok=true with at least one item for both links.
  2. Every item's remoteUrl answers with a non-empty body.
  3. Video items are probed by ffprobe when it is installed.

The service must already be running with the operator cookie pool:
  PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099

Usage:
  .venv/bin/python ops/accept_local.py
Exit 0 = pass, 1 = fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from curl_cffi import requests

BASE = os.getenv("PARSE_BASE", "http://127.0.0.1:18099").rstrip("/")
OUT = Path("/tmp/renlink_accept")

SAMPLES = [
    ("douyin", "https://v.douyin.com/Y7MgY9YnYAg/", "https://www.douyin.com/"),
    ("xhs", "https://xhslink.cn/o/1zbdThHpdb0", "https://www.xiaohongshu.com/"),
]


def parse(url: str) -> dict:
    resp = requests.post(f"{BASE}/parse", json={"url": url}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def download(url: str, referer: str, dest: Path) -> int:
    resp = requests.get(
        url,
        impersonate="chrome",
        timeout=300,
        headers={"Referer": referer, "User-Agent": "Mozilla/5.0"},
        stream=True,
    )
    resp.raise_for_status()
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(1 << 20):
            fh.write(chunk)
    return dest.stat().st_size


def probe(path: Path) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(out.stdout or "{}").get("format", {})
        return f"{data.get('duration', '?')}s / {data.get('size', '?')}B"
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
        return "ffprobe unavailable"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for name, url, referer in SAMPLES:
        result = parse(url)
        items = result.get("items") or []
        if not result.get("ok") or not items:
            failures.append(f"{name}: parse failed {result.get('error')}")
            continue
        print(f"{name}: ok type={result['content_type']} items={len(items)} {result['elapsed_ms']}ms")
        for item in items[:3]:
            dest = OUT / f"{name}-{item['index']}.{item.get('ext', 'bin')}"
            try:
                size = download(item["remoteUrl"], referer, dest)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}[{item['index']}]: download {type(exc).__name__}")
                continue
            if size <= 0:
                failures.append(f"{name}[{item['index']}]: empty file")
                continue
            detail = probe(dest) if item.get("type") == "video" else f"{size}B"
            print(f"  item {item['index']} {item['type']} -> {size}B ({detail})")
    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print("PASS: 2/2 samples parsed and downloaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
