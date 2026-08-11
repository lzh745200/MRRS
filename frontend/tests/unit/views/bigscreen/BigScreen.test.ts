import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getDashboardStats: vi.fn(),
  getYearlyTrends: vi.fn(),
  getRankings: vi.fn(),
  getSummaryStatistics: vi.fn(),
}))

vi.mock('@/api/dashboard', () => ({
  getDashboardStats: mocks.getDashboardStats,
  getYearlyTrends: mocks.getYearlyTrends,
}))

vi.mock('@/api/effectiveness', () => ({
  getRankings: mocks.getRankings,
}))

vi.mock('@/api/analytics', () => ({
  getSummaryStatistics: mocks.getSummaryStatistics,
}))

vi.mock('@/components/common/BaseChart.vue', () => ({
  default: { name: 'BaseChart', template: '<div class="chart-stub" />' },
}))

import BigScreen from '@/views/bigscreen/BigScreen.vue'

function mountComp() {
  return mount(BigScreen, { attachTo: document.body })
}

describe('BigScreen.vue（帮扶成效大屏）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    mocks.getDashboardStats.mockResolvedValue({
      total_villages: 12,
      total_projects: 34,
      total_schools: 5,
      completion_rate: 88,
      total_amount: 123.4,
    })
    mocks.getYearlyTrends.mockResolvedValue({
      trends: [
        { year: 2024, total_planned: 100, total_actual: 80, project_count: 5 },
        { year: 2025, total_planned: 120, total_actual: 110, project_count: 8 },
      ],
    })
    mocks.getRankings.mockResolvedValue({
      year: 2026,
      rankings: [
        { village_name: '甲村', score: 92 },
        { village_name: '乙村', score: 85 },
      ],
    })
    mocks.getSummaryStatistics.mockResolvedValue({
      by_status: { completed: 10, active: 8 },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('挂载加载数据并渲染 KPI 与图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.getDashboardStats).toHaveBeenCalledWith(true)
    expect(mocks.getYearlyTrends).toHaveBeenCalledWith(5)
    expect(mocks.getRankings).toHaveBeenCalled()
    expect(mocks.getSummaryStatistics).toHaveBeenCalled()
    expect(wrapper.text()).toContain('帮扶成效总览大屏')
    const vm = wrapper.vm as any
    expect(vm.kpis.length).toBe(5)
    expect(vm.kpis[1].value).toBe(34)
    expect(wrapper.findAll('.chart-stub').length).toBe(4)
    wrapper.unmount()
  })

  it('接口失败静默降级（KPI 默认 0）', async () => {
    mocks.getDashboardStats.mockRejectedValue(new Error('net'))
    mocks.getYearlyTrends.mockRejectedValue(new Error('net'))
    mocks.getRankings.mockRejectedValue(new Error('net'))
    mocks.getSummaryStatistics.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.kpis[0].value).toBe(0)
    expect(vm.rankings).toEqual([])
    expect(vm.yearlyOption.series[0].data).toEqual([])
    wrapper.unmount()
  })

  it('时钟每秒更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.clock
    expect(before).toMatch(/^\d{4}-\d{2}-\d{2}/)
    vi.advanceTimersByTime(1000)
    expect(vm.clock).toMatch(/^\d{4}-\d{2}-\d{2}/)
    wrapper.unmount()
  })

  it('图表 computed: 排名/项目状态/年度数据组装', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 排名条形图
    expect(vm.rankOption.yAxis.data).toContain('甲村')
    expect(vm.rankOption.series[0].data).toContain(92)
    // 项目状态饼图
    expect(vm.projectStatusOption.series[0].data.length).toBe(2)
    // 年度柱状图
    expect(vm.yearlyOption.xAxis.data).toContain(2025)
    expect(vm.yearlyOption.series[0].data).toEqual([5, 8])
    // 经费趋势
    expect(vm.fundTrendOption.series.length).toBe(2)
    wrapper.unmount()
  })

  it('状态图对未知状态键回退显示原始键', async () => {
    mocks.getSummaryStatistics.mockResolvedValue({ by_status: { weird: 3 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.projectStatusOption.series[0].data[0].name).toBe('weird')
    wrapper.unmount()
  })

  it('全屏切换与 fullscreenchange 监听', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // requestFullscreen mock
    const origReq = document.documentElement.requestFullscreen
    const origExit = document.exitFullscreen
    ;(document.documentElement as any).requestFullscreen = vi.fn(() => Promise.resolve())
    ;(document as any).exitFullscreen = vi.fn(() => Promise.resolve())
    Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true, writable: true })
    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(true)
    ;(document as any).fullscreenElement = document.documentElement
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(true)
    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(false)
    ;(document as any).fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(false)
    ;(document.documentElement as any).requestFullscreen = origReq
    ;(document as any).exitFullscreen = origExit
    wrapper.unmount()
  })

  it('卸载时清理定时器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    wrapper.unmount()
    vi.advanceTimersByTime(1000) // 不应报错
  })

  it('字段缺失形态：?? 链全部走兜底侧（直接改写 ref 值）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // stats 为 null → stats.value ?? {} 兜底 → KPI 全 0 / 完成率 '—'
    vm.stats = null
    expect(vm.kpis.map((k: any) => k.value)).toEqual([0, 0, 0, '—', 0])
    // yearlyTrends 为 null → ?? [] 兜底
    vm.yearlyTrends = null
    expect(vm.fundTrendOption.xAxis.data).toEqual([])
    expect(vm.fundTrendOption.series[0].data).toEqual([])
    expect(vm.yearlyOption.xAxis.data).toEqual([])
    // rankings 为 null → ?? [] 兜底
    vm.rankings = null
    expect(vm.rankOption.yAxis.data).toEqual([])
    // summary 为 null → ?? {} 兜底 → 空饼图
    vm.summary = null
    expect(vm.projectStatusOption.series[0].data).toEqual([])
    // 年度数据：year 缺失 + planned/actual/count 两级 ?? 兜底
    vm.yearlyTrends = [
      { planned: 50, actual: 40, count: 5 }, // year 缺 → ''；total_planned 缺 → planned；total_actual 缺 → actual；project_count 缺 → count
      { year: 2026 }, // planned/actual/count 全缺 → 0
    ]
    expect(vm.fundTrendOption.xAxis.data).toEqual(['', 2026])
    expect(vm.fundTrendOption.series[0].data).toEqual([50, 0])
    expect(vm.fundTrendOption.series[1].data).toEqual([40, 0])
    expect(vm.yearlyOption.series[0].data).toEqual([5, 0])
    // 排名：village_name/name/village_id 三级 ?? 兜底 + score/total_score 两级 ?? 兜底
    vm.rankings = [
      { name: '甲', total_score: 9 },
      { village_id: 'v1' },
      {},
    ]
    expect(vm.rankOption.yAxis.data).toEqual(['甲', 'v1', ''])
    expect(vm.rankOption.series[0].data).toEqual([9, 0, 0])
    // 状态图：计数为 0 → Number(v) || 0 兜底
    vm.summary = { by_status: { completed: 0, active: 8 } }
    expect(vm.projectStatusOption.series[0].data).toEqual([
      { name: '已完成', value: 0 },
      { name: '进行中', value: 8 },
    ])
    wrapper.unmount()
  })

  it('loadAll：接口全部返回 null → 静默兜底空对象/空数组', async () => {
    mocks.getDashboardStats.mockResolvedValue(null)
    mocks.getYearlyTrends.mockResolvedValue(null)
    mocks.getRankings.mockResolvedValue(null)
    mocks.getSummaryStatistics.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats).toEqual({})
    expect(vm.yearlyTrends).toEqual([])
    expect(vm.rankings).toEqual([])
    expect(vm.summary).toEqual({})
    wrapper.unmount()
  })

  it('rankings 数组直返 / items 旧格式兼容（Array.isArray 与双字段兜底）', async () => {
    // 数组直返
    mocks.getRankings.mockResolvedValue([{ village_name: '丙村', score: 77 }])
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    expect(vm.rankings).toEqual([{ village_name: '丙村', score: 77 }])
    expect(vm.rankOption.yAxis.data).toContain('丙村')
    wrapper.unmount()
    // items 旧格式（历史客户端兼容）
    mocks.getRankings.mockResolvedValue({ items: [{ village_name: '丁村', score: 66 }] })
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    expect(vm.rankings).toEqual([{ village_name: '丁村', score: 66 }])
    expect(vm.rankOption.yAxis.data).toContain('丁村')
    wrapper.unmount()
  })

  it('yearlyTrends 数组直返兼容', async () => {
    mocks.getYearlyTrends.mockResolvedValue([{ year: 2023, total_planned: 60 }])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.yearlyTrends).toEqual([{ year: 2023, total_planned: 60 }])
    expect(vm.fundTrendOption.xAxis.data).toContain(2023)
    wrapper.unmount()
  })

  it('rankings 返回无 rankings/items 字段的对象 → 空数组兜底（不崩溃）', async () => {
    mocks.getRankings.mockResolvedValue({ error: 'no data' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankings).toEqual([])
    expect(vm.rankOption.yAxis.data).toEqual([])
    wrapper.unmount()
  })
})
