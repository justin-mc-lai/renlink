# 任链接 Renlink

把社交平台分享链接解析成可下载的媒体，在小程序里逐项转存到相册，图片可再打包成 zip 下载。

一个跑在微信云托管里的后端容器 + 一个 uni-app 前端（微信小程序 / H5）。

> 定位：**学习交流用的技术样本**。不承诺可用性、不承诺长期维护、不用于商业用途。使用前请先读文末《免责声明》。

## 这是什么

用户在抖音 / 小红书等 App 里复制分享链接，粘进小程序：

1. **解析**（`POST /parse`）—— 只取元数据与每一项的 `remoteUrl`，不当场下载；
2. **转存**（`POST /stage`）—— 按序下载第 N 项、webp 转 jpg，落到对象存储（COS），返回 `cloudID`；
3. **打包**（`POST /zip`）—— 把已转存的图片打成 zip，同样返回 `cloudID`；
4. 小程序用 `wx.cloud.downloadFile(cloudID)` 拿到文件，视频/图片存相册，zip 走 `wx.shareFileMessage`。

## 架构

```
小程序（2 页，uni-app）
  │  wx.cloud.callContainer  (≤15s，自带 x-wx-openid)
  ▼
云托管容器（Python + Node20 + ffmpeg + yt-dlp + f2）
  ├─ POST /parse        解析，返回逐项 remoteUrl，不落盘
  ├─ POST /stage        下载单项 → webp 转 jpg → COS → cloudID
  ├─ GET  /stage/file   按 task 回读单项
  ├─ GET  /stage/mode   探测当前存储模式
  ├─ POST /zip          打包已转存图片 → zip 的 cloudID
  └─ GET  /health       探活 + 各平台会话（cookie）新鲜度
```

代码分层：

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 路由 | `container/app/routes_*.py` | `/parse`、`/stage`、`/zip`、`/health` |
| 解析器 | `container/app/parsers/` | 抖音（签名 HTTP 主路径 + 可选渲染兜底）、小红书图文、短链还原 |
| 会话/出口 | `container/app/session_bridge.py`、`egress.py` | cookie 池、代理出口，统一注入 `curl_cffi` / `f2` / `yt-dlp` / `httpx` |
| 转存 | `container/app/transcode.py`、`stage_store.py`、`stage_cache.py` | 下载、转码、COS 落地、进行中/失败缓存 |
| 打包 | `container/app/zipkit.py` | 流式 zip，控制内存与体积 |
| 前端 | `frontend/src/` | uni-app（Vue 3），`api/` 封装云调用，`pages/index`、`pages/mine` |
| 契约 | `contract/parse_response.schema.json` | `/parse` 响应结构 |

## 关键硬约束（平台决定的，不是选择）

这些限制直接塑造了上面的设计，改代码时不要绕开：

- **`wx.cloud.callContainer` 单次 ≤ 15s**：所以 `/parse` 只返回元数据，下载拆到 `/stage` 逐项做。
- **云托管单请求 ≤ 60s**：单项转存必须在这个窗口内完成，大文件要拆项处理。
- **单次返回 ≤ 1000 KB**：`/parse` 与 `/zip` 的响应是 JSON，媒体本体一律走 COS `cloudID`，绝不内联。
- **容器无持久盘**：重启即丢。所有中间产物必须落 COS（`cloudID`），本地目录只是临时中转。
- **手机端 `openDocument` 不支持 zip**：zip 只能 `wx.shareFileMessage` 转发出去，不能在小程序内预览。

## 本地运行

后端（容器就绪）：

```bash
docker build -t renlink .
docker run --rm -p 8080:8080 --env-file .env renlink
curl -s localhost:8080/health
```

