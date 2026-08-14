/**
 * 经费统计 API
 * Requirements: 21.1, 21.2, 21.3
 */
import { get } from '@/api/request'

// 经费类型定义
export const FUND_TYPES = {
  project: '项目经费',
  operation: '运营经费',
  education: '教育帮扶',
  infrastructure: '基础设施',
  emergency: '应急经费',
  other: '其他',
} as const

export const FUND_SOURCES = {
  military: '专项',
  government: '政府',
  donation: '捐赠',
  enterprise: '企业',
  other: '其他',
} as const

export const FUND_STATUSES = {
  pending: '待审批',
  planned: '已计划',
  approved: '已批准',
  allocated: '已拨付',
  in_use: '使用中',
  completed: '已完成',
  audited: '已审计',
  rejected: '已驳回',
} as const

export type FundType = keyof typeof FUND_TYPES

// 经费统计数据接口
export interface FundStatistics {
  fund_type: string
  fund_type_label: string
  military_investment: number
  local_investment: number
  planned_investment: number
  total_investment: number
  utilization_rate: number
}

// 年度经费汇总接口
export interface YearlyFundSummary {
  year: number
  total_military: number
  total_local: number
  total_planned: number
  total_actual: number
  utilization_rate: number
  by_type: Record<string, FundStatistics>
}

// 利用率统计接口
export interface UtilizationRateData {
  overall_utilization_rate: number
  total_actual_investment: number
  total_planned_investment: number
  by_type: Record<
    string,
    {
      utilization_rate: number
      actual: number
      planned: number
    }
  >
}

// 经费汇总接口
export interface FundSummaryData {
  period: string
  grand_total: {
    military_investment: number
    local_investment: number
    planned_investment: number
    actual_investment: number
    utilization_rate: number
  }
  by_type: Record<
    string,
    {
      label: string
      total: number
      planned: number
      utilization_rate: number
    }
  >
  yearly_data: YearlyFundSummary[]
}

// 查询参数接口
export interface FundQueryParams {
  year?: number
  village_id?: number
  department?: string
  year_start?: number
  year_end?: number
}

/**
 * 按类型获取经费统计
 */
export function getFundStatisticsByType(params?: FundQueryParams) {
  return get<{
    success: boolean
    data: Record<string, FundStatistics>
    fund_types: Record<string, string>
  }>('/funds/supported-village/statistics/by-type', params)
}

/**
 * 获取年度经费对比数据
 */
export function getYearlyFundComparison(params?: FundQueryParams) {
  return get<{
    success: boolean
    message?: string
    data: YearlyFundSummary[]
  }>('/funds/supported-village/statistics/yearly-comparison', params)
}

/**
 * 获取经费利用率统计
 */
export function getUtilizationRate(params?: FundQueryParams) {
  return get<{
    success: boolean
    data: UtilizationRateData
  }>('/funds/supported-village/statistics/utilization-rate', params)
}

/**
 * 获取经费汇总统计
 */
export function getFundSummary(params?: FundQueryParams) {
  return get<{
    success: boolean
    data: FundSummaryData
  }>('/funds/supported-village/statistics/summary', params)
}
