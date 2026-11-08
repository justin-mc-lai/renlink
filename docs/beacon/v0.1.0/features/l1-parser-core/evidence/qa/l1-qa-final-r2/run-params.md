# 本轮容器启动参数（全部 pin 到 renlink-l1-final:latest = sha256:cf44f898…）

统一参数：`--env-file /tmp/renlink_qa_r2.env`（仅 DOUYIN_COOKIE / XHS_COOKIE，取自 `~/.config/renlink/cookies.env`，去外层引号；文件 0600，验完删除，值不入证据）。

| 用途 | 容器名 | host→容器端口 | 额外 env |
|---|---|---|---|
| 主路径 accept_local + 默认 smoke | renlink-qa-r2-main | 127.0.0.1:18094→8080 | PARSE_RATE_LIMIT_PER_MIN=0 |
| TC-009 | renlink-qa-r2-stub | 127.0.0.1:18095→8080 | PARSE_RATE_LIMIT_PER_MIN=0, PARSE_STUB_COOKIE_EXPIRED=douyin |
| TC-013 + TC-022 | renlink-qa-r2-delay | 127.0.0.1:18096→8080 | PARSE_RATE_LIMIT_PER_MIN=0, PARSE_UPSTREAM_DELAY_MS=13000 |
| TC-020 | renlink-qa-r2-cache | 127.0.0.1:18097→8080 | PARSE_RATE_LIMIT_PER_MIN=0, RENLINK_DISABLE_CACHE=1 |
| TC-021 | renlink-qa-r2-drop | 127.0.0.1:18098→8080 | PARSE_RATE_LIMIT_PER_MIN=0, RENLINK_DROP_ARGUS_HEADER=1 |
| TC-024 + render probe（默认） | renlink-qa-r2-obscura | 127.0.0.1:18099→8080 | PARSE_RATE_LIMIT_PER_MIN=0, ENABLE_OBSCURA=1 |
| render probe（加私网放行） | renlink-qa-r2-obscura-pn | 127.0.0.1:18092→8080 | PARSE_RATE_LIMIT_PER_MIN=0, ENABLE_OBSCURA=1, OBSCURA_ALLOW_PRIVATE_NETWORK=1 |

每个容器的镜像 id 均由 `docker inspect --format '{{.Image}}'` 核对为 sha256:cf44f898…（与 image.txt 一致）。
客户端：仓库 `.venv/bin/python ops/smoke.py`，`PARSE_BASE` 指向对应端口；样本仅用仓库既有记录：DY_VIDEO_1=`https://v.douyin.com/Y7MgY9YnYAg/`、XHS_VIDEO_1=`https://xhslink.cn/o/1zbdThHpdb0`、DY_SHORT_1 同 DY_VIDEO_1。
