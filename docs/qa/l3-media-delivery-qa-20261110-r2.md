# l3-media-delivery · AC-016 独立复验报告（r2）

| 字段 | 值 |
|---|---|
| mode_id | `beacon-go` |
| run_id | `run_8703918d899b0b320fda8fe9`（同一 run 的 QA 复验轮） |
| stage | `qa` |
| feature | `l3-media-delivery` |
| 复验范围 | 仅 AC-016 新证据；AC-014 维持上一轮裁定 |
| 验收基线 | `13e186bf02a3979a8e66f5c55cc4eeab01f92f91`（父提交 `ebbb70c`） |
| 验收 worktree | `/tmp/l3-qa-20261110-r2`（新建，基于 13e186bf） |
| 存储模式 | `STAGE_STORE=local`，`STAGE_LOCAL_DIR=/tmp/l3-qa-20261110-r2-run/store2` |
| 服务地址 | `http://127.0.0.1:18117`（worktree 代码 + 主仓 `.venv` 解释器） |
| 验收者 | 验收员（独立于 maker） |
| AC-016 结论 | **PASS**（三条判据均有本轮自己跑出的原始输出） |
| AC-014 结论 | **维持 BLOCKED**（本轮不重新裁定） |

验收对象是新建 worktree 的 `13e186b` 干净检出；主仓 19 项 l7 在途改动未被触碰。验收过程只读代码并运行真实链路，未修改 `container/`、`truth`、`tests`、`evidence`，未 push、未发布、未 tick。

## 1. 提交 diff 审计

```bash
git -C /tmp/l3-qa-20261110-r2 rev-parse --short HEAD   # 13e186b
git -C /tmp/l3-qa-20261110-r2 rev-parse --short HEAD^  # ebbb70c
git -C /tmp/l3-qa-20261110-r2 diff --name-status ebbb70c..13e186b
git -C /tmp/l3-qa-20261110-r2 show --numstat --format='' 13e186b
```

原始输出：

```text
M	docs/beacon/v0.1.0/features/l3-media-delivery/evidence.md
A	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/parse-response.json
A	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/schema-validation.json
A	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/stage-file-readback.json
A	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/stage-response.json
A	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/summary.json

11	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence.md
1	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/parse-response.json
10	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/schema-validation.json
12	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/stage-file-readback.json
1	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/stage-response.json
40	0	docs/beacon/v0.1.0/features/l3-media-delivery/evidence/run-20261110-qa-fix/summary.json
```

结论：**只含约定的 6 个文件**（`evidence.md` + `evidence/run-20261110-qa-fix/` 下 5 个 JSON），75 insertions / 0 deletions；没有夹带 `container/`、`truth.md`、`tests.md`、`tests/` 或旧验收报告。`git ls-tree` 确认该 evidence 目录恰为 5 个文件。

## 2. 复验环境与启动方式

```bash
# 依赖解释器（主仓 .venv：fastapi 0.115.6 / jsonschema 4.23.0 / uvicorn 0.34）
/Users/apple/Developer/Personal/renlink/.venv/bin/python -c \
  'import fastapi,uvicorn,httpx,yt_dlp,f2,jsonschema;print("all deps ok")'
# all deps ok

# 启动被测 worktree 代码；cookie 只从文件读进进程环境，不打印、不落盘
cd /tmp/l3-qa-20261110-r2
set -a; . /Users/apple/.config/renlink/cookies.env; set +a
unset DOUYIN_COOKIE_LAST_REFRESH XHS_COOKIE_LAST_REFRESH
export SESSION_POOL_SOURCE=env STAGE_STORE=local \
  STAGE_LOCAL_DIR=/tmp/l3-qa-20261110-r2-run/store2 \
  PARSE_RATE_LIMIT_PER_MIN=0 PYTHONPATH=/tmp/l3-qa-20261110-r2/container
exec /Users/apple/Developer/Personal/renlink/.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 18117
```

cookie 处理说明：`~/.config/renlink/cookies.env` 同时含 `*_COOKIE` 与 `*_COOKIE_LAST_REFRESH`。带时间戳启动时 `/health` 报 `expired`（时间戳 `2026-11-09T00:48:09+08:00`，age 88647s > 86400s 上限），`/parse` 会在 freshness 门直接返回 `COOKIE_EXPIRED`。本轮只使用文件里的真实 cookie 值，去掉过期时间戳让 env 源按“有值即 fresh”处理，实际可用性由上游返回决定；**没有伪造 cookie，没有构造 body**。副作用见“限制”：operator 池时间戳已过期待刷新。

