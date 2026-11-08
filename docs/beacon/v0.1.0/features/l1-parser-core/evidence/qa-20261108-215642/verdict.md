# l1-parser-core 独立 QA 结论（Obscura 回退 / TASK-021/022）

- mode_id: `beacon-go`
- run_id: `qa-l1-20261108-2218`
- stage: `qa`
- verdict: **BLOCKED**
- 验收人: @验收员（独立验收，maker≠checker）
- 验收对象镜像:
  - v1（21:58 构建，旧源码快照）`renlink-l1:qa-obscura` = `sha256:578e1f62da94…`，247,848,614 bytes
  - v2（22:12 构建，当前源码快照）`renlink-l1:qa-obscura-v2` = `sha256:f4261e92e19f…`，247,849,845 bytes
- host run `run_1084fcb4301353f56601ec48`：`status: blocked (loop_stage governance_precheck)` / `stage: plan` / `reason: stage_executor_not_registered`（既有状态，非本轮失败理由）
- truth：`clean: true` / `body drift: false`

## 判据

只认 frozen truth 的 C9 / C10 / C12、AC-017，与 tests.md 的 TC-023 / TC-024。未改 truth、tests.md、代码；未 commit、未 push。

## 逐项结论

| # | 项 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | 干净构建 `docker build --no-cache -t renlink-l1:qa-obscura .` | **PASS** | exit 0；`build-docker.log`；镜像 `578e1f62…` |
| 2 | 默认模式进程/探针/落盘 | **PASS** | 仅 `uvicorn`；`/render/probe` 404；`/tmp` 0 项；`playwright_loaded=False` |
| 3 | 镜像默认无浏览器 | **PASS** | `/ms-playwright` ABSENT；chrome/chromium/headless_shell 可执行文件 0；obscura 0.2.6 存在但默认不启动 |
| 4 | TC-024 抖音不经 Obscura | **PASS** | v2 smoke PASS；抖音 200/625ms；`renders`、`cdp_connects` 前后不变；obscura 日志 douyin 命中 0；`douyin.py`/`douyin_argus.py` 不 import render |
| 5 | 渲染超时映射 | **PASS（附注）** | 504 `TIMEOUT`、`retryable:true`、无 items；但注入 `RENLINK_RENDER_WAIT_MS=1000` 实际 8.3s 才返回（连接阶段未受该值约束） |
| 6 | `/parse` 12s 超时 | **PASS** | 504 `TIMEOUT`、12.02s、`items:[]`、`retryable:true` |
| 7 | 抖音真实链接 `v.douyin.com/Y7MgY9YnYAg` | **PASS** | v1 200/897ms；v2 200/675ms；`remoteUrl` 非空 douyinvod，1080×1920 |
| 8 | `/tmp` 渲染残留 | **PASS** | Obscura 渲染后仅 `obscura.log`，无 `playwright-artifacts-*` |
| 9 | 代码边界 | **PASS** | `connect_over_cdp` + `new_context()`；无 `browser.close()` 调用；未启用时零 playwright import |
| 10 | TC-023 Obscura 渲染小红书笔记页 | **BLOCKED** | 见下节；最终镜像当前 3 次 504，页面被重定向到登录墙 |
| 11 | 小红书回归 `xhslink.cn/o/1zbdThHpdb0` | **BLOCKED（上游）** | 22:00 首次 200/1298ms/item_count=1；随后默认容器与 Obscura 容器同时 502；主机 `.venv` 直接 yt-dlp 报 `No video formats found`，与容器/Obscura 无关 |
| 12 | TASK 台账 | 一致 | tasks.md 中 TASK-018~022 均为 `[x]`（验收时实际状态；MausBot 描述里的 `[ ]` 已不存在） |

## TC-023 详细证据

### 1) 旧源码镜像（v1）最后绿灯

- 时间：2026-11-08 22:02
- 结果：PASS
- title：`长安四驱越野升顶皮卡房车#二手房车 #房车旅行 #房车生活 #房车自驾游 - 小红书`
- `has_xsec_token=true`，`html_bytes=578067`，`elapsed_ms=10339`，`obscura_alive=true`
- 证据：`smoke-work/smoke-TC-023.json`

### 2) 当前源码镜像（v2，`f4261e92…`）复跑

