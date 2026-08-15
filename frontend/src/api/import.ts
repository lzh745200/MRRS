/**
 * 数据导入API模块
 *
 * 提供数据导入相关的API调用，包括：
 * - 下载导入模板
 * - 导入帮扶村数据
 * - 查询导入历史
 */

import request, { post, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

// ==================== 类型定义 ====================

/** 导入模式（后端 /import/entities 支持 incremental / full） */
export type ImportMode = 'incremental' | 'full'

/** 导入结果 */
export interface ImportResult {
  success: boolean
  total_rows: number
  success_rows: number
  failed_rows: number
  skipped_rows: number
  errors?: ImportError[]
}

/** 导入错误 */
export interface ImportError {
  row_number: number
  field_name: string
  message: string
}

/** 导入历史记录 */
export interface ImportHistory {
  id: number
  file_name: string
  status: string
  total_rows: number
  success_rows: number
  failed_rows: number
  skipped_rows: number
  created_at: string
  updated_at: string
}

/** 导入历史列表响应 */
interface ImportHistoryResponse {
  items: ImportHistory[]
  total: number
}

/** 预览行（后端 /import/preview 返回） */
export interface ImportPreviewRow {
  row_number: number
  data: Record<string, any>
  has_error: boolean
  errors: ImportError[]
  is_duplicate_in_db: boolean
}

/** 导入预览响应（后端 /import/preview 返回，裸格式非信封） */
export interface ImportPreviewResponse {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  duplicate_in_db_rows: number
  rows: ImportPreviewRow[]
  warnings: string[]
}

// ==================== API函数 ====================

/**
 * 下载导入模板
 *
 * 后端返回 RFC 5987 格式的 Content-Disposition（filename*=UTF-8''xxx），
 * 浏览器会把 `UTF-8` 当文件名，因此前端必须显式解析。
 *
 * @param type 模板类型（supported_village/project/fund/school/policy）
 * @returns Blob 文件数据
 */
export async function downloadImportTemplate(type: string): Promise<Blob> {
  return apiRequest<Blob>({
    method: 'GET',
    url: `/import/template`,
    params: { entity_type: type },
    responseType: 'blob',
  })
}

/**
 * 下载导入模板并触发浏览器保存（自动解析正确文件名）。
 *
 * @param type 模板类型
 * @param fallbackName 解析失败时的兜底文件名（不含扩展名）
 */
export async function downloadImportTemplateAndSave(
  type: string,
  fallbackName = '导入模板'
): Promise<void> {
  await downloadBlobAsFile(
    () =>
      request.get(`/import/template`, {
        params: { entity_type: type },
        responseType: 'blob',
      }),
    { fallbackFileName: `${fallbackName}.xlsx` }
  )
}

/**
 * 导入实体数据（通用接口，支持 village/project/fund/school）
 * @param file 上传文件
 * @param entityType 实体类型
 * @param mode 导入模式
 * @returns 导入结果
 */
export async function importEntities(
  file: File,
  entityType: string = 'supported_village',
  mode: ImportMode = 'incremental'
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)

  // 后端 /import/entities 通过 Query 参数接收 entity_type/mode（非 FormData 字段），
  // 放入 FormData 会导致类型选择器与覆盖模式失效
  const response = await post('/import/entities', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { entity_type: entityType, mode },
    timeout: 120000,
  })
  return response
}

/** @deprecated 使用 importEntities 替代 */
export const importVillages = (file: File, mode?: ImportMode) =>
  importEntities(file, 'supported_village', mode)

/** 预览导入数据 */
export async function previewImportData(
  file: File,
  entityType: string
): Promise<ImportPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)

  // 后端 /import/preview 通过 Query 参数接收 entity_type
  const response = await post('/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { entity_type: entityType },
    timeout: 60000,
  })
  return response
}

/**
 * 获取导入历史
 * @param page 页码
 * @param pageSize 每页数量
 * @returns 导入历史列表
 */
export async function getImportHistory(
  page: number = 1,
  pageSize: number = 10
): Promise<ImportHistoryResponse> {
  const response = await apiRequest({
    method: 'GET',
    url: '/import/history',
    params: { page, page_size: pageSize },
  })
  return response
}

/**
 * 验证导入数据（不执行导入）
 * @param data 验证参数
 * @returns 验证结果
 */
export async function validateImport(data: { file?: File; entity_type?: string }): Promise<{
  valid: boolean
  errors?: Array<{ row: number; field: string; message: string }>
  total_rows?: number
}> {
  if (data.file) {
    const formData = new FormData()
    formData.append('file', data.file)
    if (data.entity_type) {
      formData.append('entity_type', data.entity_type)
    }
    const response = await post('/import/validate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    return response
  }
  const response = await post('/import/validate', data)
  return response
}

/**
 * 格式化导入状态
 * @param status 状态值
 * @returns 格式化后的状态信息
 */
export function formatImportStatus(status: string): {
  text: string
  type: string
} {
  const statusMap: Record<string, { text: string; type: string }> = {
    pending: { text: '等待中', type: 'info' },
    processing: { text: '处理中', type: 'warning' },
    completed: { text: '已完成', type: 'success' },
    failed: { text: '失败', type: 'danger' },
  }
  return statusMap[status] || { text: status, type: 'info' }
}
