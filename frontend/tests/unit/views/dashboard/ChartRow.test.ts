/**
 * views/dashboard/ChartRow.vue 唯一执行者测试（W23 W4，四指标 100%）
 *
 * 覆盖：双图容器（.app-card）/ echarts 初始化与 resize / dispose、加载三件套
 * （.app-loading 骨架、.app-error 重试、.app-empty 空态）、失败自动 2s 重试、
 * 项目与经费字段兜底、经费 allocated=0 不回退 total_funds、饼图 tooltip 格式。
 * 注：合并原 ChartRowCov.test.ts 的补充覆盖，保证单执行者。
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
      return {
        setOption: chartBox.setOption,
        dispose: chartBox.dispose,
        resize: chartBox.resize,
      }
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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import ChartRow from '@/views/dashboard/ChartRow.vue'

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
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('ChartRow 渲染与数据形状', () => {
  it('两张 .app-card 图表卡 + 双图 setOption（data.items / funds_allocated）', async () => {
    mockApiRequest.mockResolvedValue({
      data: { items: [{ name: '道路', progress: 85 }] },
    })
    mockGet.mockResolvedValue({ funds_allocated: 100, funds_pending: 20, funds_planned: 10 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(wrapper.findAll('.chart-card').length).toBe(2)
    expect(wrapper.findAll('.app-card').length).toBe(2)
    expect(vm.projects).toEqual([{ name: '道路', progress: 85 }])
    expect(vm.funds).toEqual({ allocated: 100, pending: 20, planned: 10 })
    // W8-018 清理锁定：/projects 请求只带 page_size，不得有幽灵 summary 参数
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/projects',
      params: { page_size: 5 },
    })
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
    expect(mockSetOption.mock.calls.length).toBeGreaterThanOrEqual(2)
    wrapper.unmount()
  })

  it('funds_allocated 合法为 0 时不得回退 total_funds（防已拨付虚增）', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [] } })
    mockGet.mockResolvedValue({ funds_allocated: 0, total_funds: 5000, funds_pending: 20 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper.vm as any).funds).toEqual({ allocated: 0, pending: 20, planned: 0 })
    wrapper.unmount()
  })

  it('字段全缺兜底：name/project_name → 空串；progress/completion_rate → 0', async () => {
    mockApiRequest.mockResolvedValue({
      data: { items: [{ id: 1 }, { name: '有名字', progress: 40 }] },
    })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const names = mockSetOption.mock.calls.map((c: any) => c[0]?.yAxis?.data)
    expect(names).toContainEqual(['有名字', ''])
    const values = mockSetOption.mock.calls.map((c: any) => c[0]?.series?.[0]?.data)
    expect(values).toContainEqual([40, 0])
    wrapper.unmount()
  })

  it('响应形状：data.data 嵌套 / items 直返 / 空对象兜底 []', async () => {
    mockApiRequest.mockResolvedValue({ data: { data: [{ name: 'Y', progress: 20 }] } })
    mockGet.mockResolvedValue({})
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper.vm as any).projects).toEqual([{ name: 'Y', progress: 20 }])
    expect((wrapper.vm as any).funds).toEqual({ allocated: 0, pending: 0, planned: 0 })
    wrapper.unmount()

    mockApiRequest.mockResolvedValue({ items: [{ name: 'X', progress: 10 }] })
    mockGet.mockResolvedValue({})
    const wrapper2 = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper2.vm as any).projects).toEqual([{ name: 'X', progress: 10 }])
    expect(wrapper2.findAll('.chart-body').length).toBe(1)
    wrapper2.unmount()

    mockApiRequest.mockResolvedValue({})
    mockGet.mockResolvedValue({})
    const wrapper3 = mountChart()
    await flushPromises()
    await nextTick()
    expect((wrapper3.vm as any).projects).toEqual([])
    wrapper3.unmount()
  })

  it('renderCharts 二次渲染先 dispose 再重建；数据全空 → 双 .app-empty 且不 init', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const before = chartBox.count
    await (wrapper.vm as any).loadAndRender()
    await flushPromises()
    await nextTick()
    expect(chartBox.count).toBeGreaterThan(before)
    wrapper.unmount()

    mockApiRequest.mockResolvedValue({ data: { items: [] } })
    mockGet.mockResolvedValue({ funds_allocated: 0, funds_pending: 0, funds_planned: 0 })
    mockSetOption.mockClear()
    const wrapper2 = mountChart()
    await flushPromises()
    await nextTick()
    const empties = wrapper2.findAll('.app-empty')
    expect(empties.length).toBe(2)
    expect(wrapper2.text()).toContain('暂无项目数据')
    expect(wrapper2.text()).toContain('暂无经费数据')
    expect(mockSetOption).not.toHaveBeenCalled()
    wrapper2.unmount()
  })

  it('经费全 0 且项目非空 → 第二卡片显示暂无数据', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'X', progress: 10 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 0, funds_pending: 0, funds_planned: 0 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    expect(wrapper.findAll('.app-empty').length).toBe(1)
    expect(wrapper.find('.app-empty').text()).toContain('暂无经费数据')
    wrapper.unmount()
  })

  it('buildPieOption 饼图 tooltip formatter 执行', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'X', progress: 10 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 100, funds_pending: 20, funds_planned: 10 })
    const wrapper = mountChart()
    await flushPromises()
    await nextTick()
    const pieOpt = mockSetOption.mock.calls.find((c: any) => c[0]?.series?.[0]?.type === 'pie')?.[0]
    expect(pieOpt).toBeTruthy()
    const html = pieOpt.tooltip.formatter({
      marker: '<span>',
      name: '已拨付',
      value: 100,
      percent: 76.9,
    })
    expect(html).toContain('100万')
    expect(html).toContain('76.9%')
    wrapper.unmount()
  })
})

describe('ChartRow 加载/错误/生命周期', () => {
  it('加载中显示 2 个 .app-loading 骨架，完成后隐藏', async () => {
    let resolveProj!: (v: any) => void
    let resolveFund!: (v: any) => void
    mockApiRequest.mockImplementation(() => new Promise((r) => (resolveProj = r)))
    mockGet.mockImplementation(() => new Promise((r) => (resolveFund = r)))
    const wrapper = mountChart()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(2)
    expect(wrapper.findAll('.app-loading').length).toBe(2)
    expect((wrapper.vm as any).loading).toBe(true)
    resolveProj({ data: { items: [{ name: 'A', progress: 1 }] } })
    resolveFund({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    await flushPromises()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(0)
    wrapper.unmount()
  })

  it('加载失败 → 双 .app-error；自动 2s 重试成功后恢复', async () => {
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
    expect(wrapper.findAll('.app-error').length).toBe(2)
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    await nextTick()
    expect(vm.error).toBe(false)
    expect(wrapper.findAll('.app-error').length).toBe(0)
    wrapper.unmount()
  })

  it('重试按钮：仍失败 → error 保持且 renderCharts 早退；恢复后重建图表', async () => {
    mockApiRequest.mockRejectedValue(new Error('still down'))
    mockGet.mockRejectedValue(new Error('still down'))
    const wrapper = mountChart()
    await flushPromises()
    expect(wrapper.findAll('.app-error').length).toBe(2)
    expect(mockSetOption).not.toHaveBeenCalled()

    mockApiRequest.mockResolvedValue({ data: { items: [{ name: 'A', progress: 1 }] } })
    mockGet.mockResolvedValue({ funds_allocated: 1, funds_pending: 0, funds_planned: 0 })
    await wrapper.findAll('.app-error .el-button-stub')[0].trigger('click')
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
