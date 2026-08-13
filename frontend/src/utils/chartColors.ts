/**
 * 图表配色工具 — ECharts/Chart.js 走 canvas 渲染，无法解析 CSS var()，
 * 需在运行时从 :root 计算样式取值，保证颜色单一来源（styles/tokens.scss）。
 * jsdom 等无样式环境回退到 tokens 默认色。
 */

/** 读取 CSS 变量当前计算值；取不到时回退 fallback */
export function cssVarValue(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** 主题主色（tokens.scss --color-primary，默认军绿回退 #2d6a4f） */
export function chartColorPrimary(): string {
  return cssVarValue('--color-primary', '#2d6a4f')
}

type SemanticColor = 'success' | 'warning' | 'danger' | 'info'

const SEMANTIC_FALLBACKS: Record<SemanticColor, string> = {
  success: '#67c23a',
  warning: '#e6a23c',
  danger: '#f56c6c',
  info: '#909399',
}

/** 按语义名取单色（success/warning/danger/info） */
export function chartColor(name: SemanticColor): string {
  return cssVarValue(`--color-${name}`, SEMANTIC_FALLBACKS[name])
}

/** 图表标准五色板（主/成功/警告/危险/信息），按位对应 tokens.scss 语义色 */
export function chartPalette(): string[] {
  return [
    chartColorPrimary(),
    chartColor('success'),
    chartColor('warning'),
    chartColor('danger'),
    chartColor('info'),
  ]
}
