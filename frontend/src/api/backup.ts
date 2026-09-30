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

export async function restoreBackup(filename: string, password?: string) {
  return post(`${BASE}/restore`, { filename, password })
}

/** 上传任意备份包并恢复（支持加密备份，password 为可选解密密码） */
export async function uploadRestoreBackup(file: File, password?: string) {
  const formData = new FormData()
  formData.append('file', file)
  if (password) formData.append('password', password)
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
