# l6-zip-export · spec / AC 合规验收（独立验收员）

- 日期：2026-11-09 06:30（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`（实现 `8ed9b2e`，工作区干净）
- truth：`docs/beacon/v0.1.0/features/l6-zip-export/truth.md`（`status: frozen`，HEAD 时点）
- maker：任链接 后端（codex）；本验收未改代码、未改 truth、未 commit / push
- 验收对象：`container/app/routes_zip.py`、`container/app/zipkit.py`、`tests/test_zip.py`，以及 l6 复用的 `container/app/stage_store.py` 读回能力
- 总判定：**FAIL**（2 项阻塞代码缺陷 + 2 项阻塞治理缺陷）

## 1. 实跑基线

```
$ .venv/bin/python -m pytest tests -q
45 passed, 3 warnings in 7.95s
```

l6 单文件：`tests/test_zip.py` 15 个用例全部通过。额外行为探针见 §3（脚本在 `/tmp/qa-probe/`，不入库）。

## 2. AC 逐条判定

| AC | 判定 | 依据 |
|----|------|------|
| AC-001 | PASS | `tests/test_zip.py:113-146`：200、`ok=true`、`fileID` 以 `cloud://local/l6/<task>/` 开头、`bytes` 与对象字节一致、`count=3`、`zipfile` 可读且条目数为 3 |
| AC-002 | PASS | `tests/test_zip.py:149-161`（[3,1,3]）+ 本轮实跑 [7,1,7]：200、`count=2`、条目名 `["001.jpg","007.jpg"]` |
| AC-003 | PASS | `tests/test_zip.py:261-274`；本轮计数探针：同 task 连打两次 → `fetch=1, put=1, zip_objects=1`，两次 `fileID` 相同；`tests/test_zip.py:277-293` 关闭缓存两次 sha256 相同 |
| AC-004 | PASS | `tests/test_zip.py:164-173`（未知 task 410/`STAGE_EXPIRED`/`retryable=false`/无 fileID/无 `cloud://`）、`:175-189`（TTL 过期同码） |
| AC-005 | PASS | (a) `tests/test_zip.py:225-242`；(c) `:245-258`；(b) 本轮探针 `STAGE_STORE=cos` + 有 bucket + 无凭证 + 无凭证端点 → 503 `ZIP_NOT_READY`、无 `cloud://` |
| AC-006 | PASS | `tests/test_zip.py:192-208`（实际已转存 3 张、上限 2 → 413、无 l6 对象）；本轮显式 51 个 index → 413 `TOO_LARGE`、无对象 |
| AC-007 | PASS | `tests/test_zip.py:211-222`（源对象累计超限 → 413）；本轮生成 zip 超限探针：源 50B、上限 60B → 413 `TOO_LARGE`、无 l6 对象 |
| AC-008 | PASS | `tests/test_zip.py:342-358`：`read`/`write`/`upload` 三种注入均 502 `ZIP_FAILED`、`retryable=true`、无 fileID、无临时残留 |
| AC-009 | PASS | `tests/test_zip.py:381-409`：九类非法输入（含 `cookie` 字段、空数组、视频 index、非整数、负数、不在清单、非 JSON）均 400 `INVALID_REQUEST`；`container/app/routes_zip.py:35-52` |
| AC-010 | PASS | `tests/test_zip.py:125,145`：成功响应键集合恰为四字段且 ≤1024000 字节；本轮实测键集合 `["bytes","count","fileID","ok"]` |
| AC-011 | PASS | `tests/test_zip.py:325-339` 混合已转存/未转存 `count=1`、全未转存 400；`container/app/zipkit.py:359-378` 无 `/stage` 调用 |
| AC-012 | **FAIL** | 成功与多数失败路径干净，但**打包阶段超时**后 `/tmp` 残留：本轮探针见 §3，`/tmp/renlink-zip-jn6cm85u.zip` 在 504 返回时及 2.4s 后仍在 |
| AC-013 | **FAIL** | 504 `TIMEOUT` / `retryable=true` / 无 fileID 正确；但「临时文件已清理」不成立，与 AC-012 同一泄漏。`container/app/zipkit.py:332-344` 的 `_unlink(zip_path)` 只在 `await asyncio.to_thread` 正常返回后执行，`wait_for` 取消时不会执行 |
| AC-014 | PASS | `tests/test_zip.py:132-144`：条目名 `000/001/002`、时间 1980-01-01 00:00:00、`ZIP_STORED`、无目录条目；`:277-293` 关缓存两次 sha256 相同 |
| AC-015 | **EMPTY** | 无真机/PC 证据；l5 侧契约对齐变更 `chg_1c6f5fa13031` 仍为 `pending`，l5 `materials_status: stale`。容器内无法验证 `wx.shareFileMessage` / `wx.saveFileToDisk` |
| AC-016 | **FAIL** | `/parse`、`/stage` 与 l1/l3 未改（`git diff 8ed9b2e^ 65c3112 -- routes_parse.py contract.py routes_stage.py l1-parser-core l3-media-delivery` 为空），`cookie`→400 通过；但 l5 `tasks.md`、`tests.md` 有 git diff（`materials_status: current → stale`，另有 `changes/chg_1c6f5fa13031.md`），不满足「l5 git diff 为空」的字面判据 |

