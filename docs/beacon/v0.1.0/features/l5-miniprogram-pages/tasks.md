---
slug: l5-miniprogram-pages
version: v0.1.0
materials_status: current
task_source: acceptance_criteria
depends_on: l1-parser-core, l3-media-delivery
---

# Tasks: l5-miniprogram-pages

## 任务台账

- [ ] TASK-001 前端 uni-app (Vue 3 + Vite) 工程脚手架搭建：在 frontend/ 建立 package.json、vite.config.js、index.html、src/main.js、src/App.vue、src/uni.scss、src/manifest.json 与 src/pages.json（配置主页/个人中心双 TabBar、窗口色调），完成 npm install 与开发构建链路 · ac=AC-011
- [ ] TASK-002 统一请求封装与硬约束守卫：封装 src/api/parse.js，在 MP-WEIXIN 下使用 wx.cloud.callContainer，超时设为 15000ms；H5 下支持 VITE_API_BASE 兜底；前置校验严禁包含 cookie 字段，单次请求体控制在 10KB 内 · ac=AC-011
- [ ] TASK-003 剪贴板监听与智能识别逻辑：主页 onShow 实现 uni.getClipboardData 嗅探，正则过滤抖音与小红书特征链接，实现浮层弹窗提示与一键填入防重复机制 · ac=AC-001
- [ ] TASK-004 主页输入卡片与交互样式：在 index.vue 中实现 textarea 输入框、一键清空按钮、粘贴按钮与各态按钮视觉交互（Normal/Hover/Loading/Disabled） · ac=AC-002
- [ ] TASK-005 /parse 容器服务联调与加载骨架：对接 l1 的 POST /parse 契约，实现解析中闪烁骨架屏动效与结果数据结构标准化存储 · ac=AC-002
- [ ] TASK-006 业务错误码拦截与人话提示：封装 src/utils/errors.js，对 COOKIE_EXPIRED、SHORTLINK_FAIL、TIMEOUT、UNSUPPORTED_PLATFORM 等错误信封做统一文案转换与页面异常态渲染 · ac=AC-007
- [ ] TASK-007 视频解析结果卡片组件：渲染视频封面、播放图标覆盖层、平台 Tag、标题截断及「保存视频到相册」主按钮 · ac=AC-003
- [ ] TASK-008 图文解析结果九宫格组件：渲染多图网格、总张数徽标、点击 uni.previewImage 全屏大图浏览与手势缩放支持 · ac=AC-004
- [ ] TASK-009 逐项单文件保存调度器：实现「一文件一请求」串行任务队列，顺序调用 l3 的 POST /stage 接口 stub 获取 cloudID（待 l3 truth 冻结后复核），在 MP-WEIXIN 下调用 wx.cloud.downloadFile 下载临时文件 · ac=AC-004
- [ ] TASK-010 相册保存与步进进度控制：封装 src/utils/album.js，集成 wx.saveImageToPhotosAlbum 与 wx.saveVideoToPhotosAlbum，实现「正在转存并保存第 (i/N) 张图片...」实时进度条，H5 端平滑降级 · ac=AC-004
- [ ] TASK-011 保存单项容错与独立重试：逐项保存失败不中断队列，收集失败项 index，渲染红色失败角标与独立「重试」点击按钮 · ac=AC-005
- [ ] TASK-012 系统相册权限防护体系：保存前检测 scope.writePhotosAlbum 授权状态，被拒时弹出模态确认弹窗并引导调用 uni.openSetting 开启权限 · ac=AC-008
- [ ] TASK-013 多图 ZIP 导出与微信会话转发：按 l6 冻结契约调用 POST /zip（传 `task_id`，可选 `indexes`），读取 `{ok,fileID,bytes,count}`，端侧下载后通过 `wx.shareFileMessage` 唤起转发会话（PC 降级 `saveFileToDisk`） · ac=AC-006
- [ ] TASK-014 历史记录数据库直写服务：封装 src/api/history.js，主页解析成功后在 MP-WEIXIN 下调用 wx.cloud.database() 直写 parse_history 集合，非微信端降级 localStorage · ac=AC-010
- [ ] TASK-015 个人中心页面布局与 openid 直读：实现 src/pages/mine/mine.vue，调用历史直读接口查询当前用户历史 · ac=AC-009
- [ ] TASK-016 历史记录空态、分页加载与再次解析：实现历史空态引导插画、上拉触底分页加载、点击复制原链接、点击「再次解析」自动回填主页解析 · ac=AC-009
- [ ] TASK-017 iOS 与 Android 真机全链路联调与验收：在 iPhone 和 Android 真机上运行体验版，录制端到端粘贴->解析->存相册->历史落库全流程证据 · ac=AC-012

