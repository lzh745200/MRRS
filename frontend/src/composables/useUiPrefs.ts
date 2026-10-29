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
import { computed, ref } from 'vue'
import { safeGetItem, safeSetItem } from '@/utils/safeStorage'

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

// ============================================================================
// 场景预设（②）：把"调 4 个开关"降为"选 1 个场景"
// ============================================================================

export type UiPreset = 'standard' | 'compact' | 'presentation'

/**
 * 三档场景：
 * - `standard`：默认（标准字号 + 舒适行高），长时间录入眼睛不累；
 * - `compact`：挤信息量（小字号 + 紧凑行高 + 简化模式），1366×768 政务本一屏多看几行；
 * - `presentation`：投影/演示（大字号 + 紧凑行高 + 简化模式），坐在会议桌另一头也看得清。
 *
 * 值必须覆盖全部四个字段 —— 预设是"一组完整偏好"，不是"打补丁"，
 * 否则叠加后会出现"大字 + 舒适行高 + 不简化"的奇怪组合。
 */
export const UI_PRESETS: Readonly<Record<UiPreset, UiPrefs>> = {
  standard: { fontSize: 'standard', density: 'comfortable', contrast: 'normal', simplify: false },
  compact: { fontSize: 'compact', density: 'compact', contrast: 'normal', simplify: true },
  presentation: { fontSize: 'large', density: 'compact', contrast: 'normal', simplify: true },
}

export const UI_PRESET_OPTIONS: ReadonlyArray<{ value: UiPreset; label: string; hint: string }> = [
  { value: 'standard', label: '标准', hint: '标准字号 + 舒适行高' },
  { value: 'compact', label: '紧凑', hint: '小字号 + 紧凑行高，一屏更多行' },
  { value: 'presentation', label: '演示', hint: '大字号，适合投影/汇报' },
]

/** 当前偏好精确匹配某个预设时返回其名，否则 `'custom'`（用户手动混搭过）。 */
export function matchPreset(prefs: UiPrefs): UiPreset | 'custom' {
  for (const [name, preset] of Object.entries(UI_PRESETS) as Array<[UiPreset, UiPrefs]>) {
    if (
      preset.fontSize === prefs.fontSize &&
      preset.density === prefs.density &&
      preset.contrast === prefs.contrast &&
      preset.simplify === prefs.simplify
    ) {
      return name
    }
  }
  return 'custom'
}

/**
 * 按视口高度推荐密度：≤800px（1366×768 / 1280×800 等政务本与老投影）
 * 用紧凑行高，否则舒适行高。**只在用户从未手动选过时**作为初值使用，
 * 不覆盖用户选择 —— 否则会变成"我调好了、下次打开又被改回去"。
 */
export function pickDensityForViewport(height: number): DensityPref {
  return height <= 800 ? 'compact' : 'comfortable'
}

/** 存储里是否已有用户偏好（用于判断能否安全套用视口推荐值）。 */
export function hasStoredUiPrefs(): boolean {
  try {
    return safeGetItem(UI_PREFS_STORAGE_KEY, 'local') !== null
  } catch {
    return false
  }
}

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
    const raw = safeGetItem(UI_PREFS_STORAGE_KEY, 'local')
    if (!raw) return { ...DEFAULT_UI_PREFS }
    return normalizeUiPrefs(JSON.parse(raw))
  } catch {
    return { ...DEFAULT_UI_PREFS }
  }
}

/** 写入偏好（存储不可用静默忽略，内存态仍生效）。 */
export function writeUiPrefs(prefs: UiPrefs): void {
  try {
    safeSetItem(UI_PREFS_STORAGE_KEY, JSON.stringify(prefs), 'local')
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

/** 组合式入口：响应式偏好 + 变更（写存储 + 应用 DOM）+ 预设 + 重置。 */
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
  /** 套用场景预设（一次性覆盖四个字段，不留残余组合）。 */
  const applyPreset = (preset: UiPreset) => apply({ ...UI_PRESETS[preset] })
  const resetPrefs = () => apply({ ...DEFAULT_UI_PREFS })
  const preset = computed(() => matchPreset(prefs.value))
  return { prefs, preset, setPrefs, applyPreset, resetPrefs }
}

/**
 * 应用启动时调用一次（main.ts），把已记忆偏好写回 DOM。
 *
 * 首次使用（无存储）时按视口高度给一个**初始密度**：1366×768 这类政务本
 * 用舒适行高一屏只能看 8 行，先给紧凑更实用；用户一旦手动改过就不再干预。
 */
export function initUiPrefs(): void {
  if (hasStoredUiPrefs()) {
    applyUiPrefsToDom(readUiPrefs())
    return
  }
  const auto: UiPrefs = {
    ...DEFAULT_UI_PREFS,
    density: pickDensityForViewport(
      typeof window !== 'undefined' && typeof window.innerHeight === 'number'
        ? window.innerHeight
        : DEFAULT_VIEWPORT_HEIGHT
    ),
  }
  applyUiPrefsToDom(auto)
  writeUiPrefs(auto)
}

/** 无法读取视口时的保守值（按"政务本"处理，给紧凑密度）。 */
const DEFAULT_VIEWPORT_HEIGHT = 768
