---
slug: l1-parser-core
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
depends_on: l2-xhs-images, l4-session-egress
---

# Tasks: l1-parser-core

## 任务台账

- [ ] TASK-001 解析路由与契约模型：FastAPI 挂 POST /parse 与 GET /health，pydantic 定义 ParseRequest、ParseItem、ParseResult、ErrorEnvelope，字段名与 truth.md 接口契约逐字一致 · ac=AC-011
- [ ] TASK-002 错误信封与错误码：实现 INVALID_URL、INVALID_REQUEST、UNSUPPORTED_PLATFORM、SHORTLINK_FAIL、COOKIE_EXPIRED、PARSE_FAILED、TIMEOUT、RATE_LIMITED 八个码，统一 http 状态与 retryable · ac=AC-005
- [ ] TASK-003 域名白名单与输入校验：只放行 douyin.com、v.douyin.com、xhslink.com、xiaohongshu.com 及其子域；url 长度上限 2048；请求体出现 cookie 字段直接拒绝 · ac=AC-013
- [ ] TASK-004 短链展开：3 跳上限、HEAD 优先、失败映射 SHORTLINK_FAIL，成功后把 resolved_url 交给平台分支 · ac=AC-004
- [ ] TASK-005 f2 抖音分支：DouyinHandler 取 aweme_id，视频走 yt-dlp DouyinIE 或 f2 的播放地址，图文读 PostDetailFilter.images，全程不触发下载 · ac=AC-001
- [ ] TASK-006 抖音图文条目归一：images 逐项转 index、type=image、remoteUrl、ext，封面与宽高可空；item_count 取实际条目数 · ac=AC-002
- [ ] TASK-007 小红书视频分支：yt-dlp XiaoHongShuIE 取播放地址与标题，items 固定 1 项 · ac=AC-003
- [ ] TASK-008 小红书图文路由接 l2：调用 l2 的 parse_note，把返回的 imageList 原图与 xsec_token 归一成 items，needs_transcode=true；本湖不实现 __INITIAL_STATE__ 解析 · ac=AC-011
- [ ] TASK-009 cookie 池接缝 l4：get_cookie(platform) 取运营方 cookie，捕获 CookieExpired 映射 503 COOKIE_EXPIRED，日志脱敏 · ac=AC-005
- [ ] TASK-010 超时与预算：解析整体 12s 硬超时，返回 504 TIMEOUT；慢上游可注入 PARSE_UPSTREAM_DELAY_MS 用于测试 · ac=AC-009
- [ ] TASK-011 体积与条目上限：items 最多 100 项，截断时置 truncated=true；序列化后自检字节数不大于 1024000 · ac=AC-010
- [ ] TASK-012 零落盘自检：解析链路不使用临时文件 API，代码评审加测试用 /tmp 快照对比 · ac=AC-012
- [ ] TASK-013 健康探针：GET /health 汇总两平台 cookie 新鲜度、上次刷新时间、出口代理模式 · ac=AC-014
- [ ] TASK-014 容器镜像依赖：Python 3.11、FastAPI、yt-dlp、f2 0.0.1.7、Node20、pyexecjs，镜像内自检 f2 可 import · ac=AC-001
- [ ] TASK-015 ops/smoke.py：实现 18 个用例，读环境变量样本，输出 JSON 证据；缺样本时打印 BLOCKED 并以退出码 3 结束 · ac=AC-001
- [ ] TASK-016 样本采集登记：运营采集 8 个槽位，回填采集日期与页面条目数，样本只留在运营侧 · ac=AC-004
- [ ] TASK-017 打包验收：冻结后按 tests.md 跑 18 个用例，真实样本全绿才算本湖通过 · ac=AC-014

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

## 交付物清单

| 路径 | 内容 |
|------|------|
| container/app/main.py | 应用装配与 /health |
| container/app/routes_parse.py | /parse 路由与错误映射 |
| container/app/contract.py | 请求响应模型与截断规则 |
| container/app/errors.py | 错误码常量与信封 |
| container/app/parsers/shortlink.py | 短链展开 |
| container/app/parsers/douyin.py | f2 抖音视频与图文分支 |
| container/app/parsers/xhs.py | xhs 视频分支与 l2 图文路由 |
| container/app/session_bridge.py | l4 cookie 池接缝与脱敏 |
| contract/parse_response.schema.json | 响应 schema |
| ops/smoke.py | 18 个用例的执行器 |

## 边界

勾选只在绑定证据存在时成立，完成不等于自己打勾。实现阶段的文件不在 truth 阶段创建；本阶段只允许改 truth.md、tests.md、tasks.md、evidence.md 四个文件。
