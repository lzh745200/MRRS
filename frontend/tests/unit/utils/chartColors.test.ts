/**
 * utils/chartColors.ts 测试
 * 覆盖：cssVarValue 取值/回退、chartColorPrimary、chartColor 四语义、chartPalette 五色板
 */
import { describe, it, expect, afterEach } from 'vitest'
import { cssVarValue, chartColorPrimary, chartColor, chartPalette } from '@/utils/chartColors'

afterEach(() => {
  document.documentElement.style.removeProperty('--color-primary')
  document.documentElement.style.removeProperty('--color-success')
})

describe('cssVarValue', () => {
  it('变量存在 → 返回计算值（去空白）', () => {
    document.documentElement.style.setProperty('--color-primary', ' #123456 ')
    expect(cssVarValue('--color-primary', '#000000')).toBe('#123456')
  })

  it('变量缺失 → 回退 fallback', () => {
    expect(cssVarValue('--color-nonexistent-xyz', '#abcdef')).toBe('#abcdef')
  })
})

describe('chartColorPrimary', () => {
  it('读取 --color-primary；jsdom 默认回退军绿', () => {
    expect(chartColorPrimary()).toBe('#2d6a4f')
    document.documentElement.style.setProperty('--color-primary', '#409eff')
    expect(chartColorPrimary()).toBe('#409eff')
  })
})

describe('chartColor', () => {
  it('四语义色回退值', () => {
    expect(chartColor('success')).toBe('#67c23a')
    expect(chartColor('warning')).toBe('#e6a23c')
    expect(chartColor('danger')).toBe('#f56c6c')
    expect(chartColor('info')).toBe('#909399')
  })

  it('变量存在时返回变量值', () => {
    document.documentElement.style.setProperty('--color-success', '#00ff00')
    expect(chartColor('success')).toBe('#00ff00')
  })
})

describe('chartPalette', () => {
  it('返回主/成功/警告/危险/信息五色板', () => {
    expect(chartPalette()).toEqual(['#2d6a4f', '#67c23a', '#e6a23c', '#f56c6c', '#909399'])
  })
})
