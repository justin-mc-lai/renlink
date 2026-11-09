---
slug: l5-miniprogram-pages
version: v0.1.0
materials_status: current
test_source: acceptance_criteria
env: wechat-miniprogram-real-device
---

# Tests: l5-miniprogram-pages

本测试规程主要面向微信小程序端侧交互、云开发与云托管真实联调验证。测试执行包含两台真实设备（iPhone 与 Android 手机）的真机体验版扫码实测，以及端侧契约与容错验证。测试脚本执行入口为 `python3 ops/smoke_l5.py`，测试证据产物统一登记在 `evidence.md` 对应槽位。待真机采集的用例标记为 BLOCKED，不计通过，也不算失败。

## 前置条件与测试环境

```bash
export WECHAT_APPID="wx_renlink_dev"
export TCB_ENV_ID="renlink-prod-xxx"
export DEVICE_IOS="iPhone 14 Pro, iOS 17.4, WeChat 8.0.48"
export DEVICE_ANDROID="Xiaomi 13, HyperOS/Android 14, WeChat 8.0.48"
export TEST_DY_VIDEO="https://v.douyin.com/xxxxxx/"
export TEST_XHS_NOTE="https://www.xiaohongshu.com/explore/xxxxxx"
export TEST_EXPIRED_LINK="https://v.douyin.com/invalid_or_expired/"
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | e2e | `python3 ops/smoke_l5.py --case ios-clipboard-prompt` | 剪贴板浮条出现，点击自动填入输入框并清空剪贴板 |
| AC-001 | TC-003 | behavior | `python3 ops/smoke_l5.py --case clipboard-fallback` | 无效链接时不弹浮条；系统拒绝权限时平滑降级为手动粘贴 |
| AC-002 | TC-001 | e2e | `python3 ops/smoke_l5.py --case parse-loading` | 点击解析按钮进入 loading+disabled，请求体含 url 且无 cookie |
| AC-002 | TC-002 | e2e | `python3 ops/smoke_l5.py --case xhs-parse-render` | 正常请求 /parse，展示骨架屏并在 3s 内渲染结果卡片 |
| AC-003 | TC-001 | e2e | `python3 ops/smoke_l5.py --case ios-video-album` | 视频封面与标题正确渲染；点击保存视频，系统相册新增该无水印视频文件 |
| AC-004 | TC-002 | e2e | `python3 ops/smoke_l5.py --case android-note-step` | 九宫格展示 N 张图；保存时逐项触发 /stage，步进进度 (i/N) 连续，相册存满 N 张 jpg |
| AC-005 | TC-005 | negative | `python3 ops/smoke_l5.py --case item-save-retry` | 模拟第 2 张请求超时，其余张保存成功；第 2 张角标标红，点击独立重试后保存成功 |
| AC-006 | TC-002 | e2e | `python3 ops/smoke_l5.py --case zip-share` | 点击打包 ZIP，请求体含 task_id 且无 cloudIDs/zipName，响应读 fileID/bytes/count，下载入参为 fileID，调用 wx.shareFileMessage 成功拉起微信聊天选择面板 |
| AC-007 | TC-004 | negative | `python3 ops/smoke_l5.py --case error-envelopes` | 响应 COOKIE_EXPIRED、SHORTLINK_FAIL、TIMEOUT 时，UI 呈现对应人话错误文案 |
| AC-008 | TC-006 | security | `python3 ops/smoke_l5.py --case photos-auth-flow` | 首次拒绝相册权限后再次点击保存，弹出解释模态框，点击去设置打开 wx.openSetting |
| AC-009 | TC-007 | contract | `python3 ops/smoke_l5.py --case history-openid-query` | 个人中心直查云开发数据库，无记录时展示空态插画，有记录时分页展示且仅含当前用户 openid |
| AC-010 | TC-001 | e2e | `python3 ops/smoke_l5.py --case history-auto-add` | 主页解析成功后 parse_history 集合新增 1 条记录，个人中心立即可见且支持再次解析 |
| AC-011 | TC-001 | contract | `python3 ops/smoke_l5.py --case request-budget` | 网络面板抓包验证 callContainer 请求体 <10KB 且无 cookie 键，耗时 <15s |
| AC-012 | TC-001 | e2e | `python3 ops/smoke_l5.py --case ios-full-chain` | iPhone 真机全链路贯通：粘贴->解析->存相册->历史落库 |
| AC-012 | TC-002 | e2e | `python3 ops/smoke_l5.py --case android-full-chain` | Android 真机全链路贯通：粘贴->解析->存相册->历史落库 |

## 用例明细

### TC-001 抖音视频端到端主链路（iOS 真机）
- 设备：iPhone 14 Pro 真机微信客户端。
- 步骤：复制抖音视频分享链接，进入小程序主页，浮条提示识别成功，点击自动填入；点击一键解析提取，展示视频封面与标题；点击保存视频，授权相册后成功存入系统相册；进入个人中心查看历史新增记录。
- 判据：相册新增可播放视频文件，个人中心历史记录落库。

### TC-002 小红书多图端到端主链路与 ZIP 转发（Android 真机）
- 设备：Xiaomi 13 真机微信客户端。
- 步骤：复制小红书多图链接，手动粘贴后解析；渲染九宫格，大图预览正常；点击一键保存全部，观察逐项步进进度 (i/N)，相册完整保存所有 jpg 图片；点击导出 ZIP，成功唤起微信聊天选择面板转发好友。
- 判据：全部图片存入原生相册，wx.shareFileMessage 调起成功，历史记录落库。
- 断言：
  - 请求体断言：POST /zip 请求体严格包含 `task_id`（格式 `st_<24位小写十六进制>`）与可选 `indexes`，绝对不包含 `cloudIDs` 与 `zipName` 字段。
  - 响应字段断言：成功响应严格解析 `ok`、`fileID`、`bytes`、`count` 四字段，其中 `fileID` 必须以 `cloud://` 为前缀并作为 `wx.cloud.downloadFile({ fileID })` 入参。
  - 失败文案断言：503 `ZIP_NOT_READY` 映射为人话提示「服务尚未准备好请稍后重试」，502 `ZIP_FAILED` 映射为人话提示「打包失败请重试」。

