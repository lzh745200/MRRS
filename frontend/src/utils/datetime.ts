/**
 * 统一日期时间格式化（UI 精细化设计方案 v2.0 · P1 底座）
 *
 * 全站日期/时间显示只允许使用本模块的具名格式，禁止在视图内
 * 手写 toLocaleDateString / dayjs(...).format('...') 散弹式实现
 * （此前 38 个文件各自为政）。
 *
 * 8 个具名格式：
 * - DATE          2026-08-25              列表日期列、统计维度
 * - DATETIME      2026-08-25 14:30        通用明细时间
 * - DATETIME_SEC  2026-08-25 14:30:05     审计日志（需秒级追溯）
 * - TIME          14:30                   当日内时间
 * - CN_DATE       2026年8月25日           报表/打印正式文本
 * - CN_DATETIME   2026年8月25日 14:30     报表正文
 * - MONTH         2026-08                 月度趋势图分组键
 * - FILESAFE      20260825_143005         导出文件名（无非法字符）
 */
import dayjs from 'dayjs'

export const DATE = 'YYYY-MM-DD'
export const DATETIME = 'YYYY-MM-DD HH:mm'
export const DATETIME_SEC = 'YYYY-MM-DD HH:mm:ss'
export const TIME = 'HH:mm'
export const CN_DATE = 'YYYY年M月D日'
export const CN_DATETIME = 'YYYY年M月D日 HH:mm'
export const MONTH = 'YYYY-MM'
export const FILESAFE = 'YYYYMMDD_HHmmss'

/** 安全解析：空值/无效值返回空串而非 'Invalid Date' */
function _src(value?: string | number | Date | null): dayjs.Dayjs | null {
  if (value === null || value === undefined || value === '') return null
  const d = dayjs(value as string | number | Date)
  return d.isValid() ? d : null
}

export function formatDate(value?: string | number | Date | null, pattern: string = DATE): string {
  const d = _src(value)
  return d ? d.format(pattern) : ''
}

export function formatDateTime(value?: string | number | Date | null): string {
  return formatDate(value, DATETIME)
}

export function formatDateTimeSec(value?: string | number | Date | null): string {
  return formatDate(value, DATETIME_SEC)
}

export function formatCnDate(value?: string | number | Date | null): string {
  return formatDate(value, CN_DATE)
}

export function monthKey(value?: string | number | Date | null): string {
  return formatDate(value, MONTH)
}

/** 导出文件名安全时间戳：20260825_143005 */
export function fileTimestamp(date: Date = new Date()): string {
  return formatDate(date, FILESAFE)
}
