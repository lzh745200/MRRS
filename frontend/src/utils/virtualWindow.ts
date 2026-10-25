/**
 * 窗口化计算（虚拟滚动核心，2026-10-26 / ⑥）
 *
 * 抽成纯函数的原因：虚拟滚动的 bug 几乎全是**边界算术**（首尾各差一行、缓冲区间重叠、
 * 滚到底部时列表突然变短导致跳动）。把它写成纯函数就能穷举测试，
 * 而不是靠"滚动一下看看"。
 */

export interface WindowInput {
  /** 滚动容器的滚动位移（px） */
  scrollTop: number
  /** 可视区高度（px） */
  viewportHeight: number
  /** 单行高度（px，固定行高） */
  itemHeight: number
  /** 数据总数 */
  total: number
  /** 上下各预渲染多少行（减少快速滚动时白屏） */
  buffer?: number
}

export interface WindowRange {
  /** 起始索引（含） */
  start: number
  /** 结束索引（不含） */
  end: number
  /** 顶部占位高度（px） */
  offsetTop: number
  /** 总高度（px） */
  totalHeight: number
}

/**
 * 计算当前应渲染的区间。
 *
 * 边界处理（都是真实会踩的）：
 * - `scrollTop` 为负 / `itemHeight <= 0` / `total <= 0` → 返回空区间，绝不算出负数索引；
 * - 滚到底部时 `end` 必须被 `total` 截断，否则会渲染 `undefined` 行；
 * - 缓冲区不得越界（`start` 不小于 0、`end` 不大于 total）。
 */
export function computeWindow(input: WindowInput): WindowRange {
  const { scrollTop, viewportHeight, itemHeight, total } = input
  const buffer = Math.max(0, input.buffer ?? 3)
  const safeItemHeight = itemHeight > 0 ? itemHeight : 1
  const safeTotal = Math.max(0, Math.floor(total))
  const totalHeight = safeTotal * safeItemHeight

  if (safeTotal === 0) {
    return { start: 0, end: 0, offsetTop: 0, totalHeight: 0 }
  }

  const safeScrollTop = Math.max(0, Math.min(scrollTop, Math.max(0, totalHeight - 1)))
  const first = Math.floor(safeScrollTop / safeItemHeight)
  const visible = Math.ceil(Math.max(0, viewportHeight) / safeItemHeight) + 1

  const start = Math.max(0, first - buffer)
  const end = Math.min(safeTotal, first + visible + buffer)

  return { start, end, offsetTop: start * safeItemHeight, totalHeight }
}

/** 取窗口内的数据切片（保持与 computeWindow 一致的边界语义）。 */
export function sliceWindow<T>(items: readonly T[], range: WindowRange): T[] {
  if (range.end <= range.start) return []
  return items.slice(range.start, range.end)
}
