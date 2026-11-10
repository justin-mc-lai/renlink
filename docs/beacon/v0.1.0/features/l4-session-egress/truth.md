---
slug: l4-session-egress
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
  truth: docs/beacon/v0.1.0/features/l4-session-egress/truth.md
  tests: docs/beacon/v0.1.0/features/l4-session-egress/tests.md
  tasks: docs/beacon/v0.1.0/features/l4-session-egress/tasks.md
  evidence: docs/beacon/v0.1.0/features/l4-session-egress/evidence.md
---

# Requirement Truth: l4-session-egress

## 人话

解析和下载只用运营方自己的抖音/小红书 cookie，放在 COS 或数据库的池里，容器按平台取当前那一份；cookie 过期就明确回 COOKIE_EXPIRED，不偷偷重试把上游刷爆；所有出站请求走 EGRESS_PROXY 这一个开关，默认直连；/health 让人一眼看到两个平台的新鲜度、上次刷新时间和当前出口。用户自己的 cookie 一律不收。

## User Intent

反爬能不能扛住，取决于登录态和出口。运营方要能自己刷新 cookie、自己切代理，并且在失效时立刻看见，而不是等用户报「保存失败」。这一湖把「用哪份 cookie、从哪出去、还新鲜吗」变成可观察、可更换的配置，同时守住一条红线：只做运营方池，不碰用户凭据。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
program: lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
language: zh
source: user_intent
utterance: "l4：运营方 cookie 池 + 可切换出口 + 健康上报"
goal: "解析与下载统一从运营方 cookie 池取登录态，cookie 失效返回 COOKIE_EXPIRED 且不静默重试；EGRESS_PROXY 一个开关切换出口并写入 curl_cffi/f2/yt-dlp；/health 报两平台新鲜度、上次刷新时间与出口模式"
non_goals: "接收或存储用户 cookie；服务端自动过滑块；多账号轮询调度；代理池自动选优；自建 VPS；修改 l1 解析逻辑"
constraints: "cookie 只来自 COS/DB 运营方池，DOUYIN_COOKIE/XHS_COOKIE 仅本地兜底；失效映射 COOKIE_EXPIRED，禁止静默循环重试；EGRESS_PROXY 默认空=直连；/health 不泄露 cookie 值；日志只允许前 4 位前缀"
scope_mode: lake
```

## 目标

- 让「用哪份 cookie」有唯一来源：池优先，环境变量兜底，缺失即失效，调用方拿到固定错误码。
- 让失效可观察：/health 直接给出两个平台的新鲜度与上次刷新时间，运营方刷新后立刻能看到变化。
- 让出口可切换：一个 EGRESS_PROXY 环境变量同时作用于 curl_cffi、f2、yt-dlp，不用改代码。
- 让刷新可操作：ops/refresh_cookie.py 写池，写成功才算成功。
- 让凭据不外泄：任何响应、日志、错误消息都不出现完整 cookie。

## 非目标

- 不接收、不转发、不存储用户上传的 cookie。
- 不做服务端自动过滑块、打码、验证码识别。
- 不做多账号轮询、按成功率自动切换账号。
- 不做代理池自动选优、测速、故障转移。
- 不自建 VPS 替代云托管。
- 不修改 l1 的解析分支与响应契约，只填 session_bridge 这一层接缝。
- 不做数据库建表与迁移：DB 模式只读约定的 JSON 记录。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | cookie 来源：COS/DB 的运营方池 | SESSION_POOL_SOURCE=cos 读 COS 对象 sessions/<platform>.json；=env 读 DOUYIN_COOKIE/XHS_COOKIE；默认 cos 失败自动回退 env | AC-001、AC-002 |
| C2 | 本地兜底 | 池不可用时读 DOUYIN_COOKIE/XHS_COOKIE；两处都没有视为 missing | AC-001、AC-005 |
| C3 | 失效返回 COOKIE_EXPIRED | CookieExpired 由路由映射 503 COOKIE_EXPIRED、retryable=true；不做静默循环重试 | AC-003 |
| C4 | 出口 EGRESS_PROXY | 空值直连；非空时 curl_cffi 的 proxies、yt-dlp 的 proxy、f2 的请求代理都取它 | AC-004 |
| C5 | /health 上报 | 两平台 cookie_status、last_refresh、source、pool_age_s 与 egress_proxy | AC-005 |
| C6 | 禁止收用户 cookie | 请求体出现 cookie 字段返回 400 INVALID_REQUEST；不提供写 cookie 的接口 | AC-006 |
| C7 | 刷新脚本 | ops/refresh_cookie.py 写池，成功退出码 0 且 /health 变 fresh；失败退出码非 0 且不写半份 | AC-007 |
| C8 | 新鲜度判定不发上游 | 只按池内 refreshed_at 与 max_age_s 计算 | AC-008 |
| C9 | 脱敏 | 日志、/health、错误消息只允许前 4 位前缀加 *** | AC-009 |
| C10 | 读取成本 | 池读取进程内缓存 60s，刷新后可强制重载 | AC-010 |

## Alignment Surface

本湖是登录态与出口的地基：l1 的解析与 l3 的下载都通过它取 cookie、走同一个出口，但只有 l1 真正消费 cookie；l3 只继承出口。凡是解析、转存、页面、打包的能力都不在本湖范围。

## Open Questions

| Q ID | Question | Recommendation | Status | Answer | Source |
|------|----------|----------------|--------|--------|--------|
| Q1 | 谁、什么问题、什么算完成？ | 运营方能刷新 cookie、切换出口，并在失败时看到明确错误 | answered | 运营方刷新池后 /health 变 fresh；cookie 失效返回 COOKIE_EXPIRED；改 EGRESS_PROXY 后上游请求走新出口 | MausBot |
| Q2 | DB 模式的表结构由谁定？本轮不买 MySQL | 只读约定 JSON，不建表 | answered | DB 模式读一条记录：platform、cookie、refreshed_at、max_age_s；表名由 SESSION_DB_TABLE 指定，本轮不做迁移 | MausBot |
| Q3 | cookie 过期怎么判，要不要真实请求探测？ | 只按 refreshed_at 与 max_age_s 判，避免刷上游 | answered | refreshed_at + max_age_s（默认 86400s）内为 fresh，超期为 expired，缺失为 missing；不做探测请求 | MausBot |

## Intent Coverage

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | 目标：池优先、环境变量兜底、缺失即失效 | tests.md TC-001 |
| AC-002 | 约束 C1：池来源可配、加载失败回退 | tests.md TC-002 |
| AC-003 | 约束 C3：失效返回 COOKIE_EXPIRED，不静默重试 | tests.md TC-003 |
| AC-004 | 约束 C4：EGRESS_PROXY 写入 curl_cffi/f2/yt-dlp | tests.md TC-004 |
| AC-005 | 约束 C5：/health 上报新鲜度与出口 | tests.md TC-005 |
| AC-006 | 约束 C6：禁止收用户 cookie | tests.md TC-006 |
| AC-007 | 约束 C7：refresh_cookie.py 写池 | tests.md TC-007 |
| AC-008 | 约束 C8：新鲜度判定不发上游 | tests.md TC-008 |
| AC-009 | 约束 C9：脱敏 | tests.md TC-009 |
| AC-010 | 约束 C10：池读取缓存与强制重载 | tests.md TC-010 |

## Acceptance Criteria

| AC ID | Criterion |
|-------|-----------|
| AC-001 | 池内有 douyin 记录时 get_cookie("douyin") 返回池内值；池不可用且设置 DOUYIN_COOKIE 时返回环境变量值；池与环境变量都没有时抛 CookieExpired，路由返回 HTTP 503、error.code=COOKIE_EXPIRED |
| AC-002 | SESSION_POOL_SOURCE=cos 时从 COS 读 sessions/douyin.json 与 sessions/xhs.json；读取失败不抛未捕获异常，按 env 兜底并把 /health 的 source 标为 env；SESSION_POOL_SOURCE=env 时直接读环境变量 |
| AC-003 | cookie 池内 refreshed_at 超期时 /parse 返回 HTTP 503、ok=false、error.code=COOKIE_EXPIRED、retryable=true；测试注入 PARSE_STUB_COOKIE_EXPIRED=douyin 时同样返回 503 COOKIE_EXPIRED；单请求内上游重试次数不超过 1 |
| AC-004 | EGRESS_PROXY 为空时 /health 的 egress_proxy=direct；设为 http://127.0.0.1:7890 时 curl_cffi、f2、yt-dlp 三处请求都带该代理，/health 只回 proxy，不回显完整代理串 |
| AC-005 | GET /health 返回 200 与 platforms.douyin、platforms.xhs，各含 cookie_status（fresh/expired/missing）、last_refresh、source、pool_age_s，顶层含 egress_proxy；响应体不含任何 cookie 值 |
| AC-006 | POST /parse 与 POST /stage 请求体出现 cookie 字段时均返回 HTTP 400、ok=false、error.code=INVALID_REQUEST；系统中不存在写入用户 cookie 的接口 |
| AC-007 | 运行 ops/refresh_cookie.py 成功写入池后，/health 的 last_refresh 更新且 cookie_status=fresh；写入失败时退出码非 0，池文件保持原状不出现半份 |
| AC-008 | 池内 refreshed_at 在 max_age_s 内时 cookie_status=fresh，超期时为 expired，无记录时为 missing；该判定过程不发起任何上游请求 |
| AC-009 | 日志、/health、错误消息中的 cookie 只出现前 4 位前缀，其余为 ***；对完整 cookie 子串的 grep 命中数为 0 |
| AC-010 | 同一进程内 60s 内连续取 cookie 只读池一次；设置 RENLINK_SESSION_RELOAD=1 后下一次取用会重新读池并反映新值 |

## 接口契约

### session_bridge 接口

```python
get_cookie(platform: str) -> str          # 返回 CookieHeader；失效抛 CookieExpired
cookie_status(platform: str) -> str       # fresh | expired | missing
last_refresh(platform: str) -> str        # ISO8601 字符串，未知为空串
pool_source(platform: str) -> str         # cos | db | env | missing
```

### 池记录格式

```json
{"platform": "douyin", "cookie": "sessionid=...; UIFID=...", "refreshed_at": "2026-11-08T10:00:00+08:00", "max_age_s": 86400}
```

- COS 对象键：sessions/douyin.json、sessions/xhs.json。
- DB 模式：按 SESSION_DB_TABLE 指定的表读同名字段的一条记录。
- 池读取失败按 env 兜底，不阻断服务启动。

### GET /health

```json
{
  "ok": true,
  "version": "v0.1.0",
  "platforms": {
    "douyin": {"cookie_status": "fresh", "last_refresh": "2026-11-08T10:00:00+08:00", "source": "cos", "pool_age_s": 3600},
    "xhs": {"cookie_status": "expired", "last_refresh": "2026-11-05T10:00:00+08:00", "source": "env", "pool_age_s": 345600}
  },
  "egress_proxy": "proxy"
}
```

### 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| SESSION_POOL_SOURCE | cos | cos、db、env |
| SESSION_COS_PREFIX | sessions/ | 池对象前缀 |
| SESSION_DB_TABLE | renlink_sessions | DB 模式表名 |
| DOUYIN_COOKIE | 空 | 本地兜底 |
| XHS_COOKIE | 空 | 本地兜底 |
| EGRESS_PROXY | 空 | 空=直连 |
| RENLINK_SESSION_TTL_S | 60 | 池读取进程内缓存 |
| RENLINK_SESSION_RELOAD | 0 | 1 时下次取用强制重载 |

## 本地验收方式

```bash
# 1. env 模式起服务
SESSION_POOL_SOURCE=env DOUYIN_COOKIE="sessionid=test; UIFID=test" \
  XHS_COOKIE="web_session=test" EGRESS_PROXY= \
  PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099

# 2. 健康探针
curl -sS localhost:18099/health | jq '.platforms, .egress_proxy'

# 3. 失效路径
PARSE_STUB_COOKIE_EXPIRED=douyin uvicorn app.main:app --port 18099
curl -sS -X POST localhost:18099/parse -H 'content-type: application/json' \
  -d '{"url":"'$DY_VIDEO_1'"}' | jq '.error.code'
```

## 依赖与接缝

| 依赖 | 方向 | 接缝定义 | 本湖责任 |
|------|------|----------|----------|
| l1-parser-core | l1 调 l4 | get_cookie(platform) 返回 CookieHeader，失效抛 CookieExpired | 池、新鲜度、脱敏、出口 |
| l3-media-delivery | l3 继承出口 | 下载请求只读 EGRESS_PROXY，不读 cookie | 提供统一出口配置 |
| COS | l4 读池 | 临时密钥与 l3 同一套容器开放接口 | 读 sessions/<platform>.json |
| ops/refresh_cookie.py | 运营方调 | 写池与更新 refreshed_at | 成功/失败可判定 |