后端（开发模式，直接用容器里的 app）：

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r container/requirements.txt
uvicorn app.main:app --app-dir container --host 127.0.0.1 --port 8080
```

单元测试：

```bash
pytest -q tests/
```

前端：

```bash
cd frontend
npm install
npm run dev:h5           # 浏览器调试
npm run build:mp-weixin  # 产出小程序包，用微信开发者工具打开 dist/dev/mp-weixin 或 dist/build/mp-weixin
```

> 没有对象存储与云托管环境时，`/stage`、`/zip` 只能跑本地模式或测试替身；解析相关逻辑可用 `tests/` 里的桩独立验证。仓库里不附带任何真实会话或令牌。

## 环境变量

完整占位见 `.env.example`，常用项：

| 变量 | 用途 |
| --- | --- |
| `VITE_API_BASE` | 前端云托管服务名/环境（前端构建期） |
| `COS_BUCKET` / `COS_REGION` / `COS_ENDPOINT` | 对象存储落脚点 |
| `COS_SECRET_ID` / `COS_SECRET_KEY` / `COS_SESSION_TOKEN` | COS 凭据（生产建议用临时密钥 `COS_CREDENTIAL_URL`） |
| `COS_CREDENTIAL_URL` | 动态取临时密钥的地址，优先级高于静态密钥 |
| `SESSION_DB_DSN` / `SESSION_DB_PATH` / `SESSION_DB_TABLE` | 会话池存储（云数据库或本地 sqlite） |
| `SESSION_COS_PREFIX` / `SESSION_POOL_SOURCE` | 会话在 COS 的存放前缀、池来源 |
| `RENLINK_COOKIE_ENV_FILE` | 从环境变量读取各平台 cookie 的文件位置 |
| `DOUYIN_COOKIE` | 抖音会话 cookie |
| `EGRESS_PROXY` | 出口代理；留空为直连 |
| `ENABLE_OBSCURA` / `PLAYWRIGHT_CDP` | 可选的浏览器渲染兜底（默认关闭，镜像内不含 Chromium） |
| `PARSE_RATE_LIMIT_PER_MIN` | `/parse` 每分钟限流 |
| `RENLINK_DISABLE_CACHE` / `RENLINK_RENDER_WAIT_MS` | 关闭缓存、渲染等待时长 |

改任何凭据类变量前先读 `SECURITY.md`。

## 目录说明

```
container/          云托管后端（FastAPI）：app/ 业务、requirements.txt、entrypoint.sh
frontend/           uni-app 前端：src/pages、src/api、src/utils
contract/           /parse 响应 JSON Schema
tests/              后端单测（pytest）
ops/                本地与线上运维脚本（探针、冒烟、状态巡检）
docs/PLAN.md        项目计划
docs/beacon/        需求真值（truth/tests/tasks）与设计文档，展示工程方法
Dockerfile          运行镜像（Python 3.11 + Node 20，无 Chromium）
```

`docs/beacon/` 下只保留 `truth.md` / `tests.md` / `tasks.md` / `design/**`，用于展示「需求冻结 → 测试用例 → 任务拆解 → 设计」的做法；`evidence/` 与 `changes/` 已从发布物中移除（可能含本机路径与历史调用样本）。

## 免责声明

- 本项目**仅供学习与交流**，是一个技术实现样本，不提供任何形式的服务承诺或可用性保证。
- 使用者应**遵守各平台的服务条款与当地法律法规**，包括但不限于著作权、个人信息保护与数据安全相关规定。
- **请勿将本项目用于侵权、批量抓取、爬取他人数据或任何商业用途。**
- 本项目**不提供任何明示或暗示的担保**，包括但不限于适销性、特定用途适用性与不侵权担保。**使用风险由使用者自行承担**，作者不对因使用本项目产生的任何直接或间接损失负责。
- 若你是权利方并认为本项目某部分不当，请开 issue 说明，确认后我会移除相关能力或内容。

---

## English (short)

Renlink turns social share links into downloadable media and saves them inside a WeChat Mini Program: videos go to the album, image posts are staged one by one and can be zipped.

Stack: FastAPI container on WeChat Cloud Run (Python + Node, no bundled browser) + uni-app frontend (WeChat Mini Program / H5). Platform limits shape the design — `callContainer` ≤ 15 s, a single request ≤ 60 s, ≤ 1000 KB per JSON response, no persistent disk in the container, and no `openDocument` for zip on mobile — so `/parse` only returns metadata, `/stage` downloads one item at a time to COS, and `/zip` returns a `cloudID`.

This repository is a **learning / reference sample for study and discussion only**. It is not production-ready, comes with **no warranty of any kind**, and must not be used for infringement, bulk scraping, or commercial purposes. You are responsible for complying with the terms of service of each platform and with your local laws. Use at your own risk. If you are a rights holder and object to any part of it, please open an issue and the relevant capability will be removed.

Licensed under the MIT License — see `LICENSE`.
