# Evidence Index: l1-parser-core

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | draft | truth |
| tests | test_truth | tests.md | draft | qa |
| tasks | support_advisory | tasks.md | draft | implement |
| contract | support_advisory | truth.md 的接口契约章节 | draft | implement |

## 按 AC 的证据槽位

证据文件在实现阶段由 smoke 执行器产出，统一落在 evidence 目录，命名与用例 ID 对齐。当前阶段还没有任何执行证据，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | smoke-TC-001.json、smoke-TC-002.json | 真机分享链接单发 | 未产生 |
| AC-002 | smoke-TC-003.json、smoke-TC-004.json | 图文样本按页面张数核对 | 未产生 |
| AC-003 | smoke-TC-005.json、smoke-TC-006.json | 视频笔记样本单发 | 未产生 |
| AC-004 | smoke-TC-007.json、smoke-TC-008.json | 两个平台的短链样本 | 未产生 |
| AC-005 | smoke-TC-009.json | 过期 cookie 注入 | 未产生 |
| AC-006 | smoke-TC-010.json | 失效短链构造请求 | 未产生 |
| AC-007 | smoke-TC-011.json | 三组非法输入 | 未产生 |
| AC-008 | smoke-TC-012.json | 三个非目标平台链接 | 未产生 |
| AC-009 | smoke-TC-013.json | 延迟注入 13s | 未产生 |
| AC-010 | smoke-TC-014.json | 图片最多样本与 120 项构造 | 未产生 |
| AC-011 | smoke-TC-015.json | 四类响应 schema 校验 | 未产生 |
| AC-012 | smoke-TC-016.json | 容器 /tmp 快照对比 | 未产生 |
| AC-013 | smoke-TC-017.json | 带 cookie 字段请求 | 未产生 |
| AC-014 | smoke-TC-018.json | 健康探针 | 未产生 |

## 约束证据槽位

| 约束 | 证据 | 状态 |
|------|------|------|
| callContainer 15s 与一文件一请求 | smoke-TC-013 的耗时字段 | 未产生 |
| 返回包 1000KB 与只回 cloudID | smoke-TC-014 的字节数与键集合 | 未产生 |
| 容器无持久盘，文件进 COS | smoke-TC-016 的 /tmp 前后对比 | 未产生 |
| zip 用 shareFileMessage | l6 契约，本湖只引用 | 转交 l6 |
| 小红书 webp 转 jpg | smoke-TC-015 的 needs_transcode 断言 | 未产生 |
| cookie 只做运营方池 | smoke-TC-017 与 smoke-TC-009 | 未产生 |
| f2 当库用不下载 | smoke-TC-016 的出网请求记录 | 未产生 |
| 小红书图文自研 | l2 接缝，本湖只验路由 | 转交 l2 |

## 样本采集进度

八个样本槽位的实际链接、采集日期、页面条目数与截图由运营侧登记，登记完成前覆盖矩阵里对应的 e2e 用例保持 BLOCKED。本文件不记录样本链接原文。

## Boundary

本文件是索引与槽位，不放最终判定、不放发布结论。通过与否由运营方跑 smoke 后回填的状态与验收员的独立核对决定。
