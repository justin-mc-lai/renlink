# Evidence Index: l4-session-egress

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | frozen | truth |
| tests | test_truth | tests.md | current | qa |
| tasks | support_advisory | tasks.md | current | implement |
| contract | support_advisory | truth.md 的接口契约章节 | frozen | implement |

## 按 AC 的证据槽位

执行器为 session_smoke.py，每个 TC 落一个 JSON。HTTP 轮次为 run-20261109-0047；真实 env 模式与刷新轮次为 run-20261109-0048-real；pytest 结果也落在后者。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | case-TC-001.json | 本地池记录优先、env 兜底、双缺失 503 COOKIE_EXPIRED | collected |
| AC-002 | case-TC-002.json | SESSION_POOL_SOURCE=cos 无 bucket，health 的 source=env 且不崩 | collected |
| AC-003 | case-TC-003.json、cookie-expired.json | 注入 PARSE_STUB_COOKIE_EXPIRED=douyin，503 COOKIE_EXPIRED retryable=true，未进上游 | collected |
| AC-004 | case-TC-004.json、pytest-output.txt | health 的 direct 与 proxy 两态；pytest 校验 curl_cffi、f2、yt-dlp 三处注入 | collected |
| AC-005 | case-TC-005.json、health-env.json | 两平台四字段与顶层 egress_proxy，响应无 cookie 值 | collected |
| AC-006 | case-TC-006.json | parse 与 stage 带 cookie 均 400 INVALID_REQUEST；openapi 无写 cookie 路由 | collected |
| AC-007 | case-TC-007.json、refresh-stdout.txt、health-before-refresh.json、health-after-refresh.json | 真浏览器刷新写池，health 的 last_refresh 更新；写失败退出非 0 且池文件不变 | collected |
| AC-008 | case-TC-008.json | fresh 与 expired 与 missing 三态由 refreshed_at 和 max_age_s 判定，仅走 health | collected |
| AC-009 | case-TC-009.json | health、错误响应、服务日志完整 cookie 命中 0，日志只出现前 4 位前缀 | collected |
| AC-010 | case-TC-010.json、pytest-output.txt | 60s 窗口内 10 次 health 只读一次；TTL 到期后读到新值；RELOAD 由 pytest 覆盖 | collected |

## 实测回执

真实 env 模式 health（run-20261109-0048-real 的 health-env.json，来源为本机 cookies.env）：

```json
{"platforms":{"douyin":{"cookie_status":"fresh","last_refresh":"","source":"env","pool_age_s":null},"xhs":{"cookie_status":"fresh","last_refresh":"","source":"env","pool_age_s":null}},"egress_proxy":"direct"}
```

PARSE_STUB_COOKIE_EXPIRED=douyin 实测（cookie-expired.status 为 503）：

```json
{"ok":false,"error":{"code":"COOKIE_EXPIRED","message":"运营方 cookie 失效，请运营刷新后重试","retryable":true},"items":[],"resolved_url":"","elapsed_ms":0}
```

同一轮真实 cookie 下解析一条抖音视频（parse-real.json）：HTTP 200、platform=douyin、content_type=video、item_count=1、elapsed_ms=523，说明 l4 接缝没有破坏 l1 解析路径。

真实浏览器刷新 refresh_cookie.py 退出码 0，stdout 只有平台与 cookie 数量，不打印值：

```text
douyin: ok (34 cookies)
xhs: ok (17 cookies)
wrote pool (operator pool directory)
wrote cookies.env
```

刷新前后同一进程 health（TTL=1s）变化：

```text
before: douyin 与 xhs last_refresh 为空串, source=env, pool_age_s=null
after:  douyin 与 xhs last_refresh=2026-11-09T00:48:09+08:00, source=env, pool_age_s=1
```

## 测试结果

- session_smoke.py：TC-001..TC-010 全部 PASS（run-20261109-0047 的 summary.json）。
- pytest tests：23 passed 与 0 failed（run-20261109-0048-real 的 pytest-output.txt）。
- 脱敏检查：对证据目录 grep 两个平台完整 cookie 与 43 个 cookie token，命中数 0。

## 已知限制

- COS 池读取已实现（按 sessions 前缀读取平台 JSON、静态密钥或容器开放接口），本机无真实 bucket 与临时密钥，未做真实 COS 读取验收；COS 失败回退 env 已实测。DB 模式用 SQLite 实测，MySQL 只在代码路径保留，未接真实库。
- EGRESS_PROXY 的实际公网转发未用真实代理验收；三处客户端参数注入由 pytest 断言，health 只报 direct 或 proxy 模式，不回显代理串。
- env 模式没有池时间戳时 last_refresh 为空串、pool_age_s 为 null，这是本地兜底的预期形状；刷新写入本地池镜像后两者才有值。

## Boundary

evidence.md 只登记证据索引与实测输出，不写 QA 判定、gate truth 或 release readiness。
