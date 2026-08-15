import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElButton, ElSkeleton } from 'element-plus'
import KpiCards from '@/views/dashboard/KpiCards.vue'

const { mockGet, mockPushSafe } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPushSafe: vi.fn(),
}))

// Mock request API（组件使用命名导出 get）
vi.mock('@/api/request', () => ({
  get: mockGet,
  default: { get: mockGet },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

// Mock 安全路由导航（navigateTo → pushSafe）
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

const statsPayload = {
  data: {
    code: 200,
    data: {
      total_villages: 128,
      total_projects: 45,
      total_schools: 32,
      total_population: 126000,
      total_funds: 8900000,
    },
  },
}

function mountKpi(trends?: Record<string, number>) {
  return mount(KpiCards, {
    global: {
      components: { ElButton, ElSkeleton },
      stubs: { 'el-icon': true },
    },
    props: trends ? { trends } : {},
  })
}

async function flush() {
  await new Promise((r) => setTimeout(r, 300))
}

describe('KpiCards.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue(statsPayload)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders 5 stat-card elements', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.stat-card').length).toBe(5)
  })

  it('renders .data-number on each card', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.data-number').length).toBeGreaterThanOrEqual(5)
  })

  it('shows green tag for positive, red for negative trend', async () => {
    const wrapper = mountKpi({
      villages: 12,
      projects: -3,
      schools: 0,
      population: 8,
      funds: 15,
    })
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.trend-tag--up').length).toBeGreaterThanOrEqual(3)
    expect(wrapper.findAll('.trend-tag--down').length).toBeGreaterThanOrEqual(1)
  })

  it('renders 5 kpi columns', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.kpi-col').length).toBe(5)
  })

  it('stat-card is keyboard accessible (role/tabindex)', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    const card = wrapper.find('.stat-card')
    expect(card.attributes('role')).toBe('button')
    expect(card.attributes('tabindex')).toBe('0')
  })

  it('shows error placeholder with retry button when loading fails', async () => {
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.kpi-error').exists()).toBe(true)
    expect(wrapper.findAll('.stat-card').length).toBe(0)

    // 点击“重试”后恢复渲染卡片（el-button 被全局 stub,@click 透传到 stub 根元素）
    mockGet.mockResolvedValue(statsPayload)
    await wrapper.find('.kpi-error el-button-stub').trigger('click')
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.kpi-error').exists()).toBe(false)
    expect(wrapper.findAll('.stat-card').length).toBe(5)
  })

  it('navigateTo：点击卡片导航到 route；无 route 时提前返回', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()

    await wrapper.find('.stat-card').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')

    await wrapper.find('.stat-card').trigger('keydown.enter')
    expect(mockPushSafe).toHaveBeenCalledTimes(2)

    await wrapper.find('.stat-card').trigger('keydown.space')
    expect(mockPushSafe).toHaveBeenCalledTimes(3)

    // route 缺省 → 提前返回（不调用 pushSafe）
    const before = mockPushSafe.mock.calls.length
    ;(wrapper.vm as any).navigateTo(undefined)
    expect(mockPushSafe.mock.calls.length).toBe(before)
  })

  it('格式化与趋势辅助函数：覆盖全部分支', async () => {
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    const vm = wrapper.vm as any

    expect(vm.fmt(1234)).toBe('1,234')
    expect(vm.fmt(undefined)).toBe('--')
    expect(vm.fmtFunds(8900000)).toBe('890')
    expect(vm.fmtFunds(undefined)).toBe('--')
    expect(vm.fmtPop(undefined)).toBe('--')
    expect(vm.fmtPop(9999)).toBe('9,999')
    expect(vm.fmtPop(120000)).toBe('12.0万')
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

  it('响应为 null/空 → res || {} 兜底，卡片以 0 渲染', async () => {
    mockGet.mockResolvedValue(null)
    const wrapper = mountKpi()
    await flush()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.stat-card').length).toBe(5)
    expect(wrapper.findAll('.data-number').length).toBeGreaterThanOrEqual(5)
  })

  it('加载失败自动重试：最多 3 次后停止', async () => {    vi.useFakeTimers()
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountKpi()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(0)
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

    // 已重试 3 次 → 不再排定新的定时器
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)

    wrapper.unmount()
  })

  it('重试成功后复位计数并停止后续重试', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValueOnce(new Error('first fail'))
    mockGet.mockResolvedValue(statsPayload)
    const wrapper = mountKpi()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGet).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.kpi-error').exists()).toBe(true)

    // 2s 后自动重试成功 → error 复位、计数归零
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.kpi-error').exists()).toBe(false)

    // 计数已复位：即使再等也不会重试
    await vi.advanceTimersByTimeAsync(4000)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('定时器回调：error 已复位时跳过（用户手动重试成功场景）', async () => {
    vi.useFakeTimers()
    mockGet.mockRejectedValueOnce(new Error('first fail'))
    mockGet.mockResolvedValue(statsPayload)
    const wrapper = mountKpi()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGet).toHaveBeenCalledTimes(1)

    // 手动点击“重试”成功（不等 2s 定时器）→ error=false
    await wrapper.find('.kpi-error el-button-stub').trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.kpi-error').exists()).toBe(false)

    // 挂起的定时器触发时 error=false → 跳过重载
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
