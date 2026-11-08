---
slug: l1-parser-core
version: v0.1.0
materials_status: current
test_source: acceptance_criteria
env: container-http
---

# Tests: l1-parser-core

执行入口统一是 `ops/smoke.py`：它读环境变量里的样本链接，发真实 HTTP 请求，按下面的判据断言，并把每次结果写成 JSON 存进 `evidence/l1/`。用例标记 BLOCKED 之前的样本状态是待采集，待采集的用例不计通过，也不算失败。

## 前置条件

```bash
export PARSE_BASE="https://container-host"
export DY_VIDEO_1="抖音视频样本 A"
export DY_VIDEO_2="抖音视频样本 B"
export DY_NOTE_1="抖音图文样本 A"
export DY_NOTE_2="抖音图文样本 B"
export XHS_VIDEO_1="小红书视频样本 A"
export XHS_VIDEO_2="小红书视频样本 B"
export DY_SHORT_1="抖音短链样本 A"
export XHS_SHORT_1="小红书短链样本 B"
```

构造类用例额外使用：

```bash
export PARSE_UPSTREAM_DELAY_MS=13000
```

抖音 Argus 分支与 Obscura 回退的注入开关（TC-019 ~ TC-024 分别对应一组启动环境变量）：

```bash
export RENLINK_DROP_ARGUS_HEADER=1        # TC-021：去掉 x-tt-argus，复现上游 403
export RENLINK_PLAY_ADDR_TTL_S=600        # play_addr 缓存，默认 600 秒
export ENABLE_OBSCURA=0                   # 通用渲染回退，默认关闭；抖音分支无论开关都不使用
export PLAYWRIGHT_CDP=ws://127.0.0.1:9222 # 启用 Obscura 后应用侧 CDP 接入地址
export RENLINK_RENDER_WAIT_MS=8000        # Obscura 渲染预算，默认 8000
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | e2e | `python3 ops/smoke.py --case dy-video-1` | 200 且 items 长度 1 且 remoteUrl 非空且 ext=mp4 |
| AC-001 | TC-002 | e2e | `python3 ops/smoke.py --case dy-video-2` | 200 且 items 长度 1 且 remoteUrl 非空且 ext=mp4 |
| AC-002 | TC-003 | e2e | `python3 ops/smoke.py --case dy-note-1` | content_type=note 且 item_count 等于页面张数且每项 remoteUrl 非空 |
| AC-002 | TC-004 | e2e | `python3 ops/smoke.py --case dy-note-2` | content_type=note 且 item_count 等于页面张数且每项 remoteUrl 非空 |
| AC-003 | TC-005 | e2e | `python3 ops/smoke.py --case xhs-video-1` | platform=xhs 且 content_type=video 且 items 长度 1 且 remoteUrl 非空 |
| AC-003 | TC-006 | e2e | `python3 ops/smoke.py --case xhs-video-2` | platform=xhs 且 content_type=video 且 items 长度 1 且 remoteUrl 非空 |
| AC-004 | TC-007 | e2e | `python3 ops/smoke.py --case dy-short-1` | resolved_url 命中 douyin.com 的 video 路径且清单字段齐全 |
| AC-004 | TC-008 | e2e | `python3 ops/smoke.py --case xhs-short-1` | resolved_url 命中 xiaohongshu.com 的规范路径 |
| AC-005 | TC-009 | negative | `python3 ops/smoke.py --case cookie-expired` | 503 且 error.code=COOKIE_EXPIRED 且 items 为空数组 |
| AC-006 | TC-010 | negative | `python3 ops/smoke.py --case shortlink-fail` | 422 且 error.code=SHORTLINK_FAIL 且 resolved_url 为空字符串 |
| AC-007 | TC-011 | negative | `python3 ops/smoke.py --case invalid-url` | 400 且 error.code=INVALID_URL |
| AC-008 | TC-012 | negative | `python3 ops/smoke.py --case unsupported-platform` | 400 且 error.code=UNSUPPORTED_PLATFORM |
| AC-009 | TC-013 | negative | `python3 ops/smoke.py --case timeout` | 504 且 error.code=TIMEOUT 且耗时小于 15s |
| AC-010 | TC-014 | contract | `python3 ops/smoke.py --case size-cap` | 响应体不大于 1024000 字节且 items 不大于 100 且无 base64 键 |
| AC-011 | TC-015 | contract | `python3 ops/smoke.py --case field-contract` | 四类响应必填字段齐全且类型固定且 index 连续 |
| AC-012 | TC-016 | behavior | `python3 ops/smoke.py --case no-download` | /tmp 文件数不变且响应无 cloudID 键 |
| AC-013 | TC-017 | negative | `python3 ops/smoke.py --case user-cookie` | 400 且 error.code=INVALID_REQUEST |
| AC-014 | TC-018 | contract | `python3 ops/smoke.py --case health` | 200 且 ok=true 且两平台 cookie_status 字段存在 |
| AC-015 | TC-019 | e2e | `python3 ops/smoke.py --case dy-argus-1` | 抖音真实链接补齐 Argus 头与 a_bogus/msToken 后 200、ok=true、items 长度 1、remoteUrl 为非空 play_addr |
| AC-015 | TC-020 | e2e | `python3 ops/smoke.py --case dy-argus-stability` | 同一链接连跑 3 次均 200，3 次 remoteUrl 均非空 |
| AC-016 | TC-021 | negative | `python3 ops/smoke.py --case dy-argus-missing-header` | 去掉 x-tt-argus 时上游 403，/parse 502 PARSE_FAILED retryable=true 且 items 为空数组 |
| AC-016 | TC-022 | negative | `python3 ops/smoke.py --case dy-argus-timeout` | 抖音上游超过 12s 时 504 TIMEOUT 且响应无半截 items，全程不起浏览器 |
| AC-017 | TC-023 | e2e | `python3 ops/smoke.py --case obscura-xhs-render` | ENABLE_OBSCURA=1 时 Obscura 渲染小红书笔记页成功，标题正确且含 xsec_token |
| AC-017 | TC-024 | behavior | `python3 ops/smoke.py --case douyin-no-obscura` | Obscura 开启时抖音 /parse 仍由 Argus 直连返回 play_addr，Obscura 无抖音页面请求，无浏览器进程 |

## 用例明细

### TC-001 / TC-002 抖音视频

- 输入：DY_VIDEO_1、DY_VIDEO_2 两条真实分享链接，分别单发。
- 期望响应：

```json
{"ok": true, "platform": "douyin", "content_type": "video",
 "items": [{"index": 0, "type": "video", "remoteUrl": "https://...", "ext": "mp4"}],
 "item_count": 1}
