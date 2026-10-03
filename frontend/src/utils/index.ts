/**
 * 工具函数统一导出
 */

export { logger } from './logger'
export { default as request } from '@/api/request'
export { exportUtil } from './exportUtil'
export { copyToClipboard } from './clipboard'
export { getYearOptions, DEFAULT_START_YEAR, FUTURE_YEAR_SPAN } from './yearOptions'
export type { YearOptionsConfig } from './yearOptions'

/** 日期输入的可接受形态（各页面历史实现接收的类型不一，此处统一放宽） */
export type DateInput = Date | string | number | null | undefined

/** 中文星期简写，下标与 `Date.getDay()` 对齐 */
const WEEKDAY_CN = ['日', '一', '二', '三', '四', '五', '六'] as const

/**
 * 把任意输入转成可用的 `Date`；无法解析时返回 `null`。
 *
 * 历史背景：各页面自行实现的格式化函数对"非法输入"处理不一致 ——
 * 有的直接把 `new Date('垃圾')` 交给 `toLocaleString` 从而渲染出
 * 英文 "Invalid Date"，有的靠 `try/catch`（而 `toLocaleString` 对非法日期
 * **并不抛错**，所以那些 catch 其实是死代码）。统一走本函数后可保证：
 * 空值/非法值一律回退到调用方指定的兜底文案，界面上永远不会出现 "Invalid Date"。
 */
function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === '') return null
  try {
    const d = value instanceof Date ? value : new Date(value as string | number)
    return Number.isNaN(d.getTime()) ? null : d
  } catch {
    // 极端输入（如 Symbol、畸形对象）会让 new Date() 直接抛错；
    // 这里必须兜住 —— 各页面历史实现都带 try/catch，收敛后不能比原来更脆。
    return null
  }
}

/** 两位补零 */
const pad2 = (n: number): string => String(n).padStart(2, '0')

/**
 * 按 zh-CN locale 格式化（locale 类函数的公共实现）。
 *
 * 刻意做成**模块级函数**而不是对象方法：对象方法里用 `this` 会在
 * `const { formatLocalDate2Digit } = format` 这种解构调用下丢失 `this`。
 *
 * 双层兜底（与各页面历史实现对齐 —— 收敛后不能比原来更脆）：
 *  ① `toDate` 内部 try/catch：极端输入（Symbol、畸形对象）不抛错；
 *  ② 这里的 try/catch：宿主 locale 能力异常（如 `toLocaleString` 抛错）时回退文案，
 *     保证渲染期不会因为"格式化时间"这个动作把页面搞崩。
 *
 * @param dateOnly true 走 `toLocaleDateString`（仅日期），false 走 `toLocaleString`
 */
function localeFormat(
  value: DateInput,
  options: Intl.DateTimeFormatOptions | undefined,
  fallback: string,
  dateOnly = false
): string {
  const d = toDate(value)
  if (!d) return fallback
  try {
    return dateOnly ? d.toLocaleDateString('zh-CN', options) : d.toLocaleString('zh-CN', options)
  } catch {
    return fallback
  }
}

