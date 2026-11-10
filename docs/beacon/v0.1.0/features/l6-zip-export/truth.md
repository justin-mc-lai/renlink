---
slug: l6-zip-export
version: v0.1.0
status: frozen
language: zh
domain_required: false
ux_required: false
parser_contract: beacon-feature-package-v2
truth_source_model: feature_package_authoritative
package_maturity: filled
materials_status: current
intent_confirmed: true
program_ref: docs/beacon/v0.1.0/lake-proposal.json
run_ref: run_1084fcb4301353f56601ec48
stack: python-fastapi-cloudrun-container
canonical_refs:
  truth: docs/beacon/v0.1.0/features/l6-zip-export/truth.md
  tests: docs/beacon/v0.1.0/features/l6-zip-export/tests.md
  tasks: docs/beacon/v0.1.0/features/l6-zip-export/tasks.md
  evidence: docs/beacon/v0.1.0/features/l6-zip-export/evidence.md
---

# Requirement Truth: l6-zip-export

## 人话

用户在图文解析后，把同一个 task 里已经转存到对象存储的图片一键打成一个 zip：手机转给微信聊天或文件传输助手，电脑直接存盘。只打包已经转存成功的图片，只把文件流交给系统分享面板，服务端只回一个可下载的 fileID；没有存储就明确说没准备好，绝不返回一个假的地址。

## User Intent

