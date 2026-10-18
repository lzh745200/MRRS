/**
 * composables/useFilterMemory.ts 单元测试（四指标 100%）
 *
 * 覆盖：按路由 path 生成 key、load/save/clear/apply、
 * JSON 解析失败 / 非对象脏数据 / 存储抛错 / 配额或序列化失败等全部兜底分支，
 * 以及「只回填目标已有字段」的防原型污染语义。
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import {
  FILTER_MEMORY_PREFIX,
  buildFilterMemoryKey,
  useFilterMemory,
  type FilterMemory,
} from '@/composables/useFilterMemory'

interface Filters {
  keyword: string
  status: string
  page: number
}

/** 可注入的假 Storage（真实落到普通对象上，便于断言） */
function createStorage() {
  const map = new Map<string, string>()
  return {
    map,
    getItem: vi.fn((key: string) => map.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      map.set(key, String(value))
    }),
    removeItem: vi.fn((key: string) => {
      map.delete(key)
    }),
  } as unknown as Storage & { map: Map<string, string> }
}

/** 每一步都抛错的 Storage（模拟隐私模式/存储不可用） */
const brokenStorage = {
  getItem: () => {
    throw new Error('storage denied')
  },
  setItem: () => {
    throw new Error('quota exceeded')
  },
  removeItem: () => {
    throw new Error('storage denied')
  },
} as unknown as Storage

function defaults(): Filters {
  return { keyword: '', status: '', page: 1 }
}

describe('buildFilterMemoryKey', () => {
  it('按路由 path 拼接前缀；无 path 时回落 unknown', () => {
    expect(FILTER_MEMORY_PREFIX).toBe('filter_memory:')
    expect(buildFilterMemoryKey('/funds')).toBe('filter_memory:/funds')
    expect(buildFilterMemoryKey('/supported-villages')).toBe('filter_memory:/supported-villages')
    expect(buildFilterMemoryKey(undefined)).toBe('filter_memory:unknown')
    expect(buildFilterMemoryKey(null)).toBe('filter_memory:unknown')
    expect(buildFilterMemoryKey('')).toBe('filter_memory:unknown')
  })
})

