---
slug: l5-miniprogram-pages
version: v0.1.0
status: frozen
revision_id: R1
language: zh
domain_required: false
ux_required: true
parser_contract: beacon-feature-package-v2
truth_source_model: feature_package_authoritative
package_maturity: filled
materials_status: current
intent_confirmed: true
program_ref: docs/beacon/v0.1.0/lake-proposal.json
run_ref: run_1084fcb4301353f56601ec48
stack: uni-app-vue3-vite
canonical_refs:
  truth: docs/beacon/v0.1.0/features/l5-miniprogram-pages/truth.md
  tests: docs/beacon/v0.1.0/features/l5-miniprogram-pages/tests.md
  tasks: docs/beacon/v0.1.0/features/l5-miniprogram-pages/tasks.md
  evidence: docs/beacon/v0.1.0/features/l5-miniprogram-pages/evidence.md
---

# Requirement Truth: l5-miniprogram-pages

## 人话

任链接微信小程序前端两页（主页 + 个人中心）：主页负责剪贴板智能识别、链接粘贴、一键调用云托管 /parse 接口解析无水印媒体清单，并按「一文件一请求」串行调用 /stage 下载转存后逐项保存至手机系统相册（视频存视频相册、图文逐张存图片相册并提供 ZIP 转发微信好友入口）；个人中心通过微信云开发客户端 SDK 直读数据库中的 openid 隔离历史记录，支持列表展示、快捷复制原链接与重新解析。在 callContainer ≤15s 与返回包 ≤1000KB 的硬边界内，向最终用户提供流畅、无白屏、错误可感知且可自愈的端侧闭环体验。

## User Intent

微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机：视频存相册，图文逐张保存 + zip 导出；个人中心查看历史记录。

## User Intent Snapshot

```yaml
lake_or_ocean: 湖
program: lp_renlink_v1
run_id: run_1084fcb4301353f56601ec48
source: user_intent
utterance: "任链接：微信小程序两页前端（主页粘贴/解析/逐项存相册 + 个人中心 openid 历史）"
goal: "交付微信小程序主页与个人中心两页完整 UI 规格、交互逻辑与真机验收标准：主页支持剪贴板识别、链接粘贴、调用 l1 /parse 解析展示结果、串行调用 l3 /stage 逐项转存至 COS 并保存到手机相册；个人中心通过云开发数据库端侧 SDK 直读直写当前用户 openid 隔离的历史记录"
non_goals: "小程序正式提审（个人主体审核风险高，本期以开发预览版与体验版交付）；用户 cookie 上传（严禁收用户 cookie，cookie 仅由运营方服务端维护）；付费、会员、广告、打赏体系；B站、微博、YouTube、X 等额外平台；服务端自动识别验证码与滑块；zip 打包后端算法（归 l6，l5 仅做触发与 wx.shareFileMessage 转发）；自建 MySQL/Redis 历史服务（统一使用微信云开发内置数据库客户端直写直查）"
constraints: "callContainer 上限 15s 且一文件一请求；返回包上限 1000KB，/stage 只回 ok/fileID/kind/ext/bytes（l3 口径），/zip 只回 ok/fileID/bytes/count 四字段，/parse 只回 remoteUrl；容器无持久盘，文件进 COS；手机端 openDocument 不支持 zip，zip 用 wx.shareFileMessage 转发好友/文件传输助手；小红书 webp 必须后端转 jpg，前端保存转码后图片；cookie 只做运营方池，前端绝不收集 cookie；历史表按 openid 隔离，小程序端直写直查"
scope_mode: lake
```

## 目标

- 主页（pages/index/index）交互闭环：进入页面自动读取系统剪贴板并轻提示引导填入；支持输入框编辑、清空与粘贴；点击解析展示加载态并调用云托管 POST /parse；渲染视频预览或图文九宫格；点击保存相册严格遵循一文件一请求，串行调用 POST /stage 并下载逐项写入相册；单项失败支持独立重试；多图支持引导 ZIP 转发。
- 个人中心页（pages/mine/mine）历史与信息：展示用户头像与脱敏标识；端侧直查云开发数据库 parse_history 集合，按 openid 天然隔离；展示历史卡片，支持复制原链接、快捷再次解析、空态引导与分页加载。
- 系统授权与异常提示体系：相册权限拒绝后引导跳转 wx.openSetting；对服务端错误码 COOKIE_EXPIRED、SHORTLINK_FAIL、TIMEOUT 等精准映射人话文案。

