"""l6 zip export: pack one task's already-staged l3 images into a single zip.

Selection, ordering, entry names and timestamps follow the frozen
l6-zip-export truth. The zip is written under /tmp/renlink-zip-* and
uploaded through l3's own store adapter (stage_store); this module never
re-downloads source media and never calls /stage.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import stage_cache
from .errors import ERROR_SPECS
from .stage_store import StageStore, StoreFailed, StoreNotReady, build_store

logger = logging.getLogger("renlink.zip")

ZIP_ENTRY_TIME = (1980, 1, 1, 0, 0, 0)
ZIP_CONTENT_TYPE = "application/zip"


class ZipError(Exception):
    """One fixed /zip error code from the truth error table."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        spec = ERROR_SPECS[code]
        self.code = code
        self.status = spec.http_status
        self.retryable = spec.retryable
        self.message = message or spec.message
        super().__init__(self.message)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def max_images() -> int:
    return _env_int("ZIP_MAX_IMAGES", 50) or 50


def max_bytes() -> int:
    return _env_int("ZIP_MAX_BYTES", 209715200) or 209715200


def timeout_s() -> int:
    return _env_int("ZIP_TIMEOUT_S", 60) or 60


def cache_ttl_s() -> int:
    return _env_int("ZIP_CACHE_TTL_S", 600)


def tmp_prefix() -> str:
    return os.getenv("ZIP_TMP_PREFIX", "renlink-zip-").strip() or "renlink-zip-"


def _fault(name: str) -> bool:
    """Test-only injection; local store only, per the frozen config table."""
    if (os.getenv("STAGE_STORE", "local").strip().lower() or "local") != "local":
        return False
    return os.getenv("ZIP_FAULT_INJECT", "").strip().lower() == name


def _fake_pack_delay_ms() -> int:
    """Test-only: stall inside the packing worker, not in the event loop."""
    if (os.getenv("STAGE_STORE", "local").strip().lower() or "local") != "local":
        return 0
    return _env_int("ZIP_FAKE_PACK_DELAY_MS", 0)


class _PackingCancelled(Exception):
    """The request was cancelled while the packing worker was still running."""


class _PackScope:
    """Hands the worker thread its temp paths and, on cancellation, the lock.

    `asyncio.wait_for` cancels the coroutine, but the thread running
    `_pack_sync` keeps going.  The scope lets the coroutine unlink every temp
    file it already created, and keeps the per-key lock owned by the worker
    until packing actually stops so a retry cannot pack the same key twice.
    """

    def __init__(self, key_lock: threading.Lock) -> None:
        self._mu = threading.Lock()
        self._key_lock = key_lock
        self._paths: set = set()
        self._cancelled = False
        self._finished = False
        self._release_pending = False
        self._released = False

    def _take_release(self) -> bool:
        """Caller holds `_mu`; true exactly once when a release is owed."""
        if self._release_pending and not self._released:
            self._released = True
            self._release_pending = False
            return True
        return False

    @staticmethod
    def _release(lock: threading.Lock) -> None:
        try:
            lock.release()
        except RuntimeError:
            pass

    def start(self) -> bool:
        with self._mu:
            return not self._cancelled

    def track(self, path: Path) -> bool:
        with self._mu:
            if self._cancelled:
                return False
            self._paths.add(path)
            return True

    def is_cancelled(self) -> bool:
        with self._mu:
            return self._cancelled

    def handover(self, zip_path: Path) -> bool:
        """Worker success.  False means the request was cancelled meanwhile."""
        with self._mu:
            self._finished = True
            cancelled = self._cancelled
            leftovers = [path for path in self._paths if path != zip_path]
            if cancelled:
                leftovers.append(zip_path)
                self._paths.clear()
            else:
                # Keep the finished zip tracked until the coroutine claims it,
                # so a cancellation that arrives in that window still unlinks it.
                self._paths = {zip_path}
            release = self._take_release() if cancelled else False
        for path in leftovers:
            _unlink(path)
        if release:
            self._release(self._key_lock)
        return not cancelled

    def claim(self) -> None:
        """Coroutine took ownership of the returned zip path."""
        with self._mu:
            self._paths.clear()

    def cancel(self) -> bool:
        """Request cancelled.  True means the coroutine must release the lock."""
        with self._mu:
            self._cancelled = True
            paths = list(self._paths)
            if self._finished:
                caller_releases = not self._released
                self._released = True
                return caller_releases
            self._release_pending = True
        for path in paths:
            _unlink(path)
        return False

    def finish(self) -> None:
        """Worker thread ended, normally or by cancellation."""
        with self._mu:
            self._finished = True
            leftovers = list(self._paths)
            self._paths.clear()
            release = self._take_release()
        for path in leftovers:
            _unlink(path)
        if release:
            self._release(self._key_lock)


_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}
_key_locks: Dict[str, threading.Lock] = {}


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if entry["expires_at"] <= time.monotonic():
            _cache.pop(key, None)
            return None
        return dict(entry)


