# l3-media-delivery 独立 QA 验收报告

| 字段 | 值 |
|---|---|
| mode_id | `beacon-go` |
| run_id | `run_8703918d899b0b320fda8fe9` |
| stage | `qa` |
| feature | `l3-media-delivery` |
| truth | `docs/beacon/v0.1.0/features/l3-media-delivery/truth.md`，frozen；最新 refreeze 对应 `chg_81984a1ff2f3` |
| 验收基线 | `e8f23fe` |
| 验收 worktree | `/tmp/l3-qa-20261110`（验收前后 `git status --short` 为空） |
| 存储模式 | `STAGE_STORE=local`（本地验收）；生产 `cos` 上传未实测 |
| 验收者 | 验收员（独立于 maker） |
| 总判定 | **不能进 release 门**：AC-014 BLOCKED，AC-016 真实链接证据不足 |

验收对象为 `e8f23fe` 的干净 worktree，没有使用主仓混有 l7 未提交改动的工作区。验收过程未改断言、未放宽用例、未改 `container/` 与 `docs/beacon` 下任何在途文件，未 push、未发布、未 tick goal。

## 结论摘要

- AC-001..AC-013、AC-015 共 14 条判 **PASS**。
- **AC-014 判 BLOCKED**：视频半边是真实链路，图片清单经 `PARSE_L2_NOTE_STUB` 注入，不满足“真实 /parse 清单”的原文要求。
- **AC-016 判证据不足**：当前路由级行为通过，但历史真实 /parse 成功样本早于 `task_id` 变更，没有一条真实链接的成功响应能同时满足 `task_id` 正则与当前 schema。
- 15 个 case JSON 的内部 checks 全部为 true、summary 计数一致，但这些自检不能覆盖上面两处证据缺口。

## 实际执行的命令与真实输出

### 基线

```bash
git -C /Users/apple/Developer/Personal/renlink worktree add /tmp/l3-qa-20261110 e8f23fe
git -C /tmp/l3-qa-20261110 rev-parse --short HEAD
# e8f23fe
git -C /tmp/l3-qa-20261110 status --short
# （空）
```

### 主命令与真实 pytest 结果

```bash
cd /tmp/l3-qa-20261110
/tmp/l3-qa-venv/bin/python -m pytest tests/test_parse.py tests/test_stage.py -q
```

输出末尾（原始输出）：

```text
12 passed, 2 warnings in 5.71s
```

2 条 warning 均为 FastAPI `on_event` 弃用提示，不是失败。

首次用系统 Python 直接跑时，收集阶段因环境缺依赖失败，原始输出：

```text
E   ModuleNotFoundError: No module named 'jsonschema'
2 warnings, 1 error in 0.43s
```

随后用 `python3 -m venv --system-site-packages /tmp/l3-qa-venv` 建隔离环境并安装 `jsonschema==4.23.0`，再跑得到上面的 `12 passed`。没有修改仓库依赖或测试文件。

### 分项复跑

```bash
/tmp/l3-qa-venv/bin/python -m pytest tests/test_stage.py -q -k stage_file
# 2 passed, 9 deselected, 2 warnings in 0.93s

/tmp/l3-qa-venv/bin/python -m pytest tests/test_parse.py -q
# 1 passed in 0.14s
```

### 验收侧补充检查

另用临时脚本 `/tmp/l3-extra-qa.py`（不属于仓库产物）以 TestClient + 假 parser 做路由级核验，覆盖 AC-003/004/007/008/011/012/013/015/016，结果：

```text
SUMMARY total=27 failed=0
```

该脚本只证明当前代码的路由行为，不替代真实外链证据；AC-016 的真实链接缺口仍按下文判定。

## 15 个 case JSON 审计

目录：`docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261109-0030/`

| 审计项 | 实测 |
|---|---|
| `summary.case_files` | 15 |
| 实际 `case-*.json` 文件数 | 15 |
| `summary.cases` 条数 | 15 |
| `failures` / `blocked` | 0 / 0 |
| 文件清单与 summary 是否一致 | 一致 |
| `status=PASS` 的 case | 15 / 15 |
| `checks[].ok` 全为 true 的 case | 15 / 15 |
| “summary 写 PASS 但 check 为 false” | 0 例 |

| case | status | checks | STAGE_STORE |
|---|---|---|---|
| case-bad-index.json | PASS | 6 | local |
| case-expired-ttl.json | PASS | 3 | local |
| case-expired.json | PASS | 3 | local |
| case-idempotent.json | PASS | 4 | local |
| case-image-ok.json | PASS | 12 | local |
| case-multi-index.json | PASS | 8 | local |
| case-not-ready.json | PASS | 4 | cos（无 bucket/凭证） |
| case-real-video-and-image.json | PASS | 21 | local |
| case-response-shape.json | PASS | 5 | local |
| case-timeout.json | PASS | 3 | local |
| case-tmp-clean.json | PASS | 4 | local |
| case-too-large.json | PASS | 3 | local |
| case-user-cookie.json | PASS | 2 | local |
| case-video-ok.json | PASS | 9 | local |
| case-webp-to-jpg.json | PASS | 7 | local |

