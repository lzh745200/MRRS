// T031：轻量甘特图 —— 项目列表视图切换（表格/甘特）
// 零新依赖：复用 echarts 时间轴 + 堆叠条模拟横条，今日线用 markLine。
import type { EChartsOption } from 'echarts'

export interface GanttItem {
  id: string | number
  name: string
  start?: string | null
  end?: string | null
  progress?: number
}

/** 纯日期（YYYY-MM-DD）——只有这种形态才做 '/' 替换（见下） */
const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/

function toTs(s?: string | null): number | null {
  if (!s) return null
  const raw = String(s)
  // 原实现对**所有** '-' 做替换：'2026-09-17T10:00:00Z' → '2026/09/17T10:00:00Z'
  // （Z 被当成本地时间，偏移 8 小时），'2026-09-17T10:00:00-05:00' → '…/05:00' → NaN，
  // 脏值随后进入 hasRange 与条形偏移。只有纯日期串在部分引擎里需要替换成 '/' 才能
  // 稳定按**本地时间**解析，其余原样交给 Date（保留 Z/偏移语义）。
  const normalized = DATE_ONLY_RE.test(raw) ? raw.replace(/-/g, '/') : raw
  const t = new Date(normalized).getTime()
  return Number.isNaN(t) ? null : t
}

export interface GanttRow {
  id: string | number
  name: string
  start: number | null
  end: number | null
  hasRange: boolean
  progress: number
}

export function buildGanttData(items: GanttItem[]): GanttRow[] {
  return (items || []).map((it) => {
    const s = toTs(it.start)
    const e = toTs(it.end)
    const hasRange = s !== null && e !== null && e >= s
    return {
      id: it.id,
      name: it.name,
      start: s,
      end: e,
      hasRange,
      progress: Math.max(0, Math.min(100, Number(it.progress) || 0)),
    }
  })
}

export function buildGanttOption(items: GanttItem[], today = Date.now()): EChartsOption {
  const rows = buildGanttData(items)
  const names = rows.map((r) => r.name)
  // offset 条（透明，定位起点）+ duration 条（可见，按进度着色）
  const offset: any[] = []
  const duration: any[] = []
  rows.forEach((r) => {
    if (r.hasRange) {
      const len = r.end! - r.start!
      offset.push({ value: r.start, itemStyle: { color: 'transparent' } })
      const color = r.progress >= 100 ? '#2d6a4f' : r.progress >= 60 ? '#40916c' : '#d4af37'
      duration.push({ value: len, itemStyle: { color, borderRadius: [3, 3, 3, 3] } })
    } else {
      // 无日期：占位灰条，避免崩溃
      offset.push({ value: today, itemStyle: { color: 'transparent' } })
      duration.push({ value: 1, itemStyle: { color: '#c0c4cc', opacity: 0.4 } })
    }
  })

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 160, right: 40, top: 20, bottom: 30 },
    xAxis: {
      type: 'time',
      axisLabel: { formatter: (v: any) => new Date(v).toLocaleDateString('zh-CN') },
    },
    yAxis: { type: 'category', data: names, inverse: true },
    series: [
      { name: '__offset', type: 'bar', stack: 'g', silent: true, data: offset },
      {
        name: '工期',
        type: 'bar',
        stack: 'g',
        data: duration,
        markLine: {
          symbol: 'none',
          lineStyle: { color: '#e63946', type: 'dashed' },
          data: [{ xAxis: today }],
          label: { formatter: '今日', position: 'end' },
        },
      },
    ],
  }
}
