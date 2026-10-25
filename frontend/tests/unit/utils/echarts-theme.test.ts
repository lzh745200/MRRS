import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const { registerThemeMock } = vi.hoisted(() => ({
  registerThemeMock: vi.fn(),
}))

vi.mock('echarts/core', () => ({
  registerTheme: registerThemeMock,
}))

import {
  registerMilitaryTheme,
  getCurrentTheme,
  COLOR_PALETTE,
  MILITARY_BLUE,
  REVITALIZATION_GREEN,
  BADGE_GOLD,
  themeColor,
  syncPaletteFromTokens,
  refreshMilitaryTheme,
  chartThemeRevision,
  ECHARTS_THEME_CHANGED,
} from '@/utils/echarts-theme'

describe('utils/echarts-theme', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.documentElement.removeAttribute('data-theme')
  })

  it('注册浅色与暗色主题、内容正确且幂等', () => {
    registerMilitaryTheme()
    expect(registerThemeMock).toHaveBeenCalledTimes(2)
    expect(registerThemeMock).toHaveBeenNthCalledWith(1, 'militaryTech', expect.any(Object))
    expect(registerThemeMock).toHaveBeenNthCalledWith(2, 'militaryTechDark', expect.any(Object))

    const lightTheme = registerThemeMock.mock.calls[0][1] as any
    expect(lightTheme.color).toEqual(COLOR_PALETTE)
    expect(lightTheme.backgroundColor).toBe('transparent')
    expect(lightTheme.line.smooth).toBe(false)

    const darkTheme = registerThemeMock.mock.calls[1][1] as any
    expect(darkTheme.textStyle.color).toBe('#e2e8f0')
    expect(darkTheme.title.textStyle.color).toBe('#f1f5f9')
    expect(darkTheme.color).toEqual(COLOR_PALETTE)

    registerMilitaryTheme()
    registerMilitaryTheme()
    expect(registerThemeMock).toHaveBeenCalledTimes(2)
  })

  it('getCurrentTheme 默认返回浅色主题', () => {
    expect(getCurrentTheme()).toBe('militaryTech')
  })

  it('getCurrentTheme 检测 data-theme="dark-bigscreen" / "outdoor"（主题 5→3）', () => {
    document.documentElement.setAttribute('data-theme', 'dark-bigscreen')
    expect(getCurrentTheme()).toBe('militaryTechDark')
    document.documentElement.setAttribute('data-theme', 'outdoor')
    expect(getCurrentTheme()).toBe('militaryTechDark')
  })

  it('data-theme 为其他值时回退浅色主题', () => {
    document.documentElement.setAttribute('data-theme', 'light')
    expect(getCurrentTheme()).toBe('militaryTech')
  })

  it('document 不可用时回退浅色主题', () => {
    vi.stubGlobal('document', undefined)
    expect(getCurrentTheme()).toBe('militaryTech')
  })

  it('色彩常量导出', () => {
    expect(COLOR_PALETTE).toHaveLength(16)
    expect(COLOR_PALETTE[0]).toBe('#1e4d8c')
    expect(MILITARY_BLUE).toBe('#1e4d8c')
    expect(REVITALIZATION_GREEN).toBe('#2d6a4f')
    expect(BADGE_GOLD).toBe('#b8960c')
  })

  // W11-T45：图表轴/文字/分割线颜色跟随主题（读根元素 CSS 变量）
  describe('themeColor', () => {
    it('读取根元素 CSS 变量值', () => {
      document.documentElement.style.setProperty('--color-text-primary', '#334155')
      try {
        expect(themeColor('--color-text-primary', '#000000')).toBe('#334155')
      } finally {
        document.documentElement.style.removeProperty('--color-text-primary')
      }
    })

    it('变量缺失时回退 fallback', () => {
      expect(themeColor('--w19-undefined-color-var', '#abcdef')).toBe('#abcdef')
    })

    it('document 不可用时回退 fallback', () => {
      vi.stubGlobal('document', undefined)
      expect(themeColor('--color-text-primary', '#abcdef')).toBe('#abcdef')
    })
  })

  describe('调色板跟随 Token（① 主题切换图表跟随）', () => {
    afterEach(() => {
      document.documentElement.style.removeProperty('--color-primary')
      document.documentElement.style.removeProperty('--color-success')
      document.documentElement.style.removeProperty('--color-warning')
      document.documentElement.style.removeProperty('--color-danger')
      document.documentElement.style.removeProperty('--color-gold')
    })

    it('syncPaletteFromTokens 用 Token 值原地替换调色板（不换引用）', () => {
      const ref0 = COLOR_PALETTE
      document.documentElement.style.setProperty('--color-primary', '#111111')
      document.documentElement.style.setProperty('--color-success', '#222222')

      syncPaletteFromTokens()

      expect(COLOR_PALETTE).toBe(ref0) // 引用不变，既有 COLOR_PALETTE[i] 调用点无需改动
      expect(COLOR_PALETTE[0]).toBe('#111111')
      expect(COLOR_PALETTE[1]).toBe('#222222')
    })

    it('未纳入 Token 体系的索引保留原字面量（不编近似值）', () => {
      syncPaletteFromTokens()
      expect(COLOR_PALETTE[3]).toBe('#3b82f6')
      expect(COLOR_PALETTE[13]).toBe('#14b8a6')
    })

    it('Token 缺失时回退内置字面量', () => {
      document.documentElement.style.removeProperty('--color-danger')
      syncPaletteFromTokens()
      expect(COLOR_PALETTE[6]).toBe('#ef4444')
    })

    it('refreshMilitaryTheme 重新注册并递增版本号、派发事件', () => {
      const before = chartThemeRevision.value
      const handler = vi.fn()
      window.addEventListener(ECHARTS_THEME_CHANGED, handler)

      refreshMilitaryTheme()

      expect(registerThemeMock).toHaveBeenCalledTimes(2) // 两个主题各注册一次
      expect(chartThemeRevision.value).toBe(before + 1)
      expect(handler).toHaveBeenCalledTimes(1)

      window.removeEventListener(ECHARTS_THEME_CHANGED, handler)
    })
  })
})
