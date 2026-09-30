/**
 * 导出 API
 *
 * Blob 下载类函数统一使用 downloadBlobAsFile 工具，
 * 消除 apiRequest 返回值误用导致的 bug。
 */
import request, { get } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

export interface ExportTask {
  id: string
  status: string
  filename: string
  file_size?: number
  created_at: string
  completed_at?: string
}

export interface ExportFilterParams {
  village_ids?: number[]
  date_from?: string
  date_to?: string
  type?: string
  format?: string
  department?: string
  support_unit?: string
  region_scope?: string
  is_revitalization_tier?: boolean
}

const EXPORT_BASE = '/export'
const ASYNC_EXPORT_BASE = '/async-export'

// ─── 非 Blob 端点 ───

export async function getExportStatus(taskId: string) {
  const res = await get(`${ASYNC_EXPORT_BASE}/status/${taskId}`)
  return res
}

/**
 * 异步导出任务历史列表。
 *
 * 后端 async_export 只有 /tasks 一个列表端点（无 /history），故此处是**唯一**实现；
 * 同名同 URL 的 getExportTasks 死代码已删除（零生产调用方，语义完全重复）。
 */
export async function getExportHistory(params?: { page?: number; page_size?: number }) {
  const res = await get(`${ASYNC_EXPORT_BASE}/tasks`, params)
  return res
}

// ─── Blob 下载端点（使用统一工具函数）──

/**
 * 导出帮扶村数据 — 触发浏览器下载
 */
export async function exportVillages(params: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/villages`, { params, responseType: 'blob' }),
    { fallbackFileName: '帮扶村数据.xlsx' }
  )
}

/**
 * 下载异步导出文件 — 触发浏览器下载
 */
export async function downloadExportFile(taskId: string): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${ASYNC_EXPORT_BASE}/download/${taskId}`, { responseType: 'blob' }),
    { fallbackFileName: `导出文件_${taskId}.xlsx` }
  )
}

/**
 * 导出 Word 报告 — 触发浏览器下载
 */
export async function exportReportWord(reportType: string, year?: number): Promise<void> {
  await downloadBlobAsFile(
    () =>
      request.get(`${EXPORT_BASE}/report-word`, {
        params: { report_type: reportType, ...(year ? { year } : {}) },
        responseType: 'blob',
      }),
    { fallbackFileName: `报告_${reportType}.docx` }
  )
}

/**
 * 导出 PDF 报告 — 触发浏览器下载
 */
export async function exportReportPdf(reportType: string, year?: number): Promise<void> {
  await downloadBlobAsFile(
    () =>
      request.get(`${EXPORT_BASE}/report-pdf`, {
        params: { report_type: reportType, ...(year ? { year } : {}) },
        responseType: 'blob',
      }),
    { fallbackFileName: `报告_${reportType}.pdf` }
  )
}

/**
 * 导出用户数据 — 触发浏览器下载
 */
export async function exportUsers(params?: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/users`, { params, responseType: 'blob' }),
    { fallbackFileName: '用户数据.xlsx' }
  )
}

/**
 * 导出学校数据 — 触发浏览器下载
 */
export async function exportSchools(params?: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/schools`, { params, responseType: 'blob' }),
    { fallbackFileName: '学校数据.xlsx' }
  )
}

/**
 * 导出项目数据 — 触发浏览器下载
 */
export async function exportProjects(params?: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/projects`, { params, responseType: 'blob' }),
    { fallbackFileName: '项目数据.xlsx' }
  )
}

/**
 * 导出经费数据 — 触发浏览器下载
 */
export async function exportFunds(params?: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/funds`, { params, responseType: 'blob' }),
    { fallbackFileName: '经费数据.xlsx' }
  )
}

/**
 * 导出综合数据 — 触发浏览器下载
 */
export async function exportComprehensive(params?: ExportFilterParams): Promise<void> {
  await downloadBlobAsFile(
    () => request.get(`${EXPORT_BASE}/comprehensive`, { params, responseType: 'blob' }),
    { fallbackFileName: '综合数据.xlsx' }
  )
}

// ─── 工具函数（保留兼容导出）──

export function formatExportStatus(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`
}

/**
 * @deprecated 使用 downloadBlobAsFile 替代。保留以兼容旧调用方。
 */
export function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
