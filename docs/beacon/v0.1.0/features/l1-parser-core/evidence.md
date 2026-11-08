# Evidence Index: l1-parser-core

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | draft | truth |
| tests | test_truth | tests.md | draft | qa |
| tasks | support_advisory | tasks.md | draft | implement |
| contract | support_advisory | truth.md 的接口契约章节 | draft | implement |

## 按 AC 的证据槽位

证据文件在实现阶段由 smoke 执行器产出，统一落在 evidence 目录，命名与用例 ID 对齐。当前阶段还没有任何执行证据，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | smoke-TC-001.json、smoke-TC-002.json | 真机分享链接单发 | 未产生 |
| AC-002 | smoke-TC-003.json、smoke-TC-004.json | 图文样本按页面张数核对 | 未产生 |
| AC-003 | smoke-TC-005.json、smoke-TC-006.json | 视频笔记样本单发 | 未产生 |
| AC-004 | smoke-TC-007.json、smoke-TC-008.json | 两个平台的短链样本 | 未产生 |
| AC-005 | smoke-TC-009.json | 过期 cookie 注入 | 未产生 |
| AC-006 | smoke-TC-010.json | 失效短链构造请求 | 未产生 |
| AC-007 | smoke-TC-011.json | 三组非法输入 | 未产生 |
| AC-008 | smoke-TC-012.json | 三个非目标平台链接 | 未产生 |
| AC-009 | smoke-TC-013.json | 延迟注入 13s | 未产生 |
| AC-010 | smoke-TC-014.json | 图片最多样本与 120 项构造 | 未产生 |
| AC-011 | smoke-TC-015.json | 四类响应 schema 校验 | 未产生 |
| AC-012 | smoke-TC-016.json | 容器 /tmp 快照对比 | 未产生 |
| AC-013 | smoke-TC-017.json | 带 cookie 字段请求 | 未产生 |
| AC-014 | smoke-TC-018.json | 健康探针 | 未产生 |

## 约束证据槽位

| 约束 | 证据 | 状态 |
|------|------|------|
| callContainer 15s 与一文件一请求 | smoke-TC-013 的耗时字段 | 未产生 |
| 返回包 1000KB 与只回 cloudID | smoke-TC-014 的字节数与键集合 | 未产生 |
| 容器无持久盘，文件进 COS | smoke-TC-016 的 /tmp 前后对比 | 未产生 |
| zip 用 shareFileMessage | l6 契约，本湖只引用 | 转交 l6 |
| 小红书 webp 转 jpg | smoke-TC-015 的 needs_transcode 断言 | 未产生 |
| cookie 只做运营方池 | smoke-TC-017 与 smoke-TC-009 | 未产生 |
| f2 当库用不下载 | smoke-TC-016 的出网请求记录 | 未产生 |
| 小红书图文自研 | l2 接缝，本湖只验路由 | 转交 l2 |

## 样本采集进度

八个样本槽位的实际链接、采集日期、页面条目数与截图由运营侧登记，登记完成前覆盖矩阵里对应的 e2e 用例保持 BLOCKED。本文件不记录样本链接原文。

## Boundary

本文件是索引与槽位，不放最终判定、不放发布结论。通过与否由运营方跑 smoke 后回填的状态与验收员的独立核对决定。

## 实现回执（lake: implement，TASK-001 ~ TASK-015）

- 时间：2026-11-08 19:40 Asia/Shanghai
- host run：`run_1084fcb4301353f56601ec48`，stage=`plan`，status=`blocked (loop_stage governance_precheck)`，reason=`stage_executor_not_registered`。host run 保持原状，本轮是 lake 级 implement，未重建 run。
- 实现依据：truth.md（frozen, R1）、tasks.md、tests.md
- 契约参考： docs/PLAN.md
- 以上四份正文未修改。
- 交付物： container/app/main.py container/app/routes_parse.py container/app/contract.py container/app/errors.py container/app/parsers/shortlink.py container/app/parsers/douyin.py container/app/parsers/xhs.py container/app/session_bridge.py container/requirements.txt contract/parse_response.schema.json ops/smoke.py Dockerfile

### 验证结果

- `docker build -t renlink-l1:local .`：退出码 0；镜像 `sha256:8c0da220d69769635f60ed30de9bb8585882913516ee0edd4ea93b874ae77890`；构建日志 docs/beacon/v0.1.0/features/l1-parser-core/evidence/build-docker.log 。镜像内 Node `v20.20.2`、`python -c "import f2"` 输出 `f2 import ok 0.0.1.7`。
- 容器运行：`renlink-l1-test` 启动成功，`GET /health` 返回 200；`curl -X POST localhost:18080/parse -d '{"url":"https://example.com"}'` 返回 HTTP 400、`error.code=UNSUPPORTED_PLATFORM` 信封。
- `python ops/smoke.py` （无真实样本、容器地址）：18 个用例，`pass=5 fail=0 blocked=13`，退出码 3；原始输出见 docs/beacon/v0.1.0/features/l1-parser-core/evidence/smoke-run.log ，逐用例结果见 docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/smoke-TC-001.json ~ smoke-TC-018.json。
- `python -m compileall container ops`：退出码 0。
- `uv pip install -r container/requirements.txt` （Python 3.11.14 venv）：退出码 0；f2 0.0.1.7 可 import。
- 截断与体积：120 项输入截为 100 项且 `truncated=true`；恰好 100 项不置 truncated；100 条超长 URL 序列化后收缩到 84 项、1020074 字节，仍 ≤1024000。
- 超时：注入 13000ms 延迟后请求返回 HTTP 504、`TIMEOUT`、`elapsed_ms=12001`、墙钟 12.011865s（<15s）。
- 限流：默认 20 次/分钟，同一 IP 第 21 次请求返回 HTTP 429、`RATE_LIMITED`。
- cookie 失效：注入过期标记后返回 HTTP 503、`COOKIE_EXPIRED`、`items=[]`，日志与响应不含 cookie 值。
- 零落盘：容器内 `/tmp` 文件数请求前 0、请求后 0；解析请求后 `/app/logs` 不存在（f2 导入前挂 NullHandler，避免 f2 写 `./logs`）。
- 小红书图文接缝：注入测试替身后返回 `content_type=note`，`needs_transcode=true`，webp 原地址与 `xsec_token` 原样保留。

### 逐 TASK 状态

| TASK | 状态 | 说明 |
|------|------|------|
| TASK-001 | done | FastAPI `/parse`、`/health` 与 pydantic 契约模型落盘，字段对齐 truth 接口契约 |
| TASK-002 | done | 八个错误码、HTTP 状态与 retryable 统一在 `errors.py`，错误信封含 ok/error/items/resolved_url/elapsed_ms |
| TASK-003 | done | 白名单、2048 长度、cookie 字段拒绝；`example.com` 返回 UNSUPPORTED_PLATFORM |
| TASK-004 | done | 短链 3 跳上限、HEAD 优先、GET 只读响应头；失效短链返回 422 SHORTLINK_FAIL、resolved_url="" |
| TASK-005 | done | f2 当库调用 `DouyinHandler.fetch_one_video`（异步），kwargs 按 0.0.1.7 要求补 cookie/headers；未触发下载 |
| TASK-006 | done | 图文 images 归一为 index/type/remoteUrl/ext/cover/width/height；用构造 detail 验证 3 图提取 |
| TASK-007 | done | 小红书视频走 yt-dlp `XiaoHongShuIE`，items 固定 1 项、ext=mp4 |
| TASK-008 | done（stub 接缝） | xhs 图文委托 `parse_note`；默认 stub 返回 PARSE_FAILED，可用 `configure_note_parser` 或 `PARSE_L2_NOTE_STUB` 替换 |
| TASK-009 | done（stub 接缝） | `get_cookie` / `CookieExpired` 在 `session_bridge.py`，缺失或过期均映射 503；日志不打印 cookie |
| TASK-010 | done | 路由层 12s 硬超时；`PARSE_UPSTREAM_DELAY_MS` 注入已验证 504 |
| TASK-011 | done | items 上限 100、`truncated=true`、序列化后 ≤1024000 字节自检 |
| TASK-012 | done | 解析链路无临时文件 API；容器 `/tmp` 前后均为 0 |
| TASK-013 | done | `/health` 返回两平台 cookie_status、last_refresh、egress_proxy |
| TASK-014 | done | 镜像 Python 3.11 + FastAPI + yt-dlp + f2 0.0.1.7 + Node20 + pyexecjs；镜像内 f2 import 通过 |
| TASK-015 | done | `ops/smoke.py` 定义 18 个用例，缺样本逐条 BLOCKED，退出码 3 |
| TASK-016 | BLOCKED | 缺 8 个真实样本（DY_VIDEO_1/2、DY_NOTE_1/2、XHS_VIDEO_1/2、DY_SHORT_1、XHS_SHORT_1），未采集、未编造 |
| TASK-017 | BLOCKED | 依赖 TASK-016 的真实样本，打包验收未执行 |

### stub 替换说明

- l2-xhs-images：`xhs.parse_note` 契约已留出，当前用 `configure_note_parser` / `PARSE_L2_NOTE_STUB` 测试替身；**等 l2 冻结后替换 stub**，l1 不实现 `__INITIAL_STATE__`。
- l4-session-egress：`get_cookie(platform)` 从环境变量读取运营方 cookie，`CookieExpired` 映射 503；**等 l4 冻结后替换 stub**。
- 真实抖音/小红书样本未到位，涉及上游网络的 TC-001~TC-009、TC-013~TC-016 全部 BLOCKED，不能据此宣称真实链接解析通过。

### 边界

未 commit、未 push、未改价格/密钥/生产配置；未执行 QA 判定，QA 由验收员独立完成。

## 验收回执（独立 QA：lake 级 implement 后复验）

