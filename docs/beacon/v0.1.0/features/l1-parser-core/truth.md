---
slug: l1-parser-core
version: v0.1.0
status: frozen
revision_id: R1
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
  truth: docs/beacon/v0.1.0/features/l1-parser-core/truth.md
  tests: docs/beacon/v0.1.0/features/l1-parser-core/tests.md
  tasks: docs/beacon/v0.1.0/features/l1-parser-core/tasks.md
  evidence: docs/beacon/v0.1.0/features/l1-parser-core/evidence.md
---

# Requirement Truth: l1-parser-core

## 人话

运营方把一条抖音或小红书链接 POST 给云托管容器的 /parse，拿回一份逐项 remoteUrl 的媒体清单；本湖只解析和归一化字段，不下载文件、不落地磁盘、不接触用户 cookie。做到 4 类真实链接各返回正确清单、失败路径返回固定错误码，这个湖才算完。

## User Intent

用户要的是「粘贴一条链接就能保存到手机」。这条链的地基是解析：没有正确的逐项远程地址，后面的下载、转存、存相册全是空的。所以本湖的完成标志不是「接口存在」，而是运营方在容器域名上直接 curl 一条真实链接，就能看到与页面一致的清单。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
program: lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
source: user_intent
utterance: "任链接：微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机（视频存相册、图文逐张+zip）"
goal: "云托管容器提供 POST /parse，输入抖音视频、抖音图文、小红书视频、短链四类链接，返回逐项 remoteUrl 的标准化清单，运营方可用 curl 直接验证"
non_goals: "B站、微博、YouTube、X；用户 cookie 上传；/parse 下载文件；前端页面与相册保存；zip 打包；付费、会员、广告；服务端自动过滑块"
constraints: "callContainer 上限 15s 且一文件一请求；返回包上限 1000KB 且只回 cloudID，/parse 只回 remoteUrl；容器无持久盘且文件必须进 COS；手机端 openDocument 不支持 zip，zip 用 wx.shareFileMessage；小红书 webp 必须后端转 jpg；cookie 只做运营方池，禁止收用户 cookie；f2 当 Python 库用，fetch_one_video 到 PostDetailFilter，/parse 不下载；小红书图文必须自研"
scope_mode: lake
```

## 目标

- 交付一个可独立验证的解析接口：运营方不经过小程序，只用 curl 就能确认 4 类链接的清单正确。
- 统一输出契约：平台、内容类型、展开后的规范链接、逐项媒体地址、条目数与耗时一次给全，供 l3 逐项下载、l5 展示进度。
- 失败可判定：cookie 失效、短链展开失败、非法输入、不支持平台、上游超时各有固定错误码，调用方不用猜。
- 把「只解析不下载」做成可检验的行为，而不是口头约定。

## 非目标

- B站、微博、YouTube、X 的解析一律不做；域名白名单之外返回 UNSUPPORTED_PLATFORM。
- 不做用户 cookie 上传，请求体出现 cookie 字段直接拒绝。
- /parse 不下载媒体、不写磁盘、不传 COS、不返回 cloudID。
- 不交付小程序页面、相册保存、zip 打包（分别归 l5、l3、l6）。
- 不做付费、会员、广告，不做服务端自动过滑块。
- 不在本湖重写 l2 的小红书图文原图逻辑，只定义路由与归一化接缝。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | callContainer ≤15s，一文件一请求 | /parse 只返回清单，单文件下载交给 /stage 一次一项；解析硬超时 12s，留 3s 余量给网络与序列化 | AC-009、AC-012 |
| C2 | 返回包 ≤1000KB，只回 cloudID | /parse 只回 remoteUrl 文本；响应体不大于 1024000 字节；items 上限 100；/stage 与 /zip 才回 cloudID，且不回文件流 | AC-010、AC-011 |
| C3 | 容器无持久盘，文件必须进 COS | /parse 零落盘；/stage 的临时文件落在 /tmp，上传 COS 成功后立即删除，容器重建不影响任何数据 | AC-012 |
| C4 | 手机端 openDocument 不支持 zip，zip 用 wx.shareFileMessage | 本湖不产 zip；/zip 只回 zip 的 cloudID，由 l6 与 l5 用 wx.shareFileMessage 转发聊天，PC 端 saveFileToDisk | 契约条款，l6 AC 承接 |
| C5 | 小红书 webp 必须后端转 jpg | /parse 对 xhs 图片项标 needs_transcode=true 并保留原始 remoteUrl 不改写；转码在 l3 /stage 落地，因为 /parse 不下载 | AC-011、AC-010 |
| C6 | cookie 只做运营方池，禁止收用户 cookie | cookie 只从容器环境变量与密钥注入；请求体带 cookie 字段返回 400 INVALID_REQUEST；日志对 cookie 值脱敏 | AC-013、AC-005 |
| C7 | f2 当 Python 库用（fetch_one_video → PostDetailFilter），/parse 不下载 | 抖音图文分支只调 DouyinHandler.fetch_one_video 并读 PostDetailFilter.images 的 URL，不触发媒体下载；镜像内置 Node20 与 pyexecjs | AC-002、AC-012 |
| C8 | 小红书图文必须自研（yt-dlp 只给缩略图） | xhs 视频走 yt-dlp XiaoHongShuIE；xhs 图文走自研 __INITIAL_STATE__ 到 imageList 加 xsec_token，由 l2 实现，l1 只做路由与字段归一 | AC-003、依赖表 |

## Alignment Surface

本湖是 7 湖程序里的解析地基，只交付 HTTP 解析清单接口与健康探针。上游是运营方 curl 与后续小程序，下游是 l2 图文、l3 下载转存、l4 登录态。凡是需要下载、转码、打包、页面交互的能力都不在本湖范围。

## Open Questions

| Q ID | Question | Recommendation | Status | Answer |
|------|----------|----------------|--------|--------|
| Q1 | 4 类真实链接样本由谁提供、什么时间到位？ | 运营方按分享面板采集，truth 阶段只登记槽位与步骤，不阻塞冻结 | answered | 幕僚长 2026-11-08 指派：拿不到真实链接就标样本待采集，禁止编造链接冒充已验证；采集规程与槽位见「样本登记」 |
| Q2 | /parse 是否覆盖小红书图文的图片数量？ | 本湖只定义路由与归一化，图片数量与封面归 l2 | answered | 作者按 l2 接缝固化：parse_note 返回 ParseResult，l1 不重复实现，4 类 AC 不含 xhs 图文数量 |
| Q3 | 业务失败用什么 HTTP 状态码？ | 4xx 与 5xx 加 ok:false 信封，curl 用状态码与 jq 双判 | answered | 作者按 AC-005 到 AC-009 固化：503 COOKIE_EXPIRED、422 SHORTLINK_FAIL、400 INVALID_URL、400 UNSUPPORTED_PLATFORM、504 TIMEOUT |
| Q4 | cookie 失效时返回空清单还是部分清单？ | 整请求失败，绝不返回半份清单让调用方误存 | answered | 作者按 AC-005 固化：items 为空数组且 ok=false |

## Intent Coverage

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | lake-proposal 指标：抖音视频返回正确清单 | tests.md TC-001、TC-002 |
| AC-002 | lake-proposal 指标：抖音图文返回正确清单 | tests.md TC-003、TC-004 |
| AC-003 | lake-proposal 指标：小红书视频返回正确清单 | tests.md TC-005、TC-006 |
| AC-004 | lake-proposal 指标：短链返回正确清单 | tests.md TC-007、TC-008 |
| AC-005 | 约束 C6 与 l4 接缝：cookie 失效必须可判别 | tests.md TC-009 |
| AC-006 | 短链展开失败必须可判别 | tests.md TC-010 |
| AC-007 | 非法输入必须可判别 | tests.md TC-011 |
| AC-008 | 非目标：域名白名单之外不做 | tests.md TC-012 |
| AC-009 | 约束 C1：15s 预算内结束 | tests.md TC-013 |
| AC-010 | 约束 C2：返回包体积上限 | tests.md TC-014 |
| AC-011 | 统一输出契约，供 l3 与 l5 消费 | tests.md TC-015 |
| AC-012 | 非目标与约束 C3、C7：只解析不下载 | tests.md TC-016 |
| AC-013 | 约束 C6：禁止收用户 cookie | tests.md TC-017 |
| AC-014 | l4 接缝：运营方可观察 cookie 新鲜度 | tests.md TC-018 |

## Acceptance Criteria

每条 AC 都可在容器域名上直接 curl 复现。样本链接用环境变量注入，链接本身登记在「样本登记」，真实链接未采集前的用例不计通过。

| AC ID | Criterion |
|-------|-----------|
| AC-001 | POST /parse 传抖音视频链接，返回 200 且 ok=true、platform=douyin、content_type=video、items 长度 1、items[0].remoteUrl 为非空 http(s) 地址、items[0].ext=mp4 |
| AC-002 | POST /parse 传抖音图文链接，返回 200 且 ok=true、platform=douyin、content_type=note、items 每项 type=image 且 remoteUrl 为非空 http(s) 地址、item_count 等于页面图片张数 |
| AC-003 | POST /parse 传小红书视频笔记链接，返回 200 且 ok=true、platform=xhs、content_type=video、items 长度 1、items[0].remoteUrl 为非空 http(s) 地址 |
| AC-004 | POST /parse 传 v.douyin.com 短链，返回 200 且 resolved_url 为 douyin.com 规范链接、清单字段与 AC-001 相同；传 xhslink.com 短链，resolved_url 为 xiaohongshu.com 规范链接 |
| AC-005 | 抖音 cookie 失效时 POST /parse 返回 HTTP 503、ok=false、error.code=COOKIE_EXPIRED、items 为空数组 |
| AC-006 | 短链展开失败时 POST /parse 返回 HTTP 422、ok=false、error.code=SHORTLINK_FAIL、resolved_url 为空字符串 |
| AC-007 | 请求体 url 不是 http(s) 链接时返回 HTTP 400、ok=false、error.code=INVALID_URL |
| AC-008 | 链接域名不在抖音与小红书白名单时返回 HTTP 400、ok=false、error.code=UNSUPPORTED_PLATFORM |
| AC-009 | 上游解析超过 12s 时返回 HTTP 504、ok=false、error.code=TIMEOUT，响应总耗时小于 15s |
| AC-010 | 任意 /parse 成功响应体不大于 1024000 字节，items 数量上限 100，响应内无 base64 字段与文件流字段 |
| AC-011 | 四类成功响应必填字段齐全且类型固定：ok 布尔、platform 字符串、content_type 字符串、source_url 字符串、resolved_url 字符串、title 字符串、item_count 整数、elapsed_ms 整数、items 数组；items[].index 从 0 连续递增 |
| AC-012 | POST /parse 全程不写容器磁盘、不传 COS、响应不含 cloudID 字段；请求前后容器 /tmp 新增文件数为 0 |
| AC-013 | 请求体出现 cookie 字段时返回 HTTP 400、ok=false、error.code=INVALID_REQUEST，服务端只读运营方 cookie 池 |
| AC-014 | GET /health 返回 200、ok=true 与 douyin、xhs 两平台的 cookie 状态字段，cookie 失效时该平台 status=expired |

## 接口契约

### POST /parse

请求体只有 url 一个必填字段，其他字段忽略；出现 cookie 字段视为违规请求。

```json
{"url": "https://v.douyin.com/XXXXXXX/"}
```

成功响应（200）：

```json
{
  "ok": true,
  "platform": "douyin",
  "content_type": "note",
  "source_url": "https://v.douyin.com/XXXXXXX/",
  "resolved_url": "https://www.douyin.com/note/7xxxxxxxxxxxxxxxxxx",
  "title": "标题文本",
  "item_count": 9,
  "elapsed_ms": 1830,
  "items": [
    {
      "index": 0,
      "type": "image",
      "remoteUrl": "https://p3-sign.douyinpic.com/example.jpeg",
      "ext": "jpeg",
      "cover": "",
      "width": 1440,
      "height": 1920,
      "needs_transcode": false
    }
  ]
}
```

字段规则：

- platform 取值 douyin、xhs。
- content_type 取值 video、note。
- items[].type 取值 video、image。
- items[].remoteUrl 必须是非空 http(s) 地址，查询串原样保留。
- items[].index 从 0 连续递增，供 /stage 按 index 取项。
- 小红书图片项 needs_transcode=true，remoteUrl 保持 webp 原地址。
- 视频项 ext=mp4，remoteUrl 指向 CDN 播放地址。

失败响应（4xx 与 5xx 共用信封）：

```json
{
  "ok": false,
  "error": {
    "code": "COOKIE_EXPIRED",
    "message": "运营方 cookie 失效，请运营刷新后重试",
    "retryable": true
  },
  "items": [],
  "elapsed_ms": 420
}
```

### 错误码

| code | HTTP | 触发条件 | retryable |
|------|------|----------|-----------|
| INVALID_URL | 400 | url 为空、非 http(s)、长度超过 2048 | false |
| INVALID_REQUEST | 400 | 请求体不合法，含 cookie 字段，字段类型错误 | false |
| UNSUPPORTED_PLATFORM | 400 | 域名不在抖音与小红书白名单 | false |
| SHORTLINK_FAIL | 422 | 短链 3 次重定向后仍未到规范页 | true |
| COOKIE_EXPIRED | 503 | 运营方 cookie 失效或风控拦截登录态 | true |
| PARSE_FAILED | 502 | 页面结构变化、找不到媒体字段 | true |
| TIMEOUT | 504 | 上游解析超过 12s | true |
| RATE_LIMITED | 429 | 单 IP 每分钟超过 20 次 | true |

### GET /health

```json
{
  "ok": true,
  "version": "v0.1.0",
  "platforms": {
    "douyin": {"cookie_status": "fresh", "last_refresh": "2026-11-08T10:00:00+08:00"},
    "xhs": {"cookie_status": "expired", "last_refresh": "2026-11-05T10:00:00+08:00"}
  },
  "egress_proxy": "direct"
}
```

## 可直接 curl 的验收方式

先把容器地址与样本变量导出（样本由运营采集后填真实值）：

```bash
export PARSE_BASE="https://container-host"
export DY_VIDEO_1="抖音视频分享链接"
export DY_NOTE_1="抖音图文分享链接"
export XHS_VIDEO_1="小红书视频笔记链接"
export DY_SHORT_1="v.douyin.com 短链"
```

AC-001 抖音视频：

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_VIDEO_1\"}" | jq -e '
  .ok == true and .platform == "douyin" and .content_type == "video"
  and (.items | length) == 1
  and (.items[0].remoteUrl | test("^https?://.+"))
  and .items[0].ext == "mp4"'
```

