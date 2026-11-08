# l1-parser-core 独立 QA 结论

- mode_id: beacon-go
- run_id: qa-l1-20261108-2143
- stage: qa
- verdict: **BLOCKED**
- 验收人: @验收员（独立验收，maker≠checker）

## 判定摘要

镜像干净构建成功，默认镜像无任何 Chromium/Chrome/Playwright 浏览器二进制（C9/C12 达标）。
默认路径 TC 与 accept_local 全部通过；但 **7 个 TC 因缺少真实样本无法执行**，且 **AC-017 的 Obscura 渲染（TC-023）在真实页面上实测失败**（根因已定位并验证修法），因此 release 门不通过。

| 项 | 结果 |
|---|---|
| 干净构建 `docker build --no-cache` | exit 0，镜像 1.02GB，ID 5c2a8624 |
| 默认镜像内浏览器 | 无 chromium/chrome/headless_shell、无 /ms-playwright；playwright 仅客户端；`chromium.launch` 按预期报可执行文件不存在 |
| ENABLE_OBSCURA 默认 | 未设置（/health render.enabled=false），entrypoint 不启动 obscura |
| smoke 合并矩阵 | **PASS 17 / FAIL 0 / BLOCKED 7** |
| accept_local | **PASS 2/2**（douyin 121261002B、xhs 21220376B；ffprobe 缺失，未验编码/时长） |
| Obscura 渲染探针 | **FAIL**：真实 xhs 页 502 PARSE_FAILED；根因 SSRF 防护拦截 Docker DNS |

以上全部结果均在最终镜像 `sha256:5c2a862471b1…`（构建于 2026-11-08 21:36:50 +0800）上复跑取得；容器 `docker inspect` 的 Image 与该 ID 一致。

## 必改项（按优先级）

1. **P0 · AC-017 / TC-023 渲染链路不可用。**
   entrypoint 以 `obscura serve --port 9222 --stealth` 启动，obscura 0.2.6 的 SSRF 守卫把 Docker 内置 DNS
   `127.0.0.11` 视为私网地址，所有外部导航报
   `dns error: SSRF blocked`。同容器内 Python urllib 访问 xiaohongshu.com/example.com 均 200，排除容器断网。
   手工以 `obscura serve --port 9333 --stealth --allow-private-network` 重试后，CDP 打开
   example.com(200)、www.xiaohongshu.com(200) 成功，根因确认。
   **修复**：在 `container/entrypoint.sh` 的 obscura 启动参数补 `--allow-private-network`（或等效
   `OBSCURA_ALLOW_PRIVATE_NETWORK=1`，并评估 SSRF 暴露面），然后用真实 XHS_NOTE_1 样本重跑 TC-023。
2. **P0 · 7 个 TC 缺真实样本，无法认证对应 AC。**
   缺：`DY_VIDEO_2`、`DY_NOTE_1`、`DY_NOTE_2`、`XHS_VIDEO_2`、`XHS_NOTE_MAX`、`XHS_NOTE_1`；
   TC-015 还依赖 `DY_NOTE_1`。truth/tests 中这些样本仍是占位文案（如「抖音短链样本 A」）。
   **修复**：补齐真实样本 URL（note 页需带 xsec_token 的 HTTPS 链接，外加超限大文件样本），重跑 smoke。
   BLOCKED 列表：TC-002、TC-003、TC-004、TC-006、TC-014、TC-015、TC-023。
3. **P1 · `ops/refresh_cookie.py` 写出的 env 无法被 `docker --env-file` 使用。**
   脚本用 Python repr 写值（单引号包裹），docker `--env-file` 不解析引号，容器内 cookie 名与值被污染，
   表现为抖音 502 `upstream returned an empty 200`。剥掉引号后同一镜像抖音即 200。
   **修复**：改为裸值/双引号转义或导出纯 `KEY=VALUE`，并补一条容器内 cookie 自检。
4. **P1 · 默认限流与验收脚本冲突。**
   `PARSE_RATE_LIMIT_PER_MIN` 默认 20/min/IP，而 smoke 一轮会发 >20 次 /parse，默认配置下
   尾部用例收到 429（本轮 TC-022、TC-024 实际命中 429）。专项容器已用
   `PARSE_RATE_LIMIT_PER_MIN=100` 规避并在日志中注明。
   **修复**：明确验收时该变量的取值（脚本内置或文档化），或调整默认限流策略。
5. **P2 · 验收脚本健壮性。**
   - `accept_local.py` 在 douyin 失败时直接抛错，后续 xhs 不执行，一次运行无法给出双平台结论。
   - `smoke.py` TC-016/TC-024 的说明在未真正完成检查时也打印「SMOKE_CONTAINER_ID 未设置」；
     镜像内无 docker CLI，TC-024 的 obscura 日志检查恒为跳过。
   - 镜像无 ffprobe，accept_local 只能校验字节数，不能校验编码/时长。

## 已验证达标项

- 默认镜像不装浏览器：`INSTALL_CHROMIUM` 已从 Dockerfile 移除（ARG 不存在），实测无任何浏览器二进制；
  这与 truth C9/C12「默认不装 Chromium」一致。任务描述中的「INSTALL_CHROMIUM 默认 0」已无法按原样核对，
  改为按 C9/C12 的运行时事实验收。
- Obscura 二进制存在（0.2.6，120MB），默认不启动；开启后 `/health` render.enabled=true，CDP 可连。
- 抖音全程 Argus 直连：TC-019/020 在主容器 PASS，TC-021/022 在对应注入容器 PASS，browser_launches 不增；
  ENABLE_OBSCURA=1 时 TC-024 PASS。
- TC-009（COOKIE_EXPIRED 503）、TC-013（TIMEOUT 504）、TC-021（PARSE_FAILED 502）、TC-022（TIMEOUT 504）
  在各自注入容器内全部 PASS，错误信封字段完整、items 为空。
- 下载不落盘、用户 cookie 字段被拒、健康检查、非法输入与不支持平台均 PASS。

## 各容器运行说明

- main：默认配置（限流 20/min），`PARSE_BASE=http://127.0.0.1:8080`，使用去掉引号的干净 cookie env。
- stub / drop / delay / obscura：各自注入
  `PARSE_STUB_COOKIE_EXPIRED=douyin` / `RENLINK_DROP_ARGUS_HEADER=1` / `PARSE_UPSTREAM_DELAY_MS=13000` /
  `ENABLE_OBSCURA=1`，并统一 `PARSE_RATE_LIMIT_PER_MIN=100` 以免限流掩盖结论。
- 合并矩阵规则：某 TC 在为其设计的容器内 PASS 即记 PASS；其余容器因注入的极端环境产生的 FAIL
  （如 delay 容器内 13s 延迟导致正常用例超时）不作为产品失败。
- 快照：`snapshot-digest.txt`（源文件 MD5 汇总，2026-11-08 21:24:31 +0800 冻结），镜像由该快照构建。

## 证据文件

- `build-default.log` / `build-exit.txt` / `image.txt` / `snapshot-digest.txt` / `dockerfile-md5.txt` / `git-status.txt`
- `image-browser-check.txt` — 镜像内浏览器检查原始输出
- `smoke-main.log` + `main/l1/` — 默认配置 24 用例逐条 JSON
- `stub/` `drop/` `delay/` `obscura/` — 专项注入容器 smoke 日志与逐条 JSON
- `accept-local.log` — 双样本解析+下载
- `render-probe.log` — Obscura 真实页探针、CDP 直连、同容器 Python 对照组、`--allow-private-network` 对照、健康计数
- `matrix.json` — 合并后的每 TC 判定
