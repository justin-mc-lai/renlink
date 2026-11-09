"""l2 xhs note parsing: imageList order and fallbacks, xsec_token, failures."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import pytest

from app.errors import ApiError
from app.parsers import xhs

NOTE_ID = "6a0000000000000000000001"
PAGE_URL = "https://www.xiaohongshu.com/explore/{0}".format(NOTE_ID)
TOKEN_URL = PAGE_URL + "?xsec_token=query-token"


@pytest.fixture(autouse=True)
def xhs_env(monkeypatch: pytest.MonkeyPatch):
    xhs.reset_cache()
    for name in (
        "XHS_NOTE_HTTP_STUB",
        "XHS_NOTE_TIMEOUT_S",
        "XHS_NOTE_MAX_BYTES",
        "XHS_NOTE_MAX_HOPS",
        "XHS_NOTE_UA",
        "XHS_NOTE_CACHE_TTL_S",
        "PARSE_XHS_SKIP_YTDLP",
        "PARSE_L2_NOTE_STUB",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    xhs.reset_cache()


def page(state: dict) -> str:
    return (
        "<html><script>window.__INITIAL_STATE__="
        + json.dumps(state, ensure_ascii=False)
        + ";</script></html>"
    )


def install_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, url: str, html: str
) -> None:
    body = tmp_path / "page.html"
    body.write_text(html, encoding="utf-8")
    stub = {
        url: {
            "status": 200,
            "headers": {"content-type": "text/html"},
            "body_file": str(body),
        }
    }
    path = tmp_path / "stub.json"
    path.write_text(json.dumps(stub), encoding="utf-8")
    monkeypatch.setenv("XHS_NOTE_HTTP_STUB", str(path))


def note_state(image_list: list, extra_note: dict | None = None) -> dict:
    note = {"title": "标题", "imageList": image_list}
    note.update(extra_note or {})
    return {"note": {"noteDetailMap": {NOTE_ID: {"note": note}}}}


def test_note_images_keep_order_and_original_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_state(
        [
            {
                "urlDefault": "https://sns-img-qc.xhscdn.com/a.webp",
                "urlPre": "https://sns-img-qc.xhscdn.com/a-thumb.webp",
                "width": 1080,
                "height": 1440,
                "infoList": [
                    {
                        "imageScene": "CRD_WM_WEBP",
                        "url": "https://sns-img-qc.xhscdn.com/a-wm.webp",
                    }
                ],
            },
            {
                "infoList": [
                    {
                        "imageScene": "CRD_WM_WEBP",
                        "url": "https://sns-img-qc.xhscdn.com/b-wm.webp",
                    },
                    {
                        "imageScene": "WB_DFT",
                        "url": "https://sns-img-qc.xhscdn.com/b.jpg",
                    },
                ]
            },
            {
                "infoList": [
                    {
                        "imageScene": "CRD_WM_WEBP",
                        "url": "https://sns-img-qc.xhscdn.com/c.webp",
                    }
                ]
            },
            {"infoList": [{"imageScene": "WB_DFT"}]},
            "not-an-object",
        ]
    )
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))

    result = asyncio.run(xhs.parse_note(TOKEN_URL, "implicit=1"))

    urls = [entry["remoteUrl"] for entry in result["items"]]
    assert urls == [
        "https://sns-img-qc.xhscdn.com/a.webp",
        "https://sns-img-qc.xhscdn.com/b.jpg",
        "https://sns-img-qc.xhscdn.com/c.webp",
    ]
    assert [entry["index"] for entry in result["items"]] == [0, 1, 2]
    assert [entry["ext"] for entry in result["items"]] == ["webp", "jpeg", "webp"]
    assert all(entry["needs_transcode"] for entry in result["items"])
    assert all(entry["type"] == "image" for entry in result["items"])
    assert result["note_id"] == NOTE_ID
    assert result["title"] == "标题"
    assert result["xsec_token"] == "query-token"
    assert "urlPre" not in json.dumps(result)


def test_note_token_falls_back_to_note_then_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_state(
        [{"urlDefault": "https://sns-img-qc.xhscdn.com/d.webp"}],
        extra_note={"xsecToken": "note-token"},
    )
    state["xsecToken"] = "state-token"
    install_stub(tmp_path, monkeypatch, PAGE_URL, page(state))

    result = asyncio.run(xhs.parse_note(PAGE_URL, "c=1"))

    assert result["xsec_token"] == "note-token"


def test_note_accepts_bare_keys_and_undefined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (
        'window.__INITIAL_STATE__={note:{noteDetailMap:{"'
        + NOTE_ID
        + '":{note:{title:"裸键",imageList:[{urlDefault:'
        + '"https://sns-img-qc.xhscdn.com/e.png",width:undefined}]}}}},'
        + 'xsecToken:"bare-token"}'
    )
    install_stub(tmp_path, monkeypatch, PAGE_URL, html)

    result = asyncio.run(xhs.parse_note(PAGE_URL, "c=1"))

    assert result["xsec_token"] == "bare-token"
    assert result["items"][0]["remoteUrl"] == "https://sns-img-qc.xhscdn.com/e.png"
    assert result["items"][0]["width"] is None


def test_note_missing_token_needs_xsec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_state([{"urlDefault": "https://sns-img-qc.xhscdn.com/f.webp"}])
    install_stub(tmp_path, monkeypatch, PAGE_URL, page(state))

    with pytest.raises(ApiError) as caught:
        asyncio.run(xhs.parse_note(PAGE_URL, "c=1"))

    error = caught.value
    assert error.code == "NEED_XSEC_TOKEN"
    assert error.http_status == 422
    assert error.retryable is True


def test_note_missing_state_is_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stub(tmp_path, monkeypatch, PAGE_URL, "<html><body>no state</body></html>")

    with pytest.raises(ApiError) as caught:
        asyncio.run(xhs.parse_note(PAGE_URL + "?xsec_token=t", "c=1"))

    assert caught.value.code == "PARSE_FAILED"


def _count_fetches(
    monkeypatch: pytest.MonkeyPatch, calls: list, state: dict
) -> None:
    async def fake_fetch(url: str, cookie: str) -> tuple:
        calls.append(url)
        return page(state), url

    monkeypatch.setattr(xhs, "_fetch_note", fake_fetch)


def test_note_cache_hit_skips_upstream(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list = []
    state = note_state(
        [
            {"urlDefault": "https://sns-img-qc.xhscdn.com/j.webp"},
            {"urlDefault": "https://sns-img-qc.xhscdn.com/k.webp"},
        ]
    )
    _count_fetches(monkeypatch, calls, state)

    with caplog.at_level(logging.INFO, logger="renlink.xhs"):
        first = asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))
        second = asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert calls == [TOKEN_URL]
    assert first == second
    stats = xhs.counters()
    assert stats["xhs_note_cache_hit_total"] == 1
    assert stats["xhs_note_cache_miss_total"] == 1
    assert stats["xhs_note_parse_total{result=ok}"] == 2
    assert stats["xhs_note_images_total"] == 4
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=xhs_note_parse" in logs
    assert "cache=hit" in logs
    assert "cache=miss" in logs


def test_note_cache_expires_after_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    state = note_state([{"urlDefault": "https://sns-img-qc.xhscdn.com/l.webp"}])
    _count_fetches(monkeypatch, calls, state)
    monkeypatch.setenv("XHS_NOTE_CACHE_TTL_S", "1")

    asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))
    time.sleep(1.1)
    asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert len(calls) == 2
    assert xhs.counters()["xhs_note_cache_hit_total"] == 0
    assert xhs.counters()["xhs_note_cache_miss_total"] == 2


def test_note_cache_ttl_zero_disables(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list = []
    state = note_state([{"urlDefault": "https://sns-img-qc.xhscdn.com/m.webp"}])
    _count_fetches(monkeypatch, calls, state)
    monkeypatch.setenv("XHS_NOTE_CACHE_TTL_S", "0")

    with caplog.at_level(logging.INFO, logger="renlink.xhs"):
        asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))
        asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert len(calls) == 2
    assert xhs.counters()["xhs_note_cache_hit_total"] == 0
    assert xhs.counters()["xhs_note_cache_miss_total"] == 0
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "cache_state=disabled" in logs


def test_note_failure_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []

    async def failing_fetch(url: str, cookie: str) -> tuple:
        calls.append(url)
        raise ApiError("PARSE_FAILED", "页面没有 window.__INITIAL_STATE__")

    monkeypatch.setattr(xhs, "_fetch_note", failing_fetch)

    for _ in range(2):
        with pytest.raises(ApiError) as caught:
            asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))
        assert caught.value.code == "PARSE_FAILED"

    assert len(calls) == 2
    stats = xhs.counters()
    assert stats["xhs_note_parse_total{result=failed}"] == 2
    assert stats["xhs_note_cache_hit_total"] == 0


def test_note_empty_image_list_is_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_state([])
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))

    with pytest.raises(ApiError) as caught:
        asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert caught.value.code == "PARSE_FAILED"


def test_parse_seam_returns_normalized_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_state(
        [
            {"urlDefault": "https://sns-img-qc.xhscdn.com/g.webp"},
            {"urlDefault": "https://sns-img-qc.xhscdn.com/h.jpg"},
        ]
    )
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))
    monkeypatch.setenv("PARSE_XHS_SKIP_YTDLP", "1")

    result = asyncio.run(xhs.parse(TOKEN_URL, "c=1"))

    assert result["content_type"] == "note"
    assert result["title"] == "标题"
    assert len(result["items"]) == 2
    assert all(entry["type"] == "image" for entry in result["items"])
    assert all(entry["needs_transcode"] is True for entry in result["items"])


# --- l2-xhs-images AC-004: noteDetailMap / noteData dual structure -----------


IMAGE_LIST = [
    {
        "urlDefault": "https://sns-img-qc.xhscdn.com/n1.webp",
        "width": 1080,
        "height": 1440,
    },
    {"urlDefault": "https://sns-img-qc.xhscdn.com/n2.jpg"},
]


def note_data_state(
    image_list: list, note_id: str = NOTE_ID, title: str = "标题"
) -> dict:
    return {
        "noteData": {
            "data": {"noteData": {"noteId": note_id, "title": title, "imageList": image_list}}
        }
    }


def item_signature(result: dict) -> list:
    return [
        (entry["index"], entry["type"], entry["remoteUrl"], entry["ext"])
        for entry in result["items"]
    ]


def test_note_detail_map_and_note_data_parse_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XHS_NOTE_CACHE_TTL_S", "0")
    install_stub(
        tmp_path,
        monkeypatch,
        TOKEN_URL,
        page({"note": {"noteDetailMap": {NOTE_ID: {"note": {"title": "标题", "imageList": IMAGE_LIST}}}}}),
    )
    from_map = asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(note_data_state(IMAGE_LIST)))
    from_data = asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert item_signature(from_map) == item_signature(from_data)
    assert len(from_data["items"]) == len(IMAGE_LIST) == 2
    assert all(entry["type"] == "image" for entry in from_data["items"])
    assert from_data["title"] == "标题"
    assert from_data["note_id"] == NOTE_ID


def test_note_multiple_map_entries_fall_back_to_note_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other_note = {"title": "别的笔记", "imageList": IMAGE_LIST}
    state = note_data_state(IMAGE_LIST, title="第二结构")
    state["note"] = {"noteDetailMap": {"other-1": {"note": other_note}, "other-2": {"note": other_note}}}
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))

    result = asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert result["title"] == "第二结构"
    assert len(result["items"]) == 2


def test_note_note_data_id_mismatch_is_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = note_data_state(IMAGE_LIST, note_id="6a0000000000000000000002")
    state["note"] = {"noteDetailMap": {}}
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))

    with pytest.raises(ApiError) as caught:
        asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert caught.value.code == "PARSE_FAILED"
    assert caught.value.retryable is True


def test_note_malformed_map_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"note": {"noteDetailMap": ""}, "noteData": {"data": {"noteData": "broken"}}}
    install_stub(tmp_path, monkeypatch, TOKEN_URL, page(state))

    with pytest.raises(ApiError) as caught:
        asyncio.run(xhs.parse_note(TOKEN_URL, "c=1"))

    assert caught.value.code == "PARSE_FAILED"