AC-002 抖音图文（item_count 用页面实际张数核对）：

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_NOTE_1\"}" | jq -e '
  .ok == true and .content_type == "note"
  and .item_count == (.items | length)
  and ([.items[] | select(.type != "image")] | length) == 0
  and ([.items[].remoteUrl | select(test("^https?://") | not)] | length) == 0'
```

AC-003 小红书视频：

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$XHS_VIDEO_1\"}" | jq -e '
  .ok == true and .platform == "xhs" and .content_type == "video"
  and (.items | length) == 1
  and (.items[0].remoteUrl | test("^https?://.+"))'
```

AC-004 短链展开：

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_SHORT_1\"}" | jq -e '
  .ok == true and (.resolved_url | test("^https://www\\.douyin\\.com/(video|note)/[0-9]+"))'
```

AC-005 cookie 失效（运营把池里 cookie 换成过期值后执行）：

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d "{\"url\":\"$DY_VIDEO_1\"}"
jq -e '.ok == false and .error.code == "COOKIE_EXPIRED" and (.items | length) == 0' /tmp/r.json
```

AC-006 短链展开失败：

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d '{"url":"https://v.douyin.com/0000000/"}'
jq -e '.ok == false and .error.code == "SHORTLINK_FAIL" and .resolved_url == ""' /tmp/r.json
```

AC-007 非法输入：

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d '{"url":"not-a-url"}'
jq -e '.error.code == "INVALID_URL"' /tmp/r.json
```