## 非目标

- 不做小程序正式提审与上线发布（本期交付体验版与真机预览）。
- 不做用户 Cookie 输入或上传，前端不提供 Cookie 配置面板，不向后端传递凭证。
- 不做商业化功能：无登录绑定手机号、无 VIP 会员、无广告。
- 不做非白名单平台：前端拦截非抖音和小红书链接。
- 不做自建服务端历史接口：完全由小程序端直写直查云开发数据库。
- 不做前端 ZIP 解压或打包：ZIP 由 l6 后端生成，前端仅调用 wx.shareFileMessage 转发。

## 约束（逐条落地）

| # | 约束原文 | 在本湖的落地方式 | 验证 |
|---|----------|------------------|------|
| C1 | callContainer ≤15s，一文件一请求 | 前端严禁发起合并保存请求；多图保存采用前端调度队列，串行循环执行 POST /stage，每次仅传 1 个条目 URL，耗时严格控制在 15s 内 | AC-004、AC-005 |
| C2 | 返回包 ≤1000KB，只回 fileID | /parse 仅接收轻量 items 数组；/stage 成功响应仅含 ok/fileID/kind/ext/bytes 五个字段，前端只读 fileID；端侧使用 wx.cloud.downloadFile 下载临时文件，不传 Base64 或二进制流 | AC-003、AC-004 |
| C3 | 容器无持久盘，文件必须进 COS | 端侧仅消费 fileID（格式 cloud://...）并在小程序端安全临时下载，绝不依赖容器本地路径 | AC-003、AC-004 |
| C4 | 手机端 openDocument 不支持 zip，zip 用 wx.shareFileMessage | 手机端针对 ZIP 资源，使用返回的 fileID 调用 wx.cloud.downloadFile 获得本地临时路径后，直接调用 wx.shareFileMessage 唤起转发面板分享给微信好友或文件传输助手，PC 端降级支持 wx.saveFileToDisk | AC-006 |
| C5 | 小红书 webp 必须后端转 jpg | 前端不做 Canvas 转码，直接将后端 /stage 转码完成返回的 jpg 临时文件保存入相册，确保 iOS/Android 均能写入系统相册 | AC-004 |
| C6 | cookie 只做运营方池，禁止收用户 cookie | 前端页面无任何 cookie 输入框或上传配置，所有 callContainer 请求体均不带 cookie 字段；遇到 COOKIE_EXPIRED 仅提示系统维护中 | AC-007、AC-011 |
| C7 | 历史表按 openid 隔离，小程序端直写 | 使用 wx.cloud.database() 客户端 SDK 操作集合 parse_history，数据库安全规则配置为仅创建者可读写，客户端由微信底座自动注入 _openid 实现天然隔离 | AC-009、AC-010 |
| C8 | f2 当库用不下载；小红书图文自研 | 前端遵循严格两阶段节奏：Stage 1 仅调用 /parse 拿到轻量元数据并展示；Stage 2 只有用户点击保存时才按需触发 /stage 单文件转存，避免预览产生无效流量与存储 | AC-002、AC-003 |

## Alignment Surface

本湖是任链接产品直接面向终端用户的交互表面，承担全部用户输入、视觉呈现、端侧保存与历史查看体验。上游消费 l1 的 /parse 解析清单、l3 的 /stage 媒体转存服务与 l6 的 /zip 打包服务；数据层直连微信云开发数据库。

## UI 规格说明书（前端实现手册级）

### 1. 全局设计规范
- 画布基准：微信小程序标准 750rpx 宽度响应式布局。
- 色彩规范：品牌主色 `#07C160`（微信绿）；平台辅助色 `#FE2C55`（抖音红）与 `#FF2442`（小红书红）；警告色 `#FA5151`；背景主色 `#F7F8FA`；卡片纯白 `#FFFFFF`（圆角 16rpx）；主要文字 `#191919`，次要文字 `#7F7F7F`。

