/**
 * 工具函数统一导出
 */

export { logger } from './logger'
export { default as request } from '@/api/request'
export { exportUtil } from './exportUtil'
export { copyToClipboard } from './clipboard'
export { getYearOptions, DEFAULT_START_YEAR, FUTURE_YEAR_SPAN } from './yearOptions'
export type { YearOptionsConfig } from './yearOptions'

/** 格式化工具集 */
export const format = {
  /** 格式化日期时间（与 Date.toLocaleString("zh-CN") 一致） */
  formatDateTime(date: Date | string, fmt = 'YYYY-MM-DD HH:mm:ss'): string {
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return String(date)
    const pad = (n: number) => String(n).padStart(2, '0')
    return fmt
      .replace('YYYY', String(d.getFullYear()))
      .replace('MM', pad(d.getMonth() + 1))
      .replace('DD', pad(d.getDate()))
      .replace('HH', pad(d.getHours()))
      .replace('mm', pad(d.getMinutes()))
      .replace('ss', pad(d.getSeconds()))
  },

  /** 格式化日期时间（locale 格式） */
  formatDateTimeLocale(date: Date | string): string {
    if (!date) return '-'
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return '-'
    return d.toLocaleString('zh-CN')
  },

  /** 格式化日期 */
  formatDate(date: Date | string): string {
    if (!date) return '-'
    return format.formatDateTime(date, 'YYYY-MM-DD')
  },

  /** 格式化日期时间（带时间） */
  formatDateTimeFull(date: Date | string): string {
    if (!date) return '-'
    return format.formatDateTime(date, 'YYYY-MM-DD HH:mm:ss')
  },

  /** 格式化货币 */
  formatCurrency(value: number, unit = '元'): string {
    return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) + unit
  },
}
