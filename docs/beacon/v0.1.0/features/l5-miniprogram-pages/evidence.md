# Evidence Index: l5-miniprogram-pages

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | draft | truth |
| tests | test_truth | tests.md | draft | qa |
| tasks | support_advisory | tasks.md | draft | implement |
| contract | support_advisory | truth.md 的接口契约章节 | draft | implement |

## 按 AC 的证据槽位

端侧证据在实现与联调阶段由 smoke_l5 执行器与真机录屏产出，统一命名与用例 ID 对齐。当前处于 truth 阶段，所有执行产物均处于待采集状态，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | smoke-TC-001.json、smoke-TC-003.json | iPhone 真机剪贴板识别与降级录屏 | 未产生 |
| AC-002 | smoke-TC-001.json、smoke-TC-002.json | 解析触发与 Loading 骨架屏截图 | 未产生 |
| AC-003 | smoke-TC-001.json | iPhone 视频解析并存相册真机录屏 | 未产生 |
| AC-004 | smoke-TC-002.json | Android 图文九宫格与逐张步进存相册录屏 | 未产生 |
| AC-005 | smoke-TC-005.json | 单张转存超时与独立重试录屏 | 未产生 |
| AC-006 | smoke-TC-002.json | ZIP 打包与微信会话转发录屏 | 未产生 |
| AC-007 | smoke-TC-004.json | 错误信封人话提示界面截图 | 未产生 |
| AC-008 | smoke-TC-006.json | 相册权限被拒与 openSetting 恢复录屏 | 未产生 |
| AC-009 | smoke-TC-007.json | 个人中心 openid 历史与空态截图 | 未产生 |
| AC-010 | smoke-TC-001.json、smoke-TC-002.json | parse_history 自动落库与再次解析联动 | 未产生 |
| AC-011 | smoke-TC-001.json、smoke-TC-004.json | callContainer 请求体抓包分析报告 | 未产生 |
| AC-012 | smoke-TC-001.json、smoke-TC-002.json | 双真机端到端全链路验收录屏 | 未产生 |

## 约束证据槽位

| 约束 | 证据 | 状态 |
|------|------|------|
| callContainer 15s 与一文件一请求 | smoke-TC-002.json 的耗时与网络请求序列 | 未产生 |
| 返回包 1000KB 与只回 cloudID | smoke-TC-001.json 的响应大小与键集合 | 未产生 |
| 容器无持久盘，文件进 COS | smoke-TC-001.json 的 downloadFile 结果 | 未产生 |
| zip 用 shareFileMessage | smoke-TC-002.json 的转发调用截图 | 未产生 |
| 小红书 webp 转 jpg | smoke-TC-002.json 的相册文件格式校验 | 未产生 |
| cookie 只做运营方池 | smoke-TC-001.json 的请求头与请求体审计 | 未产生 |
| 历史表按 openid 隔离，小程序端直写 | smoke-TC-007.json 的双账号查询对比 | 未产生 |
| f2 当库用不下载；小红书图文自研 | smoke-TC-001.json 的分阶段网络记录 | 未产生 |

## 真机测试设备登记

两台测试设备（iPhone 14 Pro 与 Xiaomi 13）由测试人员登记在验收台账，登记完成前覆盖矩阵里对应的 e2e 用例保持 BLOCKED。本文件不记录最终判定。

## Boundary

本文件是索引与槽位，不放最终判定、不放发布结论。通过与否由独立验收员在真实手机上体验验证后回填。
