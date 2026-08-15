import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import YearlyComparisonChart from '@/components/funds/YearlyComparisonChart.vue'
import BaseChart from '@/components/common/BaseChart.vue'

enableAutoUnmount(afterEach)

const echartsInstance = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  on: vi.fn(),
}))
vi.mock('@/utils/echarts', () => ({
  __esModule: true,
  default: { init: vi.fn(() => echartsInstance), use: vi.fn(), graphic: {} },
}))

const mockGet = vi.hoisted(() => vi.fn())
vi.mock('@/api/request', () => ({
  get: mockGet,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

const stubs = {
  'el-card': {
    name: 'ElCard',
    props: ['shadow'],
    template: '<div class="el-card"><slot name="header" /><slot /></div>',
  },
  'el-empty': {
    name: 'ElEmpty',
    props: ['description'],
    template: '<div class="el-empty" />',
  },
  'el-skeleton': {
    name: 'ElSkeleton',
    template: '<div class="el-skeleton" />',
  },
  // 覆盖全局 true-stub：转发 click 事件，使 ChartErrorState 的重试按钮可点击
  'el-button': {
    name: 'ElButton',
    template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
  },
}

describe('funds/YearlyComparisonChart.vue', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('loads data on mount and renders BaseChart with computed option', async () => {
    mockGet.mockResolvedValue({
      data: [
        { year: 2022, total_actual: 100 },
        { year: 2023, amount: 200 },
        { year: 2024 },
        { total_actual: 50 },
      ],
    })
    const wrapper = mount(YearlyComparisonChart, {
      props: { yearStart: 2022, yearEnd: 2024, department: 'rural' },
      global: { stubs },
    })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/funds/supported-village/statistics/yearly-comparison', {
      year_start: 2022,
      year_end: 2024,
      department: 'rural',
    })
    const baseChart = wrapper.findComponent(BaseChart)
    expect(baseChart.exists()).toBe(true)
    const option = baseChart.props('option') as any
    expect(option.xAxis.data).toEqual(['2022', '2023', '2024', ''])
    expect(option.series[0].data).toEqual([100, 200, 0, 50])
  })

  it('renders empty state when API returns empty list', async () => {
    mockGet.mockResolvedValue({ data: [] })
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect(wrapper.findComponent(BaseChart).exists()).toBe(false)
    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })

  it('renders empty state when response has no data property', async () => {
    mockGet.mockResolvedValue({})
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })

  it('handles API failure with inline error state and retry', async () => {
    mockGet.mockRejectedValue(new Error('network'))
    const wrapper = mount(YearlyComparisonChart, {
      props: { department: '' },
      global: { stubs },
    })
    await flushPromises()
    // 2026-08-14：失败不再静默空白 → 内联错误态 + 重试
    expect(wrapper.find('.chart-error-state').exists()).toBe(true)
    expect(wrapper.find('.el-empty').exists()).toBe(false)

    // 点击重试 → 重新加载并恢复
    mockGet.mockResolvedValue({ data: [{ year: 2024, total_actual: 10 }] })
    const retryBtn = wrapper.find('.chart-error-state .el-button-stub')
    expect(retryBtn.exists()).toBe(true)
    await retryBtn.trigger('click')
    await flushPromises()
    await new Promise((r) => setTimeout(r, 450)) // ChartErrorState 复位延时
    expect(wrapper.findComponent(BaseChart).exists()).toBe(true)
    expect(wrapper.find('.chart-error-state').exists()).toBe(false)
  })

  it('falls back to [] when API returns null', async () => {
    mockGet.mockResolvedValue(null)
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })

  it('bare array response（裸数组旧形态）→ 正常渲染图表', async () => {
    mockGet.mockResolvedValue([{ year: 2025, total_actual: 88 }])
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    const baseChart = wrapper.findComponent(BaseChart)
    expect(baseChart.exists()).toBe(true)
    const option = baseChart.props('option') as any
    expect(option.xAxis.data).toEqual(['2025'])
    expect(option.series[0].data).toEqual([88])
  })

  it('explicit failure success:false → 内联错误态（message 有/无两侧）', async () => {
    mockGet.mockResolvedValue({ success: false, message: '年度对比失败' })
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect((wrapper.vm as any).loadError).toBe('年度对比失败')
    expect(wrapper.find('.chart-error-state').exists()).toBe(true)
    expect(wrapper.findComponent(BaseChart).exists()).toBe(false)

    // 无 message → 兜底文案
    mockGet.mockResolvedValue({ success: false })
    await (wrapper.vm as any).refresh()
    await flushPromises()
    expect((wrapper.vm as any).loadError).toBe('暂无年度对比数据')
  })

  it('only sends defined query params', async () => {
    mockGet.mockResolvedValue({ data: [] })
    mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith(
      '/funds/supported-village/statistics/yearly-comparison',
      {}
    )
  })

  it('reloads when watched props change and exposes refresh', async () => {
    mockGet.mockResolvedValue({ data: [] })
    const wrapper = mount(YearlyComparisonChart, { global: { stubs } })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ yearStart: 2023 })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)

    await (wrapper.vm as any).refresh()
    expect(mockGet).toHaveBeenCalledTimes(3)
  })
})
