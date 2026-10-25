/**
 * OCR 识别结果的「字段级建议」（2026-10-25 / ⑤）
 *
 * ## 为什么不是"整段文本贴进来"
 * 后端 `/funds/ocr-voucher` 返回 `{text, amount, date, confidence, engine}`。
 * 原计划只在后端存在（**前端零调用**），现场实际是"识别完还得自己抄进表单"。
 * 本模块把识别结果拆成**逐字段建议**：每个字段显示"当前值 / 识别值 / 置信度"，
 * 由用户逐条采纳或忽略 —— 而不是一次性覆盖表单（覆盖错了更麻烦，且用户不知道改了哪）。
 *
 * ## 置信度策略
 * 引擎给的是整体 confidence，这里按阈值分级：
 * - ≥0.85 高（默认直接推荐采纳）
 * - 0.6~0.85 中（提示核对）
 * - <0.6 低（默认不推荐，需人工确认，通常意味着图片模糊/角度斜）
 */

export interface OcrRawResult {
  text?: string
  amount?: number | string | null
  date?: string | null
  confidence?: number | null
  engine?: string | null
}

export type OcrSuggestionLevel = 'high' | 'medium' | 'low'

export interface OcrFieldSuggestion {
  /** 业务字段名（页面据此写回表单） */
  key: string
  label: string
  /** 识别值（字符串形式，便于直接塞进 input） */
  recognized: string
  /** 表单当前值（用于展示"将会覆盖成什么"） */
  current: string
  level: OcrSuggestionLevel
  /** 是否与当前值相同（相同则无需采纳） */
  same: boolean
}

/** 置信度阈值（导出便于测试与调整）。 */
export const OCR_HIGH_CONFIDENCE = 0.85
export const OCR_LOW_CONFIDENCE = 0.6

export function classifyConfidence(confidence: number | null | undefined): OcrSuggestionLevel {
  const value = typeof confidence === 'number' && Number.isFinite(confidence) ? confidence : 0
  if (value >= OCR_HIGH_CONFIDENCE) return 'high'
  if (value >= OCR_LOW_CONFIDENCE) return 'medium'
  return 'low'
}

/** 金额归一：字符串/数字 → 去掉千分位与货币符号；无有效数字返回空串。 */
export function normalizeOcrAmount(raw: unknown): string {
  if (raw === null || raw === undefined) return ''
  const text = String(raw).replace(/[,，¥￥元\s]/g, '')
  const match = text.match(/-?\d+(\.\d+)?/)
  return match ? match[0] : ''
}

/** 日期归一：兼容 2024-01-02 / 2024/1/2 / 2024年1月2日 → YYYY-MM-DD；不可解析返回空串。 */
export function normalizeOcrDate(raw: unknown): string {
  if (raw === null || raw === undefined) return ''
  const text = String(raw)
  const match = text.match(/(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})/)
  if (!match) return ''
  const [, y, m, d] = match
  const month = String(Number(m)).padStart(2, '0')
  const day = String(Number(d)).padStart(2, '0')
  if (Number(month) < 1 || Number(month) > 12 || Number(day) < 1 || Number(day) > 31) return ''
  return `${y}-${month}-${day}`
}

export interface OcrFieldTarget {
  key: string
  label: string
  /** 该字段取哪个识别结果（目前只有 amount/date 是结构化的） */
  source: 'amount' | 'date'
}

/**
 * 生成字段级建议：只包含"识别出值"的字段（没识别出的字段不出现，
 * 避免列表里全是"—"让人误以为识别失败）。
 */
export function buildOcrSuggestions(
  ocr: OcrRawResult,
  current: Record<string, string>,
  targets: OcrFieldTarget[]
): OcrFieldSuggestion[] {
  const level = classifyConfidence(ocr?.confidence)
  const suggestions: OcrFieldSuggestion[] = []
  for (const target of targets) {
    const recognized =
      target.source === 'amount' ? normalizeOcrAmount(ocr?.amount) : normalizeOcrDate(ocr?.date)
    if (!recognized) continue
    const cur = String(current?.[target.key] ?? '').trim()
    suggestions.push({
      key: target.key,
      label: target.label,
      recognized,
      current: cur,
      level,
      same: cur === recognized,
    })
  }
  return suggestions
}

/** 默认字段映射（经费凭证场景）。 */
export const DEFAULT_OCR_TARGETS: OcrFieldTarget[] = [
  { key: 'amount', label: '金额', source: 'amount' },
  { key: 'transfer_date', label: '划转日期', source: 'date' },
]
