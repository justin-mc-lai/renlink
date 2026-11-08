# l2-xhs-images · spec / AC 合规验收（独立验收员）

- 日期：2026-11-09 06:30（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`（实现 `8ed9b2e`，工作区干净）
- truth：`docs/beacon/v0.1.0/features/l2-xhs-images/truth.md`（`status: frozen`，HEAD 时点）
- maker：任链接 后端（codex）；本验收未改代码、未改 truth、未 commit / push
- 验收对象：`container/app/parsers/xhs.py`、`tests/test_xhs.py`
- **口径说明**：本湖 truth 实际为 **AC-001..AC-012**（不是派单里写的 AC-016）；下表按 truth 正文逐条判定。
- 总判定：**FAIL**（AC-009、AC-010 未实现，2 项阻塞）

## 1. 实跑基线

```
$ .venv/bin/python -m pytest tests -q
45 passed, 3 warnings in 7.95s
```

`tests/test_xhs.py` 7 个用例全部通过。额外行为探针见 §3（脚本在 `/tmp/qa-probe/`，不入库）。

## 2. AC 逐条判定

| AC | 判定 | 依据 |
|----|------|------|
| AC-001 | PASS | HTTP 探针：`/parse` 构造 3 图页 → 200、`ok=true`、`platform=xhs`、`content_type=note`、`item_count=3`、index `[0,1,2]`、全 `type=image`、`needs_transcode=true`；`tests/test_xhs.py:65-123,198-216` |
| AC-002 | PASS | `tests/test_xhs.py:65-123`：urlDefault 优先、WB_DFT 先于 CRD_WM_WEBP、无地址条目跳过不计数、`urlPre` 不出现在响应；`container/app/parsers/xhs.py:432-445` |
| AC-003 | PASS | 直连 `parse_note` 探针：2 跳短链成功落到规范页；4 跳、缺 Location、站外域名均 502 `PARSE_FAILED`；`container/app/parsers/xhs.py:265-333` |
| AC-004 | PASS | 探针：note_id 命中、唯一项兜底成功、多项无匹配 502 `PARSE_FAILED`；`container/app/parsers/xhs.py:413-429` |
| AC-005 | PASS | 探针 8 类结构失败（无 state、坏 JSON、无 noteDetailMap、无 note、无 imageList、imageList 非数组、空数组）均 502 `PARSE_FAILED`、`retryable=true`、无调用栈；`container/app/parsers/xhs.py:390-473` |
| AC-006 | PASS | 探针：URL query → note.xsecToken → state 顶层顺序成立；三者全缺 → 422 `NEED_XSEC_TOKEN`、`retryable=true`、`items=[]`；`tests/test_xhs.py:126-172`；HTTP 信封实测 `elapsed_ms` 为整数、无 Traceback |
| AC-007 | PASS | HTTP 探针字段集合 `cover/ext/height/index/needs_transcode/remoteUrl/type/width` 齐全、`item_count` 等于 items 长度；视频笔记、无图笔记、空 imageList 均 502 `PARSE_FAILED`（探针，`container/app/parsers/xhs.py:448-473`） |
| AC-008 | PASS | `container/app/errors.py:26` 新增 `NEED_XSEC_TOKEN(422, True)`，既有码未改（commit diff 仅追加 7 行）；失败信封实测 `ok=false`、`code`、`retryable`、`items=[]`、`elapsed_ms` 整数 |
| AC-009 | **FAIL** | 无解析缓存实现：全仓搜不到 `xhs:note:v1` / `XHS_NOTE_CACHE_TTL_S`；探针同 URL 连打两次 → `fetch` 被调用 **2 次**（命中应 0 次），两次结果均标 `cache=miss`。maker 自己的 evidence.md 亦写明「未做/未验证：解析缓存 AC-009」 |
| AC-010 | **FAIL** | 无计数器实现：全仓无 `xhs_note_parse_total` / `xhs_note_cache_hit_total` / `xhs_note_cache_miss_total` / `xhs_note_images_total`；日志行 `container/app/parsers/xhs.py:499-514` 只有 `xhs_note_parse` 前缀，缺 `event=xhs_note_parse` 字段，且 `cache` 恒为 `miss`。maker evidence.md 亦写明「未做/未验证：xhs_note_* 计数器 AC-010」 |
| AC-011 | PASS | 成功 `/parse` 前后 `/tmp` 新增文件数为 0（探针）；l1 的 `routes_parse.py`、`contract.py` 与 l3 未改（git diff 为空）；无下载/转码/COS 写入。注：l5 的 tasks/tests frontmatter 因 `chg_1c6f5fa13031` 标 `stale`，非本湖正文改动 |
| AC-012 | PASS | 探针：桩延迟 1.5s / 超时 1s → 504 `TIMEOUT`、`retryable=true`；页面超 `XHS_NOTE_MAX_BYTES` → 502 `PARSE_FAILED`；l2 不截断，截断由 l1 `contract.normalize_items` 统一处理 |

## 3. 关键探针与原始结果

```json
{
 "ac001_3images": {"ok": true, "items": 3, "token": "tok"},
 "ac003_shortlink_2hop": {"ok": true, "items": 1},
 "ac003_4hops": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac003_offdomain": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac003_no_location": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_no_state": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_bad_json": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_no_map": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_no_note": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_no_imagelist": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_imagelist_not_array": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac005_imagelist_empty": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac004_unique_fallback": {"ok": true, "items": 1},
 "ac004_multi_mismatch": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac006_missing_token": {"ok": false, "code": "NEED_XSEC_TOKEN", "http": 422, "retryable": true},
 "ac012_timeout": {"ok": false, "code": "TIMEOUT", "http": 504},
 "ac012_oversize": {"ok": false, "code": "PARSE_FAILED", "http": 502},
 "ac009_upstream_fetches_for_2_calls": 2,
 "ac009_cache_env_honored": "<unset>"
}
```

HTTP 层补充：`/parse` 成功响应 200、`item_count=3`、字段齐全、无 `urlPre`/`thumbnail`；缺 token 422、`items=[]`、`elapsed_ms` 为 int；成功解析前后 `/tmp` 无新增文件。

## 4. 缺陷清单

| 编号 | 严重度 | 是否阻塞 | 描述 | 必改项 |
|------|--------|----------|------|--------|
| L2-1 | P1 | **阻塞** | AC-009 解析缓存完全缺失：无 `xhs:note:v1:<note_id>:<sha256(token)[:12]>` 键、不读 `XHS_NOTE_CACHE_TTL_S`、命中不发上游请求的能力不存在；实测两次调用两抓上游 | 按 truth「缓存与观测」实现进程内缓存：键/TTL/只缓存成功/失败不写/命中返回一致；命中时不发请求。补自动化用例（同一 URL 两次，第二次上游调用数 0） |
| L2-2 | P1 | **阻塞** | AC-010 观测面缺失：四个计数器不存在，日志缺 `event=xhs_note_parse` 字段，`cache` 只有 `miss` 没有 `hit`；l7 无法读取命中/失败计数 | 补结构化日志字段（event/note_id/image_count/xsec_token=present|missing/cache=hit|miss/elapsed_ms/code）与四个进程内计数器，token 只写 present/missing；补用例断言字段与计数 |
| L2-3 | P1 | **阻塞**（治理） | 实现提交 `8ed9b2e` 的树中，本湖 truth 仍为 `status: draft`，AC 表仅占位符；`AC-001..012` 实体与 `status: frozen` 在之后的 `65c3112` 才写入。违反「truth 未冻结不得实现」，冻结 AC 不是实现前的前置契约 | 在 run `run_1084fcb4301353f56601ec48` 补齐/更正冻结时序证据；不得以冻结后的 AC 反推实现已合规 |
| L2-4 | P2 | 非阻塞 | `tests.md` 的 TC-012（缓存）、TC-013（短链）、TC-015（零落盘）、TC-016/017（超时/超限）在 `tests/test_xhs.py` 中没有对应自动化用例；maker evidence.md 已自述未做。本轮我用外部探针补测了短链/超时/超限/零落盘，但仓库内测试证据链不完整 | 把本轮探针固化为仓库测试，或在 evidence 中明确这些 TC 不由单测覆盖、以何种方式复核 |
| L2-5 | P3 | 非阻塞 | 本湖 truth 仅 12 条 AC，派单写「AC-001..AC-016」，编号口径不一致 | 统一派单与 truth 的 AC 编号口径 |

## 5. 结论

l2 的解析主链路（初始状态定位、原图回退与顺序、token 链与缺失码、结构失败矩阵、短链防御、超时/页面超限、`/parse` 归一化契约、零落盘）实现正确且实测通过；但 **AC-009 缓存与 AC-010 观测面整体缺失**，maker 在 evidence.md 中也已自述未做，属功能性缺口，必须补齐。叠加 truth 冻结时序治理缺口，本轮 **FAIL**。

---

# Round 2（返工后独立复验）

- 日期：2026-11-09 06:59（Asia/Shanghai）
- HEAD：`65c3112ab9088f1254d36a95024ffc11dad5c12c`；返工改动**未提交**在工作区（`container/app/parsers/xhs.py`、`tests/test_xhs.py` 等）
- 树指纹（派单口径）：`git diff container tests | shasum -a 256` = `1d0e7d9acf1df416ba4e04a57e4e845eb7e46392e8237546657124c1ce3e9b20`（与派单一致）
- truth 正文 `git diff` 为空，`status: frozen` 不变；本验收未改实现、未改 truth、未 commit / push
- 复验范围：L2-1（TTL 解析缓存）、L2-2（计数器与结构化日志）+ 全 AC 复核
- 总判定：**PASS**（AC-001..012 全部 PASS；治理项 L2-3 与 L2-4 单列，属 release 前待办，不改变本轮 AC 判定）

## R2-1. 实跑基线

```
$ .venv/bin/python -m pytest tests -q
50 passed, 3 warnings in 10.62s

