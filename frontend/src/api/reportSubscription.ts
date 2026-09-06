/**
 * 报表订阅 API（工单 003 订阅闭环前端契约）
 *
 * 后端路由：/reports/subscriptions（data 包无额外前缀，见 w14 R4 契约核验）
 * 响应形态：list=ok_list 信封；create=裸对象（response_model 直出）；
 *           toggle/generate-now/delete=success_response 信封。
 * 生成走站内消息通知（单机版送达语义），无需前端 blob 下载。
 */
import { get, post, put, del } from '@/api/request'

export interface ReportSubscription {
  id: number
  user_id: number
  name: string
  report_type: string
  format: string
  year?: number | null
  village_ids?: number[] | null
  include_sections?: string[] | null
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly'
  send_day?: number | null
  send_time?: string | null
  email?: string | null
  output_dir?: string | null
  output_format?: string | null
  is_active: boolean
  last_sent_at?: string | null
  next_send_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface ReportSubscriptionCreatePayload {
  name: string
  report_type: string
  format?: string
  year?: number | null
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly'
  send_day?: number | null
  send_time?: string
  output_format?: string
}

const BASE = '/reports/subscriptions'

/** 分页列表（ok_list 信封：{items,total,page,page_size,pages}） */
export async function listSubscriptions(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
}) {
  return await get(BASE, params)
}

/** 创建订阅（后端裸对象返回，无信封） */
export async function createSubscription(payload: ReportSubscriptionCreatePayload) {
  return await post(BASE, payload)
}

/** 更新订阅 */
export async function updateSubscription(
  id: number,
  payload: Partial<ReportSubscriptionCreatePayload> & { is_active?: boolean }
) {
  return await put(`${BASE}/${id}`, payload)
}

/** 删除订阅（硬删，success_response 信封） */
export async function deleteSubscription(id: number) {
  return await del(`${BASE}/${id}`)
}

/** 切换启用/禁用（success_response 信封） */
export async function toggleSubscription(id: number) {
  return await post(`${BASE}/${id}/toggle`, {})
}

/** 立即生成（工单 003 方案 B：不等调度周期；成功后站内消息送达） */
export async function generateSubscriptionNow(id: number) {
  return await post(`${BASE}/${id}/generate-now`, {})
}
