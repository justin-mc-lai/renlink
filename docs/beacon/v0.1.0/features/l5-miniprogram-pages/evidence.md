# Evidence Index: l5-miniprogram-pages

## Evidence Index

| Surface | Authority | Canonical Artifact | Status | Route |
|---------|-----------|--------------------|--------|-------|
| truth | requirement_truth | truth.md | frozen | truth |
| tests | test_truth | tests.md | current | qa |
| tasks | support_advisory | tasks.md | current | implement |
| contract | support_advisory | truth.md 的接口契约章节 | frozen | implement |
| qa | acceptance_truth | l5-qa-r1.md | collected | qa |
| qa | acceptance_truth | l5-qa-r2.md | collected | qa |

## 按 AC 的证据槽位

端侧证据在实现与联调阶段由 smoke_l5 执行器与真机录屏产出，统一命名与用例 ID 对齐。当前处于 truth 阶段，所有执行产物均处于待采集状态，状态一列保持未产生。

| AC | 证据文件 | 采集方式 | 状态 |
|----|----------|----------|------|
| AC-001 | smoke-TC-001.json、smoke-TC-003.json | iPhone 真机剪贴板识别与降级录屏 | 未产生 |
| AC-002 | smoke-TC-001.json、smoke-TC-002.json | 解析触发与 Loading 骨架屏截图 | 未产生 |
| AC-003 | smoke-TC-001.json | iPhone 视频解析并存相册真机录屏 | 未产生 |
| AC-004 | smoke-TC-002.json | Android 图文九宫格与逐张步进存相册录屏 | 未产生 |
| AC-005 | smoke-TC-005.json | 单张转存超时与独立重试录屏 | 未产生 |
| AC-006 | smoke-TC-002.json | ZIP 打包与微信会话转发录屏（契约字段按 {task_id,indexes?} → {ok,fileID,bytes,count} 取证） | 未产生 |
| AC-007 | smoke-TC-004.json | 错误信封人话提示界面截图 | 未产生 |
| AC-008 | smoke-TC-006.json | 相册权限被拒与 openSetting 恢复录屏 | 未产生 |
| AC-009 | smoke-TC-007.json | 个人中心 openid 历史与空态截图 | 未产生 |
| AC-010 | smoke-TC-001.json、smoke-TC-002.json | parse_history 自动落库与再次解析联动 | 未产生 |
| AC-011 | smoke-TC-001.json、smoke-TC-004.json | callContainer 请求体抓包分析报告 | 未产生 |
| AC-012 | smoke-TC-001.json、smoke-TC-002.json | 双真机端到端全链路验收录屏 | 未产生 |

## 约束证据槽位

| 约束 | 证据 | 状态 |
|------|------|------|
| callContainer 15s 与一文件一请求 | smoke-TC-002.json 的耗时与网络请求序列 | 未产生 |
| 返回包 1000KB 与只回 cloudID | smoke-TC-001.json 的响应大小与键集合 | 未产生 |
| 容器无持久盘，文件进 COS | smoke-TC-001.json 的 downloadFile 结果 | 未产生 |
| zip 用 shareFileMessage | smoke-TC-002.json 的转发调用截图 | 未产生 |
| 小红书 webp 转 jpg | smoke-TC-002.json 的相册文件格式校验 | 未产生 |
| cookie 只做运营方池 | smoke-TC-001.json 的请求头与请求体审计 | 未产生 |
| 历史表按 openid 隔离，小程序端直写 | smoke-TC-007.json 的双账号查询对比 | 未产生 |
| f2 当库用不下载；小红书图文自研 | smoke-TC-001.json 的分阶段网络记录 | 未产生 |

## 真机测试设备登记

两台测试设备（iPhone 14 Pro 与 Xiaomi 13）由测试人员登记在验收台账，登记完成前覆盖矩阵里对应的 e2e 用例保持 BLOCKED。本文件不记录最终判定。


## 本地工程构建与任务执行台账

### 1. 本地构建与代码规范验证记录

