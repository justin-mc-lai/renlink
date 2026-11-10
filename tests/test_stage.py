"""l3 /stage behavior tests: success, expiry, size cap, store readiness,
idempotency and temp-file cleanup."""

from __future__ import annotations

import glob
import io
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import stage_cache
from app.main import app

NOTE_URL = "https://www.xiaohongshu.com/explore/6af04386000000001500d626"
NOTE_ID = "6af04386000000001500d626"


class CountingHandler(SimpleHTTPRequestHandler):
    hits = 0

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        type(self).hits += 1
        super().do_GET()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture()
def media_server(tmp_path: Path) -> str:
    web = tmp_path / "web"
    web.mkdir()
    Image.new("RGB", (16, 16), (200, 30, 30)).save(web / "tiny.webp", "WEBP")
    Image.new("RGB", (16, 16), (30, 200, 30)).save(web / "tiny.jpg", "JPEG")
    (web / "big.bin").write_bytes(b"x" * 256)
    CountingHandler.hits = 0
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(CountingHandler, directory=str(web))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{0}".format(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def stage_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stage_cache.clear()
    for name in (
        "STAGE_STORE",
        "STAGE_LOCAL_DIR",
        "STAGE_TASK_TTL_S",
        "STAGE_OBJECT_TTL_S",
        "STAGE_MAX_VIDEO_BYTES",
        "STAGE_MAX_IMAGE_BYTES",
        "STAGE_TIMEOUT_S",
        "STAGE_FAKE_CONTENT_LENGTH",
        "STAGE_FAKE_DELAY_MS",
        "COS_BUCKET",
        "COS_REGION",
        "COS_ENDPOINT",
        "COS_SECRET_ID",
        "COS_SECRET_KEY",
        "COS_SESSION_TOKEN",
        "COS_CREDENTIAL_URL",
        "TENCENTCLOUD_SECRETID",
        "TENCENTCLOUD_SECRETKEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STAGE_STORE", "local")
    monkeypatch.setenv("STAGE_LOCAL_DIR", str(tmp_path / "store"))
    yield tmp_path
    stage_cache.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def image_item(index: int, url: str, ext: str, transcode: bool) -> dict:
    return {
        "index": index,
        "type": "image",
        "remoteUrl": url,
        "ext": ext,
        "cover": "",
        "width": None,
        "height": None,
        "needs_transcode": transcode,
    }


def remember(items: list[dict]) -> str:
    return stage_cache.remember(
        {
            "ok": True,
            "platform": "xhs",
            "content_type": "note",
            "source_url": NOTE_URL,
            "resolved_url": NOTE_URL,
            "title": "",
            "item_count": len(items),
            "elapsed_ms": 1,
            "items": items,
        }
    )


def tmp_residue() -> set[str]:
    return {path for path in glob.glob("/tmp/renlink-stage-*") if Path(path).is_file()}


def test_image_success_transcodes_webp_to_jpeg(
    client: TestClient, media_server: str, stage_env: Path
) -> None:
    before = tmp_residue()
    task_id = remember([image_item(0, media_server + "/tiny.webp", "webp", True)])

    response = client.post("/stage", json={"task_id": task_id, "index": 0})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ok", "fileID", "kind", "ext", "bytes"}
    assert body["ok"] is True
    assert body["kind"] == "image"
    assert body["ext"] == "jpg"
    assert body["fileID"].startswith("cloud://local/l3/{0}/".format(NOTE_ID))
    stored = stage_env / "store" / body["fileID"].removeprefix("cloud://local/")
    data = stored.read_bytes()
    assert len(data) == body["bytes"]
    assert data[:3] == b"\xff\xd8\xff"
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG"
    assert tmp_residue() == before


def test_unknown_task_expired(client: TestClient) -> None:
    response = client.post("/stage", json={"task_id": "st_" + "0" * 24, "index": 0})
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "STAGE_EXPIRED"


def test_task_ttl_expiry(
    client: TestClient, media_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STAGE_TASK_TTL_S", "1")
    task_id = remember([image_item(0, media_server + "/tiny.jpg", "jpg", False)])
    time.sleep(1.1)
    response = client.post("/stage", json={"task_id": task_id, "index": 0})
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "STAGE_EXPIRED"


def test_too_large_rejected(
    client: TestClient,
    media_server: str,
    monkeypatch: pytest.MonkeyPatch,
    stage_env: Path,
) -> None:
    monkeypatch.setenv("STAGE_MAX_IMAGE_BYTES", "10")
    before = tmp_residue()
    task_id = remember([image_item(0, media_server + "/big.bin", "jpg", False)])

    response = client.post("/stage", json={"task_id": task_id, "index": 0})

    body = response.json()
    assert response.status_code == 413
    assert body["error"]["code"] == "TOO_LARGE"
    assert "fileID" not in body
    assert tmp_residue() == before
    assert not (stage_env / "store" / "l3" / NOTE_ID).exists()


def test_store_not_ready_hides_cloud_id(
    client: TestClient, media_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STAGE_STORE", "cos")
    task_id = remember([image_item(0, media_server + "/tiny.jpg", "jpg", False)])

    response = client.post("/stage", json={"task_id": task_id, "index": 0})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STAGE_NOT_READY"
    assert "cloud://" not in response.text


def test_idempotent_second_call_skips_download(
    client: TestClient, media_server: str, stage_env: Path
) -> None:
    task_id = remember([image_item(0, media_server + "/tiny.jpg", "jpg", False)])

    first = client.post("/stage", json={"task_id": task_id, "index": 0})
    second = client.post("/stage", json={"task_id": task_id, "index": 0})

    assert first.status_code == second.status_code == 200
    assert first.json()["fileID"] == second.json()["fileID"]
    assert CountingHandler.hits == 1
    stored = stage_env / "store" / first.json()["fileID"].removeprefix("cloud://local/")
    assert stored.stat().st_size == first.json()["bytes"]


def test_failure_cleans_temp_files(
    client: TestClient, media_server: str
) -> None:
    before = tmp_residue()
    task_id = remember([image_item(0, media_server + "/missing.jpg", "jpg", False)])

    response = client.post("/stage", json={"task_id": task_id, "index": 0})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STAGE_FAILED"
    assert tmp_residue() == before


def test_cookie_field_rejected(client: TestClient) -> None:
    response = client.post(
        "/stage", json={"task_id": "st_" + "0" * 24, "index": 0, "cookie": "a=b"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_bad_index_is_not_retryable(client: TestClient, media_server: str) -> None:
    task_id = remember([image_item(0, media_server + "/tiny.jpg", "jpg", False)])
    response = client.post("/stage", json={"task_id": task_id, "index": 5})
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "STAGE_FAILED"
    assert body["error"]["retryable"] is False


def test_stage_file_streams_stored_object(
    client: TestClient, media_server: str, stage_env: Path
) -> None:
    task_id = remember([image_item(0, media_server + "/tiny.jpg", "jpg", False)])
    staged = client.post("/stage", json={"task_id": task_id, "index": 0}).json()

    response = client.get("/stage/file", params={"file_id": staged["fileID"]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert len(response.content) == staged["bytes"]


def test_stage_file_rejects_non_cloud_id(client: TestClient) -> None:
    response = client.get("/stage/file", params={"file_id": "/etc/passwd"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
