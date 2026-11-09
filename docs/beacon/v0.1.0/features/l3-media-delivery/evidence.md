# Evidence Index: l3-media-delivery

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | frozen | truth |
| tests | test_truth | tests.md | current | qa |
| tasks | support_advisory | tasks.md | current | implement |
| contract | support_advisory | truth.md 的接口契约章节 | frozen | implement |

## 按 AC 的证据槽位

执行器为 stage_smoke.py，每个用例落一个 JSON；TC-001..TC-013 的完整轮次为 run-20261109-0030，AC-014 的复跑轮次为 run-20261109-0034。
下表只登记裸文件名，避免把实现源码当成 requirement authority。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | case-image-ok.json | 真实 /parse 清单取图片项，/stage 后本地读回 | collected |
| AC-002 | case-video-ok.json | 真实抖音 /parse 清单取视频项，/stage 后本地读回 | collected |
| AC-003 | case-webp-to-jpg.json | webp 源转码，校验 FF D8 FF 与 Pillow 解码 | collected |
| AC-004 | case-too-large.json | 注入 Content-Length 209715201 | collected |
| AC-005 | case-expired.json、case-expired-ttl.json | 未知 task_id 与 TTL=1 过期 | collected |
| AC-006 | case-not-ready.json | STAGE_STORE=cos 且无 bucket/凭证 | collected |
| AC-007 | case-idempotent.json | 同一 task_id/index 连调两次 | collected |
| AC-008 | case-bad-index.json | index=-1 与越界 | collected |
| AC-009 | case-response-shape.json | 键集合与响应体字节数 | collected |
| AC-010 | case-tmp-clean.json | 成功与失败后容器临时目录文件数 | collected |
| AC-011 | case-multi-index.json、case-video-ok.json | 多 index 与 parse schema 校验 | collected |
| AC-012 | case-user-cookie.json | 请求体带 cookie 字段 | collected |
| AC-013 | case-timeout.json | STAGE_TIMEOUT_S=2、延迟 5000ms | collected |
| AC-014 | run-20261110-ac014/parse-video.json、stage-video.json、readback-video.json、xhs-attempt-*.json、xhs-fetch-shape.json | 真实抖音分享链接 /parse→/stage→读回；真实小红书图文链接 /parse（当前被平台风控拦截） | blocked（图片半边未取得真实链路，见下节） |
| AC-016 | run-20261110-qa-fix/parse-response.json、schema-validation.json、stage-response.json、stage-file-readback.json | 真实抖音分享链接 POST /parse，取响应 task_id 直接 /stage，GET /stage/file 读回 | collected |

说明：历史 run（run-20261109-0027/0030/0034/0036-all）的 /parse body 早于 task_id 变更，其 parse_schema 结论属于旧 schema，不能作为 AC-016 证据；AC-016 的 schema 结论以 run-20261110-qa-fix 为准。

说明（AC-014 图片半边）：run-20261109-0034 / 0036-all 里的图片清单经 l1 的 PARSE_L2_NOTE_STUB 接缝注入，不是真实 xhs 图文解析结果，自本轮回执起不再作为 AC-014 证据。

## AC-014 补证（run-20261110-ac014，2026-11-10）

- 基线：worktree `/tmp/l3-ac014-20261110`，分支 `beacon/l3-ac014-evidence-20261110`，起点 `13e186bf`；服务 `STAGE_STORE=local`、`STAGE_LOCAL_DIR=/tmp/ac014-store`、端口 18114。
- 样本来源：真实 Chrome 打开 `https://www.xiaohongshu.com/explore` 公共信息流，从笔记卡片复制 `note id + xsec_token`（未登录即可读信息流）。证据里 `xsec_token` 一律打码为 `***`，运营 cookie 只经进程环境变量传入。

视频半边（真实抖音 `https://v.douyin.com/Y7MgY9YnYAg/`）：

    parse: 200, content_type=video, task_id=st_e8f79c64ed76853319c6ba7c
    stage: 200, {"fileID":"cloud://local/l3/7705367833957403946/0.mp4","kind":"video","ext":"mp4","bytes":162700599}
    read:  200, 162700599 bytes, 与响应 bytes 一致

图片半边（真实小红书图文笔记，5 条新 token 同轮实测）：

    /parse 200+video  × 4（这些笔记本身是视频笔记，走 yt-dlp 分支）
    /parse 502 PARSE_FAILED "没有落到笔记规范页"  × 1（图文笔记 6ac9b7cc0000000015008d58）

阻塞根因（两项，均在 l3 证据范围之外）：

1. 图文笔记页拉取被平台风控拦截：iPhone H5 UA 请求 `/explore/<id>?xsec_token=…` 302 到 `/404/sec_*`；桌面 Chrome UA 直接 302 到 `/login`。同轮 6 个新 token 全部复现（xhs-fetch-shape.json）。视频笔记不受影响，因为走 yt-dlp 的接口路径，不拉 HTML。
2. 即使页面取回，当前 l2 只认 `state.note.noteDetailMap`；今天的小红书 H5 页面把笔记放在 `state.noteData.data.noteData`。用一张真实抓回的页面跑 `_note_from_state`，实测抛 `PARSE_FAILED 页面缺少 noteDetailMap`（xhs-parser-shape.json）。

