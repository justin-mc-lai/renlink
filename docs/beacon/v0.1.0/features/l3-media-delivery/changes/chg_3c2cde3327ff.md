---
change_id: chg_3c2cde3327ff
slug: l3-media-delivery
status: pending
created_by: apple
created_at: 2026-11-09T08:33:56.553544Z
base_truth_sha256: 06fb07e185eb74a82d1ba733fcc05382ce42f80ba659615d57170eb12bf64818
base_package_fingerprint: fa22f3fdc31373656d88b1255d09636f3b7f602f98f7588d225617abdadf6319
base_requirement_fingerprints:
  AC-001: 5130099a1140c9dd2d8714e24691184255c1cd2b9078d0550dab566764bba6d1
  AC-002: 86fe3f9f49fcca1004eb759cf0ed1891a53b7de0a3132fb36f20fb3e70486a01
  AC-003: 4c4a122474ee625f3ffc3eb731eaa0393abbd67787f32e0fcbab3ed6179e6b7f
  AC-004: 0f185eb6843b86465eb1c6eefc19a8aeb459b8b4bb84b2669443d8527cbcd1c4
  AC-005: 165f41b3a9825b664edbfd0cd4209c3d99acfcb90c8d663abdfbeb6da17ceefd
  AC-006: d6952bb8c2c58fc56ba2e8a48c1b968f6cf37758e9431ea1083dd52b7f2dc7c7
  AC-007: 80b7833c4d009562728bc91f6bb14d51c5d3b758b268e86bcec36b09500957e9
  AC-008: 85bc654257a06446f0c92ff7549e9a04888672acbcd3296b05a08fbaf9d2ad5d
  AC-009: 5e7040f559c5a68fb0872812324941aa8b4310ed81173790ff6ac9b4b90ed234
  AC-010: 556edf59c294b63826ebd36f9253aca8311c18f0923586e67c911dbf0e4b1920
  AC-011: 4ab9be260385478865750ba5267128cf8249acf90833b9e236e3acb72749288d
  AC-012: b94a4d639e11b0ad06e77dd1c18e0afc0a96d21f4b4aed9ce0040035ef19142d
  AC-013: 51f4606d5270d766fc65b8c2fb76fd82eecc667da60be1cb2e51524a57acd2f9
  AC-014: e6b260b98904d4d810d26d586af864475c057821e31859ae0b05a254290d733c

---

# Change Request: 契约补登：/parse 响应新增 task_id 字段（确定性哈希照旧，客户端不再自行计算）；新增 GET /stage/file 流式下载已转存对象，供 H5/PC 直接下载；同步更新 l1 响应 schema 与前端 stageMedia/createZip 的真实调用

契约补登：/parse 响应新增 task_id 字段（确定性哈希照旧，客户端不再自行计算）；新增 GET /stage/file 流式下载已转存对象，供 H5/PC 直接下载；同步更新 l1 响应 schema 与前端 stageMedia/createZip 的真实调用

## Route

Edit the package truth (and its tests/tasks/evidence as needed), then close this change with `beacon truth refreeze`. The change stays pending — and the truth_freeze gate stays blocked — until the refreeze lands.

## AC Diff

added:
- AC-015
- AC-016

changed:
- (none)

removed:
- (none)
