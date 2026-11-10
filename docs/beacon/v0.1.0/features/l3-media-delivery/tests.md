---
slug: l3-media-delivery
version: v0.1.0
materials_status: current
test_source: acceptance_criteria
env: container-http
---

# Tests: l3-media-delivery

执行入口统一是 `ops/stage_smoke.py`：先 POST /parse 拿真实清单，按 truth 的 task_id 算法算出 token，再 POST /stage，最后用 fileID 读回对象校验字节。每次结果写 JSON 到 `docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-*/`。

## 前置条件

```bash
export PARSE_BASE="http://127.0.0.1:18099"
export STAGE_STORE=local                 # 本地验收；生产用 cos
export STAGE_LOCAL_DIR=/tmp/renlink-stage-store
export STAGE_TASK_TTL_S=600
export STAGE_OBJECT_TTL_S=86400
export DY_VIDEO_1="抖音视频真实分享链接"
export XHS_NOTE_1="小红书图文真实分享链接"
```

构造类用例额外使用：

```bash
export STAGE_MAX_VIDEO_BYTES=209715200   # 200MB
export STAGE_MAX_IMAGE_BYTES=33554432    # 32MB
export STAGE_TIMEOUT_S=60
export STAGE_FAKE_CONTENT_LENGTH=209715201   # 超限注入
export STAGE_FAKE_DELAY_MS=61000             # 超时注入
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | e2e | `python3 ops/stage_smoke.py --case image-ok` | 200 且 fileID 以 cloud:// 开头且 kind=image 且读回字节等于 bytes |
| AC-002 | TC-002 | e2e | `python3 ops/stage_smoke.py --case video-ok` | 200 且 kind=video 且 ext=mp4 且耗时 ≤60s |
| AC-003 | TC-003 | behavior | `python3 ops/stage_smoke.py --case webp-to-jpg` | ext=jpg 且对象前 3 字节 FF D8 FF 且 Pillow 可解码 |
| AC-004 | TC-004 | negative | `python3 ops/stage_smoke.py --case too-large` | 413 且 error.code=TOO_LARGE 且无 fileID |
| AC-005 | TC-005 | negative | `python3 ops/stage_smoke.py --case expired` | 410 且 error.code=STAGE_EXPIRED |
| AC-006 | TC-006 | negative | `python3 ops/stage_smoke.py --case not-ready` | 503 且 error.code=STAGE_NOT_READY 且无 cloud:// |
| AC-007 | TC-007 | behavior | `python3 ops/stage_smoke.py --case idempotent` | 两次 fileID 相同且上游下载/上传计数不增 |
| AC-008 | TC-008 | negative | `python3 ops/stage_smoke.py --case bad-index` | 400 且 error.code=STAGE_FAILED 且 retryable=false |
| AC-009 | TC-009 | contract | `python3 ops/stage_smoke.py --case response-shape` | 响应 ≤1024000 字节且仅五个键且无可疑字段 |
| AC-010 | TC-010 | behavior | `python3 ops/stage_smoke.py --case tmp-clean` | /tmp 下 renlink-stage-* 文件数为 0 |
| AC-011 | TC-011 | e2e | `python3 ops/stage_smoke.py --case multi-index` | 同 task_id 多 index 各自 fileID 不同；/parse schema 校验通过 |
| AC-012 | TC-012 | negative | `python3 ops/stage_smoke.py --case user-cookie` | 400 且 error.code=INVALID_REQUEST |
| AC-013 | TC-013 | negative | `python3 ops/stage_smoke.py --case timeout` | 504 且 error.code=TIMEOUT 且临时文件已清 |
| AC-014 | TC-014 | e2e | `python3 ops/stage_smoke.py --case real-video-and-image` | 1 视频 + 1 图均返回可读 fileID，bytes 一致 |
| AC-015 | TC-015 | contract | `pytest tests/test_stage.py -q -k stage_file` | 200 且字节数一致；非 cloud:// 返回 400 |
| AC-016 | TC-016 | contract | `pytest tests/test_parse.py -q` | task_id 匹配 ^st_[0-9a-f]{24}$ 且 schema 通过 |

## 用例明细

### TC-001 图片成功

- 输入：XHS_NOTE_1 的 /parse 清单，取第一个 image index。
- 期望：HTTP 200，`{"ok":true,"fileID":"cloud://...","kind":"image","ext":"jpg","bytes":N}`。
- 通过判据：fileID 以 `cloud://` 开头；按 fileID 读回字节数等于 bytes；内容非空。

