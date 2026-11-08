---
slug: renlink
version: v0.1.0
status: draft
language: zh
domain_required: false
ux_required: true
parser_contract: beacon-feature-package-v2
truth_source_model: feature_package_authoritative
package_maturity: draft
materials_status: draft
intent_confirmed: false
canonical_refs:
  truth: docs/beacon/v0.1.0/features/renlink/truth.md
  tests: docs/beacon/v0.1.0/features/renlink/tests.md
  tasks: docs/beacon/v0.1.0/features/renlink/tasks.md
  evidence: docs/beacon/v0.1.0/features/renlink/evidence.md
---

# Requirement Truth: renlink

## 人话

「任链接」是微信小程序加云托管容器：用户粘贴一条抖音或小红书链接，服务端解析出每一段媒体，视频存进手机相册，图文逐张存相册并能打成一个 zip 发出去。全局做到 7 个湖全部冻结并通过独立验收、真机完成「1 个视频、9 张图、1 个 zip」三条验收、经人工确认 release，才算完。

## User Intent Snapshot

```yaml
lake_or_ocean: 海洋
program: lp_renlink_v1
program_slug: sea-lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
language: zh
source: user_intent
utterance: "任链接：微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机（视频存相册、图文逐张+zip）"
goal: "7 个湖（l1 解析内核、l2 小红书图文、l3 文件下发、l4 登录态与出口、l5 两页前端、l6 zip 导出、l7 风控合规）全部 frozen/Freeze 并通过带 evaluator 的独立 truth_integrity；真机完成 1 个视频进相册、9 张图文进相册、1 个 zip 可打开；最后经人工确认 release"
non_goals: "小程序正式提审；用户上传 cookie；B站/微博/YouTube/X；付费、会员、广告；服务端自动过滑块；自建 VPS 替代云托管；直接改写 l1～l6 已冻结正文（需走 truth change）"
constraints: "callContainer ≤15s、单文件一请求；返回包 ≤1000KB，/stage 只回 {ok,fileID,kind,ext,bytes}、/zip 只回 {ok,fileID,bytes,count}；容器无持久盘，文件必须进 COS；手机端 openDocument 不支持 zip，zip 走 wx.shareFileMessage、PC 用 saveFileToDisk；小红书 webp 必须后端转 jpg；cookie 只做运营方池；7 湖按 l1→l2/l3/l4→l5/l6→l7 依赖推进；maker≠checker；release 由人确认"
scope_mode: ocean
```

utterance 来源：`docs/beacon/v0.1.0/lake-proposal.json` 的 `utterance` 字段，与 l1-parser-core 已冻结 truth 的记录一致；本包没有新写用户原话。

## Open Questions

One question at a time; a package cannot be signed while a row is open.
Use beacon truth ask / beacon truth answer to drive this ledger.

| Q ID | Question | Recommendation | Status | Answer |
|------|----------|----------------|--------|--------|
| Q1 | 用一句话说清：谁、什么问题、什么算完成？ | 先写目标与非目标，再写一条可验证的完成标准 | open | 草案（待 justin 确认）：普通微信用户粘贴抖音/小红书链接，把视频或图文保存到手机，运营方可用 curl 独立验证；完成 = 7 湖全部 frozen 并通过独立验收，真机 1 视频、9 图、1 zip 三条通过，人工 release。 |

## Intent Coverage

Every AC must trace to the intent or evidence it serves.

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | `lake-proposal.json` utterance：「7 湖交付」 | docs/beacon/v0.1.0/lake-proposal.json；docs/PLAN.md「湖与验收」；l1-parser-core truth 的 User Intent Snapshot |
| AC-002 | utterance：「下载到用户手机（视频存相册、图文逐张+zip）」 | docs/PLAN.md 架构与验收表；l3/l5/l6 已冻结 truth |
| AC-003 | 硬约束 C1/C2/C4/C5/C6 与各湖错误码表 | l1/l2/l6 truth 的约束表与错误码表 |
| AC-004 | 统一运行内核：release 由人确认 | docs/PLAN.md「常用命令」；beacon-go release gate 语义 |

## Acceptance Criteria

| AC ID | Criterion |
|-------|-----------|
| AC-001 | 7 个湖的四件套全部 frozen/Freeze，且每湖都有带 evaluator 的 `gate integrity` pass 记录；l7-risk-compliance 从 draft/Think 转 frozen 是本条前置；`beacon-go truth list --project .` 的输出逐湖可核 |
| AC-002 | 真机端到端：同一轮验收里完成 ①抖音视频保存进相册 ②小红书图文 ≥9 张 jpg 进相册 ③该图文 zip 通过 wx.shareFileMessage 发出并能在文件 App 打开；三条各有截图与 fileID 证据 |
| AC-003 | 固定错误码与边界：/parse 缺 xsec_token 返回 422 NEED_XSEC_TOKEN；/zip 的 50 张上限与 200MB 上限任一被突破时返回 413 TOO_LARGE；无 COS 凭证返回 503 ZIP_NOT_READY 且不伪造 cloud://；/parse 响应 ≤1000KB；请求体带用户 cookie 返回 400 INVALID_REQUEST |
| AC-004 | release 只在「qa 门 pass、独立 verifier 已挂、人工确认」三者同时满足时通过；auto 发布被拒绝，auto_shadow 只出预览 |

## Alignment Surface

| 湖 | 交付面 | truth 状态（2026-11-09） | 证据 |
|----|--------|--------------------------|------|
| l1-parser-core | /parse 解析内核 | frozen/Freeze | docs/beacon/v0.1.0/features/l1-parser-core/evidence.md |
| l2-xhs-images | 小红书图文原图 + xsec_token | frozen/Freeze | docs/beacon/v0.1.0/features/l2-xhs-images/evidence.md |
| l3-media-delivery | /stage 下载、转码、COS、fileID | frozen/Freeze | docs/beacon/v0.1.0/features/l3-media-delivery/evidence.md |
| l4-session-egress | 运营方 cookie 池与出口切换 | frozen/Freeze | docs/beacon/v0.1.0/features/l4-session-egress/evidence.md |
| l5-miniprogram-pages | 主页与个人中心两页 | frozen/Freeze | docs/beacon/v0.1.0/features/l5-miniprogram-pages/evidence.md |
| l6-zip-export | /zip 打包与端侧转发 | frozen/Freeze | docs/beacon/v0.1.0/features/l6-zip-export/evidence.md |
| l7-risk-compliance | 限流、缓存、大小上限、版权、投诉、内容安全 | draft/Think（未冻结） | docs/beacon/v0.1.0/features/l7-risk-compliance/evidence.md |

已冻结的 6 个湖，其独立 `truth_integrity pass` 记录以各湖 evidence 与 `beacon-go gate status --feature <slug>` 为准；l7 尚未冻结，不能计入 AC-001。

## FSM 五元组

Only required when frontmatter domain_required: true. Fill the
five-tuple, declare terminal states (终态： ...), and add an
Illegal Transitions section below listing forbidden moves
(- illegal: from -> to). The graph is machine-validated at
freeze: a missing target, a missing event, or a missing illegal
section blocks.

| State | Event | Guard | To | Action |
|-------|-------|-------|----|--------|

## Parity Matrix

Only required when scope_mode: full_parity. List the source capability,
whether Beacon covers it, and the evidence.

| Capability | Covered | Evidence |
|------------|---------|----------|
