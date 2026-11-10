# Evidence Index: l6-zip-export

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | frozen/Freeze | truth |
| tests | test_truth | tests.md | frozen/Freeze | qa |
| tasks | support_advisory | tasks.md | frozen/Freeze | implement |
| contract | support_advisory | truth.md 的「接口契约」「打包与存储规则」章节 | frozen/Freeze | implement |

## 按 AC 的证据槽位

证据在实现阶段由 zip 打包执行器产出，统一落在本湖 evidence 目录，文件名与用例 ID 对齐。当前处于 truth 阶段，所有执行产物尚未开始，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | case-zip-all.json、zip-all.zip | local 存储全量打包后读回 | 未产生 |
| AC-002 | case-zip-subset.json、zip-subset.zip | 前置样本 ≥8 张，传 [7,1,7]，断言条目 001/007；样本不足记 BLOCKED 并记录 N | 未产生 |
| AC-003 | case-zip-idempotent.json | 两次请求并对比对象文件数 | 未产生 |
| AC-004 | case-zip-expired.json | 未知 task_id 与 TTL=1 过期 | 未产生 |
| AC-005 | case-zip-not-ready-a.json、case-zip-not-ready-b.json、case-zip-not-ready-c.json | (a) cos 无 bucket、(b) cos 无凭证、(c) local 目录不可写 | 未产生 |
| AC-006 | case-zip-too-many.json | 数量上限注入为 1 后请求两张 | 未产生 |
| AC-007 | case-zip-too-large.json | 体积上限注入为 1 后请求一张 | 未产生 |
| AC-008 | case-zip-failed-read.json、case-zip-failed-write.json、case-zip-failed-upload.json | 故障注入 read、write、upload | 未产生 |
| AC-009 | case-zip-invalid.json | 八类非法输入与视频 index | 未产生 |
| AC-010 | case-zip-shape.json | 响应字节数与键集合 | 未产生 |
| AC-011 | case-zip-staged-only.json | 混合已转存与未转存，另测全未转存 | 未产生 |
| AC-012 | case-zip-tmp-clean.txt | 成功与失败后查看临时文件数 | 未产生 |
| AC-013 | case-zip-timeout.json | 超时预算设为 1 秒并注入延迟 | 未产生 |
| AC-014 | case-zip-stable.json、zip-stable-1.zip、zip-stable-2.zip | 关闭缓存连打两次 | 未产生 |
| AC-015 | device-share-phone.png、device-save-pc.png | 体验版真机转发与电脑存盘 | 未产生 |
| AC-016 | case-zip-boundary.txt | 三湖 git diff 与 cookie 字段 | 未产生 |
| GATES | gate-integrity.json | 验收员独立执行 integrity；工具记录 gate_b197569ffe84cbd315fba18c（audit_only pass），独立判定 gate_337b5c3394e18ca78cb14aa0（verdict=FAIL，缺陷 MF-1～MF-9），返工后复跑并写入本文件 | 未产生 |

## 命名与目录约定

每轮完整复跑在 evidence 目录下建一个以日期时间命名的子目录，用例文件按 case-用例语义名.json 落盘，同一用例多次观测加 a 与 b 后缀。端侧人工证据另建 device 子目录，保存手机转发、电脑存盘、失败文案三类截图或录屏。超过 10MB 的 zip 不留在仓库，只记录 sha256 与字节数。

## 实测回执

尚未采集：本包当前处于 truth 冻结阶段，业务代码与证据均未开始。冻结回执进入本湖门结果；实现后按上表逐项落盘，真实 COS、51 张样本、200MB 样本与真机分享按 tests.md 的 BLOCKED 表登记原因与解除条件。

## 实现轮测试记录（2026-11-09）

实现者：任链接 后端。本轮只写代码与单测：未 commit、未 push、未改 truth 正文、未跑 gate integrity。

- 改动面：新增 <container/app/routes_zip.py>、<container/app/zipkit.py>；<container/app/stage_store.py> 增补 fetch_sync（local 直读、COS download_file）；<main.py> 注册 zip_router；<errors.py> 追加 ZIP_NOT_READY、ZIP_FAILED、STAGE_EXPIRED、TOO_LARGE。
- 文件名差异：tasks.md TASK-001 写的是 `zip_export.py`，本轮按派单改用 `zipkit.py`，truth/tasks 正文未动。
- `python3 -m compileall -q container/app tests`：exit 0。
- python3 -m pytest <tests/test_zip.py> -q：15 passed。
- 覆盖路径：成功打包（四字段、条目名、1980-01-01、ZIP_STORED、bytes 一致）、子集去重排序、STAGE_EXPIRED（未知 task 与 TTL 过期）、TOO_LARGE（张数与源体积）、ZIP_NOT_READY（COS 无 bucket、local 目录不可写）、幂等同键、关闭缓存两次 sha256 一致、并发同键只打包一次、只打已转存、read/write/upload 故障 502 ZIP_FAILED 且无临时残留、TIMEOUT 504、九类非法输入 400。
- 端到端（TestClient，local 存储）：/parse（构造 stub）→ /stage ×3 → /zip 返回 `cloud://local/l6/<task>/<hash>.zip`，bytes=2229、count=3；`unzip -l` 条目 000.jpg、001.jpg、002.jpg，时间 1980-01-01 00:00；二次调用同一 fileID；/tmp/renlink-zip-* 为 0。
- 未验证：真实 COS 上传与读回、51 张与 200MB 样本、<ops/zip_smoke.py> 的 16 case curl 复跑（TASK-011、TASK-016）、真机分享。

## 冻结时序治理记录（2026-11-09）

变更 chg_a17d6ce4e5d6 登记事实：实现提交 8ed9b2e 时本包 truth 仍为 status=draft、AC 表为占位符；完整 AC 与 status=frozen 直到其后 65c3112 才写入。
本记录只登记该时序事实，不修改任何 AC、约束或既有结论正文。
truth_freeze 门以本次 refreeze 关闭该治理变更。
