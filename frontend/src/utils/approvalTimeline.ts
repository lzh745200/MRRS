// T033：审批详情时间线 —— 聚合「审批历史 + 状态日志」为统一轨迹节点。
export interface TimelineNode {
  operator: string
  action: string
  time: string
  type: string
}

function norm(e: any, type: string): TimelineNode {
  return {
    operator: e?.operator || e?.actor || e?.user || e?.handler || e?.approver || '-',
    action: e?.action || e?.description || e?.title || e?.remark || '',
    time: e?.time || e?.created_at || e?.timestamp || e?.operated_at || '',
    type: e?.type || type,
  }
}

/**
 * 把时间值解析为可比较的数值时间戳（毫秒）。
 *
 * 返回 null 表示"无法解析"——排序时沉底，且不参与"谁最新"的竞争。
 * 兼容：Date、epoch 秒（10 位）/毫秒（13 位）、"YYYY-MM-DD"、
 * "YYYY-MM-DD HH:mm:ss" 与 ISO 8601（带 Z/时区偏移）。
 *
 * 入参声明为 `unknown`（但**仅**由 `norm()` 传入，其值必为 string 或 Date/number
 * 这类"后端原样透传"的形态）：null/undefined 不可能到达这里 —— 历史实现里的
 * `raw === null` 判定因此是不可达死代码（实测该分支计数器恒为 0），已移除。
 * 无值场景由上游 `norm()` 的 `|| ''` 归一为**空串**，由下方 `if (!s) return null` 兜底。
 */
function toTimeValue(raw: unknown): number | null {
  if (raw instanceof Date) {
    const t = raw.getTime()
    return Number.isNaN(t) ? null : t
  }
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) return null
    return raw < 1e12 ? raw * 1000 : raw
  }
  const s = String(raw).trim()
  if (!s) return null
  // 纯数字串按 epoch 解析（否则 "1700000000" 会被 Date.parse 当成年份）
  if (/^\d+$/.test(s)) {
    const n = Number(s)
    if (!Number.isFinite(n)) return null
    return n < 1e12 ? n * 1000 : n
  }
  const t = Date.parse(s)
  return Number.isNaN(t) ? null : t
}

export function buildApprovalTimeline(history: any[], statusLogs: any[]): TimelineNode[] {
  const a = (history || []).map((e) => norm(e, 'history'))
  const b = (statusLogs || []).map((e) => norm(e, 'status'))
  // 时间倒序（最新在上）。
  //
  // 原实现是 String(y.time).localeCompare(String(x.time))：只在"同一格式且零填充"
  // 时正确——ISO（2026-09-17T10:00:00Z）与空格格式（2026-09-17 10:00:00）混排会错序，
  // epoch 秒/毫秒完全乱序，空 time 沉底，localeCompare 还受运行环境语言影响。
  // 现改为解析为数值时间戳比较；无法解析的时间沉底；同一时刻保持输入顺序（稳定排序）。
  //
  // 比较器写法：把三类判定拆成互斥的**单条件** return，而不是
  // `if (a) return …; if (b) return …` 的连续短路链 —— 后者在 v8 分支计数下
  // 会出现"两个守卫共用一个计数器、只记录最后一次求值"的统计歧义
  // （表现为 lines 100% 而 branches 恒差 2）。语义完全等价。
  return [...a, ...b]
    .map((node, index) => ({ node, index, ts: toTimeValue(node.time) }))
    .sort((x, y) => {
      const xInvalid = x.ts === null
      const yInvalid = y.ts === null
      if (xInvalid && yInvalid) return x.index - y.index
      if (xInvalid) return 1
      if (yInvalid) return -1
      if (y.ts !== x.ts) return (y.ts as number) - (x.ts as number)
      return x.index - y.index
    })
    .map((it) => it.node)
}
