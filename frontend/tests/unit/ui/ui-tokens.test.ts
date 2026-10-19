/**
 * W23 UI 视觉 Token 静态契约断言（视觉回归基线 · vitest 部分）
 *
 * 目标（契约 `.scratch/w23-ui-redesign/000-contract.md` §0.1~§0.4）：
 * - tokens.scss 关键变量存在且值正确（主题 5→3、字体缩放、色彩阶、圆角/阴影、密度/高对比/简化/大屏距离分档）；
 * - 全局模板样式（components/*.scss、accessibility.css）提供契约要求的类与选择器；
 * - 任何一条被改回旧口径都会让本测试变红（防回退）。
 *
 * 说明：jsdom 不做 SCSS 编译与 CSS 变量解析（`getComputedStyle` 无法求值 var()），
 * 因此这里采用**静态文本解析**——这是可在 CI 稳定运行的视觉 token 基线；
 * 页面级 DOM 结构快照见 `tests/e2e/visual/visual-baseline.spec.ts`。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

const STYLES_DIR = resolve(process.cwd(), 'src/styles')

/** 去掉 SCSS 行注释与块注释，避免注释中的示例/历史名污染断言 */
function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

function readStyle(relativePath: string): string {
  return readFileSync(join(STYLES_DIR, relativePath), 'utf8')
}

/** 递归读取 src/styles 下全部 .scss/.css（拼成一份静态文本） */
function collectAllStyleSources(dir = STYLES_DIR): string[] {
  const sources: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name)
    if (entry.isDirectory()) {
      sources.push(...collectAllStyleSources(fullPath))
    } else if (/\.(scss|css)$/.test(entry.name)) {
      sources.push(stripComments(readFileSync(fullPath, 'utf8')))
    }
  }
  return sources
}

const tokensSource = stripComments(readStyle('tokens.scss'))
const allStyleSource = collectAllStyleSources().join('\n')

/** 断言某段 SCSS 中存在“变量: 值”的声明（允许空白差异） */
function expectDeclaration(source: string, property: string, valuePattern: string): void {
  const escapedProperty = property.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  expect(source).toMatch(new RegExp(`${escapedProperty}\\s*:\\s*${valuePattern}`))
}

/** 断言某个选择器块内包含指定声明 */
function expectBlockDeclaration(blockSelectorPattern: string, declaration: string): void {
  expect(allStyleSource).toMatch(
    new RegExp(`${blockSelectorPattern}[^{]*\\{[^}]*${declaration}`, 's')
  )
}

