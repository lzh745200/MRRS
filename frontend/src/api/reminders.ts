/**
 * 提醒中心 API（审批超时/项目截止/预算预警等聚合 + 处置闭环）
 *
 * 处置动作（handle/ignore/snooze/reopen）仅提醒接收人本人可操作，
 * 越权/不存在后端一律 404（fail-closed）。
 */
import { get, post } from '@/api/request'

const BASE = '/reminders'

/** 处置状态：open=待处理 / handled=已处理 / ignored=已忽略 */
export type ReminderState = 'open' | 'handled' | 'ignored'

export interface ReminderItem {
  id: number
  type: string
  title: string
  content: string
  created_at?: string | null
  is_read: boolean
  state?: ReminderState | string
  note?: string | null
  snooze_until?: string | null
  acted_at?: string | null
  link?: string | null
  entity_id?: number | null
}

export interface ReminderStats {
  pending: number
  handled: number
  ignored: number
  snoozed: number
  total: number
}

export interface ReminderList {
  items: ReminderItem[]
  total: number
  unread: number
  stats?: ReminderStats
}

export interface ReminderDisposition {
  message_id: number
  state: string
  note: string | null
  snooze_until: string | null
  acted_at: string | null
}

/** 获取提醒列表（includeIgnored=true 时包含已忽略的提醒） */
export async function getReminders(includeIgnored = false): Promise<ReminderList> {
  return includeIgnored ? get(BASE, { include_ignored: true }) : get(BASE)
}

/** 手动触发一次提醒扫描 */
export async function triggerReminderScan(): Promise<{ created: number }> {
  return post(`${BASE}/scan`)
}

/** 标记提醒已处理（note 为选填说明） */
export async function handleReminder(id: number, note = ''): Promise<ReminderDisposition> {
  return post(`${BASE}/${id}/handle`, { note })
}

/** 忽略提醒（reason 为选填原因） */
export async function ignoreReminder(id: number, reason = ''): Promise<ReminderDisposition> {
  return post(`${BASE}/${id}/ignore`, { note: reason })
}

/** 延期提醒 N 天（1-90） */
export async function snoozeReminder(id: number, days = 7): Promise<ReminderDisposition> {
  return post(`${BASE}/${id}/snooze`, { days })
}

/** 重新打开已处理/已忽略的提醒 */
export async function reopenReminder(id: number, note = ''): Promise<ReminderDisposition> {
  return post(`${BASE}/${id}/reopen`, { note })
}