注意：`case-real-video-and-image.json` 的内部 PASS 只表示脚本断言全过，脚本本身接受 stub 注入的图片清单；这不等于 AC-014 的“真实 /parse 清单”已满足。

## 逐 AC 结论

| AC | TC | 结论 | 证据 | 依据 |
|---|---|---|---|---|
| AC-001 | TC-001 | **PASS** | `run-20261109-0030/case-image-ok.json` | 200；`kind=image`、`ext=jpg`、`bytes=514859`；fileID 以 `cloud://` 开头；本地读回 514859 字节，与 bytes 一致，Pillow 可解码。 |
| AC-002 | TC-002 | **PASS** | `run-20261109-0030/case-video-ok.json` | 200；`kind=video`、`ext=mp4`；读回 162700599 字节，与 bytes 一致；单请求 15376ms，小于 60s。 |
| AC-003 | TC-003 | **PASS** | `run-20261109-0030/case-webp-to-jpg.json` | webp 源转存后 `ext=jpg`；对象 magic 为 `ffd8ff`；Pillow 以 JPEG 解码成功；读回 517309 字节一致。补充检查确认原始 remoteUrl 未被改写。样本为本地 382KB webp，evidence.md 已注明。 |
| AC-004 | TC-004 | **PASS** | `run-20261109-0030/case-too-large.json` | 注入 `Content-Length: 209715201` 后返回 413、`TOO_LARGE`、无 fileID。补充检查用实际超限字节流验证视频与图片均返回 413。 |
| AC-005 | TC-005 | **PASS** | `case-expired.json`、`case-expired-ttl.json` | 未知 task_id 与 TTL=1 过期均返回 410、`STAGE_EXPIRED`、无 fileID；pytest 的 TTL 用例通过。 |
| AC-006 | TC-006 | **PASS** | `run-20261109-0030/case-not-ready.json` | `STAGE_STORE=cos` 且无 bucket/凭证时返回 503、`STAGE_NOT_READY`；响应不含 `cloud://`；/tmp 计数 1→1，无新增。 |
| AC-007 | TC-007 | **PASS** | `run-20261109-0030/case-idempotent.json` | 同一 task_id/index 两次调用 fileID 完全相同，对象未被重写。补充检查：第二次上游下载计数仍为 1；等价键 `platform:content_id:index` 在不同 task_id 下命中同一 fileID，下载计数为 0。 |
| AC-008 | TC-008 | **PASS** | `run-20261109-0030/case-bad-index.json` | index=-1 与越界 index=9999 均返回 400、`STAGE_FAILED`、`retryable=false`。补充检查清单缺项同样 400/STAGE_FAILED。 |
| AC-009 | TC-009 | **PASS** | `run-20261109-0030/case-response-shape.json` | 成功响应键集合恰为 `{ok,fileID,kind,ext,bytes}`；响应体 110 字节，远小于 1024000；无 /tmp 路径、无 base64、无文件流。 |
| AC-010 | TC-010 | **PASS** | `run-20261109-0030/case-tmp-clean.json` | 请求前 `renlink-stage-*` 为 0；成功请求后 0；失败请求后 0。pytest 的失败清理用例也通过。 |
| AC-011 | TC-011 | **PASS** | `run-20261109-0030/case-multi-index.json` | 同一 task_id 连续取 3 个 index，均 200，fileID 互异；读回字节分别为 514859、517309、514859，均与 bytes 一致。补充检查两个 task_id 的清单并存、互不覆盖。当前 schema 的路由级校验通过；历史 parse_schema 证据的时效问题见“证据链缺口”。 |
| AC-012 | TC-012 | **PASS** | `run-20261109-0030/case-user-cookie.json` | 请求体带 cookie 字段返回 400、`INVALID_REQUEST`；补充检查确认未触发任何下载。 |
| AC-013 | TC-013 | **PASS** | `run-20261109-0030/case-timeout.json` | 注入延迟后返回 504、`TIMEOUT`；请求前后 `renlink-stage-*` 均为 0。补充检查同样 504 且临时文件已清。 |
| AC-014 | TC-014 | **BLOCKED** | `run-20261109-0034/case-real-video-and-image.json`、`evidence.md`“已知限制” | 视频为真实抖音链路：162700599 字节、4285ms、读回一致。图片清单不是真实 /parse：由 `PARSE_L2_NOTE_STUB` 注入，l2-xhs-images 仍为 draft，l1 没有真实 xhs 图文解析；仅媒体 URL 是真实 xhs CDN。详见下节。 |
| AC-015 | TC-015 | **PASS** | `pytest tests/test_stage.py -q -k stage_file`、补充检查 | 2 passed；有效 `cloud://` fileID 返回 200，632B 与对象一致；`/etc/passwd` 返回 400；不存在的对象返回 502 `STAGE_FAILED`。 |
| AC-016 | TC-016 | **证据不足** | `pytest tests/test_parse.py`、`run-20261109-0027/0030/0034/0036-all`、补充路由检查 | pytest 1 passed，但该用例只构造本地 payload、手工调用 `stage_cache.remember` 注入 task_id 后校验 schema，没有调用 `POST /parse`。补充路由检查用假 parser 验证了 `/parse` 返回 `st_cf904e6e6ab823c61e6e32aa`、schema 通过且可直接用于 `/stage`。但历史真实 /parse 成功响应均无 `task_id`，当前环境没有取得变更后的真实成功样本，TC-016“POST /parse 一条真实链接”未闭合。 |

