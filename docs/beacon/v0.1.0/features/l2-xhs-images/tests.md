---
slug: l2-xhs-images
version: v0.1.0
materials_status: current
test_source: acceptance_criteria
env: container-http
---

# Tests: l2-xhs-images

主执行方式是 curl 打 /`parse`，构造样本由 `XHS_NOTE_HTTP_STUB` 注入页面 HTML，不需要访问真实小红书；真实图文样本按 BLOCKED 表登记。结果按本轮复跑起始时间建目录落盘，例如 `evidence/run-20261109-0700/case-*.json`。

## 前置条件

```bash
export PARSE_BASE="http://127.0.0.1:18099"
export XHS_COOKIE="web_session=test-only"
export XHS_NOTE_HTTP_STUB=/tmp/xhs-fixtures/stub.json
export PARSE_XHS_SKIP_YTDLP=1

python3 - <<'PY'
import json, pathlib

root = pathlib.Path("/tmp/xhs-fixtures")
root.mkdir(parents=True, exist_ok=True)
ids = {n: "6a00000000000000000000%02d" % n for n in range(1, 14)}
files = {}

def write(name, body):
    path = root / (name + ".html")
    path.write_text(body, encoding="utf-8")
    return str(path)

def note_data_html(note_id, note):
    state = {"noteData": {"data": {"noteData": dict(note, noteId=note_id)}}}
    return "<html><body><script>window.__INITIAL_STATE__ = " + json.dumps(state, ensure_ascii=False) + "</script></body></html>"

def state_html(note_id, note, with_state=True, raw=None):
    parts = ['<html><body><div id="app"></div>']
    if raw is not None:
        parts.append("<script>window.__INITIAL_STATE__ = " + raw + "</script>")
    elif with_state:
        state = {"note": {"firstNoteId": note_id, "noteDetailMap": {}}}
        if note is not None:
            state["note"]["noteDetailMap"][note_id] = {"note": note}
        parts.append("<script>window.__INITIAL_STATE__ = " + json.dumps(state, ensure_ascii=False) + "</script>")
    parts.append("</body></html>")
    return "".join(parts)

def image(url_default=None, info=None, extra=None):
    item = {}
    if url_default:
        item["urlDefault"] = url_default
    if info:
        item["infoList"] = info
    if extra:
        item.update(extra)
    return item

files[1] = write("case-001", state_html(ids[1], {
    "title": "构造样本-3图", "xsecToken": "tok-001",
    "imageList": [
        image("https://sns-img-qc.xhscdn.com/a.webp", extra={"width": 1080, "height": 1440}),
        image("https://sns-img-qc.xhscdn.com/b.webp", extra={"width": 1080, "height": 1440}),
        image("https://sns-img-qc.xhscdn.com/c.webp", extra={"width": 1080, "height": 1440}),
    ],
}))
files[2] = write("case-002", state_html(ids[2], {
    "title": "构造样本-原图回退", "xsecToken": "tok-002",
    "imageList": [
        image("https://sns-img-qc.xhscdn.com/d.webp"),
        image(info=[{"url": "https://sns-img-qc.xhscdn.com/e-wb.webp", "imageScene": "WB_DFT"}]),
        image(info=[{"url": "https://sns-img-qc.xhscdn.com/f-crd.webp", "imageScene": "CRD_WM_WEBP"}]),
        image(extra={"urlPre": "https://sns-img-qc.xhscdn.com/g-pre.webp"}),
    ],
}))
files[3] = write("case-003", state_html(ids[3], {
    "title": "构造样本-state-token", "xsecToken": "tok-003",
    "imageList": [image("https://sns-img-qc.xhscdn.com/h.webp")],
}))
files[4] = write("case-004", state_html(ids[4], {
    "title": "构造样本-无token",
    "imageList": [image("https://sns-img-qc.xhscdn.com/i.webp")],
}))
files[5] = write("case-005", state_html(ids[5], None, with_state=False))
files[6] = write("case-006", state_html(ids[6], None, raw="{oops"))
files[7] = write("case-007", state_html(ids[7], {"xsecToken": "tok-007", "imageList": []}))
files[8] = write("case-008", state_html(ids[8], None))
files[9] = write("case-009", state_html(ids[9], {"xsecToken": "tok-009", "video": {"media": {"stream": {}}}}))
files[10] = write("case-010", state_html(ids[10], {
    "xsecToken": "tok-010",
    "imageList": [
        image("https://sns-img-qc.xhscdn.com/j.webp"),
        image("https://sns-img-qc.xhscdn.com/k.webp"),
    ],
}))
files[11] = write("case-011", state_html(ids[11], {
    "title": "构造样本-契约", "desc": "描述兜底", "xsecToken": "tok-011",
    "imageList": [image("https://sns-img-qc.xhscdn.com/l.webp", extra={"width": 720, "height": 1080})],
}))
files[12] = write("case-012", state_html(ids[12], {
    "xsecToken": "tok-012", "imageList": [image("https://sns-img-qc.xhscdn.com/m.webp")],
}))
files[13] = write("case-013", "<html><body>" + ("x" * 5242881) + "</body></html>")

tokens = {1: "tok-001", 2: "tok-002", 3: None, 4: None, 5: "tok-005", 6: "tok-006",
          7: "tok-007", 8: "tok-008", 9: "tok-009", 10: "tok-010", 11: "tok-011",
          12: "tok-012", 13: "tok-013"}
stub = {}
for n, token in tokens.items():
    url = "https://www.xiaohongshu.com/explore/" + ids[n]
    if token:
        url += "?xsec_token=" + token
    stub[url] = {"status": 200, "body_file": files[n]}
    if n == 12:
        stub[url]["delay_ms"] = 9000

stub["https://xhslink.com/a/ok"] = {"status": 302, "location": "https://www.xiaohongshu.com/explore/" + ids[1] + "?xsec_token=tok-001"}
stub["https://xhslink.com/a/loop"] = {"status": 302, "location": "https://xhslink.com/a/loop"}

root.joinpath("stub.json").write_text(json.dumps(stub, ensure_ascii=False, indent=1), encoding="utf-8")
print("fixtures:", len(stub), "entries")
PY

cd /Users/apple/Developer/Personal/renlink/container
XHS_COOKIE="$XHS_COOKIE" XHS_NOTE_HTTP_STUB="$XHS_NOTE_HTTP_STUB" \
  PARSE_XHS_SKIP_YTDLP="$PARSE_XHS_SKIP_YTDLP" PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18099 > /tmp/xhs-server.log 2>&1 &
sleep 2
curl -sS "$PARSE_BASE/health" | jq -e '.ok == true'
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | e2e | curl /parse 构造 3 图页 | 200、note、count=3、index 0/1/2、needs_transcode=true |
| AC-002 | TC-002、TC-003 | behavior | 构造 4 图页，含 urlDefault 缺失与仅 urlPre 项 | count=3、顺序保持、只用原图字段、缩略图不出现 |
| AC-003 | TC-013 | behavior | 直连 parse_note 传短链桩 | 3 跳内成功落到规范页；自环短链 PARSE_FAILED |
| AC-004 | TC-001、TC-009 | behavior | 构造 noteDetailMap 页、noteData 页与两种结构都无目标笔记的页 | 两种结构都能命中 note；都取不到返回 PARSE_FAILED |
| AC-005 | TC-006 至 TC-009 | negative | 无 state、坏 JSON、空列表、两种结构都取不到目标笔记 | 均 502 PARSE_FAILED、items 为空 |
| AC-006 | TC-004、TC-005 | negative | URL 无 token 但 state 有；两处都无 | 前者 200；后者 422 NEED_XSEC_TOKEN |
| AC-007 | TC-010、TC-011 | contract | 视频笔记；单图契约 | 视频 502；字段齐全、needs_transcode=true |
| AC-008 | TC-005、TC-006、TC-014 | negative | 缺 token、结构失败、cookie 字段、站外域名 | 错误码与信封固定 |
| AC-009 | TC-012 | behavior | 同一 URL 连打两次并查日志 | 第二次 cache=hit 且内容一致 |
| AC-010 | TC-012 | behavior | 查日志与计数器字段 | event、note_id、image_count、cache 齐 |
| AC-011 | TC-015 | governance | 成功解析前后 /tmp 文件列表 | 无新增文件 |
| AC-012 | TC-016、TC-017 | negative | 桩延迟 9s；5MB 页面 | 504 TIMEOUT；502 PARSE_FAILED |
| AC-006 | TC-018 | real-sample | 10 条真实图文样本 | BLOCKED，待采集 |

## 用例明细

### TC-001 三图成功

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000001?xsec_token=tok-001"}' \
  -o /tmp/xhs-001.json -w '%{http_code}\n'
jq -e '.ok == true and .platform == "xhs" and .content_type == "note" and .item_count == 3' /tmp/xhs-001.json
jq -e '[.items[].index] == [0,1,2] and ([.items[].type] | unique) == ["image"] and ([.items[].needs_transcode] | unique) == [true]' /tmp/xhs-001.json
jq -e '[.items[].remoteUrl] == ["https://sns-img-qc.xhscdn.com/a.webp","https://sns-img-qc.xhscdn.com/b.webp","https://sns-img-qc.xhscdn.com/c.webp"]' /tmp/xhs-001.json
```