$ .venv/bin/python -m pytest tests/test_zip.py tests/test_xhs.py -q
27 passed, 3 warnings in 5.32s
```

行为探针（不入库）：`/tmp/qa-probe-r2/probe_r2.py`（直接 `monkeypatch` `_fetch_note` 计数上游抓取，绕过 HTTP 桩）。

## R2-2. AC 逐条判定

| AC | 判定 | 依据 |
|----|------|------|
| AC-001 | PASS | 未受返工影响；回归探针 `/parse` 200、`platform=xhs`、`content_type=note`、`item_count=2`、每个 item 字段齐全、`needs_transcode=true`；`tests/test_xhs.py` 全绿 |
| AC-002 | PASS | 与 Round 1 一致；`tests/test_xhs.py` 原图回退与顺序用例全绿 |
| AC-003 | PASS | 与 Round 1 一致；短链防御代码未改 |
| AC-004 | PASS | 与 Round 1 一致；`__INITIAL_STATE__` / `noteDetailMap` 定位未改 |
| AC-005 | PASS | 与 Round 1 一致；本轮探针「无 state → 502 `PARSE_FAILED`」复验通过，`failed` 计数 +1 |
| AC-006 | PASS | 本轮探针：URL 无 token → `NEED_XSEC_TOKEN`，`need_xsec` 计数 =1，日志 `xsec_token=missing`；三段取值逻辑未改 |
| AC-007 | PASS | 与 Round 1 一致；`/parse` 归一化字段集合复验通过 |
| AC-008 | PASS | 错误信封未改；本轮 NEED_XSEC_TOKEN / PARSE_FAILED 实测码正确 |
| AC-009 | **PASS（已修复）** | 同 URL 连续两次：上游 `_fetch_note` 仅 **1 次**，两次结果完全相等；计数器 `hit=1 / miss=1 / ok=2 / images=4`。TTL=1s 过期后重抓（2 次，hit=0）；TTL=0 关闭缓存（2 次，hit/miss 均 0）；失败两次均重抓、`failed=2`、`hit=0`（失败不缓存）。键格式 `xhs:note:v1:<note_id>:<sha256(token)[:12]>` 与 truth 一致（`container/app/parsers/xhs.py:_cache_key`） |
| AC-010 | **PASS（已修复）** | 结构化日志实测：`event=xhs_note_parse note_id=... image_count=... xsec_token=present\|missing cache=hit\|miss cache_state=enabled\|disabled elapsed_ms=... code=...`；token 原值 `query-token` 未出现在日志。四个计数器全部存在且为实值：`xhs_note_parse_total{result=ok}=2`、`{result=need_xsec}=1`、`{result=failed}=2`、`xhs_note_cache_hit_total`、`xhs_note_cache_miss_total`、`xhs_note_images_total`（`counters()` 只读副本） |
| AC-011 | PASS | 回归探针：成功 `/parse` 前后 `/tmp` 新增文件数 **0**；l1 的 `routes_parse.py` / `contract.py`、l3 未改；无下载/转码/COS 写入 |
| AC-012 | PASS | 与 Round 1 一致（超时 504、页面超限 502）；抓取预算与页面上限代码未改 |

## R2-3. L2-1 / L2-2 关键探针原始结果

```json
{"upstream_fetches": 1, "results_equal": true,
 "counters": {"xhs_note_parse_total{result=ok}": 2,
              "xhs_note_parse_total{result=need_xsec}": 0,
              "xhs_note_parse_total{result=failed}": 0,
              "xhs_note_cache_hit_total": 1,
              "xhs_note_cache_miss_total": 1,
              "xhs_note_images_total": 4},
 "log_lines": ["... cache=miss cache_state=enabled ... code=ok",
               "... cache=hit cache_state=enabled ... code=ok"],
 "raw_token_in_logs": false}

