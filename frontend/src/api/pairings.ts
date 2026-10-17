/**
 * 结对帮扶与走访台账 API（w17-002）
 *
 * - 结对台账：列表（数据域内）/ 统计 / 详情 / 增删改（软删）；
 * - 走访记录：挂在结对下，独立增删改；
 * - 对象名称（partner_name）由后端富化，前端直接展示。
 */
import { get, post, put, del } from '@/api/request'

const BASE = '/pairings'

export interface PairingItem {
  id: number
  subject_type: string
  subject_name: string
  subject_user_id?: number | null
  partner_type: string
  village_id?: number | null
  school_id?: number | null
  student_name?: string | null
  title: string
  content?: string | null
  start_date?: string | null
  end_date?: string | null
  status: string
  note?: string | null
  partner_name?: string | null
  organization_id?: number | null
  created_by?: number | null
  is_deleted?: boolean
  deleted_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  viewableBecause?: string | null
}

export interface VisitItem {
  id: number
  pairing_id: number
  visit_date: string
  visitors: string
  purpose?: string | null
  content?: string | null
  materials?: string | null
  organization_id?: number | null
  created_by?: number | null
  is_deleted?: boolean
  deleted_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface PairingStats {
  total: number
  active: number
  ended: number
  villages: number
  schools: number
  students: number
  visits: number
}

export interface PairingListQuery {
  page?: number
  page_size?: number
  keyword?: string
  subject_type?: string
  partner_type?: string
  partner_id?: number
  status?: string
  include_deleted?: boolean
}

export interface PairingListData {
  items: PairingItem[]
  total: number
  page: number
  page_size: number
}

export interface VisitListData {
  items: VisitItem[]
  total: number
  page: number
  page_size: number
}

export interface PairingPayload {
  subject_type?: string
  subject_name?: string
  subject_user_id?: number | null
  partner_type?: string
  village_id?: number | null
  school_id?: number | null
  student_name?: string | null
  title?: string
  content?: string | null
  start_date?: string | null
  end_date?: string | null
  status?: string
  note?: string | null
}

export interface VisitPayload {
  visit_date?: string
  visitors?: string
  purpose?: string | null
  content?: string | null
  materials?: string | null
}

/** 结对台账列表（envelope 由请求层展开） */
export async function getPairings(params: PairingListQuery = {}): Promise<PairingListData> {
  return get(BASE, params)
}

/** 台账统计（当前用户数据域内口径） */
export async function getPairingStats(): Promise<PairingStats> {
  return get(`${BASE}/stats`)
}

/** 结对详情 */
export async function getPairing(id: number): Promise<PairingItem> {
  return get(`${BASE}/${id}`)
}

/** 新建结对 */
export async function createPairing(payload: PairingPayload): Promise<PairingItem> {
  return post(BASE, payload)
}

/** 更新结对 */
export async function updatePairing(id: number, payload: PairingPayload): Promise<PairingItem> {
  return put(`${BASE}/${id}`, payload)
}

/** 删除结对（软删） */
export async function deletePairing(id: number): Promise<{ id: number }> {
  return del(`${BASE}/${id}`)
}

/** 某结对下的走访记录 */
export async function getVisits(
  pairingId: number,
  params: { page?: number; page_size?: number } = {}
): Promise<VisitListData> {
  return get(`${BASE}/${pairingId}/visits`, params)
}

/** 登记走访 */
export async function createVisit(pairingId: number, payload: VisitPayload): Promise<VisitItem> {
  return post(`${BASE}/${pairingId}/visits`, payload)
}

/** 更新走访 */
export async function updateVisit(
  pairingId: number,
  visitId: number,
  payload: VisitPayload
): Promise<VisitItem> {
  return put(`${BASE}/${pairingId}/visits/${visitId}`, payload)
}

/** 删除走访（软删） */
export async function deleteVisit(pairingId: number, visitId: number): Promise<{ id: number }> {
  return del(`${BASE}/${pairingId}/visits/${visitId}`)
}