结论：AC-014 图片半边在本轮无法取得真实端到端证据，不能转 PASS。可选修复（都不在本次证据任务授权内）：用已登录的小红书桌面账号刷新运营 cookie（需人工扫码），或修改 `container/app/parsers/xhs.py` 以适配 H5 `noteData` 结构。

## 实测回执

真视频（case-video-ok.json，冷启动后重新下载）：

    {"ok":true,"fileID":"cloud://local/l3/7705367833957403946/0.mp4","kind":"video","ext":"mp4","bytes":162700599}

真图片（case-real-video-and-image.json，冷启动后重新下载，148ms）：

    {"ok":true,"fileID":"cloud://local/l3/6af04386000000001500d626/0.jpg","kind":"image","ext":"jpg","bytes":514859}

两个 fileID 都从本地存储读回，读回字节数与响应 bytes 一致。视频请求耗时 4.2s，在 60s 预算内。同轮 /parse 响应通过 parse_response.schema.json 校验。15 个用例文件的所有 check 均为 true；验收判定仍归独立验收员。

### 本轮复跑与 pytest

- AC-014 复跑：run-20261109-0034 的 real-video-and-image 用例，STAGE_STORE=local，视频请求 4285ms、图片请求 146ms；视频 162700599 字节、图片 514859 字节，两个 fileID 都读回成功且字节一致。
- 本地全量复跑：run-20261109-0036-all，10 个 local 用例全部 PASS（TC-001/002/003/007/008/009/010/011/012/014）。
- 构造类用例 TC-004/005/006/013 的完整证据仍在 run-20261109-0030；其中超限、TTL 过期、未配置存储另由 pytest 覆盖。
- pytest 补充用例：tests 目录下的 stage 用例，9 passed / 0 failed，覆盖成功、过期、超限、未配置存储、幂等、临时文件清理、cookie 拒绝与非法 index；结果与同轮 smoke 证据放在一起。

### AC-016 复采（run-20261110-qa-fix，HEAD ebbb70c）

- 真实抖音分享链接 `https://v.douyin.com/Y7MgY9YnYAg/` → `POST /parse` HTTP 200，`task_id=st_79d23ecb056057db7cbffd8b`，匹配 `^st_[0-9a-f]{24}$`。
- `contract/parse_response.schema.json`（Draft 2020-12）校验：`valid=true`，无 errors。
- 直接用该 task_id 调 `POST /stage`（index=0）：HTTP 200，`fileID=cloud://local/l3/7705367833957403946/0.mp4`，`kind=video`，`ext=mp4`，`bytes=162700599`。
- `GET /stage/file?file_id=...`：HTTP 200，读回 162700599 字节，与响应 bytes 一致；sha256 `cf0e2fbe65a241b431e22ec678cdc1126a9a5a3a89666e752fcd71f6e3c616be`。
- store 模式：`STAGE_STORE=local`（`STAGE_LOCAL_DIR=/tmp/renlink-stage-store-fix`）；原始响应与校验输出见 run-20261110-qa-fix/。

## 已知限制

- AC-014 的图片半边还不是完全真实的端到端路径。l2-xhs-images 仍是 draft，l1 没有真实 xhs 图文解析；抖音图文经 f2 解析三个公开 note 链接均返回 HTTP 403。图片项通过 l1 既有的 PARSE_L2_NOTE_STUB 接缝注入，清单使用真实 xhs note id 6af04386000000001500d626，媒体 URL 是真实 /parse 返回的 xhs CDN 图片；webp 用例使用本地 382KB webp 样本。视频半边完全真实。
- 本地验收未上传真实 COS。COS 适配器已改用 cos-python-sdk-v5 并在无 bucket/凭证时按契约返回 STAGE_NOT_READY；生产需要真实 COS bucket 与云托管临时密钥接口，上传路径尚无真实凭证实测。
- 本地 mock 写 STAGE_LOCAL_DIR；生产用 COS，容器不保留持久对象。

## Boundary

evidence.md 是索引与实测回执，不是 QA gate 判定，也不声明 release readiness。

## 契约补登 chg_3c2cde3327ff（2026-11-09）

- `/parse` 成功响应新增 `task_id`（`st_` 前缀 + sha256 前 24 位）；客户端不再自行复算，契约同步 `contract/parse_response.schema.json`。
- 新增 `GET /stage/file`：仅接受 `cloud://` id，流式返回已转存对象，供 H5/PC 直接下载。
- 验证：`pytest tests/test_parse.py tests/test_stage.py -q` → 12 passed；本地 E2E 抖音视频 162,700,599B，`/stage/file` 返回 200 video/mp4 且字节一致。
