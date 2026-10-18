/**
 * utils/datetime.ts 具名导出 API 锁定（W5-T10 拆分自 utils/index.ts）。
 *
 * 关键不变量：具名导出与 utils/index.ts 的 `format` 聚合对象**同源同输出**——
 * 拆分只是搬家，任何一条输出的格式串发生变化都会在这里被拦下
 * （迁移视图本地 formatDate 时依赖"输出逐字不变"）。
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import * as dt from '@/utils/datetime'
import { format } from '@/utils'

const CASES: Array<[string, any]> = [
  ['2026-10-02T20:03:40', new Date(2026, 9, 2, 20, 3, 40)],
  ['空值 null', null],
  ['空值 undefined', undefined],
  ['空串', ''],
  ['非法值', 'not-a-date'],
]

describe('utils/datetime 具名导出与 format 聚合对象同源', () => {
  it('日期/时间类函数逐一等价', () => {
    const names = [
      'formatDateTime',
      'formatDateTimeLocale',
      'formatLocalDate',
      'formatLocalDate2Digit',
      'formatLocalDateTime2Digit',
      'formatDate',
      'formatDateTimeFull',
      'formatCnDate',
      'formatShortDateTime',
      'formatShortDateTimePadded',
    ] as const
    for (const name of names) {
      for (const [label, value] of CASES) {
        expect(
          (dt as any)[name](value),
          `${name}(${label}) 具名导出与 format 聚合对象输出必须一致`
        ).toBe((format as any)[name](value))
      }
    }
  })

  it('formatDuration 等价（含空值兜底文案参数）', () => {
    for (const v of [null, undefined, 0, -1, Number.NaN, 59, 3600, 90061]) {
      expect(dt.formatDuration(v)).toBe(format.formatDuration(v))
      expect(dt.formatDuration(v, '未知')).toBe(format.formatDuration(v, '未知'))
    }
  })

  it('toDate：合法输入返回 Date、空值/非法值返回 null、异常输入不抛错', () => {
    expect(dt.toDate(new Date(2026, 0, 1))?.getFullYear()).toBe(2026)
    expect(dt.toDate('2026-01-01')?.getFullYear()).toBe(2026)
    expect(dt.toDate(1767225600000)?.getTime()).toBe(1767225600000)
    expect(dt.toDate(null)).toBeNull()
    expect(dt.toDate(undefined)).toBeNull()
    expect(dt.toDate('')).toBeNull()
    expect(dt.toDate('nope')).toBeNull()
    // Symbol 会让 new Date() 抛 TypeError，toDate 必须兜住
    expect(dt.toDate(Symbol('x') as any)).toBeNull()
  })
})

describe('formatRelativeTime 相对时间分档（拆分后行为不变）', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('刚刚 / 分钟 / 小时 / 天 / 更早短日期时间', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 2, 20, 0, 0))
    expect(dt.formatRelativeTime(new Date(2026, 9, 2, 19, 59, 30))).toBe('刚刚')
    expect(dt.formatRelativeTime(new Date(2026, 9, 2, 19, 30, 0))).toBe('30分钟前')
    expect(dt.formatRelativeTime(new Date(2026, 9, 2, 15, 0, 0))).toBe('5小时前')
    expect(dt.formatRelativeTime(new Date(2026, 8, 30, 20, 0, 0))).toBe('2天前')
    // ≥7 天 → locale 短日期时间
    expect(dt.formatRelativeTime(new Date(2026, 7, 1, 8, 5, 0))).not.toBe('--:--')
    expect(dt.formatRelativeTime(null)).toBe('--:--')
    expect(dt.formatRelativeTime(null, '无')).toBe('无')
  })
})