### 2. 主页（pages/index/index）结构与规格
- 页面区块垂直流向：
  1. 顶部导航栏：标题「任链接 - 社媒无水印提取」，纯白背景。
  2. 剪贴板智能提示条：位于输入卡片上方，仅在检测到有效链接时浮现，字号 24rpx。
  3. 链接输入卡片：textarea 多行输入，高度 180rpx，支持滚动；右下角含「清空」文字按钮与「粘贴剪贴板」快捷按钮（高度 56rpx，圆角 28rpx）。
  4. 主解析按钮：宽度 100%，高度 88rpx，圆角 44rpx，加粗字号 32rpx。文案「一键解析提取」。
  5. 骨架屏/解析中状态：展示闪烁动画卡片，文案「正在高速解析中，请稍候...」，解析按钮呈现 loading 旋转圆圈。
  6. 解析结果展示卡片：头部含平台 Tag、内容类型 Tag、标题截断；视频模式展示 16:9 封面与居中播放图标；图文模式展示九宫格缩略图（每张 218rpx * 218rpx，间距 12rpx），支持点击全屏大图预览。
  7. 保存操作与进度控制区：单视频「保存视频到相册」；图文「一键保存全部图片 (共 N 张)」；辅助入口「打包导出 ZIP 并转发」；保存时展示进度条与步进文案「正在转存并保存第 (i/N) 张图片...」；单项失败标红并提供独立「重试」按钮。

### 3. 按钮状态定义表

| 按钮类型 | 状态 | 背景色 / 边框 | 文字颜色 | 交互表现 |
|---------|------|--------------|---------|---------|
| 解析按钮 | Normal（正常） | `#07C160` | `#FFFFFF` | 可点击，缩放微反馈 |
| 解析按钮 | Loading（解析中）| `#07C160` (透明度 0.6) | `#FFFFFF` | 禁用点击，显示 loading spinner，文字「正在解析...」 |
| 解析按钮 | Disabled（禁用）| `#CCCCCC` | `#FFFFFF` | 输入框为空时禁用，点击无响应 |
| 保存全部按钮 | Normal | `#07C160` | `#FFFFFF` | 可点击，触发相册权限检查与批量转存 |
| 保存全部按钮 | In-Progress | `#F2F3F5` | `#07C160` | 正在保存中，显示进度百分比，禁用重复点击 |
| ZIP 导出按钮 | Normal | 背景白 / 边框 `#07C160` | `#07C160` | 可点击，触发 l6 ZIP 生成与转发 |
| 单项重试按钮 | Error-Retry | `#FFF0F0` / 边框 `#FA5151` | `#FA5151` | 仅针对失败条目独立触发单文件请求 |

### 4. 个人中心页（pages/mine/mine）结构与规格
- 用户身份卡片：默认圆形头像（120rpx * 120rpx），展示「微信用户」与脱敏 UID。
- 历史记录标题栏：左侧标题「解析历史」，右侧「下拉可刷新」。
- 历史列表容器：卡片高度 160rpx，间距 16rpx。左侧缩略图（120rpx * 120rpx），中间展示平台 Tag、标题、条数与解析时间；右侧提供「复制链接」与「再次解析」按钮。
- 历史记录空态：垂直居中展示 240rpx 插画，文案「暂无解析记录，快去主页提取第一个链接吧」，附带「去解析」主操作按钮。
- 分页与触底：每页 10 条，触底展示加载动效，无更多数据展示底线。

### 5. 异常提示与人话文案矩阵

