import { getErrorMessage } from '../utils/errors'

// 白名单域名正则校验
const DOUYIN_REGEX = /https?:\/\/(?:v|www)\.douyin\.com\/[^\s]+/i
const XHS_REGEX = /https?:\/\/(?:xhslink\.cn|www\.xiaohongshu\.com|xiaohongshu\.com)\/[^\s]+/i

/**
 * 校验并提取纯净 URL
 * @param {string} rawText 
 * @returns {{ valid: boolean, url: string, platform: 'douyin' | 'xiaohongshu' | null }}
 */
export function extractValidUrl(rawText) {
  if (!rawText || typeof rawText !== 'string') {
    return { valid: false, url: '', platform: null }
  }
  const text = rawText.trim()
  const dyMatch = text.match(DOUYIN_REGEX)
  if (dyMatch) {
    return { valid: true, url: dyMatch[0], platform: 'douyin' }
  }
  const xhsMatch = text.match(XHS_REGEX)
  if (xhsMatch) {
    return { valid: true, url: xhsMatch[0], platform: 'xiaohongshu' }
  }
  return { valid: false, url: '', platform: null }
}

/**
 * 统一请求调用 POST /parse
 * 约束：callContainer <= 15s；请求体 <= 10KB 且严格不含 cookie
 * @param {string} url 
 * @returns {Promise<object>}
 */
export async function parseUrl(url) {
  const { valid, url: cleanUrl } = extractValidUrl(url)
  if (!valid) {
    const error = new Error(getErrorMessage('UNSUPPORTED_PLATFORM'))
    error.code = 'UNSUPPORTED_PLATFORM'
    throw error
  }

  const payload = { url: cleanUrl }
  const payloadStr = JSON.stringify(payload)
  if (payloadStr.length > 10240) {
    const error = new Error('请求体过大')
    error.code = 'REQUEST_TOO_LARGE'
    throw error
  }

  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    if (!wx.cloud) {
      const err = new Error('微信云开发环境未初始化')
      err.code = 'NO_WX_CLOUD'
      return reject(err)
    }

    const timer = setTimeout(() => {
      const timeoutErr = new Error(getErrorMessage('TIMEOUT'))
      timeoutErr.code = 'TIMEOUT'
      reject(timeoutErr)
    }, 15000)

    wx.cloud.callContainer({
      path: '/parse',
      method: 'POST',
      header: {
        'X-WX-SERVICE': 'renlink-container',
        'content-type': 'application/json'
      },
      data: payload,
      timeout: 15000,
      success(res) {
        clearTimeout(timer)
        if (res.statusCode >= 200 && res.statusCode < 300) {
          const body = res.data
          if (body && body.ok) {
            resolve(body)
          } else {
            const errCode = body?.error?.code || 'PARSE_FAILED'
            const msg = getErrorMessage(errCode, body?.error?.message)
            const err = new Error(msg)
            err.code = errCode
            reject(err)
          }
        } else {
          const errCode = res.data?.error?.code || 'PARSE_FAILED'
          const msg = getErrorMessage(errCode, res.data?.error?.message)
          const err = new Error(msg)
          err.code = errCode
          reject(err)
        }
      },
      fail(wxErr) {
        clearTimeout(timer)
        const errMsg = wxErr.errMsg || ''
        if (errMsg.includes('timeout') || errMsg.includes('abort')) {
          const err = new Error(getErrorMessage('TIMEOUT'))
          err.code = 'TIMEOUT'
          reject(err)
        } else {
          const err = new Error(getErrorMessage('PARSE_FAILED'))
          err.code = 'PARSE_FAILED'
          reject(err)
        }
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  const apiBase = import.meta.env?.VITE_API_BASE || ''
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)

  try {
    const res = await fetch(`${apiBase}/parse`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json'
      },
      body: payloadStr,
      signal: controller.signal
    })
    clearTimeout(timer)
    const data = await res.json()
    if (data && data.ok) {
      return data
    }
    const errCode = data?.error?.code || 'PARSE_FAILED'
    const err = new Error(getErrorMessage(errCode, data?.error?.message))
    err.code = errCode
    throw err
  } catch (fetchErr) {
    clearTimeout(timer)
    if (fetchErr.name === 'AbortError') {
      const timeoutErr = new Error(getErrorMessage('TIMEOUT'))
      timeoutErr.code = 'TIMEOUT'
      throw timeoutErr
    }
    if (fetchErr.code) {
      throw fetchErr
    }
    const err = new Error(getErrorMessage('PARSE_FAILED'))
    err.code = 'PARSE_FAILED'
    throw err
  }
  // #endif
}

const API_BASE = import.meta.env?.VITE_API_BASE || ''

/** URL of the staged object, streamed by GET /stage/file. H5/PC download path. */
export function stageFileUrl(fileID) {
  return `${API_BASE}/stage/file?file_id=${encodeURIComponent(fileID)}`
}

/**
 * 单文件转存：POST /stage {task_id, index} -> {ok, fileID, kind, ext, bytes}
 * 一文件一请求；失败按错误码显式抛出，不伪造成功。
 */
export async function stageMedia(item, taskId) {
  if (!taskId) {
    const err = new Error(getErrorMessage('STAGE_EXPIRED'))
    err.code = 'STAGE_EXPIRED'
    throw err
  }
  const payload = { task_id: taskId, index: item.index }

  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    wx.cloud.callContainer({
      path: '/stage',
      method: 'POST',
      header: {
        'X-WX-SERVICE': 'renlink-container',
        'content-type': 'application/json'
      },
      data: payload,
      timeout: 15000,
      success(res) {
        if (res.statusCode === 200 && res.data?.ok) {
          resolve(res.data)
        } else {
          const code = res.data?.error?.code || 'STAGE_FAILED'
          const err = new Error(getErrorMessage(code, res.data?.error?.message))
          err.code = code
          reject(err)
        }
      },
      fail() {
        const err = new Error(getErrorMessage('STAGE_FAILED'))
        err.code = 'STAGE_FAILED'
        reject(err)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  const res = await fetch(`${API_BASE}/stage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (data?.ok) return data
  const code = data?.error?.code || 'STAGE_FAILED'
  const err = new Error(getErrorMessage(code, data?.error?.message))
  err.code = code
  throw err
  // #endif
}

/**
 * 多图打包：POST /zip {task_id, indexes?} -> {ok, fileID, bytes, count}
 */
export async function createZip(taskId, indexes) {
  if (!taskId) {
    const err = new Error(getErrorMessage('STAGE_EXPIRED'))
    err.code = 'STAGE_EXPIRED'
    throw err
  }
  const payload = indexes ? { task_id: taskId, indexes } : { task_id: taskId }

  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    wx.cloud.callContainer({
      path: '/zip',
      method: 'POST',
      header: {
        'X-WX-SERVICE': 'renlink-container',
        'content-type': 'application/json'
      },
      data: payload,
      timeout: 15000,
      success(res) {
        if (res.statusCode === 200 && res.data?.ok) {
          resolve(res.data)
        } else {
          const code = res.data?.error?.code || 'ZIP_FAILED'
          const err = new Error(getErrorMessage(code, res.data?.error?.message))
          err.code = code
          reject(err)
        }
      },
      fail() {
        const err = new Error(getErrorMessage('ZIP_FAILED'))
        err.code = 'ZIP_FAILED'
        reject(err)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  const res = await fetch(`${API_BASE}/zip`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (data?.ok) return data
  const code = data?.error?.code || 'ZIP_FAILED'
  const err = new Error(getErrorMessage(code, data?.error?.message))
  err.code = code
  throw err
  // #endif
}
