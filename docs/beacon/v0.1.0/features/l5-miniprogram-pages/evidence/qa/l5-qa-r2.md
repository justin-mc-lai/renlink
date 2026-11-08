# 独立验收报告：l5-miniprogram-pages v0.1.0（r2）

- mode_id: `beacon-go`
- run_id: `qa-l5-20261108-2258`
- stage: `qa`
- feature: `l5-miniprogram-pages` v0.1.0
- 验收对象: 前端 r2 返工（r1 唯一 P1 + 两个 P2）
- 仓库 / 基线: `/Users/apple/Developer/Personal/renlink`，HEAD `b4a1624`，分支 `main`（`main...origin/main` 无 ahead/behind，无新 commit）
- 验收人: 验收员（独立验收，未修改任何实现代码、truth、container/）
- 判定时间: 2026-11-08 22:58 Asia/Shanghai

## Verdict

**PASS** — r1 的唯一 P1 已真实闭环，两个 P2 均已修；r1 的 PASS 项无回归。
保留 P2 建议项（不阻塞）；TASK-017 真机验收维持 **BLOCKED**（缺真实 appid + 真机）。
不签 release。

### Blocked mapping

| 项 | 状态 | 阻塞原因 |
|---|---|---|
| TASK-017 / AC-012 真机端到端 | BLOCKED | 缺真实微信 AppID 与 iOS/Android 真机体验版扫码；本机无法替代 |
| TASK-009 / AC-004 逐项保存 | stub（显式失败） | l3-media-delivery truth 未冻结，`/stage` 服务未上线 |
| TASK-013 / AC-006 ZIP 导出 | stub（显式失败） | l6-zip-export truth 未冻结 |

## 1. r1 唯一 P1：AC-010「再次解析」链路 — PASS

```text
$ rg -n "renlink_auto_parse_url" frontend/src
frontend/src/pages/mine/mine.vue:139:  uni.setStorageSync('renlink_auto_parse_url', url)
frontend/src/pages/index/index.vue:174:  const autoUrl = uni.getStorageSync('renlink_auto_parse_url')
frontend/src/pages/index/index.vue:176:    uni.removeStorageSync('renlink_auto_parse_url')
```

`frontend/src/pages/index/index.vue:173-181` 的 `onShow`：

```js
onShow(() => {
  const autoUrl = uni.getStorageSync('renlink_auto_parse_url')
  if (autoUrl) {
    uni.removeStorageSync('renlink_auto_parse_url')
    inputUrl.value = autoUrl
    handleParse()
  } else {
    checkClipboard()
  }
})
```

- 顺序符合要求：取值 → 清 storage（防重复触发）→ 写 `inputUrl` → `handleParse()`；无值才走 `checkClipboard()`。
- `handleParse()`（`index.vue:239-267`）内部读的是 `inputUrl.value`（`parseUrl(inputUrl.value)`），不依赖 `onLoad` query；`switchTab` 只触发 `onShow` 也能生效。
- `mine.vue:137-143` 的 `reParse()` 先 `setStorageSync` 再 `switchTab`，无竞态。**结论：闭环。**

## 2. 两个 P2 — 均 PASS

- **P2-1 `saveSingleVideo` 进度态提前复位**：`index.vue:284-290` 已改成 `const downloadRes = await new Promise((resolve, reject) => { wx.cloud.downloadFile({ success: resolve, fail: reject }) })`，`isSaving=false` 只在 `finally` 里执行一次，不再有 inner 回调与 `finally` 双写。
- **P2-2 零成功文案**：`index.vue:342-350` 三分支齐全——全成功「全部图片已保存到相册」、`successCount === 0` →「本次未能保存任何图片，请检查网络或相册权限」、部分成功 →「保存完成，有 N 项失败，点击红色标记可重试」。

## 3. 干净构建 — PASS

```text
$ cd frontend && rm -rf dist && npm run build:mp-weixin
exit=0
DONE  Build complete.
运行方式：打开 微信开发者工具, 导入 dist/build/mp-weixin 运行。

$ node -e "const j=require('./dist/build/mp-weixin/app.json');console.log(...)"
{"pages":["pages/index/index","pages/mine/mine"],
 "tabBar":[{"pagePath":"pages/index/index","text":"提取"},{"pagePath":"pages/mine/mine","text":"我的"}]}

$ npm run build:h5
exit=0  DONE  Build complete.
```