| 场景 / 触发条件 | HTTP 状态 / error.code | 页面表现 | 用户可见标准文案 | 推荐后续操作 |
|----------------|----------------------|---------|-----------------|------------|
| 剪贴板无有效链接 | 无 | 输入框保留为空，不做多余打扰 | 静默不展示 | 用户手动粘贴 |
| 输入框内容非法 | 客户端本地校验未匹配域名 | 输入框下方红色文字提示 | 请输入有效的抖音或小红书链接 | 重新检查复制内容 |
| 抖音 Cookie 失效 | 503 / COOKIE_EXPIRED | 结果区域展示错误卡片 | 服务维护中，请稍后重试 | 引导稍后重试，不索要 cookie |
| 短链失效 / 404 | 422 / SHORTLINK_FAIL | 错误提示弹窗 | 分享链接已失效或内容已被作者删除 | 重新在对应 App 复制 |
| 接口超时 | 504 / TIMEOUT | 错误提示弹窗 | 网络或解析服务超时，请重试 | 提供重新解析按钮 |
| 非目标平台 | 400 / UNSUPPORTED_PLATFORM | 底部 Toast | 仅支持抖音与小红书分享链接 | 清空输入框 |
| 单张图片转存超时 | 单次 /stage 调用 >15s 或报错 | 保存进度条停顿，该项标红 | 第 X 张图片转存失败，可单独重试 | 点击该项右侧重试按钮 |
| 相册权限初次被拒 | scope.writePhotosAlbum 失败 | 弹出系统模态确认框 | 需要相册权限才能将视频/图片保存到手机 | 确认后唤起 wx.openSetting |
| 下载临时文件失败 | downloadFile 失败 | 轻提示 Toast | 图片下载失败，请检查网络 | 允许单项重试 |

## Open Questions

| Q ID | Question | Recommendation | Status | Answer |
|------|----------|----------------|--------|--------|
| Q1 | 剪贴板识别是否在每次进入页面都无条件弹窗？ | 仅在剪贴板内容匹配抖音/小红书域名特征、且与当前输入框内容不同时提示一次，避免重复打扰 | answered | 作者按交互规范固化：在 onShow 中匹配正则，命中且与上次填入不同时弹出轻浮层提示 |
| Q2 | 多图保存时如果中间某张图片转存失败，如何处理？ | 采用容错降级模式：继续完成剩余图片，将失败项标红并提供单独重试按钮，不整批废弃 | answered | 作者固化：前端维护状态数组记录每项状态（待处理、转存中、已保存、失败），错误项支持点击单独重新触发 /stage |
| Q3 | 手机端无法打开 ZIP，如何引导用户？ | 下载 ZIP 本地临时文件后调用 wx.shareFileMessage 唤起微信文件转发面板 | answered | 作者固化：前端提示 ZIP 文件已生成，请转发至文件传输助手或微信好友，直接调起官方会话选择器 |
| Q4 | 历史记录按 openid 隔离由谁保证？ | 微信云开发数据库客户端 SDK 自动在 insert 时注入 _openid，并在查询时自带该环境用户鉴权 | answered | 作者固化：无需自建鉴权服务，集合规则配置为仅创建者可读写，小程序端直接 db.collection 查询 |
| Q5 | 用户拒绝相册授权后再次点击保存如何处理？ | 拦截授权失败回调，弹窗提示必须授权相册才能保存，点击去设置调用 wx.openSetting | answered | 作者固化：遵循微信规范，通过 wx.getSetting 检查权限，若已拒绝则弹窗引导打开设置页 |
| Q6 | /stage 契约字段是否已最终冻结？ | 已按 l3 冻结确认：{task_id,index} → {ok,fileID,kind,ext,bytes} | closed | 已按 l3 冻结确认：{task_id,index} → {ok,fileID,kind,ext,bytes}，见 changes/chg_1c6f5fa13031 |
| Q7 | /zip 契约字段是否已最终冻结？ | 已按 l6 冻结确认：{task_id,indexes?} → {ok,fileID,bytes,count} | closed | 已按 l6 冻结确认：{task_id,indexes?} → {ok,fileID,bytes,count}，见 changes/chg_1c6f5fa13031 |

## Intent Coverage

