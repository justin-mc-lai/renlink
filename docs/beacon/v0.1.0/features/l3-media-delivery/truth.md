---
slug: l3-media-delivery
version: v0.1.0
status: frozen
language: zh
domain_required: false
ux_required: false
parser_contract: beacon-feature-package-v2
truth_source_model: feature_package_authoritative
package_maturity: filled
materials_status: current
intent_confirmed: true
program_ref: docs/beacon/v0.1.0/lake-proposal.json
run_ref: run_1084fcb4301353f56601ec48
stack: python-fastapi-cloudrun-container
canonical_refs:
  truth: docs/beacon/v0.1.0/features/l3-media-delivery/truth.md
  tests: docs/beacon/v0.1.0/features/l3-media-delivery/tests.md
  tasks: docs/beacon/v0.1.0/features/l3-media-delivery/tasks.md
  evidence: docs/beacon/v0.1.0/features/l3-media-delivery/evidence.md
---

# Requirement Truth: l3-media-delivery

## 人话

用户在小程序里点某一项，容器按 index 把这一项从 /parse 给的 remoteUrl 下载下来，小红书 webp 先转成 jpg，再传到云托管对象存储 COS，只回一个 cloudID；小程序拿着它下载存相册。容器不落持久盘，单请求一分钟内结束，存不了就明说存不了。

## User Intent

