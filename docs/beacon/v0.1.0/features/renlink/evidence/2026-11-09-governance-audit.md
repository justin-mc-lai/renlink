# 任链接 · run 治理审计（2026-11-09）

审计时间：2026-11-09 05:34 +08（2026-11-08T21:34:19Z）
审计人：任链接 后端（只读核查 + run 治理，未改产品代码）
仓库：/Users/apple/Developer/Personal/renlink（main）

## 0. 基线（与本单下发时的差异）

- 下发时写的 HEAD 是 e547d96；实查 HEAD 已是 **27172fb**，且与 origin/main 同点（ahead=0）。
- 27172fb = `chore(ops): allow silent mode for workspace monitor hook`，作者 kunqi.lai，时间 2026-11-09 05:30:39 +08，内容只有 `ops/hourly_status.sh` 的 `HOURLY_NO_SEND` 分支（+3/-1）。也就是说 hourly 报的那 1 个脚本改动已经落到 main 并同步到 origin，已不再是未提交改动。
- 当前未提交：l2-xhs-images 四件套 + l6-zip-export 四件套（8 个修改）+ l6 的未跟踪 `changes/`。`container/`、`frontend/` 的 diff 为 0。`.beacon/` 被 .gitignore 忽略。

## 1. beacon-go goal status 原文

审计时的当前输出（2026-11-09 05:36 +08）：

```text
run:    run_1084fcb4301353f56601ec48
status: running (loop_stage governance_precheck)
stage:  plan
blocked: false
gate:   plan evaluated=false (this stage has no recorded verdict)
next:   beacon-plan
```

current_stage = **plan**（loop_stage = governance_precheck）。`blocked` 已为 false，但 metadata 里 `last_block_reason = stage_executor_not_registered`、`blocked_streak = 2` 仍在，执行器依旧未注册，下一次 tick 会以同一理由再停。

审计开始时（执行 `goal resume` 之前）的输出是：

```text
run:    run_1084fcb4301353f56601ec48
status: blocked (loop_stage governance_precheck)
stage:  plan
blocked: true
reason: stage_executor_not_registered
gate:   plan evaluated=false (this stage has no recorded verdict)
next:   beacon-plan
```

差异原因已核实：`beacon-go goal resume` 不只是读决策，源码 `internal/orchestrator/resume.go: Resume()` 对 `Blocked && BlockedStreak < 3` 的软阻塞会顺手清掉 `Blocked`（不写 lifecycle 事件、不清 `LastBlockReason`）。本次审计调用 resume 时触发了这个副作用，属我方的状态改动，按实记录；没有发生 stage 推进。

## 2. A · plan 阶段执行器为什么没注册

结论：**不是某个配置文件缺一段注册，而是这个 run 创建时没有记录任何执行器**。beacon-go 的 stage executor 只从两处来：创建 run 时记录的 `executor_mode` / `exec`，或每次 tick 时用 `--executor` 现注册。这个 run 两处都是空的。

实查（runs.metadata_json）：

```text
executor_mode      = null
executor_defaulted = null
exec               = {}
executor_id        = renlink-dev-room
```

代码路径：

1. `internal/cli/goal_p3c.go: realGoalEngine()`：`--executor` 为空时直接返回一个未注册任何执行器的 Engine。
2. `internal/orchestrator/tick.go: TickBy()`：run 不是 manual/external（`isManualExecutor()==false`），走 `tickExecutor()`；plan 阶段查不到执行器，写 `stage_executor_not_registered` 并停住。
3. `internal/orchestrator/exec_resolve.go: ResolveExecutorFor()`：只有 `recording | subprocess | subprocess:<profile> | ralph` 会返回执行器；`""` / `none` 明确返回 nil（设计上就是诚实停住）。

同一个问题也存在于 l1 的 lake run `run_bde3174e4fdc3edd7710c87b`：`executor_mode=null`、`exec={}`，所以 `goal program route` 指到它，但 `program drive` 不带 `--executor` 时会以同样理由停住。

### 最小可执行修复路径

路径 1（推荐，人工/房间驱动，不改任何配置或代码）：

```bash
cd /Users/apple/Developer/Personal/renlink

# 1) 新建一个 manual run，并把 7 湖节目单重新记录到这个 run
beacon-go goal run --project . --version v0.1.0 --feature renlink \
  --executor manual --executor-id renlink-dev-room --ux \
  --utterance "任链接：微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机（视频存相册、图文逐张+zip）。按7湖交付：L1解析内核、L2小红书图文、L3文件下发、L4登录态与出口、L5两页前端、L6压缩包、L7风控合规。"

beacon-go goal program plan --run-id <新run-id> --program sea-lp_renlink_v1 \
  --from-proposal lp_renlink_v1 --freeze

# 2) 每完成一个阶段，用身份记账（manual run 的唯一推进方式）
beacon-go goal tick --run-id <新run-id> --by 任链接后端
```

路径 2（保留现 run，真执行子进程）：

```bash
beacon-go goal tick --run-id run_1084fcb4301353f56601ec48 \
  --executor subprocess --exec-cmd /绝对路径/可执行程序 --exec-arg ...
# 或 subprocess:<profile>：--profile codex-style / claude-style
```

注意：tick 的 `--exec-cmd` **不会写回 run 记录**（只有 `goal run` 会记录 `exec`），因此路径 2 每次 tick 都要重复带执行器参数，或用 `goal driver run-once` / `goal program drive` 时带同一组参数。

不要用 `--executor recording` 来过这一关：它在事件里写 `placeholder: true`，等于用占位执行器制造一个假的 plan 通过。也不要手改 `~/.beacon/beacon-go.db` 的 metadata。