- 时间：2026-11-08 19:56 Asia/Shanghai
- host run：`run_1084fcb4301353f56601ec48`，stage=`plan`，status=`blocked (loop_stage governance_precheck)`，reason=`stage_executor_not_registered`。未重建 run，本次是 lake 级 implement 后的独立 QA。
- 结论：**FAIL / gate = blocked**。实现骨架、错误码、白名单、超时、体积上限、容器依赖均独立复跑通过；但抖音图文条目归一存在可复现的契约缺陷（D1），必须修复后才能进 TASK-017。
- 写权限：只在 evidence/qa 目录写验收证据并在本文件追加本节；未改 container、contract、ops、Dockerfile、truth.md、tests.md；未 commit、未 push。

### 独立复跑（非引用实现方证据）

| 检查 | 命令 | 结果 |
|------|------|------|
| 干净构建 | `docker build --no-cache -t renlink-l1:qa-verify .` | 退出码 0，镜像 `52eb2dffd549`，无 ERROR 行 |
| 容器依赖 | `docker exec … node --version` / `python -c "import f2"` | `v20.20.2` / `f2 0.0.1.7` |
| 编译 | `.venv/bin/python -m compileall -q container ops` | 退出码 0 |
| smoke | `PARSE_BASE=http://localhost:18081 python ops/smoke.py` | `pass=5 fail=0 blocked=13`，退出码 3 |
| 错误码矩阵 | 8 个码逐一实打 | 全部 HTTP/retryable 与 truth 一致 |
| 白名单 | `evil-douyin.com`、`douyin.com.evil.com` 等 | 全部 400 UNSUPPORTED_PLATFORM |
| 超时 | `PARSE_UPSTREAM_DELAY_MS=13000` | 504 TIMEOUT，墙钟 12.03s |
| 限流 | 默认 20/min 连打 22 次 | 第 21 次起 429 RATE_LIMITED |
| 零落盘 | 真实 f2 解析尝试前后对比 | `/tmp` 0→0，`/app/logs` 不存在 |
| 成功契约 | l2 stub 注入 120 图 | 200、100 项、`truncated=true`、webp 原址、schema 通过 |

### 必改项

| ID | 严重度 | 位置 | 问题 | 复现 |
|----|--------|------|------|------|
| D1 | 高（FAIL TASK-006） | container/app/parsers/douyin.py 第 139 行、第 218–247 行 | 抖音图文按 `images[*].url_list` 的全部镜像展开，每张图产出 3 条 item；f2 0.0.1.7 的 `PostDetailFilter.images` 只取 `url_list[0]` | 3 张图 × 3 镜像 → 9 项（ docs/beacon/v0.1.0/features/l1-parser-core/evidence/qa/qa_unit_checks.py ） |
| D2 | 低 | container/app/routes_parse.py 第 70–71 行 | `url` 非字符串返回 INVALID_URL；truth 把「字段类型错误」归 INVALID_REQUEST | `POST {"url":123}` → INVALID_URL |

D1 影响：AC-002 的 `item_count` 会等于页面张数的 3 倍，l3 会把同一张图下载 3 次；即使真实样本未到也能确定性复现，不能留到 TASK-017。

### 非阻塞偏差与风险

- D3 `session_bridge.py:47-53`：cookie 缺失时 `/health` 返回 `missing`，truth 示例只有 fresh/expired；建议改 expired 或补 truth。
- D4 `douyin.py:50`、`:134`：解析跑在 `asyncio.to_thread` + 内部 `asyncio.run`，12s 超时只取消外层协程，工作线程会继续跑；TC-013 字面通过，生产上有线程泄漏风险。
- D5 `main.py:20`：f2 日志经 root logger 传播，容器 stdout 出现含 msToken/a_bogus 的上游 URL；cookie 值未出现（grep 为 0），C6 字面通过。
- TC-014 需要第 9 个变量 `XHS_NOTE_MAX`，不在 8 个样本槽位内；「缺 8 个样本」不足以解除它的 BLOCKED。
- TC-016 的出网日志与 COS 桶两条判据 smoke 未自动校验；代码无下载路径，风险低。

### 逐 TASK 独立判定

| TASK | 判定 | 依据 |
|------|------|------|
| 001 | PASS | 契约字段与 schema 实测通过 |
| 002 | PASS | 八码表逐个实打一致 |
| 003 | PASS | 白名单/2048/cookie 字段均实测；D2 轻微偏差 |
| 004 | PASS | 3 跳、HEAD 优先、GET 回退、422 均实测 |
| 005 | IMPLEMENTED / 真实网络 BLOCKED | f2 403 → 502 PARSE_FAILED 实测；无真实样本；D4 风险 |
| 006 | **FAIL** | D1 确定性复现 |
| 007 | IMPLEMENTED / 真实网络 BLOCKED | 无 XHS_VIDEO 样本 |
| 008 | PASS | stub 接缝可注入，webp 原址 + needs_transcode=true 实测 |
| 009 | PASS | 无 cookie → 503 COOKIE_EXPIRED 实测，日志无 cookie 值 |
| 010 | PASS | 12s 超时 504 实测，墙钟 <15s |
| 011 | PASS | 120→100、truncated、1024000 字节自检实测 |
| 012 | PASS | `/tmp` 0→0、无 `/app/logs`、无下载代码路径 |
| 013 | PASS | `/health` 两平台字段、version、egress_proxy 实测；D3 备注 |
| 014 | PASS | 干净构建 + Node20 + f2 0.0.1.7 + pyexecjs 自检通过 |
| 015 | PASS | 18 用例，`pass=5 fail=0 blocked=13`，退出码 3 |
| 016 | BLOCKED | 缺 8 个真实样本（DY_VIDEO_1/2、DY_NOTE_1/2、XHS_VIDEO_1/2、DY_SHORT_1、XHS_SHORT_1） |
| 017 | BLOCKED | 依赖 TASK-016；且需先修 D1、补 XHS_NOTE_MAX |

### 证据

证据目录 docs/beacon/v0.1.0/features/l1-parser-core/evidence/qa ：build-docker-qa.log、compile.log、smoke-run-qa.log、http-matrix.json、unit-checks.log、shortlink-checks.log、qa-findings.json、qa_unit_checks.py、qa_shortlink_checks.py。

### 边界

真实抖音/小红书链接解析未验证，stub/构造用例范围通过不等于 TASK-017 通过。修复 D1/D2 后由验收员复验 TASK-006 并重跑 smoke；release 与发布动作由人类确认。

---

# 返工回执（D1 + D2，lake implement-fix）

日期：2026-11-08。范围：TASK-006 图文归一、TASK-003 字段类型错误对齐、f2 日志签名参数脱敏、TC-014 样本变量说明。未改 `truth.md` / `tasks.md` / `tests.md` 正文，未 commit / push，未自证 QA。

## host run 状态

```text
run:    run_1084fcb4301353f56601ec48
status: blocked (loop_stage governance_precheck)
stage:  plan
blocked: true
reason: stage_executor_not_registered
next:   beacon-plan
```

host run 仍是诚实 blocked 状态；本轮是 lake 级 implement-fix，未重建 run。

## D1 修复（TASK-006）

文件： container/app/parsers/douyin.py 。

- 新增 `_primary_image_urls()`：每个图片元素只取 `url_list` 中第一条 http(s)，跨图去重；语义与 f2 0.0.1.7 `PostDetailFilter.images = $.aweme_detail.images[*].url_list[0]` 一致。
- 图文分支抽成 `_note_payload(data)`，`_f2_result()` 调用它；可脱离网络做确定性单测。
- 修复前 `_image_urls` 递归收下 3 个 CDN 镜像，3 张图 → 9 条；修复后 3 张图 → 3 条。

```text
OLD _image_urls (pre-fix behavior) = 9
NEW _primary_image_urls = 3
```

`ops/checks_note_normalize.py` 实际输出：

```text
case=3x3-mirrors
item_count=3 truncated=False
remoteUrls=["https://cdn-a.example.com/img0.webp", "https://cdn-a.example.com/img1.webp", "https://cdn-a.example.com/img2.webp"]
case=120-images
item_count=100 truncated=True
RESULT=PASS
checks_exit=0
```

## D2 修复（TASK-003）

文件： container/app/routes_parse.py 。url 缺失 → `INVALID_URL`；`url` 存在但非字符串（null / 数字 / 数组 / 对象）→ `INVALID_REQUEST`；空串、纯空白、非 http(s)、超 2048 → `INVALID_URL`。

容器 18082 实际响应：

```text
BODY {"url":123}
{"ok":false,"error":{"code":"INVALID_REQUEST","message":"url 字段必须是字符串","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
BODY {"url":null}
{"ok":false,"error":{"code":"INVALID_REQUEST","message":"url 字段必须是字符串","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
BODY {"url":[]}
{"ok":false,"error":{"code":"INVALID_REQUEST","message":"url 字段必须是字符串","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
BODY {}
{"ok":false,"error":{"code":"INVALID_URL","message":"url 为空、不是 http(s) 链接或长度超过 2048","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
BODY {"url":""}
{"ok":false,"error":{"code":"INVALID_URL","message":"url 为空、不是 http(s) 链接或长度超过 2048","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
BODY {"url":"https://example.com"}
{"ok":false,"error":{"code":"UNSUPPORTED_PLATFORM","message":"只支持抖音与小红书链接","retryable":false},"items":[],"resolved_url":"","elapsed_ms":0}
http=400
```

## f2 日志脱敏

`container/app/main.py` 安装 LogRecord 工厂，对 `msToken` / `a_bogus` / `X-Bogus` / `X-Amz-Signature` / `verifyFp` / `fp` / `signtime` / `signature` 的查询值统一替换为 `[REDACTED]`；cookie 值仍不出现。f2 子 logger 实测：

```text
2026-11-08 11:45:37,328 INFO f2.apps.douyin.handler https://www.douyin.com/aweme/v1/web/aweme/detail/?msToken=[REDACTED]&a_bogus=[REDACTED]&X-Bogus=[REDACTED]&device_platform=webapp
redaction_exit=0
```

