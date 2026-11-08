---
slug: l1-parser-core
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
depends_on: l2-xhs-images, l4-session-egress
---

# Tasks: l1-parser-core

## 任务台账

- [x] TASK-001 解析路由与契约模型：FastAPI 挂 POST /parse 与 GET /health，pydantic 定义 ParseRequest、ParseItem、ParseResult、ErrorEnvelope，字段名与 truth.md 接口契约逐字一致 · ac=AC-011
- [x] TASK-002 错误信封与错误码：实现 INVALID_URL、INVALID_REQUEST、UNSUPPORTED_PLATFORM、SHORTLINK_FAIL、COOKIE_EXPIRED、PARSE_FAILED、TIMEOUT、RATE_LIMITED 八个码，统一 http 状态与 retryable · ac=AC-005
- [x] TASK-003 域名白名单与输入校验：只放行 douyin.com、v.douyin.com、xhslink.com、xiaohongshu.com 及其子域；url 长度上限 2048；请求体出现 cookie 字段直接拒绝 · ac=AC-013
- [x] TASK-004 短链展开：3 跳上限、HEAD 优先、失败映射 SHORTLINK_FAIL，成功后把 resolved_url 交给平台分支 · ac=AC-004
- [x] TASK-005 f2 抖音分支：DouyinHandler 取 aweme_id，视频走 yt-dlp DouyinIE 或 f2 的播放地址，图文读 PostDetailFilter.images，全程不触发下载 · ac=AC-001
- [x] TASK-006 抖音图文条目归一：images 逐项转 index、type=image、remoteUrl、ext，封面与宽高可空；item_count 取实际条目数 · ac=AC-002
- [x] TASK-007 小红书视频分支：yt-dlp XiaoHongShuIE 取播放地址与标题，items 固定 1 项 · ac=AC-003
- [x] TASK-008 小红书图文路由接 l2：调用 l2 的 parse_note，把返回的 imageList 原图与 xsec_token 归一成 items，needs_transcode=true；本湖不实现 __INITIAL_STATE__ 解析 · ac=AC-011
- [x] TASK-009 cookie 池接缝 l4：get_cookie(platform) 取运营方 cookie，捕获 CookieExpired 映射 503 COOKIE_EXPIRED，日志脱敏 · ac=AC-005
- [x] TASK-010 超时与预算：解析整体 12s 硬超时，返回 504 TIMEOUT；慢上游可注入 PARSE_UPSTREAM_DELAY_MS 用于测试 · ac=AC-009
- [x] TASK-011 体积与条目上限：items 最多 100 项，截断时置 truncated=true；序列化后自检字节数不大于 1024000 · ac=AC-010
- [x] TASK-012 零落盘自检：解析链路不使用临时文件 API，代码评审加测试用 /tmp 快照对比 · ac=AC-012
- [x] TASK-013 健康探针：GET /health 汇总两平台 cookie 新鲜度、上次刷新时间、出口代理模式 · ac=AC-014
- [x] TASK-014 容器镜像依赖：Python 3.11、FastAPI、yt-dlp、f2 0.0.1.7、curl_cffi、Node20、pyexecjs，镜像内自检 f2 与 curl_cffi 可 import；镜像不默认装 Chromium · ac=AC-001
- [x] TASK-015 ops/smoke.py：实现 24 个用例，读环境变量样本，输出 JSON 证据；缺样本时打印 BLOCKED 并以退出码 3 结束 · ac=AC-001
- [ ] TASK-016 样本采集登记：运营采集 8 个槽位，回填采集日期与页面条目数，样本只留在运营侧 · ac=AC-004 · BLOCKED：缺 8 个真实样本槽位（DY_VIDEO_1/2、DY_NOTE_1/2、XHS_VIDEO_1/2、DY_SHORT_1、XHS_SHORT_1），另缺 TC-014 用的 XHS_NOTE_MAX；样本未采集、未编造
- [ ] TASK-017 打包验收：冻结后按 tests.md 跑 24 个用例，真实样本全绿才算本湖通过 · ac=AC-014 · BLOCKED：缺 8 个真实样本槽位，24 用例未能全绿；独立 QA 另有 7 条 BLOCKED，且 TC-023 渲染 P0 未闭合
- [x] TASK-018 抖音 Argus HTTP 分支：f2 取 aweme_id/a_bogus/msToken，curl_cffi(impersonate="chrome") 直连 detail API，补 x-tt-argus、uifid 头与 uifid/verifyFp/fp 参数；主路径不起浏览器，小红书与图文分支不动 · ac=AC-015
- [x] TASK-019 预算、缓存与清理：抖音 /parse 总预算 ≤12s，超时 TIMEOUT，失败 PARSE_FAILED retryable=true 且无半截 items；play_addr 按 aweme_id 缓存 10 分钟；缺 x-tt-argus 时复现上游 403 · ac=AC-016、AC-012
- [x] TASK-020 真实样本验证与证据：用真实抖音链接跑 /parse 连跑 3 次记录 JSON（remoteUrl 可截断）；把实测输出与容器规格写进 evidence.md；tests.md TC-019 到 TC-024 附实测输出 · ac=AC-015、AC-016、AC-017
- [x] TASK-021 容器与部署说明：Dockerfile 默认不装浏览器与 Chromium；Obscura 走可选多阶段（从 h4ckf0r0day/obscura:latest 拷二进制或直接用其镜像），默认关闭；标注不开 Obscura 0.5C1G 可跑、开启建议 1C1G · ac=AC-015、AC-017
- [x] TASK-022 Obscura 通用渲染回退：ENABLE_OBSCURA=1 时启动 `obscura serve --port 9222 --stealth`，应用侧读 PLAYWRIGHT_CDP=ws://127.0.0.1:9222，用 new_context() 接入且不 browser.close()；只服务小红书/未来平台，抖音分支禁止接 Obscura；默认关闭时零进程零依赖 · ac=AC-017 · 对应 change chg_42c00bf71013（可选回退）；该 change 仍 pending，TC-023 的容器 SSRF P0 未闭合

