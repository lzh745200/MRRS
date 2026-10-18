/**
 * 大屏配置（卡片取舍与顺序 / 自动刷新频率 / 汇报脱敏）。
 *
 * 持久化到 localStorage（浏览器本地、按角色/汇报现场自行调整），
 * 读取时对损坏 JSON、未知卡片 key、重复卡片、非法刷新频率等一律
 * 归一化回安全默认值 —— 配置永远可解析，绝不让大屏白屏。
 */
import { maskName } from '@/utils/desensitize'

/** localStorage 配置键 */
export const BIGSCREEN_CONFIG_KEY = 'bigscreen:config'

/** 可配置的自动刷新频率选项（0 = 关闭自动刷新） */
export const REFRESH_OPTIONS = [
  { value: 30, label: '30 秒' },
  { value: 60, label: '60 秒' },
  { value: 300, label: '5 分钟' },
  { value: 0, label: '关闭自动刷新' },
] as const

/** 刷新频率（秒），0 表示不轮询 */
export type RefreshInterval = (typeof REFRESH_OPTIONS)[number]['value']

/** 频率 → 文案映射（避免渲染期再做查找兜底） */
export const REFRESH_LABELS: Record<number, string> = Object.fromEntries(
  REFRESH_OPTIONS.map((option) => [option.value, option.label])
) as Record<number, string>

/** 大屏卡片定义（顺序即默认渲染顺序） */
export const BIG_SCREEN_CARDS = [
  { key: 'fundTrend', title: '经费执行趋势', wide: true },
  { key: 'rank', title: '帮扶成效排名', wide: false },
  { key: 'projectStatus', title: '项目状态分布', wide: false },
  { key: 'yearly', title: '年度对比', wide: false },
  { key: 'leaders', title: '重点项目负责人', wide: false },
] as const

/** 卡片 key 联合类型 */
export type BigScreenCardKey = (typeof BIG_SCREEN_CARDS)[number]['key']

/** 单张卡片配置 */
export interface BigScreenCardConfig {
  key: BigScreenCardKey
  title: string
  wide: boolean
  visible: boolean
}

/** 大屏完整配置 */
export interface BigScreenConfig {
  cards: BigScreenCardConfig[]
  refreshInterval: RefreshInterval
  desensitized: boolean
}

/** 默认配置：全部卡片可见、30 秒刷新、不脱敏 */
export function defaultBigScreenConfig(): BigScreenConfig {
  return {
    cards: BIG_SCREEN_CARDS.map((card) => ({ ...card, visible: true })),
    refreshInterval: 30,
    desensitized: false,
  }
}

/** 刷新频率归一化：非法值一律回落 30 秒 */
export function normalizeRefreshInterval(value: unknown): RefreshInterval {
  return REFRESH_OPTIONS.some((option) => option.value === value) ? (value as RefreshInterval) : 30
}

/**
 * 配置归一化：
 * - cards 按保存顺序保留「已知且不重复」的卡片，缺失卡片按默认顺序追加且可见；
 * - refreshInterval 非法 → 30 秒；
 * - desensitized 仅接受严格 true。
 */
export function normalizeBigScreenConfig(raw: unknown): BigScreenConfig {
  const fallback = defaultBigScreenConfig()
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return fallback
  const data = raw as Record<string, unknown>

  const cardDefs = new Map(BIG_SCREEN_CARDS.map((card) => [card.key, card]))
  const cards: BigScreenCardConfig[] = []
  const seen = new Set<string>()
  if (Array.isArray(data.cards)) {
    for (const item of data.cards) {
      if (!item || typeof item !== 'object') continue
      const key = (item as Record<string, unknown>).key
      if (typeof key !== 'string' || !cardDefs.has(key as BigScreenCardKey) || seen.has(key)) {
        continue
      }
      const def = cardDefs.get(key as BigScreenCardKey)!
      seen.add(key)
      cards.push({ ...def, visible: (item as Record<string, unknown>).visible !== false })
    }
  }
  for (const def of BIG_SCREEN_CARDS) {
    if (!seen.has(def.key)) cards.push({ ...def, visible: true })
  }

  return {
    cards,
    refreshInterval: normalizeRefreshInterval(data.refreshInterval),
    desensitized: data.desensitized === true,
  }
}

/** 读取配置（损坏 / 缺失 → 默认配置） */
export function loadBigScreenConfig(storage: Storage = localStorage): BigScreenConfig {
  try {
    const raw = storage.getItem(BIGSCREEN_CONFIG_KEY)
    if (!raw) return defaultBigScreenConfig()
    return normalizeBigScreenConfig(JSON.parse(raw))
  } catch {
    return defaultBigScreenConfig()
  }
}

/** 保存配置（存储不可用 / 配额满 → 静默降级） */
export function saveBigScreenConfig(
  config: BigScreenConfig,
  storage: Storage = localStorage
): void {
  try {
    storage.setItem(BIGSCREEN_CONFIG_KEY, JSON.stringify(config))
  } catch {
    /* 隐私模式 / 配额满：配置仅本次会话生效 */
  }
}

/** 脱敏模式：隐藏金额精度（四舍五入到整数；非法值回落 0） */
export function hideAmountPrecision(value: unknown): number {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return 0
  return Math.round(n)
}

/**
 * 负责人姓名展示：脱敏模式下按 `maskName` 打码（保留首尾字符），
 * 空值统一占位符，避免页面出现 "undefined"。
 */
export function formatLeaderName(name: string | null | undefined, desensitized: boolean): string {
  if (name === null || name === undefined || name === '') return '—'
  return desensitized ? maskName(name) : name
}