## 编译 / 构建 / 超时 / smoke

```text
compile_exit=0
docker_build_exit=0
```

```text
{"ok":false,"error":{"code":"TIMEOUT","message":"上游解析超过 12 秒","retryable":true},"items":[],"resolved_url":"","elapsed_ms":11999}
http=504
real 12.02
```

```text
PARSE_BASE=http://localhost:18082
TC-001 dy-video-1: BLOCKED (缺少样本: DY_VIDEO_1)
TC-002 dy-video-2: BLOCKED (缺少样本: DY_VIDEO_2)
TC-003 dy-note-1: BLOCKED (缺少样本: DY_NOTE_1)
TC-004 dy-note-2: BLOCKED (缺少样本: DY_NOTE_2)
TC-005 xhs-video-1: BLOCKED (缺少样本: XHS_VIDEO_1)
TC-006 xhs-video-2: BLOCKED (缺少样本: XHS_VIDEO_2)
TC-007 dy-short-1: BLOCKED (缺少样本: DY_SHORT_1)
TC-008 xhs-short-1: BLOCKED (缺少样本: XHS_SHORT_1)
TC-009 cookie-expired: BLOCKED (缺少样本: DY_VIDEO_1)
TC-010 shortlink-fail: PASS (构造的失效短链，不冒充真实样本)
TC-011 invalid-url: PASS (三组输入：空串、not-a-url、超长 URL)
TC-012 unsupported-platform: PASS (三个非目标平台)
TC-013 timeout: BLOCKED (缺少样本: DY_VIDEO_1)
TC-014 size-cap: BLOCKED (缺少样本: XHS_NOTE_MAX)
TC-015 field-contract: BLOCKED (缺少样本: DY_VIDEO_1, DY_NOTE_1, XHS_VIDEO_1, DY_SHORT_1)
TC-016 no-download: BLOCKED (缺少样本: DY_VIDEO_1)
TC-017 user-cookie: PASS (请求体含 cookie 字段，不应进入解析分支)
TC-018 health: PASS
SUMMARY pass=5 fail=0 blocked=13
smoke_exit=3
```

## 样本变量清单

8 个真实样本：`DY_VIDEO_1`、`DY_VIDEO_2`、`DY_NOTE_1`、`DY_NOTE_2`、`XHS_VIDEO_1`、`XHS_VIDEO_2`、`DY_SHORT_1`、`XHS_SHORT_1`。

另有第 9 个变量 `XHS_NOTE_MAX`，仅 TC-014 使用（超过 100 张图的小红书图文），不是真实链接样本；只备 8 个变量时 TC-014 仍 BLOCKED。

## 逐 TASK 状态（返工后）

| TASK | 状态 | 说明 |
|---|---|---|
| 001–005 | done | 未改动；005 真实网络仍待样本 |
| 006 | done | 3×3 → 3 条、120 → 100 且 truncated=true，确定性用例通过 |
| 007–015 | done | 未改动；008/009 为 l2/l4 stub 接缝；015 smoke 退出码 3 |
| 016 | BLOCKED | 缺 8 个真实样本，未采集、未编造 |
| 017 | BLOCKED | 依赖 TASK-016，真实网络解析未验证 |

## 已知非阻塞偏差（保持现状）

- `/health` 无 cookie 时返回 `missing`（truth 示例只有 fresh/expired）。
- `parse_note` / `get_cookie` 仍是明确接缝与测试替身，等 l2/l4 冻结后替换。
- 失败信封保留 `resolved_url:""`（AC-006 要求短链失败时为空字符串）。
- `asyncio.to_thread` 超时只取消外层协程，f2 线程可能继续跑到结束。

## 证据

证据目录 docs/beacon/v0.1.0/features/l1-parser-core/evidence/fix ：compile.log、docker-build.log、checks-note-normalize.log、d1-before-after.log、d2-responses.log、timeout.log、log-redaction.log、smoke-run.log。

真实抖音/小红书网络解析仍未验证；QA 由验收员独立复验。

---

## 复验回执（independent QA re-verification, 2026-11-08）

**结论：PASS（implement gate green）**，TASK-001~015 的实现验收通过；TASK-016/017 仍 BLOCKED（缺 8 个真实样本），真实抖音/小红书网络解析未验证，未给 PASS。全程只读实现代码；除本文件和 evidence/qa 目录外未改任何文件，未 commit、未 push。

**current_stage（原文）**

```text
run:    run_1084fcb4301353f56601ec48
status: blocked (loop_stage governance_precheck)
stage:  plan
blocked: true
reason: stage_executor_not_registered
next:   beacon-plan
```

host run 仍为 `plan/blocked`；本次是 lake 级 implement-fix 后的独立复验，未重建 run。

### 独立复跑（不引用实现方日志）

| 检查 | 命令 | 实测 |
|---|---|---|
| 干净构建 | `docker build --no-cache -t renlink-l1:qa-reverify .` | 完成，无 ERROR，镜像 `9b378b056835` |
| 编译 | `.venv/bin/python -m compileall -q container ops` | `compile_exit=0` |
| 容器依赖 | 镜像内 `python -V` / `node --version` / `import f2` / `pip show pyexecjs` | `3.11.18` / `v20.20.2` / `0.0.1.7` / `PyExecJS 1.5.1` |
| smoke | `PARSE_BASE=http://localhost:18083 python ops/smoke.py --out .../evidence/qa/l1` | `pass=5 fail=0 blocked=13`，`smoke_exit=3` |
| 超时 | 容器 `PARSE_UPSTREAM_DELAY_MS=13000` | `504 TIMEOUT`，墙钟 `12.006252s` |
| 限流 | 默认 20/min 连打 22 次 | 第 21 次起 `429 RATE_LIMITED`，retryable=true |
| 零落盘 | 真实 f2 解析尝试前后 `find /tmp -type f` + `/app/logs` | `/tmp` 0→0，`/app/logs` 不存在 |
| 日志脱敏 | 容器 stdout 扫描 | `msToken=[REDACTED]`、`a_bogus=[REDACTED]`，无 cookie 值 |
| 短链失败 | `{"url":"https://v.douyin.com/0000000/"}` | `422 SHORTLINK_FAIL`，`resolved_url=""` |

### D1/D2 复验

- **D1（TASK-006）已修复**：走真实 `POST /parse`（同一 ASGI 应用，上游用注入替身）验证——3 张图 × 每张 3 个 CDN 镜像 → 恰好 3 条、`item_count=3`、每项 `remoteUrl` 为各图 `url_list[0]`、全为 `type=image`、index 0..2；120 图 → 100 条且 `truncated=true`。镜像内确认 f2 0.0.1.7 `filter.images` 本身按 `url_list[0]` 取图。
- **D2（TASK-003）已修复**：容器内实打 `{"url":123|null|[]|{}}` → `400 INVALID_REQUEST`；`{}`、`{"url":""}`、`{"url":"   "}`、`not-a-url`、`ftp://`、超 2048 → `400 INVALID_URL`；请求体为数组/非法 JSON → `INVALID_REQUEST`。
- **顺带项**：日志掩码已生效（见上表）； ops/smoke.py 与样本清单已写明第 9 个变量 `XHS_NOTE_MAX` 仅 TC-014 使用。

### 契约与边界（独立核对）

- 成功响应九字段齐全、类型正确，`items[].index` 从 0 连续，schema 校验通过；xhs 图片 `needs_transcode=true` 且 `remoteUrl` 保留 webp 原址与查询串。
- 体积上限：12000 字符长 URL × 100 项 → 收缩到 84 项、`1020996` 字节 ≤ 1024000、`truncated=true`、`item_count` 与 items 一致。
- 白名单：`evil-douyin.com`、`douyin.com.evil.com`、`notdouyin.com`、`xiaohongshu.com.cn` 均 `UNSUPPORTED_PLATFORM`；大小写与子域正常放行；请求体带 `cookie` 字段 → `INVALID_REQUEST` 且不回显。
- 八码表 HTTP/retryable 全部实测一致（含 `PARSE_FAILED 502/true`、`COOKIE_EXPIRED 503/true`）。
- l2 `parse_note` 与 l4 `get_cookie` 仍是可注入接缝（`configure_note_parser` / 环境变量替身），未发现 `__INITIAL_STATE__` 越权实现。

### 逐 TASK

| TASK | 判定 |
|---|---|
| 001–004 | PASS（003 的 D2 已修复） |
| 005 | 已实现；真实网络 BLOCKED |
| 006 | **PASS**（D1 已修复并复验） |
| 007 | 已实现；真实网络 BLOCKED |
| 008–015 | PASS（008/009 为可替换 stub 接缝；013 带 `missing` 备注） |
| 016 | BLOCKED，缺 8 个真实样本，未编造 |
| 017 | BLOCKED，依赖 016 |

### 非阻塞偏差 / 未验证

- `/health` 无 cookie 时返回 `missing`（truth 示例只有 fresh/expired）。
- 12s 超时只取消外层协程，`asyncio.to_thread` 内 f2 线程可能继续运行。
- 失败信封保留 `resolved_url:""`（AC-006 要求，接受）。
- `tasks.md` 的 001–015 勾选仍未更新（文档层面）。
- 限流以直连客户端 IP 为键；若部署在 Cloud Run 代理后，所有调用方可能共享同一桶，属生产部署风险，本机无法验证。
- 真实抖音/小红书解析、真实短链展开（TC-007/008）、真实 l2 图文均未验证，只能说明「stub/构造用例范围通过，真实样本 BLOCKED」。

**证据**： docs/beacon/v0.1.0/features/l1-parser-core/evidence/qa/qa-findings-reverify.json 、http-matrix-reverify.json、smoke-reverify.log、reverify-contract.log、reverify-size-cap*.log。

## 真实样本验证（2026-11-08，运营方本机）

