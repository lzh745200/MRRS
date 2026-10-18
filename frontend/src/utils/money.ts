/**
 * 金额展示工具 —— MoneyText 组件的纯逻辑层。
 *
 * 常规金额展示复用 `utils/index.ts` 的 `format.formatMoney4` 语义
 * （千分位、最多 4 位小数、自动去尾零、非法值回落 '0'），保证与存量页面
 * **数值与视觉完全一致**；本模块只补足组件需要的三件事：
 * 空值占位判定、可选单位拼接、人民币大写转换。
 */
import { format } from './index'

/** 空值占位符（与 `format.formatCurrency` 等存量实现保持一致的 `-`） */
export const MONEY_PLACEHOLDER = '-'

/** MoneyText 展示选项 */
export interface MoneyTextOptions {
  /** 数值单位后缀（如 `万元`） */
  unit?: string
  /** 空值占位文案，默认 `-` */
  placeholder?: string
  /** 是否展示人民币大写（大写文本自带「元/角/分」单位，调用方通常不再传 unit） */
  uppercase?: boolean
}

/** 金额是否为空：null / undefined / 空白字符串都按空值处理 */
export function isMoneyEmpty(value: number | string | null | undefined): boolean {
  return value === null || value === undefined || (typeof value === 'string' && value.trim() === '')
}

const CN_DIGITS = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖'] as const
const CN_SMALL_UNITS = ['', '拾', '佰', '仟'] as const
const CN_GROUP_UNITS = ['', '万', '亿', '万亿', '京'] as const

/** 万以内数字段 → 大写（不处理前导零，由调用方补「零」） */
function groupToChinese(group: number): string {
  let text = ''
  let pendingZero = false
  for (let pos = 3; pos >= 0; pos--) {
    const digit = Math.floor(group / 10 ** pos) % 10
    if (digit === 0) {
      if (text) pendingZero = true
      continue
    }
    if (pendingZero) {
      text += '零'
      pendingZero = false
    }
    text += CN_DIGITS[digit] + CN_SMALL_UNITS[pos]
  }
  return text
}

/** 整数部分 → 大写（按 万/亿/万亿 分组，组间缺位补「零」） */
function integerToChinese(integer: number): string {
  if (integer === 0) return '零'
  const groups: number[] = []
  let rest = integer
  while (rest > 0) {
    groups.push(rest % 10000)
    rest = Math.floor(rest / 10000)
  }
  let text = ''
  for (let i = groups.length - 1; i >= 0; i--) {
    const group = groups[i]
    if (group === 0) {
      if (text && !text.endsWith('零')) text += '零'
      continue
    }
    // 上一组已输出且当前组不足四位（千位缺位）→ 补「零」（已补过则不重复）
    if (text && !text.endsWith('零') && group < 1000) text += '零'
    text += groupToChinese(group) + CN_GROUP_UNITS[i]
  }
  return text.replace(/零+$/, '')
}

/**
 * 人民币大写（金额单位：元）。
 *
 * - 保留 2 位小数（角/分），四舍五入到分；
 * - 无角分时以「整」结尾；整数部分为 0 时按「零元…」输出；
 * - 非法/不可解析的值按 0 处理，返回「零元整」，绝不抛错；
 * - 超出「京」级（≥1e20 元）不具现实意义，同样回落「零元整」。
 */
export function toChineseUppercase(value: number | string | null | undefined): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n) || Math.abs(n) >= 1e20) return '零元整'
  const cents = Math.round(Math.abs(n) * 100)
  const negative = n < 0 && cents > 0
  const integer = Math.floor(cents / 100)
  const jiao = Math.floor((cents % 100) / 10)
  const fen = cents % 10
  let text = `${integerToChinese(integer)}元`
  if (jiao === 0 && fen === 0) {
    text += '整'
  } else {
    if (jiao > 0) text += `${CN_DIGITS[jiao]}角`
    if (jiao === 0 && fen > 0) text += '零'
    if (fen > 0) text += `${CN_DIGITS[fen]}分`
  }
  return negative ? `负${text}` : text
}

/**
 * 组件统一入口：空值 → 占位符；否则复用 `format.formatMoney4`
 * （大写模式走 `toChineseUppercase`），最后按需拼接单位后缀。
 */
export function formatMoneyText(
  value: number | string | null | undefined,
  options: MoneyTextOptions = {}
): string {
  const { unit = '', placeholder = MONEY_PLACEHOLDER, uppercase = false } = options
  if (isMoneyEmpty(value)) return placeholder
  const text = uppercase ? toChineseUppercase(value) : format.formatMoney4(value)
  return unit ? `${text}${unit}` : text
}