{"ttl_expiry_upstream_calls": 2, "ttl_expiry_hits": 0, "ttl_expiry_misses": 2,
 "ttl_zero_upstream_calls": 2,
 "ttl_zero_counters": {"xhs_note_cache_hit_total": 0, "xhs_note_cache_miss_total": 0},
 "failure_codes": ["PARSE_FAILED", "PARSE_FAILED"],
 "failure_upstream_calls": 2,
 "failure_counters": {"xhs_note_parse_total{result=failed}": 2,
                      "xhs_note_cache_hit_total": 0}}

{"missing_token_code": "NEED_XSEC_TOKEN", "need_xsec_counter": 1,
 "bad_state_code": "PARSE_FAILED", "failed_counter": 1}
```

## R2-4. 缺陷清单（Round 2）

| 编号 | 严重度 | 是否阻塞 | 状态 | 描述 / 必改项 |
|------|--------|----------|------|----------------|
| L2-1 | P1 | 阻塞 | **已修复（本轮复核通过）** | TTL 缓存按 truth 键与 TTL 工作；命中 0 次上游、结果一致；TTL 过期重抓、TTL=0 禁用、失败不缓存 |
| L2-2 | P1 | 阻塞 | **已修复（本轮复核通过）** | 四个计数器 + `event=xhs_note_parse` 结构化字段齐全；`cache` 为实值；日志无 token 原值 |
| L2-3 | P1 | 阻塞（治理） | **未关闭** | 已出 `changes/chg_6a639cf6df40.md`（pending，未 refreeze，truth 正文未动）；仍需 run 负责人在 `run_1084fcb4301353f56601ec48` 内裁定 |
| L2-4 | P2 | 非阻塞 | 部分改善 | 缓存类 TC-012 已转成仓库用例（4 条）；TC-013（短链）、TC-015（零落盘）、TC-016/017（超时/超限）仍只有外部探针，建议回填仓库 |
| L2-5 | P3 | 非阻塞 | 未变化 | 派单写 AC-001..016、truth 实为 AC-001..012，编号口径需统一 |

## R2-5. 结论

L2-1 / L2-2 在本轮独立实跑中全部通过：缓存键、TTL、命中不发上游、失败不写缓存、计数器与结构化日志字段均与 truth「缓存与观测」一节一致，且 token 不落日志。l2 的 AC-001..012 现全部 PASS。剩余 L2-3（冻结时序治理）与 L2-4（部分 TC 未固化为仓库用例）不影响本次 AC 判定，release 前需由 run 负责人关闭 L2-3。