| 链接 | 平台 | 解析方式 | 下载结果 |
|---|---|---|---|
| `v.douyin.com/Y7MgY9YnYAg` | 抖音 | headless Chromium 渲染页面 | ✅ 155MB / 1080x1920 / h264+aac / 1407s |
| `xhslink.cn/o/1zbdThHpdb0` | 小红书 | yt-dlp + Chrome cookie | ✅ 20MB / 720x1280 / h264+aac / 52s |

`/parse` 实测：
- 小红书：`ok=true`，`content_type=video`，1 项 mp4，`elapsed_ms≈1061`。
- 抖音：`ok=false`，`PARSE_FAILED`（f2 APIResponseError / HTTP 403）。

关键结论（变更输入）：
1. 小红书链路已跑通：`xhslink.cn` 短链 → `discovery/item`，`xsec_token` 原样保留。
2. 抖音 web detail API 对服务端直连返回 403：f2 0.0.1.7 与 yt-dlp 2026.08.19 均失败；即使带上完整 Chrome 安全 cookie（含 `UIFID`/`UIFID_TEMP`/`odin_tt`/`__ac_signature`）仍 403。headless Chromium 渲染页面后可拿到 `play_addr` 并成功下载。
3. 因此 truth 里「抖音用 f2」的假设不再成立，需要变更：抖音 `/parse` 增加浏览器渲染分支，或等价的 UIFID/签名方案。
4. 短链修正（已改代码）：`v.douyin.com` 对 HEAD 返回 404，只有 GET 会 302；`iesdouyin.com/share/video/<id>` 必须归一化为 `www.douyin.com/video/<id>`。
5. 白名单修正（已改代码）：需包含 `xhslink.cn` 与 `iesdouyin.com`。
6. 容器成本影响：浏览器渲染分支会给镜像 +~100MB、内存 +~300–500MB，云托管规格需上调。

## 抖音 403 根因与免浏览器方案（2026-11-08 追加验证）

- 403 响应体：`Blocked by ArgusSecurityPlugin Uifid Not Found`。
- 根因不是 TLS/JA3/JA4，而是 Argus 网关要求成套的 header + query：
  - header：`x-tt-argus: <任意非空>`、`uifid: <cookie 的 UIFID 或 UIFID_TEMP>`
  - query：`uifid`、`verifyFp=<s_v_web_id>`、`fp=<s_v_web_id>`
  - 再加 f2 的 `a_bogus` 与 `msToken`
- 实测：`curl_cffi(impersonate="chrome")` 连跑 3 次，全部 HTTP 200 且返回 `play_addr`；**不需要浏览器**。
- 参照：MediaCrawler 开源项目里 douyin client 对 Argus 的处理（`x-tt-argus` + `uifid` + `verifyFp/fp`）。
- 结论：抖音 `/parse` 应改为「HTTP + Argus 头 + a_bogus」；抖音任何情况都不走渲染（后续 chg_42c00bf71013 明确禁用 Obscura），容器**不需要**装 Chromium，镜像与内存保持轻量。

## 回退方案选型：Obscura（2026-11-08 实测）

- 版本 `0.2.6`，Apache-2.0，30.5k stars，Rust + V8 + CDP，无 Chromium，官方 Docker 镜像 `h4ckf0r0day/obscura`。
- 本机（macOS arm64 `-stealth` 包）实测：
  - `example.com` ✅；`quotes.toscrape.com/js` ✅（JS 渲染出 10 条）
  - 小红书笔记页 ✅ 正确渲染标题（带 `xsec_token`）
  - 抖音首页 / 视频页 / 分享页 ❌ 返回「验证码中间页」；CDP 下目标页会被关闭
- 结论：Obscura 作为**通用渲染回退**可用（小红书 / 未来平台），但**不能用于抖音**；抖音继续走 Argus HTTP。
- 生产集成：默认不启用；`ENABLE_OBSCURA=1` 时才启动 `obscura serve --port 9222 --stealth`。镜像 +~70MB、内存 ~60MB，不影响主路径。
- 决策（2026-11-08，chg_42c00bf71013）：Obscura 定位为唯一渲染回退，默认关闭；CDP 接入用 `new_context()` 且不 `browser.close()`；抖音分支禁止接 Obscura；容器默认不装浏览器与 Chromium，开启 Obscura 时建议 1C1G。

## 实现回执（lake: implement，抖音浏览器渲染分支 TASK-018 ~ TASK-021｜历史存档，已被 chg_42d5d41158ba 取代）

> 本节的浏览器主路径已被同日的 `chg_42d5d41158ba` 取代：主路径改为 HTTP + Argus 头直连；其中 Playwright 最终回退又被 `chg_42c00bf71013` 取代为 Obscura 通用渲染回退，且抖音禁用。本节保留为那次实现的真实记录，不作为当前需求的验收依据。

时间：2026-11-08 20:15–20:30（Asia/Shanghai）。依据 truth R2 / `chg_a8c858b31f4c`、tests.md TC-019 ~ TC-022。不 commit、不 push；QA 留给独立验收。

### 代码改动

| 文件 | 改动 |
|---|---|
| 历史渲染模块 `douyin_browser.py`（已随本次变更删除，文件不存在） | headless Chromium 打开 `https://www.douyin.com/video/<aweme_id>`，`domcontentloaded` 后在剩余预算内读 `window._ROUTER_DATA` 的 `video.play_addr.url_list[0]`；8s 渲染上限；aweme_id 键进程内缓存 10 分钟；每次请求在 `/tmp/renlink-render-*` 建 profile，`finally` 删除 |
| `container/app/parsers/douyin.py` | 抖音视频分支改为「浏览器渲染 → f2/yt-dlp 回退」；图文仍走 f2；`iesdouyin.com/share/video/<id>` 统一用 aweme_id 生成规范页 |
| `container/app/main.py` | `/health` 增加 `render` 计数（browser_launches / cache_hits / render_failures / render_timeouts / cache_entries），供缓存与「小红书不起浏览器」判定 |
| `container/requirements.txt` | `playwright==1.64.1` |
| `Dockerfile` | `python -m playwright install chromium --with-deps`，构建期自检 Chromium 可启动 |
| `ops/smoke.py` | 新增 TC-019 ~ TC-022 四个用例：`dy-render-1`、`dy-render-cache`、`dy-render-403`、`dy-render-timeout` |

### 抖音真实链接 /parse 实测

冷启动首次请求（浏览器渲染 3015ms，/parse 3329ms）：

```json
{"ok":true,"platform":"douyin","content_type":"video","source_url":"https://v.douyin.com/Y7MgY9YnYAg","resolved_url":"https://www.douyin.com/video/7705367833957403946","title":"走进影视飓风和TIM聊聊人生与理想#人间观察计划 #溥江半日谈 #人生 #影视飓风","item_count":1,"elapsed_ms":3329,"items":[{"index":0,"type":"video","remoteUrl":"https://aweme.snssdk.com/aweme/v1/playwm/?video_id=v0300fg10000db...","ext":"mp4","cover":"https://p9-sign.douyinpic.com/tos-cn-i-dy/b144006...","width":1080,"height":1920,"needs_transcode":false}]}
```

同一 aweme_id 第二次请求（缓存命中，0ms）：

```json
{"ok":true,"platform":"douyin","content_type":"video","resolved_url":"https://www.douyin.com/video/7705367833957403946","item_count":1,"elapsed_ms":0,"items":[{"index":0,"type":"video","remoteUrl":"https://aweme.snssdk.com/aweme/v1/playwm/?video_id=v0300fg10000db...","ext":"mp4"}]}
```

缓存与浏览器计数（同一进程连续请求）：

```text
health 初始            browser_launches=0 cache_hits=0 cache_entries=0
xhs 先请求后          browser_launches=0 cache_hits=0 cache_entries=0   ← 小红书不启动浏览器
douyin 首次后         browser_launches=1 cache_hits=0 cache_entries=1
douyin 二次后         browser_launches=1 cache_hits=1 cache_entries=1
```

`remoteUrl` 可下载性：对 `playwm` 地址发 `curl -L -r 0-1023`，302 到 `v11-*.douyinvod.com`，最终 `206 video/mp4`。

### 小红书回归

`xhslink.cn/o/1zbdThHpdb0`：`ok=true`，`content_type=video`，1 项 mp4，`elapsed_ms=1017`，`resolved_url` 保留 `discovery/item` 与 `xsec_token`；`browser_launches` 保持 0。

### TC-019 ~ TC-022 实测

| TC | 用例 | 结果 | 实测 |
|---|---|---|---|
| TC-019 | `dy-render-1` | PASS | 200 / ok=true / 1 项 / remoteUrl 非空 / elapsed<12000 |
| TC-020 | `dy-render-cache` | PASS | 两次 remoteUrl 相同；二次 0–224ms；browser_launches 不增，cache_hits 2→4 |
| TC-021 | `dy-render-403` | PASS | 502 / PARSE_FAILED / retryable=true / items=[] / 1152ms |
| TC-022 | `dy-render-timeout` | PASS | 504 / TIMEOUT / retryable=true / items=[] / 8305ms |

TC-021 的注入开关是 `RENLINK_FORCE_RENDER_403=1`（跳过浏览器，f2 真实 403 失败）；TC-022 的注入开关是 `RENLINK_RENDER_DELAY_MS=9000`（超过 8s 渲染预算）。8s 内渲染失败但页面已返回（403/风控/无地址）走 f2 回退，回退也失败返回 502；渲染本身超过 8s 返回 504。两者都不返回半截 items。

### 零落盘 / 清理

- 渲染请求结束后 `/tmp/renlink-render-*` 残留数为 0；无残留 Chromium/headless_shell 进程（成功、403 回退、超时三种路径都实测）。
- `/parse` 仍不下载媒体、不写媒体文件；浏览器只写自己的临时 profile，并在同一请求内删除。
- 并发默认 1（`RENLINK_RENDER_CONCURRENCY`），避免 1C1G 下多 Chromium 争内存；排队时间计入 12s 总预算。

