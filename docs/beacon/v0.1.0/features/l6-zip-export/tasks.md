---
slug: l6-zip-export
version: v0.1.0
materials_status: stale
task_source: acceptance_criteria
---

# Tasks: l6-zip-export

## Task Ledger

- [ ] TASK-001 在 `container/app/` 增加 `routes_zip.py` 与 `zip_export.py`：请求校验、task manifest 解析、index 归一与错误码映射 · owner=后端 · deps=l3 stage_cache · ac=AC-004,AC-009,AC-011 · evidence=TC-004,TC-009,TC-011
- [ ] TASK-002 选图逻辑：只取 `type=image` 且 stage_cache 有对象记录且 `store.exists` 为真的项；未转存跳过，全部跳过返回 400 · owner=后端 · deps=TASK-001 · ac=AC-011 · evidence=TC-011
- [ ] TASK-003 数量与体积上限：`ZIP_MAX_IMAGES`=50、`ZIP_MAX_BYTES`=209715200，显式请求与已转存集双重校验 · owner=后端 · deps=TASK-002 · ac=AC-006,AC-007 · evidence=TC-006,TC-007
- [ ] TASK-004 存储读回能力：local 直接读文件，cos 签名 GET；缺 bucket、缺凭证、local 目录不可读写三种情形都在选图前统一抛 ZIP_NOT_READY · owner=后端 · deps=l3 stage_store · ac=AC-005 · evidence=TC-005
- [ ] TASK-005 确定性打包：index 升序、条目名 `{index:03d}.{ext}`、固定时间戳 1980-01-01、ZIP_STORED、无目录条目 · owner=后端 · deps=TASK-002 · ac=AC-014 · evidence=TC-014
- [ ] TASK-006 上传 zip 到 `l6/<task_id>/<index_set_hash>.zip` 并拼 fileID（local/cos 两模式） · owner=后端 · deps=TASK-004,TASK-005 · ac=AC-001,AC-014 · evidence=TC-001,TC-014
- [ ] TASK-007 幂等缓存：键 `zip:v1:<task_id>:<升序 index 逗号串>`、TTL 600s、命中校验对象存在、同键单锁串行 · owner=后端 · deps=TASK-006 · ac=AC-003 · evidence=TC-003
- [ ] TASK-008 60s 预算与临时文件：`/tmp/renlink-zip-*`、finally 清理、超时 504 TIMEOUT · owner=后端 · deps=TASK-005,TASK-006 · ac=AC-012,AC-013 · evidence=TC-012,TC-013
- [ ] TASK-009 响应形状：成功仅四字段、≤1024000 字节、失败无 fileID 且不回 `cloud://` · owner=后端 · deps=TASK-001,TASK-006 · ac=AC-001,AC-010 · evidence=TC-001,TC-010
- [ ] TASK-010 测试注入面：`ZIP_FAKE_DELAY_MS`、`ZIP_FAULT_INJECT=read|write|upload`（read=源对象读回失败，write=本地 zip 落盘失败，upload=对象存储写入失败）、`ZIP_CACHE_TTL_S=0`，仅 local 生效 · owner=后端 · deps=TASK-004,TASK-007,TASK-008 · ac=AC-008,AC-013,AC-014 · evidence=TC-008,TC-013,TC-014
- [ ] TASK-011 编写 `ops/zip_smoke.py`（--verify 与 16 个 case），按 TC-001～TC-014、TC-016 输出 evidence JSON · owner=后端 · deps=TASK-001～TASK-010 · ac=ALL · evidence=TC-001～TC-016
- [ ] TASK-012 补充 `tests/test_zip.py`：成功/子集/幂等/过期/未就绪/超限/失败/非法/响应形状/只打已转存/临时文件/超时/稳定性 · owner=后端 · deps=TASK-001～TASK-010 · ac=ALL · evidence=TC-001～TC-014,TC-016
- [ ] TASK-013 前端 `createZip` 改为传 task_id 与可选的 indexes 并从 `/zip` 读 `fileID`；task_id 复用与 /stage 同一算法 · owner=前端 · deps=TASK-001 · ac=AC-001,AC-015 · evidence=TC-015
- [ ] TASK-014 前端 ZIP 按钮串 `wx.cloud.downloadFile` → `wx.shareFileMessage`，PC 降级 `wx.saveFileToDisk`，取消/失败/错误码文案表落地 · owner=前端 · deps=TASK-013 · ac=AC-015 · evidence=TC-015
- [ ] TASK-015 端侧真机验收：手机转发到文件传输助手、电脑存盘、失败与取消文案，留截图/录屏 · owner=前端+验收 · deps=TASK-014 · ac=AC-015 · evidence=TC-015
- [ ] TASK-016 本地 curl 复跑 TC-001～TC-014、TC-016（`STAGE_STORE=local`），登记 evidence 与 BLOCKED 项 · owner=后端 · deps=TASK-011,TASK-012 · ac=ALL · evidence=TC-001～TC-016
- [ ] TASK-017 独立验收：`beacon-go gate integrity --feature l6-zip-export --evaluator 验收员`（由验收员执行，作者不自证） · owner=验收 · deps=TASK-016 · ac=GATES · evidence=GATES

## 依赖顺序

```text
TASK-001 → TASK-002 → TASK-003
              ↘ TASK-005 → TASK-006 → TASK-007 → TASK-010
TASK-004 ─────↗                    ↘ TASK-008
TASK-006 → TASK-009
TASK-011, TASK-012 覆盖全部后端 AC
TASK-013 → TASK-014 → TASK-015（前端与真机）
TASK-016 → TASK-017（验收，独立执行）
```

## Boundary

Checkboxes are AC-bound ledgers. `[x]` is valid only when the bound evidence file exists (completion ≠ self-tick). 本湖 truth 冻结阶段所有 TASK 保持 `[ ]`；冻结后先做后端实现，前端 TASK-013～015 需 l5 走变更后执行。
