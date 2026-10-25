import { describe, expect, it } from 'vitest'

import { actionLabel, formatLogTime, toDrawerRows } from '@/utils/syncLogFormat'

describe('actionLabel', () => {
  it('已知动作码翻译成中文', () => {
    expect(actionLabel('import')).toBe('导入')
    expect(actionLabel('export')).toBe('导出')
    expect(actionLabel('sync')).toBe('同步')
    expect(actionLabel('upload')).toBe('上传')
    expect(actionLabel('download')).toBe('下载')
  })

  it('未知动作码原样返回（便于按码排查）', () => {
    expect(actionLabel('reconcile')).toBe('reconcile')
  })

  it('空值 / null / undefined → 未知动作', () => {
    expect(actionLabel('')).toBe('未知动作')
    expect(actionLabel(null)).toBe('未知动作')
    expect(actionLabel(undefined)).toBe('未知动作')
  })
})

describe('formatLogTime', () => {
  it('合法 ISO → 本地时间字符串（不含 Invalid Date）', () => {
    const text = formatLogTime('2026-10-25T10:30:00+08:00')
    expect(text).not.toContain('Invalid')
    expect(text).toContain('2026')
  })

  it('非法/缺失 → —', () => {
    expect(formatLogTime('not-a-date')).toBe('—')
    expect(formatLogTime(null)).toBe('—')
    expect(formatLogTime(undefined)).toBe('—')
  })
})

describe('toDrawerRows', () => {
  it('映射成表格行并补默认占位', () => {
    const rows = toDrawerRows([
      { id: '1', action: 'import', status: 'success', created_at: '2026-10-25T10:00:00+08:00' },
      { id: '2', action: 'export', status: '', created_at: 'bad' },
    ])
    expect(rows).toHaveLength(2)
    expect(rows[0].action).toBe('导入')
    expect(rows[1].action).toBe('导出')
    expect(rows[1].time).toBe('—')
    expect(rows[1].status).toBe('—')
    expect(rows[1].message).toBe('—')
  })

  it('空列表 → 空行', () => {
    expect(toDrawerRows([])).toEqual([])
  })

  it('容错脏记录（null 元素不炸）', () => {
    const rows = toDrawerRows([null as never])
    expect(rows[0]).toEqual({ time: '—', action: '未知动作', status: '—', message: '—' })
  })
})
