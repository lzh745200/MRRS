/**
 * 系统自检 API（P3）。
 *
 * GET /api/v1/system/self-check —— 仅管理员；只返回配置一致性结论，不含 PII。
 * 与 diagnostics / business-health 等同属 system 包聚合路由（/api/v1/system/*）。
 */
import { get } from '@/api/request'

export type SelfCheckLevel = 'ok' | 'warn' | 'error'

export interface SelfCheckItem {
  name: string
  level: SelfCheckLevel
  detail: string
  count: number
}

export interface SelfCheckSummary {
  check_count: number
  error_count: number
  warn_count: number
  issue_count: number
}

export interface SelfCheckReport {
  generated_at: string
  status: SelfCheckLevel
  summary: SelfCheckSummary
  checks: SelfCheckItem[]
}

export async function getSelfCheck(): Promise<SelfCheckReport> {
  const res = await get<any>('/system/self-check')
  return res?.data ?? res
}