## 依赖关系

| 任务 | 依赖 | 说明 |
|------|------|------|
| TASK-004 | TASK-001 | 展开结果要写进统一契约 |
| TASK-005 | TASK-001、TASK-009 | f2 分支需要 cookie 与统一模型 |
| TASK-006 | TASK-005 | 图文条目来自同一 f2 响应 |
| TASK-007 | TASK-001、TASK-009 | xhs 视频需要 cookie 与统一模型 |
| TASK-008 | TASK-001、l2 交付 | parse_note 由 l2 提供，l1 只做归一 |
| TASK-009 | l4 交付 | get_cookie 与 CookieExpired 由 l4 定义 |
| TASK-010 | TASK-001 | 超时包在路由层 |
| TASK-011 | TASK-001 | 序列化后自检 |
| TASK-015 | TASK-001 到 TASK-013 | 用例依赖接口全部就位 |
| TASK-017 | TASK-015、TASK-016 | 需要真实样本才能判定通过 |
| TASK-018 | TASK-001、TASK-009 | Argus 直连分支复用统一契约与 cookie 池 |
| TASK-019 | TASK-018、TASK-010 | 预算与缓存挂在 Argus 分支上 |
| TASK-020 | TASK-018、TASK-019 | 有可跑的 Argus 分支才能留证据 |
| TASK-021 | TASK-018、TASK-022 | 镜像默认不带浏览器，Obscura 作为可选组件单独说明 |
| TASK-022 | TASK-007 | 渲染回退接在小红书渲染型链路上，抖音分支不接 |

## 交付物清单

| 路径 | 内容 |
|------|------|
| container/app/main.py | 应用装配与 /health |
| container/app/routes_parse.py | /parse 路由与错误映射 |
| container/app/contract.py | 请求响应模型与截断规则 |
| container/app/errors.py | 错误码常量与信封 |
| container/app/parsers/shortlink.py | 短链展开 |
| container/app/parsers/douyin.py | f2 抖音视频与图文分支 |
| container/app/parsers/douyin_argus.py | 抖音 Argus 头/参数直连分支与 play_addr 缓存；抖音不接 Obscura |
| container/app/parsers/render_obscura.py | Obscura CDP 可选接入（默认关闭，仅通用渲染平台）；render.py 保留为兼容别名 |
| container/app/parsers/xhs.py | xhs 视频分支与 l2 图文路由 |
| container/app/session_bridge.py | l4 cookie 池接缝与脱敏 |
| contract/parse_response.schema.json | 响应 schema |
| ops/smoke.py | 24 个用例的执行器 |

## 容器与云端部署（2026-11-08 变更 chg_42d5d41158ba、chg_42c00bf71013）

- Dockerfile 默认不安装 Chromium，也不安装 Playwright 浏览器；主路径与冷启动都不依赖浏览器。
- Obscura 只做通用渲染回退：从 `h4ckf0r0day/obscura:latest` 多阶段拷 `obscura` 二进制（或直接用其镜像），默认关闭；`ENABLE_OBSCURA=1` 才启动 `obscura serve --port 9222 --stealth`。
- 应用侧通过 `PLAYWRIGHT_CDP=ws://127.0.0.1:9222` 接入 Obscura；连接用 `new_context()`，禁止 `browser.close()`（会带走 server）。
- 抖音分支禁止使用 Obscura，始终走 Argus HTTP 直连；Obscura 仅服务小红书或未来需要渲染的平台。
- 不开 Obscura 时云托管 0.5C1G 可跑；开启时建议 1C1G（镜像约 +70MB 估算、常驻内存约 60MB；实测 obscura 二进制 115MB，最终镜像规格见 evidence「容器规格」段）。
- 冷启动：默认路径不启动浏览器或 Obscura，冷启动不受影响；`ENABLE_OBSCURA=1` 时 entrypoint 先启动 `obscura serve` 并等 CDP 端口就绪，冷启动会变慢。
- 依赖与缓存目录只放 /tmp，请求结束清理；容器不挂持久盘。

## 边界

勾选只在绑定证据存在时成立，完成不等于自己打勾。实现阶段的文件不在 truth 阶段创建；本阶段只允许改 truth.md、tests.md、tasks.md、evidence.md 四个文件。
