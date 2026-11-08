---
slug: l4-session-egress
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
---

# Tasks: l4-session-egress

## Task Ledger

- [x] TASK-001 实现池读取：SESSION_POOL_SOURCE=cos/db/env，COS 对象与 DB 记录格式 · ac=AC-001,AC-002 · evidence=TC-001,TC-002
- [x] TASK-002 实现 env 兜底与 CookieExpired 映射，清理静默重试 · ac=AC-001,AC-003 · evidence=TC-001,TC-003
- [x] TASK-003 实现新鲜度判定（refreshed_at + max_age_s）与 60s 读取缓存 · ac=AC-008,AC-010 · evidence=TC-008,TC-010
- [x] TASK-004 实现 EGRESS_PROXY 注入 curl_cffi/f2/yt-dlp 三个客户端 · ac=AC-004 · evidence=TC-004
- [x] TASK-005 扩展 health：两平台 cookie_status/last_refresh/source/pool_age_s 与出口模式 · ac=AC-005 · evidence=TC-005
- [x] TASK-006 实现脱敏与禁止用户 cookie 的请求校验 · ac=AC-006,AC-009 · evidence=TC-006,TC-009
- [x] TASK-007 对齐 refresh_cookie.py：写池、更新 refreshed_at、失败非 0 · ac=AC-007 · evidence=TC-007
- [x] TASK-008 编写 session_smoke.py 覆盖 TC-001..TC-010 并输出 evidence JSON · ac=ALL · evidence=TC-010
- [x] TASK-009 本地真跑：env 模式起服务，health 与 COOKIE_EXPIRED 两条路径留证，登记 evidence.md · ac=AC-005,AC-003 · evidence=TC-005,TC-003
- [x] TASK-010 校验 package gates（truth review + freeze + integrity）· ac=GATES · evidence=GATES

## Boundary

Checkboxes are AC-bound ledgers. `[x]` is valid only when the bound evidence file exists (completion ≠ self-tick).
