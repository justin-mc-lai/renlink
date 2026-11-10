#!/usr/bin/env python3
"""l3-media-delivery smoke runner (TC-001..TC-014).

Every case talks to a running container over HTTP: POST /parse first, compute
the frozen task_id locally, then POST /stage. Results are JSON files under
docs/beacon/v0.1.0/features/l3-media-delivery/evidence/.

Real samples come from environment variables; the runner never invents links.
Missing samples are BLOCKED (exit 3), matching ops/smoke.py.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = (
    ROOT
    / "docs"
    / "beacon"
    / "v0.1.0"
    / "features"
    / "l3-media-delivery"
    / "evidence"
)
BASE = os.getenv("PARSE_BASE", "http://127.0.0.1:18099").rstrip("/")
LOCAL_DIR = Path(os.getenv("STAGE_LOCAL_DIR", "/tmp/renlink-stage-store"))


class Blocked(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _request(
    method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 70.0
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"content-type": "application/json"},
        method=method,
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
        raise Blocked("服务不可达: {0}".format(type(exc).__name__)) from exc
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
    }


def parse_url(url: str) -> Dict[str, Any]:
    return _request("POST", "/parse", {"url": url}, timeout=25.0)


def stage(task_id: str, index: int, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"task_id": task_id, "index": index}
    if extra:
        payload.update(extra)
    return _request("POST", "/stage", payload, timeout=75.0)


def task_id_for(payload: Dict[str, Any]) -> str:
    platform = str(payload.get("platform") or "")
    content_type = str(payload.get("content_type") or "")
    resolved_url = str(payload.get("resolved_url") or "")
    lines = []
    for item in payload.get("items") or []:
        lines.append(
            "{index}:{type}:{ext}:{url}".format(
                index=item.get("index"),
                type=item.get("type"),
                ext=item.get("ext"),
                url=item.get("remoteUrl"),
            )
        )
    material = "v1|" + platform + "|" + content_type + "|" + resolved_url + "\n" + "\n".join(lines)
    return "st_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def sample(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise Blocked("缺少样本 {0}".format(name))
    return value


def image_sample() -> str:
    for name in ("STAGE_IMAGE_URL", "DY_NOTE_1", "XHS_NOTE_1"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise Blocked("缺少图片样本 STAGE_IMAGE_URL / DY_NOTE_1")


def video_sample() -> str:
    for name in ("STAGE_VIDEO_URL", "DY_VIDEO_1", "XHS_VIDEO_1"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise Blocked("缺少视频样本 DY_VIDEO_1 / XHS_VIDEO_1")


def find_item(payload: Dict[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    for item in payload.get("items") or []:
        if isinstance(item, dict) and item.get("type") == kind:
            return item
    return None


def local_path(file_id: str) -> Optional[Path]:
    prefix = "cloud://local/"
    if not file_id.startswith(prefix):
        return None
    return LOCAL_DIR / file_id[len(prefix) :]


def verify_object(body: Dict[str, Any], checks: List[Dict[str, Any]]) -> Optional[bytes]:
    file_id = str(body.get("fileID") or "")
    path = local_path(file_id)
    if path is None:
        checks.append({"name": "readback", "ok": None, "detail": "非 local fileID，未做字节回读"})
        return None
    exists = path.is_file()
    checks.append({"name": "file_exists", "ok": exists, "detail": str(path)})
    if not exists:
        return None
    data = path.read_bytes()
    checks.append(
        {
            "name": "readback_bytes",
            "ok": len(data) == body.get("bytes"),
            "detail": "{0} vs {1}".format(len(data), body.get("bytes")),
        }
    )
    return data


def _ok(checks: List[Dict[str, Any]], name: str, condition: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(condition), "detail": detail})


def check_parse_schema(payload: Dict[str, Any], checks: List[Dict[str, Any]]) -> None:
    try:
        import jsonschema

        schema = json.loads(
            (ROOT / "contract" / "parse_response.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.validate(payload, schema)
    except Exception as exc:  # noqa: BLE001 - report the first schema failure
        _ok(checks, "parse_schema", False, type(exc).__name__ + ": " + str(exc)[:160])
    else:
        _ok(checks, "parse_schema", True, "")


def case_image_ok() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(image_sample())
    checks: List[Dict[str, Any]] = []
    _ok(checks, "parse_200", parsed["status"] == 200, str(parsed["status"]))
    body = parsed["body"]
    if parsed["status"] == 200:
        check_parse_schema(body, checks)
    item = find_item(body, "image")
    _ok(checks, "parse_has_image", item is not None, str(body.get("item_count")))
    if parsed["status"] != 200 or item is None:
        return checks, {"parse": parsed}
    result = stage(task_id_for(body), int(item["index"]))
    stage_body = result["body"]
    _ok(checks, "stage_200", result["status"] == 200, str(result["status"]))
    _ok(checks, "stage_ok", stage_body.get("ok") is True, "")
    _ok(checks, "fileID_cloud", str(stage_body.get("fileID", "")).startswith("cloud://"), "")
    _ok(checks, "kind_image", stage_body.get("kind") == "image", str(stage_body.get("kind")))
    _ok(checks, "ext_nonempty", bool(stage_body.get("ext")), str(stage_body.get("ext")))
    _ok(checks, "bytes_positive", int(stage_body.get("bytes") or 0) > 0, str(stage_body.get("bytes")))
    data = verify_object(stage_body, checks)
    if data:
        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(data)) as image:
                _ok(checks, "pillow_decode", True, image.format or "")
        except Exception as exc:  # noqa: BLE001
            _ok(checks, "pillow_decode", False, type(exc).__name__)
    return checks, {"parse": parsed, "stage": result}


def case_video_ok() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    checks: List[Dict[str, Any]] = []
    _ok(checks, "parse_200", parsed["status"] == 200, str(parsed["status"]))
    body = parsed["body"]
    if parsed["status"] == 200:
        check_parse_schema(body, checks)
    item = find_item(body, "video")
    _ok(checks, "parse_has_video", item is not None, str(body.get("item_count")))
    if parsed["status"] != 200 or item is None:
        return checks, {"parse": parsed}
    result = stage(task_id_for(body), int(item["index"]))
    stage_body = result["body"]
    _ok(checks, "stage_200", result["status"] == 200, str(result["status"]))
    _ok(checks, "kind_video", stage_body.get("kind") == "video", str(stage_body.get("kind")))
    _ok(checks, "ext_mp4", stage_body.get("ext") == "mp4", str(stage_body.get("ext")))
    _ok(checks, "under_60s", result["elapsed_ms"] <= 60000, str(result["elapsed_ms"]))
    verify_object(stage_body, checks)
    return checks, {"parse": parsed, "stage": result}


def case_webp_to_jpg() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    url = os.getenv("STAGE_WEBP_URL", "").strip() or os.getenv("XHS_NOTE_1", "").strip()
    if not url:
        raise Blocked("缺少 STAGE_WEBP_URL / XHS_NOTE_1")
    parsed = parse_url(url)
    checks: List[Dict[str, Any]] = []
    item = None
    for candidate in parsed["body"].get("items") or []:
        if candidate.get("type") != "image":
            continue
        if str(candidate.get("ext") or "").lower() == "webp" or str(
            candidate.get("remoteUrl") or ""
        ).lower().endswith(".webp"):
            item = candidate
            break
    if item is None:
        item = find_item(parsed["body"], "image")
    _ok(checks, "parse_image", item is not None, str(parsed["body"].get("item_count")))
    if parsed["status"] != 200 or item is None:
        return checks, {"parse": parsed}
    result = stage(task_id_for(parsed["body"]), int(item["index"]))
    body = result["body"]
    _ok(checks, "stage_200", result["status"] == 200, str(result["status"]))
    _ok(checks, "ext_jpg", body.get("ext") == "jpg", str(body.get("ext")))
    data = verify_object(body, checks)
    if data is not None:
        _ok(checks, "jpeg_magic", data[:3] == b"\xff\xd8\xff", data[:3].hex())
        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(data)) as image:
                _ok(checks, "jpeg_decode", image.format == "JPEG", image.format or "")
        except Exception as exc:  # noqa: BLE001
            _ok(checks, "jpeg_decode", False, type(exc).__name__)
    return checks, {"parse": parsed, "stage": result}


def case_too_large() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    checks: List[Dict[str, Any]] = []
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    result = stage(task_id_for(parsed["body"]), int(item["index"]))
    body = result["body"]
    error = body.get("error") or {}
    _ok(checks, "http_413", result["status"] == 413, str(result["status"]))
    _ok(checks, "code_TOO_LARGE", error.get("code") == "TOO_LARGE", str(error.get("code")))
    _ok(checks, "no_fileID", "fileID" not in body, "")
    return checks, {"parse": parsed, "stage": result, "server_env": "STAGE_FAKE_CONTENT_LENGTH"}


def case_expired() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    task_id = os.getenv("STAGE_EXPIRED_TASK_ID", "").strip() or "st_" + "0" * 24
    result = stage(task_id, 0)
    body = result["body"]
    error = body.get("error") or {}
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_410", result["status"] == 410, str(result["status"]))
    _ok(checks, "code_STAGE_EXPIRED", error.get("code") == "STAGE_EXPIRED", str(error.get("code")))
    _ok(checks, "no_fileID", "fileID" not in body, "")
    return checks, {"stage": result}


def case_expired_ttl() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    task_id = task_id_for(parsed["body"])
    time.sleep(2.0)
    result = stage(task_id, int(item["index"]))
    body = result["body"]
    error = body.get("error") or {}
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_410", result["status"] == 410, str(result["status"]))
    _ok(checks, "code_STAGE_EXPIRED", error.get("code") == "STAGE_EXPIRED", str(error.get("code")))
    _ok(checks, "no_fileID", "fileID" not in body, "")
    return checks, {"parse": parsed, "stage": result, "server_env": "STAGE_TASK_TTL_S=1"}


def case_not_ready() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    before = set(glob.glob("/tmp/renlink-stage-*"))
    result = stage(task_id_for(parsed["body"]), int(item["index"]))
    after = set(glob.glob("/tmp/renlink-stage-*"))
    body = result["body"]
    error = body.get("error") or {}
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_503", result["status"] == 503, str(result["status"]))
    _ok(checks, "code_STAGE_NOT_READY", error.get("code") == "STAGE_NOT_READY", str(error.get("code")))
    _ok(checks, "no_cloud_id", "cloud://" not in json.dumps(body), "")
    _ok(checks, "no_new_tmp", before == after, "{0} -> {1}".format(len(before), len(after)))
    return checks, {"parse": parsed, "stage": result, "server_env": "STAGE_STORE=cos"}


def case_idempotent() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    task_id = task_id_for(parsed["body"])
    first = stage(task_id, int(item["index"]))
    first_path = local_path(str((first["body"] or {}).get("fileID") or ""))
    first_mtime = first_path.stat().st_mtime_ns if first_path and first_path.exists() else None
    second = stage(task_id, int(item["index"]))
    second_path = local_path(str((second["body"] or {}).get("fileID") or ""))
    second_mtime = second_path.stat().st_mtime_ns if second_path and second_path.exists() else None
    checks: List[Dict[str, Any]] = []
    _ok(checks, "first_200", first["status"] == 200, str(first["status"]))
    _ok(checks, "second_200", second["status"] == 200, str(second["status"]))
    _ok(
        checks,
        "same_fileID",
        first["body"].get("fileID") == second["body"].get("fileID"),
        str(first["body"].get("fileID")),
    )
    _ok(checks, "object_not_rewritten", first_mtime == second_mtime, str(first_mtime))
    return checks, {"parse": parsed, "first": first, "second": second}


def case_bad_index() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    task_id = task_id_for(parsed["body"])
    results = {
        "negative": stage(task_id, -1),
        "out_of_range": stage(task_id, 9999),
    }
    checks: List[Dict[str, Any]] = []
    for name, result in results.items():
        error = (result["body"] or {}).get("error") or {}
        _ok(checks, name + "_http_400", result["status"] == 400, str(result["status"]))
        _ok(checks, name + "_STAGE_FAILED", error.get("code") == "STAGE_FAILED", str(error.get("code")))
        _ok(checks, name + "_not_retryable", error.get("retryable") is False, str(error.get("retryable")))
    return checks, {"parse": parsed, "results": results}


def case_response_shape() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    result = stage(task_id_for(parsed["body"]), int(item["index"]))
    body = result["body"]
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_200", result["status"] == 200, str(result["status"]))
    _ok(
        checks,
        "exact_keys",
        set(body.keys()) == {"ok", "fileID", "kind", "ext", "bytes"},
        str(sorted(body.keys())),
    )
    _ok(checks, "body_le_1024000", result["bytes"] <= 1024000, str(result["bytes"]))
    dumped = json.dumps(body, ensure_ascii=False)
    _ok(checks, "no_tmp_path", "/tmp/" not in dumped, "")
    _ok(checks, "no_base64", "base64" not in dumped.lower(), "")
    return checks, {"parse": parsed, "stage": result}


def _tmp_files() -> int:
    return sum(1 for path in glob.glob("/tmp/renlink-stage-*") if os.path.isfile(path))


def case_tmp_clean() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    task_id = task_id_for(parsed["body"])
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    before = _tmp_files()
    success = stage(task_id, int(item["index"]))
    after_success = _tmp_files()
    failure = stage(task_id, 9999)
    after_failure = _tmp_files()
    checks: List[Dict[str, Any]] = []
    _ok(checks, "success_200", success["status"] == 200, str(success["status"]))
    _ok(checks, "after_success_zero", after_success == 0, str(after_success))
    _ok(checks, "after_failure_zero", after_failure == 0, str(after_failure))
    _ok(checks, "before", before >= 0, str(before))
    return checks, {"parse": parsed, "success": success, "failure": failure}


def case_multi_index() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(image_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    items = [item for item in parsed["body"].get("items") or [] if item.get("type") == "image"]
    if len(items) < 2:
        raise Blocked("图片清单少于 2 项: {0}".format(len(items)))
    task_id = task_id_for(parsed["body"])
    indexes = [int(item["index"]) for item in items[: min(3, len(items))]]
    results = [stage(task_id, index) for index in indexes]
    file_ids = [str((result["body"] or {}).get("fileID") or "") for result in results]
    checks: List[Dict[str, Any]] = []
    _ok(checks, "all_200", all(result["status"] == 200 for result in results), str([r["status"] for r in results]))
    _ok(checks, "distinct_fileIDs", len(set(file_ids)) == len(file_ids), str(file_ids))
    for result in results:
        verify_object(result["body"], checks)
    return checks, {"parse": parsed, "indexes": indexes, "results": results}


def case_user_cookie() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    result = stage("st_" + "0" * 24, 0, {"cookie": "sessionid=should-not-be-read"})
    body = result["body"]
    error = body.get("error") or {}
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_400", result["status"] == 400, str(result["status"]))
    _ok(checks, "code_INVALID_REQUEST", error.get("code") == "INVALID_REQUEST", str(error.get("code")))
    return checks, {"stage": result}


def case_timeout() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = parse_url(video_sample())
    if parsed["status"] != 200:
        raise Blocked("parse 未成功: {0}".format(parsed["status"]))
    item = find_item(parsed["body"], "video")
    if item is None:
        raise Blocked("清单没有 video 项")
    before = _tmp_files()
    result = stage(task_id_for(parsed["body"]), int(item["index"]))
    after = _tmp_files()
    body = result["body"]
    error = body.get("error") or {}
    checks: List[Dict[str, Any]] = []
    _ok(checks, "http_504", result["status"] == 504, str(result["status"]))
    _ok(checks, "code_TIMEOUT", error.get("code") == "TIMEOUT", str(error.get("code")))
    _ok(checks, "tmp_clean", after == 0, "{0} -> {1}".format(before, after))
    return checks, {"parse": parsed, "stage": result, "server_env": "STAGE_FAKE_DELAY_MS"}


def case_real_video_and_image() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    checks1, detail1 = case_video_ok()
    checks2, detail2 = case_image_ok()
    return checks1 + checks2, {"video": detail1, "image": detail2}


CASES = {
    "image-ok": case_image_ok,
    "video-ok": case_video_ok,
    "webp-to-jpg": case_webp_to_jpg,
    "too-large": case_too_large,
    "expired": case_expired,
    "expired-ttl": case_expired_ttl,
    "not-ready": case_not_ready,
    "idempotent": case_idempotent,
    "bad-index": case_bad_index,
    "response-shape": case_response_shape,
    "tmp-clean": case_tmp_clean,
    "multi-index": case_multi_index,
    "user-cookie": case_user_cookie,
    "timeout": case_timeout,
    "real-video-and-image": case_real_video_and_image,
}

ALL_LOCAL = [
    "video-ok",
    "image-ok",
    "webp-to-jpg",
    "idempotent",
    "bad-index",
    "response-shape",
    "tmp-clean",
    "multi-index",
    "user-cookie",
    "real-video-and-image",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="", help="one case or 'all'")
    parser.add_argument("--out", default="", help="evidence directory")
    args = parser.parse_args()
    names = ALL_LOCAL if args.case in ("all", "") else [args.case]
    unknown = [name for name in names if name not in CASES]
    if unknown:
        print("unknown case: {0}".format(unknown), file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else (
        DEFAULT_OUT / ("run-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    blocked = 0
    for name in names:
        try:
            checks, detail = CASES[name]()
        except Blocked as exc:
            blocked += 1
            record = {"case": name, "status": "BLOCKED", "reason": str(exc), "at": _now()}
            print("{0}: BLOCKED ({1})".format(name, exc))
        else:
            failed = [check for check in checks if check["ok"] is False]
            status = "PASS" if not failed else "FAIL"
            if failed:
                failures += 1
            record = {
                "case": name,
                "status": status,
                "at": _now(),
                "base": BASE,
                "store": os.getenv("STAGE_SERVER_STORE") or os.getenv("STAGE_STORE", "local"),
                "checks": checks,
                "detail": detail,
            }
            print("{0}: {1}".format(name, status))
            for check in failed:
                print("  - {0}: {1}".format(check["name"], check["detail"]))
        (out_dir / ("case-" + name + ".json")).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    records = []
    for path in sorted(out_dir.glob("case-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        records.append(
            {
                "case": record.get("case"),
                "status": record.get("status"),
                "file": path.name,
            }
        )
    summary = {
        "at": _now(),
        "store": os.getenv("STAGE_SERVER_STORE") or os.getenv("STAGE_STORE", "local"),
        "case_files": len(records),
        "cases": records,
        "failures": sum(1 for record in records if record["status"] == "FAIL"),
        "blocked": sum(1 for record in records if record["status"] == "BLOCKED"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("evidence: {0}".format(out_dir))
    if failures:
        return 1
    if blocked:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
