---
slug: l2-xhs-images
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
---

# Tasks: l2-xhs-images

## Task Ledger

- [ ] TASK-001 新建 `container/app/parsers/xhs_note.py`：抓取规范笔记页、定位 window.__INITIAL_STATE__、按 note.noteDetailMap 优先、noteData.data.noteData 回退定位 note 并解析 imageList · owner=后端 · deps=l1 xhs 接缝 · ac=AC-001,AC-004,AC-005 · evidence=TC-001,TC-006,TC-007,TC-008,TC-009
- [ ] TASK-002 原图选择与顺序：urlDefault → infoList WB_DFT → CRD_WM_WEBP，全部缺失跳过；两种页面结构下都保持 imageList 顺序，不出现缩略地址 · owner=后端 · deps=TASK-001 · ac=AC-002 · evidence=TC-002,TC-003
- [ ] TASK-003 直连短链防御：xhslink.com 与 xhslink.cn 最多 3 跳、校验最终主机与规范路径，失败返回 PARSE_FAILED · owner=后端 · deps=TASK-001 · ac=AC-003 · evidence=TC-013
- [ ] TASK-004 xsec_token 提取：URL query → note.xsecToken → state 顶层；缺失抛 NEED_XSEC_TOKEN · owner=后端 · deps=TASK-001 · ac=AC-006 · evidence=TC-004,TC-005
- [ ] TASK-005 错误码注册：`container/app/errors.py` 的 ERROR_SPECS 增加 NEED_XSEC_TOKEN(422, retryable=true)，既有码不动 · owner=后端 · deps=TASK-004 · ac=AC-008 · evidence=TC-005
- [ ] TASK-006 接入 l1 xhs 分支：xhs.py 默认注册 `xhs_note.parse_note`；新增仅测试开关 `PARSE_XHS_SKIP_YTDLP`（默认 0）跳过 yt-dlp；不改 /parse 字段与归一化 · owner=后端 · deps=TASK-001 · ac=AC-007,AC-011 · evidence=TC-001,TC-010,TC-011
- [ ] TASK-007 解析缓存：键 `xhs:note:v1:<note_id>:<sha256(xsec_token)[:12]>`、TTL `XHS_NOTE_CACHE_TTL_S`、只缓存成功结果 · owner=后端 · deps=TASK-001,TASK-004 · ac=AC-009 · evidence=TC-012
- [ ] TASK-008 观测：`event=xhs_note_parse` 结构化日志与 `xhs_note_*` 进程内计数器，token 只写 present/missing · owner=后端 · deps=TASK-001,TASK-007 · ac=AC-010 · evidence=TC-012
- [ ] TASK-009 预算与上限：`XHS_NOTE_TIMEOUT_S`=8、`XHS_NOTE_MAX_BYTES`=5242880、`XHS_NOTE_MAX_HOPS`=3 · owner=后端 · deps=TASK-001 · ac=AC-012 · evidence=TC-016,TC-017
- [ ] TASK-010 测试桩：`XHS_NOTE_HTTP_STUB` 读取 URL→status/headers/body_file/location/delay_ms，未覆盖的 URL 判 PARSE_FAILED，仅测试使用 · owner=后端 · deps=TASK-001,TASK-003 · ac=ALL · evidence=TC-001 至 TC-017
- [ ] TASK-011 编写 `ops/xhs_note_smoke.py` 与 `tests/test_xhs_note.py`：覆盖 14 个构造用例与直连短链用例 · owner=后端 · deps=TASK-001 至 TASK-010 · ac=ALL · evidence=TC-001 至 TC-017
- [ ] TASK-012 本地 curl 复跑 TC-001 至 TC-017，按 evidence.md 落盘并登记 BLOCKED 项 · owner=后端 · deps=TASK-011 · ac=ALL · evidence=TC-001 至 TC-018
- [ ] TASK-013 真实样本采集：10 条小红书图文 + 1 条图文短链，写入样本登记后复跑 TC-018 · owner=后端+验收 · deps=TASK-012 · ac=AC-001,AC-003 · evidence=TC-018
- [ ] TASK-014 前端联调确认：小程序图文页按 items 顺序展示、needs_transcode 透传给 l3，不改 UI 结构 · owner=前端 · deps=l5 页面与 TASK-006 · ac=AC-007 · evidence=TC-015
- [ ] TASK-015 独立验收：`beacon-go gate integrity --feature l2-xhs-images --evaluator 验收员`（由验收员执行，作者不自证） · owner=验收 · deps=TASK-012 · ac=GATES · evidence=GATES

## 依赖顺序

```text
TASK-001 → TASK-002, TASK-003, TASK-004 → TASK-005
TASK-001 → TASK-006
TASK-001 → TASK-007 → TASK-008
TASK-001 → TASK-009
TASK-010 → TASK-011 → TASK-012 → TASK-015
TASK-012 → TASK-013（真实样本）
TASK-006 → TASK-014（前端联调）
```

## Boundary

Checkboxes are AC-bound ledgers. `[x]` is valid only when the bound evidence file exists (completion ≠ self-tick). 本湖 truth 冻结阶段所有 TASK 保持 `[ ]`；l1 的 xhs.py 只做注册与测试开关两处接入，不改 l1 冻结正文。
