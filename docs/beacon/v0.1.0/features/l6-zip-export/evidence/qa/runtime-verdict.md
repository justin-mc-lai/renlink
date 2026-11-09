# l6-zip-export · 运行时行为验收（QA 验收 · agy）

- 日期：2026-11-09 06:45（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`（实现提交 `8ed9b2e`，工作区干净）
- 角色：QA 验收 · agy（视觉/端侧 / 运行时行为验收）
- 验收对象：`container/app/routes_zip.py`、`container/app/zipkit.py`、`tests/test_zip.py`
- 执行环境：`/Users/apple/Developer/Personal/renlink/.venv/bin/python`
- 约束遵从：只读验收，未修改实现代码，未修改 truth，未 commit，未 push；不覆盖独立验收员的 spec-verdict.md
- 总判定：**FAIL**（1 项硬边界运行时阻断缺陷 + 2 项治理阻塞项）

## 1. 运行时基线与回归

```
$ .venv/bin/python -m pytest tests -q
45 passed, 3 warnings in 7.97s
```

`tests/test_zip.py` 15 个用例全部 passed。L1 `/parse`、L3 `/stage`、L4 cookie 拦截与 egress 代理配置回归均实跑验证通过。

## 2. 运行时场景验证表

| 场景 | 期望行为 | 实际行为 | 原始证据相对路径 | 判定 |
|---|---|---|---|---|
| **成功路径与 ZIP 读回** | POST `/zip` 返回 `{ok, fileID, bytes, count}`；拿 fileID 读回 zip 校验：字节数=bytes、条目数=count、条目名 `{index:03d}.{ext}` 升序、时间戳 1980-01-01、ZIP_STORED、内容与源图片一致 | HTTP 200，响应键恰为 `['bytes', 'count', 'fileID', 'ok']`，fileID 以 `cloud://local/l6/<task_id>/` 开头；本地读回校验 bytes=351、count=3、条目名 `["000.jpg", "001.png", "002.webp"]`、date_time=(1980,1,1,0,0,0)、compress_type=ZIP_STORED，内容解包逐字节匹配 | `runtime/01-success-readback.txt` | PASS |
| **失败路径 410 STAGE_EXPIRED** | 未知或过期 task 返回 410，`ok=false`，`error.code="STAGE_EXPIRED"`，`retryable=false`，无 fileID，无 `cloud://` | HTTP 410，`error.code="STAGE_EXPIRED"`，`retryable=false`，无 fileID 且响应无 `cloud://` | `runtime/02-failures-410-413-503.txt` | PASS |
| **失败路径 413 TOO_LARGE** | 显式 index 超限或图片体积超限返回 413，`error.code="TOO_LARGE"`，`retryable=false`，无 fileID | HTTP 413，`error.code="TOO_LARGE"`，`retryable=false`，无 fileID 且响应无 `cloud://` | `runtime/02-failures-410-413-503.txt` | PASS |
| **失败路径 503 ZIP_NOT_READY** | COS 未配置凭证或本地存储目录不可读写返回 503，`error.code="ZIP_NOT_READY"`，`retryable=true`，无 fileID | HTTP 503，`error.code="ZIP_NOT_READY"`，`retryable=true`，无 fileID 且响应无 `cloud://` | `runtime/02-failures-410-413-503.txt` | PASS |
| **幂等性与存储操作** | 同 task 同 cloudID 集合连打两次，响应完全一致；第二次调用命中缓存，源对象读取 (`fetch_sync`) 与上传 (`put`) 计数不增 | Call 1 `fetch_sync=2, put=1`；Call 2 `fetch_sync=2, put=1`（增量为 0）；两次响应 `fileID/bytes/count` 完全一致 | `runtime/03-idempotency.txt` | PASS |
| **硬边界：Cookie 拦截** | 请求体带 cookie 字段返回 400，拒绝处理用户凭据 | HTTP 400，`code="INVALID_REQUEST"`，提示 `"请求体不得包含 cookie 字段"` | `runtime/04-hard-boundaries-and-timeout-leak.txt` | PASS |
| **硬边界：正常清理** | 正常成功与多数失败后 `/tmp/renlink-zip-*` 无残留 | 正常打包前后对比，残留临时文件数为 0 | `runtime/04-hard-boundaries-and-timeout-leak.txt` | PASS |
| **硬边界：超时清理** | 打包阶段触发 `ZIP_TIMEOUT_S` 时返回 504 `TIMEOUT`，且临时文件数清理为 0 | **实测复现泄漏**：HTTP 504 返回后，后台线程生成的 `/tmp/renlink-zip-*.zip` 留在 `/tmp` 无人清理（`_build_cached` 协程被取消，`finally` 中的 `_unlink` 无法执行） | `runtime/04-hard-boundaries-and-timeout-leak.txt` | **FAIL** |
| **L1/L3/L4 回归** | L1 `/parse` 响应 schema、L3 `/stage` 响应 schema 与文件落地、L4 cookie 拦截与 egress 代理注入不受影响 | L1 返回 9 字段完整 schema；L3 正确落盘并返回 5 字段；L4 拦截与代理模式正常 | `runtime/05-regression-l1-l3-l4.txt` | PASS |

