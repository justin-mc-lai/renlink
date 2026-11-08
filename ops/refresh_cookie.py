#!/usr/bin/env python3
"""Operator cookie-pool refresh (l4).

Opens each platform in headless Chromium with the current jar, waits for the
security cookies (UIFID / UIFID_TEMP for Douyin, web_session for XHS), then
writes the operator pool and ``~/.config/renlink/cookies.env`` (mode 0600).

Pool writes are atomic per platform: the old file stays in place until a
complete new record is ready. A failed fetch or write exits non-zero and never
leaves a partial record. Cookie values are never printed.

Usage:
  .venv/bin/python ops/refresh_cookie.py            # both platforms
  .venv/bin/python ops/refresh_cookie.py douyin     # one platform
  .venv/bin/python ops/refresh_cookie.py --from-env # write the current jar only
  .venv/bin/python ops/refresh_cookie.py --pool-dir /tmp/pool --env-file /tmp/cookies.env
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict

DEFAULT_ENV_PATH = Path.home() / ".config" / "renlink" / "cookies.env"
DEFAULT_POOL_DIR = Path.home() / ".config" / "renlink" / "sessions"

PLATFORMS = {
    "douyin": {
        "url": "https://www.douyin.com/",
        "domain": "douyin.com",
        "need": ("UIFID|UIFID_TEMP", "s_v_web_id"),
    },
    "xhs": {
        "url": "https://www.xiaohongshu.com/",
        "domain": "xiaohongshu.com",
        "need": ("web_session",),
    },
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)


def load_env(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip("'\"")
    return out


def jar_to_header(cookies: list[dict], domain: str) -> str:
    pairs = [
        f"{c['name']}={c['value']}"
        for c in cookies
        if c.get("value") and domain in (c.get("domain") or "")
    ]
    return "; ".join(pairs)


def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def write_pool_records(pool_dir: Path, records: Dict[str, str]) -> None:
    """Stage every record first, then replace files one by one."""
    if not records:
        return
    pool_dir.mkdir(parents=True, exist_ok=True)
    max_age = int(os.getenv("RENLINK_SESSION_MAX_AGE_S", "86400") or "86400")
    staged: list[tuple[str, Path, str]] = []
    try:
        for platform, cookie in records.items():
            payload = {
                "platform": platform,
                "cookie": cookie,
                "refreshed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "max_age_s": max_age,
            }
            target = pool_dir / f"{platform}.json"
            fd, name = tempfile.mkstemp(prefix=f".{platform}.", dir=str(pool_dir))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            os.chmod(name, 0o600)
            staged.append((platform, target, name))
        for _platform, target, name in staged:
            os.replace(name, target)
    finally:
        for _platform, _target, name in staged:
            try:
                os.unlink(name)
            except OSError:
                pass


def _cos_upload_ready() -> bool:
    return bool(os.getenv("COS_BUCKET", "").strip())


def _cos_credentials() -> Dict[str, str]:
    secret_id = os.getenv("COS_SECRET_ID", "") or os.getenv("TENCENTCLOUD_SECRETID", "")
    secret_key = os.getenv("COS_SECRET_KEY", "") or os.getenv("TENCENTCLOUD_SECRETKEY", "")
    token = os.getenv("COS_SESSION_TOKEN", "") or os.getenv("TENCENTCLOUD_SESSIONTOKEN", "")
    if secret_id and secret_key:
        return {"secret_id": secret_id, "secret_key": secret_key, "token": token}
    url = os.getenv("COS_CREDENTIAL_URL", "http://api.weixin.qq.com/_/cos/getauth").strip()
    if not url:
        raise RuntimeError("no credential source")
    import urllib.request

    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - fixed operator URL
        data = json.loads(response.read().decode("utf-8"))
    for wrapper in ("Credentials", "credentials", "data", "Data"):
        if isinstance(data.get(wrapper), dict):
            data = data[wrapper]
            break
    secret_id = data.get("TmpSecretId") or data.get("secret_id") or ""
    secret_key = data.get("TmpSecretKey") or data.get("secret_key") or ""
    token = data.get("Token") or data.get("token") or ""
    if not secret_id or not secret_key:
        raise RuntimeError("credential response missing fields")
    return {"secret_id": secret_id, "secret_key": secret_key, "token": token}


def upload_pool_cos(pool_dir: Path, platforms: list[str]) -> list[str]:
    """Upload the freshly written records when COS is configured."""
    if not _cos_upload_ready():
        return []
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        return ["COS SDK missing"]
    try:
        creds = _cos_credentials()
    except Exception:  # noqa: BLE001 - reported as a failure below
        return ["COS credentials unavailable"]
    bucket = os.getenv("COS_BUCKET", "").strip()
    region = os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai"
    prefix = (os.getenv("SESSION_COS_PREFIX", "sessions/").strip() or "sessions/").rstrip("/")
    client = CosS3Client(
        CosConfig(
            Region=region,
            SecretId=creds["secret_id"],
            SecretKey=creds["secret_key"],
            Token=creds.get("token") or None,
            Scheme="https",
            Timeout=15,
        )
    )
    failures: list[str] = []
    for platform in platforms:
        try:
            with (pool_dir / f"{platform}.json").open("rb") as handle:
                client.put_object(
                    Bucket=bucket,
                    Body=handle,
                    Key=f"{prefix}/{platform}.json",
                    ContentType="application/json",
                )
        except Exception as exc:  # noqa: BLE001 - one fixed failure label
            failures.append(f"{platform}: COS upload failed ({type(exc).__name__})")
    return failures


def fetch_browser(env: Dict[str, str], targets: list[str], fetched: Dict[str, str]) -> list[str]:
    from playwright.sync_api import sync_playwright

    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        for name in targets:
            spec = PLATFORMS[name]
            ctx = browser.new_context(user_agent=UA, locale="zh-CN")
            seed = []
            for pair in env.get(f"{name.upper()}_COOKIE", "").split(";"):
                if "=" not in pair:
                    continue
                key, value = pair.strip().split("=", 1)
                if not key or not value:
                    continue
                seed.append(
                    {
                        "name": key,
                        "value": value,
                        "domain": "." + spec["domain"],
                        "path": "/",
                        "expires": -1,
                        "httpOnly": False,
                        "secure": True,
                        "sameSite": "Lax",
                    }
                )
            if seed:
                try:
                    ctx.add_cookies(seed)
                except Exception as exc:  # noqa: BLE001 - stale jar is not fatal
                    print(f"{name}: seed skipped ({type(exc).__name__})")
            page = ctx.new_page()
            try:
                page.goto(spec["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(9000)
            except Exception as exc:  # noqa: BLE001 - network variance is expected
                print(f"{name}: goto failed ({type(exc).__name__})")
            header = jar_to_header(ctx.cookies(), spec["domain"])
            names = {part.strip().split("=", 1)[0] for part in header.split(";") if "=" in part}
            missing = [n for n in spec["need"] if not any(alt in names for alt in n.split("|"))]
            if missing or not header:
                failed.append(name)
                print(f"{name}: missing {missing or 'all cookies'}")
            else:
                env[f"{name.upper()}_COOKIE"] = header
                fetched[name] = header
                print(f"{name}: ok ({len(names)} cookies)")
            ctx.close()
        browser.close()
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="refresh operator cookies")
    parser.add_argument("platforms", nargs="*", default=[])
    parser.add_argument("--from-env", action="store_true", help="skip the browser; write the current jar")
    parser.add_argument("--env-file", default=os.getenv("RENLINK_COOKIE_ENV_FILE", ""))
    parser.add_argument("--pool-dir", default=os.getenv("RENLINK_SESSION_LOCAL_POOL", ""))
    parser.add_argument("--no-env-file", action="store_true", help="write the pool only")
    args = parser.parse_args()

    unknown = [name for name in args.platforms if name not in PLATFORMS]
    if unknown:
        print(f"unknown platform: {unknown}", file=sys.stderr)
        return 2
    targets = args.platforms or list(PLATFORMS)
    env_path = Path(args.env_file).expanduser() if args.env_file else DEFAULT_ENV_PATH
    pool_dir = Path(args.pool_dir).expanduser() if args.pool_dir else DEFAULT_POOL_DIR

    env = dict(os.environ)
    env.update(load_env(env_path))
    fetched: Dict[str, str] = {}
    failed: list[str] = []

    if args.from_env:
        for name in targets:
            cookie = env.get(f"{name.upper()}_COOKIE", "").strip()
            if cookie:
                fetched[name] = cookie
                print(f"{name}: ok (from env)")
            else:
                failed.append(name)
                print(f"{name}: missing cookie")
    else:
        failed.extend(fetch_browser(env, targets, fetched))

    if fetched:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        for name in fetched:
            env[f"{name.upper()}_COOKIE_LAST_REFRESH"] = stamp
        try:
            write_pool_records(pool_dir, fetched)
            print(f"wrote pool {pool_dir}")
        except Exception as exc:  # noqa: BLE001 - one fixed failure path
            failed.extend(f"{name}: pool write failed" for name in fetched)
            print(f"pool write failed ({type(exc).__name__})", file=sys.stderr)
        else:
            failed.extend(upload_pool_cos(pool_dir, list(fetched)))
        if not args.no_env_file:
            lines = []
            for key in ("DOUYIN_COOKIE", "XHS_COOKIE", "DOUYIN_COOKIE_LAST_REFRESH", "XHS_COOKIE_LAST_REFRESH"):
                if key in env:
                    lines.append(f"{key}={env[key]!r}\n")
            try:
                _atomic_write(env_path, "".join(lines), stat.S_IRUSR | stat.S_IWUSR)
                print(f"wrote {env_path}")
            except Exception as exc:  # noqa: BLE001 - one fixed failure path
                failed.append(f"env write failed ({type(exc).__name__})")
                print(f"env write failed ({type(exc).__name__})", file=sys.stderr)

    for item in failed:
        print(item, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
