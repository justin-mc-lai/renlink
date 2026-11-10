---
slug: l4-session-egress
version: v0.1.0
materials_status: current
test_source: acceptance_criteria
env: container-http
---

# Tests: l4-session-egress

执行入口是 `ops/session_smoke.py`（HTTP 侧）；每个用例独立起容器或独立进程，按环境变量注入池状态。结果写 JSON 到 `docs/beacon/v0.1.0/features/l4-session-egress/evidence/run-*/`。

## 前置条件

```bash
export PARSE_BASE="http://127.0.0.1:18099"
export SESSION_POOL_SOURCE=env
export DOUYIN_COOKIE="sessionid=test; UIFID=test"
export XHS_COOKIE="web_session=test"
export EGRESS_PROXY=""
export RENLINK_SESSION_TTL_S=60
```

失效与出口注入：

```bash
export PARSE_STUB_COOKIE_EXPIRED=douyin
export EGRESS_PROXY=http://127.0.0.1:7890
export RENLINK_SESSION_RELOAD=1
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | contract | `python3 ops/session_smoke.py --case pool-first` | 池内值优先，缺失时 env 兜底，双缺失 503 COOKIE_EXPIRED |
| AC-002 | TC-002 | behavior | `python3 ops/session_smoke.py --case pool-fallback` | cos 读取失败回退 env，source=env，进程不崩 |
| AC-003 | TC-003 | negative | `python3 ops/session_smoke.py --case cookie-expired` | 503 COOKIE_EXPIRED retryable=true，上游重试 ≤1 |
| AC-004 | TC-004 | behavior | `python3 ops/session_smoke.py --case egress-proxy` | 空=direct；非空时 curl_cffi/f2/yt-dlp 都带代理，health 不回显完整串 |
| AC-005 | TC-005 | contract | `python3 ops/session_smoke.py --case health-shape` | 两平台四字段齐全，响应无 cookie 值 |
| AC-006 | TC-006 | negative | `python3 ops/session_smoke.py --case user-cookie` | 400 INVALID_REQUEST，无写用户 cookie 接口 |
| AC-007 | TC-007 | behavior | `python3 ops/session_smoke.py --case refresh-cookie` | 刷新后 last_refresh 更新且 fresh；失败退出码非 0 |
| AC-008 | TC-008 | contract | `python3 ops/session_smoke.py --case freshness` | fresh/expired/missing 三态正确，全程不发上游 |
| AC-009 | TC-009 | behavior | `python3 ops/session_smoke.py --case redaction` | 日志与响应只出现前 4 位前缀，完整串 grep 命中 0 |
| AC-010 | TC-010 | behavior | `python3 ops/session_smoke.py --case pool-cache` | 60s 内只读池一次，RELOAD=1 后读到新值 |

## 用例明细

### TC-001 来源优先级

- 池有记录：get_cookie 返回池值。
- 池不可用且设置 DOUYIN_COOKIE：返回环境变量值。
- 两者都没有：/parse 返回 503 COOKIE_EXPIRED。

### TC-002 池回退

- SESSION_POOL_SOURCE=cos 且 COS 凭证缺失：服务正常启动，/health.platforms.douyin.source=env，/parse 仍可用 env cookie。

### TC-003 失效

- 注入 PARSE_STUB_COOKIE_EXPIRED=douyin。
- 期望：503、error.code=COOKIE_EXPIRED、retryable=true；统计上游请求次数不超过 1。

### TC-004 出口

- EGRESS_PROXY 为空：/health.egress_proxy=direct。
- EGRESS_PROXY=http://127.0.0.1:7890：抓取 curl_cffi 的 proxies、yt-dlp 的 proxy、f2 的代理参数，三处都等于该值；/health.egress_proxy=proxy，不含主机与端口。

### TC-005 健康形状

- 通过判据：platforms.douyin 与 platforms.xhs 各含 cookie_status、last_refresh、source、pool_age_s；顶层含 egress_proxy；响应体不含 cookie 明文。

### TC-006 用户 cookie

- /parse 与 /stage 请求体带 cookie 字段均返回 400 INVALID_REQUEST；代码库中不存在写入用户 cookie 的路由。

### TC-007 刷新脚本

- 在临时池目录执行 ops/refresh_cookie.py，写入后 /health 的 last_refresh 变化且 fresh。
- 失败注入（只读目录）时退出码非 0，池内容不变。

### TC-008 新鲜度

- refreshed_at 在 max_age_s 内：fresh；超期：expired；无记录：missing。
- 通过判据：判定期间上游请求计数为 0。

### TC-009 脱敏

- 通过判据：日志、/health、错误响应中只出现 cookie 前 4 位；完整 cookie 子串 grep 命中 0。

### TC-010 池缓存

- 连续取 10 次 cookie，池读取计数为 1；设置 RENLINK_SESSION_RELOAD=1 后下一次取用读取计数变为 2 且返回新值。