## 3. 缺陷清单

| 编号 | 严重度 | 是否阻塞 | 缺陷描述 | 修复建议 |
|---|---|---|---|---|
| **L6-1** | P1 | **阻塞** | 打包阶段超时导致 `/tmp/renlink-zip-*.zip` 泄漏。`zipkit.py` 中 `asyncio.wait_for` 取消了 `_build_cached`，而 `_pack_sync` 在后台工作线程继续运行并返回临时文件路径，协程因已被取消而无法执行 `finally: _unlink(zip_path)`，违反硬边界 AC-012/AC-013「临时文件数为 0」。 | 让临时 zip 生命周期的清理下沉到 `_pack_sync` 内部，或在协程外部建立注册表并在取消分支清理；补写打包中途超时测试用例。 |
| **L6-2** | P1 | **阻塞（治理）** | 冻结时序违规：提交 `8ed9b2e` 实现代码时 truth 仍为 `draft`，AC 均为占位；`frozen` 与完整 AC 在其后的 `65c3112` 写入，违反「truth 未冻结不得实现」。 | 在 goal run 中更正时序证据与基线 sha 说明。 |
| **L6-3** | P1 | **阻塞（发布门）** | AC-015 缺少真机/PC端集成验证证据；l5 端侧 `chg_1c6f5fa13031` 尚未关闭，端侧合同状态为 `stale`。 | 待 l5 端侧对齐后补测端侧实际导出与存盘。 |
| **L6-4** | P2 | 非阻塞 | 超时后后台打包线程仍继续运行，同键锁已释放，后续同 key 请求可能重复触发打包。 | 在任务取消时同步中止打包线程或做任务追踪。 |

## 4. 结论

l6-zip-export 主链路（成功导出、字段收敛、子集排序、幂等缓存、410/413/503 失败信封、无伪造 cloud://、Cookie 拒绝）实测表现良好，但在**打包阶段超时**下存在**临时 zip 文件泄漏（L6-1）**，且叠加治理时序（L6-2）与端侧门禁（L6-3），本轮运行时总判定为 **FAIL**。

---

# Round 2（返工后运行时复验）

