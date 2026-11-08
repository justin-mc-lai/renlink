#!/usr/bin/env python3
"""Independent QA re-verification (D1/D2 + contract) for l1-parser-core.

Drives the real FastAPI /parse route through TestClient with explicit test
doubles for the upstream parsers (no network, no real samples). This checks the
route -> contract -> cap path, not just a helper function.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

os.environ["PARSE_RATE_LIMIT_PER_MIN"] = "0"
os.environ["PARSE_UPSTREAM_DELAY_MS"] = "0"

ROOT = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
import jsonschema  # noqa: E402

from container.app import routes_parse  # noqa: E402
from container.app.errors import ApiError  # noqa: E402
from container.app.main import app  # noqa: E402
from container.app.parsers import douyin, xhs  # noqa: E402
from container.app.parsers.douyin import _note_payload as dy_note_payload  # noqa: E402
from container.app.parsers.xhs import _note_payload as xhs_note_payload  # noqa: E402
from container.app.session_bridge import CookieExpired  # noqa: E402

SCHEMA = json.loads((ROOT / "contract" / "parse_response.schema.json").read_text(encoding="utf-8"))
client = TestClient(app)

FAILS: list[str] = []
CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def post(body, raw: str | None = None):
    if raw is not None:
        return client.post("/parse", content=raw, headers={"content-type": "application/json"})
    return client.post("/parse", json=body)


def images(count: int) -> list:
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


async def fake_dy_note(url, cookie):
    return dy_note_payload({"desc": "3x3", "images": images(3)})


async def fake_dy_many(url, cookie):
    return dy_note_payload({"desc": "120", "images": images(120)})


async def fake_dy_fail(url, cookie):
    raise ApiError("PARSE_FAILED")


async def fake_xhs_note(url, cookie):
    return xhs_note_payload(
        {
            "title": "webp",
            "items": [
                {"remoteUrl": f"https://sns-img.example.com/note/{i}.webp?xsec_token=ABC&xsec_source=pc"}
                for i in range(3)
            ],
        }
    )


async def fake_xhs_many(url, cookie):
    return xhs_note_payload(
        {
            "title": "many",
            "items": [
                {"remoteUrl": f"https://sns-img.example.com/note/{i}.webp?xsec_token=ABC"}
                for i in range(120)
            ],
        }
    )


def validate_schema(body: dict, label: str) -> None:
    try:
        jsonschema.validate(body, SCHEMA)
        check(f"{label}:schema", True)
    except Exception as exc:  # noqa: BLE001
        check(f"{label}:schema", False, f"{type(exc).__name__}: {str(exc)[:200]}")


def main() -> int:
    # ---- D1: 3 images x 3 CDN mirrors through POST /parse ----
    routes_parse.get_cookie = lambda platform: "stub-cookie"
    douyin.parse = fake_dy_note
    r = post({"url": "https://www.douyin.com/note/1234567890123456"})
    body = r.json()
    items = body.get("items") or []
    urls = [i.get("remoteUrl") for i in items]
    expected = [f"https://cdn-a.example.com/img{i}.webp" for i in range(3)]
    check("D1:http200", r.status_code == 200, str(r.status_code))
    check("D1:item_count", body.get("item_count") == 3 and len(items) == 3, f"item_count={body.get('item_count')} len={len(items)}")
    check("D1:url_list0", urls == expected, json.dumps(urls, ensure_ascii=False))
    check("D1:all_image", all(i.get("type") == "image" for i in items), str([i.get("type") for i in items]))
    check("D1:index_contiguous", [i.get("index") for i in items] == [0, 1, 2])
    validate_schema(body, "D1")

    # ---- D1b: 120 images -> 100 + truncated ----
    douyin.parse = fake_dy_many
    r = post({"url": "https://www.douyin.com/note/1234567890123457"})
    body = r.json()
    check("D1b:http200", r.status_code == 200, str(r.status_code))
    check("D1b:cap100", len(body.get("items") or []) == 100, str(len(body.get("items") or [])))
    check("D1b:truncated", body.get("truncated") is True, str(body.get("truncated")))
    check("D1b:item_count", body.get("item_count") == 100, str(body.get("item_count")))
    check("D1b:bytes", len(r.content) <= 1024000, str(len(r.content)))

    # ---- xhs note: webp URL kept, needs_transcode=true ----
    xhs.parse = fake_xhs_note
    r = post({"url": "https://www.xiaohongshu.com/explore/abc123def"})
    body = r.json()
    items = body.get("items") or []
    check("XHS:http200", r.status_code == 200, str(r.status_code))
    check("XHS:needs_transcode", all(i.get("needs_transcode") is True for i in items), str([i.get("needs_transcode") for i in items]))
    check("XHS:webp_kept", all(i.get("remoteUrl", "").endswith(".webp?xsec_token=ABC&xsec_source=pc") for i in items), str([i.get("remoteUrl") for i in items]))
    check("XHS:ext_webp", all(i.get("ext") == "webp" for i in items), str([i.get("ext") for i in items]))
    validate_schema(body, "XHS")

    xhs.parse = fake_xhs_many
    r = post({"url": "https://www.xiaohongshu.com/explore/abc123eee"})
    body = r.json()
    check("XHS120:cap100", len(body.get("items") or []) == 100 and body.get("truncated") is True, f"len={len(body.get('items') or [])} truncated={body.get('truncated')}")
    check("XHS120:bytes", len(r.content) <= 1024000, str(len(r.content)))

    # ---- D2: request body matrix ----
    matrix = [
        ({"url": 123}, "INVALID_REQUEST", "int"),
        ({"url": None}, "INVALID_REQUEST", "null"),
        ({"url": []}, "INVALID_REQUEST", "list"),
        ({"url": {}}, "INVALID_REQUEST", "object"),
        ({}, "INVALID_URL", "missing"),
        ({"url": ""}, "INVALID_URL", "empty"),
        ({"url": "   "}, "INVALID_URL", "whitespace"),
        ({"url": "not-a-url"}, "INVALID_URL", "not_a_url"),
        ({"url": "ftp://www.douyin.com/video/1"}, "INVALID_URL", "ftp"),
        ({"url": "https://www.douyin.com/" + "a" * 2100}, "INVALID_URL", "too_long"),
        ([1, 2], "INVALID_REQUEST", "body_list"),
    ]
    for payload, code, label in matrix:
        r = post(payload)
        b = r.json()
        got = (b.get("error") or {}).get("code")
        check(f"D2:{label}", r.status_code == 400 and got == code and b.get("ok") is False, f"http={r.status_code} code={got}")
        check(f"D2:{label}:envelope", b.get("items") == [] and isinstance(b.get("elapsed_ms"), int) and isinstance((b.get("error") or {}).get("retryable"), bool))

    r = post(None, raw="{not json")
    b = r.json()
    check("D2:bad_json", r.status_code == 400 and (b.get("error") or {}).get("code") == "INVALID_REQUEST", f"http={r.status_code}")

    r = post({"url": "https://v.douyin.com/XXXXXXX/", "cookie": "sessionid=1"})
    b = r.json()
    check("AC013:cookie_field", r.status_code == 400 and (b.get("error") or {}).get("code") == "INVALID_REQUEST", f"http={r.status_code}")
    check("AC013:no_echo", "sessionid=1" not in json.dumps(b), "response does not echo cookie")

    # ---- error envelope mapping through the route ----
    xhs.parse = fake_xhs_note  # ensure non-douyin path
    douyin.parse = fake_dy_fail
    r = post({"url": "https://www.douyin.com/video/1234567890123458"})
    b = r.json()
    check("PARSE_FAILED:502", r.status_code == 502 and (b.get("error") or {}).get("code") == "PARSE_FAILED" and (b.get("error") or {}).get("retryable") is True, f"http={r.status_code}")

    routes_parse.get_cookie = lambda platform: (_ for _ in ()).throw(CookieExpired("x"))
    r = post({"url": "https://www.douyin.com/video/1234567890123459"})
    b = r.json()
    check("COOKIE_EXPIRED:503", r.status_code == 503 and (b.get("error") or {}).get("code") == "COOKIE_EXPIRED" and b.get("items") == [], f"http={r.status_code}")
    routes_parse.get_cookie = lambda platform: "stub-cookie"

    async def fail_shortlink(url, timeout_s=3.0):
        raise ApiError("SHORTLINK_FAIL")

    routes_parse.expand_shortlink = fail_shortlink
    r = post({"url": "https://v.douyin.com/0000000/"})
    b = r.json()
    check("SHORTLINK_FAIL:422", r.status_code == 422 and (b.get("error") or {}).get("code") == "SHORTLINK_FAIL" and b.get("resolved_url") == "", f"http={r.status_code} resolved={b.get('resolved_url')!r}")

    # ---- whitelist host matcher ----
    allowed = ["douyin.com", "www.douyin.com", "v.douyin.com", "xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com", "s.xhslink.com"]
    blocked = ["evil-douyin.com", "douyin.com.evil.com", "notdouyin.com", "xiaohongshu.com.cn", "evil-xhslink.com"]
    check("WL:allowed", all(routes_parse._allowed_host(h) for h in allowed), str(allowed))
    check("WL:blocked", not any(routes_parse._allowed_host(h) for h in blocked), str(blocked))

    # ---- log redaction ----
    stream = []

    class _Capture(logging.Handler):
        def emit(self, record):
            stream.append(record.getMessage())

    handler = _Capture()
    f2_logger = logging.getLogger("f2")
    f2_logger.addHandler(handler)
    f2_logger.setLevel(logging.INFO)
    f2_logger.info("GET https://www.douyin.com/x?msToken=SECRET_TOKEN&a_bogus=SECRET_BOGUS&ok=1")
    text = "\n".join(stream)
    f2_logger.removeHandler(handler)
    check("LOG:msToken_redacted", "SECRET_TOKEN" not in text and "[REDACTED]" in text, text[:160])
    check("LOG:a_bogus_redacted", "SECRET_BOGUS" not in text, text[:160])

    print("SUMMARY checks=%d fails=%d" % (len(CHECKS), len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
