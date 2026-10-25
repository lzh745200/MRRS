import { describe, expect, it } from 'vitest'

import {
  OCR_HIGH_CONFIDENCE,
  OCR_LOW_CONFIDENCE,
  buildOcrSuggestions,
  classifyConfidence,
  normalizeOcrAmount,
  normalizeOcrDate,
} from '@/utils/ocrSuggestion'

describe('classifyConfidence', () => {
  it('三分档：高 ≥0.85、中 ≥0.6、低', () => {
    expect(classifyConfidence(0.95)).toBe('high')
    expect(classifyConfidence(OCR_HIGH_CONFIDENCE)).toBe('high')
    expect(classifyConfidence(0.7)).toBe('medium')
    expect(classifyConfidence(OCR_LOW_CONFIDENCE)).toBe('medium')
    expect(classifyConfidence(0.2)).toBe('low')
  })

  it('缺失/非数值一律按最低档（宁可让人核对）', () => {
    expect(classifyConfidence(null)).toBe('low')
    expect(classifyConfidence(undefined)).toBe('low')
    expect(classifyConfidence(Number.NaN)).toBe('low')
  })
})

describe('normalizeOcrAmount', () => {
  it('数字直接转字符串', () => {
    expect(normalizeOcrAmount(12.5)).toBe('12.5')
  })

  it('去掉千分位、货币符号与单位', () => {
    expect(normalizeOcrAmount('¥1,234.50元')).toBe('1234.50')
    expect(normalizeOcrAmount('１２'.replace(/[０-９]/g, ''))).toBe('')
  })

  it('取第一个数字串', () => {
    expect(normalizeOcrAmount('金额：3000 元整')).toBe('3000')
  })

  it('无数字/空值 → 空串', () => {
    expect(normalizeOcrAmount('无')).toBe('')
    expect(normalizeOcrAmount(null)).toBe('')
    expect(normalizeOcrAmount(undefined)).toBe('')
  })
})

describe('normalizeOcrDate', () => {
  it('标准与中文日期都归一成 YYYY-MM-DD', () => {
    expect(normalizeOcrDate('2024-01-02')).toBe('2024-01-02')
    expect(normalizeOcrDate('2024/1/2')).toBe('2024-01-02')
    expect(normalizeOcrDate('2024年1月2日')).toBe('2024-01-02')
  })

  it('月份/日期补零', () => {
    expect(normalizeOcrDate('2024-9-8')).toBe('2024-09-08')
  })

  it('非法月份/日期 → 空串', () => {
    expect(normalizeOcrDate('2024-13-01')).toBe('')
    expect(normalizeOcrDate('2024-01-45')).toBe('')
  })

  it('无法解析/空值 → 空串', () => {
    expect(normalizeOcrDate('无日期')).toBe('')
    expect(normalizeOcrDate(null)).toBe('')
  })
})

describe('buildOcrSuggestions', () => {
  const targets = [
    { key: 'amount', label: '金额', source: 'amount' as const },
    { key: 'transfer_date', label: '划转日期', source: 'date' as const },
  ]

  it('识别出值的字段才出现（不出现整列 —）', () => {
    const out = buildOcrSuggestions({ amount: '100', confidence: 0.9 }, {}, targets)
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ key: 'amount', recognized: '100', level: 'high', same: false })
  })

  it('与当前值相同时 same=true（无需采纳）', () => {
    const out = buildOcrSuggestions(
      { amount: 100, date: '2024-01-02', confidence: 0.9 },
      { amount: '100', transfer_date: '2024-01-02' },
      targets
    )
    expect(out.every((item) => item.same)).toBe(true)
  })

  it('置信度低时全部建议标 low', () => {
    const out = buildOcrSuggestions({ amount: 1, date: '2024-01-02', confidence: 0.3 }, {}, targets)
    expect(out.map((item) => item.level)).toEqual(['low', 'low'])
  })

  it('无识别结果 → 空数组', () => {
    expect(buildOcrSuggestions({}, {}, targets)).toEqual([])
  })
})
