import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 主题持久化 localStorage 键 */
export const THEME_STORAGE_KEY = 'theme'

/** 默认主题标识（军绿，对应 tokens.scss :root；DOM 上不设置 data-theme 属性） */
export const DEFAULT_THEME = 'default'

/** 主题选项（顶栏切换器与系统设置共用） */
export interface ThemeOption {
  value: string
  label: string
}

export const THEME_OPTIONS: ThemeOption[] = [
  { value: 'default', label: '军绿' },
  { value: 'light', label: '明亮' },
  { value: 'dark', label: '深色' },
  { value: 'military', label: '军旅' },
  { value: 'outdoor', label: '户外' },
  { value: 'high-contrast', label: '高对比' },
]

/**
 * 主题取值白名单校验。
 *
 * 非法/未知主题一旦落到 data-theme 上（例如 localStorage 被写入 "darkk"），
 * 全站 token 全部失效（没有任何 [data-theme="darkk"] 规则命中）→ 界面裸奔。
 * 因此所有外部来源（localStorage / 后端配置）的主题值都必须先过这里。
 */
export function normalizeTheme(value: unknown): string {
  return THEME_OPTIONS.some((t) => t.value === value) ? (value as string) : DEFAULT_THEME
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
    return normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY))
  } catch {
    return DEFAULT_THEME
  }
}

/**
 * 将主题应用到 DOM：
 * - 'default' → 移除 data-theme 属性（渲染 :root 军绿默认主题）
 * - 其他值 → 设置 data-theme，匹配 tokens.scss 的 [data-theme="..."]
 */
export function applyThemeToDom(theme: string): void {
  if (theme === DEFAULT_THEME) {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
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
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // 存储不可用（隐私模式/配额）不阻断主题切换：本次会话内仍然生效
    }
    applyThemeToDom(next)
  }

  return { appName, version, theme, setTheme }
})
