"""l3 contract addition: /parse returns a task_id that /stage accepts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

from app import stage_cache
from app.contract import ParseItem, ParseResult

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "contract" / "parse_response.schema.json"
TASK_ID = re.compile(r"^st_[0-9a-f]{24}$")


def _payload() -> dict:
    result = ParseResult(
        platform="douyin",
        content_type="video",
        source_url="https://v.douyin.com/demo/",
        resolved_url="https://www.douyin.com/video/7705367833957403946",
        title="demo",
        item_count=1,
        elapsed_ms=1,
        items=[
            ParseItem(
                index=0,
                type="video",
                remoteUrl="https://example.com/a.mp4",
                ext="mp4",
            )
        ],
    )
    return result.model_dump(mode="json")


def test_parse_payload_carries_task_id_and_validates() -> None:
    payload = _payload()
    task_id = stage_cache.remember(payload)
    payload["task_id"] = task_id

    assert TASK_ID.fullmatch(task_id)
    assert stage_cache.get_task(task_id) is not None
    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")))