describe('W23 tokens.scss 色彩契约', () => {
  it('军绿主色与主色阶 50/100/500/600/700/900', () => {
    expectDeclaration(tokensSource, '--color-primary', '#2d6a4f')
    expectDeclaration(tokensSource, '--color-primary-50', '#f2f8f4')
    expectDeclaration(tokensSource, '--color-primary-100', '#dfeee5')
    expectDeclaration(tokensSource, '--color-primary-500', 'var\\(--color-primary\\)')
    expectDeclaration(tokensSource, '--color-primary-600', '#235a42')
    expectDeclaration(tokensSource, '--color-primary-700', '#1b4332')
    expectDeclaration(tokensSource, '--color-primary-900', '#0f2e22')
  })

  it('金色点缀 token 存在（选中竖条/数据高亮/表头底线三用途）', () => {
    expectDeclaration(tokensSource, '--color-accent-gold', '#d4af37')
  })

  it('页面/卡片/边框色升级为 v2 值', () => {
    expectDeclaration(tokensSource, '--color-bg-page', '#f5f7f5')
    expectDeclaration(tokensSource, '--color-bg-card', '#ffffff')
    expectDeclaration(tokensSource, '--color-card-border', '#e5e9e6')
  })

  it('卡片阴影两档（--shadow-card / --shadow-pop），使用 v2 轻阴影色', () => {
    expect(tokensSource).toMatch(/--shadow-card:[\s\S]*?rgba\(\s*16\s*,\s*40\s*,\s*28/)
    expect(tokensSource).toMatch(/--shadow-pop:[\s\S]*?rgba\(\s*16\s*,\s*40\s*,\s*28/)
  })

  it('侧栏深绿渐变与金色竖条宽度 token', () => {
    expect(tokensSource).toMatch(
      /--sidebar-bg:\s*linear-gradient\(\s*180deg\s*,\s*#123f2e\s+0%\s*,\s*#0f2e22\s+100%\s*\)/
    )
    expectDeclaration(tokensSource, '--sidebar-current-bar-width', '3px')
  })

  it('圆角三档：卡片 8 / 控件 6 / 胶囊 999', () => {
    expectDeclaration(tokensSource, '--radius-card', '8px')
    expectDeclaration(tokensSource, '--radius-control', '6px')
    expectDeclaration(tokensSource, '--radius-pill', '999px')
  })
})

describe('W23 主题 5→3 契约', () => {
  it('仅保留 dark-bigscreen 与 outdoor 两个显式主题块（军绿为 :root 默认）', () => {
    const themeBlocks = [...tokensSource.matchAll(/\[data-theme="([a-z-]+)"\]/g)].map(
      (match) => match[1]
    )
    expect([...new Set(themeBlocks)].sort()).toEqual(['dark-bigscreen', 'outdoor'])
    expect(tokensSource).not.toMatch(/\[data-theme="light"\]/)
    expect(tokensSource).not.toMatch(/\[data-theme="dark"\]/)
    expect(tokensSource).not.toMatch(/\[data-theme="military"\]/)
  })

  it('深色大屏主题保留大屏专用底色/文字色', () => {
    expectBlockDeclaration('\\[data-theme="dark-bigscreen"\\]', '--color-text-primary:\\s*#ffffff')
  })

  it('户外高对比主题通过 --font-scale: 1.5 放大字号', () => {
    expectBlockDeclaration('\\[data-theme="outdoor"\\]', '--font-scale:\\s*1\\.5')
  })
})

describe('W23 字体缩放与字号阶梯契约', () => {
  it('默认缩放因子为 1，字号阶梯全部 calc(var(--font-scale)) 化', () => {
    expect(tokensSource).toMatch(/--font-scale:\s*1;/)
    for (const [name, size] of [
      ['xs', '12px'],
      ['sm', '13px'],
      ['md', '14px'],
      ['lg', '16px'],
      ['xl', '18px'],
      ['xxl', '20px'],
      ['xxxl', '24px'],
      ['display', '32px'],
    ] as const) {
      expect(tokensSource).toMatch(
        new RegExp(`--font-size-${name}:\\s*calc\\(${size} \\* var\\(--font-scale\\)\\)`)
      )
    }
  })

  it('--text-* 兼容别名与 --font-size-* 同源', () => {
    for (const name of ['xs', 'sm', 'md', 'lg', 'xl', '2xl', '3xl'] as const) {
      expect(tokensSource).toMatch(
        new RegExp(
          `--text-${name}:\\s*var\\(--font-size-${name === '2xl' ? 'xxl' : name === '3xl' ? 'xxxl' : name}\\)`
        )
      )
    }
    expect(tokensSource).toMatch(/--text-display:\s*var\(--font-size-display\)/)
  })

  it('Element Plus 基础字号跟随缩放后的正文 token', () => {
    expect(tokensSource).toMatch(/--el-font-size-base:\s*var\(--(?:font-size|text)-md\)/)
  })

  it('正文行高 1.6', () => {
    expect(tokensSource).toMatch(/--line-height-normal:\s*1\.6/)
  })

  it('字号档位：compact ×0.92 / large ×1.12', () => {
    expectBlockDeclaration('\\[data-font-size="compact"\\]', '--font-scale:\\s*0\\.92')
    expectBlockDeclaration('\\[data-font-size="large"\\]', '--font-scale:\\s*1\\.12')
  })
})

describe('W23 密度/高对比/简化模式契约', () => {
  it('密度档 compact 收紧表格行高与控件高度', () => {
    expectBlockDeclaration('\\[data-density="compact"\\]', '--table-row-height:\\s*34px')
    expectBlockDeclaration('\\[data-density="compact"\\]', '--control-height:\\s*32px')
    expect(allStyleSource).toMatch(/\[data-density="compact"\]\s+\.el-table/)
  })

  it('高对比档覆盖文字/边框/卡片边框并去阴影', () => {
    expectBlockDeclaration('\\[data-contrast="high"\\]', '--color-text-primary:\\s*#0b1f16')
    expectBlockDeclaration('\\[data-contrast="high"\\]', '--color-card-border:\\s*#8aa596')
    expectBlockDeclaration('\\[data-contrast="high"\\]', '--shadow-card:\\s*none')
    expect(allStyleSource).toMatch(/\[data-contrast="high"\]\s+\.el-card/)
  })

  it('简化档隐藏次要信息（趋势箭头/辅助说明/高级项）', () => {
    expect(allStyleSource).toMatch(/\[data-simplify="true"\]\s+\.stat-trend/)
    expect(allStyleSource).toMatch(/\[data-simplify="true"\]\s+\.list-hint/)
    expect(allStyleSource).toMatch(/\[data-simplify="true"\]\s+\.advanced-only/)
  })
})

describe('W23 大屏字号距离分档契约', () => {
  it('大屏根字号三档变量存在且默认 6m 为基线', () => {
    expectDeclaration(tokensSource, '--bs-title-size', '28px')
    expectDeclaration(tokensSource, '--bs-kpi-size', '40px')
    expectDeclaration(tokensSource, '--bs-label-size', '14px')
    expectDeclaration(tokensSource, '--bs-chart-title-size', '18px')
  })

  it('data-bigscreen-distance 覆盖 3m/6m/10m 三档', () => {
    expectBlockDeclaration('\\[data-bigscreen-distance="3m"\\]', '--bs-title-size:\\s*22px')
    expectBlockDeclaration('\\[data-bigscreen-distance="6m"\\]', '--bs-title-size:\\s*28px')
    expectBlockDeclaration('\\[data-bigscreen-distance="10m"\\]', '--bs-title-size:\\s*36px')
    expectBlockDeclaration('\\[data-bigscreen-distance="10m"\\]', '--bs-kpi-size:\\s*56px')
  })
})

describe('W23 全局模板样式类契约（供 W2/W4/W6 组件接入）', () => {
  it('卡片与统计卡类存在，数字使用 tabular-nums', () => {
    expect(allStyleSource).toMatch(/\.app-card\s*\{/)
    expect(allStyleSource).toMatch(/\.app-stat-card\s*\{/)
    expect(allStyleSource).toMatch(/\.num-highlight\s*\{/)
    expect(allStyleSource).toMatch(/font-variant-numeric:\s*tabular-nums/)
  })

  it('状态三件套全局类存在（空态/加载/错误）', () => {
    expect(allStyleSource).toMatch(/\.app-empty[,\s]/)
    expect(allStyleSource).toMatch(/\.app-loading[,\s]/)
    expect(allStyleSource).toMatch(/\.app-error[,\s]/)
    expect(allStyleSource).toMatch(/\.app-error__retry/)
  })

  it('表格模板：表头金色底线与 hover 行使用主色浅底', () => {
    expect(allStyleSource).toMatch(/border-bottom:\s*2px solid var\(--color-accent-gold/)
    expect(allStyleSource).toMatch(/\[data-density="compact"\]\s+\.el-table\s+\.cell/)
  })
})
