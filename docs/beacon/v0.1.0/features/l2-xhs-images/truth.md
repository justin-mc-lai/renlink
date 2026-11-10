---
slug: l2-xhs-images
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
  truth: docs/beacon/v0.1.0/features/l2-xhs-images/truth.md
  tests: docs/beacon/v0.1.0/features/l2-xhs-images/tests.md
  tasks: docs/beacon/v0.1.0/features/l2-xhs-images/tasks.md
  evidence: docs/beacon/v0.1.0/features/l2-xhs-images/evidence.md
---

# Requirement Truth: l2-xhs-images

## 人话

用户贴一条小红书图文笔记链接，/parse 要按页面原始顺序返回每一张原图的地址，并标好这些图后面需要转码。小红书图文的原图只藏在页面里的 window.__INITIAL_STATE__，通用下载器只给缩略图，所以这一段必须自己解析；拿不到 xsec_token 就明确告诉调用方要重新分享带 token 的链接，不猜、不拿缩略图凑数。

## User Intent

小程序要支持小红书图文逐张保存。l1 的 xhs 分支目前只有视频走 yt-dlp、图文走一个未实现的接缝，真实图文链接会返回 PARSE_FAILED。本湖把这条接缝补成可用实现：解析规范笔记页的初始状态，按原顺序给出原图地址与 xsec_token 判定，错误路径给出固定错误码，供 l3 逐张转存、l5 展示进度、l7 做限流与缓存观测。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
program: lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
source: user_intent
utterance: "任链接：微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机（视频存相册、图文逐张+zip）"
goal: "小红书图文笔记经 POST /parse 返回按页面顺序排列的原图清单，图片项 needs_transcode=true，缺 xsec_token 时返回固定错误码"
non_goals: "视频解析（yt-dlp 已有）；图片下载、转码、打包；小程序页面；抖音分支；B站/微博/YouTube/X；用户 cookie 上传"
constraints: "/parse 返回包 ≤1000KB、items ≤100；/parse 不下载不落盘；图片 remoteUrl 保留 webp 原址，转码归 l3；cookie 只用运营方池；单次解析预算 8s，整体 12s 内必须给结果"
scope_mode: focused
```

## 目标

- 让真实小红书图文链接经 /parse 返回逐张原图清单，顺序与页面 imageList 一致。
- 图片项保持 webp 原址并标 needs_transcode=true，交给 l3 下载与转码。
- xsec_token 缺失时给出可判别的错误码，调用方能提示用户重新分享链接。
- 页面结构变化、字段缺失、空列表、视频或无图笔记都返回固定错误码与空 items，不返回半成品。

## 非目标

- 不实现小红书视频解析；视频仍走 l1 的 yt-dlp 分支。
- 不下载图片、不转码、不写 COS、不打包 zip（分别归 l3、l6）。
- 不改 /parse 的请求与成功响应字段，不改 l1 的归一化与截断逻辑。
- 不做抖音、B站、微博、YouTube、X。
- 不接收用户 cookie；cookie 只来自运营方池。
- 不新增小程序页面与交互（归 l5）。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | 小红书图文必须自研，yt-dlp 只给缩略图 | 自研 fetch 页面 → 定位 window.__INITIAL_STATE__ → 优先 note.noteDetailMap[note_id].note，取不到时回退 noteData.data.noteData → 读取 imageList，直接取原图地址；不复用 yt-dlp 的图片结果 | AC-001、AC-004 |
| C2 | 原图优先，不返回缩略图 | 每张图优先 urlDefault；缺失时取 infoList 中 imageScene=WB_DFT，再其次 CRD_WM_WEBP；都缺失则跳过该项；urlPre 等缩略字段不作为降级来源 | AC-002 |
| C3 | 保留 webp 原址，转码归 l3 | remoteUrl 原样返回，不拼接、不代理；needs_transcode 恒为 true | AC-002、AC-007 |
| C4 | xsec_token 必须真实拿到 | 依次取最终 URL 的 xsec_token 查询参数、note.xsecToken、state 顶层 xsecToken；都没有返回 NEED_XSEC_TOKEN，不猜测、不省略 | AC-006 |
| C5 | /parse 只解析不下载，零落盘 | 只读取 HTML 文本，不写磁盘；请求前后 /tmp 新增文件数为 0 | AC-011 |
| C6 | 返回包 ≤1000KB、items ≤100、整体 12s | 页面 HTML 上限 5MB；单次抓取 8s 超时映射为 504 TIMEOUT；items 不截断，由 l1 统一截到 100 | AC-012 |
| C7 | 失败可判定，不返回半截清单 | 所有失败都走 l1 共享错误信封，items 为空数组，日志与响应不带调用栈 | AC-005、AC-008 |
| C8 | 限流与缓存计数由 l7 观测 | 本湖定义解析缓存键与 TTL 并暴露进程内计数器；l7 只读这些计数，不重复实现解析缓存 | AC-009、AC-010 |

## Alignment Surface

本湖是 l1 解析框架内的小红书图文分支实现，接缝是 `container/app/parsers/xhs.py` 的 `configure_note_parser` / `parse_note(url, cookie)`。上游是 l1 的 /parse 路由与归一化，下游是 l3 的逐张转存（消费 needs_transcode 与 remoteUrl）。跨湖只读：不改 l3、l5 冻结正文，不改 l1 的请求与响应字段。

## Open Questions

| Q ID | Question | Recommendation | Status | Answer |
|------|----------|----------------|--------|--------|
| Q1 | 谁、什么问题、什么算完成？ | 小红书图文链接经 /parse 返回按序原图清单，缺 token 可判别 | answered | 派单 2026-11-09：图文返回 items 且 needs_transcode=true，缺 xsec_token 返回 NEED_XSEC_TOKEN，解析失败 PARSE_FAILED |
| Q2 | 短链展开归谁？ | l1 已有 expand_shortlink，l2 不重复实现 | answered | 经 /parse 的短链先由 l1 展开并校验规范页；l2 只在直连 parse_note 入口做最多 3 跳防御，失败返回 PARSE_FAILED |
| Q3 | NEED_XSEC_TOKEN 用什么状态码？ | 422，与 l1 的 SHORTLINK_FAIL 同档 | answered | 422 NEED_XSEC_TOKEN、retryable=true；提示用户重新分享带 token 的链接 |
| Q4 | 视频或无图笔记怎么处理？ | 视频归 l1 的 yt-dlp，l2 遇到一律失败 | answered | parse_note 收到视频或无图笔记返回 502 PARSE_FAILED，不返回空清单冒充成功 |
| Q5 | 解析缓存由谁定义？ | 本湖定义键与 TTL，l7 只读计数 | answered | 键 xhs:note:v1:<note_id>:<sha256(xsec_token)[:12]>，TTL XHS_NOTE_CACHE_TTL_S 默认 600s，只缓存成功结果 |
| Q6 | 10 条真实图文样本何时到位？ | 未采集就如实标 BLOCKED | answered | 本机现有真实小红书样本是视频笔记（1 项），图文样本待采集；TC-018 标 BLOCKED 并写解除条件 |

## Intent Coverage

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | 派单 AC3：图文返回 items、needs_transcode=true | tests.md TC-001、TC-011 |
| AC-002 | 约束 C1、C2、C3：原图优先、保持顺序、保留 webp 原址 | tests.md TC-002、TC-003 |
| AC-003 | 派单 AC1：短链跟进到最终笔记 URL | tests.md TC-013 |
| AC-004 | 约束 C1：定位 window.__INITIAL_STATE__ 与 imageList | tests.md TC-001、TC-009 |
| AC-005 | 派单 AC1、AC2：字段缺失、列表为空都不返回半成品 | tests.md TC-006、TC-007、TC-008、TC-009 |
| AC-006 | 派单 AC3：缺 xsec_token 返回 NEED_XSEC_TOKEN | tests.md TC-004、TC-005 |
| AC-007 | 派单 AC4：接 l1 /parse 契约，视频行为写死 | tests.md TC-010、TC-011 |
| AC-008 | 派单 AC5：错误码与 HTTP 状态固定 | tests.md TC-005、TC-006、TC-014 |
| AC-009 | 派单 AC6：缓存边界写死 | tests.md TC-012 |
| AC-010 | 派单 AC8：失败可观测，计数器字段名写清 | tests.md TC-012 |
| AC-011 | 派单 AC7：依赖边界、不重写 l1、不改冻结正文 | tests.md TC-015 |
| AC-012 | 约束 C6：8s 抓取预算与页面大小上限 | tests.md TC-016、TC-017 |

## Acceptance Criteria

每条 AC 都在容器上直接 curl 或直连模块复现。构造样本用 XHS_NOTE_HTTP_STUB 注入页面 HTML，真实样本未采集前不计通过。

| AC ID | Criterion |
|-------|-----------|
| AC-001 | POST /parse 传规范小红书图文链接（构造样本 3 张图）返回 200、ok=true、platform=xhs、content_type=note、item_count=3，items 三项 index 依次为 0、1、2，每项 type=image、remoteUrl 为非空 http(s) 原图地址、needs_transcode=true |
| AC-002 | imageList 顺序即 items 顺序；每张图优先 urlDefault，缺失时取 infoList 中 imageScene=WB_DFT，再其次 CRD_WM_WEBP；三项都缺失的条目被跳过且不计数；urlDefault 与 infoList 都缺失时才判该条不可用；所有条目都不可用返回 502 PARSE_FAILED；响应中不出现 urlPre、thumbnail 等缩略地址 |
| AC-003 | 直连 parse_note 传入 xhslink.com、xhslink.cn 短链时最多跟随 3 跳，落到 xiaohongshu.com 的 /explore/<id>、/discovery/item/<id> 规范页后继续解析；超过 3 跳、缺少 Location、落到站外域名、非规范页，任一情形返回 502 PARSE_FAILED，items 为空；经 /parse 的短链仍由 l1 expand_shortlink 负责，l2 不替换它的行为 |
| AC-004 | 从页面 HTML 中定位 window.__INITIAL_STATE__ 的赋值对象，按固定顺序取 note：第一步取 note.noteDetailMap[note_id].note，URL 的 note_id 在 map 中缺失但 map 只有一项时取该唯一项，map 有多项且无匹配时进入第二步；第二步取 noteData.data.noteData，其 noteId 与 URL 的 note_id 一致才采用；两处都取不到目标笔记返回 502 PARSE_FAILED |
| AC-005 | 页面无 window.__INITIAL_STATE__、初始状态 JSON 解析失败、两种结构（note.noteDetailMap 与 noteData.data.noteData）都取不到目标笔记、imageList 缺失、imageList 不是数组、imageList 为空数组，以上情形均返回 502、ok=false、error.code=PARSE_FAILED、retryable=true、items 为空数组，响应不带调用栈、异常类型 |
| AC-006 | xsec_token 依次取最终 URL 的 xsec_token 查询参数、note.xsecToken、state 顶层 xsecToken；三者都缺失时返回 422、ok=false、error.code=NEED_XSEC_TOKEN、retryable=true、items 为空数组；不得猜测 token、不得降级为缩略图、不得返回空地址 |
| AC-007 | 图文成功响应经 l1 归一化后 items[].index、type、remoteUrl、ext、cover、width、height、needs_transcode 字段齐全，needs_transcode 恒为 true，item_count 等于 items 长度；parse_note 收到视频笔记、无图笔记均返回 502 PARSE_FAILED，不返回空 items 冒充成功 |
| AC-008 | 本湖新增错误码 NEED_XSEC_TOKEN（422、retryable=true）；其余沿用 l1：INVALID_URL 400、INVALID_REQUEST 400、UNSUPPORTED_PLATFORM 400、SHORTLINK_FAIL 422、COOKIE_EXPIRED 503、PARSE_FAILED 502、TIMEOUT 504、RATE_LIMITED 429；失败信封固定为 ok=false、error.code、error.message、error.retryable、items 空数组、elapsed_ms 整数 |
| AC-009 | 解析缓存键为 xhs:note:v1:<note_id>:<sha256(xsec_token) 前 12 位>，TTL 由 XHS_NOTE_CACHE_TTL_S 控制、默认 600s、取值 0 表示禁用；只缓存成功结果；命中时不发上游请求且返回内容与首次一致；失败不写缓存 |
| AC-010 | 每次解析产出一条结构化日志，字段含 event=xhs_note_parse、note_id、image_count、xsec_token 取 present 与 missing 两值之一、cache 取 hit 与 miss 两值之一、elapsed_ms、code；进程内计数器为 xhs_note_parse_total{result=ok|need_xsec|failed}、xhs_note_cache_hit_total、xhs_note_cache_miss_total、xhs_note_images_total；日志与计数器不出现 token 原值；l7 从这些字段读取命中与失败计数 |
| AC-011 | 不改 l1 的 /parse 请求与成功响应字段、不改 l3 与 l5 冻结正文、不下载图片、不转码、不写 COS、不落盘；一次成功 /parse 请求前后容器 /tmp 新增文件数为 0 |
| AC-012 | 单次上游抓取超过 XHS_NOTE_TIMEOUT_S（默认 8s）返回 504 TIMEOUT、retryable=true；页面 HTML 超过 XHS_NOTE_MAX_BYTES（默认 5242880 字节）返回 502 PARSE_FAILED；items 不截断，由 l1 统一截到 100 |

## 接口契约

### POST /parse（不变）

请求体仍是 {"url": "..."}，出现 cookie 字段返回 400 INVALID_REQUEST；小红书图文成功响应的字段与 l1 冻结契约完全一致：

```json
{
  "ok": true,
  "platform": "xhs",
  "content_type": "note",
  "source_url": "https://xhslink.com/a/XXXX",
  "resolved_url": "https://www.xiaohongshu.com/explore/6a0000000000000000000001?xsec_token=tok",
  "title": "标题文本",
  "item_count": 3,
  "elapsed_ms": 640,
  "items": [
    {
      "index": 0,
      "type": "image",
      "remoteUrl": "https://sns-img-qc.xhscdn.com/a.webp",
      "ext": "webp",
      "cover": "",
      "width": 1080,
      "height": 1440,
      "needs_transcode": true
    }
  ]
}
```

### 内部接缝 parse_note

l1 的 xhs 分支通过 configure_note_parser 注入本湖实现，签名与返回约定：

```python
async def parse_note(url: str, cookie: str) -> dict:
    """返回 {"note_id": str, "title": str, "xsec_token": str, "items": [{"index": int, "remoteUrl": str, "ext": str, "cover": str, "width": int|None, "height": int|None, "type": "image", "needs_transcode": True}]}"""
