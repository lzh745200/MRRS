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

// 经费类型统计（单一类型条目）
// 2026-10-16 按真实契约订正（backend/app/api/v1/funds.py `fund_stats_by_type`）：
// 后端只返回 fund_type / fund_type_label / total_investment / count 四个字段，
// 历史上的 military_investment/local_investment/planned_investment/utilization_rate
// 均为前端虚构，读取恒 undefined（H10 类型谎报清理）。
export interface FundStatistics {
  fund_type: string
  fund_type_label: string
  total_investment: number
  count: number
}

// 年度经费对比接口
// 2026-10-14 按真实契约订正（backend/app/api/v1/funds.py
// `/supported-village/statistics/yearly-comparison` 的实际返回体）：
// 历史上虚构了 total_military/total_local/utilization_rate/by_type 等字段，
// 导致经费分析页"利用率趋势"折线图恒为 0（排查报告 H10）。
// 利用率由前端按 total_actual / total_planned 计算。
export interface YearlyFundSummary {
  year: number
  total_actual: number
  total_planned: number
  count: number
}

// 利用率统计接口
// 2026-10-16 按真实契约订正：后端 `fund_stats_utilization` 不含 by_type 分组，
// 页面若要按类型拆分需另调 by-type 端点自行计算。
export interface UtilizationRateData {
  overall_utilization_rate: number
  total_actual_investment: number
  total_planned_investment: number
}

// 经费汇总接口
// 2026-10-16 按真实契约订正：后端 `fund_stats_summary` 返回四项总量指标，
// 历史字段 period/grand_total/by_type/yearly_data 均为前端虚构（H10 清理）。
export interface FundSummaryData {
  total_count: number
  total_amount: number
  total_allocated: number
  total_used: number
}

// 查询参数接口
export interface FundQueryParams {
  year?: number
  village_id?: number
  department?: string
  year_start?: number
  year_end?: number
}

// ── 契约编译期断言（对照 backend/app/api/v1/funds.py 四个统计端点）──
// "接口类型写错"这类谎报运行时测试无法拦截（多写字段只会让页面读取恒 undefined），
// 这里用严格类型相等断言把它锁进 vue-tsc 门禁：契约漂移 → 编译期报 TS2344。
type Assert<T extends true> = T
/** 严格类型相等判定（含多余键与可选性，等价 vitest expectTypeOf 的相等技巧） */
type TypeEquals<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false

export type FundStatisticsContract = Assert<
  TypeEquals<
    FundStatistics,
    { fund_type: string; fund_type_label: string; total_investment: number; count: number }
  >
>
export type YearlyFundSummaryContract = Assert<
  TypeEquals<
    YearlyFundSummary,
    { year: number; total_actual: number; total_planned: number; count: number }
  >
>
export type UtilizationRateDataContract = Assert<
  TypeEquals<
    UtilizationRateData,
    {
      overall_utilization_rate: number
      total_actual_investment: number
      total_planned_investment: number
    }
  >
>
export type FundSummaryDataContract = Assert<
  TypeEquals<
    FundSummaryData,
    { total_count: number; total_amount: number; total_allocated: number; total_used: number }
  >
>

/**
 * 按类型获取经费统计
 * 后端 data 为 {fund_type: 类型条目} 映射（信封经响应拦截器会把条目提升到顶层，
 * 但契约保证的读取路径是 res.data[fund_type]）；无 fund_types 字段。
 */
export function getFundStatisticsByType(params?: FundQueryParams) {
  return get<{
    success: boolean
    message?: string
    data: Record<string, FundStatistics>
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
