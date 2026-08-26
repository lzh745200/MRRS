/**
 * views/dashboard/ChartRow.vue 补充覆盖（与 ChartRow.test.ts 合并达四指标 100%）
 *
 * 覆盖：loadData 响应多形状（data.items / data.data / items；funds_allocated / total_funds）、
 * buildBarOption 名称与进度字段兜底（name/project_name、progress/completion_rate）、
 * 加载失败自动重试 2s 分支、重试按钮、error 时 renderCharts 早退、
 * 加载中骨架屏、hasFunds=false 暂无数据、renderCharts 空 ref 跳过、dispose 清理。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { chartBox, mockInit, mockApiRequest, mockGet, logError } = vi.hoisted(() => {
  const chartBox: { setOption: any; resize: any; dispose: any; count: number } = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    count: 0,
  }
  return {
    chartBox,
    mockInit: vi.fn(() => {
      chartBox.count++
      return { setOption: chartBox.setOption, dispose: chartBox.dispose, resize: chartBox.resize }
    }),
    mockApiRequest: vi.fn(),
    mockGet: vi.fn(),
    logError: vi.fn(),
  }
})

vi.mock('@/utils/echarts', () => ({
  default: {
    init: mockInit,
    graphic: { LinearGradient: vi.fn(() => ({})) },
  },
}))

vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  default: {},
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import ChartRow from '@/views/dashboard/ChartRow.vue'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'

const mockSetOption = chartBox.setOption
const mockResize = chartBox.resize
const mockDispose = chartBox.dispose

function mountChart() {
  return mount(ChartRow, {
    global: {
      stubs: {
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-icon': { template: '<span><slot /></span>' },
        'el-skeleton': { template: '<div class="skeleton-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ChartRow 数据形状', () => {
  it('loadData：data.items 项目 + funds_allocated 经费 → 渲染双图', async () => {
    mockApiRequest.mockResolvedValue({
      data: { items: [{ name: '道路', progress: 85 }] },
    })
    mockGet.mockResolvedValue({ funds_allocated: 100, funds_pending: 20, funds_planned: 10 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.projects).toEqual([{ name: '道路', progress: 85 }])
    expect(vm.funds).toEqual({ allocated: 100, pending: 20, planned: 10 })
    // 双图 setOption 均调用（bar + pie）
    expect(mockSetOption.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(wrapper.findAll('.chart-body').length).toBe(2)
    wrapper.unmount()
  })

  it('项目字段兜底：project_name / completion_rate；经费 total_funds 兜底', async () => {
    mockApiRequest.mockResolvedValue({
      data: { items: [{ project_name: '桥梁', completion_rate: 60 }] },
    })
    mockGet.mockResolvedValue({ total_funds: 5000 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.projects[0].project_name).toBe('桥梁')
    expect(vm.funds).toEqual({ allocated: 5000, pending: 0, planned: 0 })
    // 仅 bar 图（funds 只有 allocated 且为 0 时 hasFunds 为假——此处 allocated=5000 为真）
    expect(mockSetOption.mock.calls.length).toBeGreaterThanOrEqual(2)
    wrapper.unmount()
  })

  it('项目字段全缺：name/project_name 均无 → 空串；progress/completion_rate 均无 → 0', async () => {
    mockApiRequest.mockResolvedValue({
      data: { items: [{ id: 1 }, { name: '有名字', progress: 40 }] },
    })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    // 无名称无进度 → '' / 0；混合行 → name/progress 左支
    const names = mockSetOption.mock.calls.map((c: any) => c[0]?.yAxis?.data)
    expect(names).toContainEqual(['有名字', ''])
    const values = mockSetOption.mock.calls.map((c: any) => c[0]?.series?.[0]?.data)
    expect(values).toContainEqual([40, 0])
    wrapper.unmount()
  })

  it('响应形状：projRes.data.data 嵌套、items 直返；funds 对象缺失 → 全 0', async () => {
    mockApiRequest.mockResolvedValue({ data: { data: [{ name: 'Y', progress: 20 }] } })
    mockGet.mockResolvedValue({})
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.projects).toEqual([{ name: 'Y', progress: 20 }])
    expect(vm.funds).toEqual({ allocated: 0, pending: 0, planned: 0 })
    wrapper.unmount()

    mockApiRequest.mockResolvedValue({ items: [{ name: 'X', progress: 10 }] })
    mockGet.mockResolvedValue({})
    const wrapper2 = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper2.vm as any).projects).toEqual([{ name: 'X', progress: 10 }])
    expect(wrapper2.findAll('.chart-body').length).toBe(1)
    wrapper2.unmount()
    // 无 items 也无 data → || [] 右侧兜底
    mockApiRequest.mockResolvedValue({})
    mockGet.mockResolvedValue({})
    const wrapper3 = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper3.vm as any).projects).toEqual([])
    wrapper3.unmount()
  })

  it('renderCharts 二次渲染：已有图表 → dispose 后重建；数据全空 → null 安全跳过', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const before = chartBox.count
    // 二次 loadAndRender → renderCharts 先 dispose 已存在图表
    await (wrapper.vm as any).loadAndRender()
    await flushPromises()
    await nextTick()
    expect(chartBox.count).toBeGreaterThan(before)
    wrapper.unmount()

    // 数据全空 → hasProjects/hasFunds 均为假 → 无图表可初始化，null 安全
    mockApiRequest.mockResolvedValue({ data: { items: [] } })
    mockGet.mockResolvedValue({ funds_allocated: 0, funds_pending: 0, funds_planned: 0 })
    chartBox.setOption.mockClear()
    const wrapper2 = mountChart()
    await flushPromises()
    await nextTick()
    expect(wrapper2.findAllComponents(EmptyState).length).toBe(2)
    expect(
      wrapper2
        .findAllComponents(EmptyState)
        .some((e) => e.props('text') === '暂无项目数据'),
    ).toBe(true)
    expect(mockSetOption).not.toHaveBeenCalled()
    wrapper2.unmount()
  })

  it('经费全 0 且项目非空 → 第二卡片显示暂无数据', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'X', progress: 10 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 0, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const covEmpties = wrapper.findAllComponents(EmptyState)
    expect(covEmpties.length).toBe(1)
    expect(covEmpties[0].props('text')).toBe('暂无经费数据')
    wrapper.unmount()
  })

  it('buildPieOption 饼图 tooltip formatter 执行', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'X', progress: 10 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 100, funds_pending: 20, funds_planned: 10 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const pieOpt = mockSetOption.mock.calls.find(
      (c: any) => c[0]?.series?.[0]?.type === 'pie'
    )?.[0]
    expect(pieOpt).toBeTruthy()
    const formatter = pieOpt.tooltip.formatter
    const html = formatter({ marker: '<span>', name: '已拨付', value: 100, percent: 76.9 })
    expect(html).toContain('100万')
    expect(html).toContain('76.9%')
    wrapper.unmount()
  })
})

describe('ChartRow 加载状态', () => {
  it('加载中显示骨架屏；完成后隐藏', async () => {
    let resolveProj!: (v: any) => void
    let resolveFund!: (v: any) => void
    mockApiRequest.mockImplementation(() => new Promise((r) => (resolveProj = r)))
    mockGet.mockImplementation(() => new Promise((r) => (resolveFund = r)))
    const wrapper = mountChart()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(2)
    expect((wrapper.vm as any).loading).toBe(true)
    resolveProj({ data: { items: [{ name: 'A', progress: 1 }] } })
    resolveFund({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    await flushPromises()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(0)
    wrapper.unmount()
  })

  it('加载失败 → error 置位、自动 2s 重试成功后恢复', async () => {
    vi.useFakeTimers()
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    mockGet.mockRejectedValueOnce(new Error('net'))
    mockApiRequest.mockResolvedValueOnce({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValueOnce({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.error).toBe(true)
    expect(wrapper.findAll('.chart-state--error').length).toBe(2)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    await nextTick()
    expect(vm.error).toBe(false)
    expect(wrapper.findAll('.chart-state--error').length).toBe(0)
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('重试按钮：仍失败 → error 保持（renderCharts 早退）；成功 → 恢复', async () => {
    mockApiRequest.mockRejectedValue(new Error('still down'))
    mockGet.mockRejectedValue(new Error('still down'))
    const wrapper = mountChart()
    await flushPromises()
    expect(wrapper.findAll('.chart-state--error').length).toBe(2)
    expect(mockSetOption).not.toHaveBeenCalled()

    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    await wrapper.findAll('.chart-state--error .el-button-stub')[0].trigger('click')
    await flushPromises()
    await nextTick()
    expect((wrapper.vm as any).error).toBe(false)
    expect(mockSetOption.mock.calls.length).toBeGreaterThanOrEqual(2)
    wrapper.unmount()
  })

  it('unmount：移除 resize 监听并 dispose 图表', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    window.dispatchEvent(new Event('resize'))
    expect(mockResize).toHaveBeenCalled()
    wrapper.unmount()
    expect(mockDispose).toHaveBeenCalled()
  })
})