| AC ID | Intent Source | Evidence |
|-------|---------------|----------|
| AC-001 | 目标 1：剪贴板智能识别与一键填入 | tests.md TC-001、TC-003 |
| AC-002 | 目标 1：链接解析发起与 Loading 态展示 | tests.md TC-001、TC-002 |
| AC-003 | 目标 1 与约束 C2、C8：视频解析结果展示与保存入相册 | tests.md TC-001 |
| AC-004 | 目标 1 与约束 C1、C5：图文九宫格展示与逐项步进保存 | tests.md TC-002 |
| AC-005 | 目标 1 与约束 C1：保存失败单项容错与独立重试 | tests.md TC-005 |
| AC-006 | 目标 1 与约束 C4：多图 ZIP 导出与微信会话转发引导 | tests.md TC-002 |
| AC-007 | 目标 3 与约束 C6：业务错误码映射与人话提示 | tests.md TC-004 |
| AC-008 | 目标 3：相册授权被拒检测与 openSetting 恢复引导 | tests.md TC-006 |
| AC-009 | 目标 2 与约束 C7：个人中心 openid 历史直查与空态 | tests.md TC-007 |
| AC-010 | 目标 2 与约束 C7：解析成功自动落库与再次解析联动 | tests.md TC-001、TC-002 |
| AC-011 | 约束 C1、C2、C6：请求信封无 cookie 与参数上限 | tests.md TC-001、TC-004 |
| AC-012 | 整体目标：真机端到端全链路闭环（iOS + Android） | tests.md TC-001、TC-002 |

## Acceptance Criteria

| AC ID | Criterion |
|-------|-----------|
| AC-001 | 主页在 onShow 时读取剪贴板，命中合规社媒链接且未重复填入时展示浮动提示框「检测到分享链接，是否填入？」；用户点击「立即填入」后将纯净链接填入输入框并清空剪贴板；剪贴板无匹配链接与无权限场景静默降级为手动粘贴 |
| AC-002 | 点击「一键解析提取」按钮时，按钮进入 loading + disabled 状态；前端向云托管发起 POST /parse，请求体包含 `{ "url": "..." }` 且绝对不包含任何 cookie 键；成功后渲染结果卡片并恢复按钮状态 |
| AC-003 | 当 /parse 返回 content_type=video 时，结果卡片展示视频封面、标题截断、平台徽标与「保存视频到相册」按钮；点击后携带 `task_id` 与 `index` 发起 POST /stage 请求单文件转存，按 `{ok,fileID,kind,ext,bytes}` 读取并用 fileID 调 `wx.cloud.downloadFile` 下载，通过 wx.saveVideoToPhotosAlbum 写入手机系统相册，Toast 提示「视频已保存到相册」 |
| AC-004 | 当 /parse 返回 content_type=note 时，结果卡片以九宫格展示图片列表并标注总张数；点击「一键保存全部图片」后，前端按队列顺序逐项发起 POST /stage（一文件一请求，每次耗时 ≤15s），展示实时步进进度文案 `正在转存并保存第 (i/N) 张图片...`；每张图下载后通过 wx.saveImageToPhotosAlbum 保存入相册；全部完成后 Toast 提示「全部图片已保存到相册」 |
| AC-005 | 在图文逐项保存过程中，若某一项请求发生网络超时异常，不终止剩余未保存项；保存队列结束后，将失败项角标置为红叉并在下方展示独立重试按钮，点击仅对失败单项重新触发 /stage 与相册写入，重试成功后恢复正常态 |
| AC-006 | 在图文模式下展示「打包导出 ZIP」副操作按钮；点击后携带当前解析任务的 `task_id` 与可选 `indexes` 向云托管发起 POST /zip，按 `{ok,fileID,bytes,count}` 读取结果，用返回的 `fileID` 调用 `wx.cloud.downloadFile` 下载到本地临时文件，再调用 `wx.shareFileMessage` 唤起微信聊天选择面板，展示提示「ZIP 已生成，请选择微信好友与文件传输助手进行保存」 |
| AC-007 | 当 /parse 请求返回业务错误信封 ok=false 时，界面精准映射错误码并展示人话文案：COOKIE_EXPIRED 提示「服务维护中，请稍后重试」；SHORTLINK_FAIL 提示「分享链接已失效」；TIMEOUT 提示「网络服务超时，请重试」；INVALID_URL 提示「请输入有效的抖音与小红书链接」 |
| AC-008 | 用户初次触发保存相册时正常申请 scope.writePhotosAlbum 权限；若用户点击拒绝，再次触发保存时弹出模态弹窗「需要相册权限才能将视频/图片保存到手机」，点击「去设置」直接调用 wx.openSetting 引导用户手动开启，开启返回后能继续执行保存 |
| AC-009 | 个人中心页进入时，端侧 SDK 直查云开发数据库 parse_history 集合，按 create_time 倒序加载前 10 条记录；当集合中无当前用户记录时，展示友好的空态插画与「暂无解析记录，去主页提取」引导按钮；上拉触底时平滑加载下一页 |
| AC-010 | 主页每次成功获取 /parse 清单后，前端端侧自动调用 db.collection('parse_history').add(...) 记录该次解析的元数据（包含 original_url, title, cover, platform, content_type, item_count, create_time）；在个人中心点击任一历史卡片提供「复制链接」与「再次解析」双操作，点击「再次解析」携带原链接返回主页并自动执行解析 |
| AC-011 | 前端发出的所有 callContainer 请求体大小均不超过 10KB 且严格不含任何 Cookie 字段；接收的所有响应包体均不超过 1000KB；容器请求 timeout 参数均显式设为 15000（15秒） |
| AC-012 | 在真实 iPhone（iOS）与真实 Android 手机上分别完成完整验收链路：进入主页自动/手动粘贴分享链接 -> 触发解析成功展示卡片 -> 点击保存成功写入手机原生相册 -> 进入个人中心查看到新增的历史卡片，链路全程无卡死、无报错崩溃 |

