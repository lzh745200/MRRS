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
  UI_PRESETS,
  applyUiPrefsToDom,
  hasStoredUiPrefs,
  initUiPrefs,
  matchPreset,
  normalizeUiPrefs,
  pickDensityForViewport,
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
    const prefs = {
      fontSize: 'large' as const,
      density: 'compact' as const,
      contrast: 'high' as const,
      simplify: true,
    }
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

// ② 场景预设与按视口自适应
describe('UI_PRESETS / matchPreset / applyPreset', () => {
  it('三档预设都是完整偏好（四字段齐全，不是打补丁）', () => {
    for (const preset of Object.values(UI_PRESETS)) {
      expect(Object.keys(preset).sort()).toEqual(['contrast', 'density', 'fontSize', 'simplify'])
    }
  })

  it('matchPreset 精确命中预设名', () => {
    expect(matchPreset({ ...UI_PRESETS.presentation })).toBe('presentation')
    expect(matchPreset({ ...UI_PRESETS.compact })).toBe('compact')
    expect(matchPreset({ ...DEFAULT_UI_PREFS })).toBe('standard')
  })

  it('混搭（无任何预设完全一致）返回 custom', () => {
    expect(matchPreset({ ...DEFAULT_UI_PREFS, density: 'compact' })).toBe('custom')
  })

  it('applyPreset 一次性覆盖四个字段并持久化 + 应用 DOM', () => {
    const { prefs, preset, applyPreset } = useUiPrefs()
    applyPreset('presentation')
    expect(prefs.value).toEqual(UI_PRESETS.presentation)
    expect(preset.value).toBe('presentation')
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string)).toEqual(
      UI_PRESETS.presentation
    )
    expect(document.documentElement.dataset.fontSize).toBe('large')
    expect(document.documentElement.dataset.simplify).toBe('true')
  })

  it('手动改任一开关后预设变为 custom（预设行不再高亮）', () => {
    const { preset, applyPreset, setPrefs } = useUiPrefs()
    applyPreset('compact')
    expect(preset.value).toBe('compact')
    setPrefs({ contrast: 'high' })
    expect(preset.value).toBe('custom')
  })
})

describe('视口自适应与首次初始化', () => {
  it('pickDensityForViewport：≤800 紧凑，>800 舒适', () => {
    expect(pickDensityForViewport(768)).toBe('compact')
    expect(pickDensityForViewport(800)).toBe('compact')
    expect(pickDensityForViewport(801)).toBe('comfortable')
    expect(pickDensityForViewport(1080)).toBe('comfortable')
  })

  it('hasStoredUiPrefs 反映存储现状，存储不可用返回 false', () => {
    expect(hasStoredUiPrefs()).toBe(false)
    writeUiPrefs({ ...DEFAULT_UI_PREFS })
    expect(hasStoredUiPrefs()).toBe(true)
    // jsdom 的 localStorage.getItem 是自有属性，必须打在实例上才能拦到
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(hasStoredUiPrefs()).toBe(false)
    vi.restoreAllMocks()
  })

  it('首次使用按视口高度给紧凑密度并落盘', () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(720)
    initUiPrefs()
    expect(document.documentElement.dataset.density).toBe('compact')
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).density).toBe('compact')
    vi.restoreAllMocks()
  })

  it('大视口首次使用给舒适密度', () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(1440)
    initUiPrefs()
    expect(document.documentElement.dataset.density).toBe('comfortable')
    vi.restoreAllMocks()
  })

  it('已有存储时不被视口推荐覆盖（尊重用户选择）', () => {
    writeUiPrefs({ ...DEFAULT_UI_PREFS, density: 'comfortable' })
    localStorage.setItem(
      UI_PREFS_STORAGE_KEY,
      JSON.stringify({ ...DEFAULT_UI_PREFS, density: 'comfortable' })
    )
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(600)
    initUiPrefs()
    expect(document.documentElement.dataset.density).toBe('comfortable')
    vi.restoreAllMocks()
  })

  // SSR / 无 window 环境（构建期预渲染、单测、Electron 早期阶段）不能抛错：
  // 取不到视口就按 768（政务本）保守处理，行为与"小屏"一致。
  it('无 window 环境回退 768，不抛错', () => {
    vi.stubGlobal('window', undefined)
    expect(() => initUiPrefs()).not.toThrow()
    expect(document.documentElement.dataset.density).toBe('compact')
    vi.unstubAllGlobals()
  })
})
