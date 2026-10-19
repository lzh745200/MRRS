/**
 * 单位授权矩阵 API（R33）
 *
 * 授权以**单位**为粒度：上级把「模块 × 级别」写成授权包下发，下级导入后只读执行。
 * 级别语义：`edit` 可写 / `view` 只读 / `none` 不可见。
 *
 * 全部端点仅管理员可用；导入是下级唯一的写入口（导入后本机不提供编辑入口）。
 */
import request, { downloadBlob, get, parseContentDisposition, post, put } from '@/api/request'

/** 模块授权级别 */
export type GrantLevel = 'edit' | 'view' | 'none'

/** 单位授权矩阵 + 版本元信息 */
export interface OrgGrantMatrix {
  organization_id: number
  org_code: string | null
  grant_version: number
  grant_source: string | null
  grant_applied_at: string | null
  signed: boolean
  grants: Record<string, GrantLevel>
}

/** 设置矩阵后的返回 */
export interface GrantSetResult {
  organization_id: number
  grant_version: number
  modules: number
}

/** 导入授权包后的返回 */
export interface GrantImportResult {
  org_code: string
  version: number
  modules: number
  signed: boolean
}

const BASE = '/org-grants'

/** 查询某单位的授权矩阵与元信息 */
export async function getOrgGrants(orgId: number): Promise<OrgGrantMatrix> {
  const res = await get<any>(`${BASE}/${orgId}`)
  return res?.data ?? res
}

/** 直接设置矩阵（替换语义，版本号自增） */
export async function setOrgGrants(
  orgId: number,
  grants: Record<string, GrantLevel>
): Promise<GrantSetResult> {
  const res = await put<any>(`${BASE}/${orgId}`, { grants })
  return res?.data ?? res
}

/** 导入授权包文件（下级） */
export async function importGrantPackage(file: File): Promise<GrantImportResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await post<any>(`${BASE}/import`, form)
  return res?.data ?? res
}

/**
 * 生成并下载授权包（上级）。
 * 后端以附件形式返回 JSON，这里用 blob 接收并按响应头文件名落盘。
 * 返回实际使用的文件名，便于页面提示。
 */
export async function exportGrantPackage(
  orgId: number,
  fallbackName = `grant-${orgId}.json`
): Promise<string> {
  const res = await request.post(`${BASE}/${orgId}/export`, null, { responseType: 'blob' })
  const filename = parseContentDisposition(
    res.headers as unknown as Record<string, string>,
    fallbackName
  )
  downloadBlob(res.data as Blob, filename)
  return filename
}
