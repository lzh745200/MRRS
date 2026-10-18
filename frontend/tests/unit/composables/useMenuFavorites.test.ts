/**
 * useMenuFavorites —— 菜单收藏（localStorage 持久化，上限 8，损坏回退）
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  useMenuFavorites,
  resetMenuFavorites,
  MENU_FAVORITES_STORAGE_KEY,
  MENU_FAVORITES_LIMIT,
} from '@/composables/useMenuFavorites'
import type { NavMenuRecord } from '@/composables/useRecentMenus'

function makeEntry(index: number): NavMenuRecord {
  return {
    key: `menu-${index}`,
    label: `菜单${index}`,
    path: `/menu/${index}`,
    icon: 'Location',
  }
}

describe('useMenuFavorites', () => {
  beforeEach(() => {
    localStorage.clear()
    resetMenuFavorites()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetMenuFavorites()
  })

  it('初始无数据 → 空收藏且不写存储', () => {
    const { favorites } = useMenuFavorites()
    expect(favorites.value).toEqual([])
    expect(localStorage.getItem(MENU_FAVORITES_STORAGE_KEY)).toBeNull()
  })

  it('toggleFavorite 添加收藏并返回 true，再次切换移除并返回 false', () => {
    const { favorites, isFavorite, toggleFavorite } = useMenuFavorites()
    expect(toggleFavorite(makeEntry(1))).toBe(true)
    expect(isFavorite('menu-1')).toBe(true)
    expect(favorites.value.map((entry) => entry.key)).toEqual(['menu-1'])
    expect(localStorage.getItem(MENU_FAVORITES_STORAGE_KEY)).toContain('menu-1')

    expect(toggleFavorite(makeEntry(1))).toBe(false)
    expect(isFavorite('menu-1')).toBe(false)
    expect(favorites.value).toEqual([])
  })

  it('新收藏置顶，超过上限截断', () => {
    const { favorites, toggleFavorite } = useMenuFavorites()
    for (let i = 0; i < MENU_FAVORITES_LIMIT + 2; i += 1) {
      toggleFavorite(makeEntry(i))
    }
    expect(favorites.value).toHaveLength(MENU_FAVORITES_LIMIT)
    expect(favorites.value[0].key).toBe(`menu-${MENU_FAVORITES_LIMIT + 1}`)
    expect(favorites.value[MENU_FAVORITES_LIMIT - 1].key).toBe('menu-2')
  })

  it('从已有 localStorage 读取（模块单例首次使用时加载）', () => {
    localStorage.setItem(MENU_FAVORITES_STORAGE_KEY, JSON.stringify([makeEntry(1), makeEntry(2)]))
    resetMenuFavorites()
    const { favorites } = useMenuFavorites()
    expect(favorites.value.map((entry) => entry.key)).toEqual(['menu-1', 'menu-2'])
  })

  it('损坏 JSON 回退空数组', () => {
    localStorage.setItem(MENU_FAVORITES_STORAGE_KEY, 'not-json')
    resetMenuFavorites()
    const { favorites } = useMenuFavorites()
    expect(favorites.value).toEqual([])
  })

  it('非数组结构回退空数组', () => {
    localStorage.setItem(MENU_FAVORITES_STORAGE_KEY, JSON.stringify('nope'))
    resetMenuFavorites()
    const { favorites } = useMenuFavorites()
    expect(favorites.value).toEqual([])
  })

  it('脏条目被过滤，读取时同样按上限截断', () => {
    const records: unknown[] = [
      null,
      42,
      { key: 'only-key' },
      { key: 'a', label: 'A' },
      { key: 'b', label: 'B', path: '/b' },
      ...Array.from({ length: MENU_FAVORITES_LIMIT }, (_, i) => makeEntry(i)),
    ]
    localStorage.setItem(MENU_FAVORITES_STORAGE_KEY, JSON.stringify(records))
    resetMenuFavorites()
    const { favorites } = useMenuFavorites()
    expect(favorites.value).toHaveLength(MENU_FAVORITES_LIMIT)
    expect(favorites.value[0].key).toBe('b')
  })

  it('setItem 抛错时静默降级（内存态仍可用）', () => {
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    const { favorites, toggleFavorite } = useMenuFavorites()
    expect(() => toggleFavorite(makeEntry(1))).not.toThrow()
    expect(favorites.value).toHaveLength(1)
    expect(spy).toHaveBeenCalled()
  })

  it('removeFavorite 移除指定收藏，不存在时无副作用', () => {
    const { favorites, toggleFavorite, removeFavorite } = useMenuFavorites()
    toggleFavorite(makeEntry(1))
    toggleFavorite(makeEntry(2))
    removeFavorite('menu-1')
    expect(favorites.value.map((entry) => entry.key)).toEqual(['menu-2'])
    removeFavorite('not-exists')
    expect(favorites.value.map((entry) => entry.key)).toEqual(['menu-2'])
  })

  it('clearFavorites 清空内存与存储', () => {
    const { favorites, toggleFavorite, clearFavorites } = useMenuFavorites()
    toggleFavorite(makeEntry(1))
    clearFavorites()
    expect(favorites.value).toEqual([])
    expect(localStorage.getItem(MENU_FAVORITES_STORAGE_KEY)).toBe('[]')
  })

  it('模块单例：侧栏与搜索弹窗共享同一份收藏', () => {
    const first = useMenuFavorites()
    const second = useMenuFavorites()
    first.toggleFavorite(makeEntry(1))
    expect(second.isFavorite('menu-1')).toBe(true)
  })
})
