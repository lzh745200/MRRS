/**
 * 错误消息提取工具（零依赖模块）
 *
 * 刻意不 import element-plus / notify / logger —— 任何视图、API 层、
 * 测试环境都可安全引用，不会引入 ElMessage/ElNotification 的副作用链。
 *
 * ## 为什么要有 isRawAxiosMessage
 *
 * axios 在 4xx/5xx 时生成的 `error.message` 是
 * `Request failed with status code 422` 这类**开发者文案**。它一旦被
 * `ElMessage.error(error.message)` 直接展示，用户看到的就是英文技术串
 * ——这正是 2026-10-25 反馈的问题。所有面向用户的取文案路径都必须
 * 经过本模块，且本模块**保证不返回**这种原文。
 */

/** axios 的原始技术文案（不得展示给用户） */
const RAW_AXIOS_PATTERN = /^Request failed with status code \d{3}$/i
/** 其它不该直出给用户的底层文案 */
const RAW_BROWSER_PATTERNS: RegExp[] = [
  /^Network Error$/i,
  /^timeout of \d+ms exceeded$/i,
  /^Failed to fetch$/i,
  /^Load failed$/i,
]

/** 是否为不得直接展示的底层技术文案 */
export function isRawAxiosMessage(message: unknown): boolean {
  if (typeof message !== 'string') return false
  const text = message.trim()
  if (!text) return false
  return RAW_AXIOS_PATTERN.test(text) || RAW_BROWSER_PATTERNS.some((re) => re.test(text))
}

/** 按 HTTP 状态码给出兜底文案（当服务端没给可读 detail/message 时） */
export function statusFallbackMessage(status: unknown): string {
  switch (status) {
    case 400:
    case 422:
      return '请求参数有误，请检查填写内容后重试'
    case 401:
      return '登录已过期，请重新登录'
    case 403:
      return '权限不足，无法执行该操作'
    case 404:
      return '请求的资源不存在或已被删除'
    case 405:
      return '该操作不被支持'
    case 408:
    case 504:
      return '请求超时，请稍后重试'
    case 409:
      return '数据冲突，请刷新后重试'
    case 413:
      return '提交内容过大，请减小后重试'
    case 429:
      return '操作过于频繁，请稍后再试'
    default:
      return typeof status === 'number' && status >= 500 ? '服务器繁忙，请稍后重试' : ''
  }
}

/**
 * 从 FastAPI 的 `detail` 数组里取可读文案。
 *
 * 后端已对 422 做中文化（`detail` 为字符串），但历史端点/第三方形态仍可能
 * 返回数组，这里做防御性兼容：取前 2 条的 `msg`，自动去掉 "body." 前缀。
 */
function fromDetailArray(detail: unknown[]): string {
  const parts: string[] = []
  for (const item of detail.slice(0, 2)) {
    if (typeof item === 'string') {
      if (item.trim()) parts.push(item.trim())
      continue
    }
    if (item && typeof item === 'object') {
      // FastAPI 用 msg；部分自定义校验器/历史形态用 message —— 两者都认
      const record = item as { msg?: unknown; message?: unknown }
      const msg = typeof record.msg === 'string' ? record.msg : record.message
      if (typeof msg === 'string' && msg.trim()) {
        // 不再回拼 "body." 前缀：后端 422 已带中文字段名，前缀只会更吵
        parts.push(msg.trim())
      }
    }
  }
  return parts.join('；')
}

/** 从响应体里提取服务端文案（message 优先，其次 detail / errors） */
export function extractServerMessage(error: any): string {
  const data = error?.response?.data ?? error?.data
  if (!data) return ''

  if (typeof data === 'string') {
    // 非 JSON 响应体：只在看起来不是 HTML/技术串时使用
    const text = data.trim()
    if (text && !text.startsWith('<') && text.length <= 200) return text
    return ''
  }
  if (Array.isArray(data)) return fromDetailArray(data)

  const message = data.message
  if (typeof message === 'string' && message.trim()) return message.trim()

  const detail = data.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail)) {
    const joined = fromDetailArray(detail)
    if (joined) return joined
  }

  const errors = data.errors
  if (Array.isArray(errors)) {
    const joined = fromDetailArray(errors)
    if (joined) return joined
  }

  // 嵌套形态：{ error: { message } }
  const nested = data.error?.message
  if (typeof nested === 'string' && nested.trim()) return nested.trim()

  return ''
}

/**
 * 从任意错误对象中提取最适合展示给用户的消息。
 *
 * 优先级：拦截器挂载的 userMessage（含服务端 detail/message 与 Blob 响应体解析）
 * → 服务端 message/detail/errors → 非技术性的 error.message
 * → 按状态码兜底 → 传入的 fallback。
 *
 * **保证**：返回值永不为 axios 原文（如 `Request failed with status code 422`）。
 */
export function getErrorMessage(error: any, fallback = '操作失败'): string {
  if (!error) return fallback

  const userMessage = error?.userMessage
  if (typeof userMessage === 'string' && userMessage && !isRawAxiosMessage(userMessage)) {
    return userMessage
  }

  const serverMessage = extractServerMessage(error)
  if (serverMessage) return serverMessage

  const status = error?.response?.status ?? error?.status
  if (
    error?.code === 'ECONNABORTED' ||
    (typeof error?.message === 'string' && /timeout/i.test(error.message))
  ) {
    return '请求超时，请检查网络后重试'
  }
  if (error?.code === 'ERR_NETWORK' || isRawAxiosMessage(error?.message)) {
    const byStatus = statusFallbackMessage(status)
    return byStatus || '网络连接失败，请检查网络后重试'
  }

  const msg = error?.message
  if (typeof msg === 'string' && msg && !isRawAxiosMessage(msg)) return msg

  const byStatus = statusFallbackMessage(status)
  if (byStatus) return byStatus

  return fallback
}

export default getErrorMessage
