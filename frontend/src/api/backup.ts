/**
 * 备份 API
 */
import { get, post, del, put } from '@/api/request'

export interface BackupItem {
  filename: string
  size: number
  file_size: number
  created_at: string
  id?: string | number
}

export interface BackupStats {
  total_backups: number
  total_size: number
  auto_backup_enabled: boolean
  totalBackups?: number
  lastBackup?: string
  totalSize?: number
}

const BASE = '/system/backup'

export interface CreateBackupPayload {
  description?: string
  include_uploads?: boolean
  password?: string
}

export async function getBackupList(params?: { page?: number; page_size?: number }) {
  return get(BASE, params)
}

export async function createBackup(data: CreateBackupPayload) {
  return post(BASE, data)
}

/**
 * 恢复备份。
 *
 * @param filename 备份文件名
 * @param password 加密备份的解密密码
 * @param allowKeyMismatch 备份的 PII 密钥指纹与本机不一致时是否强制恢复。
 *   默认 false：后端返回 409 并提示"敏感字段将不可读"；只有用户在界面上
 *   显式确认（危险勾选 + 二次确认）后才允许置 true。**严禁默认 true。**
 */
export async function restoreBackup(
  filename: string,
  password?: string | null,
  allowKeyMismatch = false
) {
  return post(`${BASE}/restore`, {
    filename,
    password,
    allow_key_mismatch: allowKeyMismatch,
  })
}

/**
 * 上传任意备份包并恢复（支持加密备份，password 为可选解密密码）。
 *
 * `allowKeyMismatch` 语义同 restoreBackup：跨密钥备份默认 409，
 * 仅用户显式确认后以 FormData 字段 `allow_key_mismatch=true` 强制恢复。
 */
export async function uploadRestoreBackup(file: File, password?: string, allowKeyMismatch = false) {
  const formData = new FormData()
  formData.append('file', file)
  if (password) formData.append('password', password)
  formData.append('allow_key_mismatch', allowKeyMismatch ? 'true' : 'false')
  return post(`${BASE}/upload-restore`, formData)
}

/**
 * 删除备份文件。
 *
 * 文件名来自后端列表，但仍属"外部输入"：未编码直接拼进路径时，
 * 含 / ? # 或被 ../ 构造的名字会被解析到别的路由（路径穿越/越权删除）。
 * 这里 fail-closed：先校验形态，再逐段编码（encodeURIComponent 不编码 . - _ ~ ! * ' ( )，
 * 正常备份名 `backup-2024-01-01.zip` 编码后不变，不影响既有调用）。
 */
export async function deleteBackup(filename: string) {
  if (typeof filename !== 'string' || !filename.trim()) {
    throw new Error('备份文件名不能为空')
  }
  if (filename.includes('/') || filename.includes('\\') || filename.includes('..')) {
    throw new Error('备份文件名非法：不允许路径分隔符')
  }
  return del(`${BASE}/${encodeURIComponent(filename)}`)
}

export async function getBackupStats(): Promise<BackupStats> {
  const res = await get(`${BASE}/stats`)
  return res
}

export interface BackupDirInfo {
  path: string
  type: string
  available: boolean
}

export interface BackupDirsResponse {
  dirs: BackupDirInfo[]
  current: string
  default_dir: string
}

/** 检测可用备份目标目录（U盘/移动硬盘） */
export async function getBackupDirs(): Promise<BackupDirsResponse> {
  return get(`${BASE}/dirs`)
}

/** 设置备份目标目录 */
export async function setBackupTarget(targetDir: string): Promise<void> {
  return put(`${BASE}/target`, { target_dir: targetDir })
}
