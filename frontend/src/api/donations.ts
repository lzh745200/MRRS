/**
 * 捐赠物资台账 API（w17-003）
 *
 * - 实物捐赠口径：图书 / 设备 / 物资（区别于资金侧的 donation 类型）；
 * - 去向：帮扶村 / 帮扶学校 / 项目（三选一，与 destination_type 联动）；
 * - 列表/统计均按当前用户数据域过滤（后端 donation_base_query）。
 */
import { get, post, put, del } from '@/api/request'

const BASE = '/donations'

/** 物资类别（与后端 category 取值一致） */
export const DONATION_CATEGORIES = [
  { value: 'book', label: '图书' },
  { value: 'equipment', label: '设备' },
  { value: 'material', label: '物资' },
] as const

/** 去向下拉 */
export const DONATION_DESTINATIONS = [
  { value: 'village', label: '帮扶村' },
  { value: 'school', label: '帮扶学校' },
  { value: 'project', label: '项目' },
] as const

export interface DonationAttachment {
  url: string
  file_name?: string | null
}

export interface DonationItem {
  id: number
  name: string
  category: string
  quantity: number
  unit?: string | null
  valuation: number
  source_unit?: string | null
  destination_type: string
  village_id?: number | null
  school_id?: number | null
  project_id?: number | null
  delivery_date?: string | null
  receiver?: string | null
  attachments?: DonationAttachment[] | null
  remark?: string | null
  organization_id?: number | null
  created_by?: number | null
  is_deleted?: boolean
  created_at?: string | null
  updated_at?: string | null
  /** 去向显示名（后端 attach_destination_names 富化） */
  destination_name?: string | null
  viewableBecause?: string | null
}

export interface DonationStats {
  total: number
  villages: number
  schools: number
  projects: number
  books: number
  equipment: number
  materials: number
  quantity: number
  valuation: number
}

export interface DonationListQuery {
  page?: number
  page_size?: number
  keyword?: string
  category?: string
  destination_type?: string
  destination_id?: number
  include_deleted?: boolean
}

export interface DonationListData {
  items: DonationItem[]
  total: number
  page: number
  page_size: number
}

export interface DonationPayload {
  name?: string
  category?: string
  quantity?: number
  unit?: string | null
  valuation?: number
  source_unit?: string | null
  destination_type?: string
  village_id?: number | null
  school_id?: number | null
  project_id?: number | null
  delivery_date?: string | null
  receiver?: string | null
  attachments?: DonationAttachment[] | null
  remark?: string | null
}

/** 台账列表（envelope 由请求层展开） */
export async function getDonations(params: DonationListQuery = {}): Promise<DonationListData> {
  return get(BASE, params)
}

/** 台账统计（当前用户数据域内口径） */
export async function getDonationStats(): Promise<DonationStats> {
  return get(`${BASE}/stats`)
}

/** 物资详情 */
export async function getDonation(id: number): Promise<DonationItem> {
  return get(`${BASE}/${id}`)
}

/** 登记物资 */
export async function createDonation(payload: DonationPayload): Promise<DonationItem> {
  return post(BASE, payload)
}

/** 更新物资 */
export async function updateDonation(id: number, payload: DonationPayload): Promise<DonationItem> {
  return put(`${BASE}/${id}`, payload)
}

/** 删除物资（软删） */
export async function deleteDonation(id: number): Promise<{ id: number }> {
  return del(`${BASE}/${id}`)
}
