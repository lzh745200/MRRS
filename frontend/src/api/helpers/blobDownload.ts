/**
 * Blob 下载统一工具
 *
 * 解决项目中 Blob 下载的两大痛点：
 * 1. `apiRequest()` 已返回 `res.data`（即 Blob 本身），但很多代码误用 `response.data` 导致 undefined
 * 2. 需要响应头 `Content-Disposition` 解析文件名时，必须使用原始 axios 实例而非 `apiRequest`
 *
 * 使用方式：
 *   // 纯 Blob 下载（不需要文件名解析）
 *   await downloadBlobAsFile(() => apiRequest<Blob>({ url: '/export', responseType: 'blob' }))
 *
 *   // 需要从响应头解析文件名
 *   await downloadBlobAsFile(
 *     () => request.get('/export', { responseType: 'blob' }),
 *     { fallbackFileName: '导出数据.xlsx' }
 *   )
 */

import type { AxiosResponse } from 'axios'
import { parseContentDisposition, downloadBlob as triggerDownload } from '@/api/request'

// ─── 类型定义 ───

/** 下载选项 */
export interface DownloadOptions {
  /** 解析失败时的兜底文件名（含扩展名） */
  fallbackFileName?: string
  /** 开始下载前回调 */
  onStart?: () => void
  /** 下载完成后回调（无论成功失败） */
  onEnd?: () => void
  /** 下载出错回调 */
  onError?: (err: unknown) => void
}

// ─── 核心函数 ───

/**
 * 从 Content-Disposition 头字符串中解析文件名。
 *
 * 支持 RFC 5987 格式（`filename*=UTF-8''%E5%B8%AE...`）
 * 和 ASCII 格式（`filename="xxx"`）。
 *
 * @param contentDisposition Content-Disposition 头的原始值
 * @returns 解析出的文件名，失败返回 null
 */
export function parseFileName(contentDisposition: string | undefined | null): string | null {
  if (!contentDisposition) return null
  // 解析逻辑统一由 @/api/request 的 parseContentDisposition 提供（原实现在此处
  // 逐字复制了一份同构代码，两处规则一旦漂移就会出现"下载文件名不一致"）。
  // fallback 传空串以保留本函数的 null 语义（调用方据此回退 fallbackFileName）。
  const headers = { 'content-disposition': contentDisposition }
  return parseContentDisposition(headers, '') || null
}

/**
 * 统一的 Blob 下载函数。
 *
 * 封装了"发起请求 → 解析文件名 → 触发浏览器下载 → 清理内存"完整流程。
 *
 * @param requestFn 返回 AxiosResponse<Blob> 或 Blob 的请求函数
 *   - 需要文件名解析时：传入返回 AxiosResponse 的函数（如 `() => request.get(...)`）
 *   - 不需要文件名解析时：传入返回 Blob 的函数（如 `() => apiRequest<Blob>(...)`）
 * @param options 下载选项
 *
 * @example
 *   // 方式1：需要从响应头解析文件名（推荐）
 *   await downloadBlobAsFile(
 *     () => request.get('/funds/export', { responseType: 'blob' }),
 *     { fallbackFileName: '经费列表.csv' }
 *   )
 *
 *   // 方式2：纯 Blob（不需要文件名解析）
 *   await downloadBlobAsFile(
 *     () => apiRequest<Blob>({ method: 'GET', url: '/data/download', responseType: 'blob' }),
 *     { fallbackFileName: '数据包.zip' }
 *   )
 */
export async function downloadBlobAsFile(
  requestFn: () => Promise<AxiosResponse<Blob> | Blob>,
  options: DownloadOptions = {}
): Promise<void> {
  const { fallbackFileName = 'download', onStart, onEnd, onError } = options

  onStart?.()

  try {
    const result = await requestFn()

    let blob: Blob
    let fileName: string = fallbackFileName

    if (result instanceof Blob) {
      // 纯 Blob 返回（来自 apiRequest）
      blob = result
    } else if (result && typeof result === 'object' && 'data' in result) {
      // AxiosResponse<Blob> — 必须先证实载荷确实是 Blob：
      // 204/空响应在 responseType:'blob' 下 data 可能是 '' / undefined，
      // 直接当 Blob 用会在 URL.createObjectURL 抛 TypeError（用户看到无提示的失败）。
      const payload: unknown = result.data
      if (!(payload instanceof Blob)) {
        throw new Error('下载失败：响应内容不是文件')
      }
      // 服务端错误页（HTML）被包成 Blob 时同样不是可下载文件
      if ((payload.type || '').toLowerCase().includes('text/html')) {
        throw new Error('下载失败：服务端返回了错误页面')
      }
      blob = payload
      // 尝试从响应头解析文件名
      const headers = result.headers || {}
      const cd =
        headers['content-disposition'] ||
        headers['Content-Disposition'] ||
        headers['CONTENT-DISPOSITION']
      const parsed = parseFileName(cd)
      if (parsed) fileName = parsed
    } else {
      throw new Error('downloadBlobAsFile: 请求返回值既不是 Blob 也不是 AxiosResponse')
    }

    // 触发浏览器下载
    triggerDownload(blob, fileName)
  } catch (err) {
    onError?.(err)
    throw err
  } finally {
    onEnd?.()
  }
}

// ─── 便捷方法 ───

/**
 * 从 AxiosResponse 中提取文件名（便捷方法）。
 *
 * @param response Axios 响应对象
 * @param fallback 兜底文件名
 * @returns 解析出的文件名
 */
export function getFileNameFromResponse(response: AxiosResponse, fallback = 'download'): string {
  const headers = response.headers || {}
  return parseContentDisposition(headers as Record<string, string>, fallback)
}
