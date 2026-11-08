# l1-parser-core 独立 QA 结论（Obscura 回退专项）

- mode_id: beacon-go
- run_id: qa-l1-20261108-2145
- stage: qa
- verdict: **FAIL**（功能链路通过；容器规格口径不成立）
- 验收人: @验收员（独立验收，maker≠checker）
- 被测镜像: `sha256:8b4f47626ff402a7cac59697764a4f1f406562debd7663cdff8e8ec37f187a6c`
- 构建: `docker build --no-cache -t renlink-l1:qa2 .` → exit 0（2026-11-08 21:47 +0800）
- 未 commit、未 push、未改任何产品代码或 truth/tests/tasks。

## 判定表

| 项 | 结果 | 实测 |
|---|---|---|
| TC-023 Obscura 渲染小红书（文档口径 1C1G） | **FAIL 6/6** | 502 PARSE_FAILED ×5、504 TIMEOUT ×1；12.2–13.5s；标题在 13.1s 才就绪 |
| TC-023 同上（2C1G） | **PASS 2/2 + smoke PASS 1/1** | 9.44s / 9.96s；smoke 冷启动 11.905s（余量 95ms） |
| TC-023 同上（不限制 CPU） | **PASS 2/2** | 9.57s / 9.83s；title 正确、xsec_token=true、obscura_alive=true |
| TC-023 严格模式（生产默认，不加 allow 参数） | **FAIL（环境前提）** | 502，1.66s；`dns error: SSRF blocked: 'example.com' resolves to forbidden address 198.18.0.141` |
| TC-024 抖音不经 Obscura（1C1G，ENABLE_OBSCURA=1） | **PASS** | 200 / 173ms；items=1；remoteUrl 为非空 play_addr；renders 0→0、cdp_connects 1→1；obscura 日志抖音命中 0；两模块均不 import render |
| 默认关闭（0.5C1G，未设 ENABLE_OBSCURA） | **PASS** | render.enabled=false；obscura 进程数 0；`/render/probe` → 404 |
| TC-018 health | **PASS** | 200，ok=true，两平台 cookie_status 存在 |
| TC-019 抖音 Argus 直连 | **PASS** | 200；argus_requests 0→1；browser_launches 不增 |
| `/render/probe` 域名边界 | **PASS** | douyin.com → 400；`xiaohongshu.com.evil.example` → 400 |

## 必改项

1. **P0 · 开启 Obscura 的容器规格口径与实测不符。**
   truth C12 与实现证据均写「开启时建议 1C1G」，但同一镜像在 `--cpus 1 --memory 1g` 下
   TC-023 连续 6 次全部失败：`page.goto` 8s 超时后，代码里的 1000ms 等待在 1C 配额下实际耗时
   约 4s（8.0s→13.0s），标题 13.1s 才就绪，超过 C10 的 12s 总预算。
   同一镜像 `--cpus 2 --memory 1g` 时 2/2 通过（9.44–9.96s），smoke 冷启动 11.905s，距 12s 只剩 95ms。
   **修复**：把「开启时」的口径改为 **至少 2C1G**（建议 2C2G），并在 truth C12、evidence.md
   同步；truth 变更需人类确认。若要保留 1C，需实现降低冷启动开销（例如复用 Playwright/CDP 连接，
   每次只 `new_context()`）并复测到稳定余量。
2. **P1 · 严格模式的生产前提需写明。**
   生产默认不加 `OBSCURA_ALLOW_PRIVATE_NETWORK=1` 时，本机 Docker DNS 经 Clash 返回
   `198.18.0.0/15` fake-ip，Obscura 的 SSRF 守卫 100% 拦截，TC-023 直接 502。
   这不是本轮代码引入的缺陷，但交付文档必须写明「Obscura 主机不得处于 fake-ip/私网解析环境」，
   或给出可配置的解析方案；默认安全策略不应放宽。

## 复跑说明

- 默认容器 0.5C1G：`qa2-default`，未设 ENABLE_OBSCURA。
- Obscura 容器：`qa2-obscura-strict`（严格）、`qa2-obscura-work`（1C1G）、
  `qa2-obscura-2c`（2C1G）、`qa2-obscura-nolimit`（无限制），均 `ENABLE_OBSCURA=1`；
  除 strict 外均带 `OBSCURA_ALLOW_PRIVATE_NETWORK=1`（仅本地绕开 Clash fake-ip，生产默认不带）。
- 所有容器 `PARSE_RATE_LIMIT_PER_MIN=0`，避免限流掩盖结论。
- 抖音 /parse 样本：`https://v.douyin.com/Y7MgY9YnYAg/`；
  TC-023 样本：`XHS_NOTE_1`（与实现证据同一笔记链接）。

## 证据文件

- `qa-matrix.json` — 机器可读判定
- `qa-build.log` / `qa-image.txt` — 干净构建与镜像信息
- `qa-source-digest.txt` / `qa-git-status.txt` — 源码快照与未改动证明
- `qa-strict-ssrf.json` — 严格模式 SSRF 原始错误
- `qa-1c-vs-2c.json` — 1C/2C/无限制三组原始测量
- `default/`、`work/`、`work2c/` — smoke 逐条 JSON
- `qa-probes/` — 原始 probe 响应

## next

- 人类确认开启 Obscura 的容器规格（≥2C1G）并更新 truth C12；或让实现方先做冷启动优化。
- 规格更新后，只需复跑 TC-023（2C 容器）即可转 PASS；TC-024、默认关闭、TC-018/019、域名边界本轮已 PASS。
- host run `run_1084fcb4301353f56601ec48` 仍为 `current_stage=plan`、`status=blocked`（`stage_executor_not_registered`），本轮未推进。

plain_summary: Obscura 渲染链路本身在 2C 机器上能跑通（标题、xsec_token、进程存活都对），
但按交付文档写的 1C1G 规格连续 6 次全部失败，12s 预算不够；抖音不使用 Obscura、默认关闭和回归项均通过。
