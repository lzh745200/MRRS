/**
 * 数据分级存储 API
 * 提供数据分级查询、归档管理和存储统计功能
 */

import { get, post, del } from '@/api/request'

// ==================== 类型定义 ====================

/** 存储统计 */
export interface StorageStats {
  [key: string]: any
}

/** 存储摘要 */
export interface StorageSummary {
  [key: string]: any
}

/** 数据分级信息 */
export interface TierInfo {
  tier: string
  hot_threshold_days?: number
  warm_threshold_days?: number
  storage_path?: string
}

/** 归档结果 */
export interface ArchiveResult {
  archived_count: number
  message: string
  model: string
  before_date: string
}

/** 归档文件 */
export interface ArchiveFile {
  name: string
  size: number
  size_mb: number
  modified: string
}

/** 归档文件列表 */
export interface ArchiveList {
  cold_archives: ArchiveFile[]
  warm_archives: ArchiveFile[]
}

/** 恢复结果 */
export interface RestoreResult {
  restored_count: number
  message: string
  archive_file: string
}

/** 清理结果 */
export interface CleanupResult {
  deleted_count: number
  message: string
  max_age_days: number
}

/** 记录分级信息 */
export interface RecordTierInfo {
  record_date: string
  tier: string
  age_days: number
}

// ==================== API 函数 ====================

/** 获取存储统计信息 */
export async function getStorageStats(): Promise<StorageStats> {
  return get<StorageStats>('/data-tier/stats')
}

/** 获取存储摘要报告 */
export async function getStorageSummary(): Promise<StorageSummary> {
  return get<StorageSummary>('/data-tier/summary')
}

/** 获取指定分级信息 */
export async function getTierInfo(tier: string): Promise<TierInfo> {
  return get<TierInfo>(`/data-tier/tier/${tier}`)
}

/** 归档指定模型的旧数据 */
export async function archiveModel(
  modelName: string,
  beforeDays?: number,
  batchSize?: number
): Promise<ArchiveResult> {
  return post(
    `/data-tier/archive/${modelName}?before_days=${beforeDays || 365}&batch_size=${batchSize || 1000}`
  )
}

/** 列出归档文件 */
/** 归档列表：后端可能只返回某一层（cold/warm 各自可选） */
export async function listArchives(tier?: string): Promise<Partial<ArchiveList>> {
  return get('/data-tier/archives', tier ? { tier } : undefined)
}

/** 从归档恢复数据 */
export async function restoreFromArchive(
  archiveFile: string,
  modelName: string
): Promise<RestoreResult> {
  return post(
    `/data-tier/restore?archive_file=${encodeURIComponent(archiveFile)}&model_name=${encodeURIComponent(modelName)}`
  )
}

/** 清理过期归档文件 */
export async function cleanupArchives(maxAgeDays?: number): Promise<CleanupResult> {
  return del(`/data-tier/cleanup?max_age_days=${maxAgeDays || 365}`)
}

/** 根据日期确定数据分级 */
export async function getTierForRecord(date: string): Promise<RecordTierInfo> {
  return get(`/data-tier/tier-for-record/${encodeURIComponent(date)}`)
}

// ==================== 分组导出 ====================

export const dataTierApi = {
  getStats: getStorageStats,
  getSummary: getStorageSummary,
  getTier: getTierInfo,
  archiveModel,
  listArchives,
  restore: restoreFromArchive,
  cleanup: cleanupArchives,
  getTierForRecord,
}
