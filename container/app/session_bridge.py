"""l4-session-egress: operator cookie pool, freshness, and redaction.

Sources: ``SESSION_POOL_SOURCE=cos|db|env``. COS/DB failures fall back to the
env source and ``/health`` reports ``source=env``. The env source may read a
local operator-pool mirror (``RENLINK_SESSION_LOCAL_POOL``) written by
``ops/refresh_cookie.py``; otherwise it reads ``DOUYIN_COOKIE`` / ``XHS_COOKIE``.

Freshness never probes upstream: it is computed from pool ``refreshed_at`` and
``max_age_s`` only. Reads are cached for ``RENLINK_SESSION_TTL_S`` seconds;
``RENLINK_SESSION_RELOAD=1`` forces the next read. Cookie values are never
logged or returned by health.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger("renlink.session")

PLATFORMS = ("douyin", "xhs")
DEFAULT_MAX_AGE_S = 86400
DEFAULT_TTL_S = 60
POOL_SOURCES = ("cos", "db", "env")
_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CookieExpired(Exception):
    """Raised when the operator cookie is missing or stale."""


class PoolUnavailable(Exception):
    """The configured pool could not be read; the caller falls back to env."""


@dataclass(frozen=True)
class PoolRecord:
    platform: str
    cookie: str
    refreshed_at: str
    max_age_s: int
    source: str

    @property
    def present(self) -> bool:
        return bool(self.cookie)


_lock = threading.RLock()
_cache: Dict[str, Tuple[float, PoolRecord]] = {}
_stats = {"pool_reads": 0, "env_fallbacks": 0}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _cache_ttl_s() -> int:
    return _env_int("RENLINK_SESSION_TTL_S", DEFAULT_TTL_S)


def _default_max_age_s() -> int:
    return _env_int("RENLINK_SESSION_MAX_AGE_S", DEFAULT_MAX_AGE_S)


def _stub_expired(platform: str) -> bool:
    raw = os.getenv("PARSE_STUB_COOKIE_EXPIRED", "").strip().lower()
    values = {token.strip() for token in raw.replace(";", ",").split(",") if token.strip()}
    if values & {"1", "true", "all", "*"}:
        return True
    if platform in values:
        return True
    return os.getenv(f"PARSE_STUB_{platform.upper()}_COOKIE_EXPIRED", "") == "1"


def _parse_time(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def _age_s(record: PoolRecord) -> Optional[int]:
    parsed = _parse_time(record.refreshed_at)
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0, int((now - parsed.astimezone(timezone.utc)).total_seconds()))


def _status(record: PoolRecord) -> str:
    if not record.present:
        return "missing"
    if _stub_expired(record.platform):
        return "expired"
    age = _age_s(record)
    if age is None:
        # Env cookies have no operator timestamp; a present value is usable.
        return "fresh" if record.source == "env" else "expired"
    return "fresh" if age <= record.max_age_s else "expired"


def _record(platform: str, data: Any, source: str) -> PoolRecord:
    if not isinstance(data, dict):
        raise PoolUnavailable("池记录不是 JSON 对象")
    cookie = data.get("cookie")
    if not isinstance(cookie, str):
        cookie = ""
    refreshed = data.get("refreshed_at")
    if not isinstance(refreshed, str):
        refreshed = ""
    try:
        max_age = int(data.get("max_age_s") or _default_max_age_s())
    except (TypeError, ValueError):
        max_age = _default_max_age_s()
    return PoolRecord(
        platform=platform,
        cookie=cookie.strip(),
        refreshed_at=refreshed.strip(),
        max_age_s=max(1, max_age),
        source=source,
    )


def _local_pool_dir() -> Optional[Path]:
    raw = os.getenv("RENLINK_SESSION_LOCAL_POOL", "").strip()
    return Path(raw).expanduser() if raw else None


def _read_local_pool(platform: str) -> Optional[PoolRecord]:
    root = _local_pool_dir()
    if root is None:
        return None
    path = root / f"{platform}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "session local pool unreadable platform=%s type=%s",
            platform,
            type(exc).__name__,
        )
        return None
    try:
        record = _record(platform, data, "env")
    except PoolUnavailable:
        return None
    return record if record.present else None


def _read_env_pool(platform: str) -> PoolRecord:
    mirror = _read_local_pool(platform)
    if mirror is not None:
        return mirror
    cookie = os.getenv(f"{platform.upper()}_COOKIE", "").strip()
    refreshed = os.getenv(f"{platform.upper()}_COOKIE_LAST_REFRESH", "").strip()
    return PoolRecord(platform, cookie, refreshed, _default_max_age_s(), "env")


def _cos_credentials() -> Dict[str, str]:
    from .stage_store import _parse_credentials, _static_credentials

    static = _static_credentials()
    if static:
        return static
    url = os.getenv("COS_CREDENTIAL_URL", "http://api.weixin.qq.com/_/cos/getauth").strip()
    if not url:
        raise PoolUnavailable("没有 COS 临时密钥来源")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            parsed = _parse_credentials(response.json())
    except Exception as exc:  # noqa: BLE001 - pool failure is not fatal
        raise PoolUnavailable("COS 临时密钥获取失败") from exc
    if not parsed:
        raise PoolUnavailable("COS 临时密钥响应缺少字段")
    return parsed


def _read_cos_pool(platform: str) -> PoolRecord:
    bucket = os.getenv("COS_BUCKET", "").strip()
    if not bucket:
        raise PoolUnavailable("COS_BUCKET 未配置")
    prefix = os.getenv("SESSION_COS_PREFIX", "sessions/").strip() or "sessions/"
    key = prefix.rstrip("/") + f"/{platform}.json"
    creds = _cos_credentials()
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise PoolUnavailable("缺少 cos-python-sdk-v5") from exc
    region = os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai"
    endpoint = os.getenv("COS_ENDPOINT", "").strip().rstrip("/")
    client = CosS3Client(
        CosConfig(
            Region=region,
            SecretId=creds["secret_id"],
            SecretKey=creds["secret_key"],
            Token=creds.get("token") or None,
            Scheme="https",
            Endpoint=endpoint or None,
            Timeout=5,
        )
    )
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].get_raw_stream().read()
        data = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - pool failure is not fatal
        raise PoolUnavailable(f"COS 池读取失败: {type(exc).__name__}") from exc
    return _record(platform, data, "cos")


def _db_connection():
    dsn = os.getenv("SESSION_DB_DSN", "").strip() or os.getenv("SESSION_DB_PATH", "").strip()
    if not dsn:
        raise PoolUnavailable("SESSION_DB_DSN 未配置")
    if dsn.startswith("mysql"):
        try:
            import pymysql  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PoolUnavailable("缺少 pymysql") from exc
        parsed = urlparse(dsn)
        return pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=(parsed.path or "/").lstrip("/"),
            connect_timeout=5,
            read_timeout=5,
        ), "mysql"
    if dsn.startswith("sqlite:///"):
        path = dsn[len("sqlite:///") :]
    elif dsn.startswith("sqlite://"):
        path = dsn[len("sqlite://") :]
    else:
        path = dsn
    return sqlite3.connect(path, timeout=5), "sqlite"


def _read_db_pool(platform: str) -> PoolRecord:
    table = os.getenv("SESSION_DB_TABLE", "renlink_sessions").strip() or "renlink_sessions"
    if not _TABLE.match(table):
        raise PoolUnavailable("SESSION_DB_TABLE 不合法")
    try:
        connection, kind = _db_connection()
    except PoolUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - pool failure is not fatal
        raise PoolUnavailable(f"DB 连接失败: {type(exc).__name__}") from exc
    try:
        if kind == "sqlite":
            row = connection.execute(
                f'SELECT platform, cookie, refreshed_at, max_age_s FROM "{table}" WHERE platform=? LIMIT 1',
                (platform,),
            ).fetchone()
        else:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT platform, cookie, refreshed_at, max_age_s FROM `{table}` WHERE platform=%s LIMIT 1",
                (platform,),
            )
            row = cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - pool failure is not fatal
        raise PoolUnavailable(f"DB 池读取失败: {type(exc).__name__}") from exc
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
    if not row:
        raise PoolUnavailable("DB 池没有记录")
    return _record(
        platform,
        {
            "platform": row[0],
            "cookie": row[1],
            "refreshed_at": row[2],
            "max_age_s": row[3],
        },
        "db",
    )


def _resolve(platform: str) -> PoolRecord:
    source = os.getenv("SESSION_POOL_SOURCE", "cos").strip().lower() or "cos"
    if source not in POOL_SOURCES:
        source = "cos"
    if source == "env":
        return _read_env_pool(platform)
    try:
        record = _read_cos_pool(platform) if source == "cos" else _read_db_pool(platform)
        if record.present:
            return record
        raise PoolUnavailable("池记录没有 cookie")
    except PoolUnavailable as exc:
        with _lock:
            _stats["env_fallbacks"] += 1
        logger.warning(
            "session pool fallback platform=%s source=%s reason=%s",
            platform,
            source,
            str(exc),
        )
        return _read_env_pool(platform)


def _load(platform: str) -> PoolRecord:
    with _lock:
        if os.getenv("RENLINK_SESSION_RELOAD", "").strip() == "1":
            _cache.clear()
            os.environ.pop("RENLINK_SESSION_RELOAD", None)
        ttl = _cache_ttl_s()
        cached = _cache.get(platform)
        now = time.monotonic()
        if cached is not None and ttl > 0 and now - cached[0] < ttl:
            return cached[1]
        record = _resolve(platform)
        _stats["pool_reads"] += 1
        _cache[platform] = (now, record)
        logger.info(
            "session loaded platform=%s source=%s status=%s cookie=%s",
            platform,
            record.source,
            _status(record),
            redact(record.cookie),
        )
        return record


def _known(platform: str) -> bool:
    return platform in PLATFORMS


def get_cookie(platform: str) -> str:
    """Return the operator Cookie header; raise CookieExpired when unusable."""
    if not _known(platform):
        return ""
    if _stub_expired(platform):
        raise CookieExpired(f"{platform} cookie expired")
    record = _load(platform)
    state = _status(record)
    if state != "fresh":
        raise CookieExpired(f"{platform} cookie {state}")
    return record.cookie


def cookie_status(platform: str) -> str:
    if not _known(platform):
        return "unknown"
    return _status(_load(platform))


def last_refresh(platform: str) -> str:
    if not _known(platform):
        return ""
    return _load(platform).refreshed_at


def pool_source(platform: str) -> str:
    if not _known(platform):
        return "missing"
    record = _load(platform)
    return record.source if record.present else "missing"


def pool_age_s(platform: str) -> Optional[int]:
    if not _known(platform):
        return None
    return _age_s(_load(platform))


def health_snapshot() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for platform in PLATFORMS:
        record = _load(platform)
        out[platform] = {
            "cookie_status": _status(record),
            "last_refresh": record.refreshed_at,
            "source": record.source if record.present else "missing",
            "pool_age_s": _age_s(record),
        }
    return out


def redact(value: Optional[str]) -> str:
    """Log-safe representation: first 4 characters plus ***."""
    if not value:
        return ""
    return f"{value[:4]}***" if len(value) > 4 else "***"


def invalidate() -> None:
    with _lock:
        _cache.clear()


def reset() -> None:
    """Test helper: clear cache and counters."""
    with _lock:
        _cache.clear()
        _stats["pool_reads"] = 0
        _stats["env_fallbacks"] = 0
        os.environ.pop("RENLINK_SESSION_RELOAD", None)


def session_stats() -> Dict[str, int]:
    with _lock:
        return dict(_stats)