```

- 通过判据：HTTP 200；items 长度等于 1；remoteUrl 以 http 开头且能直接 GET 到 200 与 video 内容类型；ext 等于 mp4；item_count 等于 1。
- 手工复核：用列表里的 remoteUrl 在浏览器或 curl 打一次，确认能播放。

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_VIDEO_1\"}" | jq .
```

### TC-003 / TC-004 抖音图文

- 输入：DY_NOTE_1、DY_NOTE_2 两条真实图文链接，分别单发。
- 期望响应：content_type=note；items 每项 type=image；remoteUrl 非空。
- 通过判据：item_count 等于页面上滑出的图片张数；items 长度等于 item_count；每项 remoteUrl 能直接 GET 到 200；每项 index 从 0 连续。
- 反例判据：出现任何一项 type=video 判失败；item_count 大于 items 长度判失败。

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_NOTE_1\"}" | jq '{item_count, got: (.items|length), types: [.items[].type]}'
```

### TC-005 / TC-006 小红书视频

- 输入：XHS_VIDEO_1、XHS_VIDEO_2 两条真实视频笔记链接。
- 期望响应：platform=xhs；content_type=video；items 长度 1；remoteUrl 非空。
- 通过判据：HTTP 200；remoteUrl 能直接 GET 到 200 与 video 内容类型；ext 等于 mp4。
- 说明：xhs 视频用 yt-dlp XiaoHongShuIE 取播放地址；本条不要求图片能力。

### TC-007 抖音短链

- 输入：DY_SHORT_1，形如 v.douyin.com 分享短链。
- 通过判据：HTTP 200；resolved_url 命中 `^https://www\.douyin\.com/(video|note)/[0-9]+`；清单字段与同类型长链一致；source_url 保留用户原始短链。
- 重定向判据：跟踪不超过 3 跳。

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$DY_SHORT_1\"}" | jq -e '.resolved_url, .source_url'
```

### TC-008 小红书短链

- 输入：XHS_SHORT_1，形如 xhslink.com 分享短链。
- 通过判据：HTTP 200；resolved_url 命中 xiaohongshu.com 的 explore 或 discovery 规范路径；platform=xhs；清单字段齐全。

### TC-009 COOKIE_EXPIRED

- 前置：运营把 cookie 池里的 douyin cookie 换成过期值并热加载（l4 刷新脚本负责写入）。
- 输入：DY_VIDEO_1。
- 期望响应：

```json
{"ok": false, "items": [], "error": {"code": "COOKIE_EXPIRED", "retryable": true}}
```

- 通过判据：HTTP 503；error.code 等于 COOKIE_EXPIRED；items 是空数组；响应里不出现 cookie 原值。
- 反例判据：返回 200 加空清单判失败，返回半份清单判失败。

### TC-010 SHORTLINK_FAIL

- 输入：`{"url":"https://v.douyin.com/0000000/"}`，这是构造的失效短链，不冒充真实样本。
- 通过判据：HTTP 422；error.code 等于 SHORTLINK_FAIL；resolved_url 为空字符串；items 为空数组；总耗时小于 15s。

```bash
curl -sS -o /tmp/r.json -w '%{http_code}' -X POST "$PARSE_BASE/parse" \
  -H 'content-type: application/json' -d '{"url":"https://v.douyin.com/0000000/"}'
