/**
 * 工具函数统一导出
 *
 * 日期/时间与金额格式化自 W5-T10 起拆分为独立模块（`utils/datetime.ts`、
 * `utils/currency.ts`）——那是**唯一实现**所在；本文件保留 `format` 聚合对象
 * 只是为兼容历史调用方（`format.formatDate(...)`），不承载任何格式化逻辑。
 */

export { logger } from './logger'
export { default as request } from '@/api/request'
export { exportUtil } from './exportUtil'
export { copyToClipboard } from './clipboard'
export { getYearOptions, DEFAULT_START_YEAR, FUTURE_YEAR_SPAN } from './yearOptions'
export type { YearOptionsConfig } from './yearOptions'

// 具名导出：新代码直接 `import { formatDate } from '@/utils/datetime'`
export type { DateInput } from './datetime'
export {
  toDate,
  formatDateTime,
  formatDateTimeLocale,
  formatLocalDate,
  formatLocalDate2Digit,
  formatLocalDateTime2Digit,
  formatDate,
  formatDateTimeFull,
  formatCnDate,
  formatRelativeTime,
  formatShortDateTime,
  formatShortDateTimePadded,
  formatDuration,
} from './datetime'
export { formatCurrency, formatMoney4 } from './currency'

import * as datetime from './datetime'
import * as currency from './currency'

/** 格式化工具集（历史聚合入口，实现见 datetime.ts / currency.ts） */
export const format = {
  ...datetime,
  ...currency,
}
