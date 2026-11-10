/**
 * 业务错误码与人话文案映射矩阵
 */
export const ERROR_MESSAGES = {
  COOKIE_EXPIRED: '服务维护中，请稍后重试',
  SHORTLINK_FAIL: '分享链接已失效',
  TIMEOUT: '网络服务超时，请重试',
  UNSUPPORTED_PLATFORM: '请输入有效的抖音或小红书链接',
  INVALID_URL: '请输入有效的抖音与小红书链接',
  PARSE_FAILED: '解析失败，请检查链接后重试',
  NETWORK_ERROR: '网络连接失败，请检查网络设置',
  STAGE_NOT_READY: '转存服务暂未上线',
  ZIP_NOT_READY: '打包导出暂未上线',
  RATE_LIMITED: '请求过于频繁，请稍后重试',
  TOO_LARGE: '内容超出限制：视频超过 200MB 或图文超过 20 张，请压缩视频或减少张数后重试'
}

/**
 * 获取错误码对应的人话提示文案
 * @param {string} code 错误码
 * @param {string} fallback 默认兜底文案
 * @returns {string}
 */
export function getErrorMessage(code, fallback = '解析失败，请重试') {
  if (!code) return fallback
  return ERROR_MESSAGES[code] || fallback
}
