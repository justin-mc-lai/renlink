---
change_id: chg_9aeb569f66df
slug: l2-xhs-images
status: pending
created_by: 任链接后端
created_at: 2026-11-09T17:52:17.246978Z
base_truth_sha256: 0142e9da94d3ceb139090e486560836b5a63f1a1836330a32fd1b0b3f89fc47d
base_package_fingerprint: 44c9cf2e14d6f6ad1df02e54c207f50c8b4ed722933c17d90e2698237d0a6c38
base_requirement_fingerprints:
  AC-001: e0b63b16f3e77c630939f3a002abd52645da26941799a26376c400dd34e242d5
  AC-002: 1b233ed5666682c58a3b07ae8d1b9751bf556e50a3d08c563354922657f0a870
  AC-003: 33fdc0d994e10d46ad0195280a77acd4e69473ddcf16fbdf0e76b467b19760c7
  AC-004: 373b104c468cecb8ac106f7e9bf50a82c128e648f1176ce498f9fb4138dd3f47
  AC-005: 669ff4fb3bef7402427c2ecbb2bcf3227d3e5496bb146610f6ccd7dcab86fdc8
  AC-006: d4a1c56ce695a8047921008427ca846cdd0f57e589e1b36350d77e454c60633b
  AC-007: d9bddd82a0e7494fd5646c66fb2f5a3f2cb773f6cb0d67cde090542b2543a3ea
  AC-008: 85f19eb7b96166c7f854d84a81488650be2eb1b5b5b5a80c2cf8bf112019e8e7
  AC-009: 4e747fe57330b7c387cf53ea539f18f51aeac37cf6facde27c8090dfb9cc5c61
  AC-010: 9bb8042f6232bac2a9716e56ce7ad04841b92e0824738082a7a1a3f78d8ea612
  AC-011: 14b718826e405025c6843a7f25983a05b1cdea1ee834e1aab32efe7280416c15
  AC-012: 0dc538f48b3eda0d924025dbe8bf058846d2c3c285ffe7869093770767dc4c43

---

# Change Request: 解析器兼容当前小红书 H5 的 state.noteData.data.noteData 结构（图文 imageList），保留 noteDetailMap 兼容；AC-004 定位口径与 AC-005 结构失败口径同步调整

解析器兼容当前小红书 H5 的 state.noteData.data.noteData 结构（图文 imageList），保留 noteDetailMap 兼容；AC-004 定位口径与 AC-005 结构失败口径同步调整

## Route

Edit the package truth (and its tests/tasks/evidence as needed), then close this change with `beacon truth refreeze`. The change stays pending — and the truth_freeze gate stays blocked — until the refreeze lands.

## AC Diff

added:
- (none)

changed:
- AC-004 (before 373b104c468c → after ec41d92a113c)
- AC-005 (before 669ff4fb3bef → after 31a39b3de4ca)

removed:
- (none)
