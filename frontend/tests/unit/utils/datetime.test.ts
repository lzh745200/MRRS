import { describe, it, expect } from 'vitest'
import {
  formatDate,
  formatDateTime,
  formatDateTimeSec,
  formatCnDate,
  monthKey,
  fileTimestamp,
  DATE,
  DATETIME,
  DATETIME_SEC,
  CN_DATE,
  MONTH,
  FILESAFE,
} from '@/utils/datetime'

describe('utils/datetime 统一格式化', () => {
  it('8 个具名格式常量', () => {
    expect(DATE).toBe('YYYY-MM-DD')
    expect(DATETIME).toBe('YYYY-MM-DD HH:mm')
    expect(DATETIME_SEC).toBe('YYYY-MM-DD HH:mm:ss')
    expect(CN_DATE).toBe('YYYY年M月D日')
    expect(MONTH).toBe('YYYY-MM')
    expect(FILESAFE).toBe('YYYYMMDD_HHmmss')
  })

  it('formatDate 默认日期格式', () => {
    expect(formatDate('2026-08-25T14:30:05Z')).toMatch(/^2026-08-25$/)
    expect(formatDate(new Date(2026, 7, 25))).toBe('2026-08-25')
    expect(formatDate(1756000000000)).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('空值/无效值返回空串而非 Invalid Date', () => {
    expect(formatDate(null)).toBe('')
    expect(formatDate(undefined)).toBe('')
    expect(formatDate('')).toBe('')
    expect(formatDate('not-a-date')).toBe('')
    expect(formatDateTime(null)).toBe('')
  })

  it('formatDateTime / formatDateTimeSec', () => {
    const v = new Date(2026, 7, 25, 14, 30, 5)
    expect(formatDateTime(v)).toBe('2026-08-25 14:30')
    expect(formatDateTimeSec(v)).toBe('2026-08-25 14:30:05')
  })

  it('formatCnDate 中文正式文本', () => {
    expect(formatCnDate(new Date(2026, 7, 25))).toBe('2026年8月25日')
  })

  it('monthKey 月度分组键', () => {
    expect(monthKey(new Date(2026, 7, 25))).toBe('2026-08')
  })

  it('fileTimestamp 导出文件名安全（无冒号等非法字符）', () => {
    const ts = fileTimestamp(new Date(2026, 7, 25, 14, 30, 5))
    expect(ts).toBe('20260825_143005')
    expect(ts).not.toMatch(/[:/]/)
  })
})
