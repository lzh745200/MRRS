/**
 * views/dashboard/KpiCards.vue 补充覆盖（与 KpiCards.test.ts 合并达四指标 100%）
 *
 * 覆盖：navigateTo 无路由早退/点击卡片与键盘事件跳转、loadStats 失败后 2s 自动重试、
 * fmt/fmtFunds/fmtPop 的 undefined 兜底（--）、trendClass/trendTagClass/trendIcon 零值分支、
 * 加载中骨架屏、卡片点击 pushSafe。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { mockGet, mockPushSafe, logError } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPushSafe: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  default: {},
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import KpiCards from '@/views/dashboard/KpiCards.vue'

function mountKpi(trends?: Record<string, number>) {
  return mount(KpiCards, {
    props: trends ? { trends } : {},
    global: {
      stubs: {
        'el-icon': { template: '<span><slot /></span>' },
        'el-skeleton': { template: '<div class="skeleton-stub" />' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({
    total_villages: 100,
    total_projects: 20,
    total_schools: 5,
    total_population: 300000,
    total_funds: 8000000,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('KpiCards 补充覆盖', () => {
  it('navigateTo：无路由早退；点击卡片与 enter/space 键盘跳转', async () => {
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.navigateTo(undefined as any)
    expect(mockPushSafe).not.toHaveBeenCalled()

    const card = wrapper.find('.stat-card')
    await card.trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    mockPushSafe.mockClear()
    await card.trigger('keydown.enter')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    mockPushSafe.mockClear()
    await card.trigger('keydown.space')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    wrapper.unmount()
  })

  it('loadStats 失败 → 错误态；2s 自动重试成功恢复', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValueOnce(new Error('net'))
    mockGet.mockResolvedValueOnce({ total_villages: 1, total_projects: 1, total_schools: 1, total_population: 1, total_funds: 1 })
    const wrapper = mountKpi()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(wrapper.find('.kpi-error').exists()).toBe(true)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    await nextTick()
    expect(wrapper.find('.kpi-error').exists()).toBe(false)
    expect(wrapper.findAll('.stat-card').length).toBe(5)
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('loadStats 连续失败 → 最多重试 3 次后放弃（retryCount 上限分支）', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValue(new Error('persistent down'))
    const wrapper = mountKpi()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(3)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)
    // 第 4 次失败后 retryCount=3，不再调度新定时器
    vi.advanceTimersByTime(20000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)
    expect(wrapper.find('.kpi-error').exists()).toBe(true)
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('fmt/fmtFunds/fmtPop：undefined → --；人口 ≥1万 → 万 单位', () => {
    const wrapper = mountKpi()
    const vm = wrapper.vm as any
    expect(vm.fmt(undefined)).toBe('--')
    expect(vm.fmtFunds(undefined)).toBe('--')
    expect(vm.fmtPop(undefined)).toBe('--')
    expect(vm.fmtPop(12345)).toBe('1.2万')
    expect(vm.fmtPop(9999)).toBe('9,999')
    expect(vm.fmtFunds(50000)).toBe('5')
    wrapper.unmount()
  })

  it('趋势工具函数：零值 → 持平图标与空 class', async () => {
    const wrapper = mountKpi({
      villages: 12,
      projects: -3,
      schools: 0,
      population: 8,
      funds: 15,
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.trendClass(0)).toBe('')
    expect(vm.trendClass(5)).toBe('stat-trend--up')
    expect(vm.trendClass(-5)).toBe('stat-trend--down')
    expect(vm.trendTagClass(0)).toBe('trend-tag--flat')
    expect(vm.trendTagClass(5)).toBe('trend-tag--up')
    expect(vm.trendTagClass(-5)).toBe('trend-tag--down')
    expect(vm.trendIcon(0)?.name).toBeDefined()
    expect(vm.trendIcon(5)).toBeDefined()
    expect(vm.trendIcon(-5)).toBeDefined()
    // 模板：非零趋势渲染百分比数字
    expect(wrapper.text()).toContain('12%')
    wrapper.unmount()
  })

  it('加载中显示 5 个骨架列', async () => {
    let resolve!: (v: any) => void
    mockGet.mockImplementation(() => new Promise((r) => (resolve = r)))
    const wrapper = mountKpi()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(5)
    expect((wrapper.vm as any).loading).toBe(true)
    resolve({
      total_villages: 1,
      total_projects: 1,
      total_schools: 1,
      total_population: 1,
      total_funds: 1,
    })
    await flushPromises()
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()
  })

  it('stats 响应为 null → res || {} 兜底；字段缺失 → 全 0', async () => {
    mockGet.mockResolvedValueOnce(null)
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.total_villages).toBe(0)

    mockGet.mockResolvedValue({})
    await vm.loadStats()
    expect(vm.stats.total_villages).toBe(0)
    // 人口卡片无单位 → 不渲染 data-unit
    const units = wrapper.findAll('.data-unit')
    expect(units.length).toBe(4)
    wrapper.unmount()
  })

  it('零趋势卡片渲染「持平」', async () => {
    const wrapper = mountKpi({
      villages: 0,
      projects: 0,
      schools: 0,
      population: 0,
      funds: 0,
    })
    await flushPromises()
    expect(wrapper.text()).toContain('持平')
    expect(wrapper.findAll('.trend-tag--flat').length).toBe(5)
    wrapper.unmount()
  })
})