def _cache_put(key: str, value: Dict[str, Any], ttl: int) -> None:
    if ttl <= 0:
        return
    with _cache_lock:
        _cache[key] = dict(value, expires_at=time.monotonic() + ttl)


def _cache_drop(key: str) -> None:
    with _cache_lock:
        _cache.pop(key, None)


def clear() -> None:
    """Test hook: drop every cached zip result."""
    with _cache_lock:
        _cache.clear()
        _key_locks.clear()


def _key_lock(key: str) -> threading.Lock:
    with _cache_lock:
        lock = _key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _key_locks[key] = lock
        return lock


async def _acquire(lock: threading.Lock) -> None:
    """Serialize one cache key across requests and event loops.

    The blocking acquire runs on a helper thread so the event loop stays free.
    If this coroutine is cancelled mid-wait, the helper releases on delivery.
    """
    loop = asyncio.get_running_loop()
    future: "asyncio.Future[None]" = loop.create_future()

    def deliver() -> None:
        if future.done():
            lock.release()
        else:
            future.set_result(None)

    def worker() -> None:
        lock.acquire()
        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            lock.release()

    threading.Thread(target=worker, daemon=True).start()
    try:
        await future
    except asyncio.CancelledError:
        future.cancel()
        raise


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("zip temp cleanup failed")


def normalize_indexes(
    manifest: stage_cache.StageManifest, raw: Any
) -> Optional[List[int]]:
    """Validate an explicit indexes list; None means all staged images."""
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        raise ZipError("INVALID_REQUEST", "indexes 必须是非空整数数组")
    wanted: List[int] = []
    seen = set()
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ZipError("INVALID_REQUEST", "indexes 元素必须是整数")
        if value < 0:
            raise ZipError("INVALID_REQUEST", "indexes 元素不能为负数")
        item = manifest.item_at(value)
        if item is None:
            raise ZipError("INVALID_REQUEST", "index 不在清单内")
        if str(item.get("type") or "") != "image":
            raise ZipError("INVALID_REQUEST", "只能显式指定图片 index")
        if value not in seen:
            seen.add(value)
            wanted.append(value)
    return sorted(wanted)


def select_entries(
    manifest: stage_cache.StageManifest,
    requested: Optional[List[int]],
    store: StageStore,
) -> List[Dict[str, Any]]:
    """Only items that are images, cached by l3 and still present in storage."""
    if requested is None:
        wanted = sorted(
            int(item.get("index", -1))
            for item in manifest.items
            if str(item.get("type") or "") == "image"
        )
    else:
        wanted = requested
    entries: List[Dict[str, Any]] = []
    for index in wanted:
        item = manifest.item_at(index)
        if item is None or str(item.get("type") or "") != "image":
            continue
        record = stage_cache.get_object(manifest.platform, manifest.content_id, index)
        if not record:
            continue
        try:
            present = store.exists(record["fileID"])
        except Exception:  # noqa: BLE001 - a broken store counts as missing
            present = False
        if not present:
            continue
        ext = str(record.get("ext") or item.get("ext") or "webp").lower()
        entries.append(
            {
                "index": index,
                "fileID": record["fileID"],
                "ext": ext,
                "bytes": int(record.get("bytes") or 0),
            }
        )
    return entries


def index_set_hash(indices: List[int]) -> str:
    material = ",".join(str(index) for index in indices)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def cache_key(task_id: str, indices: List[int]) -> str:
    return "zip:v1:{0}:{1}".format(task_id, ",".join(str(index) for index in indices))


async def ready_store() -> StageStore:
    store = build_store()
    try:
        await store.ready()
    except StoreNotReady as exc:
        raise ZipError("ZIP_NOT_READY", "打包服务未配置对象存储: {0}".format(exc)) from exc
    if store.mode == "local":
        root = getattr(store, "root", None)
        if root is None:
            raise ZipError("ZIP_NOT_READY", "本地存储目录不可读写")
        try:
            fd, probe = tempfile.mkstemp(prefix="renlink-stage-probe-", dir=str(root))
            os.close(fd)
            Path(probe).unlink()
        except OSError as exc:
            raise ZipError("ZIP_NOT_READY", "本地存储目录不可读写") from exc
    return store