判据：HTTP 200；platform=xhs、content_type=note、count=3；三张图顺序与 imageList 一致；每项 needs_transcode=true。同一份 note 分别以 note.noteDetailMap 与 noteData.data.noteData 两种页面结构注入，两次结果一致。

### TC-002 原图字段回退与顺序

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000002?xsec_token=tok-002"}' \
  -o /tmp/xhs-002.json -w '%{http_code}\n'
jq -e '.ok == true and .item_count == 3' /tmp/xhs-002.json
jq -e '[.items[].remoteUrl] == ["https://sns-img-qc.xhscdn.com/d.webp","https://sns-img-qc.xhscdn.com/e-wb.webp","https://sns-img-qc.xhscdn.com/f-crd.webp"]' /tmp/xhs-002.json
```

判据：urlDefault 优先；缺失时取 WB_DFT，再取 CRD_WM_WEBP；顺序与 imageList 一致。

### TC-003 缩略图不降级

```bash
jq -e '[.items[].remoteUrl | select(test("pre|thumb"))] | length == 0' /tmp/xhs-002.json
jq -e '[.items[].remoteUrl] | index("https://sns-img-qc.xhscdn.com/g-pre.webp") == null' /tmp/xhs-002.json
```

判据：只有 urlPre 的第 4 项被跳过；响应中不出现任何缩略图地址。

### TC-004 URL 无 token、state 有 token

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000003"}' \
  -o /tmp/xhs-003.json -w '%{http_code}\n'
jq -e '.ok == true and .item_count == 1 and .items[0].remoteUrl == "https://sns-img-qc.xhscdn.com/h.webp"' /tmp/xhs-003.json
```

