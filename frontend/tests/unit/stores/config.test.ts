import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  useConfigStore,
  applyThemeToDom,
  normalizeTheme,
  readStoredTheme,
  DEFAULT_THEME,
  THEME_STORAGE_KEY,
  THEME_OPTIONS,
} from '@/stores/config'

describe('useConfigStore', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    setActivePinia(createPinia())
  })

  it('appName 和 version 是常量', () => {
    const store = useConfigStore()
    expect(store.appName).toBe('帮扶管理信息系统')
    expect(store.version).toBe('1.5.0')
  })

  it('无 localStorage 时 theme 默认 default（军绿）', () => {
    const store = useConfigStore()
    expect(store.theme).toBe('default')
  })

  it('localStorage 存在时 theme 从其中读取', () => {
    localStorage.setItem('theme', 'dark')
    setActivePinia(createPinia())
    const store = useConfigStore()
    expect(store.theme).toBe('dark')
  })

  it('setTheme 修改 theme 并持久化到 localStorage', () => {
    const store = useConfigStore()
    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('setTheme 多次调用会覆盖', () => {
    const store = useConfigStore()
    store.setTheme('dark')
    store.setTheme('light')
    expect(store.theme).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('setTheme 非 default 主题设置 data-theme 属性', () => {
    const store = useConfigStore()
    store.setTheme('outdoor')
    expect(document.documentElement.getAttribute('data-theme')).toBe('outdoor')
  })

  it('setTheme default 移除 data-theme 属性（渲染 :root 军绿）', () => {
    const store = useConfigStore()
    store.setTheme('outdoor')
    store.setTheme('default')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('default')
  })
})

describe('applyThemeToDom', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme')
  })

  it('default 移除属性', () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    applyThemeToDom(DEFAULT_THEME)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('其他主题设置属性', () => {
    applyThemeToDom('high-contrast')
    expect(document.documentElement.getAttribute('data-theme')).toBe('high-contrast')
  })
})

// 2026-09-30 深审：localStorage 读取/写入无守卫，受限存储（隐私模式/配额）下
// SecurityError 会中断 main.ts 入口模块（白屏）；非法主题值会原样写进 data-theme。
describe('主题取值 fail-closed（白名单 + 存储守卫）', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    setActivePinia(createPinia())
  })
  afterEach(() => vi.restoreAllMocks())

  it('normalizeTheme：白名单内保留，非法/非字符串回退默认主题', () => {
    expect(normalizeTheme('dark')).toBe('dark')
    expect(normalizeTheme('high-contrast')).toBe('high-contrast')
    expect(normalizeTheme('darkk')).toBe(DEFAULT_THEME)
    expect(normalizeTheme('')).toBe(DEFAULT_THEME)
    expect(normalizeTheme(null)).toBe(DEFAULT_THEME)
    expect(normalizeTheme(undefined)).toBe(DEFAULT_THEME)
    expect(normalizeTheme(123)).toBe(DEFAULT_THEME)
  })

  it('readStoredTheme：非法存量值回退默认主题（不再写坏 data-theme）', () => {
    localStorage.setItem(THEME_STORAGE_KEY, '<script>')
    expect(readStoredTheme()).toBe(DEFAULT_THEME)
    localStorage.setItem(THEME_STORAGE_KEY, 'outdoor')
    expect(readStoredTheme()).toBe('outdoor')
  })

  it('readStoredTheme：getItem 抛错（受限存储）时回退默认主题而不抛出', () => {
    // 必须 spy 全局 localStorage 实例本身，不能 spy Storage.prototype：
    // src/test/setup.ts 用 Object.defineProperty 把 localStorage 换成普通对象字面量桩，
    // 其原型链上根本没有 Storage.prototype → 对原型的 spy 不会被命中，catch 分支永远进不去
    // （覆盖率计数恒为 0，测试给出虚假信心）。同 traps 参见 guards.test.ts / lockDigest.test.ts。
    const spy = vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    try {
      expect(readStoredTheme()).toBe(DEFAULT_THEME)
    } finally {
      spy.mockRestore()
    }
  })

  it('readStoredTheme：getItem 抛非 Error 值（如字符串）同样回退默认主题', () => {
    const spy = vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw 'SecurityError'
    })
    try {
      expect(readStoredTheme()).toBe(DEFAULT_THEME)
    } finally {
      spy.mockRestore()
    }
  })

  it('readStoredTheme：getItem 正常返回但值为非法主题时回退默认主题', () => {
    const spy = vi.spyOn(localStorage, 'getItem').mockImplementation(() => 'darkk')
    try {
      expect(readStoredTheme()).toBe(DEFAULT_THEME)
    } finally {
      spy.mockRestore()
    }
  })

  it('store 初始化：存量非法主题不会写进 data-theme', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'not-a-theme')
    setActivePinia(createPinia())
    const store = useConfigStore()
    expect(store.theme).toBe(DEFAULT_THEME)
  })

  it('setTheme 非法值不落盘、不写 data-theme', () => {
    const store = useConfigStore()
    store.setTheme('evil-theme')
    expect(store.theme).toBe(DEFAULT_THEME)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe(DEFAULT_THEME)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('setTheme 写盘抛错（配额）时仍在本会话生效且不抛出', () => {
    const store = useConfigStore()
    // 同 readStoredTheme：spy 实例而非 Storage.prototype（setup.ts 的桩不在原型链上）
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      expect(() => store.setTheme('dark')).not.toThrow()
      expect(store.theme).toBe('dark')
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
      // 写盘失败：值不落盘（区别于正常路径的持久化断言）
      expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
    } finally {
      spy.mockRestore()
    }
  })

  it('setTheme 写盘抛非 Error 值（如字符串）时同样不抛出且本会话生效', () => {
    const store = useConfigStore()
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw 'QuotaExceededError'
    })
    try {
      expect(() => store.setTheme('high-contrast')).not.toThrow()
      expect(store.theme).toBe('high-contrast')
      expect(document.documentElement.getAttribute('data-theme')).toBe('high-contrast')
    } finally {
      spy.mockRestore()
    }
  })

  it('store 初始化：getItem 抛错（受限存储）时 theme 回退默认且不中断构造', () => {
    const spy = vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    try {
      setActivePinia(createPinia())
      const store = useConfigStore()
      expect(store.theme).toBe(DEFAULT_THEME)
      expect(store.appName).toBe('帮扶管理信息系统')
    } finally {
      spy.mockRestore()
    }
  })
})

describe('THEME_OPTIONS / THEME_STORAGE_KEY', () => {
  it('包含 default 军绿选项且值不重复', () => {
    const values = THEME_OPTIONS.map((t) => t.value)
    expect(values).toContain('default')
    expect(new Set(values).size).toBe(values.length)
    expect(THEME_OPTIONS.every((t) => t.label.length > 0)).toBe(true)
  })

  it('THEME_STORAGE_KEY 为 theme', () => {
    expect(THEME_STORAGE_KEY).toBe('theme')
  })
})
