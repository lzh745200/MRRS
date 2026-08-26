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