l3 已经把图片一张张换成了 cloudID，但用户没法把九张图一次性发给别人或带回电脑。l6 负责把同一 task 的已转存图片收集起来、打成 zip、上传对象存储，返回一个能被 `wx.cloud.downloadFile` 读取的 fileID；重复点导出不重复打包也不重复上传；任务过期、图片太多太大、存储未就绪、打包失败都要有固定错误码，前端据此给人话提示。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
language: zh
source: user_intent
utterance: "l6：POST /zip 把同一 task 已转存的图片打包 zip → 上传 COS → 返回 cloudID，端侧 wx.shareFileMessage 转发（PC 降级 saveFileToDisk）"
goal: "容器提供 POST /zip，输入 {task_id,indexes?}，把该 task 已转存成功的图片打成 zip 上传对象存储，返回 {ok,fileID,bytes,count}，fileID 可被 wx.cloud.downloadFile 读取；同 task 与同 index 集合幂等"
non_goals: "链接解析（l1）；单文件下载与转码（l3）；小程序页面与相册保存（l5）；ZIP 解压、加密、分卷、断点续传；跨 task 合包；接收用户 cookie；响应携带文件流/base64/本地路径；持久盘缓存"
constraints: "单请求 ≤60s；只打包已转存图片且不重跑 /stage；≤50 张且 zip 总量 ≤200MB；task_id 沿用 l3 的 10 分钟清单缓存；无 COS 凭证返回 ZIP_NOT_READY；响应 ≤1024000 字节且只回 fileID；zip 条目名与顺序稳定；/tmp 临时文件成功失败都清理"
scope_mode: "lake"
```

## 目标

- 交付一个可独立 curl 的打包接口：拿到有效 task_id，就能把该 task 已转存的图片换成一个 zip 的 fileID，不依赖小程序。
- 把「选图 → 读回对象 → 打包 → 上传 → 回 fileID」压进一次请求，满足 60s 硬上限。
- 让重复导出便宜且结果稳定：同 task_id 与同 index 集合直接回同一个 fileID，不重复打包、不重复上传。
- 让失败可判别：清单过期、请求非法、图片太多太大、存储未就绪、打包上传失败、超时各有固定 HTTP 状态与错误码。
- 让 zip 可复现：条目名、条目顺序、时间戳与压缩方式固定，关掉缓存重打两次字节一致。
- 让端侧只做两件事：拿 fileID 下载，然后交给微信分享或电脑存盘；取消与失败都有明确文案。

## 非目标

- 不做链接解析与清单生成（l1），不改变 `/parse` 字段与 schema。
- 不做单文件下载、webp→jpg 转码与单文件转存（l3），不重新触发 `/stage`。
- 不做小程序页面、相册保存、历史记录（l5），只锚定 l5 的 ZIP 按钮与转发交互。
- 不做 ZIP 解压、密码、分卷、断点续传、增量打包。
- 不做跨 task 或跨用户合包，不接收 `cloudIDs` 数组作为入参（见 Open Questions Q2）。
- 不接收用户 cookie，响应不携带文件流、base64、临时路径或容器本地路径。
- 不使用容器持久盘缓存，zip 对象与其他产物一律进对象存储。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | 契约 `{task_id, indexes?}` → `{ok, fileID, bytes, count}` | `task_id` 必填，格式 `st_[0-9a-f]{24}`；`indexes` 可省略，省略时取该 task 全部已转存图片；成功响应恰好四个字段 | AC-001、AC-010 |
| C2 | 幂等：同 task 重复请求返回同一 fileID | 缓存键 `zip:v1:<task_id>:<去重升序 index 逗号串>`，TTL 默认 600s（`ZIP_CACHE_TTL_S`）；命中直接回缓存，校验对象仍存在；zip 对象键由 task_id 与 index 集合确定性推导 | AC-003 |
| C3 | 错误码固定 | 400 INVALID_REQUEST、410 STAGE_EXPIRED、413 TOO_LARGE、503 ZIP_NOT_READY、502 ZIP_FAILED（retryable=true）、504 TIMEOUT（沿用 l3 AC-013）；失败响应一律 `ok=false` 且不含 fileID | AC-004 至 AC-009、AC-013 |
| C4 | 单请求 ≤60s；/tmp 清理 | `ZIP_TIMEOUT_S` 默认 60，到点中止返回 504 TIMEOUT；临时文件只写 `/tmp/renlink-zip-*`，`finally` 清理成功与失败路径 | AC-012、AC-013 |
| C5 | 端侧转发与降级 | 手机 `wx.shareFileMessage({filePath,fileName})`；`platform` 为 windows/mac 时 `wx.saveFileToDisk`；取消与失败分别给固定文案；错误码按本湖错误表映射 | AC-015 |
| C6 | 只打已转存图片，不触发 /stage | 选图同时要求清单项存在、`type=image`、`stage_cache` 有对象记录、`store.exists(fileID)` 为真；未转存项跳过且不计入 count | AC-011 |
| C7 | zip 条目稳定 | 按 index 升序；条目名 `{index:03d}.{ext}`；固定时间戳 1980-01-01 00:00:00；ZIP_STORED；不写目录条目 | AC-014 |
| C8 | 响应 ≤1024000 字节，只回 fileID | 成功响应只有 `ok`、`fileID`、`bytes`、`count`；无 base64、无文件流、无 `/tmp` 或绝对路径 | AC-010 |
| C9 | 无 COS 凭证返回 ZIP_NOT_READY | `STAGE_STORE=cos` 且缺 bucket/凭证，或 local 存储目录不可读写时，不打包、不上传、不返回任何 `cloud://` 值 | AC-005 |
| C10 | 依赖边界与禁止项 | 不改 l1/l3/l5 已冻结正文；请求体出现 `cookie` 字段返回 400 INVALID_REQUEST；不新增 `/parse`、`/stage` 行为 | AC-016 |

## Alignment Surface

本湖站在 l3 之后：只消费 l3 的 `stage_cache` 对象记录与对象存储里的既有对象，把「多张图」收成「一个 zip 文件ID」，交给 l5 的 ZIP 按钮去下载与转发。解析、单文件转存、页面渲染都不在本湖。l6 不重新下载源站媒体，也不重跑 `/stage`；打包时读回的既有对象，其字节就是 l3 当初转存成功的字节。

## Open Questions

One question at a time; a package cannot be signed while a row is open.
Use beacon truth ask / beacon truth answer to drive this ledger.

