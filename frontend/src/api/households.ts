/**
 * 一户一档 API（W22 契约 §2 /households）
 *
 * - 列表筛选（村/风险等级/户类型/关键词）、CRUD（软删）；
 * - 家庭成员 CRUD；
 * - 预警清单（规则命中 + open 风险记录）、风险记录登记/关闭；
 * - 一键汇总回填 VillagePopulation；
 * - 台账导出（xlsx/csv，链式 triggerDownload）。
 *
 * 所有请求经 @/api/request 的 get/post/put/del 自动解包 envelope；
 * 导出为 blob 响应，由本模块内部链式触发浏览器下载，调用方只需 await。
 */
import request, { get, post, put, del } from '@/api/request'
import { triggerDownload } from '@/api/export'

const BASE = '/households'

/** 户类型：一般户 / 脱贫户 / 监测户 */
export type HouseholdType = 'general' | 'poverty' | 'monitor'
/** 风险类型 */
export type HouseholdRiskType =
  | 'none'
  | 'income_drop'
  | 'illness'
  | 'housing'
  | 'sudden'
  | 'multiple'
/** 风险等级 */
export type HouseholdRiskLevel = 'low' | 'medium' | 'high'
/** 风险记录状态 */
export type HouseholdRiskStatus = 'open' | 'closed'

/** 一户一档列表项 */
export interface HouseholdItem {
  id: number
  supported_village_id: number
  village_name?: string | null
  household_code?: string | null
  household_name: string
  address?: string | null
  household_type: HouseholdType
  risk_type: HouseholdRiskType
  risk_level: HouseholdRiskLevel
  helper_name?: string | null
  helper_phone?: string | null
  annual_income?: number | null
  migrant_workers?: number | null
  has_serious_illness?: boolean
  housing_safe?: boolean
  last_visit_date?: string | null
  monitoring_note?: string | null
  organization_id?: number | null
  created_by?: number | null
  is_active?: boolean
  created_at?: string | null
  updated_at?: string | null
  /** 后端富化：家庭成员数 */
  member_count?: number
  /** 后端富化：预警规则命中文案 */
  risk_alerts?: string[]
}

/** 家庭成员 */
export interface HouseholdMember {
  id: number
  household_id: number
  name: string
  relation?: string | null
  id_card?: string | null
  gender?: string | null
  birth_year?: number | null
  education?: string | null
  health_status?: string | null
  employment_status?: string | null
  income?: number | null
  is_special_support?: boolean
  created_at?: string | null
  updated_at?: string | null
}

/** 风险/预警记录 */
export interface HouseholdRiskRecord {
  id: number
  household_id: number
  risk_type: HouseholdRiskType
  risk_level: HouseholdRiskLevel
  reason?: string | null
  detected_at?: string | null
  status: HouseholdRiskStatus
  closed_at?: string | null
  closed_note?: string | null
  created_at?: string | null
}

/** 挂户走访记录（visit_records.household_id，详情接口富化） */
export interface HouseholdVisit {
  id: number
  pairing_id?: number | null
  visit_date: string
  visitors: string
  purpose?: string | null
  content?: string | null
  materials?: string | null
}

/** 一户一档详情（含后端富化的成员/风险记录/走访） */
export interface HouseholdDetail extends HouseholdItem {
  members?: HouseholdMember[]
  risk_records?: HouseholdRiskRecord[]
  visits?: HouseholdVisit[]
}

/** 列表查询参数 */
export interface HouseholdListQuery {
  page?: number
  page_size?: number
  village_id?: number
  risk_level?: HouseholdRiskLevel | ''
  household_type?: HouseholdType | ''
  keyword?: string
}

/** 列表响应 */
export interface HouseholdListData {
  items: HouseholdItem[]
  total: number
  page: number
  page_size: number
}

/** 新建/更新载荷 */
export interface HouseholdPayload {
  supported_village_id?: number | null
  household_code?: string | null
  household_name?: string
  address?: string | null
  household_type?: HouseholdType
  risk_type?: HouseholdRiskType
  risk_level?: HouseholdRiskLevel
  helper_name?: string | null
  helper_phone?: string | null
  annual_income?: number | null
  migrant_workers?: number | null
  has_serious_illness?: boolean
  housing_safe?: boolean
  last_visit_date?: string | null
  monitoring_note?: string | null
}