/parse 只给地址，用户还拿不到文件。真正兑现「保存到手机」的是这一湖：一项一个请求，下载、转码、转存一次做完，返回值小到能塞进 callContainer 的 1000KB 包，并且失败必须可判别——没配存储就说没配，清单过期就说过期，文件太大就说太大，绝不伪造一个 cloudID 让前端以为成功了。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
program: lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
language: zh
source: user_intent
utterance: "l3：POST /stage 按 index 取一项 → 下载 → webp 转 jpg → 上传对象存储 → 返回 cloudID，不落持久盘"
goal: "容器提供 POST /stage，输入 {task_id,index}，单请求 60s 内完成下载、必要的 webp→jpg 转码、COS 转存，返回 {ok,fileID,kind,ext,bytes}，fileID 可被 wx.cloud.downloadFile 读取"
non_goals: "zip 打包（l6）；解析（l1）；小程序页面与相册保存（l5）；视频转码/压缩；接收用户 cookie；持久盘缓存；多文件合并；断点续传"
constraints: "单请求 ≤60s；视频 ≤200MB；task_id 10 分钟有效；COS 用云托管容器开放接口取临时密钥；图片 webp 必须 Pillow 转 jpg；同一 (aweme_id,index) 幂等；无 COS 凭证返回 STAGE_NOT_READY，不得伪造成功；callContainer 返回包 ≤1000KB 且只回 cloudID；容器无持久盘，临时文件在 /tmp 且请求结束即删；新增 GET /stage/file?file_id=cloud://... 流式返回已转存对象，仅接受 cloud:// id，供 H5/PC 直接下载"
scope_mode: lake
```

## 目标

- 交付一个可独立 curl 的转存接口：拿到 /parse 的清单后，按 index 逐项换到 cloudID，不依赖小程序。
- 把「下载 → 转码 → 上传 → 回 ID」压进一次请求，满足 callContainer ≤15s 的业务预期与 ≤60s 的硬上限。
- 让失败可判别：清单过期、文件超限、存储未配置、上游失败各有固定错误码，前端不用猜。
- 让重复点击不重复搬文件：同一 (aweme_id,index) 命中已转存结果直接回原 cloudID。
- 把「不落持久盘」做成可检验行为：请求结束后 /tmp 无残留。

## 非目标

- 不做 zip 打包与分享（l6）。
- 不做链接解析、清单生成（l1）；/stage 只消费 /parse 的清单。
- 不做视频转码、压缩、裁剪、加水印。
- 不做小程序页面、进度条、相册保存（l5）。
- 不接收用户 cookie，不提供任何写入用户凭据的字段。
- 不使用容器本地持久盘做缓存，不把文件留在容器里等下次读。
- 不做断点续传、分片上传、多文件合并。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | 单请求 ≤60s | /stage 总预算 60s（STAGE_TIMEOUT_S 默认 60），到点中止并返回 504 TIMEOUT | AC-013 |
| C2 | 视频 ≤200MB | 下载前看 Content-Length，下载中累计字节数，超限即断流并返回 413 TOO_LARGE；图片上限 32MB | AC-004 |
| C3 | task_id 10 分钟内有效 | /parse 成功时把清单写进进程内 TTL 缓存（默认 600s），键为 task_id；过期或未知返回 410 STAGE_EXPIRED | AC-005、AC-011 |
| C4 | COS 临时密钥走容器开放接口 | 优先 COS_SECRET_ID/COS_SECRET_KEY（本地/临时注入），其次云托管容器开放接口取临时密钥；两者都拿不到返回 503 STAGE_NOT_READY | AC-006 |
| C5 | 图片 webp 必须转 jpg | needs_transcode=true 或源为 webp 时用 Pillow 转 RGB JPEG（quality 90），返回 ext=jpg；原 remoteUrl 不改写 | AC-003 |
| C6 | 幂等 (aweme_id,index) | 以 platform:content_id:index 为键缓存 cloudID（默认 24h），命中直接返回，不再请求上游、不再上传 | AC-007 |
| C7 | 无 COS 凭证返回 STAGE_NOT_READY | 存储未配置时不下载、不落盘、不返回任何 cloud:// 值 | AC-006 |
| C8 | 返回包 ≤1000KB 只回 cloudID | 成功响应只有 ok、fileID、kind、ext、bytes 五个字段，无 base64、无文件流、无本地路径 | AC-009 |
| C9 | 容器无持久盘 | 临时文件只写 /tmp/renlink-stage-*，finally 删除；成功与失败路径都要清 | AC-010 |
| C10 | 禁止收用户 cookie | 请求体出现 cookie 字段返回 400 INVALID_REQUEST | AC-012 |

## Alignment Surface

本湖是「解析 → 交付」里的交付段：上游吃 l1 的 items[].index / remoteUrl / needs_transcode，下游把 cloudID 交给 l5 下载存相册、交给 l6 打包。凡是解析、页面、分享、打包的能力都不在本湖范围。l4 的 cookie 只影响上游下载能否成功，本湖不直接管理 cookie。

## Open Questions

One question at a time; a package cannot be signed while a row is open.
Use beacon truth ask / beacon truth answer to drive this ledger.

| Q ID | Question | Recommendation | Status | Answer | Source |
|------|----------|----------------|--------|--------|--------|
| Q1 | 谁、什么问题、什么算完成？ | 用户点一项就能拿到可下载的 cloudID，失败有固定错误码 | answered | 运营方/用户把 /parse 清单里的一项换成 cloudID；单请求 60s 内返回可读 fileID 即完成 | MausBot |
| Q2 | task_id 从哪来？ | 由 /parse 响应直接返回，客户端不再自行计算 | answered | task_id 仍是 st_ 前缀加 sha256 十六进制前 24 位（输入 v1、platform、content_type、resolved_url 与每项 index:type:ext:remoteUrl）；自 chg_3c2cde3327ff 起 /parse 成功响应新增 task_id 字段（schema 同步），客户端直接使用该值调用 /stage | apple |
| Q3 | 本地验收用真实 COS 还是 mock？ | 本地默认 mock，生产走 COS；两条路径同一接口 | answered | STAGE_STORE=local 时写 STAGE_LOCAL_DIR，fileID 形如 cloud://local/key；STAGE_STORE=cos 时走 COS。本地验收用 local，evidence 写明模式 | MausBot |
| Q4 | task_id 从哪来？ | 同 Q2，/parse 直接返回 | answered | 同 Q2：/parse 响应新增 task_id 字段，客户端不再复算；容器在 /parse 成功时写 TTL 缓存 | apple |
| Q5 | 本地验收用真实 COS 还是 mock？ | 本地默认 mock，生产走 COS；两条路径同一接口 | answered | 同 Q3：本地用 STAGE_STORE=local 的 mock，生产用 cos | MausBot |

## Intent Coverage

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | 目标：按 index 换 cloudID，可独立 curl | tests.md TC-001 |
| AC-002 | 目标：视频项同样换 cloudID | tests.md TC-002 |
| AC-003 | 约束 C5：小红书 webp 转 jpg | tests.md TC-003 |
| AC-004 | 约束 C2：视频 ≤200MB | tests.md TC-004 |
| AC-005 | 约束 C3：task_id 10 分钟有效 | tests.md TC-005 |
| AC-006 | 约束 C4、C7：存储未配置不得伪造成功 | tests.md TC-006 |
| AC-007 | 约束 C6：同一 (aweme_id,index) 幂等 | tests.md TC-007 |
| AC-008 | 目标：索引越界/清单缺项必须可判别 | tests.md TC-008 |
| AC-009 | 约束 C8：返回包只回 cloudID | tests.md TC-009 |
| AC-010 | 约束 C9：临时文件请求结束即删 | tests.md TC-010 |
| AC-011 | 约束 C3：task_id 可连续取多个 index，缓存按 task_id 隔离 | tests.md TC-011 |
| AC-012 | 约束 C10：禁止收用户 cookie | tests.md TC-012 |
| AC-013 | 约束 C1：60s 硬超时 | tests.md TC-013 |
| AC-014 | lake-proposal 指标：真实清单取 1 视频 + 1 图，fileID 可读 | tests.md TC-014 |
| AC-015 | 契约补登：GET /stage/file 流式下载已转存对象 | tests.md TC-015 |
| AC-016 | 契约补登：/parse 响应返回 task_id 且 schema 校验通过 | tests.md TC-016 |

## Acceptance Criteria

| AC ID | Criterion |
|-------|-----------|
| AC-001 | POST /stage 传有效 task_id 与图片 index，返回 200、ok=true、fileID 以 cloud:// 开头、kind=image、ext 非空、bytes>0；用 fileID 读回的对象字节数等于 bytes |
| AC-002 | POST /stage 传有效 task_id 与视频 index，返回 200、ok=true、kind=video、ext=mp4、fileID 以 cloud:// 开头，单请求耗时 ≤60s |
| AC-003 | 小红书图片项在 needs_transcode=true 时转存后 ext=jpg，对象 magic 前 3 字节为 FF D8 FF，可被 Pillow 以 JPEG 解码；源为 webp 的图片项同样处理；原 remoteUrl 与清单不被改写 |
| AC-004 | 视频源 Content-Length 超过 200MB 时返回 HTTP 413、ok=false、error.code=TOO_LARGE，且不产生任何 cloudID；视频实际下载字节超过 200MB 时同样返回 TOO_LARGE；图片超过 32MB 时同样返回 TOO_LARGE |
| AC-005 | task_id 不存在时返回 HTTP 410、ok=false、error.code=STAGE_EXPIRED；写入缓存超过 600s（STAGE_TASK_TTL_S）后调用同样返回 HTTP 410、STAGE_EXPIRED，响应无 fileID |
| AC-006 | 未配置任何 COS 凭证且 STAGE_STORE=cos 时返回 HTTP 503、ok=false、error.code=STAGE_NOT_READY；响应不含 cloud:// 值，/tmp 不新增文件 |
| AC-007 | 同一 task_id 与 index 在 cloudID 缓存有效期内第二次调用，返回与第一次完全相同的 fileID，上游下载次数与上传次数均不增加；等价键 platform:content_id:index 命中时行为一致 |
| AC-008 | index 小于 0、index 越界、task_id 对应清单中不存在该项，三种输入均返回 HTTP 400、ok=false、error.code=STAGE_FAILED、retryable=false |
| AC-009 | 任意 /stage 成功响应体不大于 1024000 字节，字段仅 ok、fileID、kind、ext、bytes；响应中无 base64、无文件流、无 /tmp 路径 |
| AC-010 | /stage 成功请求与失败请求（含 TOO_LARGE、STAGE_FAILED）结束后，容器 /tmp 下 renlink-stage-* 文件数均为 0 |
| AC-011 | 同一 task_id 在 10 分钟内可连续请求多个不同 index，各自返回不同 fileID；不同 task_id 的缓存互不覆盖；/parse 响应字段与 contract/parse_response.schema.json 校验保持通过 |
| AC-012 | /stage 请求体出现 cookie 字段时返回 HTTP 400、ok=false、error.code=INVALID_REQUEST，且不触发下载 |
| AC-013 | 上游下载、转码、上传任一步骤使单请求超过 60s 时返回 HTTP 504、ok=false、error.code=TIMEOUT，且临时文件被清理 |
| AC-014 | 真实 /parse 清单连续调用 /stage 取 1 个视频 + 1 张图，两次都返回可读 fileID，读回字节与响应 bytes 一致；evidence 写明 STAGE_STORE 模式 |
| AC-015 | GET /stage/file?file_id=cloud://... 返回 200，Content-Length 等于对象字节数、Content-Type 与 ext 匹配；file_id 不是 cloud:// 时返回 HTTP 400、error.code=INVALID_REQUEST；对象不存在时返回 502 STAGE_FAILED |
| AC-016 | POST /parse 成功响应包含 task_id，匹配 ^st_[0-9a-f]{24}$，且 contract/parse_response.schema.json 校验通过；同一 task_id 可直接用于 /stage |

## 接口契约

### 请求

```json
{"task_id": "st_3f1c9a0b7e2d4c58a1b6d0f3", "index": 0}
```

- task_id 必填，字符串，长度 27（st_ + 24 位十六进制）。
- index 必填，整数，≥0，对应 /parse 响应 items[].index。
- 其他字段忽略；出现 cookie 字段视为违规请求。

### task_id 算法（客户端与容器必须一致）

```text
material = "v1|" + platform + "|" + content_type + "|" + resolved_url + "\n" +
           join("\n", "{index}:{type}:{ext}:{remoteUrl}" for items)
