# R2 诊断与顶层 truth 起草记录

- 时间：2026-11-09 05:37 CST
- 仓库：/Users/apple/Developer/Personal/renlink（main，HEAD 27172fb）
- run：run_1084fcb4301353f56601ec48
- 范围：只诊断执行器、起草顶层 truth 四段、给未提交改动定性；未跑 implement、未改产品代码、未 commit、未 push、未 freeze。

## 1. 执行器注册诊断（stage_executor_not_registered）

### 现状

goal status 原文（2026-11-09 05:37）：

```text
run:    run_1084fcb4301353f56601ec48
status: running (loop_stage governance_precheck)
stage:  plan
blocked: false
gate:   plan evaluated=false (this stage has no recorded verdict)
next:   beacon-plan
```

run metadata（sqlite 直读，只读）：

```text
executor_mode = ""            （null/空）
executor_defaulted = ""       （null/空）
exec = {}
last_block_reason = stage_executor_not_registered
blocked_streak = 2
```

### 根因

这个 run 创建时没有记录执行器。beacon-go 没有「给已存在的 run 补写执行器」的命令，也没有可编辑的执行器注册配置文件；执行器只有两个来源：

1. 建 run 时由 `goal run --executor ...` 写进 run metadata；
2. 每次 `goal tick` / `goal driver` / `goal program drive` 用 `--executor ...` 临时注册（不写回 run 记录）。

源码链路（/Users/apple/Developer/Personal/products/beacon-go）：

- `internal/cli/goal_p3c.go: realGoalEngine()`：selector 为空时返回无执行器的 Engine。
- `internal/orchestrator/exec_resolve.go: ResolveExecutorFor()`：`""` / `"none"` 明确返回 (nil, nil)；selector 词表没有 `manual`，所以 `goal tick --executor manual` 会报 unknown executor selector。
- `internal/orchestrator/tick.go: tickExecutor()`：非 manual/external 的 run 查不到执行器 → 写 `stage_executor_not_registered`。
- `internal/cli/goal.go: newGoalRunCmd()`：当前版本没给 `--executor` 时默认 manual（B4），但本 run 创建时早于该默认逻辑，metadata 仍是空。

### 最小修复（二选一，未执行）

路径 1（推荐，房间/人工驱动，一次建好）：

```bash
beacon-go goal run --project . --version v0.1.0 --feature renlink \
  --executor manual --executor-id renlink-dev-room --ux \
  --utterance "任链接：微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机（视频存相册、图文逐张+zip）"
```

新 run 建好后需要重新挂节目单（program plan 记录在 run 上，不会自动迁移）：

```bash
beacon-go goal program plan --run-id <新run-id> --program sea-lp_renlink_v1 \
  --from-proposal lp_renlink_v1 --freeze
beacon-go goal tick --run-id <新run-id> --by 任链接后端
```

truth 包与 gate 记录在磁盘和全局 store 上，不受换 run 影响；旧 run 保留为审计轨迹。

路径 2（保留现 run，每个阶段都要带执行器）：

```bash
beacon-go goal tick --run-id run_1084fcb4301353f56601ec48 \
  --executor subprocess --exec-cmd /绝对路径/程序 --exec-arg ...
```

注意：`--exec-cmd` 不会写回 run 记录；`--executor recording` 会写 `placeholder: true`，不能当真实交付。不建议手改 DB。

### 附带发现

上一个会话调用 `goal resume` 时，源码 `internal/orchestrator/resume.go` 对 `Blocked && Streak < 3` 会清 `Blocked`（不写事件、不清 LastBlockReason），所以状态从 blocked 变成 running，但 stage 没有推进；下一次 tick 会以同一 reason 再停。

## 2. 顶层 truth 起草

文件：`docs/beacon/v0.1.0/features/renlink/truth.md`

已填四段：

