# 独立验收报告：l5-miniprogram-pages v0.1.0（r1）

- mode_id: `beacon-go`
- run_id: `qa-l5-20261108-2248`
- stage: `qa`
- feature: `l5-miniprogram-pages` v0.1.0
- 验收对象: implement 轮 + 返工轮（uni-app 两页工程）
- 仓库 / 基线: `/Users/apple/Developer/Personal/renlink`，HEAD `b4a1624`，分支 `main`（与 origin/main 同步，无新 commit）
- 验收人: 验收员（独立验收，未修改实现代码）
- 判定时间: 2026-11-08 22:48 Asia/Shanghai

## Verdict

**FAIL** — 无 P0；1 项 P1 必改（AC-010「再次解析」联动断开，且 evidence.md 该 TASK 标为 done，属证据与行为不一致）。
TASK-017 真机验收维持 **BLOCKED**（缺真实 appid + 真机）。

### Blocked mapping

| 项 | 状态 | 阻塞原因 |
|---|---|---|
| TASK-017 / AC-012 真机端到端 | BLOCKED | 缺真实微信 AppID 与 iOS/Android 真机体验版扫码；本机无法替代 |
| TASK-009 / AC-004 逐项保存 | stub（显式失败） | l3-media-delivery truth 未冻结，`/stage` 不存在（container 内 grep 无该路由） |
| TASK-013 / AC-006 ZIP 导出 | stub（显式失败） | l6-zip-export truth 未冻结 |

## 1. truth 冻结与变更一致性 — PASS

命令与输出：

```text
$ beacon-go truth show --feature l5-miniprogram-pages --version v0.1.0
package:  l5-miniprogram-pages (v0.1.0)
status:   frozen
lifecycle: Freeze/Completed
branch:   check=ok current=main canonical=main
baseline: uncommitted

$ beacon-go truth drift --feature l5-miniprogram-pages --version v0.1.0
package: l5-miniprogram-pages
clean:   true
body drift: false
```

- frontmatter `stack: uni-app-vue3-vite` 已落（truth.md:17）。
- 正文含「## 工程结构与条件编译」（truth.md:193），写清 `frontend/`、`@dcloudio/vite-plugin-uni`、MP-WEIXIN 走 `wx.cloud.callContainer`、H5/App 走 `VITE_API_BASE` REST 兜底、云开发数据库仅 MP-WEIXIN。
- 与 HEAD（change 前基线）对比，truth.md 仅删除 2 行（`stack: wechat-miniprogram-tcb` 与旧阶段授权句），新增 28 行；AC-001~AC-012、C1~C8、错误矩阵、UI 规格均未被改动。
- change 文档 `chg_11f33b7cb108` 仍 `status: pending`：按内核语义，refreeze 只清 trail pending 并写 `truth_refrozen` 事件，不作为阻塞项。

## 2. 构建 — PASS

```text
$ cd frontend && rm -rf dist && npm run build:mp-weixin
DONE  Build complete.
build_exit=0
dist/build/mp-weixin 存在

$ node -e "const j=require('./dist/build/mp-weixin/app.json');console.log(JSON.stringify(j.pages));console.log(JSON.stringify(j.tabBar.list))"
["pages/index/index","pages/mine/mine"]
[{"pagePath":"pages/index/index","text":"提取"},{"pagePath":"pages/mine/mine","text":"我的"}]

$ npm run build:h5
DONE  Build complete.
h5_exit=0
```

（构建过程有 sass legacy-js-api DEPRECATION WARNING，非报错，不影响产物。）

## 3. 假成功是否清干净（P0 检查） — PASS

- `src/api/parse.js:159-202` `stageMedia`：MP 分支仅在 `statusCode===200 && data.ok` 时 resolve；非 200/非 ok → reject `STAGE_NOT_READY`；`fail` → reject `STAGE_NOT_READY`；H5 分支直接 `throw STAGE_NOT_READY`。全文无 `resolve({ ok: true, cloudID: item.remoteUrl })`，无任何把 remoteUrl 当 cloudID 的返回。
- `src/api/parse.js:211-216` `createZip`：直接 `throw ZIP_NOT_READY`，不再 fetch / `wx.cloud.callContainer` 打 `/zip`。
- `index.vue:263-295` 视频保存：`stageMedia` 抛错 → catch → Toast 错误文案，不出现「视频已保存到相册」；成功 Toast 只在该函数正常走完时出现，stub 下不可达。
- `index.vue:311-341` 批量保存：单项异常 → `failedItems` 标红，成功计数只在 `saveSingleImageItem` 正常返回时 +1；stub 下 successCount=0，落「有 N 项失败」而非「全部图片已保存」。
- `index.vue:362-383` `saveSingleImageItem`：非 `cloud://` 分支虽存在 `saveImageToAlbum(staged.cloudID)`，但 `staged` 唯一来源是 `stageMedia`，而该函数所有路径都 reject → 该分支当前不可达，不会被当作成功路径。
- `container/app` 内 grep `/stage`、`/zip` 无任何路由命中，确认端点确实不存在，调用只会快速失败。

## 4. 硬约束 — PASS

