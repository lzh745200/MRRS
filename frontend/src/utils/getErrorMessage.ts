/**
 * 错误消息提取工具（零依赖模块）
 *
 * 刻意不 import element-plus / notify / logger —— 任何视图、API 层、
 * 测试环境都可安全引用，不会引入 ElMessage/ElNotification 的副作用链。
 */

/**
 * 从任意错误对象中提取最适合展示给用户的消息。
 *
 * 优先级：拦截器挂载的 userMessage（含服务端 detail/message 与 Blob 响应体解析）
 * → 服务端 detail → 服务端 message → 错误 message → 兜底文案。
 *
 * 用于替换页面中"加载XX失败，请稍后重试"式的笼统文案，
 * 让用户看到真实原因（如"权限不足""经费记录不存在"）。
 */
export function getErrorMessage(error: any, fallback = '操作失败'): string {
  if (!error) return fallback
  const userMessage = error?.userMessage
  if (typeof userMessage === 'string' && userMessage) return userMessage
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  const message = error?.response?.data?.message
  if (typeof message === 'string' && message) return message
  const msg = error?.message
  if (typeof msg === 'string' && msg && msg !== 'Network Error') return msg
  return fallback
}

export default getErrorMessage
