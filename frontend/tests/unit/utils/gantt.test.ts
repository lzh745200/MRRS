import { describe, expect, it } from 'vitest'
import { buildGanttData, buildGanttOption, type GanttItem } from '@/utils/gantt'

const items: GanttItem[] = [
  { id: 1, name: '项目A', start: '2024-01-01', end: '2024-03-01', progress: 80 },
  { id: 2, name: '项目B', start: '2024-02-01', end: '2024-02-15', progress: 100 },
  { id: 3, name: '项目C', start: null, end: null, progress: 0 },
  { id: 4, name: '项目D', start: 'bad', end: '2024-05-01', progress: 30 },
]

describe('buildGanttData (T031)', () => {
  const rows = buildGanttData(items)
  it('映射名称与进度', () => {
    expect(rows[0].name).toBe('项目A')
    expect(rows[0].progress).toBe(80)
  })
  it('有效区间 hasRange=true', () => {
    expect(rows[0].hasRange).toBe(true)
    expect(rows[1].hasRange).toBe(true)
  })
  it('无日期回退 hasRange=false 不崩溃', () => {
    expect(rows[2].hasRange).toBe(false)
  })
  it('非法日期回退 hasRange=false', () => {
    expect(rows[3].hasRange).toBe(false)
  })
  it('进度越界被夹取到 0~100', () => {
    const over = buildGanttData([{ id: 9, name: 'x', progress: 200 }])
    expect(over[0].progress).toBe(100)
  })
})

describe('buildGanttOption (T031)', () => {
  it('生成时间轴堆叠条 + 今日线', () => {
    const opt = buildGanttOption(items, new Date('2024-02-10').getTime()) as any
    expect(opt.xAxis.type).toBe('time')
    expect(opt.yAxis.data.length).toBe(4)
    // 2 条 series：offset + duration（含 markLine）
    expect(opt.series.length).toBe(2)
    expect(opt.series[1].markLine.data[0].xAxis).toBe(new Date('2024-02-10').getTime())
  })
  it('无日期项 duration 用占位灰条值=1', () => {
    const opt = buildGanttOption(items) as any
    // 项目C 无日期 -> duration 值 1
    expect(opt.series[1].data[2].value).toBe(1)
  })
  it('空数组不崩溃', () => {
    const opt = buildGanttOption([]) as any
    expect(opt.yAxis.data.length).toBe(0)
    expect(opt.series[1].data.length).toBe(0)
  })
})

/**
 * 补齐 buildGanttData / buildGanttOption 的剩余分支与回调。
 */
describe('buildGanttData 防御分支', () => {
  it('items 为 null/undefined 时走 `items || []` 兜底，返回空数组', () => {
    // 后端列表接口异常或视图未就绪时会把 undefined 传进来；
    // 源码用 `(items || [])` 兜底，此用例锁定该兜底不被误删。
    expect(buildGanttData(undefined as unknown as GanttItem[])).toEqual([])
    expect(buildGanttData(null as unknown as GanttItem[])).toEqual([])
    // 经由 buildGanttOption 的间接调用路径同样不崩溃
    const opt = buildGanttOption(undefined as unknown as GanttItem[]) as any
    expect(opt.yAxis.data).toEqual([])
    expect(opt.series[1].data).toEqual([])
  })

  it('progress 缺失/非法时回退 0，负值被夹取到 0', () => {
    expect(buildGanttData([{ id: 1, name: 'a' }])[0].progress).toBe(0)
    expect(buildGanttData([{ id: 1, name: 'a', progress: NaN }])[0].progress).toBe(0)
    expect(buildGanttData([{ id: 1, name: 'a', progress: -20 }])[0].progress).toBe(0)
  })

  it('end < start（脏数据倒挂区间）视为 hasRange=false', () => {
    const rows = buildGanttData([
      { id: 1, name: '倒挂', start: '2024-05-01', end: '2024-01-01', progress: 50 },
    ])
    expect(rows[0].hasRange).toBe(false)
  })
})

describe('buildGanttOption 进度着色三档 + 时间轴 formatter', () => {
  /** 三档色阶：>=100 深绿、>=60 中绿、<60 金色（预警） */
  const graded: GanttItem[] = [
    { id: 'done', name: '已完成', start: '2024-01-01', end: '2024-02-01', progress: 100 },
    { id: 'mid', name: '过半', start: '2024-01-01', end: '2024-02-01', progress: 60 },
    { id: 'low', name: '滞后', start: '2024-01-01', end: '2024-02-01', progress: 30 },
  ]

  it('progress>=100 → #2d6a4f；>=60 → #40916c；<60 → #d4af37', () => {
    const opt = buildGanttOption(graded, new Date('2024-01-15').getTime()) as any
    const bars = opt.series[1].data
    expect(bars[0].itemStyle.color).toBe('#2d6a4f')
    expect(bars[1].itemStyle.color).toBe('#40916c')
    // <60 的金色档此前无用例触达（既有 fixture 的 hasRange=true 项进度只有 80/100）
    expect(bars[2].itemStyle.color).toBe('#d4af37')
    // 三档均为真实工期长度（非占位灰条），确认着色分支取自有区间的行
    expect(bars[0].value).toBeGreaterThan(1)
    expect(bars[0].itemStyle.borderRadius).toEqual([3, 3, 3, 3])
  })

  it('progress=0 且有区间 → 仍走金色档（0 为合法进度，不回退占位灰）', () => {
    const opt = buildGanttOption(
      [{ id: 'z', name: '未开工', start: '2024-01-01', end: '2024-03-01', progress: 0 }]
    ) as any
    expect(opt.series[1].data[0].itemStyle.color).toBe('#d4af37')
    expect(opt.series[1].data[0].itemStyle.opacity).toBeUndefined()
  })

  it('xAxis.axisLabel.formatter 把时间戳格式化为 zh-CN 本地日期', () => {
    const opt = buildGanttOption(graded) as any
    const formatter = opt.xAxis.axisLabel.formatter
    expect(typeof formatter).toBe('function')
    // formatter 仅由 echarts 渲染时回调，单测需直接调用以覆盖
    const ts = new Date(2024, 4, 20).getTime()
    expect(formatter(ts)).toBe(new Date(ts).toLocaleDateString('zh-CN'))
    expect(formatter(ts)).toContain('2024')
  })

  it('offset 条透明且值等于起始时间戳；无区间项回退 today', () => {
    const today = new Date('2024-06-01').getTime()
    const opt = buildGanttOption(
      [
        { id: 'a', name: '有区间', start: '2024-01-01', end: '2024-02-01', progress: 70 },
        { id: 'b', name: '无区间', progress: 70 },
      ],
      today
    ) as any
    // toTs 内部把 '2024-01-01' 改写为 '2024/01/01' 再 new Date()，
    // 得到的是【本地】零点（而 new Date('2024-01-01') 是 UTC 零点），
    // 故断言必须用本地构造式，避开时区差导致的偏差。
    expect(opt.series[0].data[0].value).toBe(new Date(2024, 0, 1).getTime())
    expect(opt.series[0].data[0].itemStyle.color).toBe('transparent')
    expect(opt.series[0].data[1].value).toBe(today)
    expect(opt.series[0].silent).toBe(true)
    // 无区间项：占位灰条
    expect(opt.series[1].data[1].itemStyle).toEqual({ color: '#c0c4cc', opacity: 0.4 })
    expect(opt.series[1].markLine.label).toEqual({ formatter: '今日', position: 'end' })
  })
})
