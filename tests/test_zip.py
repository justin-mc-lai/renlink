"""l6 /zip behavior tests: success, subset, idempotency, expiry, size caps,
store readiness, failure cleanup and timeout."""

from __future__ import annotations

import glob
import hashlib
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import stage_cache, zipkit
from app.main import app

NOTE_URL = "https://www.xiaohongshu.com/explore/6af04386000000001500d626"
CONTENT_ID = "6af04386000000001500d626"
ENV_NAMES = (
    "STAGE_STORE",
    "STAGE_LOCAL_DIR",
    "STAGE_TASK_TTL_S",
    "STAGE_OBJECT_TTL_S",
    "COS_BUCKET",
    "COS_REGION",
    "COS_ENDPOINT",
    "COS_SECRET_ID",
    "COS_SECRET_KEY",
    "COS_SESSION_TOKEN",
    "COS_CREDENTIAL_URL",
    "ZIP_MAX_IMAGES",
    "ZIP_MAX_BYTES",
    "ZIP_TIMEOUT_S",
    "ZIP_CACHE_TTL_S",
    "ZIP_TMP_PREFIX",
    "ZIP_FAKE_DELAY_MS",
    "ZIP_FAKE_PACK_DELAY_MS",
    "ZIP_FAULT_INJECT",
)


@pytest.fixture(autouse=True)
def zip_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stage_cache.clear()
    zipkit.clear()
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STAGE_STORE", "local")
    monkeypatch.setenv("STAGE_LOCAL_DIR", str(tmp_path / "store"))
    yield tmp_path
    stage_cache.clear()
    zipkit.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def item(index: int, item_type: str = "image", ext: str = "jpg") -> dict:
    return {
        "index": index,
        "type": item_type,
        "remoteUrl": "https://sns-img-qc.xhscdn.com/{0}.{1}".format(index, ext),
        "ext": ext,
        "cover": "",
        "width": None,
        "height": None,
        "needs_transcode": item_type == "image",
    }


def remember(items: list) -> str:
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


def stage_image(root: Path, index: int, ext: str, data: bytes) -> None:
    path = root / "l3" / CONTENT_ID / "{0}.{1}".format(index, ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    stage_cache.put_object(
        "xhs",
        CONTENT_ID,
        index,
        "cloud://local/l3/{0}/{1}.{2}".format(CONTENT_ID, index, ext),
        "image",
        ext,
        len(data),
    )


def zip_residue() -> set:
    return {path for path in glob.glob("/tmp/renlink-zip-*") if Path(path).is_file()}


def stored_zip(root: Path, file_id: str) -> Path:
    return root / file_id.removeprefix("cloud://local/")


def test_zip_all_staged_images(client: TestClient, zip_env: Path) -> None:
    root = zip_env / "store"
    before = zip_residue()
    stage_image(root, 0, "jpg", b"image-zero")
    stage_image(root, 1, "png", b"image-one!")
    stage_image(root, 2, "webp", b"image-two!!")
    task_id = remember([item(0, ext="jpg"), item(1, ext="png"), item(2, ext="webp")])

    response = client.post("/zip", json={"task_id": task_id})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ok", "fileID", "bytes", "count"}
    assert body["ok"] is True
    assert body["count"] == 3
    assert body["fileID"].startswith("cloud://local/l6/{0}/".format(task_id))
    zip_path = stored_zip(root, body["fileID"])
    assert zip_path.is_file()
    assert zip_path.stat().st_size == body["bytes"]
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        assert [info.filename for info in infos] == [
            "000.jpg",
            "001.png",
            "002.webp",
        ]
        for info in infos:
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED
        assert archive.read("000.jpg") == b"image-zero"
        assert archive.read("001.png") == b"image-one!"
        assert archive.read("002.webp") == b"image-two!!"
    assert len(response.content) <= 1024000
    assert zip_residue() == before


def test_zip_subset_dedup_keeps_index_order(client: TestClient, zip_env: Path) -> None:
    root = zip_env / "store"
    for index in range(4):
        stage_image(root, index, "jpg", "img-{0}".format(index).encode())
    task_id = remember([item(index) for index in range(4)])

    response = client.post("/zip", json={"task_id": task_id, "indexes": [3, 1, 3]})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    with zipfile.ZipFile(stored_zip(root, body["fileID"])) as archive:
        assert archive.namelist() == ["001.jpg", "003.jpg"]


def test_zip_unknown_task_expired(client: TestClient) -> None:
    response = client.post("/zip", json={"task_id": "st_" + "0" * 24})

    body = response.json()
    assert response.status_code == 410
    assert body["error"]["code"] == "STAGE_EXPIRED"
    assert body["error"]["retryable"] is False
    assert "fileID" not in body
    assert "cloud://" not in response.text


def test_zip_task_ttl_expiry(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    monkeypatch.setenv("STAGE_TASK_TTL_S", "1")
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0)])
    time.sleep(1.1)

    response = client.post("/zip", json={"task_id": task_id})

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "STAGE_EXPIRED"