## 页面状态与交互流转

| 当前状态 | 触发事件 | 守卫条件 | 目标状态 | 动作 |
|---------|---------|---------|---------|------|
| IDLE（初始空闲） | ON_SHOW | 剪贴板匹配有效链接 | CLIPBOARD_DETECTED | 展示浮动粘贴引导条 |
| IDLE / CLIPBOARD_DETECTED | INPUT_CHANGE | 输入框非空且符合白名单 | READY_TO_PARSE | 解析按钮解除禁用 |
| READY_TO_PARSE | CLICK_PARSE | 无在途请求 | PARSING | 按钮 loading，发起 POST /parse |
| PARSING | PARSE_SUCCESS | 返回 ok=true 且有 items | RESULT_SHOWN | 渲染结果卡片，异步落库 parse_history |
| PARSING | PARSE_FAIL | 返回 ok=false 或网络异常 | ERROR_SHOWN | 映射错误码，展示人话文案与重试入口 |
| RESULT_SHOWN | CLICK_SAVE | 相册权限已授予 | SAVING_MEDIA | 启动单文件/逐项步进保存队列 |
| RESULT_SHOWN | CLICK_SAVE | 相册权限未授予/被拒 | AUTH_PENDING | 弹窗引导 wx.openSetting |
| AUTH_PENDING | AUTH_SUCCESS | 用户在设置页开启权限 | SAVING_MEDIA | 恢复保存队列执行 |
| SAVING_MEDIA | SAVE_PROGRESS | 还有剩余待转存项 | SAVING_MEDIA | 更新步进文案 (i/N)，发起下一项 /stage |
| SAVING_MEDIA | ITEM_FAIL | 某一项转存/下载失败 | SAVING_MEDIA | 记录该项为错误，继续处理下一项 |
| SAVING_MEDIA | SAVE_ALL_DONE | 全部完成（无失败项） | SAVE_SUCCESS | Toast 提示保存完成，恢复按钮 |
| SAVING_MEDIA | SAVE_ALL_DONE | 存在部分失败项 | PARTIAL_SUCCESS | 提示部分完成，高亮展示失败项单独重试按钮 |
| PARTIAL_SUCCESS | CLICK_RETRY_ITEM | 点击特定失败项 | RETRYING_ITEM | 仅针对该项重新调用 /stage 与写入相册 |

## 工程结构与条件编译

为支持以微信小程序为第一目标平台，同时具备后续跨端编译至 H5/App/其他小程序的能力，前端代码采用 uni-app（Vue 3 + Vite）架构组织，代码根目录位于 `frontend/`：

1. **工程组织与构建工具**：
   - 根目录为 `frontend/`，构建基于 Vite 与 `@dcloudio/vite-plugin-uni` 插件；
   - 依赖统一采用 Vue 3 与 @dcloudio 官方套件，开发语言采用 JavaScript/ESNext + 原生 Vue 3 `<script setup>` 组合式 API；
   - 样式遵循全局设计规范，使用 SCSS 预处理器与 uni-app 标准 `rpx` 响应式单位，严禁引入第三方 UI 组件库，保证轻量高效。