## 3. B · 顶层 renlink truth 必须由人补签的 intent

`beacon-go truth questions --project . --feature renlink --version v0.1.0` 当前 4 条阻塞：

```text
blocked: truth_intent_snapshot_incomplete: User Intent Snapshot is missing: utterance, goal, non_goals, constraints
blocked: truth_intent_question_open: Q1 is still open
blocked: truth_intent_coverage_untraced: AC-001 has no traced intent source/evidence
blocked: truth_intent_package_scaffold: ## 人话 still carries the skeleton placeholder
```

需要 justin 明确签的，只有这几条：

1. **Q1 一句话**：谁用、解决什么问题、什么算完成（同时作为 `## 人话` 正文）。
2. **goal**：这个顶层包要达成的结果（建议写成「7 湖全部 frozen + 实现 + 独立验收通过 + 人工 release」这类可判定句）。
3. **non_goals**：明确不做什么（例如：不做多平台扩展、不做付费、不做下载站点）。
4. **constraints**：硬边界（微信小程序 + 云托管、7 湖切分、不重写 l1 解析框架、视频转存归 l3 等）。
5. **范围裁定**：顶层 `renlink` v0.1.0 是作为「海洋验收包」冻结，还是作为历史容器不冻结；以及重复的 `docs/beacon/v0.1/features/renlink/`（同样是 draft 模板）是删除还是归档。
6. **l5 Q7 契约裁决**：l5 冻结正文的 `{cloudIDs, zipName} → {cloudID}` 与 l6 的 `{task_id, indexes?} → {ok, fileID, bytes, count}` 二选一——改 l5 走 `truth change`，或由前端调用层适配。改冻结正文必须人签。

签名顺序：

```bash
beacon-go truth intent --project . --feature renlink --version v0.1.0 --by justin-mc-lai \
  --utterance "..." --goal "..." --non-goals "..." --constraints "..." --scope-mode ocean
beacon-go truth answer --project . --feature renlink --version v0.1.0 --q Q1 --answer "..."
beacon-go truth confirm --project . --feature renlink --version v0.1.0 --by justin-mc-lai
beacon-go truth freeze  --project . --feature renlink --version v0.1.0 --by 任链接后端
```

`intent_confirmed: true` 只能由 confirm 写；冻结前的 AC-001（模板句）也要一并换成真实完成标准，否则 `truth_intent_coverage_untraced` 仍会挡。

## 4. C · 10 个改动逐项定性

| # | 路径 | 定性 | 说明 |
|---|------|------|------|
| 1 | l6-zip-export/truth.md | truth 正文（冻结内容） | 配置表 `ZIP_FAULT_INJECT` 补 `write`，AC 正文未动；有 change 记录 |
| 2 | l6-zip-export/tests.md | tests 更新 | MF-1～MF-7、MF-9 的返工 |
| 3 | l6-zip-export/tasks.md | tasks 更新 | TASK-010 注入面同步 |
| 4 | l6-zip-export/evidence.md | evidence 索引 | 状态改 frozen/Freeze，GATES 补两个 gate id |
| 5 | l2-xhs-images/truth.md | truth 正文（首冻） | 12 AC 正文 |
| 6 | l2-xhs-images/tests.md | tests（首冻） | 18 TC（TC-018 真实样本 BLOCKED） |
| 7 | l2-xhs-images/tasks.md | tasks（首冻） | 15 TASK |
| 8 | l2-xhs-images/evidence.md | evidence 索引 | 四件套索引 + 未产生状态 |
| 9 | l6-zip-export/changes/chg_f2492e8df79c.md | 变更记录（未跟踪） | truth change/refreeze 的审计轨迹 |
| 10 | ops/hourly_status.sh | 运维脚本 | 已提交并推送为 27172fb，本轮不是脏文件 |

没有任何产品代码混入：`git status --porcelain container frontend` 为空。

规模复核：l2 = 12 AC / 18 TC / 15 TASK，l6 = 16 AC / 16 TC / 17 TASK；两包占位串（`(fill`、`TBD`、`YYYYMMDD`、`（一句话`）命中 0。两湖独立 integrity 均为 pass，记录时间 2026-11-08T21:29:40Z，晚于文件 mtime。

### 落盘建议

1. 新建分支 `beacon/l2-l6-freeze`，把上表 1～9 作为一个 docs 提交：`docs(beacon): freeze l2-xhs-images and refreeze l6-zip-export`。
2. 合并回 main 用 fast-forward（docs-only，无产品代码）。注意 AC-139：冻结正文必须是 **main 上已提交的基线**，truth 阶段才允许离开；只留分支会卡在 `canonical_refreeze_not_committed`。
3. 本审计文件（`docs/beacon/v0.1.0/features/renlink/evidence/2026-11-09-governance-audit.md`）跟随同一提交或作为紧随其后的 docs 提交。
4. push 等 justin 确认；本轮未 commit、未 push。

## 5. 未做 / 未验证

- 未执行 `goal tick` / `goal continue` / `program drive`，未改动 run 状态。
- 例外并已披露：`goal resume` 按其源码语义清掉了软阻塞标记（blocked=true→false，streak 2 保留，last_block_reason 保留），stage 未推进、无 lifecycle 事件。
- 未 commit、未 push、未改 main。
- 新 run 的路径只在源码层面核对过，未实际创建（避免产生第二个 ocean run）。
- l7-risk-compliance 仍是 draft/Think，未纳入本轮。
- `goal conformance` 仍为 fail：truth_frozen / gates_evaluated / verifier_attached / state_exported 四项。