### TC-003 剪贴板异常与降级
- 步骤：剪贴板无链接时静默不打扰；系统权限拒绝时不红屏崩溃，平滑降级为手动粘贴。
- 判据：无弹窗打扰，输入框手动粘贴与解析正常。

### TC-004 服务端业务错误码人话文案
- 步骤：Mock 服务端返回 COOKIE_EXPIRED、SHORTLINK_FAIL、TIMEOUT、UNSUPPORTED_PLATFORM。
- 判据：界面精确呈现定义的人话文案，不暴露技术堆栈与错误代码。

### TC-005 图文逐项保存单项失败与独立重试
- 步骤：模拟保存 3 张图片中第 2 张请求超时，第 1 张与第 3 张保存成功；保存队列结束后第 2 张标红并展示独立重试按钮；点击单独重试该项成功。
- 判据：单项失败不中断批次，独立重试机制正常生效。

### TC-006 相册授权拦截与 openSetting 恢复
- 步骤：用户首次拒绝相册权限，再次点击保存时弹出模态弹窗；点击去设置唤起 wx.openSetting 手动开启，返回后能恢复执行保存。
- 判据：弹窗提示清晰，授权恢复后保存成功。

### TC-007 个人中心 openid 历史直查与空态
- 步骤：无记录时展示空态插画与「去解析」引导；有记录时展示卡片列表；不同微信号登录互不可见对方记录；点击卡片再次解析联动跳转主页。
- 判据：openid 隔离完全有效，再次解析联动正常。
