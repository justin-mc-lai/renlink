# QA 证据索引：l1-parser-core 最终镜像复验（r2）

- 目录：`evidence/qa/l1-qa-final-r2/`
- 权威结论：`evidence/qa/l1-qa-final-r2/verdict.md`
- 验收对象：`renlink-l1-final:latest` = `sha256:cf44f898eb17caa77baaa44013deb83bd816de5f2cfeed15b6d161f35b2bfe6a`（created 2026-11-08T13:14:17Z）
- run_id：`qa-l1-20261108-2225`，stage `qa`，mode `beacon-go`
- 一句话结论：douyin 主路径 PASS；xhs 主路径 FAIL（会话失效，调用方 2/2 不可复现）；6 个服务端模式用例 PASS；8 个 TC 因缺样本 BLOCKED；TC-023 遗留 P0 未关闭。
- 证据清单与哈希：`evidence/qa/l1-qa-final-r2/sha256-manifest.txt`
- 上一轮（保留不覆盖）：`evidence/qa/l1-qa-final/`