AC-008 不支持平台：

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d '{"url":"https://www.bilibili.com/video/BV1xx411c7mD"}'
jq -e '.error.code == "UNSUPPORTED_PLATFORM"' /tmp/r.json
```

AC-010 体积与条目上限：

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$XHS_NOTE_MAX\"}" -o /tmp/big.json -w '%{size_download}\n'
jq -e '(.items | length) <= 100 and ([.items[] | has("base64")] | any | not)' /tmp/big.json
```

AC-012 只解析不下载：

```bash
docker exec CONTAINER_ID sh -c 'find /tmp -type f | wc -l'
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_VIDEO_1\"}" | jq -e 'has("cloudID") | not'
docker exec CONTAINER_ID sh -c 'find /tmp -type f | wc -l'
```

AC-013 拒绝用户 cookie：

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d '{"url":"https://v.douyin.com/XXXXXXX/","cookie":"sessionid=1"}'
jq -e '.error.code == "INVALID_REQUEST"' /tmp/r.json
```

AC-014 健康探针：

```bash
curl -sS "$PARSE_BASE/health" | jq -e '.ok == true and (.platforms.douyin.cookie_status | length) > 0'
```

## 样本登记

真实链接由运营方从 App 分享面板采集，每类两条，采集时记录日期、平台、页面显示的条目数、截图。未采集的槽位保持待采集，禁止用编造链接冒充已验证。

| 槽位 | 环境变量 | 类别 | 页面条目数 | 采集日期 | 状态 |
|------|----------|------|-----------|----------|------|
| S1 | DY_VIDEO_1 | 抖音视频 | 1 | | 待采集 |
| S2 | DY_VIDEO_2 | 抖音视频 | 1 | | 待采集 |
| S3 | DY_NOTE_1 | 抖音图文 | 按页面张数 | | 待采集 |
| S4 | DY_NOTE_2 | 抖音图文 | 按页面张数 | | 待采集 |
| S5 | XHS_VIDEO_1 | 小红书视频 | 1 | | 待采集 |
| S6 | XHS_VIDEO_2 | 小红书视频 | 1 | | 待采集 |
| S7 | DY_SHORT_1 | 抖音短链 | 1 | | 待采集 |
| S8 | XHS_SHORT_1 | 小红书短链 | 1 | | 待采集 |

```
采集规程：
1. 在手机 App 里打开目标内容，点分享，复制链接，原样粘贴进样本表。
2. 同时记录页面显示的条目数（视频记 1，图文记实际张数）与采集日期。
3. 短链样本只来自分享面板，不用手工拼接的 id。
4. 样本链接只在运营侧保存，不写进代码仓库。
```

## 依赖与接缝

| 依赖 | 方向 | 接缝定义 | 本湖责任 |
|------|------|----------|----------|
| l2-xhs-images | l1 调 l2 | parse_note(url, cookie) 返回 ParseResult，items 为原图地址加 xsec_token | 路由、字段归一、错误映射；不重复实现 __INITIAL_STATE__ |
| l4-session-egress | l1 调 l4 | get_cookie(platform) 返回 CookieHeader，失效抛 CookieExpired | 捕获后映射 COOKIE_EXPIRED，日志脱敏 |
| l3-media-delivery | l3 消费 l1 | 按 items[].index 与 remoteUrl 逐项下载，needs_transcode 决定 webp 转 jpg | 保证 index 连续、ext 正确、URL 可直接 GET |
| l5-miniprogram-pages | l5 消费 l1 | 读 ok、content_type、items 长度与 title 渲染页面 | 契约稳定，字段不改名 |
| l6-zip-export | l6 独立 | /zip 只回 cloudID，小程序用 wx.shareFileMessage | 本湖不产 zip |

## 边界

本文件只定义需求真相。实现代码、容器配置、价格与发布动作不在 truth 阶段发生；样本采集属于运营动作，采集结果只登记在 evidence.md。
