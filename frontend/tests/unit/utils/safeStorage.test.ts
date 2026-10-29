import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  isStorageAvailable,
  safeGetItem,
  safeRemoveItem,
  safeSetItem,
} from '@/utils/safeStorage'

function makeStore(overrides: Partial<Storage> = {}): Storage {
  const data = new Map<string, string>()
  return {
    getItem: vi.fn((key: string) => data.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      data.set(key, value)
    }),
    removeItem: vi.fn((key: string) => {
      data.delete(key)
    }),
    clear: vi.fn(() => data.clear()),
    key: vi.fn(() => null),
    get length() {
      return data.size
    },
    ...overrides,
  } as Storage
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('safeStorage 正常路径', () => {
  it('local/session 读写删都走对应 Storage', () => {
    const local = makeStore()
    const session = makeStore()
    vi.stubGlobal('localStorage', local)
    vi.stubGlobal('sessionStorage', session)

    expect(safeSetItem('a', '1')).toBe(true)
    expect(safeGetItem('a')).toBe('1')
    expect(safeRemoveItem('a')).toBe(true)
    expect(safeGetItem('a')).toBeNull()

    expect(safeSetItem('b', '2', 'session')).toBe(true)
    expect(safeGetItem('b', 'session')).toBe('2')
    expect(safeRemoveItem('b', 'session')).toBe(true)

    expect(local.setItem).toHaveBeenCalledWith('a', '1')
    expect(session.setItem).toHaveBeenCalledWith('b', '2')
  })

  it('isStorageAvailable 成功时写探针并清理', () => {
    const local = makeStore()
    vi.stubGlobal('localStorage', local)

    expect(isStorageAvailable()).toBe(true)
    expect(local.setItem).toHaveBeenCalledWith('__storage_probe__', '1')
    expect(local.removeItem).toHaveBeenCalledWith('__storage_probe__')
  })

  it('全局 Storage 缺失时回退到 window.localStorage/sessionStorage', () => {
    const local = makeStore()
    const session = makeStore()
    vi.stubGlobal('localStorage', undefined)
    vi.stubGlobal('sessionStorage', undefined)
    vi.stubGlobal('window', { localStorage: local, sessionStorage: session })

    expect(safeSetItem('k', 'v')).toBe(true)
    expect(safeGetItem('k')).toBe('v')
    expect(safeGetItem('s', 'session')).toBeNull()
    expect(safeSetItem('s', 'sv', 'session')).toBe(true)
    expect(safeGetItem('s', 'session')).toBe('sv')
  })
})

describe('safeStorage 受限环境降级', () => {
  it('getItem 抛错返回 null', () => {
    vi.stubGlobal('localStorage', makeStore({
      getItem: () => {
        throw new Error('SecurityError')
      },
    }))
    expect(safeGetItem('x')).toBeNull()
  })

  it('setItem 抛错返回 false', () => {
    vi.stubGlobal('localStorage', makeStore({
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
    }))
    expect(safeSetItem('x', '1')).toBe(false)
  })

  it('removeItem 抛错返回 false', () => {
    vi.stubGlobal('localStorage', makeStore({
      removeItem: () => {
        throw new Error('SecurityError')
      },
    }))
    expect(safeRemoveItem('x')).toBe(false)
  })

  it('isStorageAvailable 写探针失败返回 false', () => {
    vi.stubGlobal('localStorage', makeStore({
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
    }))
    expect(isStorageAvailable()).toBe(false)
  })

  it('无全局 Storage 且无 window 时所有操作静默降级', () => {
    vi.stubGlobal('localStorage', undefined)
    vi.stubGlobal('sessionStorage', undefined)
    vi.stubGlobal('window', undefined)

    expect(safeGetItem('x')).toBeNull()
    expect(safeSetItem('x', '1')).toBe(false)
    expect(safeRemoveItem('x')).toBe(false)
    expect(isStorageAvailable()).toBe(false)
  })
})
