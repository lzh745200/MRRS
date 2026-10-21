/**
 * PII 字段加密密钥管理 API
 *
 * 多机离线同步时 PII 列（身份证/手机号等）以**密文**出包，要求各机使用同一把
 * 密钥；默认安装下每台机器各自随机生成，同步后对端密文永久不可解。
 * 本模块提供状态查询、密钥导出（搬机）与导入（统一解钥），均限管理员。
 */

import { get, post } from '@/api/request'

/** 密钥配置来源 */
export type PiiKeySource = 'env' | 'runtime'

/** 本机 PII 密钥状态 */
export interface PiiKeyStatus {
  /** 密钥指纹（SHA-256 前 16 位）；空串表示密钥不可用 */
  fingerprint: string
  /** env=环境变量显式配置（导入不生效）；runtime=运行时密钥存储 */
  source: PiiKeySource
  available: boolean
}

/** 导出的密钥（含本体，仅管理员可取） */
export interface PiiKeyExportResult extends PiiKeyStatus {
  key: string
}

/** 查询本机 PII 密钥状态（不含密钥本体） */
export async function getPiiKeyStatus(): Promise<PiiKeyStatus> {
  return get<PiiKeyStatus>('/system/pii-key')
}

/** 导出本机 PII 密钥（用于搬到其它机器统一解钥） */
export async function exportPiiKey(): Promise<PiiKeyExportResult> {
  return get<PiiKeyExportResult>('/system/pii-key/export')
}

/** 导入源机 PII 密钥（成功后立即生效） */
export async function importPiiKey(key: string): Promise<PiiKeyStatus> {
  return post<PiiKeyStatus>('/system/pii-key/import', { key })
}

export const piiKeyApi = {
  status: getPiiKeyStatus,
  exportKey: exportPiiKey,
  importKey: importPiiKey,
}