jq . /tmp/r.json
```

### TC-011 INVALID_URL

- 输入三组：空字符串、`not-a-url`、长度 3000 的字符串。
- 通过判据：三组都返回 HTTP 400 与 error.code=INVALID_URL；不发起任何上游请求；耗时小于 500ms。

### TC-012 UNSUPPORTED_PLATFORM

- 输入：`https://www.bilibili.com/video/BV1xx411c7mD`、`https://weibo.com/1/abc`、`https://youtu.be/abc`。
- 通过判据：三组都返回 HTTP 400 与 error.code=UNSUPPORTED_PLATFORM；不发起任何上游请求。
- 说明：这三个平台属于明确非目标，白名单之外一律拒绝。

### TC-013 TIMEOUT

- 前置：设置 PARSE_UPSTREAM_DELAY_MS=13000 注入上游延迟，模拟弱网与反爬拖延。
- 输入：DY_VIDEO_1。
- 通过判据：HTTP 504；error.code 等于 TIMEOUT；从发出请求到收到响应的墙钟时间小于 15s；进程没有残留协程。
- 说明：延迟注入开关只在测试环境生效，生产环境默认关闭。

### TC-014 体积与条目上限

- 输入：图片最多的图文样本 XHS_NOTE_MAX；同时用脚本构造 120 项清单验证截断。
- 通过判据：响应字节数不大于 1024000；items 长度不大于 100；响应里没有 base64 键；没有文件流字段；item_count 等于实际返回的 items 长度，截断时带 truncated=true。

```bash
curl -sS -X POST "$PARSE_BASE/parse" -H 'content-type: application/json' \
  -d "{\"url\":\"$XHS_NOTE_MAX\"}" -o /tmp/big.json -w '%{size_download}\n'
jq '{items: (.items|length), truncated}' /tmp/big.json
```

### TC-015 字段契约

- 输入：四类成功样本各一条。
- 通过判据：每条响应都满足下面的类型断言；errors 为空。
- 断言脚本：ops/smoke.py 内置 jsonschema 校验，schema 存在 contract/parse_response.schema.json。

```bash
jq -e '(.ok|type)=="boolean" and (.platform|type)=="string" and (.content_type|type)=="string"
  and (.source_url|type)=="string" and (.resolved_url|type)=="string" and (.title|type)=="string"
  and (.item_count|type)=="number" and (.elapsed_ms|type)=="number" and (.items|type)=="array"
  and ([.items[].index] == [range(0; .item_count)])' /tmp/r.json
```

### TC-016 零落盘与无下载

- 输入：DY_VIDEO_1。
- 步骤：记录容器 /tmp 文件清单，发一次 /parse，再记录一次。
- 通过判据：两次文件清单一致；响应不含 cloudID 键；容器出网日志里没有对媒体 CDN 的 GET（只有页面与接口请求）；CObject 存储的桶在请求期间没有新增对象。

```bash
docker exec CONTAINER_ID sh -c 'find /tmp -type f | sort' > /tmp/before.txt
python3 ops/smoke.py --case dy-video-1
docker exec CONTAINER_ID sh -c 'find /tmp -type f | sort' > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt
```