task_id  = "st_" + sha256(material.encode("utf-8")).hexdigest()[:24]
```

- 输入取 /parse 成功响应的 platform、content_type、resolved_url、items（顺序不变）。
- /parse 把同一清单按同一 task_id 写入进程内 TTL 缓存（默认 600s），响应字段与 schema 不变。
- 前端不需要新接口：拿到 /parse JSON 即可本地算出 task_id。

### 成功响应（200）

```json
{"ok": true, "fileID": "cloud://local/l3/7123456789012345678/0.jpg", "kind": "image", "ext": "jpg", "bytes": 284736}
```

- 只有这五个字段。
- fileID 必须能被 wx.cloud.downloadFile 与本地 mock 读取。
- kind 取 video、image；ext 取转存后的真实扩展名；bytes 为对象字节数。

### 失败响应

```json
{"ok": false, "error": {"code": "STAGE_EXPIRED", "message": "清单缓存已过期，请重新解析", "retryable": false}}
```

| code | HTTP | 触发条件 | retryable |
|------|------|----------|-----------|
| INVALID_REQUEST | 400 | 请求体不合法、缺字段、含 cookie 字段 | false |
| STAGE_FAILED | 502 | 上游下载失败、转码失败、上传失败 | true |
| STAGE_EXPIRED | 410 | task_id 未知或超过 TTL | false |
| TOO_LARGE | 413 | 视频 >200MB 或图片 >32MB | false |
| STAGE_NOT_READY | 503 | 没有可用 COS 凭证且不是 local 模式 | true |
| TIMEOUT | 504 | 单请求超过 60s | true |

索引越界或清单缺项按 AC-008：HTTP 400、STAGE_FAILED、retryable=false。

## 存储与转码

| 项 | 规则 |
|----|------|
| 存储模式 | STAGE_STORE=local（本地验收，默认）/ cos（生产） |
| local | 写 STAGE_LOCAL_DIR（默认 /tmp/renlink-stage-store），fileID = cloud://local/<key> |
| COS | 桶与地域来自 COS_BUCKET/COS_REGION；密钥来源见 C4；fileID = cloud://<bucket>/<key> |
| key | l3/<content_id>/<index>.<ext>，content_id 取抖音 aweme_id 或小红书 note id |
| 图片 | 源为 webp 或 needs_transcode=true → Pillow 打开、转 RGB、保存 JPEG quality 90；已是 jpg/png 且不需转码则原样上传 |
| 视频 | 不转码，原样上传，ext=mp4 |
| 超时 | 下载、转码、上传共享 60s 预算 |
| 缓存 | cloudID 缓存键 platform:content_id:index，默认 86400s（STAGE_OBJECT_TTL_S） |

## 本地验收方式

```bash
# 1. 起服务（local 存储模式，不消耗 COS）
STAGE_STORE=local STAGE_LOCAL_DIR=/tmp/renlink-stage-store \
  PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099

