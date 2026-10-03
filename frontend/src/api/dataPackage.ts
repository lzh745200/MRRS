/**
 * Data Package API
 * 数据包管理API - 导入导出功能
 */
import { get, post, apiRequest } from '@/api/request'
import type {
  DataPackage,
  DataPackageExportRequest,
  DataPackageExportResult,
  DataPackageImportResult,
  DataPackageValidationResult,
  DataPackagePreviewData,
  DataPackageConfirmRequest,
  DataPackageConfirmResult,
  DataPackageListResponse,
  ImportExportHistory,
} from '@/types/organization'

const BASE_URL = '/data-packages'

/**
 * 获取数据包列表
 */
export async function getDataPackages(params?: {
  page?: number
  page_size?: number
  org_id?: number
  status?: string
}): Promise<DataPackageListResponse> {
  const response = await get(BASE_URL, params)
  return response
}

/**
 * 获取数据包详情
 */
export async function getDataPackage(id: number): Promise<DataPackage> {
  const response = await get(`${BASE_URL}/${id}`)
  return response
}

/**
 * 导出数据包
 */
export async function exportDataPackage(
  data: DataPackageExportRequest
): Promise<DataPackageExportResult> {
  const response = await post(`${BASE_URL}/export`, data)
  return response
}

/**
 * 导入数据包
 */
export async function importDataPackage(
  file: File,
  orgId?: number
): Promise<DataPackageImportResult> {
  const formData = new FormData()
  formData.append('file', file)

  const params: Record<string, unknown> = {}
  if (orgId) {
    params.org_id = orgId
  }

  const response = await post(`${BASE_URL}/import`, formData, {
    params,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response
}

/**
 * 验证数据包
 */
export async function validateDataPackage(id: number): Promise<DataPackageValidationResult> {
  const response = await post(`${BASE_URL}/${id}/validate`)
  return response
}

/**
 * 预览数据包内容
 */
export async function previewDataPackage(id: number): Promise<DataPackagePreviewData[]> {
  const response = await get(`${BASE_URL}/${id}/preview`)
  return response
}

/**
 * 确认导入数据
 */
export async function confirmImport(
  id: number,
  data?: DataPackageConfirmRequest
): Promise<DataPackageConfirmResult> {
  const response = await post(`${BASE_URL}/${id}/confirm`, data || {})
  return response
}

/**
 * 下载数据包
 */
export async function downloadDataPackage(id: number): Promise<Blob> {
  return apiRequest<Blob>({
    method: 'GET',
    url: `${BASE_URL}/${id}/download`,
    responseType: 'blob',
  })
}

/**
 * 删除数据包
 */
export async function deleteDataPackage(id: number, reason?: string): Promise<{ message: string }> {
  return apiRequest({
    method: 'DELETE',
    url: `${BASE_URL}/${id}`,
    params: reason ? { reason } : undefined,
  })
}

/**
 * 获取数据包操作历史
 */
export async function getPackageHistory(
  id: number,
  params?: {
    page?: number
    page_size?: number
  }
): Promise<{
  package_id: number
  items: ImportExportHistory[]
}> {
  const response = await get(`${BASE_URL}/${id}/history`, params)
  return response
}

/**
 * 一键报告
 */
export async function oneClickReport(data: Record<string, any>): Promise<any> {
  const response = await post(`${BASE_URL}/one-click-report`, data)
  return response
}

/**
 * 预览导出数据
 */
export async function previewExport(data: Record<string, any>): Promise<any> {
  const response = await post(`${BASE_URL}/preview`, data)
  return response
}

/**
 * 获取下载URL
 */
export function getDownloadUrl(id: number): string {
  // 与 request.ts / projects.ts 保持同一前缀约定：VITE_API_BASE_URL 缺省为 '/api/v1'。
  // 旧实现写死 `'' + /api/v1`，一旦 VITE_API_BASE_URL 配了含 /api/v1 的值就会
  // 拼出 /api/v1/api/v1/... 导致下载 404。
  return `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}${BASE_URL}/${id}/download`
}
