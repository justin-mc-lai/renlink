#!/usr/bin/env python3
"""l4-session-egress HTTP smoke: TC-001..TC-010.

Each case starts its own uvicorn process with an isolated environment, drives
the real HTTP surface, and writes a JSON file plus a sanitized server log.
Cookie values are never written to evidence.

Usage:
  .venv/bin/python ops/session_smoke.py
  .venv/bin/python ops/session_smoke.py --out docs/beacon/.../evidence/run-...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = ROOT / "container"
DEFAULT_OUT = (
    ROOT
    / "docs/beacon/v0.1.0/features/l4-session-egress/evidence"
    / datetime.now().strftime("run-%Y%m%d-%H%M")
)
DOUYIN_URL = "https://www.douyin.com/video/7705367833957403946"
SECRET = "sessionid=SMOKESECRET123456; UIFID=SMOKESECRETABC"
CLEAN_KEYS = (
    "SESSION_POOL_SOURCE",
    "SESSION_COS_PREFIX",
    "SESSION_DB_TABLE",
    "SESSION_DB_DSN",
    "SESSION_DB_PATH",
    "COS_BUCKET",
    "COS_REGION",
    "COS_ENDPOINT",
    "COS_SECRET_ID",
    "COS_SECRET_KEY",
    "COS_SESSION_TOKEN",
    "COS_CREDENTIAL_URL",
    "TENCENTCLOUD_SECRETID",
    "TENCENTCLOUD_SECRETKEY",
    "DOUYIN_COOKIE",
    "XHS_COOKIE",
    "DOUYIN_COOKIE_LAST_REFRESH",
    "XHS_COOKIE_LAST_REFRESH",
    "PARSE_STUB_COOKIE_EXPIRED",
    "PARSE_STUB_DOUYIN_COOKIE_EXPIRED",
    "PARSE_STUB_XHS_COOKIE_EXPIRED",
    "RENLINK_SESSION_TTL_S",
    "RENLINK_SESSION_RELOAD",
    "RENLINK_SESSION_LOCAL_POOL",
    "RENLINK_SESSION_MAX_AGE_S",
    "EGRESS_PROXY",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http(
    port: int, path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 15.0
) -> Tuple[int, Any, str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"content-type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, json.loads(raw or "{}"), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw or "{}")
        except ValueError:
            parsed = {}
        return exc.code, parsed, raw


class Server:
    def __init__(self, name: str, env: Dict[str, str], log_dir: Path) -> None:
        self.name = name
        self.port = _free_port()
        self.log_path = log_dir / f"server-{name}.log"
        full = {key: value for key, value in os.environ.items() if key not in CLEAN_KEYS}
        full.update(env)
        full["PYTHONUNBUFFERED"] = "1"
        full["PARSE_RATE_LIMIT_PER_MIN"] = "0"
        full["ENABLE_OBSCURA"] = "0"
        self.log = self.log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "info",
            ],
            cwd=str(CONTAINER),
            env=full,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )

    def wait(self, timeout: float = 25.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited with {self.proc.returncode}")
            try:
                status, body, _ = _http(self.port, "/health", timeout=2.0)
                if status == 200 and body.get("ok"):
                    return
            except Exception:  # noqa: BLE001 - cold start
                pass
            time.sleep(0.2)
        raise RuntimeError("server did not become healthy")

    def get(self, path: str) -> Tuple[int, Any, str]:
        return _http(self.port, path)

    def post(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Any, str]:
        return _http(self.port, path, payload)

    def close(self) -> str:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass
        self.log.close()
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""


def _sanitize(text: str, secrets: List[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
            for part in secret.split(";"):
                value = part.strip().split("=", 1)[-1].strip()
                if len(value) >= 8:
                    text = text.replace(value, "[REDACTED]")
    return text


def _stamp(age_s: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat(timespec="seconds")


def _write_pool(root: Path, platform: str, cookie: str, age_s: int = 0, max_age_s: int = 86400) -> Path:
    root.mkdir(parents=True, exist_ok=True)
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
    os.chmod(path, 0o600)
    return path


class Case:
    def __init__(self, name: str, out: Path) -> None:
        self.name = name
        self.out = out
        self.checks: List[Dict[str, Any]] = []
        self.servers: List[Server] = []
        self.logs: List[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def server(self, env: Dict[str, str]) -> Server:
        server = Server(self.name, env, self.out)
        try:
            server.wait()
        except Exception:
            text = server.close()
            self.logs.append(text)
            raise
        self.servers.append(server)
        return server

    def finish(self) -> str:
        for server in self.servers:
            self.logs.append(server.close())
        status = "PASS" if self.checks and all(item["ok"] for item in self.checks) else "FAIL"
        payload = {"case": self.name, "status": status, "checks": self.checks}
        (self.out / f"case-{self.name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log = _sanitize("\n".join(self.logs), [SECRET])
        (self.out / f"server-{self.name}.log").write_text(log, encoding="utf-8")
        return status


def _base_env(source: str = "env") -> Dict[str, str]:
    return {"SESSION_POOL_SOURCE": source, "RENLINK_SESSION_TTL_S": "60"}


def tc001(case: Case, tmp: Path) -> None:
    pool = tmp / "pool-1"
    _write_pool(pool, "douyin", "pool=1", age_s=10)
    stamp = json.loads((pool / "douyin.json").read_text(encoding="utf-8"))["refreshed_at"]
    server = case.server(
        {
            **_base_env(),
            "RENLINK_SESSION_LOCAL_POOL": str(pool),
            "DOUYIN_COOKIE": "env=1",
        }
    )
    status, health, _ = server.get("/health")
    douyin = health["platforms"]["douyin"]
    case.check("health-200", status == 200)
    case.check("pool-record-preferred", douyin["cookie_status"] == "fresh" and douyin["last_refresh"] == stamp, str(douyin))

    server2 = case.server({**_base_env(), "DOUYIN_COOKIE": "env=1"})
    _, health2, _ = server2.get("/health")
    case.check(
        "env-fallback-usable",
        health2["platforms"]["douyin"]["cookie_status"] == "fresh"
        and health2["platforms"]["douyin"]["source"] == "env",
        str(health2["platforms"]["douyin"]),
    )

    server3 = case.server(_base_env())
    status3, body3, _ = server3.post("/parse", {"url": DOUYIN_URL})
    case.check(
        "both-missing-503",
        status3 == 503 and body3.get("error", {}).get("code") == "COOKIE_EXPIRED",
        json.dumps(body3, ensure_ascii=False),
    )


def tc002(case: Case) -> None:
    server = case.server(
        {"SESSION_POOL_SOURCE": "cos", "COS_BUCKET": "", "DOUYIN_COOKIE": "sessionid=fallback; UIFID=x"}
    )
    _, health, raw = server.get("/health")
    douyin = health["platforms"]["douyin"]
    case.check("cos-fallback-source-env", douyin["source"] == "env", str(douyin))
    case.check("cos-fallback-fresh", douyin["cookie_status"] == "fresh", str(douyin))
    case.check("no-cookie-value", "sessionid=fallback" not in raw)


def tc003(case: Case) -> None:
    server = case.server(
        {
            **_base_env(),
            "DOUYIN_COOKIE": "sessionid=expired; UIFID=x",
            "PARSE_STUB_COOKIE_EXPIRED": "douyin",
        }
    )
    _, health, _ = server.get("/health")
    case.check("health-expired", health["platforms"]["douyin"]["cookie_status"] == "expired")
    started = time.perf_counter()
    status, body, _ = server.post("/parse", {"url": DOUYIN_URL})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    error = body.get("error", {})
    case.check("parse-503", status == 503, str(status))
    case.check("code-cookie-expired", error.get("code") == "COOKIE_EXPIRED", json.dumps(body, ensure_ascii=False))
    case.check("retryable-true", error.get("retryable") is True)
    case.check("no-upstream-wait", elapsed_ms < 1000, f"{elapsed_ms}ms")


def tc004(case: Case) -> None:
    direct = case.server({**_base_env(), "EGRESS_PROXY": ""})
    _, health, _ = direct.get("/health")
    case.check("direct-mode", health["egress_proxy"] == "direct", str(health["egress_proxy"]))

    proxied = case.server({**_base_env(), "EGRESS_PROXY": "http://127.0.0.1:7890"})
    _, health2, raw = proxied.get("/health")
    case.check("proxy-mode", health2["egress_proxy"] == "proxy", str(health2["egress_proxy"]))
    case.check("proxy-not-echoed", "127.0.0.1:7890" not in raw)


def tc005(case: Case) -> None:
    server = case.server({**_base_env(), "DOUYIN_COOKIE": SECRET, "XHS_COOKIE": "web_session=OTHERSECRET"})
    status, health, raw = server.get("/health")
    case.check("health-200", status == 200)
    for platform in ("douyin", "xhs"):
        entry = health["platforms"][platform]
        case.check(
            f"{platform}-fields",
            set(entry) == {"cookie_status", "last_refresh", "source", "pool_age_s"},
            str(entry),
        )
    case.check("top-egress", "egress_proxy" in health)
    case.check("no-douyin-cookie", "SMOKESECRET" not in raw)
    case.check("no-xhs-cookie", "OTHERSECRET" not in raw)


def tc006(case: Case) -> None:
    server = case.server({**_base_env(), "DOUYIN_COOKIE": "a=b"})
    status, body, _ = server.post("/parse", {"url": DOUYIN_URL, "cookie": SECRET})
    case.check("parse-400", status == 400, str(status))
    case.check("parse-invalid", body.get("error", {}).get("code") == "INVALID_REQUEST")

    status2, body2, _ = server.post(
        "/stage", {"task_id": "st_" + "0" * 24, "index": 0, "cookie": SECRET}
    )
    case.check("stage-400", status2 == 400, str(status2))
    case.check("stage-invalid", body2.get("error", {}).get("code") == "INVALID_REQUEST")

    _, openapi, _ = server.get("/openapi.json")
    case.check(
        "no-cookie-write-route",
        not [path for path in openapi.get("paths", {}) if "cookie" in path.lower()],
    )


def _refresh(pool: Path, env_file: Path, cookie: str) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key not in CLEAN_KEYS}
    env["DOUYIN_COOKIE"] = cookie
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "ops" / "refresh_cookie.py"),
            "--from-env",
            "--env-file",
            str(env_file),
            "--no-env-file",
            "--pool-dir",
            str(pool),
            "douyin",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def tc007(case: Case, tmp: Path) -> None:
    pool = tmp / "pool-refresh"
    _write_pool(pool, "douyin", "old=1", age_s=7200, max_age_s=60)
    server = case.server(
        {
            "SESSION_POOL_SOURCE": "env",
            "RENLINK_SESSION_TTL_S": "1",
            "RENLINK_SESSION_LOCAL_POOL": str(pool),
        }
    )
    _, before, _ = server.get("/health")
    case.check("before-expired", before["platforms"]["douyin"]["cookie_status"] == "expired")
    old_stamp = before["platforms"]["douyin"]["last_refresh"]

    result = _refresh(pool, tmp / "missing.env", "sessionid=refresh; UIFID=x")
    case.check("refresh-exit-0", result.returncode == 0, result.stderr[-400:])
    time.sleep(1.3)
    _, after, _ = server.get("/health")
    douyin = after["platforms"]["douyin"]
    case.check("after-fresh", douyin["cookie_status"] == "fresh", str(douyin))
    case.check("last-refresh-updated", douyin["last_refresh"] != old_stamp, f"{old_stamp} -> {douyin['last_refresh']}")

    record = pool / "douyin.json"
    before_failure = record.read_text(encoding="utf-8")
    bad_pool = tmp / "not-a-directory"
    bad_pool.write_text("x", encoding="utf-8")
    failed = _refresh(bad_pool, tmp / "missing.env", "sessionid=refresh; UIFID=x")
    case.check("write-failure-nonzero", failed.returncode != 0, str(failed.returncode))
    case.check("pool-unchanged", record.read_text(encoding="utf-8") == before_failure)


def tc008(case: Case, tmp: Path) -> None:
    pool = tmp / "pool-freshness"
    _write_pool(pool, "douyin", "fresh=1", age_s=5, max_age_s=86400)
    server = case.server(
        {"SESSION_POOL_SOURCE": "env", "RENLINK_SESSION_TTL_S": "1", "RENLINK_SESSION_LOCAL_POOL": str(pool)}
    )
    _, health, _ = server.get("/health")
    case.check("fresh", health["platforms"]["douyin"]["cookie_status"] == "fresh")
    case.check("fresh-age", isinstance(health["platforms"]["douyin"]["pool_age_s"], int))

    _write_pool(pool, "douyin", "stale=1", age_s=7200, max_age_s=60)
    time.sleep(1.3)
    _, health2, _ = server.get("/health")
    case.check("expired", health2["platforms"]["douyin"]["cookie_status"] == "expired")

    (pool / "douyin.json").unlink()
    time.sleep(1.3)
    _, health3, _ = server.get("/health")
    missing = health3["platforms"]["douyin"]
    case.check("missing", missing["cookie_status"] == "missing" and missing["source"] == "missing", str(missing))


def tc009(case: Case) -> None:
    server = case.server({**_base_env(), "DOUYIN_COOKIE": SECRET})
    _, health, health_raw = server.get("/health")
    status, error_body, error_raw = server.post("/parse", {"url": DOUYIN_URL, "cookie": SECRET})
    log = ""
    for item in case.servers:
        item.proc.terminate()
        item.proc.wait(timeout=10)
        item.log.close()
        log += item.log_path.read_text(encoding="utf-8", errors="replace")
    case.servers.clear()
    full = SECRET + " SMOKESECRET123456 SMOKESECRETABC"
    leaks = sum(part in (health_raw + error_raw + log) for part in full.split())
    case.check("error-400", status == 400)
    case.check("health-no-cookie", "SMOKESECRET" not in health_raw)
    case.check("error-no-cookie", "SMOKESECRET" not in error_raw)
    case.check("log-full-cookie-hits-0", leaks == 0, f"hits={leaks}")
    case.check("log-redacted-prefix", "sess***" in log, "prefix present")
    case.logs.append(log)


def tc010(case: Case, tmp: Path) -> None:
    pool = tmp / "pool-cache"
    path = _write_pool(pool, "douyin", "A=1", age_s=0)
    server = case.server(
        {"SESSION_POOL_SOURCE": "env", "RENLINK_SESSION_TTL_S": "5", "RENLINK_SESSION_LOCAL_POOL": str(pool)}
    )
    stamps = set()
    for _ in range(10):
        _, health, _ = server.get("/health")
        stamps.add(health["platforms"]["douyin"]["last_refresh"])
    case.check("ten-health-one-read", len(stamps) == 1, str(stamps))
    first = next(iter(stamps))

    time.sleep(1.1)
    _write_pool(pool, "douyin", "B=1", age_s=0)
    _, cached, _ = server.get("/health")
    case.check("cache-holds-within-ttl", cached["platforms"]["douyin"]["last_refresh"] == first)
    time.sleep(5.4)
    _, fresh, _ = server.get("/health")
    case.check(
        "reload-after-ttl",
        fresh["platforms"]["douyin"]["last_refresh"] != first,
        f"{first} -> {fresh['platforms']['douyin']['last_refresh']}",
    )
    case.check("pool-file-0600", oct(path.stat().st_mode & 0o777) == "0o600")


def main() -> int:
    parser = argparse.ArgumentParser(description="l4 session smoke")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="renlink-session-smoke-"))

    runners = [
        ("TC-001", lambda case: tc001(case, tmp)),
        ("TC-002", lambda case: tc002(case)),
        ("TC-003", lambda case: tc003(case)),
        ("TC-004", lambda case: tc004(case)),
        ("TC-005", lambda case: tc005(case)),
        ("TC-006", lambda case: tc006(case)),
        ("TC-007", lambda case: tc007(case, tmp)),
        ("TC-008", lambda case: tc008(case, tmp)),
        ("TC-009", lambda case: tc009(case)),
        ("TC-010", lambda case: tc010(case, tmp)),
    ]
    results = []
    for name, runner in runners:
        case = Case(name, out)
        try:
            runner(case)
        except Exception as exc:  # noqa: BLE001 - a case failure is evidence
            case.check("exception", False, f"{type(exc).__name__}: {exc}")
        status = case.finish()
        results.append({"case": name, "status": status, "file": f"case-{name}.json"})
        print(f"{name} {status}")

    summary = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "http-local",
        "cases": results,
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": sum(1 for item in results if item["status"] == "FAIL"),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
