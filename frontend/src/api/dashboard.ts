/**
 * 仪表盘API服务
 * 提供首页统计数据、近期动态的增删改查
 */

import { get, post, put, del, apiRequest } from '@/api/request'

const BASE_URL = '/dashboard'

/** 获取仪表盘统计数据 */
/** 概览统计（视图只读 trends 四项，用索引签名放行其它字段） */
export interface DashboardStatsPayload {
  trends?: {
    villages?: number
    population_yoy?: number
    income_yoy?: number
    funds?: number
  }
  [key: string]: unknown
}

export function getDashboardStats(refresh?: boolean): Promise<DashboardStatsPayload> {
  return apiRequest({
    method: 'GET',
    url: `${BASE_URL}/stats`,
    params: { refresh: refresh ?? false },
  })
}

/** 仪表盘汇总（统计 + 近期动态，一次请求） */
export function getDashboardSummary(): Promise<any> {
  return get(`${BASE_URL}/summary`)
}

/** 获取近期动态 */
export function getRecentActivities(): Promise<any> {
  return get(`${BASE_URL}/recent-activities`)
}

/** 创建自定义动态 */
export function createActivity(data: {
  type?: string
  action: string
  target: string
}): Promise<any> {
  return post(`${BASE_URL}/recent-activities`, data)
}

/** 更新自定义动态 */
export function updateActivity(
  activityId: string,
  data: {
    type?: string
    action?: string
    target?: string
  }
): Promise<any> {
  return put(`${BASE_URL}/recent-activities/${activityId}`, data)
}

/** 删除动态（自定义动态物理删除，系统动态持久化隐藏） */
export function deleteActivity(activityId: string): Promise<any> {
  return del(`${BASE_URL}/recent-activities/${activityId}`)
}

/** KPI 年度同比趋势 */
export function getKpiTrends(): Promise<any> {
  return get(`${BASE_URL}/kpi-trends`)
}

/** 年度趋势对比数据 */
/** 年度趋势（years/villages/population/income 为对齐的数组，trends 为明细） */
export interface YearlyTrendsPayload {
  years?: number[]
  villages?: number[]
  population?: number[]
  income?: number[]
  trends?: Array<{ total_actual?: number } & Record<string, unknown>>
  [key: string]: unknown
}

export function getYearlyTrends(years?: number): Promise<YearlyTrendsPayload> {
  return get(`${BASE_URL}/yearly-trends`, { years: years ?? 5 })
}
