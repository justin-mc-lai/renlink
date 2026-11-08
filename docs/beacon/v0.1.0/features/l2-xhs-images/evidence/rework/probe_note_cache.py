"""Runtime probe: /parse twice on one note URL, cache + counters + log fields."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

REPO = Path("/Users/apple/Developer/Personal/renlink")
NOTE_ID = "6a0000000000000000000010"
URL = "https://www.xiaohongshu.com/explore/{0}?xsec_token=tok-010".format(NOTE_ID)

work = Path(tempfile.mkdtemp(prefix="renlink-l2-probe-"))
page = {
    "note": {
        "noteDetailMap": {
            NOTE_ID: {
                "note": {
                    "title": "probe",
                    "imageList": [
                        {"urlDefault": "https://sns-img-qc.xhscdn.com/j.webp"},
                        {"urlDefault": "https://sns-img-qc.xhscdn.com/k.webp"},
                    ],
                }
            }
        }
    }
}
html = (
    "<html><script>window.__INITIAL_STATE__="
    + json.dumps(page, ensure_ascii=False)
    + ";</script></html>"
)
(work / "page.html").write_text(html, encoding="utf-8")
(work / "stub.json").write_text(
    json.dumps({URL: {"status": 200, "body_file": str(work / "page.html")}}),
    encoding="utf-8",
)
os.environ["XHS_NOTE_HTTP_STUB"] = str(work / "stub.json")
os.environ["XHS_COOKIE"] = "web_session=probe"
os.environ["PARSE_XHS_SKIP_YTDLP"] = "1"
os.environ.pop("XHS_NOTE_CACHE_TTL_S", None)
sys.path.insert(0, str(REPO / "container"))

import httpx  # noqa: E402

from app.main import app  # noqa: E402
from app.parsers import xhs  # noqa: E402

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
logging.getLogger("renlink.xhs").addHandler(handler)
logging.getLogger("renlink.xhs").setLevel(logging.INFO)

calls: list = []
real_fetch = xhs._fetch_note


async def counting_fetch(url: str, cookie: str) -> tuple:
    calls.append(url)
    return await real_fetch(url, cookie)


xhs._fetch_note = counting_fetch  # type: ignore[assignment]


def show(label: str, response: httpx.Response) -> None:
    body = response.json()
    print(label, "status:", response.status_code)
    print(label, "ok:", body.get("ok"), "item_count:", body.get("item_count"))
    print(
        label,
        "remoteUrls:",
        [item.get("remoteUrl") for item in body.get("items") or []],
    )


async def main() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://probe"
    ) as client:
        xhs.reset_cache()
        calls.clear()
        first = await client.post("/parse", json={"url": URL})
        second = await client.post("/parse", json={"url": URL})
        show("first", first)
        show("second", second)
        print("upstream_fetch_calls_with_default_ttl:", len(calls))
        print("counters_with_default_ttl:", json.dumps(xhs.counters(), sort_keys=True))
        assert len(calls) == 1
        assert first.json()["items"] == second.json()["items"]

        xhs.reset_cache()
        calls.clear()
        os.environ["XHS_NOTE_CACHE_TTL_S"] = "0"
        await client.post("/parse", json={"url": URL})
        await client.post("/parse", json={"url": URL})
        print("upstream_fetch_calls_with_ttl_0:", len(calls))
        print("counters_with_ttl_0:", json.dumps(xhs.counters(), sort_keys=True))
        assert len(calls) == 2
        os.environ.pop("XHS_NOTE_CACHE_TTL_S", None)

        print("NOTE_CACHE_PROBE_OK")


asyncio.run(main())
