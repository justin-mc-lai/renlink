# l6-zip-export · QA 返工证据

- 日期：2026-11-09
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`（改动未 commit、未 push）
- 改动文件：`container/app/zipkit.py`、`tests/test_zip.py`
- truth 正文：未改（`git diff docs/beacon/v0.1.0/features/l6-zip-export/truth.md` 为空）

## L6-1（阻塞）打包中途超时的临时 zip 泄漏

原因：`asyncio.wait_for` 取消的是协程，`asyncio.to_thread(_pack_sync)` 的线程仍在写 zip；`_build_cached` 的 `finally` 拿不到线程内创建的临时路径。

修法：新增 `_PackScope`（`container/app/zipkit.py` 第 92-190 行附近），把 worker 线程创建的每个临时路径登记进去；

- 协程被取消时 `scope.cancel()` 立即 unlink 已登记路径，worker 之后重建的文件由 `scope.finish()` 在收尾时再删一次；
- worker 成功收尾用 `handover()` 把 zip 路径交接给协程，之后到来的取消仍会删掉它；
- `_pack_sync` 在开档前后与每张图之间检查取消标记，取消后不再继续产出。

证据 `probe_timeout_cleanup.log`（打包 worker 内延迟 3000ms、`ZIP_TIMEOUT_S=1`）：

```text
tmp residue mid-pack (t=500ms): ['/tmp/renlink-zip-crxj27jq.zip']
http_status: 504
body: {"error": {"code": "TIMEOUT", "message": "单请求超过 1 秒", "retryable": true}, "ok": false}
elapsed_ms_at_response: 1011
worker_finished_at_504: False
tmp residue at 504: []
worker_finished_after_wait: True
tmp residue after worker finished: []
retry_status: 200
PROBE_OK
```

结论：504 返回时 `/tmp` 已为 0 个 `renlink-zip-*`，线程跑完也不留文件；失败响应不含 fileID，未上传任何对象。

## L6-4（非阻塞）超时后同 key 锁提前释放

已一并处理：打包期间取消时，per-key 锁不再由协程释放，而是交给 `_PackScope`，由 worker 真正结束时释放（`scope.cancel()` 返回 false 时 worker 持锁；worker 已结束则由协程释放）。重试因此串行，不会在旧 worker 仍在打包时再起一份。

## 测试

- 新增 `tests/test_zip.py::test_zip_timeout_during_pack_cleans_temp_files`：用 `ZIP_FAKE_PACK_DELAY_MS` 把延迟放进 worker 线程（现有 `ZIP_FAKE_DELAY_MS` 在打包前，测不到该路径），断言 504 时与 worker 结束后 `/tmp` 均无残留，且随后重试 200。
- 更新 `test_zip_concurrent_same_key_packs_once` 适配 `_pack_sync` 的新 `scope` 参数。
- 全量：`50 passed, 3 warnings in 10.61s`（`pytest-full.log`），基线 45 passed。

## L6-3（发布门）AC-015 端侧证据

不属于本湖实现返工范围。AC-015 依赖 l5 的 `chg_1c6f5fa13031`（/zip 契约对齐），该变更仍 pending、l5 materials 为 stale；端侧实测须由 l5/前端在变更关闭后补。本湖只保证容器侧 /zip 契约与失败信封。

## 治理

- 冻结时序更正依据已用 `beacon-go truth change` 登记为 change 草稿：`docs/beacon/v0.1.0/features/l6-zip-export/changes/chg_a17d6ce4e5d6.md`（pending，未 refreeze）。
- 该命令只改 `tasks.md`/`tests.md` 的 `materials_status: current → stale` 做变更登记，truth.md 正文未动。