2. **多端平台适配与条件编译策略**：
   - **第一目标平台（MP-WEIXIN）**：
     - 请求通路：使用微信云托管 `wx.cloud.callContainer` 发起 `/parse` 解析请求，超时严格设为 15000ms；
     - 媒体保存：单文件转存与相册写入使用 `wx.cloud.downloadFile` + `wx.saveVideoToPhotosAlbum` / `wx.saveImageToPhotosAlbum`；权限不足时引导 `wx.openSetting`；
     - ZIP 导出：调用 `wx.shareFileMessage` 唤起微信聊天选择面板；
     - 历史记录：通过微信云开发客户端 SDK `wx.cloud.database()` 直连读写 `parse_history` 集合，依赖微信底座天然基于 openid 隔离。
   - **跨端兜底（H5 / App / 独立 Webview）**：
     - 请求通路：通过条件编译（`// #ifndef MP-WEIXIN`）降级走环境变量 `VITE_API_BASE` 配置的标准 RESTful API (`fetch` / `uni.request`)；
     - 媒体保存：H5 降级为直接触发浏览器媒体文件下载或新标签页预览；
     - 历史记录：降级使用本地存储 `uni.getStorageSync` / `uni.setStorageSync` (`localStorage`) 维持离线历史；
     - 条件编译严格遵循 uni-app 规范语法（如 `// #ifdef MP-WEIXIN`、`/* #ifdef MP-WEIXIN */`、`<!-- #ifdef MP-WEIXIN -->`）。

3. **双页结构与交互一致性**：
   - 主页（`src/pages/index/index.vue`）与个人中心（`src/pages/mine/mine.vue`）的双页视觉结构、交互流转、按钮状态机、错误码映射矩阵及所有 AC/TC 验收语义与微信原生小程序规格严格保持 1:1 对齐，不因框架调整产生任何功能降级。

## 接口契约

### 1. 依赖 l1-parser-core 契约（POST /parse）
- 请求方式：wx.cloud.callContainer，路径 /parse，超时 15000ms。
- 请求体：
```json
{
  "url": "https://v.douyin.com/xxxx/"
}
```
- 成功响应契约（HTTP 200）：
```json
{
  "ok": true,
  "platform": "douyin",
  "content_type": "video",
  "source_url": "https://v.douyin.com/xxxx/",
  "resolved_url": "https://www.douyin.com/video/1234567890",
  "title": "视频标题文本",
  "item_count": 1,
  "elapsed_ms": 1250,
  "items": [
    {
      "index": 0,
      "type": "video",
      "remoteUrl": "https://...",
      "ext": "mp4",
      "cover": "https://...",
      "needs_transcode": false
    }
  ]
}
```
- 字段来源与派生说明：
  - l1 的 /parse 成功响应无顶层 cover_url 字段；历史卡片/结果卡片封面优先取 items[0].cover，若首项为图片则取 items[0].remoteUrl（取不到则用占位图）。
  - 端侧入库 parse_history 与回填时，original_url 取 l1 的 source_url，不再另设字段名。
  - source_url（标准化输入短链/原始链接）与 elapsed_ms（解析耗时毫秒数）为必填返回字段，与 l1 契约严格一致。
  - `task_id` 客户端推导：按 l3 Q2 算法，`task_id = "st_" + sha256(v1/platform/content_type/resolved_url/每项 index:type:ext:remoteUrl 换行拼接) 前 24 位`。前端在拿到 `/parse` 清单后按该算法计算并保存 `task_id`，页面状态与历史记录（parse_history）均持久保存该 `task_id`，作为后续调用 `/stage` 与 `/zip` 的唯一任务凭证。
- 失败响应契约（HTTP 4xx/5xx）：
```json
{
  "ok": false,
  "error": {
    "code": "COOKIE_EXPIRED",
    "message": "运营方 cookie 失效，请运营刷新后重试",
    "retryable": true
  },
  "items": [],
  "elapsed_ms": 420
}
```