## 3. 关键探针与原始结果

超时清理探针（`ZIP_TIMEOUT_S=1`，包装真实 `_pack_sync` 使 zip 已落 /tmp 后再耗时 2s）：

```json
{
 "ac013_timeout_http": 504,
 "ac013_timeout_code": "TIMEOUT",
 "ac013_residue_at_response": ["renlink-zip-jn6cm85u.zip"],
 "ac013_residue_after_2.4s": ["renlink-zip-jn6cm85u.zip"],
 "ac007_generated_zip_over": {"http": 413, "code": "TOO_LARGE", "l6_objects": 0},
 "ac005b_cos_no_creds": {"http": 503, "code": "ZIP_NOT_READY", "has_cloud": false},
 "ac011_mixed": {"http": 200, "count": 1},
 "ac010_keys": ["bytes", "count", "fileID", "ok"]
}
```

幂等计数探针（两次请求）：`{"same_fileID": true, "fetch": 1, "put": 1, "zip_objects": 1}`。

## 4. 缺陷清单

| 编号 | 严重度 | 是否阻塞 | 描述 | 必改项 |
|------|--------|----------|------|--------|
| L6-1 | P1 | **阻塞** | 打包阶段触发 `ZIP_TIMEOUT_S` 时，`asyncio.wait_for` 取消协程，`_pack_sync` 已在 `/tmp` 建好的 `renlink-zip-*` 无人删除；AC-012/AC-013 明文要求 TIMEOUT 后临时文件数为 0 | 让临时 zip 的生命周期脱离协程取消：在发起打包前登记路径并在取消/超时分支删除，或由打包线程自持 `try/finally` 删除；补一条「打包已开始后超时」的自动化测试，断言 `/tmp/renlink-zip-*` 为 0 |
| L6-2 | P1 | **阻塞**（治理） | 实现提交 `8ed9b2e` 的树中，本湖 truth 仍为 `status: draft`，AC 表仅两行占位符；`AC-001..016` 实体与 `status: frozen` 是在其后的 `65c3112` 才写入。违反「truth 未冻结不得实现」，冻结的 AC 不是实现前的前置契约 | 在 beacon-go run `run_1084fcb4301353f56601ec48` 中补齐/更正 truth 冻结时序证据；若属 refreeze 后补，需写明变更单与基线 sha，且不得把当前 AC 作为既成事实的反推 |
| L6-3 | P1 | **阻塞**（发布门） | AC-015 无真机/PC 证据；l5 `chg_1c6f5fa13031` 未关闭，l5 仍 `stale`，端侧契约未对齐 | l5 变更落地并 refreeze 后补真机分享/PC 存盘证据；在此之前 l6 不能宣称 AC-015 通过 |
| L6-4 | P2 | 非阻塞 | 超时后打包线程继续运行，而 `_build_cached` 的 `finally` 已释放同键锁；后续请求可能与仍在运行的旧打包并发，违背「同进程内同一缓存键单锁串行」 | 取消后等线程退出再释放锁，或把锁的释放交给线程完成 |
| L6-5 | P3 | 非阻塞 | AC-016 要求 l5 文档 diff 为空，实际有 2 处 frontmatter 变更（有正式变更单，非越权改正文） | 在 evidence 中登记该 diff 属 `chg_1c6f5fa13031` 的必要副作用，或调整 AC-016 措辞；不得静默忽略 |

