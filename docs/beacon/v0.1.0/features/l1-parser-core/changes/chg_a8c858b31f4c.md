---
change_id: chg_a8c858b31f4c
slug: l1-parser-core
status: pending
created_by: MausBot
created_at: 2026-11-08T12:09:20.270691Z
base_truth_sha256: d5c642c2dd34397ea18d6b3314e22a763ed8f334f30cf2b3a02653735afef2ef
base_package_fingerprint: 6fb4b463e7faf07ad8e9c376610b77d22aba629ab7ece10f8bbb06de21ce943e
---

# Change Request: 抖音 /parse 主路径改为 headless Chromium 渲染页面取 play_addr，f2 降为失败回退；新增 12s/8s 预算、play_addr 10 分钟缓存、/tmp 清理与容器规格约束

抖音 /parse 主路径改为 headless Chromium 渲染页面取 play_addr，f2 降为失败回退；新增 12s/8s 预算、play_addr 10 分钟缓存、/tmp 清理与容器规格约束

## Route

Edit the package truth (and its tests/tasks/evidence as needed), then close this change with `beacon truth refreeze`. The change stays pending — and the truth_freeze gate stays blocked — until the refreeze lands.