### 容器规格（chg_a8c858b31f4c）

| 项 | 数值 |
|---|---|
| 镜像增量 | 约 +100MB（Chromium + 系统依赖） |
| 运行时内存增量 | 约 +300–500MB / 每个渲染请求 |
| 云托管最低规格 | ≥1C1G；建议 1C2G |
| 冷启动 | 明显变慢：首次 Chromium 启动计入首请求耗时；本机冷渲染 3015ms，仍在 8s 渲染预算内 |
| 构建依赖 | `python -m playwright install chromium --with-deps` |

### 证据文件

- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/parse-douyin-first.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/parse-douyin-cached.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/parse-xhs-regression.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/parse-douyin-403.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/parse-douyin-timeout.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/health-before.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/health-after-xhs.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/douyin-render/health-after.json`
- TC-019 ~ TC-022 的浏览器 smoke 用例结果未单独落盘，仅本节内联 JSON 可查；不作为当前 Argus 方案的验收依据。

### 逐 TASK 状态

- TASK-018 完成：抖音渲染分支与规范页归一已实现；小红书不启动浏览器（health 计数实测 0）。
- TASK-019 完成：8s 渲染预算、12s 总预算、10 分钟 aweme_id 缓存、/tmp 清理与失败整请求返回已实测。
- TASK-020 完成：真实链接 JSON、缓存/回退/超时与容器规格已写入本节。
- TASK-021 完成：Dockerfile 已加 Playwright Chromium 安装与构建期自检；构建结果见下方构建记录。

### 边界

- 未 commit、未 push，未改价格/密钥/生产配置。
- 本节是实现方证据，不构成 QA 结论；TC-019 ~ TC-022 的独立复跑由验收员执行。
- 浏览器依赖抖音移动分享页当前结构（`_ROUTER_DATA.loaderData[*].videoInfoRes.item_list[0].video.play_addr`）；结构变化时回退到 `<video>.currentSrc`，再失败则 PARSE_FAILED。

## 实现回执（lake: implement，抖音 Argus 直连 TASK-018 ~ TASK-021）

时间：2026-11-08 20:30–20:50（Asia/Shanghai）。依据 truth `chg_42d5d41158ba`、tests.md TC-019 ~ TC-022。不 commit、不 push；QA 留给独立验收。

### 代码改动

| 文件 | 改动 |
|---|---|
| `container/app/parsers/douyin_argus.py` | 新增。f2 生成 `a_bogus`；按固定参数顺序拼 detail API，补 `x-tt-argus`、`uifid` 头与 `uifid`/`verifyFp`/`fp` 参数；`curl_cffi(impersonate="chrome")` 取 `aweme_detail.video.play_addr.url_list[0]`；aweme_id 键 10 分钟缓存；只回地址不下载 |
| `container/app/parsers/douyin.py` | 视频主路径改为 Argus HTTP；抖音任何情况都不启浏览器（无 Playwright 回退分支）；图文仍走 f2 |
| `container/app/main.py` | `/health` 增加 `argus` 与 `render` 计数（argus_requests / cache_hits / argus_failures / browser_launches） |
| `container/requirements.txt` | 增加 `curl_cffi==0.17.0`；Playwright 不再进默认依赖 |
| `Dockerfile` | 默认不装浏览器；`--build-arg INSTALL_CHROMIUM=1` 才安装 playwright 包 + headless shell；默认镜像自检 f2 与 curl_cffi 可 import |
| `ops/smoke.py` | TC-019 `dy-argus-1`、TC-020 `dy-argus-stability`、TC-021 `dy-argus-missing-header`、TC-022 `dy-argus-timeout` |

### 已验证的 Argus 组合

- header：`x-tt-argus: 1`、`uifid: <cookie 的 UIFID 或 UIFID_TEMP>`、Chrome UA、`Referer: https://www.douyin.com/video/<aweme_id>`。
- query：固定参数顺序到 `uifid`，由 f2 `ABogusManager` 生成 `a_bogus`，再追加 `verifyFp=<s_v_web_id>&fp=<s_v_web_id>&timestamp=<秒>`。
- **不要带 `webid`**：f2 `TokenManager.gen_webid()` 新生成的 webid 会让上游返回空 200；去掉 webid 后连续 3 次均 200 并返回 `play_addr`（本机实测 300–410ms）。
- 去掉 `x-tt-argus` 时上游返回 `403 Blocked by ArgusSecurityPlugin Signature Not Found`，`/parse` 整请求失败。

### 抖音真实链接 /parse 实测

`v.douyin.com/Y7MgY9YnYAg` → `www.douyin.com/video/7705367833957403946`，HTTP 200，612ms，无浏览器：

```json
{"ok":true,"platform":"douyin","content_type":"video","source_url":"https://v.douyin.com/Y7MgY9YnYAg","resolved_url":"https://www.douyin.com/video/7705367833957403946","title":"走进影视飓风和TIM聊聊人生与理想#人间观察计划 #溥江半日谈 #人生 #影视飓风","item_count":1,"elapsed_ms":612,"items":[{"index":0,"type":"video","remoteUrl":"https://v26-web.douyinvod.com/c45eb739...","ext":"mp4","cover":"https://p3-pc-sign.douyinpic.com/...","width":1080,"height":1920,"needs_transcode":false}]}
```

同一 aweme_id 第二次请求命中缓存：`elapsed_ms=1`，`remoteUrl` 相同；`/health` 为 `argus_requests=1 cache_hits=1 browser_launches=0`。

`remoteUrl` 可下载性：对返回的 `douyinvod.com` 地址 `curl -L -r 0-1023` 返回 `206 video/mp4`（Detail API 直接给 CDN 地址）。

### 小红书回归

`xhslink.cn/o/1zbdThHpdb0`：`ok=true`，`content_type=video`，1 项 mp4，`elapsed_ms=975`；`resolved_url` 保留 `discovery/item` 与 `xsec_token`；`browser_launches` 保持 0。

### TC-019 ~ TC-022 实测

| TC | 用例 | 结果 | 实测 |
|---|---|---|---|
| TC-019 | `dy-argus-1` | PASS | 200 / ok=true / 1 项 / remoteUrl 非空 / 649ms / browser_launches 不增 |
| TC-020 | `dy-argus-stability` | PASS | 关缓存连跑 3 次均 200（687 / 559 / 616ms），remoteUrl 均非空，cache_hits=0，browser_launches=0 |
| TC-021 | `dy-argus-missing-header` | PASS | 502 / PARSE_FAILED / retryable=true / items=[] / 505ms / 上游 403 `Blocked by ArgusSecurityPlugin Signature Not Found` |
| TC-022 | `dy-argus-timeout` | PASS | `PARSE_UPSTREAM_DELAY_MS=13000` 下 12.0s 返回 504 / TIMEOUT / items=[] / browser_launches=0 |

TC-022 走整体预算路径：服务端以 `PARSE_UPSTREAM_DELAY_MS=13000` 启动，/parse 在 12.0s 到期返回 504，抖音分支全程不启浏览器。3 次稳定性原始日志见 `evidence/douyin-argus/dy-argus-3x.log`，前后计数见 `health-before-3x.json` 与 `health-after-3x.json`。

### 容器规格（chg_42d5d41158ba）

| 项 | 数值 |
|---|---|
| 默认镜像 | 不装 Chromium；仅多一个 curl_cffi 依赖；本机实测 `docker images` 651MB（旧镜像 595MB），inspect 压缩尺寸约 148MB |
| 可选浏览器构建 | `--build-arg INSTALL_CHROMIUM=1` 才装 playwright + headless shell；抖音分支不引用它，仅用于镜像实验；实测 headless shell 约 276MB，系统依赖约 320MB |
| 默认内存 | 与旧镜像相同，0.5C1G 可跑；推荐 1C1G 留并发余量 |
| 回退渲染内存 | 打开回退并实际渲染时约 +300–500MB |
| 冷启动 | 默认路径无浏览器，冷启动不受渲染影响；可选回退镜像首次启动会慢 |

构建验证：`docker build -t renlink-l1:argus .` 成功（最终镜像 created 2026-11-08 20:51:27 +0800）；镜像内 `/app/app/parsers/douyin.py`、`douyin_argus.py` 与工作区 md5 一致。镜像内 `/ms-playwright` 不存在、`import playwright` 按预期失败，`import f2`（0.0.1.7）与 `import curl_cffi`（0.17.0）成功；运行中的容器进程表无 chromium/playwright。容器内真实链接 `/parse`：抖音 200，小红书 200；容器 `/tmp` 只有 `/tmp` 本身，无残留文件。最终构建日志见 `evidence/douyin-argus/build-final.log`，尺寸与 `/tmp` 快照见 `container-image-size.txt`、`container-tmp.txt`。

### 证据文件

- `evidence/douyin-argus/dy-argus-3x.log`、`health-before-3x.json`、`health-after-3x.json`（3 次稳定性，缓存关闭）
- `evidence/douyin-argus/parse-douyin-missing-header.json`、`health-missing-header.json`（缺 x-tt-argus → 上游 403）
- `evidence/douyin-argus/parse-douyin-timeout-12s.json`、`health-timeout.json`（13s 上游延迟 → 12s 504）
- `evidence/douyin-argus/parse-douyin-argus.json`、`parse-douyin-cached.json`、`parse-xhs-regression.json`、`parse-xhs-regression-current.json`
- `evidence/douyin-argus/health-argus-cache.json`、`health-argus-cache-off.json`
- `evidence/douyin-argus/dockerfile-chromium-grep.txt`、`no-chromium-proof.txt`、`browser-process-scan.txt`、`container-image-size.txt`
- `evidence/douyin-argus/impl-smoke/smoke-TC-019.json` ~ `smoke-TC-022.json`（对最终镜像执行；与 QA 共用目录分开存放，避免互相覆盖）
- `evidence/douyin-argus/build-final.log`（最终镜像构建）

