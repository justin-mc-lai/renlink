---
change_id: chg_a17d6ce4e5d6
slug: l6-zip-export
status: pending
created_by: 任链接后端
created_at: 2026-11-08T22:51:35.375726Z
base_truth_sha256: bd3f1dc1e6b63d83ef013ae7c2e8d419885968f2227ac7ae30d99e6d3fdc769b
base_package_fingerprint: 47e1ad9688cbfdb1344d76cc7dc3203081bd7a05445ac4a1176890899a22fa05
---

# Change Request: 冻结时序更正依据（治理记录，truth 正文不改）：实现提交 8ed9b2e 时 truth 仍为 status=draft、AC 表为占位符，完整 AC 与 status=frozen 直到其后 65c3112 才写入。此处只登记事实与后续闸门口径，不修改任何 AC/约束正文；是否需要正式 refreeze 由 run 负责人决定。

冻结时序更正依据（治理记录，truth 正文不改）：实现提交 8ed9b2e 时 truth 仍为 status=draft、AC 表为占位符，完整 AC 与 status=frozen 直到其后 65c3112 才写入。此处只登记事实与后续闸门口径，不修改任何 AC/约束正文；是否需要正式 refreeze 由 run 负责人决定。

## Route

Edit the package truth (and its tests/tasks/evidence as needed), then close this change with `beacon truth refreeze`. The change stays pending — and the truth_freeze gate stays blocked — until the refreeze lands.
