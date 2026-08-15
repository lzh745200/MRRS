/**
 * 错误报告 API
 * 提供系统错误收集、上报、查询和统计功能
 */

import { get, post, put } from '@/api/request'

// ==================== 类型定义 ====================

/** 错误报告（后端 to_dict 返回 camelCase 键名） */
export interface ErrorReport {
  id: number
  source: string
  errorType: string
  message: string
  stackTrace?: string
  context?: Record<string, any>
  severity: 'info' | 'warning' | 'error' | 'critical'
  status: string
  reporter?: string
  createdAt: string
  updatedAt?: string
  resolvedAt?: string
  resolutionNote?: string
}

/** 错误报告列表响应 */
export interface ErrorReportListResponse {
  items: ErrorReport[]
  total: number
  page: number
  page_size: number
}

/** 错误统计 */
export interface ErrorStats {
  total: number
  open: number
  critical: number
  by_source: Record<string, number>
  by_severity: Record<string, number>
}

// ==================== API 函数 ====================

/** 上报系统错误 */
export async function submitErrorReport(data: {
  source: string
  error_type: string
  message: string
  stack_trace?: string
  context?: Record<string, any>
  severity?: string
}): Promise<{
  success: boolean
  message: string
  data: { report_id: number }
}> {
  return post('/system/error-reports', data)
}

/** 获取错误报告列表 */
export async function listErrorReports(params?: {
  source?: string
  severity?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<{ success: boolean; data: ErrorReportListResponse }> {
  return get('/system/error-reports', params)
}

/** 获取错误统计 */
export async function getErrorStats(): Promise<{
  success: boolean
  data: ErrorStats
}> {
  return get('/system/error-reports/stats')
}

/** 获取错误报告详情 */
export async function getErrorReport(
  reportId: number
): Promise<{ success: boolean; data: ErrorReport }> {
  return get(`/system/error-reports/${reportId}`)
}

/** 更新错误报告状态 */
export async function updateErrorReport(
  reportId: number,
  data: { status: string; resolution_note?: string }
): Promise<{ success: boolean; message: string }> {
  return put(`/system/error-reports/${reportId}`, data)
}

/** 简化版异常上报 */
export async function reportException(
  source: string,
  message: string
): Promise<{
  success: boolean
  message: string
  data: { report_id: number }
}> {
  return post(
    `/system/error-reports/report-exception?source=${encodeURIComponent(source)}&message=${encodeURIComponent(message)}`
  )
}

// ==================== 分组导出 ====================

export const errorReportApi = {
  submitReport: submitErrorReport,
  listReports: listErrorReports,
  getStats: getErrorStats,
  getReport: getErrorReport,
  updateReport: updateErrorReport,
  reportException,
}