### 逐 TASK 状态

- TASK-018 完成：Argus HTTP 直连已实现并实测 200；主路径不启动浏览器（health 计数 0）。
- TASK-019 完成：10 分钟缓存、12s 总预算、缺头 403 整请求失败、超时 504 与 /tmp 清理已实测；抖音无渲染回退。
- TASK-020 完成：真实链接 JSON、连跑 3 次、缺头 403、超时与容器规格已写入本节。
- TASK-021 完成：Dockerfile 默认不装 Chromium，可选 build arg 安装；默认镜像构建与 import 自检见构建记录。

### 边界

- 未 commit、未 push，未改价格/密钥/生产配置。
- 本节是实现方证据，不构成 QA 结论；TC-019 ~ TC-022 的独立复跑由验收员执行。
- 缓存与 `/health` 计数是进程内状态，多 worker 部署时按 worker 各自缓存。
- Argus 参数顺序与 cookie 字段（UIFID/UIFID_TEMP、s_v_web_id）是当前可用组合；上游结构变化时需按 evidence 的 403 文案重新定位。
- 本轮代码与证据已登记到 lake run `run_bde3174e4fdc3edd7710c87b`（registrant 任链接后端，kind evidence）。run 里仍保留一条历史渲染模块的 artifact_ref，它指向已随 chg_42d5d41158ba 删除的文件，属于被替代方案的残留，不代表当前代码。

## 实现回执（lake: implement，Obscura 通用渲染回退 TASK-022）

时间：2026-11-08 20:55–21:10（Asia/Shanghai）。依据 truth `chg_42c00bf71013`、tests.md TC-023 ~ TC-024。不 commit、不 push；QA 留给独立验收。host run `run_1084fcb4301353f56601ec48` 仍为 `current_stage=plan`、`status=blocked`（`stage_executor_not_registered`），本轮没有推进 host run。

### 代码改动

| 文件 | 改动 |
|---|---|
| `container/app/parsers/render.py` | 新增。`ENABLE_OBSCURA!=1` 时只保留模块常量，不 import Playwright、不连 CDP；启用时 `connect_over_cdp(PLAYWRIGHT_CDP)` → `new_context()` → `goto(wait_until="commit")` → 读取 title/HTML；只 `context.close()`，无 `browser.close()`；渲染预算默认 8000ms，上限 8000ms；统计 renders / failures / cdp_connects / last_url_host |
| `container/app/main.py` | `/health` 增加 `render` 统计；新增仅 `ENABLE_OBSCURA=1` 可用的 `GET /render/probe?url=`，只接受 xiaohongshu.com，返回 title、final_url、html_bytes、xsec_token、obscura_alive |
| `container/entrypoint.sh` | 新增。`ENABLE_OBSCURA=1` 时先启动 `obscura serve --port 9222 --host 127.0.0.1 --stealth` 并等待端口就绪，再 `exec` app；默认跳过；可选 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 仅用于本地 fake-ip 环境 |
| `Dockerfile` | 新增 `FROM h4ckf0r0day/obscura:latest AS obscura`，只拷 `/obscura` 二进制；删除 Chromium/Playwright 浏览器安装分支；只安装 Playwright Python CDP 客户端（1.64.1），不下载浏览器 |
| `container/app/parsers/douyin.py` | 仅修正注释：抖音永不使用渲染；模块仍不 import render |
| `ops/smoke.py` | 新增 TC-023 `obscura-xhs-render`、TC-024 `douyin-no-obscura`，用例总数 24；TC-023/024 证据额外记录 render 计数、obscura 进程、日志命中与静态 import 边界 |

### 实测结果

| 用例 | 结果 | 实测 |
|---|---|---|
| 默认镜像/容器 | PASS | 构建 `renlink-l1:obscura` 成功；镜像内 `/ms-playwright` 不存在，chrome/chromium/headless_shell 可执行文件数为 0；默认起容器无 obscura 进程，`/health.render.enabled=false`，`/render/probe` 返回 404 |
| TC-023 `obscura-xhs-render` | PASS | `ENABLE_OBSCURA=1` 下渲染小红书笔记页，title=`长安四驱越野升顶皮卡房车#二手房车 #房车旅行 #房车生活 #房车自驾游 - 小红书`，`has_xsec_token=true`，`html_bytes=578609`，`elapsed_ms=9276`，渲染后 `obscura_alive=true`（端口仍存活，未调用 `browser.close()`） |
| TC-024 `douyin-no-obscura` | PASS | Obscura 开启时抖音 `/parse` 返回 200 / ok=true / content_type=video / 1 项 play_addr；`render.renders` 与 `render.cdp_connects` 前后不变；`/tmp/obscura.log` 中 douyin 命中 0；`douyin.py`、`douyin_argus.py` 均不 import render |
| 抖音 `/parse` | PASS | 真实链接 `https://v.douyin.com/Y7MgY9YnYAg/` 在 Obscura 开启的容器中返回 200，`elapsed_ms=686`，`remoteUrl` 为非空 `douyinvod.com` play_addr |

说明：本机 Docker 的 DNS 返回 Clash fake-ip `198.18.0.0/15`，被 Obscura 的 SSRF 防护拒绝；本地证据容器额外以 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 启动。生产默认不加该参数，仍是严格的 `obscura serve --port 9222 --host 127.0.0.1 --stealth`。

默认模式 import `render` 模块本身时 `playwright` 未进入 `sys.modules`；直接 import `douyin` 也不会加载 `app.parsers.render`（两项均在最终镜像内验证）。

### 容器规格（chg_42c00bf71013）

| 项 | 数值 |
|---|---|
| 默认镜像 | 含 obscura 二进制但不启动；镜像 247,847,968 bytes（约 248MB），obscura 二进制 115MB |
| 默认内存 | 容器 RSS 约 53MiB，0.5C1G 可跑 |
| 开启 Obscura | 两次小红书渲染后 app+obscura RSS 约 194MiB，建议 1C1G |
| 浏览器 | 默认不装 Chromium、不下载 Playwright 浏览器；只装 Playwright Python CDP 客户端 |
| 冷启动 | 默认路径无浏览器进程；开启 Obscura 时 entrypoint 先等 CDP 端口就绪再启动 app |

### 证据文件

- `evidence/l1/obscura-xhs-render.json`（TC-023 响应、title、xsec_token、obscura 进程与日志尾部）
- `evidence/l1/douyin-no-obscura.json`（TC-024 的 /parse、前后 render 计数、obscura 日志命中、静态 import 边界）
- `evidence/l1/parse-douyin-obscura.json`（Obscura 开启时抖音 /parse 实测 JSON）
- `evidence/l1/default-no-obscura.json`（默认容器无 obscura 进程、render 关闭、/render/probe=404）
- `evidence/l1/dockerfile-default-browser-off.txt`、`evidence/l1/container-spec.txt`
- `evidence/l1/smoke-TC-023.json`、`evidence/l1/smoke-TC-024.json`（对最终镜像执行）

### 边界

- 未 commit、未 push，未改 truth/tests/tasks 的需求口径，未跑 release。
- 本节是实现方证据，不构成 QA 结论；TC-023/024 的独立复跑由验收员执行。
- `/render/probe` 只用于 TC-023 的接入验证，仅 `ENABLE_OBSCURA=1` 时可访问，且只接受小红书页面。

## 复跑与收口（TASK-021/022，2026-11-08 21:10–21:16）

依据 frozen truth `chg_42c00bf71013` 的 C9/C10/C12、AC-017 与 tests.md TC-023/TC-024。本轮只做收敛与复跑，不改抖音 Argus 主路径。未 commit、未 push；QA 由验收员独立执行。

### 本轮改动

| 文件 | 改动 |
|---|---|
| `container/app/parsers/render_obscura.py` | 渲染实现落到本轮要求的文件名；仍只被小红书渲染路径调用，抖音模块不 import |
| `container/app/parsers/render.py` | 保留为兼容别名，导出 `render_obscura` 的公开符号 |
| `container/app/parsers/render_obscura.py` | 每次渲染串行执行；渲染前记录 `/tmp/playwright-artifacts-*` 快照，请求结束（成功或失败）删除本次新增目录 |
| `container/app/parsers/render_obscura.py` | 新增 `RenderTimeout`：连接或页面渲染超时、或整体达到 12s 总预算时抛出 |
| `container/app/main.py` | `/render/probe` 把 `RenderTimeout` 映射为 504 `TIMEOUT`、`retryable=true`；其他渲染失败仍是 502 `PARSE_FAILED`、`retryable=true` |
| `docs/.../tasks.md` | 勾选 TASK-021、TASK-022；交付物清单写明 `render_obscura.py` 与 `render.py` 别名；部署段补冷启动变慢 |

### 默认模式（ENABLE_OBSCURA 未设置）

| 检查 | 结果 |
|---|---|
| 镜像构建 | PASS，`docker build -t renlink-l1:obscura .` 退出码 0 |
| 镜像内浏览器 | PASS，`/ms-playwright` 不存在，chrome/chromium/headless_shell 可执行文件数 0 |
| 默认容器进程 | PASS，仅 `uvicorn`，无 obscura/chromium/playwright 进程 |
| `/health.render` | PASS，`enabled=false`、`browser_launches=0`、`renders=0` |
| `/render/probe` | PASS，返回 404（默认关闭） |
| `/tmp` | PASS，默认容器条目 0 |

抖音真实链接 `https://v.douyin.com/Y7MgY9YnYAg/` 在默认模式返回 200，`browser_launches=0`：

```json
{"ok":true,"platform":"douyin","content_type":"video","item_count":1,"elapsed_ms":830,"remoteUrl":"https://v26-web.douyinvod.com/97afc1df...","ext":"mp4"}
```

