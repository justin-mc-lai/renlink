# l1-parser-core 独立 QA 复验（r2）

| 项 | 值 |
|---|---|
| mode_id | `beacon-go` |
| run_id | `qa-l1-20261108-2225` |
| stage | `qa` |
| current_stage | `plan`（`run_1084fcb4301353f56601ec48`，status=`blocked`，reason=`stage_executor_not_registered`） |
| 验收对象 | `renlink-l1-final:latest` = `sha256:cf44f898eb17caa77baaa44013deb83bd816de5f2cfeed15b6d161f35b2bfe6a`，created `2026-11-08T13:14:17.495959384Z` |
| truth | frozen / R1 |
| 判定者 | 验收员（maker≠checker；本轮只读实现、只写 evidence） |
| evidence_refs | 本目录 `image.txt`、`browser-check/`、`main/`、`stub/`、`delay/`、`cache/`、`drop/`、`obscura/`、`gate-audit/`、`blocked-mapping.json`、`run-params.md`、`sha256-manifest.txt` |

## 结论（分段，不用单一 BLOCKED 覆盖已通过部分）

1. **主路径 douyin：PASS** — 真实链接解析 + 下载 162,700,599B / 1407.53s，退出码 0 段落内通过。
2. **主路径 xhs：FAIL（本轮不可复现）** — 同一镜像、同一 cookie 池下 `POST /parse` 稳定返回 502 `PARSE_FAILED`；根因是 XHS 会话已失效（上游 302 到 `/login`），不是镜像代码路径。调用方自报的「xhs PASS 46,681,581B」在本轮无法复现，故不能记为 PASS。
3. **6 个服务端模式用例：PASS** — TC-009 / TC-013 / TC-022 / TC-020 / TC-021 各自独立容器复跑均 PASS；额外 TC-024 PASS。
4. **8 个 TC：BLOCKED（缺真实样本）** — 清单见下，全部 `failures=[]`，原因仅为样本缺失。
5. **TC-023：遗留 P0 未关闭** — 默认 `ENABLE_OBSCURA=1` 下 `/render/probe` 仍 502；加 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 后探针 200，但落点是 XHS 登录页（`has_xsec_token=false`），渲染链路取不到笔记内容。

**因此本轮不是干净的「主路径 PASS」，release 不能据此放行。**

## 1. 镜像核对

- `docker image inspect` Id 全值与调用方给定一致：`sha256:cf44f898eb17caa77baaa44013deb83bd816de5f2cfeed15b6d161f35b2bfe6a`。
- created `2026-11-08T13:14:17.495959384Z`（= 13:14 UTC），与调用方一致。
- 大小：`docker images` 显示 `1.02GB`（内容 248MB），`docker image inspect .Size=247849249` 字节；两种口径都记录，不是矛盾。
- 证据：`image.txt`。

## 2. accept_local（最终镜像，端口 18094，`PARSE_RATE_LIMIT_PER_MIN=0`）

客户端：`PARSE_BASE=http://127.0.0.1:18094 .venv/bin/python ops/accept_local.py`（证据 `main/accept-local.log`，sha256 见清单）。

| 平台 | 结果 | 耗时 | 字节 | 说明 |
|---|---|---|---|---|
| douyin | **PASS** | 762ms | 162,700,599B | ffprobe：1407.533333s |
| xhs | **FAIL** | 692ms | — | HTTP 502 `PARSE_FAILED`，未进入下载 |

- 退出码 **1**，没有出现 `PASS: 2/2`。
- xhs 响应原文：`{"ok":false,"error":{"code":"PARSE_FAILED","message":"l2-xhs-images 的 parse_note 尚未冻结，l1 仅保留接缝","retryable":true},"items":[],...}`（`main/tc-005-detail.json`）。
- 根因证据：同一 cookie 请求 `https://www.xiaohongshu.com/explore` 返回 302 → `/login`；容器内 yt-dlp 抽取该短链报 `Unsupported URL: https://www.xiaohongshu.com/login?...`（`main/xhs-cookie-check.txt`）。即 XHS 会话失效，解析降级到 note 接缝。
- **与调用方自报不一致**：调用方 douyin 121,261,002B、xhs 46,681,581B；本轮 douyin 为 162,700,599B（时长相同，取流档位不同），xhs 完全未通过。调用方的具体字节数不可复现。

## 3. 默认配置 smoke（同一容器 18094）

