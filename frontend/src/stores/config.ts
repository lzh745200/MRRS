import { defineStore } from 'pinia'
import { ref } from 'vue'
import { refreshMilitaryTheme } from '@/utils/echarts-theme'
import { safeGetItem, safeSetItem } from '@/utils/safeStorage'

/** 主题持久化 localStorage 键 */
export const THEME_STORAGE_KEY = 'theme'

/** 默认主题标识（军绿，对应 tokens.scss :root；DOM 上不设置 data-theme 属性） */
export const DEFAULT_THEME = 'default'

/**
 * 主题选项（顶栏切换器与外观设置共用）。
 *
 * UI v2.0（W23）：主题 5→3 收敛。`default`（= tokens.scss :root 军绿亮色）、
 * `dark-bigscreen`（深色大屏）、`outdoor`（户外高对比）。
 * 旧值 light/dark/military/high-contrast 由 normalizeTheme 迁移映射，历史用户不失效。
 */
export interface ThemeOption {
  value: string
  label: string
}

export const THEME_OPTIONS: ThemeOption[] = [
  { value: 'default', label: '军绿（默认）' },
  { value: 'dark-bigscreen', label: '深色大屏' },
  { value: 'outdoor', label: '户外高对比' },
]

/** 旧主题值迁移表（v1.15.0 主题 5→3）。 */
export const LEGACY_THEME_MAP: Record<string, string> = {
  light: 'default',
  dark: 'dark-bigscreen',
  military: 'default',
  'high-contrast': 'outdoor',
}

/**
 * 主题取值白名单校验（含旧值迁移）。
 *
 * 非法/未知主题一旦落到 data-theme 上（例如 localStorage 被写入 "darkk"），
 * 全站 token 全部失效（没有任何 [data-theme="darkk"] 规则命中）→ 界面裸奔。
 * 因此所有外部来源（localStorage / 后端配置）的主题值都必须先过这里。
 */
export function normalizeTheme(value: unknown): string {
  const raw = typeof value === 'string' ? value : ''
  const mapped = LEGACY_THEME_MAP[raw] ?? raw
  return THEME_OPTIONS.some((t) => t.value === mapped) ? mapped : DEFAULT_THEME
}

/**
 * 安全读取"已记忆的主题"。
 *
 * 受限存储（隐私模式/禁用 Cookie/配额）下 localStorage.getItem 会抛 SecurityError；
 * 模块顶层调用点（main.ts）一旦抛出会中断入口模块 → 整站白屏。
 * 此处吞掉异常并回退默认主题（视觉降级，不影响可用性）。
 */
export function readStoredTheme(): string {
  try {
    return normalizeTheme(safeGetItem(THEME_STORAGE_KEY, 'local'))
  } catch {
    return DEFAULT_THEME
  }
}

/**
 * 将主题应用到 DOM：
 * - 'default' → 移除 data-theme 属性（渲染 :root 军绿默认主题）
 * - 其他值 → 设置 data-theme，匹配 tokens.scss 的 [data-theme="..."]
 *
 * 写完 `data-theme` 后必须 `refreshMilitaryTheme()`：ECharts 主题是**注册时的快照**，
 * 不刷新就永远是切换前那套颜色（2026-10-25 修的观感缺陷：切到"户外高对比"图表仍军绿）。
 */
export function applyThemeToDom(theme: string): void {
  if (theme === DEFAULT_THEME) {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
  refreshMilitaryTheme()
}

export const useConfigStore = defineStore('config', () => {
  const appName = ref('帮扶管理信息系统')
  const version = ref('1.5.0')
  const theme = ref(readStoredTheme())

  function setTheme(t: string) {
    // 写路径同样过白名单：非法值不再落盘、不再写进 data-theme
    const next = normalizeTheme(t)
    theme.value = next
    try {
      safeSetItem(THEME_STORAGE_KEY, next, 'local')
    } catch {
      // 存储不可用（隐私模式/配额）不阻断主题切换：本次会话内仍然生效
    }
    applyThemeToDom(next)
  }

  return { appName, version, theme, setTheme }
})
