# l2-xhs-images · QA 返工证据

- 日期：2026-11-09
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`（改动未 commit、未 push）
- 改动文件：`container/app/parsers/xhs.py`、`tests/test_xhs.py`
- truth 正文：未改

## L2-1（阻塞）AC-009 解析缓存

补了进程内 TTL 缓存：

- 键 `xhs:note:v1:<note_id>:<sha256(xsec_token)[:12]>`，取自请求 URL 的 `xsec_token`（truth Q5）；
- TTL `XHS_NOTE_CACHE_TTL_S` 默认 600s，`0` 关闭；
- 只缓存成功结果，失败不写；命中不发上游请求，返回 items 的副本。

证据 `probe_note_cache.log`（真实 `/parse` 经 l1 路由打到 l2）：

```text
first status: 200 item_count: 2
second status: 200 item_count: 2
upstream_fetch_calls_with_default_ttl: 1
counters_with_default_ttl: {"xhs_note_cache_hit_total": 1, "xhs_note_cache_miss_total": 1, "xhs_note_images_total": 4, "xhs_note_parse_total{result=failed}": 0, "xhs_note_parse_total{result=need_xsec}": 0, "xhs_note_parse_total{result=ok}": 2}
upstream_fetch_calls_with_ttl_0: 2
NOTE_CACHE_PROBE_OK
```

## L2-2（阻塞）AC-010 计数器与结构化日志

- 计数器（进程内，`xhs.counters()` 可读）：`xhs_note_parse_total{result=ok|need_xsec|failed}`、`xhs_note_cache_hit_total`、`xhs_note_cache_miss_total`、`xhs_note_images_total`。
- 每次解析一条 INFO，首字段 `event=xhs_note_parse`，含 `note_id`、`image_count`、`xsec_token=present|missing`、`cache=hit|miss`、`elapsed_ms`、`code`；token 不落原值。
- 因 truth AC-010 把 `cache` 限定为 `hit|miss` 两值，TTL=0 时 `cache=miss`，另加 `cache_state=disabled` 表达禁用，不违背冻结枚举。

日志原文：

```text
renlink.xhs event=xhs_note_parse note_id=6a0000000000000000000010 image_count=2 xsec_token=present cache=miss cache_state=enabled elapsed_ms=0 code=ok
renlink.xhs event=xhs_note_parse note_id=6a0000000000000000000010 image_count=2 xsec_token=present cache=hit cache_state=enabled elapsed_ms=0 code=ok
renlink.xhs event=xhs_note_parse note_id=6a0000000000000000000010 image_count=2 xsec_token=present cache=miss cache_state=disabled elapsed_ms=0 code=ok
```

## 测试

- 新增 4 个用例：命中跳过上游、TTL 过期重抓、`TTL=0` 关闭、失败不入缓存；均断言计数器和日志字段。
- 全量：`50 passed, 3 warnings in 10.61s`（`pytest-full.log`），基线 45 passed；定向 4 passed。
- 硬边界：缓存只在进程内存，探针前后无落盘；请求体 cookie 拦截沿用 l1 既有断言（`tests/test_parse.py`）。

## 治理

- 冻结时序更正依据已用 `beacon-go truth change` 登记为 change 草稿：`docs/beacon/v0.1.0/features/l2-xhs-images/changes/chg_6a639cf6df40.md`（pending，未 refreeze）。
- 该命令只改 `tasks.md`/`tests.md` 的 `materials_status: current → stale` 做变更登记，truth.md 正文未动。
