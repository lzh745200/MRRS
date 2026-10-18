/**
 * utils/currency.ts 具名导出 API 锁定（W5-T10 拆分自 utils/index.ts）。
 *
 * 关键不变量：具名导出与 `format` 聚合对象**同源同输出**——迁移视图本地
 * formatMoney 时依赖"数值与视觉逐字不变"。
 */
import { describe, it, expect } from 'vitest'
import { formatCurrency, formatMoney4 } from '@/utils/currency'
import { format } from '@/utils'

describe('utils/currency 具名导出与 format 聚合对象同源', () => {
  it('formatCurrency 等价（含单位与非法值）', () => {
    const cases: Array<[string, any]> = [
      ['整数', 1234],
      ['小数', 1234.56789],
      ['字符串数字', '9876.5'],
      ['零', 0],
      ['负数', -12.5],
      ['null', null],
      ['undefined', undefined],
      ['空串', ''],
      ['NaN', Number.NaN],
      ['Infinity', Number.POSITIVE_INFINITY],
    ]
    for (const [label, value] of cases) {
      expect(formatCurrency(value), `formatCurrency(${label})`).toBe(format.formatCurrency(value))
      expect(formatCurrency(value, '万元'), `formatCurrency(${label}, 万元)`).toBe(
        format.formatCurrency(value, '万元')
      )
    }
    expect(formatCurrency(null)).toBe('-')
    expect(formatCurrency(1234)).toBe('1,234元')
    expect(formatCurrency(1234.5, '万元')).toBe('1,234.5万元')
  })

  it('formatMoney4 等价（null/非法值回落 "0"）', () => {
    const cases: Array<[string, any]> = [
      ['整数', 1234],
      ['小数', 1234.56789],
      ['字符串数字', '9876.5'],
      ['零', 0],
      ['负数', -12.5],
      ['null', null],
      ['undefined', undefined],
      ['NaN', Number.NaN],
      ['Infinity', Number.POSITIVE_INFINITY],
    ]
    for (const [label, value] of cases) {
      expect(formatMoney4(value), `formatMoney4(${label})`).toBe(format.formatMoney4(value))
    }
    expect(formatMoney4(null)).toBe('0')
    expect(formatMoney4(Number.NaN)).toBe('0')
    expect(formatMoney4(1234.56789)).toBe('1,234.5679')
  })
})
