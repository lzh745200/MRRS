/**
 * 密钥管理 API
 * 提供密钥轮换、版本管理和安全存储功能
 */

import { get, post } from '@/api/request'

// ==================== 类型定义 ====================

/** 密钥版本 */
export interface KeyVersion {
  version_id: string
  created_at?: number
  is_active?: boolean
  key_type?: string
  revoked_at?: number
  expires_at?: number
}

/** 密钥版本列表 */
export interface KeyVersionList {
  versions: KeyVersion[]
  count: number
}

/** 密钥状态 */
export interface SecretsStatus {
  total_versions: number
  active_versions: number
  latest_version?: KeyVersion
  requires_rotation: boolean
}

// ==================== 工具函数 ====================

/** 构建查询字符串 */
function buildQuery(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
  return parts.length > 0 ? `?${parts.join('&')}` : ''
}

// ==================== API 函数 ====================

/** 列出所有密钥版本 */
export async function getKeyVersions(): Promise<KeyVersionList> {
  return get<KeyVersionList>('/secrets/versions')
}

/** 轮换密钥 */
export async function rotateSecrets(
  versionId?: string
): Promise<{ message: string; new_version: string }> {
  const qs = buildQuery({ version_id: versionId })
  return post(`/secrets/rotate${qs}`)
}

/** 创建新密钥 */
export async function createSecret(params?: {
  key_type?: string
  expires_days?: number
}): Promise<{ message: string; version_id: string }> {
  const qs = buildQuery({
    key_type: params?.key_type,
    expires_days: params?.expires_days,
  })
  return post(`/secrets/create${qs}`)
}

/**
 * 撤销密钥。
 *
 * versionId 作为**路径段**必须编码并对空值 fail-fast：未编码时含 / ? # 的
 * 值会改写请求路径（打到别的密钥版本或别的路由）。version_id 允许数字形态
 * 传入（后端返回的是字符串，历史调用方可能透传 number）。
 */
export async function revokeSecret(
  versionId: string | number
): Promise<{ message: string; version_id: string }> {
  const id =
    typeof versionId === 'number' && Number.isFinite(versionId) ? String(versionId) : versionId
  if (typeof id !== 'string' || !id.trim()) {
    throw new Error('密钥版本号不能为空')
  }
  return post(`/secrets/revoke/${encodeURIComponent(id.trim())}`)
}

/** 清理过期密钥 */
export async function cleanupSecrets(
  keepDays?: number
): Promise<{ message: string; deleted_count: number }> {
  const qs = buildQuery({ keep_days: keepDays || 90 })
  return post(`/secrets/cleanup${qs}`)
}

/** 获取密钥状态 */
export async function getSecretsStatus(): Promise<SecretsStatus> {
  return get<SecretsStatus>('/secrets/status')
}

// ==================== 分组导出 ====================

export const secretsApi = {
  getVersions: getKeyVersions,
  rotateSecrets,
  createSecret,
  revokeSecret,
  cleanup: cleanupSecrets,
  getStatus: getSecretsStatus,
}