```

- 只接收规范笔记页 URL 与运营方 cookie 字符串；不读用户 cookie。
- 成功后 items 至少 1 项；失败抛 ApiError，不返回部分条目。
- l1 的 _note_payload 会再次强制 needs_transcode=true 并保留 webp 原址，两处口径一致。

### 错误码

| code | HTTP | 触发条件 | retryable | 来源 |
|------|------|----------|-----------|------|
| INVALID_URL | 400 | url 为空、非 http(s)、超长 | false | l1 |
| INVALID_REQUEST | 400 | 请求体非对象、含 cookie 字段 | false | l1 |
| UNSUPPORTED_PLATFORM | 400 | 域名不在抖音与小红书白名单 | false | l1 |
| SHORTLINK_FAIL | 422 | /parse 的短链 3 跳后仍未到规范页 | true | l1 |
| NEED_XSEC_TOKEN | 422 | URL query、note.xsecToken、state 顶层三者都没有 token | true | l2 新增 |
| COOKIE_EXPIRED | 503 | 运营方 cookie 失效 | true | l1 |
| PARSE_FAILED | 502 | 页面结构变化、初始状态缺失、imageList 空、视频或无图笔记、抓取不完整 | true | l1 与 l2 共用 |
| TIMEOUT | 504 | 单次抓取超过 XHS_NOTE_TIMEOUT_S | true | l1 与 l2 共用 |
| RATE_LIMITED | 429 | 单 IP 每分钟超过 20 次 | true | l1，l7 复核 |

## 提取规则

| 项 | 规则 |
|----|------|
| 页面抓取 | GET 规范笔记页，移动端 UA，运营方 cookie；跟随重定向时最多 3 跳并校验最终主机在白名单内 |
| 初始状态定位 | 在 HTML 中查找 window.__INITIAL_STATE__ 的赋值表达式，从第一个 { 起用 JSON 解码器读取完整对象，允许属性名带引号与不带引号两种写法 |
| note 定位 | 优先 state.note.noteDetailMap[note_id].note；缺失时回退 state.noteData.data.noteData；note_id 取最终 URL 的最后一段路径，去掉查询串 |
| 唯一项兜底 | note_id 在 map 中缺失且 map 恰好一项时取该唯一项；多项且无匹配判 PARSE_FAILED |
| 图片列表 | note.imageList 必须是数组且非空；顺序即输出顺序，index 从 0 连续递增 |
| 原图字段 | 依次取 urlDefault、infoList 中 imageScene 为 WB_DFT 的 url、imageScene 为 CRD_WM_WEBP 的 url；三者都缺失则跳过该条目 |
| 地址校验 | remoteUrl 必须是非空 http(s) 地址；不拼接、不代理、不替换主机 |
| 扩展名 | 取 remoteUrl 路径扩展名并小写；无扩展名默认 webp |
| 尺寸 | 取 imageList 条目的 width、height，缺失写 null |
| 标题 | note.title，其次 note.desc，都没有写空字符串 |
| 顺序与重复 | 保持 imageList 原顺序；相同地址不自动去重，由 l1 统一处理上限 |

## 缓存与观测

| 项 | 规则 |
|----|------|
| 缓存键 | xhs:note:v1:<note_id>:<sha256(xsec_token).hexdigest()[:12]> |
| 缓存 TTL | XHS_NOTE_CACHE_TTL_S 默认 600s，0 表示禁用 |
| 缓存内容 | 成功结果的 items、title、xsec_token 的完整副本；命中后返回同样字段 |
| 缓存写入 | 只在解析完全成功后写入；失败与 NEED_XSEC_TOKEN 不写 |
| 日志字段 | event、note_id、image_count、xsec_token、cache、elapsed_ms、code |
| 计数器 | xhs_note_parse_total{result=ok|need_xsec|failed}、xhs_note_cache_hit_total、xhs_note_cache_miss_total、xhs_note_images_total |
| 脱敏 | 日志与计数器只写 xsec_token=present 或 missing，不写 token 原值 |

## 限额与配置

| 名称 | 默认值 | 含义 |
|------|--------|------|
| XHS_NOTE_TIMEOUT_S | 8 | 单次页面抓取超时，超时映射 504 TIMEOUT |
| XHS_NOTE_CACHE_TTL_S | 600 | 解析缓存 TTL，0 为禁用 |
| XHS_NOTE_MAX_BYTES | 5242880 | 页面 HTML 字节上限 |
| XHS_NOTE_MAX_HOPS | 3 | 直连短链最多跳转次数 |
| XHS_NOTE_UA | 移动端 web UA | 抓取页面的 User-Agent |
| XHS_NOTE_HTTP_STUB | 空 | 仅测试：JSON 文件把 URL 映射到构造响应，未覆盖的 URL 判 PARSE_FAILED |
| PARSE_XHS_SKIP_YTDLP | 0 | 仅测试：1 时 l1 的 xhs 分支跳过 yt-dlp，直接进入图文解析 |

## 样本登记

真实样本待采集，构造样本只用于结构回归，不冒充真实样本。

| 槽位 | 类型 | 状态 |
|------|------|------|
| XHS_NOTE_REAL_01 至 XHS_NOTE_REAL_10 | 小红书图文，每篇至少 2 张图，含 xsec_token | 待采集 |
| XHS_SHORT_REAL_01 | 小红书图文短链分享 | 待采集 |

## 本地验收方式

```bash
# 1. 构造样本桩：把 URL 映射到本地 HTML 文件
export XHS_NOTE_HTTP_STUB=/tmp/xhs-stub/stub.json
export PARSE_XHS_SKIP_YTDLP=1