/** 格式化工具集 —— 全前端唯一的日期/金额格式化入口 */
export const format = {
  /**
   * 格式化日期时间（默认 `YYYY-MM-DD HH:mm:ss`）。
   *
   * @param fmt 格式串，支持 YYYY/MM/DD/HH/mm/ss
   * @param fallback 空值/非法值的兜底文案；**不传**时保持历史行为
   *                 （空值 `-`、非法值原样回显），传了则两者都用兜底文案
   */
  formatDateTime(date?: DateInput, fmt = 'YYYY-MM-DD HH:mm:ss', fallback?: string): string {
    // 守卫与兄弟函数（formatDateTimeLocale/formatDate/formatDateTimeFull）对齐：
    // 原实现遇到 null/undefined 会走 d.getTime() 抛 TypeError（渲染期崩溃）
    if (!date) return fallback ?? '-'
    // 走统一的 toDate：极端输入（Symbol 等）不会抛错；
    // 非法值仍保持历史语义 —— 未传 fallback 时原样回显
    const d = toDate(date)
    if (!d) return fallback ?? String(date)
    const pad = (n: number) => String(n).padStart(2, '0')
    return fmt
      .replace('YYYY', String(d.getFullYear()))
      .replace('MM', pad(d.getMonth() + 1))
      .replace('DD', pad(d.getDate()))
      .replace('HH', pad(d.getHours()))
      .replace('mm', pad(d.getMinutes()))
      .replace('ss', pad(d.getSeconds()))
  },

  /** 格式化日期时间（locale 格式，如 `2026/10/2 20:03:40`） */
  formatDateTimeLocale(date?: DateInput, fallback = '-'): string {
    return localeFormat(date, undefined, fallback)
  },

  /** 格式化日期（仅日期，如 `2026/10/2`） */
  formatLocalDate(date?: DateInput, fallback = '-'): string {
    return localeFormat(date, undefined, fallback, true)
  },

  /** 格式化日期（两位补零，如 `2026/10/02`） */
  formatLocalDate2Digit(date?: DateInput, fallback = '-'): string {
    return localeFormat(date, { year: 'numeric', month: '2-digit', day: '2-digit' }, fallback, true)
  },

  /** 格式化日期时间（两位补零，如 `2026/10/02 20:03:40`） */
  formatLocalDateTime2Digit(date?: DateInput, fallback = '-'): string {
    return localeFormat(
      date,
      {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      },
      fallback
    )
  },

  /** 格式化日期（仅 `YYYY-MM-DD`，本地时区） */
  formatDate(date?: DateInput, fallback = '-'): string {
    if (!date) return fallback
    return format.formatDateTime(date, 'YYYY-MM-DD', fallback)
  },

  /** 格式化日期时间（`YYYY-MM-DD HH:mm:ss`，本地时区） */
  formatDateTimeFull(date?: DateInput, fallback = '-'): string {
    if (!date) return fallback
    return format.formatDateTime(date, 'YYYY-MM-DD HH:mm:ss', fallback)
  },

  /** 中文长日期 + 星期，如 `2026年10月3日 周六` */
  formatCnDate(date?: DateInput, fallback = '-'): string {
    const d = toDate(date)
    if (!d) return fallback
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 周${WEEKDAY_CN[d.getDay()]}`
  },

  /**
   * 相对时间：1 分钟内「刚刚」、1 小时内「N分钟前」、24 小时内「N小时前」、
   * 7 天内「N天前」，更早显示「10月2日 20:03」形态的短日期时间。
   */
  formatRelativeTime(date?: DateInput, fallback = '--:--'): string {
    const d = toDate(date)
    if (!d) return fallback
    const minutes = Math.floor((Date.now() - d.getTime()) / 60000)
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}小时前`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}天前`
    return localeFormat(
      d,
      { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' },
      fallback,
      true
    )
  },

  /** 短日期时间（不补零），如 `10/2 8:05` */
  formatShortDateTime(date?: DateInput, fallback = ''): string {
    const d = toDate(date)
    if (!d) return fallback
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${pad2(d.getMinutes())}`
  },

  /** 短日期时间（补零），如 `10-02 08:05` */
  formatShortDateTimePadded(date?: DateInput, fallback = ''): string {
    const d = toDate(date)
    if (!d) return fallback
    return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  },

  /**
   * 把"已运行的秒数"格式化为中文时长：`N 天 N 小时` / `N 小时 N 分钟` / `N 分钟`。
   *
   * @param sec 秒数；小于等于 0、null、undefined、NaN 时返回 `emptyText`
   * @param emptyText 空值文案（各页面历史上分别用 `-` 与 `未知`，故做成参数）
   */
  formatDuration(sec?: number | null, emptyText = '-'): string {
    if (sec === null || sec === undefined || Number.isNaN(sec) || sec <= 0) return emptyText
    const days = Math.floor(sec / 86400)
    const hours = Math.floor((sec % 86400) / 3600)
    const mins = Math.floor((sec % 3600) / 60)
    if (days > 0) return `${days} 天 ${hours} 小时`
    if (hours > 0) return `${hours} 小时 ${mins} 分钟`
    return `${mins} 分钟`
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