| Q ID | Question | Recommendation | Status | Answer | Source |
|------|----------|----------------|--------|--------|--------|
| Q1 | 谁、什么问题、什么算完成？ | 用户把同一 task 已转存的多张图一次转给微信或电脑；`/zip` 返回可读 fileID 即完成 | answered | 运营方/用户完成图文解析并逐张转存后，需要把同一 task 的多张图片一次性转给微信聊天或带回电脑；调用 POST /zip 拿到可被 wx.cloud.downloadFile 读取的 zip fileID，下载后分享或存盘成功即算完成 | human |
| Q2 | `/zip` 入参与响应字段以哪份为准？l5 假定 `{cloudIDs,zipName}`→`{cloudID}` | 以本湖 `{task_id,indexes?}`→`{ok,fileID,bytes,count}` 为准，与 l3 的 fileID 命名一致 | answered | 本湖冻结口径为 task_id + indexes，成功只回 fileID；l5 Q7 已约定「待 l6 冻结后复核对齐，差异走变更流程」，l5 正文不在本湖修改 | human |
| Q3 | 清单里存在但未转存的 index 怎么处理？ | 跳过、不计入 count、不触发 /stage；若显式请求的 index 全部未转存，返回 400 INVALID_REQUEST | answered | 跳过是默认行为；显式请求集与已转存集交集为空时用 400 INVALID_REQUEST 说明「请先逐张转存」，不伪造空 zip | human |
| Q4 | 幂等缓存键与 TTL？ | `zip:v1:<task_id>:<去重升序 index 逗号串>`，TTL 600s，与 l3 清单缓存对齐 | answered | 缓存键按上述固定格式；`ZIP_CACHE_TTL_S` 默认 600；manifest 过期后先判 410，缓存不得越过清单有效期 | human |
| Q5 | 单请求超过 60s 用什么错误码？ | 504 TIMEOUT、retryable=true，沿用 l3 AC-013 的 TIMEOUT 语义 | answered | 504 TIMEOUT；不新增别的超时码，也不把它归进 ZIP_FAILED | human |

## Intent Coverage

Every AC must trace to the intent or evidence it serves.

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | 目标：task 全部已转存图片打成一个 zip 并回可读 fileID | tests.md TC-001 |
| AC-002 | 约束 C1：indexes 子集与排序归一 | tests.md TC-002 |
| AC-003 | 约束 C2：同 task 同 index 集合幂等 | tests.md TC-003 |
| AC-004 | 约束 C3：task 过期可判别 | tests.md TC-004 |
| AC-005 | 约束 C9：存储未就绪不得伪造成功 | tests.md TC-005 |
| AC-006 | 约束 C3：图片数量上限 | tests.md TC-006 |
| AC-007 | 约束 C3：zip 总量上限 | tests.md TC-007 |
| AC-008 | 约束 C3：打包/读回/上传失败可判别 | tests.md TC-008 |
| AC-009 | 约束 C1、C3：非法请求可判别 | tests.md TC-009 |
| AC-010 | 约束 C8：响应体形状与体积 | tests.md TC-010 |
| AC-011 | 约束 C6：只打已转存，不重跑 /stage | tests.md TC-011 |
| AC-012 | 约束 C4：临时文件成功失败都清理 | tests.md TC-012 |
| AC-013 | 约束 C4：60s 硬上限 | tests.md TC-013 |
| AC-014 | 约束 C7：zip 内容与字节稳定 | tests.md TC-014 |
| AC-015 | 约束 C5：端侧分享与电脑存盘 | tests.md TC-015 |
| AC-016 | 约束 C10：依赖边界与禁止项 | tests.md TC-016 |

## Acceptance Criteria