- 22:09 首次：HTTP 504，11.88s，`TIMEOUT`，`Obscura 渲染超过 12s 总预算`
- 22:10 重试 2 次：HTTP 504，13.0s / 12.6s，`TIMEOUT`
- 22:13 冷却后：HTTP 504，11.89s
- 渲染统计：`renders=0`、`failures=1`、`cdp_connects=1`、`prewarms=1`、`browser_launches=0`
- 证据：`tc023-v2-retry.txt`、`tc023-v2-after-cooldown.txt`、`smoke-v2/smoke-TC-023.json`

### 3) 同一时刻的旧镜像对照（排除“只是新代码坏了”）

- 旧镜像 v1（22:14）对本应同一笔记链接返回 HTTP 200，但：
  - `title = 小红书 - 你的生活兴趣社区`
  - `final_url = https://www.xiaohongshu.com/login?redirectPath=…`
  - `has_xsec_token=false`
- 说明：当前小红书把该分享链接重定向到登录页，旧镜像的 200 也不满足 TC-023 的“标题正确 + 含 xsec_token”。新镜像的 `_wait_ready(need_token=True)` 会一直等到 12s 预算耗尽，因此返回 504 而不是假 200。
- 证据：`tc023-old-image-now.txt`、`tc023-new-image-now.txt`

**判定：不是单纯的新代码回归；但最终产物在当前真实页面上无法通过 TC-023，AC-017 不能认证。**

## 必改项（按优先级）

1. **P0 · TC-023 无法在最终镜像上认证。**
   当前分享链接被小红书重定向到登录页（旧镜像同时刻也拿不到笔记标题与 xsec_token）。
   修复方向（二选一，需先明确再改 truth/实现）：
   - 运营提供一条新鲜、可直接打开且带有效 `xsec_token` 的笔记分享链接，在最终镜像上重跑 TC-023 至 PASS；或
   - 渲染路径把运营方 `XHS_COOKIE` 注入 `browser.new_context(cookies=…)`，让登录墙页面也能渲染出笔记。当前 `render_obscura._render_page()` 的 `new_context()` 没有携带任何 cookie，登录墙下永久 504。
2. **P1 · `RENLINK_RENDER_WAIT_MS` 没有约束 CDP 连接阶段。**
   注入 1000ms 时实测 8.3s 才返回 504（`_ensure_browser` 用 8000ms 上限，未用 `budget_ms`）。要么把连接阶段也纳入 wait 预算，要么在文档里写明该变量只约束页面阶段。
3. **P1 · “渲染等待 ≤8s”与实现不一致。**
   `_wait_ready` 的截止时间是 11.85s，不是 8s；8s 只作为 `page.goto` 的上限。C10 的 8s 语义需要澄清（是配置值还是整段渲染上限），否则每次登录墙都会把 12s 预算耗尽。
4. **P2 · `browser_launches` 是静态 0，不构成证据。**
   全仓没有自增点；本次改用 `/proc` 进程表与 obscura 日志直接验证。若保留该字段，应接真实计数或标注为占位。
5. **P2 · Obscura 只挂在 `/render/probe`，没有任何 parse 路径回退到它。**
   AC-017/TC-023 只要求渲染能力，判据上不扣分；但 C9 写的是“通用渲染回退”，若意图是 xhs `/parse` 失败时回退，当前实现没有接上。
6. **P2 · 既有 P1 仍未修：`ops/refresh_cookie.py` 用 `!r` 写 `cookies.env`。**
   `docker --env-file` 不剥单引号，容器内 cookie 会带引号。本次验收使用独立清洗过的临时 env 文件，未改脚本。
7. **P2 · 台账/版本标识不一致。**
   truth.md 仍是 `revision_id: R1`，三个 change 文件仍写着 `status: pending`，但 `truth drift` 为 clean、正文已是 Obscura 版。建议收口时统一，避免下一个验收人误读。

## 未受影响的既有结论

- 默认模式无浏览器、无 obscura 进程、`/render/probe` 404、`playwright` 未 import：PASS。
- 抖音 Argus 直连在默认模式与 Obscura 开启模式均 200，全程无浏览器：PASS。
- 12s 总预算、504 TIMEOUT、无半截 items：PASS。

## 验收边界

- 只新增 `evidence/qa-20261108-215642/`；未改代码、truth、tests.md 判据；未 commit / push。
- 源码在验收过程中于 22:02–22:03 被并发修改（`main.py`、`render_obscura.py`、`render.py`），v1 镜像不对应最终源码；本结论以 v2 镜像 `f4261e92…` 与 `source-digest-v2.txt` 为准。
- 小红书回归当前失败已用主机 `.venv` 直接复现，属上游 yt-dlp 行为，不计入本变更的代码回归；但它是 l1 的实时风险，需单独跟进。
