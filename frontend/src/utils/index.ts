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
    // 守卫与兄弟函数（formatDateTimeLocale/formatDate/formatDateTimeFull）对齐：
    // 原实现遇到 null/undefined 会走 d.getTime() 抛 TypeError（渲染期崩溃）
    if (!date) return '-'
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

  /** 格式化货币（最多4位小数，自动去尾零） */
  formatCurrency(value: number | string | null | undefined, unit = '元'): string {
    // 原实现直接 value.toLocaleString()：null/undefined 抛 TypeError，NaN 渲染成 'NaN'
    if (value === null || value === undefined || value === '') return '-'
    const n = Number(value)
    if (!Number.isFinite(n)) return '-'
    return n.toLocaleString('zh-CN', { maximumFractionDigits: 4 }) + unit
  },

  /** 格式化金额(万元)：最多4位小数、千分位、自动去尾零 */
  formatMoney4(value: number | string | null | undefined): string {
    const n = Number(value ?? 0)
    if (!Number.isFinite(n)) return '0'
    return n.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
  },
}
