/**
 * 汇报大屏 API
 *
 * 大屏支持按「帮扶村 / 帮扶学校 / 帮扶单位」筛选查看对象帮扶情况：
 * - GET /bigscreen/filters：筛选对象列表（村/校/单位），后端按数据域收敛；
 * - GET /bigscreen/overview：按 scope 聚合的 KPI/图表/对象档案/帮扶明细。
 *
 * get() 会自动解包后端 envelope，返回值即 data 本体。
 */
import { get } from '@/api/request'

/** 大屏筛选对象类型：全部 / 帮扶村 / 帮扶学校 / 帮扶单位 */
export type BigScreenScopeType = 'all' | 'village' | 'school' | 'unit'

/** 帮扶村筛选项 */
export interface BigScreenVillageOption {
  id: number
  name: string
  county: string | null
  support_unit: string | null
}

/** 帮扶学校筛选项 */
export interface BigScreenSchoolOption {
  id: number
  name: string
  district: string | null
  support_unit: string | null
}

/** 帮扶单位筛选项（含覆盖统计，供下拉文案展示） */
export interface BigScreenUnitOption {
  name: string
  village_count: number
  school_count: number
  project_count: number
  pairing_count: number
}

/** GET /bigscreen/filters 响应 */
export interface BigScreenFilters {
  villages: BigScreenVillageOption[]
  schools: BigScreenSchoolOption[]
  units: BigScreenUnitOption[]
}

/** 当前筛选范围（后端回显） */
export interface BigScreenScope {
  type: BigScreenScopeType
  id: number | null
  name: string
  subtitle: string
}

/** 顶部 KPI（后端固定 5 项） */
export interface BigScreenKpi {
  key: string
  label: string
  value: number | string
  unit: string
}

/** 经费执行趋势单年数据 */
export interface BigScreenFundTrendPoint {
  year: number
  planned: number
  actual: number
}

/** 项目状态分布单项 */
export interface BigScreenProjectStatusItem {
  key: string
  label: string
  value: number
}

/** 年度对比单年数据 */
export interface BigScreenYearlyPoint {
  year: number
  project_count: number
  fund_count: number
}

/** 经费投入排名单项 */
export interface BigScreenRankingItem {
  name: string
  score: number
}

/** 重点项目负责人单项 */
export interface BigScreenLeaderItem {
  name: string
  person: string
  unit: string | null
}

/** 对象档案字段项 */
export interface BigScreenProfileItem {
  label: string
  value: string | null
}

/** 对象档案分组 */
export interface BigScreenProfileSection {
  title: string
  items: BigScreenProfileItem[]
}

/** 对象档案标签组 */
export interface BigScreenProfileTagGroup {
  label: string
  items: string[]
}

/** 对象档案（仅 scope != all 时非空） */
export interface BigScreenProfile {
  title: string
  sections: BigScreenProfileSection[]
  tags: BigScreenProfileTagGroup[]
}

/** 帮扶明细-项目项 */
export interface BigScreenDetailProject {
  name: string
  status: string
  label: string
  amount: number
  person: string
}

/** 帮扶明细-经费项 */
export interface BigScreenDetailFund {
  name: string
  year: number
  status: string
  label: string
  amount: number
}

/** 结对帮扶统计 */
export interface BigScreenPairingStats {
  total: number
  active: number
  visits: number
}

/** 帮扶明细（仅 scope != all 时非空） */
export interface BigScreenDetails {
  projects: BigScreenDetailProject[]
  funds: BigScreenDetailFund[]
  pairing: BigScreenPairingStats
}

/** GET /bigscreen/overview 响应 */
export interface BigScreenOverview {
  scope: BigScreenScope
  kpis: BigScreenKpi[]
  fund_trend: BigScreenFundTrendPoint[]
  project_status: BigScreenProjectStatusItem[]
  yearly: BigScreenYearlyPoint[]
  rankings: BigScreenRankingItem[]
  leaders: BigScreenLeaderItem[]
  profile: BigScreenProfile | null
  details: BigScreenDetails | null
}

/** GET /bigscreen/overview 请求参数 */
export interface BigScreenOverviewParams {
  scope_type: BigScreenScopeType
  scope_id?: number
  scope_name?: string
  years?: number
}

/** 筛选对象列表（挂载时加载一次；失败时大屏仅保留「全部」视图） */
export function getBigScreenFilters(): Promise<BigScreenFilters> {
  return get<BigScreenFilters>('/bigscreen/filters')
}

/** 按筛选范围加载大屏聚合数据（挂载/切 scope/自动轮询共用） */
export function getBigScreenOverview(params: BigScreenOverviewParams): Promise<BigScreenOverview> {
  return get<BigScreenOverview>('/bigscreen/overview', params)
}
