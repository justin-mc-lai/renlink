# Evidence Index: l2-xhs-images

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | frozen/Freeze | truth |
| tests | test_truth | tests.md | frozen/Freeze | qa |
| tasks | support_advisory | tasks.md | frozen/Freeze | implement |
| contract | support_advisory | truth.md 的「接口契约」「提取规则」章节 | frozen/Freeze | implement |

## 按 AC 的证据槽位

证据在实现阶段由解析执行器与本地 curl 复跑产出，统一落在本湖 evidence 目录，文件名与用例 ID 对齐。当前处于 truth 阶段，所有执行产物尚未开始，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | case-note-3-images.json、parse-note-3-images.html | 构造 3 图页经 /parse | 未产生 |
| AC-002 | case-note-image-fallback.json、parse-note-image-fallback.html | 构造 urlDefault 缺失与 urlPre 项 | 未产生 |
| AC-003 | case-note-shortlink.txt | 直连 parse_note 传短链桩 | 未产生 |
| AC-004 | case-note-state-map.json | 构造 noteDetailMap 命中与缺失 | 未产生 |
| AC-005 | case-note-no-state.json、case-note-broken-state.json、case-note-empty-list.json、case-note-missing-note.json | 四种结构失败 | 未产生 |
| AC-006 | case-note-state-token.json、case-note-need-token.json | URL 无 token 与全缺 token | 未产生 |
| AC-007 | case-note-contract.json、case-note-video.json | 单图字段契约与视频笔记 | 未产生 |
| AC-008 | case-note-errors.json | cookie 字段、站外域名、结构失败 | 未产生 |
| AC-009 | case-note-cache.json、xhs-server.log | 同一 URL 连打两次 | 未产生 |
| AC-010 | xhs-server.log、counters.json | 日志字段与 xhs_note_* 计数器 | 未产生 |
| AC-011 | case-note-tmp-clean.txt | 解析前后 /tmp 文件列表比对 | 未产生 |
| AC-012 | case-note-timeout.json、case-note-oversize.json | 9s 延迟桩与 5MB 页面 | 未产生 |
| AC-006 | case-note-real-samples.md | 10 条真实图文样本（BLOCKED） | 未产生 |
| GATES | gate-integrity.json | 验收员独立执行 integrity | 未产生 |

## 命名与目录约定

每轮完整复跑在 evidence 目录下建一个以起始时间命名的子目录，例如 run-20261109-0700。用例文件按 case-用例语义名.json 落盘，同一用例多次观测加 a 与 b 后缀。构造样本的 HTML 与 stub.json 一并留存，便于复现；真实样本链接只保留前 32 个字符。

## 实测回执

尚未采集：本包当前处于 truth 冻结阶段，业务代码与证据均未开始。实现后按上表逐项落盘；真实样本、真实短链与小程序联调按 tests.md 的 BLOCKED 表登记原因与解除条件。

## 实现轮测试记录（2026-11-09）

实现者：任链接 后端。本轮只写代码与单测：未 commit、未 push、未改 truth 正文、未跑 gate integrity。

- 接入落在 <container/app/parsers/xhs.py>（按本轮收窄口径，未新建 tasks.md 里的 <xhs_note.py>）：定位 window.__INITIAL_STATE__ 并容忍裸键与 undefined、noteDetailMap 定位与唯一项兜底、imageList 原图选择 urlDefault → WB_DFT → CRD_WM_WEBP（保持顺序、不用缩略地址）、xsec_token 链 URL → note.xsecToken → state 顶层、缺 token 抛 NEED_XSEC_TOKEN；新增 PARSE_XHS_SKIP_YTDLP 测试开关。
- `errors.py` 增补 NEED_XSEC_TOKEN(422, retryable=true)，既有码未动。
- python3 -m pytest <tests/test_xhs.py> -q：7 passed。
- 覆盖路径：图文多图顺序与原图地址（urlPre 不入选、无地址条目跳过）、token 回退 note、裸键 + undefined、缺 token → NEED_XSEC_TOKEN、无 state → PARSE_FAILED、空 imageList → PARSE_FAILED、xhs.parse 接缝返回 note 且 needs_transcode=true。
- 未做/未验证：解析缓存 AC-009、xhs_note_* 计数器 AC-010、直连短链 3 跳 AC-003、真实样本（AC-001、AC-003）、<ops/xhs_note_smoke.py> 与 curl 复跑。

## 冻结时序治理记录（2026-11-09）

变更 chg_6a639cf6df40 登记事实：实现提交 8ed9b2e 时本包 truth 仍为 status=draft、AC 表为占位符；完整 AC 与 status=frozen 直到其后 65c3112 才写入。
本记录只登记该时序事实，不修改任何 AC、约束或既有结论正文。
truth_freeze 门以本次 refreeze 关闭该治理变更。
