#!/usr/bin/env python3
"""Independent QA unit checks for l1-parser-core (read-only against implementation).

Run: .venv/bin/python docs/beacon/v0.1.0/features/l1-parser-core/evidence/qa/qa_unit_checks.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(ROOT / "container"))

from app.contract import MAX_ITEMS, MAX_RESPONSE_BYTES, finalize_success, normalize_items  # noqa: E402
from app.contract import ParseItem, ParseResult  # noqa: E402
from app.errors import ERROR_SPECS, error_envelope  # noqa: E402
from app.parsers import douyin, xhs  # noqa: E402
from app.routes_parse import _allowed_host, _platform_for  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


# 1. Realistic f2 raw aweme_detail: each image has url_list with 3 CDN mirrors.
raw_detail = {
    "aweme_detail": {
        "desc": "三图笔记",
        "images": [
            {"url_list": [f"https://p{i}.douyinpic.com/img{j}.jpeg" for i in (3, 6, 9)], "width": 1080, "height": 1440}
            for j in range(3)
        ],
        "video": {},
    }
}


class FakeFilter:
    def __init__(self, data):
        self.data = data

    def _to_raw(self):
        return self.data


mapped = douyin._detail_mapping(FakeFilter(raw_detail))
page_images = len(mapped["images"])
urls = douyin._image_urls(mapped.get("images"))
check(
    "douyin note: one item per page image",
    len(urls) == page_images,
    f"page images={page_images}, extracted items={len(urls)}",
)

# 2. 100-item cap + truncated flag.
raw_items = [{"type": "image", "remoteUrl": f"https://p3.douyinpic.com/{i}.jpeg"} for i in range(120)]
items, truncated = normalize_items(raw_items, "douyin", "note")
check("120 items -> 100", len(items) == MAX_ITEMS and truncated is True, f"len={len(items)} truncated={truncated}")

items100, truncated100 = normalize_items(raw_items[:100], "douyin", "note")
check("exactly 100 items -> truncated=false", len(items100) == 100 and truncated100 is False)

# 3. Byte cap.
big = [
    {"type": "image", "remoteUrl": "https://p3.douyinpic.com/" + "x" * 20000 + f"/{i}.jpeg"}
    for i in range(100)
]
big_items, big_truncated = normalize_items(big, "douyin", "note")
result = ParseResult(
    ok=True, platform="douyin", content_type="note", source_url="https://www.douyin.com/note/1",
    resolved_url="https://www.douyin.com/note/1", title="t", item_count=len(big_items),
    elapsed_ms=1, items=big_items,
)
data, payload = finalize_success(result)
check(
    "serialized body <= 1024000",
    len(data) <= MAX_RESPONSE_BYTES,
    f"bytes={len(data)} items={len(payload['items'])} truncated={payload.get('truncated')}",
)
check("cap keeps item_count == len(items)", payload["item_count"] == len(payload["items"]))

# 4. xhs note seam: webp URL preserved, needs_transcode true.
note = xhs._note_payload(
    {"title": "n", "items": [{"url": "https://sns-img.xhscdn.com/a.webp?xsec_token=t", "width": 1, "height": 2}]}
)
check(
    "xhs note keeps webp URL and marks transcode",
    note["items"][0]["remoteUrl"].endswith(".webp?xsec_token=t") and note["items"][0]["needs_transcode"] is True,
)

# 5. Error code table exactly as truth.md.
expected = {
    "INVALID_URL": (400, False),
    "INVALID_REQUEST": (400, False),
    "UNSUPPORTED_PLATFORM": (400, False),
    "SHORTLINK_FAIL": (422, True),
    "COOKIE_EXPIRED": (503, True),
    "PARSE_FAILED": (502, True),
    "TIMEOUT": (504, True),
    "RATE_LIMITED": (429, True),
}
got = {code: (spec.http_status, spec.retryable) for code, spec in ERROR_SPECS.items()}
check("eight error codes and HTTP/retryable match truth", got == expected, json.dumps(got, ensure_ascii=False))

# 6. Host whitelist: allowed subdomains, rejected lookalikes.
allowed = ["douyin.com", "www.douyin.com", "v.douyin.com", "xhslink.com", "www.xiaohongshu.com"]
rejected = ["evil-douyin.com", "douyin.com.evil.com", "notdouyin.com", "bilibili.com", "douyin.co"]
check("whitelist allows target domains", all(_allowed_host(h) for h in allowed), ",".join(allowed))
check("whitelist rejects lookalike domains", not any(_allowed_host(h) for h in rejected), ",".join(rejected))
check(
    "platform mapping",
    _platform_for("v.douyin.com") == "douyin"
    and _platform_for("xhslink.com") == "xhs"
    and _platform_for("www.bilibili.com") is None,
)

# 7. Error envelope shape + schema.
envelope = error_envelope("SHORTLINK_FAIL", elapsed_ms=7)
check(
    "error envelope ok/items/resolved_url/elapsed_ms",
    envelope["ok"] is False
    and envelope["items"] == []
    and envelope["resolved_url"] == ""
    and isinstance(envelope["elapsed_ms"], int)
    and envelope["error"]["retryable"] is True,
)

try:
    import jsonschema
    schema = json.loads((ROOT / "contract" / "parse_response.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(envelope, schema)
    jsonschema.validate(json.loads(data.decode("utf-8")), schema)
    check("schema validates error and success envelopes", True)
except Exception as exc:  # noqa: BLE001
    check("schema validates error and success envelopes", False, f"{type(exc).__name__}: {exc}")

print(f"SUMMARY failures={len(failures)}")
if failures:
    print("FAILED:", ", ".join(failures))
sys.exit(1 if failures else 0)