def _pack_sync(
    entries: List[Dict[str, Any]], store: StageStore, scope: _PackScope
) -> Path:
    """Read every stored object and write a deterministic zip (worker thread)."""
    if not scope.start():
        scope.finish()
        raise _PackingCancelled()
    prefix = tmp_prefix()
    fd, name = tempfile.mkstemp(prefix=prefix, dir="/tmp", suffix=".zip")
    os.close(fd)
    zip_path = Path(name)
    if not scope.track(zip_path):
        _unlink(zip_path)
        scope.finish()
        raise _PackingCancelled()
    raws: List[Path] = []
    handed_over = False
    try:
        if _fault("write"):
            raise ZipError("ZIP_FAILED", "打包写入失败")
        delay_ms = _fake_pack_delay_ms()
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        if scope.is_cancelled():
            raise _PackingCancelled()
        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_STORED, allowZip64=True
        ) as archive:
            for entry in entries:
                if scope.is_cancelled():
                    raise _PackingCancelled()
                fd, raw_name = tempfile.mkstemp(prefix=prefix, dir="/tmp")
                os.close(fd)
                raw = Path(raw_name)
                if not scope.track(raw):
                    _unlink(raw)
                    raise _PackingCancelled()
                raws.append(raw)
                if _fault("read"):
                    raise ZipError("ZIP_FAILED", "读取已转存图片失败")
                try:
                    store.fetch_sync(entry["fileID"], raw)
                except (StoreFailed, StoreNotReady, OSError) as exc:
                    raise ZipError("ZIP_FAILED", "读取已转存图片失败") from exc
                info = zipfile.ZipInfo(
                    "{0:03d}.{1}".format(entry["index"], entry["ext"]),
                    date_time=ZIP_ENTRY_TIME,
                )
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                with raw.open("rb") as handle:
                    archive.writestr(info, handle.read())
        if not scope.handover(zip_path):
            raise _PackingCancelled()
        handed_over = True
        return zip_path
    except _PackingCancelled:
        _unlink(zip_path)
        raise
    except ZipError:
        _unlink(zip_path)
        raise
    except OSError as exc:
        _unlink(zip_path)
        raise ZipError("ZIP_FAILED", "打包 zip 失败") from exc
    finally:
        for raw in raws:
            _unlink(raw)
        if not handed_over:
            scope.finish()


async def _build_cached(
    entries: List[Dict[str, Any]],
    store: StageStore,
    key: str,
    memo: str,
) -> Dict[str, Any]:
    lock = _key_lock(memo)
    await _acquire(lock)
    lock_handed_off = False
    try:
        ttl = cache_ttl_s()
        if ttl > 0:
            hit = _cache_get(memo)
            if hit:
                try:
                    present = store.exists(hit["fileID"])
                except Exception:  # noqa: BLE001 - treat as missing
                    present = False
                if present:
                    return {
                        "ok": True,
                        "fileID": hit["fileID"],
                        "bytes": hit["bytes"],
                        "count": hit["count"],
                    }
                _cache_drop(memo)

        delay_ms = _env_int("ZIP_FAKE_DELAY_MS", 0)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        scope = _PackScope(lock)
        try:
            zip_path = await asyncio.to_thread(_pack_sync, entries, store, scope)
        except asyncio.CancelledError:
            lock_handed_off = True
            if scope.cancel():
                lock.release()
            raise
        scope.claim()
        try:
            size = zip_path.stat().st_size
            if size > max_bytes():
                raise ZipError("TOO_LARGE", "生成的 zip 超过体积上限")
            if _fault("upload"):
                raise ZipError("ZIP_FAILED", "上传 zip 失败")
            try:
                file_id = await store.put(zip_path, key, ZIP_CONTENT_TYPE)
            except (StoreFailed, StoreNotReady, OSError) as exc:
                raise ZipError("ZIP_FAILED", "上传 zip 失败") from exc
        finally:
            _unlink(zip_path)

        result = {
            "ok": True,
            "fileID": file_id,
            "bytes": size,
            "count": len(entries),
        }
        _cache_put(memo, result, ttl)
        logger.info("zip ok count=%s bytes=%s key=%s", result["count"], size, key)
        return result
    finally:
        if not lock_handed_off:
            lock.release()


async def export_zip(task_id: str, indexes: Any) -> Dict[str, Any]:
    started = time.perf_counter()
    manifest = stage_cache.get_task(task_id)
    if manifest is None:
        raise ZipError("STAGE_EXPIRED", "清单缓存已过期，请重新解析")
    requested = normalize_indexes(manifest, indexes)
    if requested is not None and len(requested) > max_images():
        raise ZipError("TOO_LARGE", "请求的图片数量超过上限")
    store = await ready_store()
    entries = select_entries(manifest, requested, store)
    if not entries:
        if requested is not None:
            raise ZipError("INVALID_REQUEST", "请求的图片都还没有转存")
        raise ZipError("INVALID_REQUEST", "没有已转存的图片，请先逐张转存")
    if len(entries) > max_images():
        raise ZipError("TOO_LARGE", "已转存图片数量超过上限")
    if sum(entry["bytes"] for entry in entries) > max_bytes():
        raise ZipError("TOO_LARGE", "源图片体积超过上限")

    indices = [entry["index"] for entry in entries]
    key = "l6/{0}/{1}.zip".format(task_id, index_set_hash(indices))
    memo = cache_key(task_id, indices)
    budget = max(0.1, float(timeout_s()) - (time.perf_counter() - started))
    try:
        return await asyncio.wait_for(
            _build_cached(entries, store, key, memo), timeout=budget
        )
    except asyncio.TimeoutError as exc:
        raise ZipError("TIMEOUT", "单请求超过 {0} 秒".format(timeout_s())) from exc