def test_zip_too_many_images(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZIP_MAX_IMAGES", "2")
    root = zip_env / "store"
    for index in range(3):
        stage_image(root, index, "jpg", b"img")
    task_id = remember([item(index) for index in range(3)])

    response = client.post("/zip", json={"task_id": task_id})

    body = response.json()
    assert response.status_code == 413
    assert body["error"]["code"] == "TOO_LARGE"
    assert body["error"]["retryable"] is False
    assert "fileID" not in body
    assert not (root / "l6" / task_id).exists()


def test_zip_too_large_source_bytes(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZIP_MAX_BYTES", "4")
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"0123456789")
    task_id = remember([item(0)])

    response = client.post("/zip", json={"task_id": task_id})

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_LARGE"


def test_zip_not_ready_without_cos_credentials(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0)])
    monkeypatch.setenv("STAGE_STORE", "cos")
    before = zip_residue()

    response = client.post("/zip", json={"task_id": task_id})

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "ZIP_NOT_READY"
    assert body["error"]["retryable"] is True
    assert "fileID" not in body
    assert "cloud://" not in response.text
    assert zip_residue() == before


def test_zip_not_ready_when_local_dir_broken(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0)])
    blocked = zip_env / "blocked"
    blocked.write_bytes(b"not a directory")
    monkeypatch.setenv("STAGE_LOCAL_DIR", str(blocked))

    response = client.post("/zip", json={"task_id": task_id})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ZIP_NOT_READY"


def test_zip_idempotent_same_file_id(client: TestClient, zip_env: Path) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"one")
    stage_image(root, 1, "webp", b"two")
    task_id = remember([item(0, ext="jpg"), item(1, ext="webp")])

    first = client.post("/zip", json={"task_id": task_id})
    second = client.post("/zip", json={"task_id": task_id})

    assert first.status_code == second.status_code == 200
    assert first.json()["fileID"] == second.json()["fileID"]
    assert first.json()["bytes"] == second.json()["bytes"]
    assert first.json()["count"] == second.json()["count"]
    assert len(list((root / "l6" / task_id).glob("*.zip"))) == 1


def test_zip_stable_bytes_with_cache_disabled(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZIP_CACHE_TTL_S", "0")
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"stable")
    task_id = remember([item(0)])

    first = client.post("/zip", json={"task_id": task_id})
    zip_path = stored_zip(root, first.json()["fileID"])
    first_digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    second = client.post("/zip", json={"task_id": task_id})
    second_digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    assert first.status_code == second.status_code == 200
    assert first.json()["fileID"] == second.json()["fileID"]
    assert first_digest == second_digest


def test_zip_concurrent_same_key_packs_once(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"one")
    stage_image(root, 1, "jpg", b"two")
    task_id = remember([item(0), item(1)])
    calls = []
    real_pack = zipkit._pack_sync

    def counting_pack(entries, store, scope):
        calls.append(1)
        time.sleep(0.05)
        return real_pack(entries, store, scope)

    monkeypatch.setattr(zipkit, "_pack_sync", counting_pack)

    def call(_: int):
        return client.post("/zip", json={"task_id": task_id})

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(call, range(4)))

    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["fileID"] for response in responses}) == 1
    assert len(calls) == 1
    assert len(list((root / "l6" / task_id).glob("*.zip"))) == 1


