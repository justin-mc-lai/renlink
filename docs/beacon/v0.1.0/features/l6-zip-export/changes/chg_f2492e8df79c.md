---
change_id: chg_f2492e8df79c
slug: l6-zip-export
rebased_by: 任链接后端
rebased_at: 2026-11-08T21:26:00.410165Z
status: pending
created_by: 任链接后端
created_at: 2026-11-08T21:25:54.92064Z
base_truth_sha256: 52586454d18b87457c35146721f9e9069f9571a8b2acdd9bda68cdd8fa0a0ab1
base_package_fingerprint: 3b21a11f906be36c919aba208a497912a67a3d7a6f598cd28a5a72d3244f5982
---

# Change Request: 按验收员 MF-1～MF-9 返工 tests/tasks/evidence：修复 setup_task 引号、补 TASK_ID_FRESH 与 /stage 不重跑断言、ZIP_FAULT_INJECT 增加 write、补 local 目录不可写实例、TC-014 增加 zipinfo 时间戳断言、TC-002 对齐 AC 样例 [7,1,7]、TC-003 补对象计数、evidence 状态与 gate id；truth.md 的 AC 正文不变

按验收员 MF-1～MF-9 返工 tests/tasks/evidence：修复 setup_task 引号、补 TASK_ID_FRESH 与 /stage 不重跑断言、ZIP_FAULT_INJECT 增加 write、补 local 目录不可写实例、TC-014 增加 zipinfo 时间戳断言、TC-002 对齐 AC 样例 [7,1,7]、TC-003 补对象计数、evidence 状态与 gate id；truth.md 的 AC 正文不变

## Route

Edit the package truth (and its tests/tasks/evidence as needed), then close this change with `beacon truth refreeze`. The change stays pending — and the truth_freeze gate stays blocked — until the refreeze lands.

## Rebase Note

接受返工后的当前正文为变更基线；AC 正文未改，只改 tests/tasks/evidence
