---
slug: l3-media-delivery
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
---

# Tasks: l3-media-delivery

## Task Ledger

- [x] TASK-001 实现 stage 缓存与 task_id 算法（/parse 成功时 remember）· ac=AC-005,AC-011 · evidence=TC-011
- [x] TASK-002 实现 POST /stage 路由、请求校验与错误码映射 · ac=AC-005,AC-008,AC-012 · evidence=TC-008
- [x] TASK-003 实现下载器：Content-Length 预检、累计字节、200MB/32MB 上限、60s 预算 · ac=AC-004,AC-013 · evidence=TC-004
- [x] TASK-004 实现图片转码：webp/needs_transcode → JPEG（Pillow）· ac=AC-003 · evidence=TC-003
- [x] TASK-005 实现 store 客户端：local 与 COS 两种模式、临时密钥、fileID 拼接 · ac=AC-001,AC-002,AC-006 · evidence=TC-006
- [x] TASK-006 实现 cloudID 幂等缓存（platform:content_id:index）· ac=AC-007 · evidence=TC-007
- [x] TASK-007 实现临时文件生命周期与 finally 清理 · ac=AC-010 · evidence=TC-010
- [x] TASK-008 编写 ops/stage_smoke.py 覆盖 TC-001..TC-014 并输出 evidence JSON · ac=ALL · evidence=TC-014
- [x] TASK-009 本地真跑：起服务 → 真实 /parse → 1 视频 + 1 图 → fileID 可读，登记 evidence.md · ac=AC-014 · evidence=TC-014
- [x] TASK-010 校验 package gates（truth review + freeze + integrity）· ac=GATES · evidence=GATES
- [x] TASK-011 补充 tests/test_stage.py pytest 用例（成功/过期/超限/未配置存储/幂等/临时文件清理）· ac=AC-001,AC-004,AC-005,AC-006,AC-007,AC-010 · evidence=TC-001,TC-004,TC-005,TC-006,TC-007,TC-010

Evidence: evidence/run-20261109-0030/ plus evidence.md. TASK-009's image half is
explicitly limited in evidence.md; the real video half and the /stage behavior
are fully exercised.

## Boundary

Checkboxes are AC-bound ledgers. `[x]` is valid only when the bound evidence file exists (completion ≠ self-tick).