/** 成员新建/更新载荷 */
export interface HouseholdMemberPayload {
  name?: string
  relation?: string | null
  id_card?: string | null
  gender?: string | null
  birth_year?: number | null
  education?: string | null
  health_status?: string | null
  employment_status?: string | null
  income?: number | null
  is_special_support?: boolean
}

/** 风险记录登记载荷 */
export interface HouseholdRiskRecordPayload {
  risk_type: HouseholdRiskType
  risk_level?: HouseholdRiskLevel
  reason?: string | null
}

/** 预警清单项（规则命中 + open 风险记录） */
export interface HouseholdAlert {
  household_id: number
  household_name?: string | null
  village_name?: string | null
  risk_level?: HouseholdRiskLevel | null
  risk_type?: HouseholdRiskType | null
  reason?: string | null
  alerts?: string[]
  /** 来源：auto=规则命中 / record=open 风险记录 */
  source?: 'auto' | 'record' | string
}

/** 汇总回填结果（写回字段摘要） */
export interface HouseholdRollupResult {
  village_id?: number
  village_name?: string
  year?: number
  total_households?: number
  total_population?: number
  poverty_households?: number
  monitor_households?: number
  written?: Record<string, number | string | null>
  message?: string
}

/** 导出参数 */
export interface HouseholdExportQuery {
  format: 'xlsx' | 'csv'
  village_id?: number
  risk_level?: HouseholdRiskLevel | ''
}

// ── 列表 / 详情 / CRUD ──
export function getHouseholds(params: HouseholdListQuery = {}): Promise<HouseholdListData> {
  return get(BASE, params)
}

export function getHousehold(id: number): Promise<HouseholdDetail> {
  return get(`${BASE}/${id}`)
}

export function createHousehold(payload: HouseholdPayload): Promise<HouseholdItem> {
  return post(BASE, payload)
}

export function updateHousehold(id: number, payload: HouseholdPayload): Promise<HouseholdItem> {
  return put(`${BASE}/${id}`, payload)
}

/** 软删（is_active=false） */
export function deleteHousehold(id: number): Promise<{ id: number }> {
  return del(`${BASE}/${id}`)
}

// ── 家庭成员 ──
/** 成员列表响应（数组直返 / ok_list envelope） */
export type HouseholdMemberList = HouseholdMember[] | { items: HouseholdMember[] }

export function getHouseholdMembers(id: number): Promise<HouseholdMemberList> {
  return get(`${BASE}/${id}/members`)
}

export function createHouseholdMember(
  id: number,
  payload: HouseholdMemberPayload
): Promise<HouseholdMember> {
  return post(`${BASE}/${id}/members`, payload)
}

export function updateHouseholdMember(
  id: number,
  memberId: number,
  payload: HouseholdMemberPayload
): Promise<HouseholdMember> {
  return put(`${BASE}/${id}/members/${memberId}`, payload)
}

export function deleteHouseholdMember(id: number, memberId: number): Promise<{ id: number }> {
  return del(`${BASE}/${id}/members/${memberId}`)
}

// ── 预警 / 风险记录 ──
/** 预警清单响应（数组直返 / ok_list envelope） */
export type HouseholdAlertList = HouseholdAlert[] | { items: HouseholdAlert[] }

export function getHouseholdAlerts(
  params: { level?: HouseholdRiskLevel | '' } = {}
): Promise<HouseholdAlertList> {
  return get(`${BASE}/alerts`, params)
}

export function createHouseholdRiskRecord(
  id: number,
  payload: HouseholdRiskRecordPayload
): Promise<HouseholdRiskRecord> {
  return post(`${BASE}/${id}/risk-records`, payload)
}

export function closeHouseholdRiskRecord(
  recordId: number,
  payload: { closed_note?: string } = {}
): Promise<HouseholdRiskRecord> {
  return put(`${BASE}/risk-records/${recordId}/close`, payload)
}

// ── 汇总回填 / 导出 ──
export function rollupHouseholds(params: {
  village_id: number
  year?: number
}): Promise<HouseholdRollupResult> {
  return post(`${BASE}/rollup`, undefined, { params })
}

/** 导出台账：blob 响应 → 链式触发浏览器下载（xlsx/csv） */
export function exportHouseholds(params: HouseholdExportQuery): Promise<void> {
  const { format, ...filters } = params
  const suffix = filters.village_id ? `_村${filters.village_id}` : ''
  return request
    .get(`${BASE}/export`, { params: { ...filters, format }, responseType: 'blob' })
    .then((res) => {
      triggerDownload(res.data as Blob, `一户一档台账${suffix}.${format}`)
    })
}