`PARSE_BASE=http://127.0.0.1:18094`，仅注入 3 个真实样本（DY_VIDEO_1 / XHS_VIDEO_1 / DY_SHORT_1），不注入任何服务端模式变量。

```text
SUMMARY pass=9 fail=1 blocked=14
exit=2
```

- 调用方自报 `pass=10 fail=0 blocked=14`；**本轮实际 `pass=9 fail=1 blocked=14`**，差异是 TC-005 xhs-video-1 失败（http 502），其余逐条一致。
- TC-001/007/010/011/012/016/017/018/019 PASS；TC-005 FAIL；14 条 BLOCKED。
- 证据：`main/smoke-main.log`、`main/l1/`、`blocked-mapping.json`。

## 4. 服务端模式用例（各自独立容器，镜像 id 均核对为 cf44f898…）

启动参数见 `run-params.md`；每条容器 env / 端口 / 镜像已 `docker inspect` 核对。

| TC | 容器 env | 端口 | 结果 | 关键输出 |
|---|---|---|---|---|
| TC-009 | `PARSE_STUB_COOKIE_EXPIRED=douyin` | 18095 | **PASS** | http 503，`error.code=COOKIE_EXPIRED`，`retryable=true` |
| TC-013 | `PARSE_UPSTREAM_DELAY_MS=13000` | 18096 | **PASS** | http 504 `TIMEOUT`，客户端 12010ms（<15000ms） |
| TC-022 | 同上 | 18096 | **PASS** | http 504 `TIMEOUT`，客户端 12004ms |
| TC-020 | `RENLINK_DISABLE_CACHE=1` | 18097 | **PASS** | 连跑 3 次，http 200 |
| TC-021 | `RENLINK_DROP_ARGUS_HEADER=1` | 18098 | **PASS** | http 502 `PARSE_FAILED` |
| TC-024（附加） | `ENABLE_OBSCURA=1` | 18099 | **PASS** | douyin 仍走 Argus；`obscura_log_douyin_hits=0`，render 计数不增 |

证据：`stub/smoke.log`、`delay/smoke.log`、`cache/smoke.log`、`drop/smoke.log`、`obscura/smoke.log` 及各自 `l1/smoke-TC-*.json`。

## 5. 镜像内浏览器事实（与调用方第 4 点不符）

`browser-check/browser-check.txt`（镜像内实测）：

```text
chromium=(none)  chromium-browser=(none)  google-chrome=(none)  chrome=(none)  headless_shell=(none)
obscura=/usr/local/bin/obscura
obscura 0.2.6
/ms-playwright 不存在；/root/.cache/ms-playwright 不存在
INSTALL_CHROMIUM / ENABLE_OBSCURA / PLAYWRIGHT* 均未设置
```

- **无 Chromium/Chrome/headless_shell、无 Playwright 浏览器：成立。**
- **但 `command -v obscura` 不是空，而是 `/usr/local/bin/obscura`（0.2.6）。** 调用方「chromium/chrome/obscura 全空」的表述与镜像事实不符；obscura 是静态 CDP 服务二进制，不等于浏览器，但这句话本身不能作为证据。

## 6. 8 条 BLOCKED 的逐条映射（7 个样本 → 8 个 TC）

`blocked-mapping.json` 中 8 条样本型 BLOCKED 全部 `failures=[]`，note 仅为「缺少样本: X」，无其他失败：

| TC | 用例 | 缺失样本 |
|---|---|---|
| TC-002 | dy-video-2 | `DY_VIDEO_2` |
| TC-003 | dy-note-1 | `DY_NOTE_1` |
| TC-004 | dy-note-2 | `DY_NOTE_2` |
| TC-006 | xhs-video-2 | `XHS_VIDEO_2` |
| TC-008 | xhs-short-1 | `XHS_SHORT_1` |
| TC-014 | size-cap | `XHS_NOTE_MAX` |
| TC-015 | field-contract | `DY_NOTE_1`（连带） |
| TC-023 | obscura-xhs-render | `XHS_NOTE_1`（连带） |

另有 6 条默认 smoke BLOCKED 属「服务端模式未开启」而非样本缺失：TC-009、TC-013、TC-020、TC-021、TC-022、TC-024；这 6 条已在第 4 节逐条独立容器验为 PASS。

## 7. TC-023 遗留 P0（未关闭，具名保留）