describe('useFilterMemory：显式 key + 注入 storage', () => {
  it('save → load 往返；key 带前缀', () => {
    const storage = createStorage()
    const memory = useFilterMemory<Filters>({ key: '/funds', storage })
    expect(memory.key).toBe('filter_memory:/funds')
    expect(memory.load()).toBeNull()

    memory.save({ keyword: '产业', status: 'pending', page: 2 })
    expect(storage.setItem).toHaveBeenCalledWith(
      'filter_memory:/funds',
      JSON.stringify({ keyword: '产业', status: 'pending', page: 2 })
    )
    expect(memory.load()).toEqual({ keyword: '产业', status: 'pending', page: 2 })
  })

  it('clear 清除记录', () => {
    const storage = createStorage()
    const memory = useFilterMemory<Filters>({ key: 'funds', storage })
    memory.save({ keyword: 'x', status: '', page: 1 })
    memory.clear()
    expect(storage.removeItem).toHaveBeenCalledWith('filter_memory:funds')
    expect(memory.load()).toBeNull()
  })

  it('load：空字符串 / JSON 解析失败 / null / 数组 / 标量 均兜底 null 且清除脏数据', () => {
    const storage = createStorage()
    const memory = useFilterMemory<Filters>({ key: 'k', storage })

    storage.map.set('filter_memory:k', '')
    expect(memory.load()).toBeNull()

    storage.map.set('filter_memory:k', '{broken json')
    expect(memory.load()).toBeNull()
    expect(storage.removeItem).toHaveBeenCalledWith('filter_memory:k')

    storage.map.set('filter_memory:k', 'null')
    expect(memory.load()).toBeNull()

    storage.map.set('filter_memory:k', '[1,2]')
    expect(memory.load()).toBeNull()

    storage.map.set('filter_memory:k', '123')
    expect(memory.load()).toBeNull()

    storage.map.set('filter_memory:k', '"str"')
    expect(memory.load()).toBeNull()
  })

  it('getItem 抛错 → load 返回 null（不抛给页面）', () => {
    const memory = useFilterMemory<Filters>({ key: 'k', storage: brokenStorage })
    expect(memory.load()).toBeNull()
  })

  it('setItem 抛错 → save 静默降级', () => {
    const memory = useFilterMemory<Filters>({ key: 'k', storage: brokenStorage })
    expect(() => memory.save(defaults())).not.toThrow()
  })

  it('JSON.stringify 失败（循环引用）→ save 静默降级', () => {
    const storage = createStorage()
    const memory = useFilterMemory<Record<string, any>>({ key: 'k', storage })
    const circular: Record<string, any> = {}
    circular.self = circular
    expect(() => memory.save(circular)).not.toThrow()
    expect(storage.setItem).not.toHaveBeenCalled()
  })

  it('removeItem 抛错 → clear 静默降级', () => {
    const memory = useFilterMemory<Filters>({ key: 'k', storage: brokenStorage })
    expect(() => memory.clear()).not.toThrow()
  })

  it('apply：只回填目标对象已有字段，忽略额外键（防原型污染）', () => {
    const storage = createStorage()
    storage.map.set(
      'filter_memory:k',
      JSON.stringify({ keyword: '恢复', page: 3, notAFilter: 'ignored' })
    )
    const memory = useFilterMemory<Filters>({ key: 'k', storage })
    const target = defaults()
    expect(memory.apply(target)).toBe(true)
    expect(target).toEqual({ keyword: '恢复', status: '', page: 3 })
    expect((target as any).notAFilter).toBeUndefined()

    // __proto__ 不会被回填（Object.keys 只遍历目标自身字段）
    storage.map.set('filter_memory:k', '{"__proto__":{"polluted":true}}')
    const safeTarget = defaults()
    expect(memory.apply(safeTarget)).toBe(false)
    expect((Object.prototype as any).polluted).toBeUndefined()
  })

  it('apply：无记忆 / 记忆无交集字段 → false 且目标不变', () => {
    const storage = createStorage()
    const memory = useFilterMemory<Filters>({ key: 'k', storage })
    const target = defaults()
    expect(memory.apply(target)).toBe(false)
    expect(target).toEqual({ keyword: '', status: '', page: 1 })

    storage.map.set('filter_memory:k', JSON.stringify({ other: 1 }))
    expect(memory.apply(target)).toBe(false)
    expect(target).toEqual({ keyword: '', status: '', page: 1 })
  })
})

describe('useFilterMemory：默认取当前路由 path + 默认 sessionStorage', () => {
  function mountWithMemory(): { key: string; memory: FilterMemory<Filters> } {
    let captured: FilterMemory<Filters> | null = null
    mount(
      defineComponent({
        setup() {
          captured = useFilterMemory<Filters>()
          return () => h('div')
        },
      })
    )
    if (!captured) throw new Error('composable 未被调用')
    return { key: (captured as FilterMemory<Filters>).key, memory: captured }
  }

  it('路由 path 作为 key；未注入 storage 时落 sessionStorage', () => {
    const { key, memory } = mountWithMemory()
    expect(key).toBe('filter_memory:/')
    memory.save({ keyword: '会话', status: 'pending', page: 1 })
    expect(sessionStorage.getItem('filter_memory:/')).toBe(
      JSON.stringify({ keyword: '会话', status: 'pending', page: 1 })
    )
    // 新实例（模拟重新进入列表）能读回
    const { memory: memory2 } = mountWithMemory()
    expect(memory2.load()).toEqual({ keyword: '会话', status: 'pending', page: 1 })
    memory2.clear()
    expect(sessionStorage.getItem('filter_memory:/')).toBeNull()
  })
})