# 2. 真实 /parse 拿清单
curl -sS -X POST localhost:18099/parse -H 'content-type: application/json' \
  -d '{"url":"'$DY_VIDEO_1'"}' > /tmp/parse.json

# 3. 算 task_id 并取第 0 项
python3 ops/stage_smoke.py --parse-json /tmp/parse.json --index 0 --out /tmp/stage-0.json

# 4. 用 fileID 读回，字节数必须等于 bytes
python3 ops/stage_smoke.py --verify /tmp/stage-0.json
```

## 依赖与接缝

| 依赖 | 方向 | 接缝定义 | 本湖责任 |
|------|------|----------|----------|
+| l1-parser-core | l3 消费 l1 | /parse 成功响应 + items[].index/remoteUrl/needs_transcode；l1 在成功返回前调用 stage_cache.remember(...) | 只调需要的字段，不改 l1 响应字段与 schema |
+| l4-session-egress | l3 间接依赖 | 下载走统一出口；cookie 由 l1 解析用，stage 下载不新增 cookie 来源 | 不读不写 cookie |
+| l5-miniprogram-pages | l5 消费 l3 | 一次一项，读 fileID 调 wx.cloud.downloadFile | 响应体小、字段稳定 |
+| l6-zip-export | l6 消费 l3 | zip 打包只读已转存对象，不重复下载 | 本湖不产 zip |
+| COS | l3 调 COS | 云托管容器开放接口取临时密钥；本地 mock 同一接口 | 上传、拼 fileID |