## AC-014 单独裁定：BLOCKED

AC-014 原文要求：“真实 /parse 清单连续调用 /stage 取 1 个视频 + 1 张图，两次都返回可读 fileID，读回字节与响应 bytes 一致；evidence 写明 STAGE_STORE 模式。”

现状拆开看：

- 视频半边 **满足**：真实抖音分享链接经 /parse 取得清单，/stage 返回 200，`bytes=162700599`，4.1~4.3s 完成，读回字节一致。
- 图片半边 **不满足真实清单要求**：evidence.md 的“已知限制”明确写明，图片项通过 l1 既有的 `PARSE_L2_NOTE_STUB` 接缝注入；l2-xhs-images 仍是 draft，l1 没有真实 xhs 图文解析；尝试公开 xhs note 链接经 f2 解析均返回 403。当前图片清单使用真实 note id 与真实 CDN 图片 URL，但清单本身不是 /parse 的真实产出。

因此 AC-014 不能判 PASS。它证明的是“/stage 能处理一份注入的图片清单”，而不是“真实 /parse 清单的图片半边端到端可用”。判 **BLOCKED**，缺的是：

1. 真实 xhs 图文链接经 /parse 成功产出 items 的链路（不能走 `PARSE_L2_NOTE_STUB`）；
2. 在该真实清单上对图片项调用 /stage，返回可读 fileID 并读回一致；
3. 与真实视频项合并重跑 `real-video-and-image`，落新 evidence，并写明 `STAGE_STORE`。

## 证据链缺口

1. **AC-016 的真实链接样本缺失。** `run-20261109-0027/0030/0034/0036-all` 里的真实 /parse 成功响应都没有 `task_id` 字段。用当前 `contract/parse_response.schema.json`（success 的 required 含 `task_id`）复验，4 个 run 中所有带 /parse 200 body 的 case 共 40 个 parse body，全部校验失败，首个错误均为 `'task_id' is a required property`。这些 case 里的 `parse_schema=true` 是采集时的旧 schema 结果，不能当作当前契约的证据。
2. **代码本身已在路由层补上 task_id。** 当前 HEAD 的 `container/app/routes_parse.py` 在成功路径执行 `task_id = stage_cache.remember(payload)` 并写入响应；补充路由检查也验证了格式、schema 与 /stage 可用性。缺的是“真实链接跑一遍”的实测证据，不是代码路径不存在。
3. **生产 COS 上传未实测。** 本地验收按 truth Q3 使用 `STAGE_STORE=local`，这符合本地验收约定；但 AC-006 只覆盖“未配置存储返回 503”，真实 bucket 与云托管临时密钥下的上传尚未验证。若 release 包含生产部署，需要在 release 前补一次真实 COS 上传与读回。
4. **主仓当前有 l7 未提交改动。** 本报告没有使用该工作区做验收；这不是 l3 的缺陷，但后续复验仍应使用干净 worktree，避免把 l7 改动混进 l3 证据。

## 必改项

1. **AC-014 必改**：打通真实 xhs 图文 /parse（或明确由 l1/l2 提供非 stub 的真实清单），在不使用 `PARSE_L2_NOTE_STUB` 的条件下重跑 1 视频 + 1 图，保存新 evidence，读回字节必须与 bytes 一致。
2. **AC-016 必改**：用一条真实链接在变更后的代码上取得 /parse 成功响应，证明 `task_id` 匹配 `^st_[0-9a-f]{24}$`、通过当前 schema，并直接用该值调用 /stage 成功。若当前环境拿不到抖音 operator cookie，需由具备有效会话的一方提供可复现环境或样本。
3. **证据重采**：在 `task_id` 已进入契约后重跑 smoke，更新 `run-20261109-0030/0034/0036-all` 中带 parse body 的 case，使 `parse_schema` 对当前 schema 为真；否则任何按 tests.md 复验的人都会得到 schema 失败。
4. **生产门补充（非本地 AC 阻塞项）**：release 若涉及生产 COS，补一次真实 bucket 上传、fileID 读回与 `/stage/file` 流式下载。

## 最终判定

**FAIL / BLOCKED，不能进 release 门。** 14 条 AC 通过，但 AC-014 因图片半边使用 stub 清单判 BLOCKED，AC-016 因缺真实链接的成功样本判证据不足。两者未闭合前，release 保持 blocked。

---

验收边界：只读验收；未修改 `container/`、`docs/beacon` 下的在途文件，未改测试断言，未 push、未发布、未 tick goal。本报告是唯一新增文件。