### TC-002 视频成功

- 输入：DY_VIDEO_1 的 /parse 清单 index 0。
- 期望：HTTP 200，kind=video，ext=mp4，fileID 可读，单请求耗时 ≤60s。

### TC-003 webp 转 jpg

- 输入：小红书 webp 图片项。
- 通过判据：ext=jpg；对象 magic 为 FF D8 FF；Pillow 以 JPEG 打开成功；/parse 原始 remoteUrl 未变化。

### TC-004 超限

- 注入：`STAGE_FAKE_CONTENT_LENGTH=209715201`（或准备 >200MB 视频样本）。
- 期望：HTTP 413，`error.code=TOO_LARGE`，无 fileID，不产生对象。

### TC-005 过期

- 注入：`STAGE_TASK_TTL_S=1`，先 /parse，等待 2s 再调 /stage。
- 期望：HTTP 410，`error.code=STAGE_EXPIRED`；未知 task_id 同样 410。

### TC-006 存储未就绪

- 注入：`STAGE_STORE=cos` 且不设任何 COS 凭证。
- 期望：HTTP 503，`error.code=STAGE_NOT_READY`，响应不含 `cloud://`，/tmp 不新增文件。

### TC-007 幂等

- 同一 (task_id,index) 连调两次。
- 通过判据：两次 fileID 完全一致；第二次不触发下载（上游请求计数与上传计数均不增）。

### TC-008 非法 index

- 输入：index=-1、index 超出 items 长度、index 在清单中缺项。
- 期望：HTTP 400，`error.code=STAGE_FAILED`，`retryable=false`。

### TC-009 响应形状

- 通过判据：成功响应 JSON 键集合恰为 `{ok,fileID,kind,ext,bytes}`；响应体 ≤1024000 字节；无 base64、无文件流、无 /tmp 路径。

### TC-010 临时文件清理

- 在服务容器内对比请求前后 /tmp 下 `renlink-stage-*` 数量。
- 通过判据：成功、TOO_LARGE、STAGE_FAILED 三类请求结束后数量均为 0。

### TC-011 多 index 与 schema

- 同一 task_id 连续取 3 个不同 index。
- 通过判据：3 个 fileID 互不相同；task_id 相同的缓存不串项；/parse 响应仍通过 contract/parse_response.schema.json 校验。

### TC-012 用户 cookie

- 请求体 `{"task_id":"...","index":0,"cookie":"sessionid=1"}`。
- 期望：HTTP 400，`error.code=INVALID_REQUEST`，不触发下载。

### TC-013 超时

- 注入：`STAGE_FAKE_DELAY_MS=61000`（或让上游挂起）。
- 期望：HTTP 504，`error.code=TIMEOUT`，临时文件已清理。

### TC-014 真实清单验收

- 输入：真实 DY_VIDEO_1 与 XHS_NOTE_1 各跑一遍 /parse，再各取 1 项 /stage。
- 通过判据：两次都返回可读 fileID；读回字节等于 bytes；evidence 写明 STAGE_STORE=local 还是 cos。


### TC-015 /stage/file 流式下载

- 输入：先对一个有效清单调用 /stage 拿到 fileID，再请求 GET /stage/file 并带上 file_id 参数。
- 期望：HTTP 200，Content-Type 与 ext 匹配，响应字节数等于 /stage 返回的 bytes。
- 负向：file_id=/etc/passwd → HTTP 400，error.code=INVALID_REQUEST。

### TC-016 /parse 返回 task_id

- 输入：POST /parse 一条真实链接。
- 期望：响应包含 task_id，匹配 `^st_[0-9a-f]{24}$`，且通过 contract/parse_response.schema.json 校验；该 task_id 可直接用于 /stage。