| 验证项 | 执行命令 | 时间 (UTC+8) | Exit Code | 关键输出 |
|-------|---------|--------------|-----------|---------|
| 依赖安装 | `cd frontend && npm install` | 2026-11-08 22:38:10 | 0 | `added 545 packages, and audited 546 packages in 58s` |
| 微信小程序构建 (r2) | `npm run build:mp-weixin` | 2026-11-08 22:55:34 | 0 | `DONE Build complete. 运行方式：打开 微信开发者工具, 导入 dist/build/mp-weixin 运行。` |
| 路由页面产物检查 | `node -e "const j=require('<dist/build/mp-weixin/app.json>');console.log(j.pages)"` | 2026-11-08 22:55:41 | 0 | `[ 'pages/index/index', 'pages/mine/mine' ]` |
| 跨端 H5 构建 (可选) | `npm run build:h5` | 2026-11-08 22:45:25 | 0 | `DONE Build complete.` |
| 未跟踪文件治理 | `git status --short --untracked-files=all frontend \| wc -l` | 2026-11-08 22:55:55 | 0 | `16`（配置 `<frontend/.gitignore>` 排除 `node_modules` 与 `dist`，仅保留源码文件） |

### 2. TASK 实施状态明细

| TASK ID | 任务内容概要 | 绑定 AC | 状态 | 说明 |
|---------|-------------|---------|------|------|
| TASK-001 | 前端 uni-app (Vue 3 + Vite) 工程脚手架搭建 | AC-011 | done | <frontend/> 工程与构建配置完整，双页路由与 TabBar 齐全 |
| TASK-002 | 统一请求封装与硬约束守卫 | AC-011 | done | `<src/api/parse.js>` 统一封装 callContainer 且超时 15s，无 cookie；H5 fetch 兜底带 15s AbortController 超时 |
| TASK-003 | 剪贴板监听与智能识别逻辑 | AC-001 | done | `index.vue` onShow 嗅探剪贴板并展示提示条，支持一键填入 |
| TASK-004 | 主页输入卡片与交互样式 | AC-002 | done | textarea、清空、粘贴与按钮状态机齐全 |
| TASK-005 | /parse 容器服务联调与加载骨架 | AC-002 | done | 对接 l1 /parse 契约，支持骨架屏与数据标准化 |
| TASK-006 | 业务错误码拦截与人话提示 | AC-007 | done | `<src/utils/errors.js>` 补齐 STAGE_NOT_READY、ZIP_NOT_READY，5 大业务错误码保持完备 |
| TASK-007 | 视频解析结果卡片组件 | AC-003 | done | 视频封面、播放层、Tag 及保存按钮 |
| TASK-008 | 图文解析结果九宫格组件 | AC-004 | done | 九宫格网格、总张数徽标与大图预览支持 |
| TASK-009 | 逐项单文件保存调度器 | AC-004 | stub | 串行队列已就绪；`/stage` 为 stub + 待办（l3 truth 未冻结），显式失败（STAGE_NOT_READY）不伪造成功 |
| TASK-010 | 相册保存与步进进度控制 | AC-004 | done | `<src/utils/album.js>` 写入相册，实时步进进度展示 |
| TASK-011 | 保存单项容错与独立重试 | AC-005 | done | 失败不中断批次，失败项角标与独立重试点击 |
| TASK-012 | 系统相册权限防护体系 | AC-008 | done | 权限状态检测、被拒弹窗引导 `openSetting` |
| TASK-013 | 多图 ZIP 导出与微信会话转发 | AC-006 | stub | 按 l6 冻结契约真实调用 /zip（传 task_id/indexes，读 fileID），未联调前状态保持未产生 |
| TASK-014 | 历史记录数据库直写服务 | AC-010 | done | `<src/api/history.js>` 直写 `parse_history` 集合 |
| TASK-015 | 个人中心页面布局与 openid 直读 | AC-009 | done | `<src/pages/mine/mine.vue>` 直读历史与用户信息 |
| TASK-016 | 历史记录空态、分页加载与再次解析 | AC-009 | done | 空态插画、触底分页、复制原链接；switchTab 后由 index.vue onShow 消费 renlink_auto_parse_url 并自动解析 |
| TASK-017 | iOS 与 Android 真机全链路联调与验收 | AC-012 | BLOCKED | 待配置正式 appid 与真实 iOS/Android 手机体验版扫码实测 |

## Boundary

本文件是索引与槽位，不放最终判定、不放发布结论。通过与否由独立验收员在真实手机上体验验证后回填。
