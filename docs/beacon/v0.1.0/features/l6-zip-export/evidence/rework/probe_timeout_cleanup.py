"""Runtime probe: timeout while the packing worker is mid-archive.

Run with the project venv; prints the 504, the /tmp residue at that moment
and again after the worker thread has finished.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path("/Users/apple/Developer/Personal/renlink")
work = Path(tempfile.mkdtemp(prefix="renlink-l6-probe-"))
os.environ["STAGE_STORE"] = "local"
os.environ["STAGE_LOCAL_DIR"] = str(work / "store")
os.environ.pop("ZIP_FAKE_DELAY_MS", None)
sys.path.insert(0, str(REPO / "container"))

import httpx  # noqa: E402

from app import stage_cache, zipkit  # noqa: E402
from app.main import app  # noqa: E402

store_root = work / "store"
task_id = stage_cache.remember(
    {
        "ok": True,
        "platform": "xhs",
        "content_type": "note",
        "source_url": "https://www.xiaohongshu.com/explore/6a0000000000000000000001",
        "resolved_url": "https://www.xiaohongshu.com/explore/6a0000000000000000000001",
        "title": "probe",
        "item_count": 2,
        "elapsed_ms": 1,
        "items": [
            {"index": 0, "type": "image", "remoteUrl": "https://x/0.jpg", "ext": "jpg"},
            {"index": 1, "type": "image", "remoteUrl": "https://x/1.jpg", "ext": "jpg"},
        ],
    }
)
content_id = "6a0000000000000000000001"
for index, data in ((0, b"probe-zero"), (1, b"probe-one!")):
    path = store_root / "l3" / content_id / "{0}.jpg".format(index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    stage_cache.put_object(
        "xhs",
        content_id,
        index,
        "cloud://local/l3/{0}/{1}.jpg".format(content_id, index),
        "image",
        "jpg",
        len(data),
    )


def residue() -> list:
    return sorted(glob.glob("/tmp/renlink-zip-*"))


started_at: dict = {}
finished_at: dict = {}
real_pack = zipkit._pack_sync


def timed_pack(entries, store, scope):
    started_at["t"] = time.monotonic()
    try:
        return real_pack(entries, store, scope)
    finally:
        finished_at["t"] = time.monotonic()


zipkit._pack_sync = timed_pack  # type: ignore[assignment]

os.environ["ZIP_FAKE_PACK_DELAY_MS"] = "3000"
os.environ["ZIP_TIMEOUT_S"] = "1"

async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe") as client:
        before = residue()
        print("tmp residue before:", before)

        t0 = time.monotonic()
        pending = asyncio.create_task(client.post("/zip", json={"task_id": task_id}))
        await asyncio.sleep(0.5)
        print("tmp residue mid-pack (t=500ms):", residue())
        response = await pending
        at_504 = time.monotonic()

        print("http_status:", response.status_code)
        print("body:", json.dumps(response.json(), ensure_ascii=False, sort_keys=True))
        print("elapsed_ms_at_response:", int((at_504 - t0) * 1000))
        print("worker_started:", "t" in started_at)
        print("worker_finished_at_504:", finished_at.get("t") is not None)
        print("tmp residue at 504:", residue())

        while time.monotonic() - t0 < 4.2:
            await asyncio.sleep(0.1)
        print("worker_finished_after_wait:", finished_at.get("t") is not None)
        print("tmp residue after worker finished:", residue())

        os.environ.pop("ZIP_FAKE_PACK_DELAY_MS", None)
        retry = await client.post("/zip", json={"task_id": task_id})
        print("retry_status:", retry.status_code)
        print("retry_body:", json.dumps(retry.json(), sort_keys=True))
        print("tmp residue after retry:", residue())
        print(
            "uploaded_objects:",
            [p.name for p in (store_root / "l6" / task_id).glob("*.zip")],
        )

        assert response.status_code == 504
        assert response.json()["error"]["code"] == "TIMEOUT"
        assert "fileID" not in response.json()
        assert finished_at.get("t") is None or finished_at["t"] > at_504
        assert residue() == before
        assert retry.status_code == 200


asyncio.run(main())
print("PROBE_OK")