- 默认 `ENABLE_OBSCURA=1`（镜像内 entrypoint 不带 `--allow-private-network`）：`GET /render/probe` 对真实 XHS 页返回 **502** `PARSE_FAILED`「Obscura 渲染失败: Error」，耗时 1.658s。复现上一轮 P0。证据：`obscura/render-probe-default.json`、`obscura/obscura-server.log`（WS read error: connection reset）。
- 加 `OBSCURA_ALLOW_PRIVATE_NETWORK=1`（entrypoint 会追加 `--allow-private-network`）：探针 **200**，`obscura_alive=true`，渲染 216,367 字节，但 `final_url` 是 `https://www.xiaohongshu.com/login?...`，`has_xsec_token=false`，耗时 11.9s。证据：`obscura/render-probe-allow-private.json`。
- `render_obscura.py` 中没有任何 cookie 注入逻辑（全文件无 cookie 相关代码），因此即使放开私网，渲染浏览器也是未登录态，拿不到笔记正文/`xsec_token`。
- **结论：P0 有两层，均未关闭**：(a) SSRF 私网守卫默认仍拦截 Docker DNS `127.0.0.11`，需非默认开关；(b) 渲染上下文不带会话 cookie，落登录页。TC-023 仍无法认证。

## 8. `ops/smoke.py` 21:28 版 BLOCKED 改动审计（sha256 `5672c937…`）

代码位置：`main()` 中

```python
missing = [key for key in case["requires"] if not ctx["samples"].get(key)]
missing_server = [key for key in case.get("server_env", []) if not os.getenv(key)]
status = "BLOCKED"
if missing: ...
elif missing_server:
    note = ... "服务端未以 " + ", ".join(missing_server) + " 启动"
else:
    ... 真正执行 case，status = PASS/FAIL
```

- 触发条件只有两种：样本缺失，或**运行 smoke 的客户端进程**未设置对应 env。二者都不执行用例，记录 `failures=[]`。
- 行为验证（`gate-audit/`）：
  - 不设 `PARSE_STUB_COOKIE_EXPIRED` → TC-009 `BLOCKED`，exit 3（`gate-control.log`）。
  - 客户端设了 `PARSE_STUB_COOKIE_EXPIRED=douyin`、但服务端未以该模式启动 → TC-009 **FAIL**，exit 2，7 条 failures（`gate-negative.log`）。
- **结论：不会把真实 FAIL 吞成 BLOCKED。** 唯一副作用是覆盖率：TC-020 上一轮在默认配置下能 PASS，本轮因 `RENLINK_DISABLE_CACHE` 未设而变 BLOCKED（属保守处理，不是假绿）。

## 9. 其他发现

| 级别 | 项 |
|---|---|
| P1 | `/health` 的 `cookie_status` 只判 env 是否存在，XHS 会话已失效（302 到 /login）仍报 `fresh`，会误导运维。证据：`main/health.json` + `main/xhs-cookie-check.txt`。 |
| P1 | XHS 会话失效时错误被包装成 `PARSE_FAILED`「l2 parse_note 尚未冻结」，而不是 `COOKIE_EXPIRED`；调用方会误判为 l2 缺口。 |
| P2 | `accept_local.py` 任一平台抛错即终止（本轮 xhs 失败掩盖了后续统计），一次运行无法给出双平台结论；上一轮已记，未改。 |
| P2 | 调用方「镜像内 obscura 命令为空」的事实陈述错误（见第 5 节）。 |
| 观察 | 复验期间仓库仍有新构建（`renlink-l1:qa3` 22:16、`qa-obscura-v2` 等）与运行中的 `task023-1c` 容器，工作区 dirty；本 verdict 只对 `sha256:cf44f898…` 生效。 |

## 10. 边界与下一步

- 本轮未改 `app/`、`truth.md`、`tests.md` 判据；未 commit、未 push；只新增/修改 `evidence/qa/l1-qa-final-r2/` 与 `evidence/qa/` 索引、`evidence.md` 登记段。
- next（建议）：运营补一个有效 XHS 会话 + 7 个缺失样本；TC-023 需决定是否给渲染上下文注入 cookie，或明确其不属于 l1 范围；之后重跑 `qa`。**release 由人类确认，本轮 verdict 不支持直接 release。**

plain_summary：最终镜像 douyin 主路径和 6 个服务端模式用例独立复验通过；xhs 主路径因会话失效未通过、调用方 2/2 不可复现；8 个 TC 仅因缺样本 BLOCKED；TC-023 遗留 P0 仍在。
