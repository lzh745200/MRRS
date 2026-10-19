/**
 * useUiPrefs（UI 显示偏好）单元测试 —— v1.15.0 / W23
 *
 * 覆盖：默认值 / JSON 读写 / 损坏与异常回退 / 白名单归一 / DOM 属性应用 / 组合式 set+reset。
 * 该 .ts 没有 .vue 的"单执行者"限制；但 AppearanceSettings.vue 的唯一执行者是
 * tests/unit/components/settings/AppearanceSettings.test.ts。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_UI_PREFS,
  UI_PREFS_STORAGE_KEY,
  applyUiPrefsToDom,
  initUiPrefs,
  normalizeUiPrefs,
  readUiPrefs,
  useUiPrefs,
  writeUiPrefs,
} from '@/composables/useUiPrefs'

function resetDom() {
  const root = document.documentElement
  delete root.dataset.fontSize
  delete root.dataset.density
  delete root.dataset.contrast
  delete root.dataset.simplify
}

beforeEach(() => {
  localStorage.clear()
  resetDom()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('normalizeUiPrefs', () => {
  it('非对象/数组/null 回退默认', () => {
    expect(normalizeUiPrefs(null)).toEqual(DEFAULT_UI_PREFS)
    expect(normalizeUiPrefs('x')).toEqual(DEFAULT_UI_PREFS)
    expect(normalizeUiPrefs([1, 2])).toEqual(DEFAULT_UI_PREFS)
  })

  it('合法值保留', () => {
    expect(
      normalizeUiPrefs({
        fontSize: 'large',
        density: 'compact',
        contrast: 'high',
        simplify: true,
      })
    ).toEqual({ fontSize: 'large', density: 'compact', contrast: 'high', simplify: true })
  })

  it('逐字段非法回退默认（不影响其它合法字段）', () => {
    expect(
      normalizeUiPrefs({ fontSize: 'huge', density: 1, contrast: 'blue', simplify: 'yes' })
    ).toEqual(DEFAULT_UI_PREFS)
    expect(
      normalizeUiPrefs({ fontSize: 'compact', density: 'comfortable', contrast: 'normal' })
    ).toEqual({ ...DEFAULT_UI_PREFS, fontSize: 'compact' })
  })
})

describe('read/write UiPrefs', () => {
  it('无存储值返回默认', () => {
    expect(readUiPrefs()).toEqual(DEFAULT_UI_PREFS)
  })

  it('写入后可读回', () => {
    const prefs = { fontSize: 'large' as const, density: 'compact' as const, contrast: 'high' as const, simplify: true }
    writeUiPrefs(prefs)
    expect(localStorage.getItem(UI_PREFS_STORAGE_KEY)).toBe(JSON.stringify(prefs))
    expect(readUiPrefs()).toEqual(prefs)
  })

  it('损坏 JSON 回退默认', () => {
    localStorage.setItem(UI_PREFS_STORAGE_KEY, '{bad json')
    expect(readUiPrefs()).toEqual(DEFAULT_UI_PREFS)
  })

  it('getItem 抛错（受限存储）回退默认不抛出', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(readUiPrefs()).toEqual(DEFAULT_UI_PREFS)
  })

  it('setItem 抛错（配额）静默忽略不抛出', () => {
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(() => writeUiPrefs(DEFAULT_UI_PREFS)).not.toThrow()
  })
})

describe('applyUiPrefsToDom / initUiPrefs', () => {
  it('四属性写入 html.dataset（含默认值显式写入）', () => {
    applyUiPrefsToDom({ fontSize: 'large', density: 'compact', contrast: 'high', simplify: true })
    const root = document.documentElement
    expect(root.dataset.fontSize).toBe('large')
    expect(root.dataset.density).toBe('compact')
    expect(root.dataset.contrast).toBe('high')
    expect(root.dataset.simplify).toBe('true')
    applyUiPrefsToDom(DEFAULT_UI_PREFS)
    expect(root.dataset.fontSize).toBe('standard')
    expect(root.dataset.density).toBe('comfortable')
    expect(root.dataset.contrast).toBe('normal')
    expect(root.dataset.simplify).toBe('false')
  })

  it('initUiPrefs 把已记忆偏好写回 DOM', () => {
    writeUiPrefs({ ...DEFAULT_UI_PREFS, fontSize: 'compact' })
    initUiPrefs()
    expect(document.documentElement.dataset.fontSize).toBe('compact')
  })
})

describe('useUiPrefs', () => {
  it('初始化读取已存偏好', () => {
    writeUiPrefs({ ...DEFAULT_UI_PREFS, density: 'compact' })
    const { prefs } = useUiPrefs()
    expect(prefs.value.density).toBe('compact')
  })

  it('setPrefs 合并并持久化 + 应用 DOM', () => {
    const { prefs, setPrefs } = useUiPrefs()
    setPrefs({ fontSize: 'large' })
    expect(prefs.value.fontSize).toBe('large')
    expect(document.documentElement.dataset.fontSize).toBe('large')
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).fontSize).toBe('large')
  })

  it('setPrefs 非法值被白名单归一', () => {
    const { prefs, setPrefs } = useUiPrefs()
    setPrefs({ fontSize: 'invalid' as never })
    expect(prefs.value.fontSize).toBe('standard')
  })

  it('resetPrefs 恢复默认并应用 DOM', () => {
    const { prefs, setPrefs, resetPrefs } = useUiPrefs()
    setPrefs({ simplify: true, contrast: 'high' })
    resetPrefs()
    expect(prefs.value).toEqual(DEFAULT_UI_PREFS)
    expect(document.documentElement.dataset.simplify).toBe('false')
    expect(document.documentElement.dataset.contrast).toBe('normal')
  })
})
