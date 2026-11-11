#!/usr/bin/env python3
"""Run one l1-parser-core TC in an isolated server (C plan).

Usage: python3 ops/tc_run.py TC-001

Each run gets its own free port and its own uvicorn process; PARSE_BASE from
the caller is never inherited. Per-TC switches are passed only to the child
process that needs them. TC-023/TC-024 run in a freshly built container image
because obscura exists only inside the image.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = ROOT / "container"
SAMPLES_PATH = ROOT / "ops" / "samples" / "l1.json"
EVIDENCE_DIR = (
    ROOT / "docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-20261111"
)
COOKIE_FILE = Path.home() / ".config" / "renlink" / "cookies.env"
PYTHON = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
CLEAN_PREFIXES = (
    "PARSE_", "RENLINK_", "ENABLE_OBSCURA", "PLAYWRIGHT_CDP", "OBSCURA_",
    "SMOKE_", "SESSION_", "COS_", "TENCENTCLOUD_",
)
CASE_ENV: Dict[str, Dict[str, Dict[str, str]]] = {
    "TC-009": {"server": {"PARSE_STUB_COOKIE_EXPIRED": "douyin"}},
    "TC-013": {"server": {"PARSE_UPSTREAM_DELAY_MS": "13000"}},
    "TC-020": {"server": {"RENLINK_DISABLE_CACHE": "1"}},
    "TC-021": {"server": {"RENLINK_DROP_ARGUS_HEADER": "1"}},
    "TC-022": {"server": {"PARSE_UPSTREAM_DELAY_MS": "13000"}},
    "TC-023": {"docker": True},
    "TC-024": {"docker": True},
}
MARKER_KEYS = (
    "PARSE_STUB_COOKIE_EXPIRED", "PARSE_UPSTREAM_DELAY_MS",
    "RENLINK_DISABLE_CACHE", "RENLINK_DROP_ARGUS_HEADER", "ENABLE_OBSCURA",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _clean_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(CLEAN_PREFIXES)}


def _load_cookies() -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        for line in COOKIE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    except OSError:
        return {}
    return values


def _samples() -> Dict[str, str]:
    try:
        data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    out: Dict[str, str] = {}
    for key, value in data.items():
        out[key] = "" if value is None else str(value)
    for key in list(out):
        if os.environ.get(key):
            out[key] = os.environ[key]
    return out


def _smoke_cases() -> Dict[str, Dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("l1_smoke", ROOT / "ops" / "smoke.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return {case["tc"]: case for case in module.CASES}


def _health_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            return resp.status == 200 and body.get("ok") is True
    except Exception:  # noqa: BLE001
        return False


def _wait_health(port: int, proc: Optional[subprocess.Popen] = None, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"server exited with {proc.returncode}")
        if _health_ok(port):
            return
        time.sleep(0.2)
    raise RuntimeError("server did not become healthy")


def _server_env(extra: Dict[str, str]) -> Dict[str, str]:
    env = _clean_env()
    env.update(_load_cookies())
    env["PARSE_RATE_LIMIT_PER_MIN"] = "0"
    env["RENLINK_SESSION_MAX_AGE_S"] = "999999999"
    env["PYTHONUNBUFFERED"] = "1"
    env.update(extra)
    return env


def _run_smoke(tc: str, port: int, markers: Dict[str, str], container_id: str = "") -> Tuple[int, str, Dict[str, Any]]:
    tmp = Path(tempfile.mkdtemp(prefix="l1-tc-"))
    env = _clean_env()
    env.update(_samples())
    env["PARSE_BASE"] = f"http://127.0.0.1:{port}"
    env.update(markers)
    if container_id:
        env["SMOKE_CONTAINER_ID"] = container_id
    proc = subprocess.run(
        [PYTHON, "ops/smoke.py", "--case", tc, "--out", str(tmp)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
    )
    payload: Dict[str, Any] = {}
    path = tmp / f"smoke-{tc}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    shutil.rmtree(tmp, ignore_errors=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip(), payload


def _write_evidence(tc: str, exit_code: int, base: str, stdout: str, payload: Dict[str, Any], blocked: str = "") -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "tc": tc,
        "command": f"python3 ops/tc_run.py {tc}",
        "exitCode": exit_code,
        "base": base,
        "stdout": stdout,
    }
    if blocked:
        doc["blockedReason"] = blocked
    else:
        doc["smoke"] = payload
    (EVIDENCE_DIR / f"{tc}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _docker_image() -> str:
    head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True).strip()
    tag = f"renlink-l1:qa-c-{head}"
    exists = subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0
    if not exists:
        print(f"[tc_run] building {tag} from HEAD {head}", file=sys.stderr)
        subprocess.run(["docker", "build", "-t", tag, "."], cwd=str(ROOT), check=True)
    return tag


def _run_docker(tc: str, markers: Dict[str, str]) -> Tuple[int, str, Dict[str, Any], str]:
    image = _docker_image()
    port = _free_port()
    name = f"l1-tc-{tc.lower()}-{os.getpid()}"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    cmd = [
        "docker", "run", "-d", "--name", name,
        "-p", f"127.0.0.1:{port}:8080",
        "-e", "PARSE_RATE_LIMIT_PER_MIN=0",
        "-e", "RENLINK_SESSION_MAX_AGE_S=999999999",
        "-e", "ENABLE_OBSCURA=1",
        "-e", "PLAYWRIGHT_CDP=ws://127.0.0.1:9222",
    ]
    if COOKIE_FILE.exists():
        cmd += ["--env-file", str(COOKIE_FILE)]
    cmd.append(image)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        _wait_health(port)
        return (*_run_smoke(tc, port, markers, container_id=name), name)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Run one l1-parser-core TC isolated")
    parser.add_argument("tc", help="TC-001 … TC-024")
    args = parser.parse_args(argv)
    tc = args.tc.upper()
    cases = _smoke_cases()
    if tc not in cases:
        print(f"unknown TC: {tc}", file=sys.stderr)
        return 2

    samples = _samples()
    missing = [key for key in cases[tc].get("requires", []) if not samples.get(key)]
    spec = CASE_ENV.get(tc, {})
    markers: Dict[str, str] = {
        key: value for key, value in spec.get("server", {}).items() if key in MARKER_KEYS
    }
    if spec.get("docker"):
        markers["ENABLE_OBSCURA"] = "1"

    if missing:
        reason = "缺少样本: " + ", ".join(missing)
        if tc == "TC-023":
            reason = "AC-017 在本机不可达，缺 XHS_NOTE_1"
        print(f"{tc} BLOCKED ({reason})")
        _write_evidence(tc, 3, "", f"{tc} BLOCKED ({reason})", {}, blocked=reason)
        return 3

    proc = None
    container_name = ""
    base = ""
    try:
        if spec.get("docker"):
            rc, stdout, payload, container_name = _run_docker(tc, markers)
            base = "docker://" + container_name
        else:
            port = _free_port()
            base = f"http://127.0.0.1:{port}"
            log = tempfile.NamedTemporaryFile(prefix="l1-tc-", suffix=".log", delete=False)
            proc = subprocess.Popen(
                [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", str(port), "--log-level", "info"],
                cwd=str(CONTAINER), env=_server_env(spec.get("server", {})),
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            _wait_health(port, proc)
            rc, stdout, payload = _run_smoke(tc, port, markers)
        _write_evidence(tc, rc, base, stdout, payload)
        print(stdout)
        return rc
    except Exception as exc:  # noqa: BLE001 - report, keep smoke exit semantics
        message = f"{tc} ERROR {type(exc).__name__}: {exc}"
        print(message, file=sys.stderr)
        _write_evidence(tc, 1, base, message, {})
        return 1
    finally:
        if proc is not None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:  # noqa: BLE001
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