小红书回归 `xhslink.cn/o/1zbdThHpdb0`：HTTP 200，`ok=true`，`content_type=video`，`item_count=1`，`elapsed_ms=1073`；该路径没有启动浏览器。

### Obscura 开启模式

TC-023 `obscura-xhs-render`：PASS。HTTP 200，客户端 9362ms，渲染 9336ms；标题
`长安四驱越野升顶皮卡房车#二手房车 #房车旅行 #房车生活 #房车自驾游 - 小红书`，`has_xsec_token=true`，`html_bytes=578609`，`obscura_alive=true`（context 关闭后 CDP 端口仍存活，未调用 `browser.close()`）。

TC-024 `douyin-no-obscura`：PASS。Obscura 开启时抖音 `/parse` 返回 200、`ok=true`、1 项 play_addr；`render.renders` 与 `render.cdp_connects` 前后均为 1，`browser_launches=0`；`/tmp/obscura.log` 中 douyin 命中 0；`douyin.py`、`douyin_argus.py` 均不 import render。

渲染预算与超时映射：把 CDP 指向只接受 TCP、不做 WebSocket 握手的本地端口，`RENLINK_RENDER_WAIT_MS=1000` 时 `/render/probe` 在 1.37s 返回 504：

```json
{"ok":false,"error":{"code":"TIMEOUT","message":"Obscura CDP 连接超时","retryable":true}}
```

`/tmp` 清理：TC-023 渲染结束后开启容器 `/tmp` 只剩 `obscura.log`（1 项），没有 `playwright-artifacts-*` 残留；默认容器 `/tmp` 为 0 项。渲染串行化避免并发请求互相删除对方目录。

### 容器规格（chg_42c00bf71013 复核）

| 项 | 数值 |
|---|---|
| 镜像 | `docker image inspect` Size 247,849,002 bytes；`docker images` 显示 1.02GB |
| obscura 二进制 | 120,358,400 bytes（约 115MB） |
| 默认常驻内存 | `docker stats` 49.48MiB；0.5C1G 可跑 |
| 开启 Obscura 常驻内存 | 渲染后 197.7MiB；建议 1C1G |
| 浏览器 | 默认镜像不含 Chromium、不下载 Playwright 浏览器；只装 Playwright Python CDP 客户端 |
| 冷启动 | 默认路径不受影响；`ENABLE_OBSCURA=1` 时 entrypoint 先启动 `obscura serve` 并等 CDP 端口就绪，冷启动变慢 |

本机 Docker DNS 返回 Clash fake-ip，Obscura 的 SSRF 防护会拒绝；本次本地证据容器以 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 启动。生产默认不加该参数，仍是 `obscura serve --port 9222 --host 127.0.0.1 --stealth`。

### 证据文件

- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/smoke-TC-023.json`（本轮对重建镜像执行）
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/smoke-TC-024.json`（本轮对重建镜像执行）
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/parse-douyin-default.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/parse-xhs-default.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/health-default.json`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/render-timeout.json`（504 TIMEOUT 映射）
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/container-spec.txt`
- `docs/beacon/v0.1.0/features/l1-parser-core/evidence/l1/impl-rerun-2112/process-tmp.txt`

### 边界

- 未 commit、未 push，未改价格/密钥/生产配置；未改 truth/tests 判据。
- 本节是实现方复跑证据，不构成 QA 结论；TC-023/TC-024 由验收员独立复跑。
- `/render/probe` 仅用于渲染接入验证，只有 `ENABLE_OBSCURA=1` 可访问且只接受小红书页面；抖音不经过该入口。

## 调用方独立本机验收（2026-11-08 21:49，非后端自证）

本节由调用方在自己的机器上独立跑通后交给后端登记，输出原文照贴；后端没有重跑，未改任何数字。

```text
douyin: ok type=video items=1 195ms
  item 0 video -> 162700599B (1407.533333s)
xhs:    ok type=video items=1 767ms
  item 0 video -> 46681581B (52.133333s)
