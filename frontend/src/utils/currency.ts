/**
 * 金额格式化 —— 全前端唯一的金额格式化入口（W5-T10 从 utils/index.ts 拆出）。
 *
 * 语义与历史实现逐字对齐（收敛不得改变页面数值/视觉）：
 * 千分位、最多 4 位小数、自动去尾零；非法值回落占位符而非渲染 `NaN`。
 * 更"重"的金额展示（大写人民币、单位后缀、空值占位）见 `utils/money.ts`。
 */

/** 格式化货币（最多4位小数，自动去尾零） */
export function formatCurrency(value: number | string | null | undefined, unit = '元'): string {
  // 原实现直接 value.toLocaleString()：null/undefined 抛 TypeError，NaN 渲染成 'NaN'
  if (value === null || value === undefined || value === '') return '-'
  const n = Number(value)
  if (!Number.isFinite(n)) return '-'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 4 }) + unit
}

/** 格式化金额(万元)：最多4位小数、千分位、自动去尾零 */
export function formatMoney4(value: number | string | null | undefined): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}