## 5. 结论

l6 主链路（成功、子集、幂等、过期、三类存储未就绪、数量/体积上限、故障注入、非法输入、响应形状、只打已转存、zip 可复现）实现与测试均成立；但 **AC-012/AC-013 的超时清理实测失败**，属硬边界「`/tmp` 成功失败都清理」违约，必须修复。叠加 truth 冻结时序与 l5 端侧未对齐两项治理缺口，本轮 **FAIL**。

---

# Round 2（返工后独立复验）

- 日期：2026-11-09 06:59（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`；返工改动**未提交**在工作区（`container/app/zipkit.py`、`container/app/parsers/xhs.py`、`tests/test_zip.py`、`tests/test_xhs.py`，另有 evidence/rework、changes 草稿与两湖 `tasks.md`/`tests.md` 的 `materials_status: current → stale`）
- 树指纹（派单口径）：`git diff container tests | shasum -a 256` = `1d0e7d9acf1df416ba4e04a57e4e845eb7e46392e8237546657124c1ce3e9b20`（与派单一致）
- truth 正文 `git diff` 为空，两湖 `status: frozen` 不变；本验收未改实现、未改 truth、未 commit / push
- 复验范围：仅 L6-1（超时清理）、L6-4（同键锁串行）及回归；其余 AC 复核不回归
- 总判定：**FAIL**（AC-015 EMPTY、AC-016 FAIL 两项外部/端侧门禁仍在；**三条返工代码缺陷已清零**，代码级 AC 全部 PASS）

## R2-1. 实跑基线

```
$ .venv/bin/python -m pytest tests -q
50 passed, 3 warnings in 10.62s