- `## 人话`：小程序 + 云托管，视频进相册、图文逐张 + zip；7 湖冻结 + 独立验收 + 真机三件套 + 人工 release。
- `## User Intent Snapshot`：utterance 逐字取自 `docs/beacon/v0.1.0/lake-proposal.json`（与 l1 冻结 truth 一致），goal / non_goals / constraints 按 PLAN.md 与六个已冻结湖的事实写；`scope_mode: ocean`。
- `## Open Questions` Q1：Answer 列写了草案，Status 保持 `open`，等 justin 点头。
- `## Acceptance Criteria` AC-001～AC-004：7 湖冻结 + 独立 integrity；真机 1 视频 / 9 图 / 1 zip；固定错误码与边界；release 人工确认。
- 另加 `## Alignment Surface`，列出 7 湖的交付面与 truth 状态，作为 ocean 包的对应面。

frontmatter：`status: draft`、`intent_confirmed: false` 保持不变；`ux_required` 由 false 改为 true，因为 l5 是两页小程序、host run 创建时也带了 `--ux`。

`beacon-go truth questions --project . --feature renlink` 现在只剩一个阻塞：

```text
Q1 [open] 用一句话说清：谁、什么问题、什么算完成？
blocked: truth_intent_question_open
```

snapshot 四项、AC-001 溯源、人话占位都已不再报错。

### AC-001 的当前差距（事实，不是声明）

- l1-parser-core：最近一条 truth_integrity 是 `audit`（2026-11-08T13:16:08Z），带 4 个 reason：audit_only、evidence_artifact_unregistered、evidence_artifact_missing、feature_package_validation_failed。
- l5-miniprogram-pages：最近一条是 `blocked`（2026-11-08T15:39:22Z），含 truth_ux_requirement_mismatch、TRUTH_DETERMINISM_PLACEHOLDER 等。
- l2、l3、l4、l6：`pass`。
- l7：`not_evaluated`，truth 仍是 draft/Think。

所以 AC-001 现在不成立，需要先补 l1/l5 的独立 integrity、冻结 l7。

## 3. 未提交改动定性（10 项清单）

| # | 路径 | 类型 | 是否阻断 implement |
|---|------|------|-------------------|
| 1 | docs/beacon/v0.1.0/features/l2-xhs-images/truth.md | truth 包更新（首冻） | 是：冻结正文需是 canonical 分支已提交基线（AC-139/141） |
| 2 | .../l2-xhs-images/tests.md | 测试包更新 | 是，同上 |
| 3 | .../l2-xhs-images/tasks.md | 任务包更新 | 是，同上 |
| 4 | .../l2-xhs-images/evidence.md | 证据索引更新 | 是，同上 |
| 5 | .../l6-zip-export/truth.md | truth 变更（配置表补 write） | 是，同上 |
| 6 | .../l6-zip-export/tests.md | 测试包更新 | 是，同上 |
| 7 | .../l6-zip-export/tasks.md | 任务包更新 | 是，同上 |
| 8 | .../l6-zip-export/evidence.md | 证据索引更新 | 是，同上 |
| 9 | .../l6-zip-export/changes/chg_f2492e8df79c.md（未跟踪） | truth 变更审计记录 | 是：应与包一起提交 |
| 10 | ops/hourly_status.sh | 运维脚本（HOURLY_NO_SEND 开关） | 否；已在 27172fb 提交并同步 origin，不属于当前未提交 |

本轮新增：`docs/beacon/v0.1.0/features/renlink/evidence/`（未跟踪），是诊断证据目录，不含产品代码。admit 的 dirty_policy 已把它计为 requirement package 脏改动。

`container/`、`frontend/` 的 diff 为 0；HEAD 27172fb，未 commit、未 push。

## 4. current_stage 原文

```text
run:    run_1084fcb4301353f56601ec48
status: running (loop_stage governance_precheck)
stage:  plan
blocked: false
gate:   plan evaluated=false (this stage has no recorded verdict)
next:   beacon-plan
```

## 5. 未验证

- 新 run 路径只在源码层核对，未实际创建；program plan 迁移未实跑。
- l7 仍 draft；l1/l5 的 integrity 缺口未修。
- 顶层 truth 未 freeze、未 confirm。