| 约束 | 证据 |
|---|---|
| callContainer ≤15s | `parse.js:62` 手动 timer 15000 + `parse.js:72` `timeout: 15000` |
| H5 fetch 15s | `parse.js:113-114` AbortController + 15000，AbortError → `TIMEOUT` |
| /parse 请求体只有 `{ url }` | `parse.js:42` `payload = { url: cleanUrl }`；src 内无 cookie/Authorization/Bearer/token |
| 一文件一请求 | `index.vue:324-341` 串行 for-await，逐项 `stageMedia` |
| appid 占位符 | `manifest.json:3,9` 均为 `wx0000000000000000` |
| 云开发库仅 MP-WEIXIN | `history.js:26-38,56-72` 在 `#ifdef MP-WEIXIN` 内，外的 localStorage 兜底通用 |
| 不引 UI 库 | package.json 无 uview/vant/nutui/tui 等 |

## 5. 错误码 — PASS（含 1 条 P2 文案口径）

`src/utils/errors.js` 含 COOKIE_EXPIRED / SHORTLINK_FAIL / TIMEOUT / UNSUPPORTED_PLATFORM / PARSE_FAILED / STAGE_NOT_READY / ZIP_NOT_READY（另有 INVALID_URL、NETWORK_ERROR）。
文案与 truth AC-007（truth.md:168）逐字一致；与 UI 规格错误表（truth.md:121-127）在 SHORTLINK_FAIL、TIMEOUT、UNSUPPORTED_PLATFORM 三处措辞略有出入——属 truth 自身两处矩阵口径不一致，不计前端缺陷。

## 6. 仓库卫生 — PASS

```text
$ git status --short --untracked-files=all frontend | wc -l
16
$ git ls-files frontend | wc -l
0
```

`.gitignore` 含 `node_modules/`、`dist/`、`.env`、`.env.*`、`!.env.example`、`.DS_Store`、`unpackage/`、`*.log`。node_modules 252MB / dist 208K 均未进入跟踪。

## 7. 边界与提交 — PASS

```text
$ git log --oneline -1
b4a1624 docs(beacon): l1 truth change, refreeze and acceptance evidence
$ git status -sb | head -1
## main...origin/main   （无 ahead，无新 commit）
$ git diff --stat container/
 container/app/parsers/render_obscura.py | 44 ++++++++++++++++---------------------------
```

`render_obscura.py` mtime 2026-11-08 22:19:15，早于本轮 frontend 全部改动（index.vue 22:44:39、parse.js 22:43:52、mine.vue 22:36:58），非本轮引入。未发现 commit / push。

## 8. 证据一致性 — FAIL（P1）

| 检查 | 结果 |
|---|---|
| evidence.md 构建时间/输出与复跑结果 | 一致（22:45 build、app.json 两页、16 个未跟踪文件） |
| TASK-009 / TASK-013 | 与代码一致：stub、显式失败、不伪造成功 |
| TASK-017 | 与代码一致：BLOCKED |
| TASK-016 | **不一致**：见 P1-1 |

## 问题清单

### P0（阻塞级：假成功 / 数据破坏 / 安全）

无。

### P1（必改）

**P1-1 AC-010「再次解析」联动断开，TASK-016 却标 done。**
`mine.vue:140-146` 的 `reParse()` 只做 `uni.switchTab` + `uni.setStorageSync('renlink_auto_parse_url', url)`；全仓 grep 该 key 只有这一处写入，`index.vue` 的 `onShow`（index.vue:173-175）只调 `checkClipboard()`，从不读取该 key；`switchTab` 也不会触发 `onLoad` 的 query 分支（index.vue:168-173）。结果：用户点「再次解析」后只跳回主页，输入框为空、不自动解析，与 truth AC-010「点击『再次解析』携带原链接返回主页并自动执行解析」不符。
必改：`index.vue` 在 `onShow` 读取并消费 `renlink_auto_parse_url`（写入 `inputUrl` → 清 storage → 调 `handleParse()`）；改完重跑 `build:mp-weixin` 并把 evidence.md 里 TASK-016 的说明补一句自验方式。

### P2（不阻塞，建议随本轮一起改或下轮清）

1. `stageMedia` 的 MP 分支仍会真打一次不存在的 `/stage`（快速失败→STAGE_NOT_READY）。不产生假成功，但真机每张图都会发一次无效请求；l3 冻结前建议直接 reject，冻结后再换成真调用。
2. `index.vue:270-292` 视频下载回调里 `finally` 会先执行 `isSaving=false`，下载中点按钮可重入（当前 stub 下不可达，接通 /stage 后要修）。
3. `saveAllImages` 在 0 成功时提示「保存完成，有 N 项失败」，措辞易被读成部分成功；建议 0 成功时改「保存失败」。
4. AC-005 要求「下方展示独立重试按钮」，实现为失败项自身红色遮罩点击重试（语义等价，位置不同）。
5. AC-001 提示文案为「检测到社媒分享链接，是否填入？」，truth 原文为「检测到分享链接，是否填入？」。
6. `mine.vue` 用户卡片是静态占位（微信用户 / wx_user_***），未真实读取 openid 脱敏标识；历史查询本身依赖数据库 `_openid` 隔离，不影响 AC-009 数据正确性。
7. evidence.md「Evidence Index」表中 truth/tests/tasks 状态仍写 `draft`，与 frozen 状态不一致；「当前处于 truth 阶段」的表述已过期。
8. TASK-005 描述为「/parse 容器服务联调」，实际只有代码级对接，无真实调用证据（需真机 + appid 才能验）；建议措辞降级为「按契约实现」，把联调归到 TASK-017。

## 未验证项

- 真实 `/parse` 端到端（需真实 appid + 云托管环境）——归 TASK-017。
- 真机相册写入、权限弹窗、剪贴板嗅探、分享转发——归 TASK-017（BLOCKED）。
- 云开发数据库 `parse_history` 读写与 openid 隔离——需真实云环境，未验证。