PASS: 2/2 samples parsed and downloaded
```

- 抖音：Argus HTTP 直连（`x-tt-argus` + `uifid` + `verifyFp`/`fp` + `a_bogus`），全程未启动浏览器。
- 小红书：yt-dlp + cookie。
- cookie 池由 `ops/refresh_cookie.py` 刷新，含 `UIFID_TEMP`、`s_v_web_id`、`web_session`。
- 与验收员容器内的数字（732ms / 121261002B、1284ms / 21220376B）不同，属不同网络、不同时刻的真实输出，两处都按原文保留。

### ops/accept_local.py 登记

| 项 | 内容 |
|---|---|
| 用途 | 两条真实链接走 `POST /parse`，逐项下载 `remoteUrl`；视频项再用 ffprobe 读时长与大小。任一解析或下载失败返回退出码 1 |
| 启动方式 | 用运营方 cookie 池起服务：`PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099`，再跑 `.venv/bin/python ops/accept_local.py`；`PARSE_BASE` 可覆盖服务地址 |
| 下载落盘 | `/tmp/renlink_accept/<platform>-<index>.<ext>` |
| 通过判定 | 末尾打印 `PASS: 2/2 samples parsed and downloaded` 且退出码 0 |
| 归属 | 本机验收由调用方执行；本次登记不作为后端自证 |

## 独立 QA 结论（验收员，只摘录不评判）

- verdict：**BLOCKED**。权威文件 `evidence/qa/l1-qa-final/verdict.md`（run_id `qa-l1-20261108-2143`，mode `beacon-go`，stage `qa`）。
- 干净构建：`docker build --no-cache -t renlink-l1:qa .` 退出码 0，镜像 `sha256:5c2a8624…`，1.02GB。
- 默认配置 `ops/smoke.py`：pass=12 fail=5 blocked=7；其中 TC-009/013/021/022/024 需要注入环境变量，TC-002/003/004/006/014/015/023 缺样本。专项容器逐条复验合并：PASS 17 / FAIL 0 / BLOCKED 7。
- 验收员容器内 `ops/accept_local.py`：douyin 732ms / 121261002B；xhs 1284ms / 21220376B；`PASS: 2/2`；容器内无 ffprobe。
- 缺真实样本的 TC：TC-002、TC-003、TC-004、TC-006、TC-014、TC-015、TC-023。
- P0：
  1. `obscura serve` 缺 `--allow-private-network`；Docker DNS `127.0.0.11` 被 SSRF 守卫判为私网，`/render/probe` 返回 502，TC-023 / AC-017 无法认证。
  2. 7 个 TC 缺真实样本，对应 AC 无法认证。
- P1：`ops/refresh_cookie.py` 用 Python repr 写 env，单引号被 `docker --env-file` 原样保留，容器内 cookie 损坏导致抖音 502；默认 20/min 限流小于 smoke 单轮请求数，尾部用例 429。
- P2：accept_local 在 douyin 失败时不继续跑 xhs；TC-016/024 的“未设置”提示有误导；镜像无 ffprobe，编码与时长未验。

## 容器默认事实（Dockerfile 只读核对，2026-11-08 本轮）

| 检查项 | 实际事实 |
|---|---|
| `INSTALL_CHROMIUM` | **已从 Dockerfile 删除**，当前不存在这个 ARG；浏览器安装分支已整体移除，镜像无条件不下载 Chromium / Playwright 浏览器，构建期以 `test ! -d /ms-playwright` 自检 |
| `ENABLE_OBSCURA` | Dockerfile 无默认值；`container/entrypoint.sh` 用 `${ENABLE_OBSCURA:-0}`，未设置时不启动 obscura、也不设置 `PLAYWRIGHT_CDP` |
| `PLAYWRIGHT_BROWSERS_PATH` | 未设置；镜像内无 `/ms-playwright`、无 `~/.cache/ms-playwright` |
| obscura 二进制 | 从 `h4ckf0r0day/obscura:latest` 多阶段拷入 `/usr/local/bin/obscura`，只有二进制，默认零进程 |
| 历史偏差 | 早前存档段落里的 `--build-arg INSTALL_CHROMIUM=1` 在当前 Dockerfile 已不存在，以本节与验收员镜像实测为准 |

任务书写的是“默认 `ARG INSTALL_CHROMIUM=0`”，当前实现更彻底：该 ARG 与安装分支都被删除，所以“默认不装浏览器”成立，但不是靠参数默认值，而是靠没有安装路径。验收员在 `--no-cache` 镜像里已复核：`INSTALL_CHROMIUM`/`ENABLE_OBSCURA`/`PLAYWRIGHT_BROWSERS_PATH` 全部 unset，无 chromium/chrome/headless_shell，`/ms-playwright` 不存在。

## 本轮逐 TASK 勾选依据（2026-11-08）

| TASK | 代码位置 | 判定 |
|---|---|---|
| 001 | `app/contract.py`、`app/main.py`、`app/errors.py` | 已实现。ErrorEnvelope 用 dict 构建并以 `contract/parse_response.schema.json` 固化，没有同名 pydantic 类 |
| 002 | `app/errors.py` | 8 个错误码、http 状态、retryable 齐全 |
| 003 | `app/routes_parse.py` | 白名单、2048 上限、cookie 字段拒绝齐全（另放行 iesdouyin.com、xhslink.cn） |
| 004 | `app/parsers/shortlink.py` | 3 跳上限、SHORTLINK_FAIL、resolved_url 交接已实现；实际用 GET 流式取 Location，未用 HEAD（实测 v.douyin.com 对 HEAD 返回 404） |
| 005 | `app/parsers/douyin.py` | 视频走 Argus/yt-dlp 取播放地址，图文走 f2 `fetch_one_video`，只取地址不下载 |
| 006 | `app/parsers/douyin.py` | `images[*].url_list[0]` 每图一条，index/type/remoteUrl/ext 归一 |
| 007 | `app/parsers/xhs.py` | yt-dlp 取播放地址与标题，items 固定 1 项 |
| 008 | `app/parsers/xhs.py` | `parse_note` 接缝与归一，图片标 needs_transcode=true；不解析 `__INITIAL_STATE__` |
| 009 | `app/session_bridge.py` | get_cookie / CookieExpired / 脱敏齐全 |
| 010 | `app/routes_parse.py` | 12s `asyncio.wait_for` 映射 TIMEOUT；`PARSE_UPSTREAM_DELAY_MS` 可注入 |
| 011 | `app/contract.py` | 100 项上限、truncated、1024000 字节自检齐全 |
| 012 | `app/` 全量 grep | 解析链路无临时文件写入；只有 `render_obscura.py` 读取 tempdir 做清理快照 |
| 013 | `app/main.py` `/health` | cookie_status、last_refresh、egress_proxy、argus/render 统计齐全 |
| 014 | `Dockerfile`、`container/requirements.txt` | Python 3.11、FastAPI、yt-dlp、f2 0.0.1.7、curl_cffi、Node20、pyexecjs；构建期自检 import；不装浏览器 |
| 015 | `ops/smoke.py` | 24 个用例，写 JSON 证据，缺样本 BLOCKED 且退出码 3 |
| 018 | `app/parsers/douyin_argus.py` | Argus 头/参数直连，curl_cffi chrome 指纹，无浏览器 |
| 019 | `app/parsers/douyin_argus.py`、`app/routes_parse.py` | 12s 预算、失败无半截 items、play_addr 缓存 TTL 600s、`RENLINK_DROP_ARGUS_HEADER=1` 复现 403 |
| 020 | `evidence.md`、`evidence/l1/`、`evidence/qa/l1-qa-final/` | 真实链接实测与容器规格已入证据；TC-019~024 有实测输出 |

## 边界（本轮）

- 本轮只改 `evidence.md` 与 `tasks.md`；未改 `truth.md`、`tests.md` 正文，未 commit / push，未关闭任何 change。
- “调用方独立本机验收”是调用方给的原文登记，“独立 QA 结论”是验收员报告摘录；两者都不是后端自证，后端本轮没有重跑 smoke 或 accept_local。

---

## 独立 QA 复验 r2 登记（验收员，2026-11-08 22:25 +08:00）

- 权威文件：`evidence/qa/l1-qa-final-r2/verdict.md`；索引：`evidence/qa/l1-qa-final-r2-index.md`；哈希清单：`evidence/qa/l1-qa-final-r2/sha256-manifest.txt`（52 个文件）。
- mode `beacon-go` / run_id `qa-l1-20261108-2225` / stage `qa`；current_stage=`plan`（blocked，`stage_executor_not_registered`）。
- 对象：`renlink-l1-final:latest` = `sha256:cf44f898eb17caa77baaa44013deb83bd816de5f2cfeed15b6d161f35b2bfe6a`，created `2026-11-08T13:14:17Z`；truth frozen / R1。
- 分段结论：
  - douyin 主路径 **PASS**（accept_local 762ms / 162,700,599B / 1407.53s）。
  - xhs 主路径 **FAIL**（502 `PARSE_FAILED`；上游会话失效 302→/login），调用方自报 xhs PASS / 2-2 未复现。
  - 默认 smoke 实测 `pass=9 fail=1 blocked=14`（调用方自报 10/0/14，差异为 TC-005）。
  - 服务端模式用例 **PASS**：TC-009、TC-013、TC-022、TC-020、TC-021（各自独立容器）；附加 TC-024 PASS。
  - 缺样本 **BLOCKED 8 条**：TC-002(DY_VIDEO_2)、TC-003(DY_NOTE_1)、TC-004(DY_NOTE_2)、TC-006(XHS_VIDEO_2)、TC-008(XHS_SHORT_1)、TC-014(XHS_NOTE_MAX)、TC-015(DY_NOTE_1 连带)、TC-023(XHS_NOTE_1 连带)。
  - TC-023 遗留 **P0 未关闭**：默认 `/render/probe` 502；加 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 后 200 但落 XHS 登录页、`has_xsec_token=false`；`render_obscura.py` 无 cookie 注入。
- 镜像事实更正：无 Chromium/Chrome/headless_shell、无 Playwright 浏览器成立；但 `obscura` 存在（`/usr/local/bin/obscura` 0.2.6），调用方“obscura 为空”的表述不成立。
- 其他：`/health` 的 `cookie_status` 仅判存在性，XHS 会话失效仍报 `fresh`（P1）；`ops/smoke.py` 21:28 版 BLOCKED 门已验证不会吞真 FAIL（客户端设 env、服务端未开 → FAIL）。
- 边界：未改 `app/`、`truth.md`、`tests.md` 判据；未 commit / push。本轮 verdict 不支持直接 release，release 由人类确认。

---

## TASK-023 返工：Obscura 冷启动与 1C 预算（2026-11-08 22:00–22:35 +08:00）

### 本轮改动（只动实现与 evidence.md）

- `container/app/parsers/render_obscura.py`
  - 去掉固定 1000ms settle，改为约 120ms 的就绪轮询：标题非 `loading` 且（xhs 页面）内容含 `xsec_token` 即返回；上限仍受 12s 总预算约束。
  - Playwright driver 与 `connect_over_cdp` 的 browser 改为进程内单例，固定在一个专用线程（sync API 有线程/greenlet 绑定）；每次请求只 `new_context()` → `new_page()`，只关闭 context，任何路径都不调用 `browser.close()`；断线时 `playwright.stop()` 后下次重连。
  - `app` 启动时预连一次 CDP（`prewarm`），失败不影响启动；预连成本不再计入首个请求。
  - 只跳过 `image` / `media` / `font` / `stylesheet` 子资源，脚本照常执行；`goto(wait_until="commit")` 用 2s 探针超时后立即进入轮询（超时不会中止导航）。
  - 就绪时间越过 11.85s 仍按 12s 预算返回 504，保持 C10 的「超过 12s 返回 TIMEOUT」。
- `container/app/main.py`：startup 预连 Obscura。
- `Dockerfile`：`HEALTHCHECK --start-period` 调整为 40s（预连需要时间）；默认仍不装 Chromium / Playwright 浏览器。
- 未改 `truth.md`、`tests.md`、`tasks.md` 的任何判据；未 commit / push。

### 1C1G 实测（`--cpus=1 --memory=1g`，ENABLE_OBSCURA=1）

- 3 个构建迭代共 15 次 TC-023 尝试：`<12s` 且 200 的只有 **7 次**，其余 8 次为 502/504 或 12s 后才返回。**没有任何一次 5/5。**
- 最优一批（轮询 + 单例 + 预连，未加严格预算检查）：`12.004s(502) / 11.464 / 11.301 / 11.313 / 11.903`，4/5。
- 最终构建 5 连跑：`12.612(502) / 11.820(200) / 12.176(504) / 12.220(502) / 15.011(504)`，1/5。
- 官方 `ops/smoke.py --case TC-023` 在 1C：**FAIL**，13.018s，HTTP 502。
- 结论：1C 下小红书页面的 JS 水合本身需要 12–15s；轮询、连接复用和预连把最好成绩从约 13.1s 压到约 11.3s，但方差大，无法稳定满足 5/5 <12s。要满足冻结的 12s 预算，容器规格应为 **≥2C1G**（truth C12 的「开启时建议 1C1G」需要人签变更，本轮未改）。

### 2C1G 实测

- 同一镜像、同一样本，`--cpus=2 --memory=1g`：probe 3/3 PASS（8.946s / 9.999s / 9.243s）；官方 smoke TC-023 PASS。余量约 2–3s。

### 1C 下的其他用例（ENABLE_OBSCURA=1）

| 用例 | 结果 | 实测 |
|---|---|---|
| TC-024 `douyin-no-obscura` | PASS | douyin 200，play_addr 非空；renders/cdp_connects 增量 0；obscura 日志抖音命中 0；两个抖音模块均不 import render |
| TC-018 health | PASS | 200 |
| TC-019 dy-argus-1 | PASS | argus 0→1，browser_launches 不增 |
| 默认关闭（0.5C1G） | PASS | `render.enabled=false`，obscura 进程 0，`/render/probe` 404 |
| 镜像默认浏览器 | PASS | `/ms-playwright` 不存在，chrome/chromium/headless_shell 计数 0，obscura 0.2.6 |

所有 502/504 之后 obscura CDP 端口仍存活（`obscura_cdp_alive=true`，进程数 1），确认没有 `browser.close()`。

### 样本问题（与代码无关）

- 冻结样本 `XHS_NOTE_1`（`6af04386000000001500d626`）现在直接 `curl` 就是 **302 → /login**，不经过 obscura；旧 `xsec_token` 已不被接受。验收员 r2 也记录了同一现象。
- 本轮 TC-023 使用 2026-11-08 22:23 从 explore feed 新取的真实笔记链接（`6a883be50000000018018c43`），见 `evidence/l1/task-023/sample-expiry.json`。QA 复跑必须换新样本；否则 FAIL/BLOCKED 是样本失效，不是实现回归。

### 生产前提（P1，与旧证据一致）

- Obscura 主机不能处于 fake-ip/私网解析环境：Clash fake-ip `198.18.0.0/15` 会被 SSRF 防护拒绝。本地证据用了 `OBSCURA_ALLOW_PRIVATE_NETWORK=1`，生产默认不加，保持严格模式。
- 开启 Obscura 时启动会多做一次 CDP 预连（约 0.3–1.1s）；默认关闭时不导入 Playwright、不连接、不启动任何浏览器进程。

### 证据文件（`evidence/l1/task-023/`）

- `tc023-1c-runs.json`、`tc023-2c-runs.json`、`tc023-1c-smoke.json`、`tc023-2c-smoke.json`
- `tc024-1c.json`、`regression-tc018.json`、`regression-tc019.json`、`default-off.json`
- `sample-expiry.json`、`build.log`