def test_zip_staged_only_and_all_unstaged(
    client: TestClient, zip_env: Path
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"only-zero")
    task_id = remember([item(0), item(1), item(2)])

    mixed = client.post("/zip", json={"task_id": task_id, "indexes": [0, 1]})
    assert mixed.status_code == 200
    assert mixed.json()["count"] == 1

    unstaged = client.post("/zip", json={"task_id": task_id, "indexes": [1]})
    assert unstaged.status_code == 400
    assert unstaged.json()["error"]["code"] == "INVALID_REQUEST"
    assert "fileID" not in unstaged.json()


def test_zip_failure_cleans_temp_files(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0)])
    before = zip_residue()

    for fault in ("read", "write", "upload"):
        monkeypatch.setenv("ZIP_FAULT_INJECT", fault)
        response = client.post("/zip", json={"task_id": task_id})
        body = response.json()
        assert response.status_code == 502
        assert body["error"]["code"] == "ZIP_FAILED"
        assert body["error"]["retryable"] is True
        assert "fileID" not in body
        assert zip_residue() == before


def test_zip_timeout(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0)])
    before = zip_residue()
    monkeypatch.setenv("ZIP_FAKE_DELAY_MS", "2000")
    monkeypatch.setenv("ZIP_TIMEOUT_S", "1")

    response = client.post("/zip", json={"task_id": task_id})

    body = response.json()
    assert response.status_code == 504
    assert body["error"]["code"] == "TIMEOUT"
    assert body["error"]["retryable"] is True
    assert "fileID" not in body
    assert zip_residue() == before


def test_zip_timeout_during_pack_cleans_temp_files(
    client: TestClient, zip_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Timeout while the worker thread is inside the zip archive body."""
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img-zero")
    stage_image(root, 1, "jpg", b"img-one")
    task_id = remember([item(0), item(1)])
    before = zip_residue()
    monkeypatch.setenv("ZIP_FAKE_PACK_DELAY_MS", "1200")
    monkeypatch.setenv("ZIP_TIMEOUT_S", "1")

    response = client.post("/zip", json={"task_id": task_id})

    body = response.json()
    assert response.status_code == 504
    assert body["error"]["code"] == "TIMEOUT"
    assert body["error"]["retryable"] is True
    assert "fileID" not in body
    # Right when the 504 is returned every temp zip of this task is gone.
    assert zip_residue() == before

    # The worker thread is still running; it must not leave a file behind.
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and zip_residue() != before:
        time.sleep(0.05)
    time.sleep(0.3)
    assert zip_residue() == before

    # The release of the key lock follows the worker, so a retry is serialized
    # and still succeeds on its own (no duplicate in-flight packing).
    monkeypatch.delenv("ZIP_FAKE_PACK_DELAY_MS")
    retry = client.post("/zip", json={"task_id": task_id})
    assert retry.status_code == 200
    assert retry.json()["count"] == 2


def test_zip_invalid_requests(client: TestClient, zip_env: Path) -> None:
    root = zip_env / "store"
    stage_image(root, 0, "jpg", b"img")
    task_id = remember([item(0), item(1, item_type="video", ext="mp4")])
    cases = [
        {},
        {"task_id": "st_bad"},
        {"task_id": task_id, "indexes": []},
        {"task_id": task_id, "indexes": "1"},
        {"task_id": task_id, "indexes": [1.5]},
        {"task_id": task_id, "indexes": [-1]},
        {"task_id": task_id, "indexes": [99]},
        {"task_id": task_id, "indexes": [1]},
        {"task_id": task_id, "indexes": [0], "cookie": "a=b"},
    ]

    for payload in cases:
        response = client.post("/zip", json=payload)
        body = response.json()
        assert response.status_code == 400, payload
        assert body["error"]["code"] == "INVALID_REQUEST", payload
        assert body["error"]["retryable"] is False
        assert "fileID" not in body

    not_json = client.post(
        "/zip", content=b"not json", headers={"content-type": "application/json"}
    )
    assert not_json.status_code == 400
    assert not_json.json()["error"]["code"] == "INVALID_REQUEST"
