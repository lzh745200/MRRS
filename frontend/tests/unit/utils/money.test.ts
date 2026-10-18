/**
 * utils/money.ts 单元测试（四指标 100%）
 *
 * 覆盖：空值判定、formatMoney4 语义复用（千分位/最多 4 位小数/去尾零/非法值）、
 * 单位拼接、人民币大写（0/负数/角分补零/组间补零/大数回落）。
 */
import { describe, it, expect } from 'vitest'
import {
  MONEY_PLACEHOLDER,
  formatMoneyText,
  isMoneyEmpty,
  toChineseUppercase,
} from '@/utils/money'
import { format } from '@/utils'

describe('isMoneyEmpty', () => {
  it('null / undefined / 空白字符串按空值处理', () => {
    expect(isMoneyEmpty(null)).toBe(true)
    expect(isMoneyEmpty(undefined)).toBe(true)
    expect(isMoneyEmpty('')).toBe(true)
    expect(isMoneyEmpty('   ')).toBe(true)
  })

  it('0 / 非空字符串 / NaN 不是空值', () => {
    expect(isMoneyEmpty(0)).toBe(false)
    expect(isMoneyEmpty('0')).toBe(false)
    expect(isMoneyEmpty('1234.5')).toBe(false)
    expect(isMoneyEmpty(Number.NaN)).toBe(false)
  })
})

describe('formatMoneyText（复用 format.formatMoney4 语义）', () => {
  it('空值返回默认占位符', () => {
    expect(MONEY_PLACEHOLDER).toBe('-')
    expect(formatMoneyText(null)).toBe('-')
    expect(formatMoneyText(undefined)).toBe('-')
    expect(formatMoneyText('')).toBe('-')
  })

  it('空值 + 自定义占位符', () => {
    expect(formatMoneyText(null, { placeholder: '暂无' })).toBe('暂无')
  })

  it('数值展示与 format.formatMoney4 完全一致（千分位 / 4 位小数 / 去尾零）', () => {
    const samples: Array<number | string> = [0, 100.5, 1234567.8, -1234.5678, '8888.1234', '0.0001']
    for (const sample of samples) {
      expect(formatMoneyText(sample)).toBe(format.formatMoney4(sample))
    }
    expect(formatMoneyText(1234567.8)).toBe('1,234,567.8')
    expect(formatMoneyText(0)).toBe('0')
    expect(formatMoneyText(-1234.5678)).toBe('-1,234.5678')
  })

  it('非法数值沿用 formatMoney4 的 0 回落（不出现 NaN）', () => {
    expect(formatMoneyText('abc')).toBe('0')
    expect(formatMoneyText('abc')).toBe(format.formatMoney4('abc'))
  })

  it('可选单位拼接；空值时不拼接单位', () => {
    expect(formatMoneyText(1234.5, { unit: '万元' })).toBe('1,234.5万元')
    expect(formatMoneyText(null, { unit: '万元' })).toBe('-')
  })

  it('uppercase 切换人民币大写', () => {
    expect(formatMoneyText(1234.56, { uppercase: true })).toBe('壹仟贰佰叁拾肆元伍角陆分')
    expect(formatMoneyText(1234.5, { uppercase: true, unit: '元' })).toBe(
      '壹仟贰佰叁拾肆元伍角元'
    )
    expect(formatMoneyText(null, { uppercase: true })).toBe('-')
  })
})

describe('toChineseUppercase（人民币大写）', () => {
  it('0 / 非法值 / 超范围回落零元整', () => {
    expect(toChineseUppercase(0)).toBe('零元整')
    expect(toChineseUppercase(null)).toBe('零元整')
    expect(toChineseUppercase('abc')).toBe('零元整')
    expect(toChineseUppercase(1e20)).toBe('零元整')
  })

  it('整数金额以「整」结尾', () => {
    expect(toChineseUppercase(100)).toBe('壹佰元整')
    expect(toChineseUppercase('1234')).toBe('壹仟贰佰叁拾肆元整')
    expect(toChineseUppercase(10001)).toBe('壹万零壹元整')
    expect(toChineseUppercase(1000000)).toBe('壹佰万元整')
    expect(toChineseUppercase(1010)).toBe('壹仟零壹拾元整')
    expect(toChineseUppercase(100010000)).toBe('壹亿零壹万元整')
    expect(toChineseUppercase(100000001)).toBe('壹亿零壹元整')
  })

  it('角分处理：伍角 / 零伍分 / 整', () => {
    expect(toChineseUppercase(0.5)).toBe('零元伍角')
    expect(toChineseUppercase(0.05)).toBe('零元零伍分')
    expect(toChineseUppercase(1.05)).toBe('壹元零伍分')
    expect(toChineseUppercase(1.5)).toBe('壹元伍角')
    expect(toChineseUppercase(100.0)).toBe('壹佰元整')
  })

  it('负数加「负」前缀；四舍五入后为零时不带负号', () => {
    expect(toChineseUppercase(-1234.56)).toBe('负壹仟贰佰叁拾肆元伍角陆分')
    expect(toChineseUppercase(-0.001)).toBe('零元整')
  })

  it('万亿级（京级以下）分组单位', () => {
    // 1e16 = 壹京（仅验证不抛错且不出现 undefined）
    expect(toChineseUppercase(1e16)).toBe('壹京元整')
  })
})
