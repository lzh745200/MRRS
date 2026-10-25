import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  SYNC_STALE_DAYS,
  computeLevel,
  formatRelative,
  pickLatest,
  summarize,
  useSyncStatus,
} from '@/composables/useSyncStatus'

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

const NOW = Date.parse('2026-10-25T12:00:00+08:00')

function log(action: string, iso: string, extra: Record<string, unknown> = {}) {
  return { id: `l-${action}-${iso}`, action, status: 'success', created_at: iso, ...extra }
}

const { getSyncLogsMock } = vi.hoisted(() => ({ getSyncLogsMock: vi.fn() }))
vi.mock('@/api/dataSync', () => ({ getSyncLogs: getSyncLogsMock }))

beforeEach(() => {
  getSyncLogsMock.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('formatRelative', () => {
  it('从未同步', () => {
    expect(formatRelative(NOW, null)).toBe('从未同步')
  })

  it('分档：刚刚 / 分钟 / 小时 / 天', () => {
    expect(formatRelative(NOW, NOW - 30_000)).toBe('刚刚')
    expect(formatRelative(NOW, NOW - 5 * MINUTE)).toBe('5 分钟前')
    expect(formatRelative(NOW, NOW - 3 * HOUR)).toBe('3 小时前')
    expect(formatRelative(NOW, NOW - 9 * DAY)).toBe('9 天前')
  })

  it('未来时间按 0 处理（时钟漂移不出现"-3 分钟前"）', () => {
    expect(formatRelative(NOW, NOW + 5 * MINUTE)).toBe('刚刚')
  })
})

describe('computeLevel', () => {
  it('未同步 → unknown', () => {
    expect(computeLevel(NOW, null)).toBe('unknown')
  })

  it('<1 天 ok、<7 天 warn、≥7 天 stale', () => {
    expect(computeLevel(NOW, NOW - 2 * HOUR)).toBe('ok')
    expect(computeLevel(NOW, NOW - 2 * DAY)).toBe('warn')
    expect(computeLevel(NOW, NOW - SYNC_STALE_DAYS * DAY)).toBe('stale')
    expect(computeLevel(NOW, NOW - 30 * DAY)).toBe('stale')
  })

  it('自定义阈值生效', () => {
    expect(computeLevel(NOW, NOW - 2 * DAY, 1)).toBe('stale')
  })
})

describe('pickLatest / summarize', () => {
  it('取最近一条（按 created_at 而非数组顺序）', () => {
    const logs = [
      log('import', '2026-10-20T08:00:00+08:00'),
      log('export', '2026-10-24T08:00:00+08:00'),
      log('import', '2026-10-22T08:00:00+08:00'),
    ]
    expect(pickLatest(logs)?.action).toBe('export')
  })

  it('跳过 created_at 非法的脏记录', () => {
    const logs = [log('import', 'not-a-date'), log('export', '2026-10-23T08:00:00+08:00')]
    expect(pickLatest(logs)?.action).toBe('export')
  })

  it('容错空记录/缺字段（不因一条脏数据整表失效）', () => {
    const dirty = [null, undefined, { id: 'x' }, log('sync', '2026-10-24T08:00:00+08:00')]
    expect(pickLatest(dirty as never)?.action).toBe('sync')
  })

  it('空列表 → unknown 汇总', () => {
    expect(summarize([], NOW)).toEqual({
      lastAction: null,
      lastAt: null,
      relativeLabel: '从未同步',
      level: 'unknown',
    })
  })

  it('正常汇总出四个字段', () => {
    const summary = summarize([log('import', '2026-10-25T09:00:00+08:00')], NOW)
    expect(summary.lastAction).toBe('import')
    expect(summary.relativeLabel).toBe('3 小时前')
    expect(summary.level).toBe('ok')
  })
})

describe('useSyncStatus', () => {
  it('refresh 拉取日志并算出汇总（数组形态）', async () => {
    getSyncLogsMock.mockResolvedValue([log('export', '2026-10-24T08:00:00+08:00')])
    const { logs, summary, loading, refresh } = useSyncStatus({ now: () => NOW })

    const pending = refresh()
    expect(loading.value).toBe(true)
    await pending

    expect(logs.value).toHaveLength(1)
    expect(summary.value.lastAction).toBe('export')
    expect(loading.value).toBe(false)
    expect(getSyncLogsMock).toHaveBeenCalledWith({ page: 1, page_size: 5 })
  })

  it('兼容 {items} / {list} / {data} 包裹形态', async () => {
    for (const box of ['items', 'list', 'data', 'records'] as const) {
      getSyncLogsMock.mockResolvedValue({ [box]: [log('import', '2026-10-25T10:00:00+08:00')] })
      const { logs, refresh } = useSyncStatus({ now: () => NOW })
      await refresh()
      expect(logs.value).toHaveLength(1)
    }
  })

  it('无法识别的载荷 → 空列表（不抛错）', async () => {
    getSyncLogsMock.mockResolvedValue({ unexpected: true })
    const { logs, refresh } = useSyncStatus({ now: () => NOW })
    await refresh()
    expect(logs.value).toEqual([])
  })

  it('接口失败 → 静默降级为未知态并记录原因（顶栏不弹错）', async () => {
    getSyncLogsMock.mockRejectedValue(new Error('网络不可达'))
    const { logs, error, summary, refresh } = useSyncStatus({ now: () => NOW })
    await refresh()
    expect(logs.value).toEqual([])
    expect(error.value).toBe('网络不可达')
    expect(summary.value.level).toBe('unknown')
  })

  it('非 Error 抛出也给出可读原因', async () => {
    getSyncLogsMock.mockRejectedValue('boom')
    const { error, refresh } = useSyncStatus({ now: () => NOW })
    await refresh()
    expect(error.value).toBe('同步日志加载失败')
  })

  it('openDrawer 打开抽屉并自动刷新；closeDrawer 关闭', async () => {
    getSyncLogsMock.mockResolvedValue([])
    const { drawerVisible, openDrawer, closeDrawer } = useSyncStatus({ now: () => NOW })

    openDrawer()
    expect(drawerVisible.value).toBe(true)
    await Promise.resolve()
    expect(getSyncLogsMock).toHaveBeenCalledTimes(1)

    closeDrawer()
    expect(drawerVisible.value).toBe(false)
  })

  it('pageSize 可配置', async () => {
    getSyncLogsMock.mockResolvedValue([])
    const { refresh } = useSyncStatus({ pageSize: 20, now: () => NOW })
    await refresh()
    expect(getSyncLogsMock).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('无参调用走默认值（pageSize=5、now=Date.now）', async () => {
    getSyncLogsMock.mockResolvedValue([log('export', new Date().toISOString())])
    const { logs, summary, refresh } = useSyncStatus()
    await refresh()
    expect(getSyncLogsMock).toHaveBeenCalledWith({ page: 1, page_size: 5 })
    expect(logs.value).toHaveLength(1)
    // 用真实当前时间 → 刚写入的记录应落在 ok 档
    expect(summary.value.level).toBe('ok')
  })
})
