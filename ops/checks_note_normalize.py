#!/usr/bin/env python3
"""Deterministic TASK-006 checks for D1: one item per image.

Uses f2-0.0.1.7 PostDetailFilter semantics: each image contributes only its
url_list[0]. No real network samples and no media downloads are involved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from container.app.contract import MAX_ITEMS, normalize_items  # noqa: E402
from container.app.parsers.douyin import _note_payload  # noqa: E402


def _images(count: int) -> list:
    return [
        {
            "url_list": [
                f"https://cdn-a.example.com/img{i}.webp",
                f"https://cdn-b.example.com/img{i}.webp",
                f"https://cdn-c.example.com/img{i}.webp",
            ]
        }
        for i in range(count)
    ]


def main() -> int:
    failures: list = []

    three = _note_payload({"desc": "3x3", "images": _images(3)})
    items, truncated = normalize_items(three["items"], "douyin", "note")
    urls = [item.remoteUrl for item in items]
    print("case=3x3-mirrors")
    print(f"item_count={len(items)} truncated={truncated}")
    print("remoteUrls=" + json.dumps(urls, ensure_ascii=False))
    expected = [f"https://cdn-a.example.com/img{i}.webp" for i in range(3)]
    if len(items) != 3:
        failures.append(f"3x3 expected 3 items, got {len(items)}")
    if truncated:
        failures.append("3x3 must not be truncated")
    if urls != expected:
        failures.append("each image must use url_list[0]")
    if any(item.type != "image" for item in items):
        failures.append("all 3x3 items must be type=image")

    many = _note_payload({"desc": "120", "images": _images(120)})
    many_items, many_truncated = normalize_items(many["items"], "douyin", "note")
    print("case=120-images")
    print(f"item_count={len(many_items)} truncated={many_truncated}")
    if len(many_items) != MAX_ITEMS:
        failures.append(f"120 images must cap at {MAX_ITEMS}, got {len(many_items)}")
    if not many_truncated:
        failures.append("120 images must set truncated=true")

    if failures:
        print("RESULT=FAIL")
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