判据：HTTP 200，state 内 note.xsecToken 被采用。

### TC-005 缺 xsec_token

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000004"}' \
  -o /tmp/xhs-004.json -w '%{http_code}')
[ "$code" = "422" ]
jq -e '.ok == false and .error.code == "NEED_XSEC_TOKEN" and .error.retryable == true and .items == []' /tmp/xhs-004.json
jq -e '.resolved_url == "https://www.xiaohongshu.com/explore/6a0000000000000000000004"' /tmp/xhs-004.json
```

判据：HTTP 422；NEED_XSEC_TOKEN；items 空数组；不返回任何图片地址。

### TC-006 无初始状态

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000005?xsec_token=tok-005"}' \
  -o /tmp/xhs-005.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED" and .items == []' /tmp/xhs-005.json
```

判据：HTTP 502、PARSE_FAILED、items 空。

### TC-007 初始状态 JSON 损坏

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000006?xsec_token=tok-006"}' \
  -o /tmp/xhs-006.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED" and (.error.message | test("Traceback|Exception") | not)' /tmp/xhs-006.json
```

判据：HTTP 502、PARSE_FAILED；响应不带调用栈。

### TC-008 imageList 为空

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000007?xsec_token=tok-007"}' \
  -o /tmp/xhs-007.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED" and .items == []' /tmp/xhs-007.json
```

判据：空列表判 PARSE_FAILED，不返回 count=0 的成功。

### TC-009 note 缺失

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000008?xsec_token=tok-008"}' \
  -o /tmp/xhs-008.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED"' /tmp/xhs-008.json
```

判据：noteDetailMap 为空且 noteData.data.noteData 也不匹配该 note_id，判 PARSE_FAILED。

### TC-010 视频或无图笔记

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000009?xsec_token=tok-009"}' \
  -o /tmp/xhs-009.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED" and .items == []' /tmp/xhs-009.json
```

判据：parse_note 遇到视频笔记返回 PARSE_FAILED，不接管视频解析。

### TC-011 成功响应契约

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000011?xsec_token=tok-011"}' \
  -o /tmp/xhs-011.json