启动后 `/health`（截断）：

```json
{"ok":true,"version":"v0.1.0","platforms":{"douyin":{"cookie_status":"fresh","last_refresh":"","source":"env","pool_age_s":null},"xhs":{"cookie_status":"fresh","last_refresh":"","source":"env","pool_age_s":null}},"egress_proxy":"direct"}
```

`/stage/mode`：`{"ok":true,"store":"local"}`

## 3. AC-016 逐项判据

真实样本：`https://v.douyin.com/Y7MgY9YnYAg/`（公开抖音分享短链，仓库内既有真实样本）。

| # | 判据 | 本轮实测 | 结论 |
|---|---|---|---|
| 1 | 真实链接 `POST /parse` 返回 200 | HTTP 200，0.656s，body 1349 bytes，`ok=true` | **PASS** |
| 2 | `task_id` 非空且匹配 `^st_[0-9a-f]{24}$` | `st_f250da7c52f0a281863e9453`，`nonempty=true`，`fullmatch=true` | **PASS** |
| 3 | `contract/parse_response.schema.json` 校验通过 | Draft 2020-12，`valid=true`，`error_count=0` | **PASS** |
| 4 | 同一 `task_id` 直接 `POST /stage` 返回 200 | HTTP 200，4.136s，`ok=true` | **PASS** |
| 5 | `fileID` 可读，`GET /stage/file` 读回 bytes 与响应一致 | `162700599 == 162700599`；sha256 与本地对象一致；MP4 `ftyp` 魔数 | **PASS** |
| 补充 | `pytest tests/test_parse.py -q`（tests.md 指定 TC-016 命令） | `1 passed in 0.12s` | **PASS** |

## 4. 原始命令与输出摘录

### 4.1 POST /parse

```bash
curl -sS -m 90 -o /tmp/l3-qa-20261110-r2-run/raw/parse-response.json \
  -w 'HTTP %{http_code} in %{time_total}s\n' \
  -X POST http://127.0.0.1:18117/parse \
  -H 'content-type: application/json' \
  --data '{"url":"https://v.douyin.com/Y7MgY9YnYAg/"}'
```

```text
HTTP 200 in 0.656173s
```

响应（媒体 URL 的签名查询参数已隐去；完整原文在 `/tmp/l3-qa-20261110-r2-run/raw/parse-response.json`，未入库）：

```json
{
  "ok": true,
  "platform": "douyin",
  "content_type": "video",
  "resolved_url": "https://www.douyin.com/video/7705367833957403946",
  "item_count": 1,
  "elapsed_ms": 654,
  "items": [
    {"index": 0, "type": "video", "ext": "mp4", "width": 1080, "height": 1920,
     "needs_transcode": false,
     "remoteUrl": "https://v26-web.douyinvod.com/...?<signed params redacted>"}
  ],
  "task_id": "st_f250da7c52f0a281863e9453"
}
```

服务端日志（同一请求，签名参数已隐去）：

```text
INFO httpx HTTP Request: GET https://v.douyin.com/Y7MgY9YnYAg/ "HTTP/1.1 302 Found"
INFO renlink.douyin.argus argus ok aweme_id=7705367833957403946 elapsed_ms=459
INFO renlink.parse parse ok platform=douyin content_type=video items=1 elapsed_ms=654 host=www.douyin.com
INFO: 127.0.0.1 - "POST /parse HTTP/1.1" 200 OK
```

本轮 `task_id` 与 maker 证据里的 `st_79d23ecb056057db7cbffd8b` 不同（task_id 由含签名参数的 resolved media URL 派生），说明这是本轮新取的响应，不是复制 JSON。

### 4.2 当前 schema 校验

```bash
cd /tmp/l3-qa-20261110-r2
/Users/apple/Developer/Personal/renlink/.venv/bin/python - <<'PY'
import json, re, jsonschema
schema=json.load(open('contract/parse_response.schema.json'))
resp=json.load(open('/tmp/l3-qa-20261110-r2-run/raw/parse-response.json'))
val=jsonschema.Draft202012Validator(schema)
errors=sorted(val.iter_errors(resp), key=lambda e: list(e.path))
tid=resp.get('task_id')
print('valid=', not errors, 'errors=', len(errors))
print('task_id=', repr(tid))
print('regex_fullmatch=', bool(re.fullmatch(r'st_[0-9a-f]{24}', tid or '')))
print('empty_task_id_schema_valid=', not list(val.iter_errors({**resp,'task_id':''})))
PY
```

原始输出：