| AC ID | Criterion |
|-------|-----------|
| AC-001 | 对有效 task_id 且已转存 N 张图片（N≥1）调用 `POST /zip` 且不带 indexes，返回 200、`ok=true`、`fileID` 以 `cloud://` 开头、`bytes>0`、`count=N`；按 fileID 读回的 zip 字节数等于 `bytes`；zip 可被 `unzip -l` 打开且条目数为 N |
| AC-002 | 传 `indexes:[7,1,7]`（清单含 index 1 与 7 的已转存图片）时返回 200、`count=2`；zip 条目名按升序为 `001.<ext>`、`007.<ext>`；重复的 7 只出现一次 |
| AC-003 | 同一 task_id 与同一 index 集合（顺序打乱并含重复，归一后相同）第二次请求返回与第一次完全相同的 `fileID`、`bytes`、`count`；zip 对象 sha256 不变；读回源对象与上传 zip 的计数均不增加 |
| AC-004 | 未知 task_id 返回 410、`ok=false`、`error.code=STAGE_EXPIRED`、`retryable=false`，响应不含 fileID；超过 `STAGE_TASK_TTL_S` 的 task_id 返回完全相同的状态与错误码 |
| AC-005 | 以下三种情形均返回 503、`ok=false`、`error.code=ZIP_NOT_READY`、`retryable=true`，响应不含 `cloud://` 字符串，`/tmp` 不新增 `renlink-zip-*`：(a) `STAGE_STORE=cos` 且未配置 `COS_BUCKET`；(b) `STAGE_STORE=cos` 且未配置凭证；(c) local 存储目录不可读写 |
| AC-006 | 去重后显式请求的 index 数超过 `ZIP_MAX_IMAGES`（默认 50）时返回 413、`error.code=TOO_LARGE`、`retryable=false`，不产生 zip 对象；实际选中已转存图片数超过 50 时返回完全相同的状态与错误码 |
| AC-007 | 选中源对象字节累计超过 `ZIP_MAX_BYTES`（默认 209715200）时返回 413、`error.code=TOO_LARGE`、`retryable=false`，不产生 zip 对象；生成 zip 实际字节超过该值时返回完全相同的状态与错误码 |
| AC-008 | 读回源对象失败、写 zip 失败、上传 zip 失败，这三种情形均返回 502、`error.code=ZIP_FAILED`、`retryable=true`，响应不含 fileID；服务不吞错返回伪造成功 |
| AC-009 | 以下八类输入均返回 400、`error.code=INVALID_REQUEST`、`retryable=false`：task_id 缺失、task_id 格式非法、indexes 非数组、indexes 元素非整数、indexes 元素为负数、index 不在清单、显式指定视频 index、显式传空数组；请求体不是 JSON 对象时同样返回 400 INVALID_REQUEST；清单内但未转存的 index 不算非法（见 AC-011） |
| AC-010 | 任意 `/zip` 成功响应体不大于 1024000 字节；键集合恰为 `ok`、`fileID`、`bytes`、`count`；响应无 base64、无文件流、无 `/tmp/` 路径、无文件系统绝对路径 |
| AC-011 | 传入 `indexes` 同时包含已转存与未转存的图片 index 时，只打包已转存项，`count` 等于已转存项数；未转存项不触发 `/stage`（源对象数、`/stage` 下载计数不变）；显式请求的 index 全部未转存时返回 400 INVALID_REQUEST 且不产生 zip 对象 |
| AC-012 | `/zip` 成功请求与失败请求（含 TOO_LARGE、ZIP_FAILED、TIMEOUT、ZIP_NOT_READY、INVALID_REQUEST）结束后，`/tmp` 下 `renlink-zip-*` 文件数为 0 |
| AC-013 | 读回、打包、上传任一步骤使单请求超过 `ZIP_TIMEOUT_S`（默认 60）时返回 504、`error.code=TIMEOUT`、`retryable=true`，响应不含 fileID，临时文件已清理 |
| AC-014 | zip 条目名固定为 `{index:03d}.{ext}`，按 index 升序；条目时间戳固定为 1980-01-01 00:00:00，压缩方式为 ZIP_STORED，不含目录条目；`ZIP_CACHE_TTL_S=0` 时连打两次，两次 zip 的 sha256 相同 |
| AC-015 | 手机端拿到 fileID 后 `wx.cloud.downloadFile` 再 `wx.shareFileMessage` 唤起微信会话选择；PC 端降级 `wx.saveFileToDisk`；用户取消、下载失败、分享失败各有固定文案；错误码 ZIP_NOT_READY、TOO_LARGE、STAGE_EXPIRED、ZIP_FAILED、INVALID_REQUEST 映射到固定人话文案，锚定 l5 AC-006 与异常提示矩阵 |
| AC-016 | 本湖改动仅限 `docs/beacon/v0.1.0/features/l6-zip-export/` 与实施阶段的 l6 专属代码；l1/l3/l5 的 truth.md、tests.md、tasks.md、evidence.md git diff 为空；请求体带 `cookie` 字段返回 400 INVALID_REQUEST；`/parse` 与 `/stage` 响应字段不变 |

