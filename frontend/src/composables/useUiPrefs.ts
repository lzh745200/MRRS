/**
 * UI 显示偏好（v1.15.0 / W23）
 *
 * 单一读写入口：字号档 / 密度档 / 高对比 / 简化模式，持久化到 localStorage `ui:prefs`，
 * 以 <html> 上的 data-* 属性驱动 tokens.scss 的显示偏好覆盖块：
 *   data-font-size="compact|standard|large"
 *   data-density="comfortable|compact"
 *   data-contrast="normal|high"
 *   data-simplify="false|true"
 *
 * 约定：
 * - standard / comfortable / normal / false 也会写入 data-*（显式、可断言、避免"删属性"歧义）；
 * - localStorage 不可用（隐私模式/配额）时静默降级为内存态（本次会话仍生效）；
 * - 损坏 JSON / 非法值一律回退默认，绝不抛错（模块在应用启动路径上）。
 */
import { ref } from 'vue'

export const UI_PREFS_STORAGE_KEY = 'ui:prefs'

export type FontSizePref = 'compact' | 'standard' | 'large'
export type DensityPref = 'comfortable' | 'compact'
export type ContrastPref = 'normal' | 'high'

export interface UiPrefs {
  fontSize: FontSizePref
  density: DensityPref
  contrast: ContrastPref
  simplify: boolean
}

export const DEFAULT_UI_PREFS: UiPrefs = {
  fontSize: 'standard',
  density: 'comfortable',
  contrast: 'normal',
  simplify: false,
}

const FONT_SIZE_VALUES: readonly FontSizePref[] = ['compact', 'standard', 'large']
const DENSITY_VALUES: readonly DensityPref[] = ['comfortable', 'compact']
const CONTRAST_VALUES: readonly ContrastPref[] = ['normal', 'high']

function pick<T extends string>(allowed: readonly T[], value: unknown, fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

/** 白名单归一化（损坏 JSON / 非法值 / 非对象 → 默认值逐字段回退）。 */
export function normalizeUiPrefs(raw: unknown): UiPrefs {
  const src = (raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}) as Partial<UiPrefs>
  return {
    fontSize: pick(FONT_SIZE_VALUES, src.fontSize, DEFAULT_UI_PREFS.fontSize),
    density: pick(DENSITY_VALUES, src.density, DEFAULT_UI_PREFS.density),
    contrast: pick(CONTRAST_VALUES, src.contrast, DEFAULT_UI_PREFS.contrast),
    simplify: typeof src.simplify === 'boolean' ? src.simplify : DEFAULT_UI_PREFS.simplify,
  }
}

/** 读取偏好（localStorage 异常/损坏 JSON 均回退默认，绝不抛错）。 */
export function readUiPrefs(): UiPrefs {
  try {
    const raw = localStorage.getItem(UI_PREFS_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_UI_PREFS }
    return normalizeUiPrefs(JSON.parse(raw))
  } catch {
    return { ...DEFAULT_UI_PREFS }
  }
}

/** 写入偏好（存储不可用静默忽略，内存态仍生效）。 */
export function writeUiPrefs(prefs: UiPrefs): void {
  try {
    localStorage.setItem(UI_PREFS_STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    // 隐私模式/配额：静默降级
  }
}

/** 将偏好应用到 <html data-*>（tokens.scss 显示偏好块据此生效）。 */
export function applyUiPrefsToDom(prefs: UiPrefs): void {
  const root = document.documentElement
  root.dataset.fontSize = prefs.fontSize
  root.dataset.density = prefs.density
  root.dataset.contrast = prefs.contrast
  root.dataset.simplify = prefs.simplify ? 'true' : 'false'
}

/** 组合式入口：响应式偏好 + 变更（写存储 + 应用 DOM）+ 重置。 */
export function useUiPrefs() {
  const prefs = ref<UiPrefs>(readUiPrefs())
  const apply = (next: UiPrefs) => {
    prefs.value = next
    writeUiPrefs(next)
    applyUiPrefsToDom(next)
  }
  const setPrefs = (patch: Partial<UiPrefs>) => {
    apply(normalizeUiPrefs({ ...prefs.value, ...patch }))
  }
  const resetPrefs = () => apply({ ...DEFAULT_UI_PREFS })
  return { prefs, setPrefs, resetPrefs }
}

/** 应用启动时调用一次（main.ts），把已记忆偏好写回 DOM。 */
export function initUiPrefs(): void {
  applyUiPrefsToDom(readUiPrefs())
}
