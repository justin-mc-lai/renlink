"""l4 session pool, freshness, egress injection, health and redaction tests."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import egress, session_bridge
from app.main import app

DOUYIN_URL = "https://www.douyin.com/video/7705367833957403946"
SECRET = "sessionid=SMOKESECRET123456; UIFID=SMOKESECRETABC"


@pytest.fixture(autouse=True)
def session_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for name in (
        "SESSION_POOL_SOURCE",
        "COS_BUCKET",
        "COS_REGION",
        "COS_ENDPOINT",
        "COS_SECRET_ID",
        "COS_SECRET_KEY",
        "COS_SESSION_TOKEN",
        "COS_CREDENTIAL_URL",
        "TENCENTCLOUD_SECRETID",
        "TENCENTCLOUD_SECRETKEY",
        "SESSION_DB_DSN",
        "SESSION_DB_PATH",
        "SESSION_DB_TABLE",
        "SESSION_COS_PREFIX",
        "DOUYIN_COOKIE",
        "XHS_COOKIE",
        "DOUYIN_COOKIE_LAST_REFRESH",
        "XHS_COOKIE_LAST_REFRESH",
        "RENLINK_SESSION_TTL_S",
        "RENLINK_SESSION_RELOAD",
        "RENLINK_SESSION_LOCAL_POOL",
        "RENLINK_SESSION_MAX_AGE_S",
        "PARSE_STUB_COOKIE_EXPIRED",
        "PARSE_STUB_DOUYIN_COOKIE_EXPIRED",
        "EGRESS_PROXY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SESSION_POOL_SOURCE", "env")
    monkeypatch.setenv("RENLINK_SESSION_TTL_S", "60")
    session_bridge.reset()
    yield tmp_path
    session_bridge.reset()


def _stamp(age_s: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat(timespec="seconds")


def _pool_file(root: Path, platform: str, cookie: str, age_s: int = 0, max_age_s: int = 86400) -> Path:
    path = root / f"{platform}.json"
    path.write_text(
        json.dumps(
            {
                "platform": platform,
                "cookie": cookie,
                "refreshed_at": _stamp(age_s),
                "max_age_s": max_age_s,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_pool_priority_mirror_then_env(monkeypatch: pytest.MonkeyPatch, session_env: Path) -> None:
    _pool_file(session_env, "douyin", "from-pool=1")
    monkeypatch.setenv("RENLINK_SESSION_LOCAL_POOL", str(session_env))
    monkeypatch.setenv("DOUYIN_COOKIE", "from-env=1")

    assert session_bridge.get_cookie("douyin") == "from-pool=1"
    assert session_bridge.pool_source("douyin") == "env"
    assert session_bridge.cookie_status("douyin") == "fresh"

    monkeypatch.delenv("RENLINK_SESSION_LOCAL_POOL")
    session_bridge.reset()
    assert session_bridge.get_cookie("douyin") == "from-env=1"


def test_missing_cookie_raises_and_parse_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(session_bridge.CookieExpired):
        session_bridge.get_cookie("douyin")
    assert session_bridge.cookie_status("douyin") == "missing"

    client = TestClient(app)
    response = client.post("/parse", json={"url": DOUYIN_URL})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "COOKIE_EXPIRED"
    assert response.json()["error"]["retryable"] is True


def test_cos_success_and_failure_fallback(
    monkeypatch: pytest.MonkeyPatch, session_env: Path
) -> None:
    monkeypatch.setenv("SESSION_POOL_SOURCE", "cos")
    monkeypatch.setenv("DOUYIN_COOKIE", "from-env=1")
    monkeypatch.setattr(
        session_bridge,
        "_read_cos_pool",
        lambda platform: session_bridge.PoolRecord(platform, "from-cos=1", _stamp(), 86400, "cos"),
    )
    assert session_bridge.get_cookie("douyin") == "from-cos=1"
    assert session_bridge.pool_source("douyin") == "cos"

    session_bridge.reset()

    def boom(platform: str):
        raise session_bridge.PoolUnavailable("no bucket")

    monkeypatch.setattr(session_bridge, "_read_cos_pool", boom)
    assert session_bridge.get_cookie("douyin") == "from-env=1"
    assert session_bridge.pool_source("douyin") == "env"
    assert session_bridge.session_stats()["env_fallbacks"] == 1


def test_db_sqlite_pool(monkeypatch: pytest.MonkeyPatch, session_env: Path) -> None:
    import sqlite3

    db = session_env / "sessions.db"
    connection = sqlite3.connect(db)
    connection.execute(
        "CREATE TABLE renlink_sessions (platform TEXT, cookie TEXT, refreshed_at TEXT, max_age_s INTEGER)"
    )
    connection.execute(
        "INSERT INTO renlink_sessions VALUES (?,?,?,?)",
        ("xhs", "from-db=1", _stamp(), 86400),
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("SESSION_POOL_SOURCE", "db")
    monkeypatch.setenv("SESSION_DB_DSN", f"sqlite:///{db}")

    assert session_bridge.get_cookie("xhs") == "from-db=1"
    assert session_bridge.pool_source("xhs") == "db"


def test_expired_and_stub_expired(monkeypatch: pytest.MonkeyPatch, session_env: Path) -> None:
    _pool_file(session_env, "douyin", "stale=1", age_s=7200, max_age_s=60)
    monkeypatch.setenv("RENLINK_SESSION_LOCAL_POOL", str(session_env))
    assert session_bridge.cookie_status("douyin") == "expired"
    with pytest.raises(session_bridge.CookieExpired):
        session_bridge.get_cookie("douyin")

    monkeypatch.setenv("DOUYIN_COOKIE", "fresh=1")
    monkeypatch.setenv("PARSE_STUB_COOKIE_EXPIRED", "douyin")
    session_bridge.reset()
    session_bridge.invalidate()
    assert session_bridge.cookie_status("douyin") == "expired"
    with pytest.raises(session_bridge.CookieExpired):
        session_bridge.get_cookie("douyin")


def test_expired_pool_parse_503_without_upstream(
    monkeypatch: pytest.MonkeyPatch, session_env: Path
) -> None:
    _pool_file(session_env, "douyin", "stale=1", age_s=7200, max_age_s=60)
    monkeypatch.setenv("RENLINK_SESSION_LOCAL_POOL", str(session_env))
    called: list[int] = []

    async def fake_parse(*args, **kwargs):
        called.append(1)
        return {"content_type": "video", "items": []}

    monkeypatch.setattr("app.parsers.douyin.parse", fake_parse)
    response = TestClient(app).post("/parse", json={"url": DOUYIN_URL})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "COOKIE_EXPIRED"
    assert called == []


def test_cache_reads_once_and_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def resolve(platform: str):
        calls["n"] += 1
        value = "old=1" if calls["n"] == 1 else "new=1"
        return session_bridge.PoolRecord(platform, value, _stamp(), 86400, "env")

    monkeypatch.setattr(session_bridge, "_resolve", resolve)
    monkeypatch.setenv("RENLINK_SESSION_TTL_S", "60")
    for _ in range(10):
        assert session_bridge.get_cookie("douyin") == "old=1"
    assert calls["n"] == 1

    monkeypatch.setenv("RENLINK_SESSION_RELOAD", "1")
    assert session_bridge.get_cookie("douyin") == "new=1"
    assert calls["n"] == 2
    assert "RENLINK_SESSION_RELOAD" not in os.environ


def test_health_shape_and_no_cookie_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOUYIN_COOKIE", SECRET)
    monkeypatch.setenv("XHS_COOKIE", "web_session=OTHERSECRET")
    monkeypatch.setenv("EGRESS_PROXY", "")
    session_bridge.reset()

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["egress_proxy"] == "direct"
    for platform in ("douyin", "xhs"):
        entry = body["platforms"][platform]
        assert set(entry) == {"cookie_status", "last_refresh", "source", "pool_age_s"}
    assert "SMOKESECRET" not in response.text
    assert "OTHERSECRET" not in response.text

    monkeypatch.setenv("EGRESS_PROXY", "http://127.0.0.1:7890")
    response = TestClient(app).get("/health")
    assert response.json()["egress_proxy"] == "proxy"
    assert "127.0.0.1:7890" not in response.text


def test_parse_rejects_cookie_field(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    response = client.post("/parse", json={"url": DOUYIN_URL, "cookie": SECRET})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "SMOKESECRET" not in response.text

    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert not [path for path in paths if "cookie" in path.lower()]


def test_egress_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGRESS_PROXY", "")
    assert egress.mode() == "direct"
    assert egress.curl_cffi_proxies() is None
    assert egress.f2_proxies() is None
    assert egress.ytdlp_options() == {}

    proxy = "http://127.0.0.1:7890"
    monkeypatch.setenv("EGRESS_PROXY", proxy)
    assert egress.mode() == "proxy"
    assert egress.curl_cffi_proxies() == {"http": proxy, "https": proxy}
    assert egress.f2_proxies()["http://"] == proxy
    assert egress.ytdlp_options() == {"proxy": proxy}


def test_ytdlp_proxy_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.parsers import douyin, xhs

    captured: list[dict] = []

    class FakeYDL:
        def __init__(self, options):
            captured.append(options)
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, *args, **kwargs):
            raise RuntimeError("stop")

    monkeypatch.setenv("EGRESS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDL)
    assert douyin._ytdlp_info("https://www.douyin.com/video/1", "a=b") is None
    assert xhs._ytdlp_info("https://www.xiaohongshu.com/explore/1", "a=b") is None
    assert captured and all(item["proxy"] == "http://127.0.0.1:7890" for item in captured)


def test_f2_proxy_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.parsers import douyin
    from app.errors import ApiError

    captured: dict = {}

    class FakeHandler:
        def __init__(self, kwargs):
            captured.update(kwargs)

        async def fetch_one_video(self, aweme_id):
            raise RuntimeError("stop")

    monkeypatch.setenv("EGRESS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setattr("f2.apps.douyin.handler.DouyinHandler", FakeHandler)
    with pytest.raises(ApiError):
        douyin._f2_result("https://www.douyin.com/note/7705367833957403946", "a=b", "note")
    assert captured["proxies"]["http://"] == "http://127.0.0.1:7890"


def test_curl_cffi_proxy_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    import curl_cffi.requests as cffi_requests
    from f2.apps.douyin.utils import ABogusManager

    from app.parsers import douyin_argus

    captured: dict = {}

    monkeypatch.setenv("EGRESS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setattr(
        ABogusManager,
        "model_2_endpoint",
        staticmethod(lambda *args, **kwargs: "https://example.test/detail"),
    )

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop")

    monkeypatch.setattr(cffi_requests, "get", fake_get)
    with pytest.raises(RuntimeError):
        douyin_argus._request_detail("7705367833957403946", {"UIFID": "u"}, "u", "v")
    assert captured["proxies"] == {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }


def _refresh_module():
    path = Path(__file__).resolve().parent.parent / "ops" / "refresh_cookie.py"
    spec = importlib.util.spec_from_file_location("refresh_cookie", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_refresh_pool_writer_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _refresh_module()
    module.write_pool_records(tmp_path, {"douyin": "sessionid=abc; UIFID=def"})
    path = tmp_path / "douyin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["platform"] == "douyin"
    assert data["max_age_s"] == 86400
    assert datetime.fromisoformat(data["refreshed_at"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    before = path.read_text(encoding="utf-8")

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises(OSError):
        module.write_pool_records(tmp_path, {"douyin": "new=1"})
    assert path.read_text(encoding="utf-8") == before
