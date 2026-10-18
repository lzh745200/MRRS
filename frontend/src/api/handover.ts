/**
 * 工作移交 API（w17-004）
 *
 * 人员轮换时把「我负责/我发起」的帮扶村、项目、待办、审批中申请一键交给接任人：
 * - inventory：可移交清单预览（按数据域过滤）
 * - candidates：同组织可选接任人（超管全量）
 * - execute：单事务执行（跨组织 403；双方站内消息 + WorkLog 审计）
 * - history：我的移交历史（后端由 WorkLog 审计行承载）
 */
import { get, post } from '@/api/request'

const BASE = '/handover'

/** 可移交资产类型（与后端 handover_service.ASSET_TYPES 一致） */
export type HandoverAssetType = 'village' | 'project' | 'todo' | 'approval'

/** 各资产类型中文标签（与后端 ASSET_LABELS 一致） */
export const ASSET_TYPE_LABELS: Record<HandoverAssetType, string> = {
  village: '帮扶村',
  project: '帮扶项目',
  todo: '待办事项',
  approval: '审批中申请',
}

/** 归属角色中文标签 */
export const ASSET_ROLE_LABELS: Record<string, string> = {
  owner: '责任人',
  approver: '待我审批',
  submitter: '我发起',
  both: '我发起且待我审批',
}

export interface HandoverAssetItem {
  type: HandoverAssetType
  id: number
  title: string
  subtitle?: string | null
  role?: string | null
}

export interface HandoverGroup {
  type: HandoverAssetType
  label: string
  count: number
  items: HandoverAssetItem[]
}

export interface HandoverInventory {
  groups: HandoverGroup[]
  total: number
  generated_at?: string | null
}

export interface HandoverCandidate {
  id: number
  username: string
  full_name?: string | null
  role?: string | null
  department?: string | null
  organization_id?: number | null
}

export interface HandoverCandidateList {
  items: HandoverCandidate[]
  total: number
}

export interface HandoverUserBrief {
  id?: number | null
  username?: string | null
  full_name?: string | null
}

export interface HandoverCounts {
  village: number
  project: number
  todo: number
  approval: number
}

export interface HandoverExecutePayload {
  to_user_id: number
  scope?: HandoverAssetType[]
  item_ids?: Partial<Record<HandoverAssetType, number[]>>
  note?: string | null
}

/** 执行成功后的交接单（响应即可直接用于展示/导出） */
export interface HandoverReceipt {
  record_id?: number | null
  record_no: string
  from_user: HandoverUserBrief
  to_user: HandoverUserBrief
  created_at?: string | null
  note?: string | null
  items: HandoverAssetItem[]
  counts: HandoverCounts
  total: number
}

/** 历史交接单（后端由 WorkLog 快照回放，字段与 receipt 略有差异） */
export interface HandoverHistoryItem {
  id: number
  record_no?: string | null
  from_user_id?: number | null
  from_username?: string | null
  to_user_id?: number | null
  to_username?: string | null
  note?: string | null
  counts: HandoverCounts
  total: number
  items: HandoverAssetItem[]
  content?: string
  log_date?: string | null
  created_at?: string | null
}

export interface HandoverHistoryData {
  items: HandoverHistoryItem[]
  total: number
  page: number
  page_size: number
}

/** 可移交清单预览 */
export async function getHandoverInventory(): Promise<HandoverInventory> {
  return get(`${BASE}/inventory`)
}

/** 可选接任人（keyword 模糊搜索；limit 上限 500） */
export async function getHandoverCandidates(
  params: { keyword?: string; limit?: number } = {}
): Promise<HandoverCandidateList> {
  return get(`${BASE}/candidates`, params)
}

/** 执行移交（单事务；失败全量回滚） */
export async function executeHandover(payload: HandoverExecutePayload): Promise<HandoverReceipt> {
  return post(`${BASE}/execute`, payload)
}

/** 我的移交历史 */
export async function getHandoverHistory(
  params: { page?: number; page_size?: number; date_from?: string; date_to?: string } = {}
): Promise<HandoverHistoryData> {
  return get(`${BASE}/history`, params)
}
