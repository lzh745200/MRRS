/**
 * views/dashboard/KpiCards.vue 唯一执行者测试（W23 W4，四指标 100%）
 *
 * 覆盖：统计卡渲染（.app-stat-card 网格/数字/单位）、趋势三态（up/down/持平）、
 * 点击与键盘导航、加载三件套（.app-loading 骨架 / .app-error 重试）、
 * 失败自动重试 3 次上限与成功复位、定时器清理、格式化函数全分支、响应形状兜底。
 * 注：合并原 KpiCardsCov.test.ts 的补充覆盖，保证单执行者。
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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import KpiCards from '@/views/dashboard/KpiCards.vue'

const statsPayload = {
  total_villages: 100,
  total_projects: 20,
  total_schools: 5,
  total_population: 300000,
  total_funds: 8000000,
}

function mountKpi(trends?: Record<string, number>) {
  return mount(KpiCards, {
    props: trends ? { trends } : {},
    global: {
      stubs: {
        'el-icon': { template: '<span class="icon-stub"><slot /></span>' },
        'el-skeleton': { template: '<div class="skeleton-stub" />' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue(statsPayload)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('KpiCards 渲染', () => {
  it('渲染 5 张 .app-stat-card 统计卡与数字/单位；数字列使用 tabular-nums', async () => {
    const wrapper = mountKpi()
    await flushPromises()
    await nextTick()
    expect(wrapper.findAll('.stat-card').length).toBe(5)
    expect(wrapper.findAll('.app-stat-card').length).toBe(5)
    expect(wrapper.findAll('.kpi-col').length).toBe(5)
    expect(wrapper.findAll('.data-number').length).toBeGreaterThanOrEqual(5)
    expect(wrapper.findAll('.data-unit').length).toBe(4) // 覆盖人口无单位
    expect(wrapper.findAll('.stat-trend').length).toBe(5)
    expect(wrapper.text()).toContain('帮扶村')
    expect(wrapper.text()).toContain('覆盖人口')
    wrapper.unmount()
  })

  it('趋势三态：正/负/零 → class、百分比与「持平」；stat-trend 供 data-simplify 隐藏', async () => {
    const wrapper = mountKpi({
      villages: 12,
      projects: -3,
      schools: 0,
      population: 8,
      funds: 15,
    })
    await flushPromises()
    expect(wrapper.findAll('.trend-tag--up').length).toBeGreaterThanOrEqual(3)
    expect(wrapper.findAll('.trend-tag--down').length).toBeGreaterThanOrEqual(1)
    expect(wrapper.findAll('.trend-tag--flat').length).toBe(1)
    expect(wrapper.text()).toContain('12%')
    expect(wrapper.text()).toContain('持平')
    // 简化模式由全局 [data-simplify="true"] .stat-trend 规则隐藏，结构上必须带该 class
    expect(wrapper.find('.stat-trend').exists()).toBe(true)
    wrapper.unmount()
  })

  it('统计卡可键盘访问（role=button / tabindex=0），点击/Enter/Space 导航；无 route 早退', async () => {
    const wrapper = mountKpi()
    await flushPromises()
    const card = wrapper.find('.stat-card')
    expect(card.attributes('role')).toBe('button')
    expect(card.attributes('tabindex')).toBe('0')

    await card.trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    mockPushSafe.mockClear()
    await card.trigger('keydown.enter')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    mockPushSafe.mockClear()
    await card.trigger('keydown.space')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')

    const before = mockPushSafe.mock.calls.length
    ;(wrapper.vm as any).navigateTo(undefined)
    expect(mockPushSafe.mock.calls.length).toBe(before)
    wrapper.unmount()
  })

  it('加载中显示 5 个 .app-loading 骨架，加载完成隐藏', async () => {
    let resolve!: (v: any) => void
    mockGet.mockImplementation(() => new Promise((r) => (resolve = r)))
    const wrapper = mountKpi()
    await nextTick()
    expect(wrapper.findAll('.skeleton-stub').length).toBe(5)
    expect(wrapper.findAll('.app-loading').length).toBe(5)
    expect((wrapper.vm as any).loading).toBe(true)
    resolve(statsPayload)
    await flushPromises()
    expect((wrapper.vm as any).loading).toBe(false)
    expect(wrapper.findAll('.skeleton-stub').length).toBe(0)
    wrapper.unmount()
  })
})

describe('KpiCards 错误与重试', () => {
  it('加载失败 → .app-error 错误态（可重试）；点击重试恢复卡片', async () => {
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountKpi()
    await flushPromises()
    await nextTick()
    expect(logError).toHaveBeenCalled()
    expect(wrapper.find('.kpi-error').exists()).toBe(true)
    expect(wrapper.find('.app-error').exists()).toBe(true)
    expect(wrapper.findAll('.stat-card').length).toBe(0)

    mockGet.mockResolvedValue(statsPayload)
    await wrapper.find('.kpi-error .el-button-stub').trigger('click')
    await flushPromises()
    await nextTick()
    expect(wrapper.find('.kpi-error').exists()).toBe(false)
    expect(wrapper.findAll('.stat-card').length).toBe(5)
    wrapper.unmount()
  })

  it('失败自动重试：最多 3 次后停止', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountKpi()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)
    await vi.advanceTimersByTimeAsync(20000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)
    expect(wrapper.find('.app-error').exists()).toBe(true)
    wrapper.unmount()
  })

  it('重试成功后复位计数并停止后续重试', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValueOnce(new Error('first fail'))
    mockGet.mockResolvedValue(statsPayload)
    const wrapper = mountKpi()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.kpi-error').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.kpi-error').exists()).toBe(false)

    await vi.advanceTimersByTimeAsync(4000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('手动重试成功后，挂起的自动重试定时器触发时跳过（error 已复位）', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValueOnce(new Error('first fail'))
    mockGet.mockResolvedValue(statsPayload)
    const wrapper = mountKpi()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGet).toHaveBeenCalledTimes(1)

    await wrapper.find('.kpi-error .el-button-stub').trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.kpi-error').exists()).toBe(false)

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('卸载时清理重试定时器（不再触发请求）', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountKpi()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGet).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)
  })
})

describe('KpiCards 工具函数与数据兜底', () => {
  it('fmt/fmtFunds/fmtPop 全分支；人口 ≥1 万 → 万单位', async () => {
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.fmt(1234)).toBe('1,234')
    expect(vm.fmt(undefined)).toBe('--')
    expect(vm.fmtFunds(8900000)).toBe('8,900,000')
    expect(vm.fmtFunds(1234.567)).toBe('1,234.57')
    expect(vm.fmtFunds(undefined)).toBe('--')
    expect(vm.fmtPop(undefined)).toBe('--')
    expect(vm.fmtPop(9999)).toBe('9,999')
    expect(vm.fmtPop(120000)).toBe('12.0万')
    wrapper.unmount()
  })

  it('趋势辅助函数全分支（class / tag class / icon）', async () => {
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.trendClass(1)).toBe('stat-trend--up')
    expect(vm.trendClass(-1)).toBe('stat-trend--down')
    expect(vm.trendClass(0)).toBe('')
    expect(vm.trendTagClass(1)).toBe('trend-tag--up')
    expect(vm.trendTagClass(-1)).toBe('trend-tag--down')
    expect(vm.trendTagClass(0)).toBe('trend-tag--flat')
    expect(vm.trendIcon(1)).toBeTruthy()
    expect(vm.trendIcon(-1)).toBeTruthy()
    expect(vm.trendIcon(0)).toBeTruthy()
    // 成功路径卸载：retryTimer 为 null → onBeforeUnmount 的 falsy 分支
    wrapper.unmount()
  })

  it('stats 响应为 null/空对象/嵌套形状 → 字段 0 兜底仍渲染 5 卡', async () => {
    mockGet.mockResolvedValueOnce(null)
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.total_villages).toBe(0)

    mockGet.mockResolvedValue({})
    await vm.loadStats()
    expect(vm.stats.total_villages).toBe(0)

    // 嵌套 {data:{...}} 形状（字段不在顶层）→ 全部 0 兜底，不抛错
    mockGet.mockResolvedValue({ data: { total_villages: 9 } })
    await vm.loadStats()
    expect(vm.stats.total_villages).toBe(0)
    expect(wrapper.findAll('.stat-card').length).toBe(5)
    wrapper.unmount()
  })

  it('trends 由 trends 字段驱动（population_yoy 映射、缺省 0）', async () => {
    mockGet.mockResolvedValue({
      ...statsPayload,
      trends: { villages: 4, projects: 2, schools: 1, population_yoy: 6, funds: 3 },
    })
    const wrapper = mountKpi()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.cards.map((c: any) => c.trend)).toEqual([4, 2, 1, 3, 6])
    wrapper.unmount()
  })
})

describe('KpiCards 取消请求（CanceledError）', () => {
  it('code=ERR_CANCELED：不置错误态、不记 error、不重试', async () => {
    mockGet.mockRejectedValueOnce(
      Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' })
    )
    const wrapper = mountKpi()
    await flushPromises()
    await nextTick()
    expect(wrapper.find('[data-testid="kpi-error"]').exists()).toBe(false)
    expect(logError).not.toHaveBeenCalled()
    expect(wrapper.findAll('.app-stat-card').length).toBe(5)
    wrapper.unmount()
  })

  it('name=CanceledError（无 code）：同样视为正常中止', async () => {
    mockGet.mockRejectedValueOnce(Object.assign(new Error('canceled'), { name: 'CanceledError' }))
    const wrapper = mountKpi()
    await flushPromises()
    await nextTick()
    expect(wrapper.find('[data-testid="kpi-error"]').exists()).toBe(false)
    expect(logError).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