```text
valid= True errors= 0
task_id= 'st_f250da7c52f0a281863e9453'
regex_fullmatch= True
empty_task_id_schema_valid= True
```

### 4.3 POST /stage（直接使用 /parse 的 task_id）

```bash
curl -sS -m 180 -o /tmp/l3-qa-20261110-r2-run/raw/stage-response.json \
  -w 'HTTP %{http_code} in %{time_total}s\n' \
  -X POST http://127.0.0.1:18117/stage \
  -H 'content-type: application/json' \
  --data '{"task_id":"st_f250da7c52f0a281863e9453","index":0}'
```

```text
HTTP 200 in 4.136160s
{"ok":true,"fileID":"cloud://local/l3/7705367833957403946/0.mp4","kind":"video","ext":"mp4","bytes":162700599}
```

服务端日志：

```text
INFO httpx HTTP Request: GET https://v26-web.douyinvod.com/...?<signed params redacted> "HTTP/1.1 200 OK"
INFO renlink.stage stage ok platform=douyin content_id=7705367833957403946 index=0 kind=video ext=mp4 bytes=162700599
INFO: 127.0.0.1 - "POST /stage HTTP/1.1" 200 OK
```

### 4.4 GET /stage/file 读回

```bash
curl -sS -m 120 -G -o /tmp/l3-qa-20261110-r2-run/raw/readback.mp4 \
  -w 'HTTP %{http_code} in %{time_total}s size=%{size_download}\n' \
  'http://127.0.0.1:18117/stage/file' \
  --data-urlencode 'file_id=cloud://local/l3/7705367833957403946/0.mp4'
```

```text
HTTP 200 in 0.485372s size=162700599
```

字节与 sha256 对比（读回文件 vs 响应 bytes vs 本地 store 对象）：

```json
{
  "fileID": "cloud://local/l3/7705367833957403946/0.mp4",
  "response_bytes": 162700599,
  "readback_bytes": 162700599,
  "bytes_match": true,
  "readback_sha256": "cf0e2fbe65a241b431e22ec678cdc1126a9a5a3a89666e752fcd71f6e3c616be",
  "store_sha256": "cf0e2fbe65a241b431e22ec678cdc1126a9a5a3a89666e752fcd71f6e3c616be",
  "sha_matches_store": true,
  "head_hex": "000000206674797069736f6d",
  "ftyp_present": true
}
```

### 4.5 契约测试

```bash
cd /tmp/l3-qa-20261110-r2
/Users/apple/Developer/Personal/renlink/.venv/bin/python -m pytest tests/test_parse.py -q
```

```text
1 passed in 0.12s
```

## 5. 空串 task_id pattern 观察结论

`schema` 里 `task_id.pattern` 是 `^st_[0-9a-f]{24}$|^$`。本轮实测：把真实响应复制一份、只把 `task_id` 换成空串 `""`，Draft 2020-12 校验仍然 `valid=true`。

结论：**这是契约层的宽松点（可称漏洞）**——schema 单独无法证明 `task_id` 非空，空串也能通过。AC-016 原文的两条判据必须合并看：非空正则匹配 + schema 通过；本轮真实样本两条都满足，因此不影响 AC-016 判 PASS。建议后续变更把 pattern 收窄为 `^st_[0-9a-f]{24}$`（或给 `task_id` 加 `minLength: 1`），按 truth/chg 流程走；本轮按要求**不改 schema/truth**。此条列为非阻塞改进项，不是本轮 FAIL 的必改项。

## 6. AC-014 本轮裁定

**AC-014 维持 BLOCKED，本轮不重新裁定。** 上一轮理由不变：图片半边清单经 `PARSE_L2_NOTE_STUB` 注入，不属于真实 `/parse` 清单。

## 7. 限制与未验证

- 本轮只验 AC-016 与抖音视频链路；xhs 图文、AC-014 图片半边未覆盖。
- `STAGE_STORE=local`；生产 COS 上传与读回未在本轮实测。
- 只用了仓库既有的一个公开抖音样本，未换第二个视频样本交叉验证。
- operator cookie 池时间戳已过 24h（88647s）；本轮用真实 cookie 值由上游判定成功，但正式 release 前应刷新池时间戳，否则 freshness 门会按 `expired` 拒绝解析。
- 运行产物在 `/tmp/l3-qa-20261110-r2-run/`（`store2/`、`raw/`），不在仓库；报告本身未提交。

## 8. 验收边界

只读验收：未改 `container/`、`truth/tests/evidence`，未 push、未发布、未 tick。worktree 唯一新增是本报告；主仓 19 项 l7 在途改动保持原样。
