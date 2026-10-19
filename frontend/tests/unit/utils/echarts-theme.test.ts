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
})
