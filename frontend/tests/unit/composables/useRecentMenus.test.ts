/**
 * useRecentMenus —— 最近访问菜单（localStorage 持久化，上限 8，损坏回退）
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  useRecentMenus,
  resetRecentMenus,
  RECENT_MENUS_STORAGE_KEY,
  RECENT_MENUS_LIMIT,
  type NavMenuRecord,
} from '@/composables/useRecentMenus'

function makeEntry(index: number): NavMenuRecord {
  return {
    key: `menu-${index}`,
    label: `菜单${index}`,
    path: `/menu/${index}`,
    icon: 'Location',
  }
}

describe('useRecentMenus', () => {
  beforeEach(() => {
    localStorage.clear()
    resetRecentMenus()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetRecentMenus()
  })

  it('初始无数据 → 空数组且不写存储', () => {
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value).toEqual([])
    expect(localStorage.getItem(RECENT_MENUS_STORAGE_KEY)).toBeNull()
  })

  it('recordMenu 记录访问并持久化（最新在前）', () => {
    const { recentMenus, recordMenu } = useRecentMenus()
    recordMenu(makeEntry(1))
    recordMenu(makeEntry(2))
    expect(recentMenus.value.map((entry) => entry.key)).toEqual(['menu-2', 'menu-1'])
    const stored = JSON.parse(localStorage.getItem(RECENT_MENUS_STORAGE_KEY) as string)
    expect(stored).toHaveLength(2)
    expect(stored[0].key).toBe('menu-2')
  })

  it('重复访问同一 key 去重置顶', () => {
    const { recentMenus, recordMenu } = useRecentMenus()
    recordMenu(makeEntry(1))
    recordMenu(makeEntry(2))
    recordMenu(makeEntry(1))
    expect(recentMenus.value.map((entry) => entry.key)).toEqual(['menu-1', 'menu-2'])
  })

  it(`超过 ${RECENT_MENUS_LIMIT} 条时截断`, () => {
    const { recentMenus, recordMenu } = useRecentMenus()
    for (let i = 0; i < RECENT_MENUS_LIMIT + 3; i += 1) {
      recordMenu(makeEntry(i))
    }
    expect(recentMenus.value).toHaveLength(RECENT_MENUS_LIMIT)
    expect(recentMenus.value[0].key).toBe(`menu-${RECENT_MENUS_LIMIT + 2}`)
    expect(recentMenus.value[RECENT_MENUS_LIMIT - 1].key).toBe('menu-3')
  })

  it('从已有 localStorage 读取（模块单例首次使用时加载）', () => {
    localStorage.setItem(RECENT_MENUS_STORAGE_KEY, JSON.stringify([makeEntry(1), makeEntry(2)]))
    resetRecentMenus()
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value.map((entry) => entry.key)).toEqual(['menu-1', 'menu-2'])
  })

  it('损坏 JSON 回退空数组', () => {
    localStorage.setItem(RECENT_MENUS_STORAGE_KEY, '{not-json')
    resetRecentMenus()
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value).toEqual([])
  })

  it('非数组结构回退空数组', () => {
    localStorage.setItem(RECENT_MENUS_STORAGE_KEY, JSON.stringify({ key: 'x' }))
    resetRecentMenus()
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value).toEqual([])
  })

  it('脏条目被过滤，读取时同样按上限截断', () => {
    const records: unknown[] = [
      null,
      'x',
      { key: 'only-key' },
      { key: 'a', label: 'A' },
      { key: 'b', label: 'B', path: '/b', icon: 42 },
      ...Array.from({ length: RECENT_MENUS_LIMIT + 2 }, (_, i) => makeEntry(i)),
    ]
    localStorage.setItem(RECENT_MENUS_STORAGE_KEY, JSON.stringify(records))
    resetRecentMenus()
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value).toHaveLength(RECENT_MENUS_LIMIT)
    // 合法条目按原顺序保留（icon 非字符串在运行时不参与校验，原样保留）
    expect(recentMenus.value[0].key).toBe('b')
    expect(recentMenus.value[1].key).toBe('menu-0')
  })

  it('setItem 抛错（配额/隐私模式）时静默降级', () => {
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    const { recentMenus, recordMenu } = useRecentMenus()
    expect(() => recordMenu(makeEntry(1))).not.toThrow()
    expect(recentMenus.value).toHaveLength(1)
    expect(spy).toHaveBeenCalled()
  })

  it('clearRecentMenus 清空内存与存储', () => {
    const { recentMenus, recordMenu, clearRecentMenus } = useRecentMenus()
    recordMenu(makeEntry(1))
    clearRecentMenus()
    expect(recentMenus.value).toEqual([])
    expect(localStorage.getItem(RECENT_MENUS_STORAGE_KEY)).toBe('[]')
  })

  it('模块单例：多个调用方共享同一份数据', () => {
    const first = useRecentMenus()
    const second = useRecentMenus()
    first.recordMenu(makeEntry(1))
    expect(second.recentMenus.value.map((entry) => entry.key)).toEqual(['menu-1'])
  })
})