$ .venv/bin/python -m pytest tests/test_zip.py tests/test_xhs.py -q
27 passed, 3 warnings in 5.32s
```

行为探针（不入库）：`/tmp/qa-probe-r2/probe_l6_async.py`。为避免 `TestClient` 在 `client.post()` 返回前等待默认 executor 线程收尾（实测会把 1s 的 504 拖到 4s 才返回，属测试工具假象），本轮改用 `httpx.ASGITransport` 在同一事件循环内直连 ASGI，时序与真实服务一致。

参数：`ZIP_TIMEOUT_S=1`、`ZIP_FAKE_PACK_DELAY_MS=4000`（在打包 worker 内延迟，确保 504 时 worker 仍在运行）。

## R2-2. AC 逐条判定

| AC | 判定 | 依据 |
|----|------|------|
| AC-001 ~ AC-011 | PASS | 与 Round 1 结论一致，未受返工影响；本轮 `tests/test_zip.py` 全绿 + 回归探针（见 R2-3） |
| AC-012 | **PASS** | 打包进行中触发超时：504 当场与 worker 结束后 `/tmp/renlink-zip-*` 均为 0（R2-3）。残余竞态见 L6-6（非阻塞） |
| AC-013 | **PASS** | 504 `TIMEOUT`、`retryable=true`、无 fileID；1012ms 返回（1s 预算），临时文件已清理 |
| AC-014 | PASS | `tests/test_zip.py` 条目名/时间戳/`ZIP_STORED`/两次 sha256 用例全绿 |
| AC-015 | **EMPTY** | 仍无真机/PC 证据；l5 `chg_1c6f5fa13031` 仍 `pending`（未变化） |
| AC-016 | **FAIL** | l1/l3/l5 truth/tests/tasks/evidence 的 git diff 中，l5 侧仍有 `materials_status: current → stale`（`chg_1c6f5fa13031` 副作用）；`cookie`→400、`/parse` `/stage` 字段未变均通过。与 Round 1 同因，非本轮返工引入 |

## R2-3. L6-1 / L6-4 关键探针原始结果

```json
{
 "first": {"status": 504, "elapsed_ms": 1012,
           "error": {"code": "TIMEOUT", "retryable": true}, "has_fileID": false},
 "residue_at_504": [], "zip_objects_at_504": [],
 "second_immediate": {"status": 504, "elapsed_ms": 1003},
 "max_concurrent_pack_workers": 1,
 "residue_after_worker": [], "zip_objects_after_worker": [],
 "third_after_worker": {"status": 200, "elapsed_ms": 5, "count": 2},
 "zip_objects_after_success": [".../store/l6/st_81a92b4b9a7236de4b4d39a9/83b97b859aa5f81b.zip"],
 "final_max_concurrency": 1
}
```

- L6-1：504 返回时与 4s worker 真正退出后，`/tmp` 残留均为 0，本地存储无任何 l6 zip 对象；随后同 key 重试 200、`count=2`、只有 1 个 zip 对象（未重复上传）。
- L6-4：worker 仍在运行时立刻发起第二次请求，并发打包 worker 峰值为 **1**；第二次请求因自身 1s 预算耗尽返回 504，但没有启动第二个打包线程。锁已交给 worker 收尾释放。
- 边界（L6-6）：`_PackScope.handover()` 已成功、协程尚未 `claim()` 的瞬间收到 `cancel()` 时，`cancel()` 在 `_finished=True` 分支提前返回、不删除已登记路径。单元级复现：`handover -> True`、文件仍存在，随后 `cancel()` 返回 True 且文件仍存在。真实链路窗口在「worker 完成 → 任务恢复」之间的同一事件循环 tick，概率极低，未在端到端探针复现。

## R2-4. 缺陷清单（Round 2）

| 编号 | 严重度 | 是否阻塞 | 状态 | 描述 / 必改项 |
|------|--------|----------|------|----------------|
| L6-1 | P1 | 阻塞 | **已修复（本轮复核通过）** | 超时后 `/tmp` 残留已消除；504 当场与 worker 退出后均为 0 |
| L6-4 | P2 | 非阻塞 | **已修复（本轮复核通过）** | per-key 锁由 worker 收尾释放；并发打包峰值 1 |
| L6-6 | P3 | 非阻塞 | 新增 | `_PackScope.cancel()` 在 `_finished=True` 时未删除 `self._paths`，handover/claim 之间被取消会残留 1 个 zip。建议：`_finished` 分支同样 `_unlink` 已登记路径（或 `claim()` 前把路径移出 scope）。非阻塞：单文件 /tmp、极端时序、无数据影响 |
| L6-2 | P1 | 阻塞（治理） | **未关闭** | 已出 `changes/chg_a17d6ce4e5d6.md`（pending，未 refreeze，truth 正文未动）；仍需 run 负责人在 `run_1084fcb4301353f56601ec48` 内裁定走「更正依据后继续」还是「正式 change + refreeze」 |
| L6-3 | P1 | 阻塞（发布门） | **未关闭** | AC-015 无端侧证据，依赖 l5 `chg_1c6f5fa13031`；maker 已确认不属本湖代码范围 |
| L6-5 | P3 | 非阻塞 | 未变化 | AC-016 的 l5 文档 diff 需登记归属或调整 AC 措辞 |

## R2-5. 结论

三条返工代码缺陷（L6-1、L2-1、L2-2 中的 l6 部分）在本轮独立实跑中全部通过：超时清理、worker 收尾后再放锁、失败后重试只产出一个 zip 对象。l6 代码级 AC 现全部 PASS；总判定仍为 **FAIL**，仅因 AC-015（EMPTY，l5 端侧未对齐）与 AC-016（l5 文档 diff）两项湖泊外部门禁未清，叠加 L6-2 冻结时序治理项待裁定。新增 L6-6 为低概率残余竞态，建议下次改动顺手修掉，不阻塞本轮。
