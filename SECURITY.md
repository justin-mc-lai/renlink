# Security Policy / 安全说明

## 不要提交的内容

本仓库是公开的技术样本，**任何情况下都不要提交**：

- 真实的平台会话 `cookie`（含 `a1`、`web_session`、`xsec_token` 等分享令牌）；
- 对象存储 / 云厂商密钥（`COS_SECRET_ID`、`COS_SECRET_KEY`、`COS_SESSION_TOKEN`、`TENCENTCLOUD_*`）；
- 数据库连接串中的账号密码、私钥文件、`Bearer` 令牌；
- 抓包日志、`evidence/` 目录下的原始请求与响应样本。

本地调试请用 `.env`（已在 `.gitignore` 中），代码里用环境变量或 `REPLACE_ME` 占位符。提交前至少自查：

```bash
grep -rnE 'xsec_token=[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|' .
# 私钥块另行搜索：文件里出现 "PRIVATE KEY" 头即视为泄露
```

## 报告漏洞

请**私下**报告，不要开公开 issue：

- 通过 GitHub 的 Security 页 → *Report a vulnerability*（Private vulnerability reporting）；
- 或在仓库 *Security* 标签下发起私密安全通告。

请说明：受影响文件/接口、复现步骤、影响范围、你的验证方式。我会确认后修复并在发布说明里致谢（若你愿意署名）。

## 范围

- 范围内：本仓库代码本身的问题，如解析器崩溃、路径穿越、SSRF、限流失效、凭据写入日志等。
- 范围外：第三方平台侧的行为与风控、对象存储与云托管服务的配置（那些由部署者负责）。