`dist` 由验收方删除后全新生成，未复用前端产物。

## 4. r1 PASS 项回归 — 全部 PASS

| 项 | 结果 | 证据 |
|---|---|---|
| stageMedia 假成功 | PASS | `parse.js:177-191` success 非 200/非 ok → reject，fail → reject；H5 分支 `:196-201` 直接 throw；全文件无 `resolve({ ok: true, cloudID: item.remoteUrl })` |
| createZip | PASS | `parse.js:211-216` 直接 `throw` `ZIP_NOT_READY`，全文件无 `/zip` 调用 |
| 超时 | PASS | callContainer `timeout: 15000` + 手动 `setTimeout(15000)`；H5 `AbortController` 15000 → `TIMEOUT` |
| 请求体 | PASS | `payload = { url: cleanUrl }`，仅 url；src 内无 cookie/Bearer/Authorization/密钥（grep 仅命中注释与错误码名） |
| appid | PASS | `manifest.json` 两处均为 `wx0000000000000000` |
| 云开发库条件编译 | PASS | `history.js` 的 `wx.cloud.database()` 均在 `// #ifdef MP-WEIXIN` 内，H5 走 `uni.getStorageSync` 兜底 |
| 错误码 | PASS | 7 条齐全（COOKIE_EXPIRED / SHORTLINK_FAIL / TIMEOUT / UNSUPPORTED_PLATFORM / PARSE_FAILED / STAGE_NOT_READY / ZIP_NOT_READY） |
| 无 UI 组件库 | PASS | 依赖仅 `@dcloudio/*` + vue/vite，无 uview/vant/element/taro |
| 仓库卫生 | PASS | `git status --short --untracked-files=all frontend \| wc -l` = 16；`git ls-files frontend` = 0；`.gitignore` 含 node_modules/、dist/、.env、.env.*、!.env.example、.DS_Store、unpackage/、*.log |
| 边界 | PASS | HEAD 仍 `b4a1624`，无 commit/push；`container/` 仅既有 `render_obscura.py`（mtime 22:19:15，早于本轮 22:50 之后的改动） |
| truth | PASS | `status: frozen` / `Freeze/Completed` / `baseline: uncommitted`；`drift clean: true`、`body drift: false`；`stack: uni-app-vue3-vite`；truth.md 193 行有「工程结构与条件编译」；对 HEAD 仅删 2 行（旧 stack + 旧阶段授权句）、加 28 行，AC/错误矩阵未动 |

## 5. evidence.md 一致性 — PASS

evidence.md 的构建台账已换成 r2 数据（22:55:34 build、22:55:41 app.json、22:55:55 未跟踪 16）；TASK-016 说明为「switchTab 后由 index.vue onShow 消费 renlink_auto_parse_url 并自动解析」；TASK-009/013 仍为 stub「显式失败不伪造成功」；TASK-017 仍 BLOCKED。QA 索引已回填 `evidence/qa/l5-qa-r1.md`。

## 6. 保留 P2（不阻塞，建议 l3/l6 冻结时一并处理）

1. `stageMedia` 的 MP 分支在 l3 未冻结时仍会真打一次不存在的 `/stage`（404 快速失败 → reject，无假成功）。建议 l3 冻结前直接 reject，省一次网络请求与日志噪音。
2. `checkClipboard` 提示文案含「社媒」，与 truth UI 规格措辞略有差异。
3. `mine.vue` 用户信息卡片仍是静态占位（无 openid/昵称展示）。
4. evidence.md 顶部 Evidence Index 的 truth/tests/tasks surface 状态仍写 `draft`，与已 frozen 不一致（清理项）。
5. TASK-005 标 done 的措辞「/parse 容器服务联调」略高于实际（本机无真实云托管环境）。

## 7. 未验证（归 TASK-017，BLOCKED）

真实 `/parse` 端到端、真机相册写入与权限弹窗、云开发 `parse_history` 读写与 openid 隔离——缺真实 appid + 真机，本机无法替代。

本报告不含 release 结论，未 commit/push，未修改实现代码、truth 与 `container/`。
