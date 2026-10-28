import { get, post, put, del } from '@/api/request'

// Types
export type WorkStatus = 'pending' | 'in_progress' | 'completed' | 'delayed' | 'cancelled'

export type WorkType =
  | 'industry'
  | 'infrastructure'
  | 'education'
  | 'medical'
  | 'party'
  | 'consumption'
  | 'employment'
  | 'other'
  | 'party_building'
  | 'ecommerce'
  | 'talent'

export interface WorkReportData {
  summary: Record<string, any>
  details: any[]
  generated_at: string
}

/**
 * 乡村工作记录（列表项的最小子集；后端还有更多字段，用索引签名兼容）。
 * 之前本文件全 `any`，视图只能靠断言读，字段拼错也发现不了。
 */
export interface RuralWorkRecord {
  id: number
  name?: string
  village_name?: string
  responsible_person?: string
  status?: string
  progress?: number
  start_date?: string
  end_date?: string
  description?: string
  created_at?: string
  [key: string]: unknown
}

/** 列表响应：兼容 {items,total} 与信封 {data:{items,total}} 两种形态 */
export interface RuralWorkListPayload {
  items?: RuralWorkRecord[]
  total?: number
  data?: { items?: RuralWorkRecord[]; total?: number }
}

export interface RuralWorkCreated {
  id?: number
  data?: { id?: number }
}

// Named functions — unwrap AxiosResponse，返回 res.data
export const getRuralWorks = (params?: Record<string, unknown>) =>
  get<RuralWorkListPayload>('/rural-works', params)

export const createRuralWork = (data: Record<string, unknown>) =>
  post<RuralWorkCreated>('/rural-works', data)

export const updateRuralWork = (id: number, data: Record<string, unknown>) =>
  put<RuralWorkCreated>('/rural-works/' + id, data)

export const deleteRuralWork = (id: number) => del('/rural-works/' + id)

export const generateWorkReport = (params?: any) => get('/rural-works/report/generate', params)

// Backward-compatible object form
export const ruralWorkApi = {
  list: (params?: any) => get('/rural-works', params),
  get: (id: number) => get('/rural-works/' + id),
  getById: (id: number) => get('/rural-works/' + id),
  create: (data: any) => post('/rural-works', data),
  update: (id: number, data: any) => put('/rural-works/' + id, data),
  delete: deleteRuralWork,
  getRuralWorks,
  createRuralWork,
  updateRuralWork,
  deleteRuralWork,
  generateWorkReport,
  getStatistics: () => get('/rural-works/statistics/summary'),
  getVillagesForSelect: () => get('/rural-works/villages'),
  getAvailableYears: () => get('/rural-works/years'),
  batchDelete: (ids: number[]) => post('/rural-works/batch-delete', { ids }),
}
