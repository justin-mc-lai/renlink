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

/**
 * 单文件转存 stub (对接 l3-media-delivery)
 * // TODO(l3 truth 未冻结): 待 l3 truth 冻结后核对对齐
 * 一文件一请求，耗时 <= 15s，返回 cloudID
 * 约束：l3 未冻结，转存服务不可用时显式失败（STAGE_NOT_READY），严禁伪造成功
 * @param {{ remoteUrl: string, type: string, ext: string, needs_transcode?: boolean }} item
 * @returns {Promise<{ ok: boolean, cloudID: string }>}
 */
export async function stageMedia(item) {
  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    // 待 l3 容器就绪，调用 POST /stage
    wx.cloud.callContainer({
      path: '/stage',
      method: 'POST',
      header: {
        'X-WX-SERVICE': 'renlink-container',
        'content-type': 'application/json'
      },
      data: {
        remoteUrl: item.remoteUrl,
        type: item.type,
        ext: item.ext,
        needs_transcode: Boolean(item.needs_transcode)
      },
      timeout: 15000,
      success(res) {
        if (res.statusCode === 200 && res.data?.ok) {
          resolve(res.data)
        } else {
          const err = new Error(getErrorMessage('STAGE_NOT_READY', res.data?.error?.message))
          err.code = 'STAGE_NOT_READY'
          reject(err)
        }
      },
      fail(err) {
        // // TODO(l3 truth 未冻结): 转存服务未就绪，显式拒绝，严禁伪造成功
        const stageErr = new Error(getErrorMessage('STAGE_NOT_READY'))
        stageErr.code = 'STAGE_NOT_READY'
        reject(stageErr)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  // // TODO(l3 truth 未冻结): 跨端转存服务未就绪，显式拒绝
  const err = new Error(getErrorMessage('STAGE_NOT_READY'))
  err.code = 'STAGE_NOT_READY'
  throw err
  // #endif
}

/**
 * 多图打包 ZIP stub (对接 l6-zip-export)
 * // TODO(l6 truth 未冻结): 待 l6 truth 冻结后核对对齐
 * 约束：l6 未冻结，直接显式拒绝（ZIP_NOT_READY），不打不存在的端点
 * @param {{ cloudIDs: string[], zipName: string }} params
 * @returns {Promise<{ ok: boolean, cloudID: string }>}
 */
export async function createZip(params) {
  // // TODO(l6 truth 未冻结): 打包导出服务未上线，直接显式拒绝
  const err = new Error(getErrorMessage('ZIP_NOT_READY'))
  err.code = 'ZIP_NOT_READY'
  throw err
}