### TC-017 用户 cookie 被拒

- 输入：`{"url":"https://v.douyin.com/XXXXXXX/","cookie":"sessionid=1"}`。
- 通过判据：HTTP 400；error.code 等于 INVALID_REQUEST；服务端日志不出现 sessionid 值；请求不进入解析分支。

### TC-018 健康探针

- 输入：GET /health。
- 通过判据：HTTP 200；ok=true；platforms.douyin 与 platforms.xhs 都有 cookie_status；cookie 失效时对应值为 expired；响应时间小于 200ms。

```bash
curl -sS "$PARSE_BASE/health" | jq -e '.ok==true and .platforms.douyin.cookie_status and .platforms.xhs.cookie_status'
```

### TC-019 抖音真实链接 Argus 直连

- 输入：DY_VIDEO_1（此前服务端直连 detail API 返回 403 的真实链接）。
- 通过判据：HTTP 200；ok=true；content_type=video；items 长度 1；items[0].remoteUrl 为非空 http(s) play_addr；响应体不含 base64、文件流或本地路径；elapsed_ms 小于 12000。
- 说明：请求带 x-tt-argus、uifid 头与 uifid/verifyFp/fp 参数，并带 f2 生成的 a_bogus、msToken；全程不起浏览器。

```bash
/usr/bin/time -p python3 ops/smoke.py --case dy-argus-1
```

### TC-020 连跑 3 次稳定性

- 前置：同一真实链接连续请求 3 次，间隔数秒。
- 通过判据：3 次都是 HTTP 200 且 ok=true；3 次 items[0].remoteUrl 均非空；任一次失败即不通过。
- 说明：这是对 Argus 参数组合稳定性的直接验证，不依赖缓存命中（可用不同 aweme_id 或先清缓存）。

### TC-021 缺 x-tt-argus → 上游 403

- 输入：DY_VIDEO_1，进程带 RENLINK_DROP_ARGUS_HEADER=1（或代码路径去掉该头）。
- 通过判据：上游 detail API 返回 403 且响应体含 Blocked by ArgusSecurityPlugin；/parse 返回 HTTP 502；ok=false；error.code=PARSE_FAILED；error.retryable=true；items 为空数组；响应里没有半截 items。
- 说明：这个用例证明 403 是缺 Argus 头造成的，也证明缺失时整请求失败，不会让调用方存半份清单。

### TC-022 抖音上游超时

- 输入：DY_VIDEO_1，进程注入 PARSE_UPSTREAM_DELAY_MS=13000（或让 Argus 上游挂起到超过 12s）。
- 通过判据：HTTP 504；error.code=TIMEOUT；items 为空数组；从发出请求到收到响应小于 15s；抖音分支无浏览器进程、无 Obscura 连接。
- 说明：抖音不做渲染兜底；超时与失败分开返回，调用方按 retryable 决定是否重试。

### TC-023 Obscura 渲染小红书页

- 输入：ENABLE_OBSCURA=1 启动容器（镜像含 obscura，且 `obscura serve --port 9222 --stealth` 已就绪），传入 XHS 笔记链接；应用侧用 PLAYWRIGHT_CDP=ws://127.0.0.1:9222 走 new_context() 渲染。
- 通过判据：渲染出的页面标题与笔记标题一致；页面内容含 xsec_token；渲染完成后 obscura 进程仍存活（未因 browser.close() 退出）；/parse 不因此新增落盘文件。
- 说明：Obscura 只是通用渲染回退的接入验证，不改变抖音主路径。

### TC-024 抖音不经 Obscura

- 输入：ENABLE_OBSCURA=1 且 obscura server 正常，传 DY_VIDEO_1 到 /parse。
- 通过判据：/parse 返回 200、ok=true、items[0].remoteUrl 为非空 play_addr；同时段 obscura 日志与 CDP 会话中没有抖音页面请求；容器内没有为抖音拉起浏览器进程。
- 说明：证明 Obscura 开启不会把抖音带回渲染路径，抖音始终走 Argus HTTP 直连。

## 证据留存

每个用例执行后，ops/smoke.py 把请求、响应状态、响应体、耗时写入 evidence/l1/ 下的 JSON，命名与用例 ID 一致。样本链接在日志里只保留前 32 个字符，避免外泄。