## 接口契约

### 请求

```json
{"task_id": "st_3f1c9a0b7e2d4c58a1b6d0f3", "indexes": [3, 1, 7]}
```

- `task_id` 必填，字符串，格式 `st_[0-9a-f]{24}`，与 l3 的确定性 task_id 完全相同。
- `indexes` 可选，整数数组；缺省表示「该 task 当前全部已转存图片」；元素去重后按升序归一；显式空数组视为非法。
- 其他字段忽略；出现 `cookie` 字段视为违规请求。
- `indexes` 中的整数必须是清单里存在的 `items[].index`，且对应 `type=image`；视频 index 不得显式出现。

### 成功响应（200）

```json
{"ok": true, "fileID": "cloud://local/l6/st_3f1c9a0b7e2d4c58a1b6d0f3/9c1f0a2b7d4e5c60.zip", "bytes": 1048576, "count": 7}
```

- 只有这四个字段。
- `fileID` 必须能被 `wx.cloud.downloadFile` 与本地 mock 读取；`bytes` 为 zip 对象字节数；`count` 为 zip 内图片条目数。
- zip 对象键规则见「打包与存储规则」。

### 失败响应

```json
{"ok": false, "error": {"code": "ZIP_NOT_READY", "message": "打包服务未配置对象存储", "retryable": true}}
```

| code | HTTP | 触发条件 | retryable |
|------|------|----------|-----------|
| INVALID_REQUEST | 400 | 请求体非法、task_id 格式错、indexes 非法、index 不在清单、显式指定视频、显式空数组、全部 index 未转存 | false |
| STAGE_EXPIRED | 410 | task_id 未知或清单缓存超过 TTL | false |
| TOO_LARGE | 413 | 选中图片 >50 张，或源对象/生成的 zip >200MB | false |
| ZIP_NOT_READY | 503 | 无可用存储（COS 缺 bucket/凭证，或 local 目录不可读写） | true |
| ZIP_FAILED | 502 | 读回源对象、写 zip 或上传 zip 失败 | true |
| TIMEOUT | 504 | 单请求超过 `ZIP_TIMEOUT_S` | true |

任何失败路径都不得返回 `cloud://` 值，也不得返回 fileID 字段。

## 打包与存储规则

| 项 | 规则 |
|----|------|
| 选图 | `manifest.items` 中 `type=image`，且 `stage_cache` 有 `platform:content_id:index` 对象记录，且 `store.exists(fileID)` 为真；显式 `indexes` 只做过滤，不扩大范围 |
| 只读 | 打包读回的是 l3 已转存对象；不重新请求源站，不调用 `/stage`，不改写 l3 缓存 |
| 顺序 | 按 index 数值升序 |
| 条目名 | `{index:03d}.{ext}`，`ext` 取 l3 缓存里的转存扩展名并小写（如 `001.jpg`、`007.png`）；不加目录、不加前缀 |
| 时间戳 | 每条固定 `1980-01-01 00:00:00`，与真实打包时间无关 |
| 压缩 | `ZIP_STORED`（图片已压缩），不加密、不分卷 |
| zip 对象键 | `l6/<task_id>/<index_set_hash>.zip`，`index_set_hash = sha256(",".join(升序 index)).hexdigest()[:16]` |
| fileID | local：`cloud://local/<key>`；cos：`cloud://<bucket>/<key>` |
| 缓存键 | `zip:v1:<task_id>:<升序 index 逗号串>` |
| 缓存 TTL | `ZIP_CACHE_TTL_S` 默认 600s，与 l3 清单 TTL 对齐；`0` 表示禁用缓存（每次都重打，用于稳定性验证） |
| 缓存命中校验 | 命中后仍需 `store.exists(fileID)`；对象丢失则删缓存重打并覆盖同一键 |
| 并发 | 同进程内同一缓存键用单锁串行，避免并发重复打包与重复上传 |

