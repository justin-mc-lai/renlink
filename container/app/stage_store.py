"""Object-store adapters for l3: local mock and Tencent COS.

STAGE_STORE=local writes under STAGE_LOCAL_DIR and returns cloud://local/<key>.
STAGE_STORE=cos uploads to COS with credentials from COS_SECRET_ID/KEY or the
cloud-hosting open credential endpoint. No credential is ever logged.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx


class StoreNotReady(Exception):
    """The configured store cannot accept an upload right now."""


class StoreFailed(Exception):
    """The store rejected or failed an upload."""


def store_mode() -> str:
    return (os.getenv("STAGE_STORE", "local").strip().lower() or "local")


class StageStore:
    mode = "local"

    async def ready(self) -> None:
        raise NotImplementedError

    async def put(self, source: Path, key: str, content_type: str) -> str:
        raise NotImplementedError

    def exists(self, file_id: str) -> bool:
        return True

    def fetch_sync(self, file_id: str, dest: Path) -> int:
        """Copy a previously stored object to a local temp file (l6 readback).

        Runs in a worker thread; raises StoreFailed when the object cannot be
        read. Callers must call ready() first.
        """
        raise NotImplementedError


class LocalStore(StageStore):
    mode = "local"

    def __init__(self) -> None:
        self.root = Path(os.getenv("STAGE_LOCAL_DIR", "/tmp/renlink-stage-store"))

    async def ready(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoreNotReady("本地存储目录不可写") from exc

    async def put(self, source: Path, key: str, content_type: str) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(source, dest)
        except OSError as exc:
            raise StoreFailed("本地对象写入失败") from exc
        return "cloud://local/" + key

    def exists(self, file_id: str) -> bool:
        path = self.path_for(file_id)
        return path is not None and path.is_file() and path.stat().st_size > 0

    def fetch_sync(self, file_id: str, dest: Path) -> int:
        path = self.path_for(file_id)
        if path is None or not path.is_file():
            raise StoreFailed("本地对象不存在")
        try:
            shutil.copyfile(path, dest)
        except OSError as exc:
            raise StoreFailed("本地对象读取失败") from exc
        return dest.stat().st_size

    def path_for(self, file_id: str) -> Optional[Path]:
        prefix = "cloud://local/"
        if not file_id.startswith(prefix):
            return None
        rel = file_id[len(prefix) :]
        if not rel or ".." in rel.split("/"):
            return None
        return self.root / rel


def _pick(data: Dict[str, Any], *names: str) -> str:
    for name in names:
        value = data.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _static_credentials() -> Optional[Dict[str, str]]:
    secret_id = _pick(
        os.environ,
        "COS_SECRET_ID",
        "TENCENTCLOUD_SECRETID",
        "TENCENTCLOUD_SECRET_ID",
    )
    secret_key = _pick(
        os.environ,
        "COS_SECRET_KEY",
        "TENCENTCLOUD_SECRETKEY",
        "TENCENTCLOUD_SECRET_KEY",
    )
    if not secret_id or not secret_key:
        return None
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "token": _pick(
            os.environ,
            "COS_SESSION_TOKEN",
            "TENCENTCLOUD_SESSIONTOKEN",
            "TENCENTCLOUD_TOKEN",
        ),
        "expires_at": time.time() + 3600,
    }


def _parse_credentials(data: Any) -> Optional[Dict[str, str]]:
    if not isinstance(data, dict):
        return None
    for wrapper in ("Credentials", "credentials", "data", "Data"):
        inner = data.get(wrapper)
        if isinstance(inner, dict):
            data = inner
            break
    secret_id = _pick(data, "TmpSecretId", "tmpSecretId", "SecretId", "secretId", "secret_id")
    secret_key = _pick(
        data, "TmpSecretKey", "tmpSecretKey", "SecretKey", "secretKey", "secret_key"
    )
    if not secret_id or not secret_key:
        return None
    expires = data.get("ExpiredTime") or data.get("expiredTime") or data.get("expires_at")
    try:
        expires_at = float(expires) if expires else time.time() + 3600
    except (TypeError, ValueError):
        expires_at = time.time() + 3600
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "token": _pick(data, "Token", "token", "SessionToken", "sessionToken"),
        "expires_at": expires_at,
    }


class CosStore(StageStore):
    mode = "cos"

    def __init__(self) -> None:
        self.bucket = os.getenv("COS_BUCKET", "").strip()
        self.region = os.getenv("COS_REGION", "ap-shanghai").strip() or "ap-shanghai"
        self.endpoint = os.getenv("COS_ENDPOINT", "").strip().rstrip("/")
        self._creds: Optional[Dict[str, str]] = None

    async def _credentials(self) -> Dict[str, str]:
        if self._creds and self._creds.get("expires_at", 0) > time.time() + 60:
            return self._creds
        static = _static_credentials()
        if static:
            self._creds = static
            return static
        url = os.getenv(
            "COS_CREDENTIAL_URL", "http://api.weixin.qq.com/_/cos/getauth"
        ).strip()
        if not url:
            raise StoreNotReady("没有 COS 临时密钥来源")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                parsed = _parse_credentials(response.json())
        except Exception as exc:  # noqa: BLE001 - map every failure to not-ready
            raise StoreNotReady("COS 临时密钥获取失败") from exc
        if not parsed:
            raise StoreNotReady("COS 临时密钥响应缺少字段")
        self._creds = parsed
        return parsed

    async def ready(self) -> None:
        if not self.bucket:
            raise StoreNotReady("未配置 COS_BUCKET")
        await self._credentials()

    async def put(self, source: Path, key: str, content_type: str) -> str:
        creds = await self._credentials()
        try:
            await asyncio.to_thread(self._put_sync, source, key, content_type, creds)
        except Exception as exc:  # noqa: BLE001 - one fixed upload error
            raise StoreFailed("COS 上传请求失败") from exc
        return "cloud://" + self.bucket + "/" + key

    def key_for(self, file_id: str) -> Optional[str]:
        prefix = "cloud://" + self.bucket + "/"
        if not self.bucket or not file_id.startswith(prefix):
            return None
        key = file_id[len(prefix) :]
        return key or None

    def fetch_sync(self, file_id: str, dest: Path) -> int:
        """Download one stored object. ready() already fetched the credentials."""
        key = self.key_for(file_id)
        if key is None:
            raise StoreFailed("COS 对象键不属于当前桶")
        creds = self._creds
        if not creds:
            raise StoreNotReady("COS 临时密钥未就绪")
        try:
            from qcloud_cos import CosConfig, CosS3Client

            config = CosConfig(
                Region=self.region,
                SecretId=creds["secret_id"],
                SecretKey=creds["secret_key"],
                Token=creds.get("token") or None,
                Scheme="https",
                Endpoint=self.endpoint or None,
                Timeout=60,
            )
            client = CosS3Client(config)
            client.download_file(
                Bucket=self.bucket, Key=key, DestFilePath=str(dest)
            )
        except Exception as exc:  # noqa: BLE001 - one fixed read error
            raise StoreFailed("COS 对象读取失败") from exc
        return dest.stat().st_size

    def _put_sync(
        self, source: Path, key: str, content_type: str, creds: Dict[str, str]
    ) -> None:
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=self.region,
            SecretId=creds["secret_id"],
            SecretKey=creds["secret_key"],
            Token=creds.get("token") or None,
            Scheme="https",
            Endpoint=self.endpoint or None,
            Timeout=60,
        )
        client = CosS3Client(config)
        with source.open("rb") as handle:
            client.put_object(
                Bucket=self.bucket,
                Body=handle,
                Key=key,
                ContentType=content_type,
            )


def build_store() -> StageStore:
    if store_mode() == "cos":
        return CosStore()
    return LocalStore()
