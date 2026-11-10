#!/usr/bin/env python3
"""l1-parser-core smoke runner: 24 cases from tests.md.

Real samples are read from environment variables. Missing samples are reported
as BLOCKED (exit code 3); the runner never invents links. Constructed negative
cases run whenever the service is reachable.

Full-suite note: the service rate-limits 20 requests/min per IP. For a complete
24-case local run start it with PARSE_RATE_LIMIT_PER_MIN=0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "beacon" / "v0.1.0" / "features" / "l1-parser-core" / "evidence" / "l1"
SCHEMA_PATH = ROOT / "contract" / "parse_response.schema.json"
BASE = os.getenv("PARSE_BASE", "http://localhost:8080").rstrip("/")


class Blocked(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _short(value: Any, limit: int = 32) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "..."


def _expect(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def _request_post(payload: Dict[str, Any], timeout: float = 16.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + "/parse",
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise Blocked(f"服务不可达: {type(exc).__name__}")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        body = {"_raw": raw.decode("utf-8", "replace")[:500]}
    return {
        "status": status,
        "body": body,
        "bytes": len(raw),
        "elapsed_ms": elapsed_ms,
        "request": {"url": _short(payload.get("url"))},
    }


def _request_get(path: str, timeout: float = 5.0) -> Dict[str, Any]:
    request = urllib.request.Request(BASE + path, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise Blocked(f"服务不可达: {type(exc).__name__}")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        body = {"_raw": raw.decode("utf-8", "replace")[:500]}
    return {"status": status, "body": body, "bytes": len(raw), "elapsed_ms": elapsed_ms, "request": {"path": path}}


def _success_shape(body: Dict[str, Any], failures: List[str]) -> List[Dict[str, Any]]:
    _expect(body.get("ok") is True, "ok 不是 true", failures)
    for field in ("platform", "content_type", "source_url", "resolved_url", "title"):
        _expect(isinstance(body.get(field), str), f"{field} 不是字符串", failures)
    for field in ("item_count", "elapsed_ms"):
        _expect(isinstance(body.get(field), int), f"{field} 不是整数", failures)
    items = body.get("items")
    _expect(isinstance(items, list), "items 不是数组", failures)
    items = items if isinstance(items, list) else []
    _expect(body.get("item_count") == len(items), "item_count 不等于 items 长度", failures)
    indices = [item.get("index") for item in items if isinstance(item, dict)]
    _expect(indices == list(range(len(items))), "items[].index 不是从 0 连续", failures)
    for item in items:
        if not isinstance(item, dict):
            failures.append("items 含非对象")
            continue
        _expect(str(item.get("remoteUrl", "")).startswith(("http://", "https://")), "remoteUrl 不是 http(s)", failures)
        _expect(item.get("type") in ("video", "image"), "item.type 不在 video/image", failures)
        _expect(isinstance(item.get("needs_transcode"), bool), "needs_transcode 不是布尔", failures)
        _expect("cloudID" not in item, "item 里出现 cloudID", failures)
    _expect("cloudID" not in body, "响应里出现 cloudID", failures)
    return items


def _error_shape(body: Dict[str, Any], code: str, status: int, expected_status: int, failures: List[str], retryable: Optional[bool] = None) -> None:
    _expect(status == expected_status, f"HTTP 状态 {status} != {expected_status}", failures)
    _expect(body.get("ok") is False, "ok 不是 false", failures)
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    _expect(error.get("code") == code, f"error.code {error.get('code')} != {code}", failures)
    _expect(isinstance(error.get("message"), str) and bool(error.get("message")), "error.message 缺失", failures)
    _expect(isinstance(error.get("retryable"), bool), "error.retryable 不是布尔", failures)
    if retryable is not None:
        _expect(error.get("retryable") is retryable, f"retryable 应为 {retryable}", failures)
    _expect(body.get("items") == [], "失败信封 items 不是空数组", failures)
    _expect(isinstance(body.get("elapsed_ms"), int), "elapsed_ms 不是整数", failures)


def _sample(ctx: Dict[str, Any], name: str) -> str:
    value = ctx["samples"].get(name, "")
    if not value:
        raise Blocked(f"缺少样本 {name}")
    return value


def case_dy_video(ctx: Dict[str, Any], sample: str) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, sample)
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    _expect(result["body"].get("platform") == "douyin", "platform 不是 douyin", failures)
    _expect(result["body"].get("content_type") == "video", "content_type 不是 video", failures)
    _expect(len(items) == 1, "items 长度不是 1", failures)
    if items:
        _expect(items[0].get("ext") == "mp4", "items[0].ext 不是 mp4", failures)
    return failures, result, ""


def case_dy_note(ctx: Dict[str, Any], sample: str) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, sample)
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    _expect(result["body"].get("platform") == "douyin", "platform 不是 douyin", failures)
    _expect(result["body"].get("content_type") == "note", "content_type 不是 note", failures)
    _expect(all(item.get("type") == "image" for item in items), "图文里有非 image 项", failures)
    return failures, result, "item_count 需与页面实际张数手工核对"


def case_xhs_video(ctx: Dict[str, Any], sample: str) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, sample)
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    _expect(result["body"].get("platform") == "xhs", "platform 不是 xhs", failures)
    _expect(result["body"].get("content_type") == "video", "content_type 不是 video", failures)
    _expect(len(items) == 1, "items 长度不是 1", failures)
    if items:
        _expect(items[0].get("ext") == "mp4", "items[0].ext 不是 mp4", failures)
    return failures, result, ""


def case_dy_short(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_SHORT_1")
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    _success_shape(result["body"], failures)
    resolved = str(result["body"].get("resolved_url") or "")
    _expect(bool(re.match(r"^https://www\.douyin\.com/(video|note)/[0-9]+", resolved)), f"resolved_url 不是抖音规范页: {resolved}", failures)
    _expect(result["body"].get("source_url") == url, "source_url 未保留原始短链", failures)
    return failures, result, ""


def case_xhs_short(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "XHS_SHORT_1")
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    _success_shape(result["body"], failures)
    resolved = str(result["body"].get("resolved_url") or "")
    _expect(
        "xiaohongshu.com/explore" in resolved or "xiaohongshu.com/discovery/item" in resolved,
        f"resolved_url 不是小红书规范页: {resolved}",
        failures,
    )
    _expect(result["body"].get("platform") == "xhs", "platform 不是 xhs", failures)
    _expect(result["body"].get("source_url") == url, "source_url 未保留原始短链", failures)
    return failures, result, ""


def case_cookie_expired(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    result = _request_post({"url": url})
    failures: List[str] = []
    _error_shape(result["body"], "COOKIE_EXPIRED", result["status"], 503, failures, True)
    response_text = json.dumps(result["body"], ensure_ascii=False)
    cookie_value = os.getenv("DOUYIN_COOKIE", "").strip()
    if cookie_value:
        _expect(cookie_value not in response_text, "响应回显了 cookie 原值", failures)
    _expect("sessionid=" not in response_text.lower(), "响应回显了 sessionid", failures)
    return failures, result, "需服务端以 PARSE_STUB_COOKIE_EXPIRED=douyin 启动"


def case_shortlink_fail(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    result = _request_post({"url": "https://v.douyin.com/0000000/"})
    failures: List[str] = []
    _error_shape(result["body"], "SHORTLINK_FAIL", result["status"], 422, failures, True)
    _expect(result["body"].get("resolved_url") == "", "resolved_url 不是空字符串", failures)
    return failures, result, "构造的失效短链，不冒充真实样本"


def case_invalid_url(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    payloads = [{"url": ""}, {"url": "not-a-url"}, {"url": "https://" + "a" * 3000 + ".com/x"}]
    failures: List[str] = []
    last: Dict[str, Any] = {}
    for payload in payloads:
        last = _request_post(payload)
        _error_shape(last["body"], "INVALID_URL", last["status"], 400, failures, False)
        _expect(last["elapsed_ms"] < 500, f"非法输入耗时 {last['elapsed_ms']}ms 超过 500ms", failures)
    return failures, last, "三组输入：空串、not-a-url、超长 URL"


def case_unsupported(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    urls = [
        "https://www.bilibili.com/video/BV1xx411c7mD",
        "https://weibo.com/1/abc",
        "https://youtu.be/abc",
    ]
    failures: List[str] = []
    last: Dict[str, Any] = {}
    for url in urls:
        last = _request_post({"url": url})
        _error_shape(last["body"], "UNSUPPORTED_PLATFORM", last["status"], 400, failures, False)
    return failures, last, "三个非目标平台"


def case_timeout(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    result = _request_post({"url": url}, timeout=16.0)
    failures: List[str] = []
    _error_shape(result["body"], "TIMEOUT", result["status"], 504, failures, True)
    _expect(result["elapsed_ms"] < 15000, f"墙钟耗时 {result['elapsed_ms']}ms 不小于 15s", failures)
    return failures, result, "需服务端以 PARSE_UPSTREAM_DELAY_MS=13000 启动"


def _has_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_has_key(entry, key) for entry in value.values())
    if isinstance(value, list):
        return any(_has_key(entry, key) for entry in value)
    return False


def case_size_cap(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "XHS_NOTE_MAX")
    result = _request_post({"url": url})
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    _expect(result["bytes"] <= 1024000, f"响应 {result['bytes']} 字节超过 1024000", failures)
    _expect(len(items) <= 100, f"items 数量 {len(items)} 超过 100", failures)
    _expect(not _has_key(result["body"], "base64"), "响应里出现 base64 键", failures)
    _expect(result["body"].get("item_count") == len(items), "item_count 不等于返回条目数", failures)
    return failures, result, "120 项截断由实现侧单元检查另存证据"


def _validate_schema(body: Dict[str, Any], failures: List[str]) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        failures.append("jsonschema 未安装，schema 校验未执行")
        return
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(body, schema)
    except Exception as exc:
        failures.append(f"schema 校验失败: {type(exc).__name__}: {str(exc)[:200]}")


def case_field_contract(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    samples = ["DY_VIDEO_1", "DY_NOTE_1", "XHS_VIDEO_1", "DY_SHORT_1"]
    failures: List[str] = []
    last: Dict[str, Any] = {}
    for sample in samples:
        url = _sample(ctx, sample)
        last = _request_post({"url": url})
        _expect(last["status"] == 200, f"{sample} HTTP 状态 {last['status']} != 200", failures)
        _success_shape(last["body"], failures)
        _validate_schema(last["body"], failures)
        for item in last["body"].get("items") or []:
            if last["body"].get("platform") == "xhs" and item.get("type") == "image":
                _expect(item.get("needs_transcode") is True, "xhs 图片 needs_transcode 不是 true", failures)
    return failures, last, "schema: contract/parse_response.schema.json"


def _tmp_snapshot(container_id: str) -> Optional[set]:
    try:
        output = subprocess.check_output(
            ["docker", "exec", container_id, "sh", "-c", "find /tmp -type f | sort"],
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        return set(output.decode("utf-8", "replace").splitlines())
    except Exception:
        return None


def case_no_download(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    container_id = os.getenv("SMOKE_CONTAINER_ID", "").strip()
    before = _tmp_snapshot(container_id) if container_id else None
    result = _request_post({"url": url})
    after = _tmp_snapshot(container_id) if container_id else None
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    _success_shape(result["body"], failures)
    _expect(not _has_key(result["body"], "cloudID"), "响应里出现 cloudID", failures)
    note = "SMOKE_CONTAINER_ID 未设置，/tmp 前后对比未执行"
    if before is not None and after is not None:
        _expect(before == after, f"/tmp 文件变化: {sorted(after - before)}", failures)
        note = "/tmp 前后快照一致"
    return failures, result, note


def case_user_cookie(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    result = _request_post({"url": "https://v.douyin.com/XXXXXXX/", "cookie": "sessionid=1"})
    failures: List[str] = []
    _error_shape(result["body"], "INVALID_REQUEST", result["status"], 400, failures, False)
    _expect("sessionid=1" not in json.dumps(result["body"], ensure_ascii=False), "响应回显了 cookie 值", failures)
    return failures, result, "请求体含 cookie 字段，不应进入解析分支"


def case_health(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    result = _request_get("/health")
    failures: List[str] = []
    body = result["body"]
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    _expect(body.get("ok") is True, "ok 不是 true", failures)
    platforms = body.get("platforms") if isinstance(body.get("platforms"), dict) else {}
    for platform in ("douyin", "xhs"):
        entry = platforms.get(platform) if isinstance(platforms.get(platform), dict) else {}
        _expect(isinstance(entry.get("cookie_status"), str) and bool(entry.get("cookie_status")), f"platforms.{platform}.cookie_status 缺失", failures)
    _expect(result["elapsed_ms"] < 200, f"健康探针耗时 {result['elapsed_ms']}ms 超过 200ms", failures)
    return failures, result, ""


def _health_stats() -> Dict[str, Any]:
    result = _request_get("/health")
    body = result["body"] if isinstance(result["body"], dict) else {}
    return {
        "argus": body.get("argus") if isinstance(body.get("argus"), dict) else {},
        "render": body.get("render") if isinstance(body.get("render"), dict) else {},
    }


def case_dy_argus(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    before = _health_stats()
    result = _request_post({"url": url})
    after = _health_stats()
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    body = result["body"]
    _expect(body.get("platform") == "douyin", "platform 不是 douyin", failures)
    _expect(body.get("content_type") == "video", "content_type 不是 video", failures)
    _expect(len(items) == 1, "items 长度不是 1", failures)
    if items:
        _expect(items[0].get("remoteUrl", "").startswith("https://"), "remoteUrl 不是 https", failures)
        _expect(items[0].get("ext") == "mp4", "items[0].ext 不是 mp4", failures)
    _expect(int(body.get("elapsed_ms") or 0) < 12000, "elapsed_ms 超过 12000", failures)
    text_body = json.dumps(body, ensure_ascii=False)
    _expect("/tmp/" not in text_body, "响应里出现本地路径", failures)
    _expect("data:video" not in text_body, "响应里出现内嵌媒体", failures)
    launches_before = int(before["render"].get("browser_launches") or 0)
    launches_after = int(after["render"].get("browser_launches") or 0)
    _expect(launches_after == launches_before, "Argus 主路径启动了浏览器", failures)
    return failures, result, f"argus requests {before['argus'].get('argus_requests')} -> {after['argus'].get('argus_requests')}，browser_launches 不增"


def case_dy_argus_stability(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    failures: List[str] = []
    last: Dict[str, Any] = {}
    for round_no in range(3):
        last = _request_post({"url": url})
        _expect(last["status"] == 200, f"第 {round_no + 1} 次 HTTP 状态 {last['status']} != 200", failures)
        items = _success_shape(last["body"], failures)
        _expect(bool(items) and bool(items[0].get("remoteUrl")), f"第 {round_no + 1} 次 remoteUrl 为空", failures)
        time.sleep(1)
    return failures, last, "连跑 3 次；需服务端以 RENLINK_DISABLE_CACHE=1 启动，避免缓存掩盖上游稳定性"


def case_dy_argus_missing_header(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    result = _request_post({"url": url})
    failures: List[str] = []
    _error_shape(result["body"], "PARSE_FAILED", result["status"], 502, failures, True)
    _expect(result["body"].get("items") == [], "失败响应带半截 items", failures)
    return failures, result, "需服务端以 RENLINK_DROP_ARGUS_HEADER=1 启动"


def case_dy_argus_timeout(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    url = _sample(ctx, "DY_VIDEO_1")
    result = _request_post({"url": url}, timeout=16.0)
    failures: List[str] = []
    _error_shape(result["body"], "TIMEOUT", result["status"], 504, failures, True)
    _expect(result["body"].get("items") == [], "超时响应带半截 items", failures)
    _expect(result["elapsed_ms"] < 15000, f"墙钟耗时 {result['elapsed_ms']}ms 不小于 15s", failures)
    return failures, result, "需服务端以 PARSE_UPSTREAM_DELAY_MS=13000 启动；抖音不启浏览器，12s 总预算到期直接 504"


def case_obscura_xhs_render(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    """TC-023: render one xhs note through the optional Obscura server."""
    url = _sample(ctx, "XHS_NOTE_1")
    result = _request_get("/render/probe?url=" + quote(url, safe=""), timeout=20.0)
    failures: List[str] = []
    body = result["body"] if isinstance(result["body"], dict) else {}
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    _expect(body.get("ok") is True, "ok 不是 true", failures)
    title = str(body.get("title") or "")
    _expect(len(title) >= 4, "渲染标题为空或过短", failures)
    _expect(not title.lower().startswith("loading"), f"页面仍是 loading shell: {title}", failures)
    _expect(title not in ("小红书", "小红书 - 你的生活指南"), "只有通用站点标题，页面未渲染出笔记", failures)
    _expect(not any(word in title for word in ("验证", "captcha", "安全验证")), f"标题是验证页: {title}", failures)
    _expect(body.get("has_xsec_token") is True, "渲染内容不含 xsec_token", failures)
    _expect(body.get("obscura_alive") is True, "渲染后 obscura CDP 端口不再存活（疑似 browser.close）", failures)
    _expect(int(body.get("html_bytes") or 0) > 2000, "渲染 HTML 过小", failures)
    _expect(result["elapsed_ms"] < 12000, f"渲染耗时 {result['elapsed_ms']}ms 超过 12s", failures)
    final_host = str(urlparse(str(body.get("final_url") or "")).hostname or "")
    _expect(final_host.endswith("xiaohongshu.com"), f"final_url 不是小红书: {body.get('final_url')}", failures)
    result["extra"] = {
        "title": title,
        "final_url": body.get("final_url"),
        "html_bytes": body.get("html_bytes"),
        "has_xsec_token": body.get("has_xsec_token"),
        "obscura_alive": body.get("obscura_alive"),
    }
    return failures, result, "需 ENABLE_OBSCURA=1 且 obscura serve 已就绪"


def case_douyin_no_obscura(ctx: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any], str]:
    """TC-024: with Obscura enabled, douyin still goes Argus HTTP only."""
    url = _sample(ctx, "DY_VIDEO_1")
    before = _health_stats()
    result = _request_post({"url": url})
    after = _health_stats()
    failures: List[str] = []
    _expect(result["status"] == 200, f"HTTP 状态 {result['status']} != 200", failures)
    items = _success_shape(result["body"], failures)
    _expect(result["body"].get("platform") == "douyin", "platform 不是 douyin", failures)
    _expect(len(items) == 1, "items 长度不是 1", failures)
    if items:
        _expect(str(items[0].get("remoteUrl", "")).startswith("https://"), "remoteUrl 不是 play_addr", failures)
    render_before = before.get("render") or {}
    render_after = after.get("render") or {}
    _expect(render_after.get("enabled") is True, "ENABLE_OBSCURA 未开启，本用例前提不成立", failures)
    for key in ("renders", "cdp_connects"):
        _expect(
            int(render_after.get(key) or 0) == int(render_before.get(key) or 0),
            f"抖音请求期间 render.{key} 增加",
            failures,
        )
    _expect("douyin" not in str(render_after.get("last_url_host") or ""), "Obscura 记录到抖音页面", failures)

    # Static boundary: neither douyin module may import the renderer.
    import_render = re.compile(r"^\s*(?:from\s+[\w.]*\brender\b|import\s+[\w.]*\brender\b)", re.M)
    for name in ("douyin.py", "douyin_argus.py"):
        source = (ROOT / "container" / "app" / "parsers" / name).read_text(encoding="utf-8")
        _expect(not import_render.search(source), f"{name} 导入了 render", failures)

    log_hits = None
    container_id = os.getenv("SMOKE_CONTAINER_ID", "").strip()
    if container_id:
        try:
            output = subprocess.check_output(
                ["docker", "exec", container_id, "sh", "-c", "grep -ci douyin /tmp/obscura.log || true"],
                stderr=subprocess.STDOUT,
                timeout=10,
            ).decode("utf-8", "replace").strip()
            log_hits = int(output or "0")
        except Exception:
            log_hits = None
        if log_hits is not None:
            _expect(log_hits == 0, f"obscura 日志出现 {log_hits} 行抖音请求", failures)
    result["extra"] = {
        "render_before": render_before,
        "render_after": render_after,
        "obscura_log_douyin_hits": log_hits,
    }
    note = "需 ENABLE_OBSCURA=1；抖音仍走 Argus 直连"
    if log_hits is None:
        note += "；SMOKE_CONTAINER_ID 未设置，obscura 日志未检查"
    return failures, result, note


CASES: List[Dict[str, Any]] = [
    {"tc": "TC-001", "name": "dy-video-1", "requires": ["DY_VIDEO_1"], "run": lambda ctx: case_dy_video(ctx, "DY_VIDEO_1"), "note": ""},
    {"tc": "TC-002", "name": "dy-video-2", "requires": ["DY_VIDEO_2"], "run": lambda ctx: case_dy_video(ctx, "DY_VIDEO_2"), "note": ""},
    {"tc": "TC-003", "name": "dy-note-1", "requires": ["DY_NOTE_1"], "run": lambda ctx: case_dy_note(ctx, "DY_NOTE_1"), "note": ""},
    {"tc": "TC-004", "name": "dy-note-2", "requires": ["DY_NOTE_2"], "run": lambda ctx: case_dy_note(ctx, "DY_NOTE_2"), "note": ""},
    {"tc": "TC-005", "name": "xhs-video-1", "requires": ["XHS_VIDEO_1"], "run": lambda ctx: case_xhs_video(ctx, "XHS_VIDEO_1"), "note": ""},
    {"tc": "TC-006", "name": "xhs-video-2", "requires": ["XHS_VIDEO_2"], "run": lambda ctx: case_xhs_video(ctx, "XHS_VIDEO_2"), "note": ""},
    {"tc": "TC-007", "name": "dy-short-1", "requires": ["DY_SHORT_1"], "run": case_dy_short, "note": ""},
    {"tc": "TC-008", "name": "xhs-short-1", "requires": ["XHS_SHORT_1"], "run": case_xhs_short, "note": ""},
    {"tc": "TC-009", "name": "cookie-expired", "requires": ["DY_VIDEO_1"], "server_env": ["PARSE_STUB_COOKIE_EXPIRED"], "run": case_cookie_expired, "note": ""},
    {"tc": "TC-010", "name": "shortlink-fail", "requires": [], "run": case_shortlink_fail, "note": ""},
    {"tc": "TC-011", "name": "invalid-url", "requires": [], "run": case_invalid_url, "note": ""},
    {"tc": "TC-012", "name": "unsupported-platform", "requires": [], "run": case_unsupported, "note": ""},
    {"tc": "TC-013", "name": "timeout", "requires": ["DY_VIDEO_1"], "server_env": ["PARSE_UPSTREAM_DELAY_MS"], "run": case_timeout, "note": ""},
    {"tc": "TC-014", "name": "size-cap", "requires": ["XHS_NOTE_MAX"], "run": case_size_cap, "note": ""},
    {"tc": "TC-015", "name": "field-contract", "requires": ["DY_VIDEO_1", "DY_NOTE_1", "XHS_VIDEO_1", "DY_SHORT_1"], "run": case_field_contract, "note": ""},
    {"tc": "TC-016", "name": "no-download", "requires": ["DY_VIDEO_1"], "run": case_no_download, "note": ""},
    {"tc": "TC-017", "name": "user-cookie", "requires": [], "run": case_user_cookie, "note": ""},
    {"tc": "TC-018", "name": "health", "requires": [], "run": case_health, "note": ""},
    {"tc": "TC-019", "name": "dy-argus-1", "requires": ["DY_VIDEO_1"], "run": case_dy_argus, "note": ""},
    {"tc": "TC-020", "name": "dy-argus-stability", "requires": ["DY_VIDEO_1"], "server_env": ["RENLINK_DISABLE_CACHE"], "run": case_dy_argus_stability, "note": ""},
    {"tc": "TC-021", "name": "dy-argus-missing-header", "requires": ["DY_VIDEO_1"], "server_env": ["RENLINK_DROP_ARGUS_HEADER"], "run": case_dy_argus_missing_header, "note": ""},
    {"tc": "TC-022", "name": "dy-argus-timeout", "requires": ["DY_VIDEO_1"], "server_env": ["PARSE_UPSTREAM_DELAY_MS"], "run": case_dy_argus_timeout, "note": ""},
    {"tc": "TC-023", "name": "obscura-xhs-render", "requires": ["XHS_NOTE_1"], "server_env": ["ENABLE_OBSCURA"], "run": case_obscura_xhs_render, "note": ""},
    {"tc": "TC-024", "name": "douyin-no-obscura", "requires": ["DY_VIDEO_1"], "server_env": ["ENABLE_OBSCURA"], "run": case_douyin_no_obscura, "note": ""},
]


def _write_evidence(out_dir: Path, tc: str, payload: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"smoke-{tc}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Renlink l1 parser smoke runner")
    parser.add_argument("--case", action="append", default=[], help="case name or TC id (repeatable)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="evidence directory")
    args = parser.parse_args(argv)

    # Real-sample variables (8): DY_VIDEO_1, DY_VIDEO_2, DY_NOTE_1,
    # DY_NOTE_2, XHS_VIDEO_1, XHS_VIDEO_2, DY_SHORT_1, XHS_SHORT_1.
    # XHS_NOTE_MAX is a 9th variable used only by TC-014 (an xhs note with
    # more than 100 images); TC-014 stays BLOCKED unless it is supplied too.
    # XHS_NOTE_1 is the TC-023 render sample.
    ctx = {"samples": {key: os.getenv(key, "").strip() for key in (
        "DY_VIDEO_1", "DY_VIDEO_2", "DY_NOTE_1", "DY_NOTE_2",
        "XHS_VIDEO_1", "XHS_VIDEO_2", "DY_SHORT_1", "XHS_SHORT_1", "XHS_NOTE_MAX",
        "XHS_NOTE_1",
    )}}
    selected = [c for c in CASES if not args.case or c["name"] in args.case or c["tc"] in args.case]
    if not selected:
        print("no matching cases", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}
    print(f"PARSE_BASE={BASE}")
    for case in selected:
        missing = [key for key in case["requires"] if not ctx["samples"].get(key)]
        missing_server = [key for key in case.get("server_env", []) if not os.getenv(key)]
        status = "BLOCKED"
        failures: List[str] = []
        note = case["note"]
        request: Dict[str, Any] = {}
        started = _now()
        if missing:
            note = (note + "; " if note else "") + "缺少样本: " + ", ".join(missing)
        elif missing_server:
            note = (note + "; " if note else "") + "服务端未以 " + ", ".join(missing_server) + " 启动"
        else:
            try:
                failures, result, extra = case["run"](ctx)
                request = result.get("request", {})
                note = (note + "; " if note and extra else "") + (extra or "")
                status = "PASS" if not failures else "FAIL"
                evidence = {
                    "tc": case["tc"],
                    "name": case["name"],
                    "status": status,
                    "startedAt": started,
                    "base": BASE,
                    "request": request,
                    "httpStatus": result.get("status"),
                    "responseBytes": result.get("bytes"),
                    "clientElapsedMs": result.get("elapsed_ms"),
                    "response": result.get("body"),
                    "failures": failures,
                    "note": note,
                }
                if result.get("extra"):
                    evidence["extra"] = result["extra"]
                _write_evidence(out_dir, case["tc"], evidence)
            except Blocked as exc:
                status = "BLOCKED"
                note = (note + "; " if note else "") + str(exc)
        if status == "BLOCKED":
            _write_evidence(out_dir, case["tc"], {
                "tc": case["tc"],
                "name": case["name"],
                "status": status,
                "startedAt": started,
                "base": BASE,
                "request": request,
                "failures": [],
                "note": note,
            })
        counts[status] += 1
        detail = f" failures={failures}" if failures else ""
        print(f"{case['tc']} {case['name']}: {status}{detail}" + (f" ({note})" if note else ""))

    print(f"SUMMARY pass={counts['PASS']} fail={counts['FAIL']} blocked={counts['BLOCKED']}")
    if counts["FAIL"]:
        return 2
    if counts["BLOCKED"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