## 限额与配置

| 名称 | 默认值 | 含义 |
|------|--------|------|
| `ZIP_MAX_IMAGES` | 50 | 单次 zip 图片数上限 |
| `ZIP_MAX_BYTES` | 209715200 | 源对象累计与生成 zip 的字节上限（200MB） |
| `ZIP_TIMEOUT_S` | 60 | 单请求总预算 |
| `ZIP_CACHE_TTL_S` | 600 | zip 幂等缓存 TTL，0 为禁用 |
| `ZIP_TMP_PREFIX` | `renlink-zip-` | `/tmp` 临时文件前缀 |
| `STAGE_STORE` | `local` | 复用 l3 的存储选择（local/cos） |
| `STAGE_LOCAL_DIR` | `/tmp/renlink-stage-store` | local 模式读写根目录 |
| `COS_BUCKET` / `COS_REGION` | 空 | cos 模式桶与地域 |
| `ZIP_FAKE_DELAY_MS` | 0 | 仅测试：打包前注入延迟，用于超时与幂等计数 |
| `ZIP_FAULT_INJECT` | 空 | 仅测试：`read`（源对象读回）、`write`（本地 zip 落盘）、`upload`（对象存储写入）注入失败，仅在 `STAGE_STORE=local` 生效 |

## 本地验收方式

```bash
# 1. 起服务（local 存储，与 /parse 同进程，task 清单才在内存里）
cd /Users/apple/Developer/Personal/renlink/container
STAGE_STORE=local STAGE_LOCAL_DIR=/tmp/renlink-stage-store \
  PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099

# 2. 真实 /parse 拿清单，并按 index 逐个转存
curl -sS -X POST localhost:18099/parse -H 'content-type: application/json' \
  -d '{"url":"'$XHS_NOTE_1'"}' > /tmp/parse.json
python3 ops/stage_smoke.py --parse-json /tmp/parse.json --index 0 --out /tmp

# 3. 算 task_id 并打包
TASK_ID=$(cd container && python3 -c \
  'import json,sys; from app.stage_cache import task_id_for; print(task_id_for(json.load(open("/tmp/parse.json"))))')
curl -sS -X POST localhost:18099/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID'"}' | tee /tmp/zip.json

# 4. 用 fileID 读回并核对字节与条目数
python3 ops/zip_smoke.py --verify /tmp/zip.json
```

## 依赖与接缝

| 依赖 | 方向 | 接缝定义 | 本湖责任 |
|------|------|----------|----------|
| l3-media-delivery | l6 消费 l3 | `stage_cache` 的 `platform:content_id:index` 对象记录（fileID/kind/ext/bytes）与对象存储里的既有对象；l6 只读不写 l3 缓存 | 选图、读回、打包、上传 |
| l3 存储适配 | l6 复用 | `STAGE_STORE`、`STAGE_LOCAL_DIR`、COS 桶与凭证；需补读回能力（local 直接读文件，cos 签名 GET） | 读回与上传，不新增第二套存储配置 |
| l1-parser-core | 间接 | task_id 算法与 `items[].index/type`；`/parse` 字段与 schema 不变 | 只消费，不改 |
| l5-miniprogram-pages | l5 消费 l6 | 本湖冻结 `{task_id,indexes?}` → `{ok,fileID,bytes,count}`；l5 Q7 现假定 `{cloudIDs,zipName}` → `{cloudID}` | l5 需走变更把按钮改为传 task_id、读 fileID；l6 不改 l5 冻结正文 |
| 微信分享 | 端侧 | `wx.shareFileMessage`；PC `wx.saveFileToDisk` | 只管给可下载 fileID 与稳定错误码 |