- 日期：2026-11-09 07:06（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`；返工改动未提交在工作区
- 树指纹：`git diff container tests | shasum -a 256` = `1d0e7d9acf1df416ba4e04a57e4e845eb7e46392e8237546657124c1ce3e9b20`（与派单一致）
- 角色：QA 验收 · agy（视觉/端侧 / 运行时行为验收）
- 执行环境：`/Users/apple/Developer/Personal/renlink/.venv/bin/python`
- 约束遵从：只读验收，未修改实现代码，未修改 truth 正文，未 commit，未 push；不覆盖独立验收员的 spec-verdict.md
- 总判定：**FAIL**（代码级运行时阻断缺陷已清零，仅因 AC-015 EMPTY / L6-3 端侧发布门未就绪及 L6-2 治理时序待裁定，按规则保持整体总判定）

## R2-1. 运行时基线与回归

```
$ .venv/bin/python -m pytest tests -q
50 passed, 3 warnings in 10.66s
```

`tests/test_zip.py`（含新增打包中途超时测试用例）及全套 50 个用例全部 passed。L1/L3/L4 回归与硬边界实测均通过。

## R2-2. 运行时场景复验表

| 场景 | 期望行为 | 实际行为 | 原始证据相对路径 | 判定 |
|---|---|---|---|---|
| **成功路径与 ZIP 读回** | POST `/zip` 返回 `{ok, fileID, bytes, count}`；拿 fileID 读回 zip 校验：字节数=bytes、条目数=count、条目名 `{index:03d}.{ext}` 升序、时间戳 1980-01-01、ZIP_STORED、内容与源图片一致 | HTTP 200，响应字段恰为 `['bytes', 'count', 'fileID', 'ok']`；本地读回校验 bytes=379、count=3、条目名 `["000.jpg", "001.png", "002.webp"]`、date_time=(1980,1,1,0,0,0)、compress_type=0 (ZIP_STORED)，解压字节逐一匹配 | `runtime/round2/01-success-readback.txt` | PASS |
| **失败路径 410 STAGE_EXPIRED** | 未知或过期 task 返回 410，`ok=false`，`error.code="STAGE_EXPIRED"`，`retryable=false`，无 fileID，无 `cloud://` | HTTP 410，`error.code="STAGE_EXPIRED"`，`retryable=false`，无 fileID 且响应无 `cloud://` | `runtime/round2/02-failures-410-413-503.txt` | PASS |
| **失败路径 413 TOO_LARGE** | 显式 index 超限或图片体积超限返回 413，`error.code="TOO_LARGE"`，`retryable=false`，无 fileID | HTTP 413，`error.code="TOO_LARGE"`，`retryable=false`，无 fileID 且响应无 `cloud://` | `runtime/round2/02-failures-410-413-503.txt` | PASS |
| **失败路径 503 ZIP_NOT_READY** | 本地存储目录不可写或存储异常返回 503，`error.code="ZIP_NOT_READY"`，`retryable=true`，无 fileID | HTTP 503，`error.code="ZIP_NOT_READY"`，`retryable=true`，无 fileID 且响应无 `cloud://` | `runtime/round2/02-failures-410-413-503.txt` | PASS |
| **幂等性与存储操作** | 同 task 同 cloudID 集合连打两次，响应完全一致；第二次调用命中缓存，源对象读取 (`fetch_sync`) 与上传 (`put`) 增量为 0 | Call 1 `fetch_sync=0, put=0`（命中 memo 缓存）；Call 2 响应完全一致；增量 fetch=0, put=0 | `runtime/round2/03-idempotency.txt` | PASS |
| **L6-1: 打包中途超时清理** | 打包阶段触发 `ZIP_TIMEOUT_S` 时返回 504 `TIMEOUT`；504 当场与后台 worker 退出后 `/tmp` 均无临时 zip 残留；重试仅生成 1 个 zip 对象 | **已修复通过**：HTTP 504 在 1003ms 返回，504 当场 `/tmp/renlink-zip-*` 残留为 0；~3.5s 后 worker 退出，`/tmp` 残留仍为 0；随后重试 200，store 仅 1 个 zip 对象 | `runtime/round2/04-timeout-cleanup-l6-1.txt` | **PASS** |
| **L6-4: 超时同 key 锁释放与并发** | worker 运行期间发起同 key 请求，锁由 worker 收尾释放，不启动重复并发打包 | worker 执行期间立即发起第二次请求返回 504，最大并发打包 worker 数为 1，锁未提前释放 | `runtime/round2/04-timeout-cleanup-l6-1.txt` | PASS |
| **硬边界与回归** | 请求带 cookie 返回 400；失败信封无 `cloud://` 伪造；L1/L3/L4 接口行为正常 | Cookie 返回 400 INVALID_REQUEST；/tmp 无残留；L1/L3/L4 正常 | `runtime/round2/05-regression-l1-l3-l4.txt` | PASS |

## R2-3. 缺陷跟踪清单（Round 2）

| 编号 | 严重度 | 是否阻塞 | 状态 | 描述与处置依据 |
|---|---|---|---|---|
| **L6-1** | P1 | 阻塞 | **已修复（本轮复核通过）** | `_PackScope` 机制使协程超时取消时立即清理已登记临时 zip，worker 退出时再次清理。实测 504 当场与 worker 结束后残留均为 0。 |
| **L6-4** | P2 | 非阻塞 | **已修复（本轮复核通过）** | per-key 锁改为由 worker 真正结束后释放，并发打包峰值保持为 1。 |
| **L6-6** | P3 | 非阻塞 | 观察项（同验收员） | `_PackScope.cancel()` 在 `_finished=True` 时未 unlink，存在 handover 与 claim 之间的低概率事件循环竞态窗口。非阻塞，建议后续顺手完善。 |
| **L6-2** | P1 | 阻塞（治理） | 待裁定 | 已有变更草稿 `chg_a17d6ce4e5d6.md`（pending，未 refreeze），待 run 负责人裁定收口方式。 |
| **L6-3** | P1 | 阻塞（发布门） | 待解决 | AC-015 缺端侧证据，依赖 l5 `chg_1c6f5fa13031` 变更关闭。 |

## R2-4. 结论

本轮运行时独立实测表明：针对 L6-1 的超时临时 zip 清理与 L6-4 并发锁机制均已完全成立，代码级功能与硬边界 AC 全部通过。总判定仍保持 **FAIL**，仅受制于 AC-015 端侧发布门禁（L6-3）与冻结时序治理裁定（L6-2）。

