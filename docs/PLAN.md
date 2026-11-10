# 任链接 (Renlink) — 项目计划 v0.1

## 一句话
微信小程序（云托管）把抖音/小红书等社媒链接解析并下载到用户手机：视频存相册，图文逐张保存 + zip 导出。

## 已冻结的程序
- host run: `run_1084fcb4301353f56601ec48`
- 程序/提案: `lp_renlink_v1`（7 湖全选，已 freeze）
- docs: `docs/beacon/v0.1.0/`

```
l1-parser-core ─┬─> l2-xhs-images
                ├─> l3-media-delivery ─┬─> l5-miniprogram-pages ──┐
                └─> l4-session-egress   └─> l6-zip-export          │
                                        l7-risk-compliance <───────┘
```

## 架构（已定）
```
小程序 2 页
  │ wx.cloud.callContainer（≤15s，自带 x-wx-openid）
  ▼
云托管容器（Docker: Python + Node20 + ffmpeg + yt-dlp + f2）
  ├─ POST /parse  只解析，返回逐项 remoteUrl，不下载
  ├─ POST /stage  下载第 N 项 → webp转jpg → 对象存储 COS → cloudID
  ├─ POST /zip    打包已转存图片 → zip 的 cloudID
  └─ GET  /health 探活 + cookie 新鲜度
小程序 wx.cloud.downloadFile(cloudID) → 存相册 / wx.shareFileMessage
历史 云开发数据库（小程序端直写，不买 MySQL）
出口 EGRESS_PROXY（默认空=直连；国内住宅/4G 代理后续接）
```

## 解析分工（源码级结论，别改）
| 平台 | 视频 | 图文 | 短链 |
|---|---|---|---|
| 抖音 | yt-dlp `DouyinIE`（仅 `/video/{id}`）或 f2 | **f2 `dy`**（抓取用库：`DouyinHandler.fetch_one_video` → `PostDetailFilter.images`） | **f2** |
| 小红书 | yt-dlp `XiaoHongShuIE` | **自研**（`window.__INITIAL_STATE__` → `imageList` 原图 + `xsec_token`） | 自研/展开 |

- yt-dlp 的 `XiaoHongShuIE` 只把图片塞进 `thumbnails`（压缩图），不能当原图。
- 本机 f2 0.0.1.7 **没有**小红书 app，只有 bark/douyin/tiktok/twitter/weibo。
- f2 依赖 `pyexecjs` → 容器镜像必须有 Node.js ≥20。
- 抖音图文的逐项 URL 从 f2 的 filter 里取，**/parse 阶段不下载**。

## 硬约束（写代码前必须遵守）
1. `callContainer` ≤15s；单请求 ≤60s → 必须一文件一请求。
2. 返回包 ≤1000KB → 只回 cloudID，不回文件流。
3. 容器无持久盘 → 临时文件必须传 COS。
4. 手机端 `wx.openDocument` 不支持 zip → zip 只能 `wx.shareFileMessage` 转发聊天（PC 用 `saveFileToDisk`）。
5. 小红书 webp 要后端转 jpg，否则存不进相册。
6. cookie 只做运营方池，**禁止收用户 cookie**。

## 湖与验收
| 湖 | 验收 |
|---|---|
| l1-parser-core | 4 类真实链接各返回正确清单（items[].remoteUrl 非空） |
| l2-xhs-images | 10 条图文 ≥9 条拿到原图 |
| l3-media-delivery | 真机存 1 视频 + 9 图 |
| l4-session-egress | 带 cookie 成功率达标；EGRESS_PROXY 可切换；失效返回 COOKIE_EXPIRED |
| l5-miniprogram-pages | 真机两页可用，历史落库 |
| l6-zip-export | 真机收到 zip 并能打开 |
| l7-risk-compliance | 限流/缓存/大小上限/版权声明/投诉入口全绿 |

## 明确不做
小程序正式提审（个人主体审核风险）、用户上传 cookie、B站/微博/YouTube/X、付费/会员/广告、服务端自动过滑块、自建 VPS 替代云托管。

## 常用命令
```bash
cd /Users/apple/Developer/Personal/renlink
beacon-go goal status --run-id run_1084fcb4301353f56601ec48
beacon-go goal program route --run-id run_1084fcb4301353f56601ec48
beacon-go truth list --project .
```

## 证据位置
每个湖：`docs/beacon/v0.1.0/features/<slug>/evidence.md`
