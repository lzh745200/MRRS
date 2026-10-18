/**
 * 消费帮扶台账 API（W22 契约 §2 /consumption，替换原舆情监测 /sentiment）
 *
 * - 列表/统计/CRUD：走 `get/post/put/del`（自动解包 envelope）；
 * - 导出：`exportConsumption({format})` 走 GET 下载（xlsx/csv），
 *   统一复用 `downloadBlobAsFile`（解析 Content-Disposition 文件名）。
 */
import request, { get, post, put, del } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

/** 消费品类（契约 §1.5） */
export type ConsumptionCategory = 'agriculture' | 'livestock' | 'handicraft' | 'other'

/** 供货方类型 */
export type ConsumptionSellerType = 'farmer' | 'cooperative' | 'enterprise'

/** 品类 → 中文标签（唯一映射源，视图/统计卡共用） */
export const CONSUMPTION_CATEGORY_LABELS: Record<ConsumptionCategory, string> = {
  agriculture: '农产品',
  livestock: '畜禽',
  handicraft: '手工',
  other: '其他',
}

/** 供货方类型 → 中文标签 */
export const CONSUMPTION_SELLER_TYPE_LABELS: Record<ConsumptionSellerType, string> = {
  farmer: '农户',
  cooperative: '合作社',
  enterprise: '企业',
}

/** 消费帮扶台账记录（consumption_records） */
export interface ConsumptionRecord {
  id: number
  supported_village_id?: number | null
  village_name?: string | null
  category: ConsumptionCategory
  item_name: string
  quantity?: number | null
  unit?: string | null
  amount: number
  buyer?: string | null
  seller?: string | null
  seller_type?: ConsumptionSellerType | null
  year: number
  record_date?: string | null
  voucher_url?: string | null
  remarks?: string | null
  created_at?: string | null
  updated_at?: string | null
}

/** 列表筛选参数（契约 §2） */
export interface ConsumptionQuery {
  page?: number
  page_size?: number
  year?: number | null
  category?: ConsumptionCategory | ''
  village_id?: number | null
  keyword?: string
}

/** 新建/编辑入参 */
export interface ConsumptionRecordPayload {
  supported_village_id?: number | null
  category: ConsumptionCategory
  item_name: string
  quantity?: number | null
  unit?: string | null
  amount: number
  buyer?: string | null
  seller?: string | null
  seller_type?: ConsumptionSellerType | null
  year: number
  record_date?: string | null
  voucher_url?: string | null
  remarks?: string | null
}

/** 品类统计条目 */
export interface ConsumptionCategoryStat {
  category: string
  amount?: number
  total_amount?: number
  count?: number
}

/** 村维度统计条目 */
export interface ConsumptionVillageStat {
  supported_village_id?: number | null
  village_id?: number | null
  village_name?: string | null
  amount?: number
  total_amount?: number
  count?: number
}

/** 年度统计（契约 §2 /consumption/statistics） */
export interface ConsumptionStatistics {
  total_amount?: number
  record_count?: number
  by_category?: ConsumptionCategoryStat[]
  by_village?: ConsumptionVillageStat[]
}

/** 导出格式 */
export type ConsumptionExportFormat = 'xlsx' | 'csv'

/** 导出入参 */
export interface ConsumptionExportQuery {
  format: ConsumptionExportFormat
  year?: number | null
  category?: ConsumptionCategory | ''
  village_id?: number | null
  keyword?: string
}

/** 列表（后端 ok_list envelope，调用方用 unwrapList 解包） */
export const getConsumptionRecords = (params?: ConsumptionQuery) => get('/consumption', params)

/** 年度统计（year 缺省时后端取当前年） */
export const getConsumptionStatistics = (year?: number | null) =>
  get('/consumption/statistics', year === undefined || year === null ? undefined : { year })

/** 新建台账记录 */
export const createConsumptionRecord = (data: ConsumptionRecordPayload) =>
  post('/consumption', data)

/** 更新台账记录 */
export const updateConsumptionRecord = (id: number, data: Partial<ConsumptionRecordPayload>) =>
  put(`/consumption/${id}`, data)

/** 删除台账记录（软删） */
export const deleteConsumptionRecord = (id: number) => del(`/consumption/${id}`)

/**
 * 导出当前筛选台账（xlsx/csv）。
 * 文件名优先取服务端 Content-Disposition，兜底按格式命名。
 */
export const exportConsumption = (params: ConsumptionExportQuery) => {
  const query: Record<string, unknown> = { format: params.format }
  if (params.year !== undefined && params.year !== null) query.year = params.year
  if (params.category) query.category = params.category
  if (params.village_id !== undefined && params.village_id !== null) {
    query.village_id = params.village_id
  }
  if (params.keyword) query.keyword = params.keyword
  return downloadBlobAsFile(
    () => request.get('/consumption/export', { params: query, responseType: 'blob' }),
    { fallbackFileName: `消费帮扶台账.${params.format}` }
  )
}