# 2. 起服务（与 tests.md 同一进程与端口）
cd /Users/apple/Developer/Personal/renlink/container
PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099

# 3. curl 构造图文链接
curl -sS -X POST localhost:18099/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000001?xsec_token=tok-001"}' \
  | tee /tmp/xhs-001.json
jq -e '.ok == true and .content_type == "note" and .item_count == 3' /tmp/xhs-001.json

# 4. 缺 token 的构造页
curl -sS -X POST localhost:18099/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000004"}' \
  -o /tmp/xhs-002.json -w '%{http_code}\n'
jq -e '.error.code == "NEED_XSEC_TOKEN"' /tmp/xhs-002.json
```

## 依赖与接缝

| 依赖 | 方向 | 接缝定义 | 本湖责任 |
|------|------|----------|----------|
| l1-parser-core | l2 填 l1 分支 | xhs.py 的 configure_note_parser 与 parse_note(url, cookie)；/parse 字段、错误信封、归一化与截断不变 | 提供 parse_note 实现与错误码注册 |
| l1 错误表 | l2 扩展 | container/app/errors.py 的 ERROR_SPECS 增加 NEED_XSEC_TOKEN 422 | 只加一个枚举，不改既有码 |
| l3-media-delivery | l3 消费 l2 | items[].remoteUrl 保持 webp 原址、needs_transcode=true；l3 按 index 逐张转存 | 只提供清单，不下载不转码 |
| l5-miniprogram-pages | l5 消费 l1/l2 | items 顺序即页面展示顺序；每项可直接显示与逐张保存 | 不改页面，不新增字段 |
| l7-risk-compliance | l7 读 l2 计数 | xhs_note_* 计数器与 event=xhs_note_parse 日志字段；缓存键与 TTL 由 l2 定义 | 暴露计数，不实现限流 |
| yt-dlp | l1 既有 | xhs 视频仍由 yt-dlp XiaoHongShuIE；l2 只在视频结果为空时被调用 | 不接管视频 |
