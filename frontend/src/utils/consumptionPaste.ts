/**
 * 消费帮扶台账「批量粘贴」解析（2026-10-26 / ③）
 *
 * 现场数据多半先在 Excel 里记成一行行台账，再逐条敲进系统。
 * 这里把「粘贴出来的二维数组」翻译成后端 `ConsumptionRecordPayload`，
 * 并且**逐行报告失败原因**（哪一行、为什么），而不是整体失败 ——
 * 否则用户只能全量重来，而重来会重复入库。
 *
 * 列顺序固定且必须与 BulkPasteDialog 的列声明一致：
 * 品类 / 品名 / 数量 / 单位 / 金额 / 购买方 / 销售方 / 年度 / 日期
 *
 * 品类同时接受**中文标签**与**枚举值**：现场人写"农产品"，接口要 `agriculture`。
 */
import {
  CONSUMPTION_CATEGORY_LABELS,
  type ConsumptionCategory,
  type ConsumptionRecordPayload,
} from '@/api/consumption'

/** 与 BulkPasteDialog 的列声明保持同一顺序（改这里必须同步改页面列声明）。 */
export const CONSUMPTION_PASTE_COLUMNS: Array<{ key: string; label: string; required?: boolean }> =
  [
    { key: 'category', label: '品类', required: true },
    { key: 'item_name', label: '品名', required: true },
    { key: 'quantity', label: '数量' },
    { key: 'unit', label: '单位' },
    { key: 'amount', label: '金额', required: true },
    { key: 'buyer', label: '购买方' },
    { key: 'seller', label: '销售方' },
    { key: 'year', label: '年度' },
    { key: 'record_date', label: '日期' },
  ]

const LABEL_TO_CATEGORY: Record<string, ConsumptionCategory> = Object.entries(
  CONSUMPTION_CATEGORY_LABELS
).reduce(
  (acc, [key, label]) => {
    acc[label] = key as ConsumptionCategory
    return acc
  },
  {} as Record<string, ConsumptionCategory>
)

export interface PasteRowError {
  /** 1 基行号（与预览表格的 # 一致） */
  index: number
  message: string
}

export interface ConsumptionPasteResult {
  payloads: ConsumptionRecordPayload[]
  /** 失败行（这些行不会进入 payloads） */
  errors: PasteRowError[]
}

/**
 * 品类：先按中文标签匹配，再按枚举值匹配；都不中返回 null。
 * 参数契约是 `string`（调用方传单元格文本），不写 `?? ''` 这种永不进入的兜底。
 */
export function resolveCategory(raw: string): ConsumptionCategory | null {
  const text = raw.trim()
  if (!text) return null
  if (text in CONSUMPTION_CATEGORY_LABELS) return text as ConsumptionCategory
  return LABEL_TO_CATEGORY[text] ?? null
}

/** 金额：去掉货币符号与千分位后取数字；非正数视为无效。 */
export function parseAmount(raw: string): number | null {
  const text = raw.replace(/[,，¥￥元\s]/g, '')
  if (!text) return null
  const value = Number(text)
  return Number.isFinite(value) && value > 0 ? value : null
}

/** 数量：允许空；非法/负数视为无效（返回 null 表示"这格没填"由调用方决定报不报错）。 */
export function parseQuantity(raw: string): number | null {
  const text = raw.trim()
  if (!text) return null
  const value = Number(text)
  return Number.isFinite(value) && value > 0 ? value : null
}

/** 年度：空 → 默认年；非法 → 默认年（台账里年份写错不值得阻断整批）。 */
export function parseYear(raw: string, defaultYear: number): number {
  const text = raw.trim()
  if (!text) return defaultYear
  const value = Number(text)
  return Number.isInteger(value) && value >= 1990 && value <= 2100 ? value : defaultYear
}

/** 日期：`YYYY-MM-DD` / `YYYY/M/D` / `YYYY年M月D日` → `YYYY-MM-DD`；无法解析 → null。 */
export function parseRecordDate(raw: string): string | null {
  const text = raw.trim()
  if (!text) return null
  const match = text.match(/(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})/)
  if (!match) return null
  const [, y, m, d] = match
  const month = Number(m)
  const day = Number(d)
  if (month < 1 || month > 12 || day < 1 || day > 31) return null
  return `${y}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

/**
 * 把粘贴行翻译成 payload + 逐行错误。
 *
 * 必填校验只做**能确定的**：品类可识别、品名非空、金额为正数。
 * 其余字段（数量/单位/买卖双方/日期）缺失就留空 —— 台账本来就常有空列，
 * 因缺一列就整批拒绝会让这个功能在真实数据上不可用。
 */
export function buildConsumptionPayloads(
  rows: string[][],
  options: { year: number; supportedVillageId?: number | null }
): ConsumptionPasteResult {
  const payloads: ConsumptionRecordPayload[] = []
  const errors: PasteRowError[] = []

  rows.forEach((row, i) => {
    const index = i + 1
    // 行数组可能比列数短（Excel 省略行尾空格），越界按空串处理
    const cell = (n: number) => (row[n] ?? '').trim()

    const category = resolveCategory(cell(0))
    if (!category) {
      errors.push({ index, message: `品类无法识别（"${cell(0) || '空'}"）` })
      return
    }

    const itemName = cell(1)
    if (!itemName) {
      errors.push({ index, message: '品名为空' })
      return
    }

    const amount = parseAmount(cell(4))
    if (amount === null) {
      errors.push({ index, message: `金额无效（"${cell(4) || '空'}"）` })
      return
    }

    payloads.push({
      category,
      item_name: itemName,
      quantity: parseQuantity(cell(2)),
      unit: cell(3) || null,
      amount,
      buyer: cell(5) || null,
      seller: cell(6) || null,
      year: parseYear(cell(7), options.year),
      record_date: parseRecordDate(cell(8)),
      supported_village_id: options.supportedVillageId ?? null,
    })
  })

  return { payloads, errors }
}