jq -e '.title == "构造样本-契约" and .item_count == (.items | length)' /tmp/xhs-011.json
jq -e '.items[0] | has("index") and has("type") and has("remoteUrl") and has("ext") and has("cover") and has("width") and has("height") and has("needs_transcode")' /tmp/xhs-011.json
jq -e '.items[0].ext == "webp" and .items[0].width == 720 and .items[0].height == 1080 and .items[0].needs_transcode == true' /tmp/xhs-011.json
```

判据：字段齐全且类型正确；needs_transcode 恒 true；ext 从地址取得，缺省 webp。

### TC-012 缓存命中

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000010?xsec_token=tok-010"}' \
  -o /tmp/xhs-010a.json
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000010?xsec_token=tok-010"}' \
  -o /tmp/xhs-010b.json
jq -e '[.items[].remoteUrl] == ["https://sns-img-qc.xhscdn.com/j.webp","https://sns-img-qc.xhscdn.com/k.webp"]' /tmp/xhs-010a.json /tmp/xhs-010b.json
grep -q 'note_id=6a0000000000000000000010.*cache=hit' /tmp/xhs-server.log
grep -q 'event=xhs_note_parse' /tmp/xhs-server.log
```

判据：第二次命中缓存不发上游请求（桩计数不再增长），两次 items 完全一致；日志出现 cache=hit。

### TC-013 短链防御

```bash
cd /Users/apple/Developer/Personal/renlink/container
XHS_NOTE_HTTP_STUB=/tmp/xhs-fixtures/stub.json python3 - <<'PY'
import asyncio
from app.errors import ApiError
from app.parsers import xhs_note

async def main():
    got = await xhs_note.parse_note("https://xhslink.com/a/ok", "web_session=test")
    assert got["note_id"] == "6a0000000000000000000001", got
    assert len(got["items"]) == 3, got
    try:
        await xhs_note.parse_note("https://xhslink.com/a/loop", "web_session=test")
    except ApiError as exc:
        assert exc.code == "PARSE_FAILED", exc.code
    else:
        raise SystemExit("自环短链应当失败")
    print("OK shortlink")

asyncio.run(main())
PY
```

判据：3 跳内落到规范页并解析成功；自环超过跳数上限返回 PARSE_FAILED。

### TC-014 错误码与信封

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000001?xsec_token=tok-001","cookie":"x"}' \
  -o /tmp/xhs-cookie.json -w '%{http_code}')
[ "$code" = "400" ] && jq -e '.error.code == "INVALID_REQUEST" and .items == []' /tmp/xhs-cookie.json

code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://example.com/note/1"}' -o /tmp/xhs-host.json -w '%{http_code}')
[ "$code" = "400" ] && jq -e '.error.code == "UNSUPPORTED_PLATFORM"' /tmp/xhs-host.json
```

判据：错误信封一致；本湖不改变 l1 的 INVALID_REQUEST 与 UNSUPPORTED_PLATFORM。

### TC-015 零落盘

```bash
ls -1 /tmp | sort > /tmp/xhs-tmp-before.txt
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000011?xsec_token=tok-011"}' \
  -o /dev/null
ls -1 /tmp | sort > /tmp/xhs-tmp-after.txt
diff /tmp/xhs-tmp-before.txt /tmp/xhs-tmp-after.txt
```

判据：diff 无输出，解析不写磁盘。

### TC-016 抓取超时

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000012?xsec_token=tok-012"}' \
  -o /tmp/xhs-012.json -w '%{http_code}')
[ "$code" = "504" ]
jq -e '.error.code == "TIMEOUT" and .error.retryable == true and .items == []' /tmp/xhs-012.json
```

判据：桩延迟 9s 超过 8s 预算，返回 504 TIMEOUT。

### TC-017 页面超限

```bash
code=$(curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/6a0000000000000000000013?xsec_token=tok-013"}' \
  -o /tmp/xhs-013.json -w '%{http_code}')
[ "$code" = "502" ]
jq -e '.error.code == "PARSE_FAILED"' /tmp/xhs-013.json
```

判据：5MB 以上页面判 PARSE_FAILED，不截断后继续解析。

### TC-018 真实样本回归（BLOCKED）

依次对 XHS_NOTE_REAL_01 至 XHS_NOTE_REAL_10 执行 TC-001 的断言，并核对每篇 item_count 与页面张数一致。样本未采集前本用例为 BLOCKED，不计通过。

## BLOCKED：需要真实环境才能完成的项

| 项 | 关联 | 阻塞原因 | 解除条件 |
|----|------|----------|----------|
| 10 条真实小红书图文样本 | TC-018 | 本机现有真实小红书样本是视频笔记，图文样本尚未采集 | 运营方按分享面板采集 10 条图文链接并写入样本登记 |
| 真实短链跳转 | TC-013 | 构造桩只证明跳转与失败分支 | 采集 1 条真实 xhslink 图文短链复跑 |
| 小程序逐张保存联调 | AC-007 | 依赖 l5 页面与 l3 转存 | l5/l3 实现后按 items 顺序联调 |