### 2. 依赖 l3-media-delivery 契约（POST /stage）
按 l3-media-delivery 冻结正文（docs/beacon/v0.1.0/features/l3-media-delivery/truth.md）契约：
- 请求方式：wx.cloud.callContainer，路径 /stage；l3 单请求预算 ≤60s，端侧按 C1 的 callContainer 上限串行调度，每次只发 1 个条目。
- 请求体：
```json
{
  "task_id": "st_1234567890abcdef12345678",
  "index": 0
}
```
- 成功响应契约（HTTP 200）：
```json
{
  "ok": true,
  "fileID": "cloud://env-id.xxx/media/20261108/abc123.jpg",
  "kind": "image",
  "ext": "jpg",
  "bytes": 284736
}
```
- 前端后续处理：端侧调用 wx.cloud.downloadFile({ fileID }) 得到 tempFilePath，随后调用 wx.saveImageToPhotosAlbum 或 wx.saveVideoToPhotosAlbum。
- 失败响应：一律 ok=false 且不含 fileID；错误码按 l3 固定表：400 INVALID_REQUEST（索引越界或清单缺项为 400 STAGE_FAILED）、410 STAGE_EXPIRED、413 TOO_LARGE、502 STAGE_FAILED、503 STAGE_NOT_READY、504 TIMEOUT；前端分别映射人话文案。

### 3. 依赖 l6-zip-export 契约（POST /zip）
按 l6-zip-export 冻结正文（docs/beacon/v0.1.0/features/l6-zip-export/truth.md）契约：
- 请求方式：`wx.cloud.callContainer`，路径 `/zip`，超时 15000ms。
- 请求体：`{ "task_id": "st_<24位小写十六进制>", "indexes": [7,1,7] }`；`indexes` 可省略。
- 成功响应（HTTP 200）：`{ "ok": true, "fileID": "cloud://env-id.xxx/zip/<name>.zip", "bytes": 1048576, "count": 9 }`。
- 前端后续处理：`wx.cloud.downloadFile({ fileID })` 得 tempFilePath → `wx.shareFileMessage({ filePath, fileName })`；PC 端 `wx.saveFileToDisk`。
- 失败响应：一律 `ok=false` 且不含 `fileID`，错误码按 l6 固定表：400 `INVALID_REQUEST`、410 `STAGE_EXPIRED`、413 `TOO_LARGE`、503 `ZIP_NOT_READY`（retryable）、502 `ZIP_FAILED`（retryable）、504 `TIMEOUT`。前端映射人话文案：任务已过期请重新解析；图片数量或体积超限；服务尚未准备好请稍后重试；打包失败请重试；超时请重试。

### 4. 依赖云开发数据库契约（parse_history 集合）
- 集合名称：parse_history
- 安全规则：仅创建者可读写（read: auth.openid == doc._openid, write: auth.openid == doc._openid）。
- 文档 Schema 结构：
```json
{
  "_id": "auto_generated_uuid",
  "_openid": "oXXXXX_wechat_user_openid",
  "original_url": "https://v.douyin.com/xxxx/",
  "resolved_url": "https://www.douyin.com/video/123",
  "platform": "douyin",
  "content_type": "video",
  "task_id": "st_0123456789abcdef012345",
  "title": "视频标题",
  "cover": "https://...",
  "item_count": 1,
  "create_time": 1762600000000
}
```

## 依赖与接缝

- 依赖 l1-parser-core：消费 POST /parse 解析结果。
- 依赖 l3-media-delivery：消费 POST /stage 单文件转存结果。
- 依赖 l6-zip-export：消费 POST /zip 打包结果。
- 依赖云开发数据库：端侧直接访问 parse_history 集合。

## 边界

当前处于 implement 阶段。允许且仅允许编写 `frontend/` 目录下的 uni-app 前端工程代码及本 feature 文档（`truth.md`、`tests.md`、`tasks.md`、`evidence.md`）；禁止改动后端 `container/` 目录、禁止 git commit / git push、禁止自签 QA 结论；前端请求与配置严格禁止包含任何用户 cookie、生产密钥或真实敏感凭据。