---

## 依赖关系与联调顺序

```
[TASK-001 uni-app 脚手架搭建]
       │
       ▼
[TASK-002 请求封装 + 约束守卫] ──> [TASK-003 剪贴板识别] ──> [TASK-004 主页输入区]
       │
       ▼
[TASK-005 对接 l1 POST /parse] ──> [TASK-006 错误信封转换]
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[TASK-007 视频结果卡片]           [TASK-008 图文结果九宫格]
       │                                 │
       ▼                                 ▼
[TASK-009 单文件转存调度 (对接 l3 stub)] <──┘
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[TASK-010 相册写入与进度]         [TASK-011 单项容错与重试]
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[TASK-012 相册授权引导]           [TASK-013 ZIP 导出转发 (对接 l6 stub)]
       │
       ▼
[TASK-014 历史服务 src/api/history.js] ──> [TASK-015 个人中心 mine.vue] ──> [TASK-016 空态/分页/再次解析]
       │
       ▼
[TASK-017 双真机端到端全链路验收 (iOS + Android)]
```

### 联调顺序说明
1. **阶段 1：脚手架与基础构建**：完成 `frontend/` 工程搭建，验证 `npm run build:mp-weixin` 产出合规 `dist/build/mp-weixin` 与双页配置。
2. **阶段 2：容器解析联调（对接 l1）**：连接云托管测试环境，用真实抖音短链与小红书链接测试 `POST /parse`，验证数据清洗与请求体积约束。
3. **阶段 3：媒体转存联调（对接 l3 stub，待 l3 truth 冻结后复核）**：联调 `POST /stage`，验证单文件串行调用、15s 超时控制、云存储 cloudID 回传与 `wx.cloud.downloadFile` 下载。
4. **阶段 4：端侧系统能力联调（按 l6 冻结契约联调 /zip）**：按 l6 冻结契约联调 `/zip`，重点验 `STAGE_EXPIRED`/`ZIP_NOT_READY` 文案；在手机上测试相册授权、`wx.saveImageToPhotosAlbum` 保存、`wx.shareFileMessage` 转发 ZIP 文件。
5. **阶段 5：云开发数据库联调**：验证小程序端直写 `parse_history`、按 openid 自动隔离、列表分页与空态展示。
6. **阶段 6：双真机综合验收**：在真实 iPhone 和 Android 手机上完整录制验收视频，提交验收员独立检验。

---

## 交付物清单

| 交付路径 | 类型 / 内容 |
|---------|------------|
| `frontend/package.json` | 前端依赖配置文件（Vue 3 + Vite + uni-app） |
| `frontend/vite.config.js` | Vite 构建配置文件（配置 @dcloudio/vite-plugin-uni） |
| `frontend/src/manifest.json` | uni-app 跨端配置文件（微信小程序 appid 占位符） |
| `frontend/src/pages.json` | 页面路由配置与 TabBar 定义（主页、个人中心） |
| `frontend/src/App.vue` | 应用入口与生命周期管理 |
| `frontend/src/main.js` | Vue 3 初始化入口 |
| `frontend/src/uni.scss` | 全局基础样式与设计系统变量 |
| `frontend/src/pages/index/index.vue` | 主页单文件组件：剪贴板提示条、输入区、解析卡片、结果九宫格、逐张保存、进度条 |
| `frontend/src/pages/mine/mine.vue` | 个人中心单文件组件：用户信息卡、历史列表、空态插画与操作按钮 |
| `frontend/src/api/parse.js` | 统一云托管 callContainer 封装，含 15s 硬超时与无 cookie 拦截，支持 H5 兜底 |
| `frontend/src/api/history.js` | 云开发数据库 parse_history 集合读写服务模块，支持 H5 localStorage 兜底 |
| `frontend/src/utils/album.js` | 相册授权检查与 wx.openSetting 二次引导及保存工具库 |
| `frontend/src/utils/errors.js` | 业务错误码拦截与人话文案转换映射 |

---

## 边界

勾选框是 AC 绑定的正式台账。只有在绑定的验收证据（真机录屏或测试报告）真实生成并归档至 `evidence/l5/` 时，复选框才允许被标记为 `[x]`。本阶段（truth 阶段）严禁提前自勾自证，严禁编写未经验证的代码。
