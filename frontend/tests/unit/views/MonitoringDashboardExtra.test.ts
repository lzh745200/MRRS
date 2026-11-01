/**
 * views/system/MonitoringDashboard.vue 补充覆盖
 * 覆盖：日志过滤、computeScore 中段分支、statusInfo 高阈值、线程偏高、
 * 各接口失败、高占用日志生成、导出、主题监听、分数徽章、sparkline
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { mockGet, mockEchartsInit, mockApiRequest } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockEchartsInit: vi.fn(),
  mockApiRequest: vi.fn(),
}))

const mockSetOption = vi.fn()
const mockDispose = vi.fn()
const echartsInstance = { setOption: mockSetOption, dispose: mockDispose, on: vi.fn() }

const mockSnapshotData = {
  cpu_usage: 23.5,
  memory_usage: 58.2,
  disk_usage: 41.0,
  network_recv_mb: 12.3,
  network_sent_mb: 5.1,
  process_threads: 12,
  cpu_count: 8,
  memory_used_mb: 4096,
  memory_total_mb: 8192,
  disk_used_gb: 80,
  disk_total_gb: 200,
}

const mockApiStatsData = {
  top_endpoints: [
    { endpoint: '/api/v1/auth/login', method: 'POST', count: 150, avg_time_ms: 45.2, error_rate: 2.1 },
    { endpoint: '/api/v1/villages', method: 'GET', count: 320, avg_time_ms: 12.5, error_rate: 0.3 },
  ],
}

const mockHealthData = {
  db_size_mb: 45.2,
  table_count: 38,
  db_integrity_ok: true,
  wal_size_kb: 128,
  uptime_seconds: 260100,
}

vi.mock('@/api/request', () => ({
  default: { get: mockGet },
  get: mockGet,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/echarts', () => ({
  __esModule: true,
  default: { init: mockEchartsInit },
}))

import { reactive } from 'vue'

const themeState = reactive({ value: 'light' })
vi.mock('@/stores/config', () => ({
  useConfigStore: () => ({
    get theme() {
      return themeState.value
    },
  }),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Refresh: { name: 'Refresh', template: '<span>Refresh</span>' },
  Download: { name: 'Download', template: '<span>Download</span>' },
  CircleCheckFilled: { name: 'CircleCheckFilled', template: '<span>CircleCheckFilled</span>' },
  CircleCloseFilled: { name: 'CircleCloseFilled', template: '<span>CircleCloseFilled</span>' },
  Monitor: { name: 'Monitor', template: '<span>Monitor</span>' },
  Files: { name: 'Files', template: '<span>Files</span>' },
  Coin: { name: 'Coin', template: '<span>Coin</span>' },
  Upload: { name: 'Upload', template: '<span>Upload</span>' },
  Setting: { name: 'Setting', template: '<span>Setting</span>' },
  FirstAidKit: { name: 'FirstAidKit', template: '<span>FirstAidKit</span>' },
  Clock: { name: 'Clock', template: '<span>Clock</span>' },
  DataAnalysis: { name: 'DataAnalysis', template: '<span>DataAnalysis</span>' },
  EditPen: { name: 'EditPen', template: '<span>EditPen</span>' },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  }
})

import MonitoringDashboard from '@/views/system/MonitoringDashboard.vue'

function setupDefaultMocks() {
  mockGet.mockReset()
  mockGet.mockImplementation((url: string) => {
    if (url === '/system/monitor/snapshot') {
      return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
    }
    if (url === '/health/full') {
      return Promise.resolve({ data: mockHealthData })
    }
    if (url === '/system/health/full') {
      return Promise.resolve({ data: { data: { status: 'ok' } } })
    }
    return Promise.reject(new Error('Unknown URL'))
  })
  mockApiRequest.mockReset()
  mockApiRequest.mockImplementation((config: any) => {
    if (config?.url === '/system/monitor/api-stats') {
      return Promise.resolve({ data: { success: true, data: mockApiStatsData } })
    }
    return Promise.reject(new Error('Unknown API request'))
  })
  mockEchartsInit.mockReset()
  mockEchartsInit.mockReturnValue(echartsInstance)
  mockSetOption.mockReset()
  mockDispose.mockReset()
  themeState.value = 'light'
}

function mountComponent() {
  return mount(MonitoringDashboard, {
    global: {
      stubs: {
        'el-icon': true,
        'el-button': {
          name: 'ElButton',
          template: '<el-button-stub><slot /></el-button-stub>',
        },
        'el-tag': true,
        'el-empty': true,
        'el-radio-group': {
          name: 'ElRadioGroup',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template:
            '<div class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'warn\')"><slot /></div>',
        },
        'el-radio-button': { name: 'ElRadioButton', template: '<span class="el-radio-button-stub"><slot /></span>' },
      },
    },
  })
}

async function advanceFakeTimersAndFlush() {
  await vi.advanceTimersByTimeAsync(50)
  await flushPromises()
  await nextTick()
}

describe('MonitoringDashboard.vue 补充', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setupDefaultMocks()
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('日志过滤：warn / error / all', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    vm.recentLogs = [
      { id: 1, time: 't', level: 'warn', message: 'w' },
      { id: 2, time: 't', level: 'error', message: 'e' },
      { id: 3, time: 't', level: 'info', message: 'i' },
    ]
    vm.logLevelFilter = 'warn'
    expect(vm.filteredLogs.map((l: any) => l.level)).toEqual(['warn'])
    vm.logLevelFilter = 'error'
    expect(vm.filteredLogs.map((l: any) => l.level)).toEqual(['error'])
    vm.logLevelFilter = 'all'
    expect(vm.filteredLogs.length).toBe(3)
    // radio-group v-model 切换
    await wrapper.find('.el-radio-group-stub').trigger('click')
    expect(vm.logLevelFilter).toBe('warn')
    expect(wrapper.findAll('.log-item').length).toBeGreaterThan(0)
  })

  it('computeScore：中段分数分支（70-90）', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    // cpu 75 → +10, mem 80 → +10, disk 85 → +10, base 20 = 50
    expect(
      vm.computeScore({ cpu_usage: 75, memory_usage: 80, disk_usage: 85 } as any, { db_integrity_ok: false } as any)
    ).toBe(50)
    // 无快照/无健康 → 20
    expect(vm.computeScore(null, null)).toBe(20)
    // 全达标 → 100
    expect(
      vm.computeScore({ cpu_usage: 10, memory_usage: 10, disk_usage: 10 } as any, { db_integrity_ok: true } as any)
    ).toBe(100)
  })

  it('statusInfo：>=90 严重 / >=70 警告 / 反转', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.statusInfo(95)).toEqual({ status: 'danger', tagType: 'danger', statusText: '严重' })
    expect(vm.statusInfo(75)).toEqual({ status: 'warning', tagType: 'warning', statusText: '警告' })
    expect(vm.statusInfo(30)).toEqual({ status: 'normal', tagType: 'success', statusText: '正常' })
    expect(vm.statusInfo(10, true)).toEqual({ status: 'danger', tagType: 'danger', statusText: '严重' })
  })

  it('线程数量偏高（>500）→ warning', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({
          data: { success: true, data: { ...mockSnapshotData, process_threads: 600 } },
        })
      }
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.secondaryCards[2].statusText).toBe('偏高')
  })

  it('API 统计接口失败 → 空数组', async () => {
    mockApiRequest.mockRejectedValue(new Error('api-stats failed'))
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.apiStats).toEqual([])
  })

  it('健康接口失败 → null', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
      }
      if (url === '/health/full') return Promise.reject(new Error('health failed'))
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.healthData).toBeNull()
    expect(vm.dbInfo.size).toBe('--')
  })

  it('健康检查接口失败 → 回退推导（responseTime 仍记录）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
      }
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.reject(new Error('not found'))
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.healthChecksData).toBeNull()
    expect(typeof vm.responseTime).toBe('number')
  })

  it('高占用快照 → 生成 warn/error 日志', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({
          data: {
            success: true,
            data: { ...mockSnapshotData, cpu_usage: 85, memory_usage: 90, disk_usage: 95 },
          },
        })
      }
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    const levels = vm.recentLogs.map((l: any) => l.level)
    expect(levels).toContain('warn')
    expect(levels).toContain('error')
    expect(vm.recentLogs.length).toBe(3)
  })

  it('exportData：导出 JSON 并提示', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    const clickSpy = vi.fn()
    const realCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = realCreateElement(tag)
      ;(el as HTMLAnchorElement).click = clickSpy
      return el
    })
    vm.exportData()
    expect(clickSpy).toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(150)
    vi.restoreAllMocks()
  })

  it('主题监听：theme 变化重建图表', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const callsBefore = mockEchartsInit.mock.calls.length
    themeState.value = 'dark'
    await vi.advanceTimersByTimeAsync(10)
    await flushPromises()
    await nextTick()
    // eslint-disable-next-line no-console
    void 0
    expect(mockEchartsInit.mock.calls.length).toBeGreaterThan(callsBefore)
    expect(mockEchartsInit).toHaveBeenLastCalledWith(expect.anything(), 'militaryTechDark')
  })

  it('分数徽章：<60 → score-danger', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({
          data: { success: true, data: { ...mockSnapshotData, cpu_usage: 95, memory_usage: 95, disk_usage: 95 } },
        })
      }
      if (url === '/health/full') return Promise.resolve({ data: { ...mockHealthData, db_integrity_ok: false } })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.healthScore).toBeLessThan(60)
    expect(vm.scoreBadgeClass).toBe('score-danger')
    const badge = wrapper.find('.health-badge')
    expect(badge.classes()).toContain('score-danger')
  })

  it('卡片 hover：activePopover 设置/清空', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    const card = wrapper.find('.primary-card')
    await card.trigger('mouseenter')
    expect(vm.activePopover).toBe('cpu')
    await card.trigger('mouseleave')
    expect(vm.activePopover).toBeNull()
  })

  it('sparkline：历史数据渲染', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    await vm.refreshAll()
    await nextTick()
    expect(vm.history.length).toBeGreaterThan(0)
    expect(wrapper.findAll('.spark-dot').length).toBeGreaterThan(0)
  })

  it('页头刷新按钮点击 → refreshAll', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    const before = mockGet.mock.calls.length
    // el-button stub 渲染 <el-button-stub> 元素
    const refreshBtn = wrapper.findAll('el-button-stub')[0]
    expect(refreshBtn.exists()).toBe(true)
    await refreshBtn.trigger('click')
    await flushPromises()
    expect(mockGet.mock.calls.length).toBeGreaterThan(before)
    expect(vm.loading).toBe(false)
  })

  it('快照字段全部缺失 → ?? 兜底路径', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({ data: { success: true, data: {} } })
      }
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.primaryCards[0].value).toBe('0.0')
    expect(vm.primaryCards[0].detail).toBe('0 核 · 0 线程')
    expect(vm.primaryCards[0].percent).toBeUndefined()
    expect(vm.secondaryCards[0].value).toBe('0.0')
    expect(vm.secondaryCards[1].value).toBe('0.0')
    expect(vm.basicChecks[3].passed).toBe(true)
    expect(vm.performanceChecks[0].passed).toBe(false)
  })

  it('健康分数 60-79 → score-warning 徽章', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') {
        return Promise.resolve({
          data: { success: true, data: { ...mockSnapshotData, cpu_usage: 75, memory_usage: 80, disk_usage: 85 } },
        })
      }
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    expect(vm.healthScore).toBe(70)
    expect(vm.scoreBadgeClass).toBe('score-warning')
  })

  it('fetchSnapshot 响应形态：扁平 data / 无 data', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    await vm.fetchSnapshot()
    expect(vm.snapshot?.cpu_usage).toBe(23.5)
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') return Promise.resolve({})
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    await vm.fetchSnapshot()
    expect(vm.snapshot).toEqual({})
  })

  it('fetchApiStats 响应形态与 top_endpoints 兜底', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    mockApiRequest.mockResolvedValue({ data: mockApiStatsData })
    await vm.fetchApiStats()
    expect(vm.apiStats).toHaveLength(2)
    mockApiRequest.mockResolvedValue({ data: { success: true, data: {} } })
    await vm.fetchApiStats()
    expect(vm.apiStats).toEqual([])
    mockApiRequest.mockResolvedValue({})
    await vm.fetchApiStats()
    expect(vm.apiStats).toEqual([])
  })

  it('fetchHealth 响应无 data → 空对象', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
      if (url === '/health/full') return Promise.resolve({})
      if (url === '/system/health/full') return Promise.resolve({ data: { data: { status: 'ok' } } })
      return Promise.reject(new Error('Unknown URL'))
    })
    await vm.fetchHealth()
    expect(vm.healthData).toEqual({})
  })

  it('fetchHealthChecks 响应形态：扁平 data / 无 data', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({ data: { status: 'ok' } })
      return Promise.reject(new Error('Unknown URL'))
    })
    await vm.fetchHealthChecks()
    expect(vm.healthChecksData).toEqual({ status: 'ok' })
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/monitor/snapshot') return Promise.resolve({ data: { success: true, data: mockSnapshotData } })
      if (url === '/health/full') return Promise.resolve({ data: mockHealthData })
      if (url === '/system/health/full') return Promise.resolve({})
      return Promise.reject(new Error('Unknown URL'))
    })
    await vm.fetchHealthChecks()
    expect(vm.healthChecksData).toEqual({})
  })

  it('buildChart chartRef 为空 → 直接返回', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    const callsBefore = mockEchartsInit.mock.calls.length
    vm.chartRef = null
    await vm.buildChart()
    expect(mockEchartsInit.mock.calls.length).toBe(callsBefore)
  })

  it('API 端点字段缺失 → ?? 兜底', async () => {
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    const vm = wrapper.vm as any
    vm.apiStats = [
      { endpoint: '/no-method', count: 1, avg_time_ms: 1, error_rate: 1 },
      { endpoint: '/tr', method: 'GET', total_requests: 5, avg_time_ms: 1, error_rate: 1 },
      { endpoint: '/no-count', method: 'GET', avg_time_ms: 1, error_rate: 1 },
      { endpoint: '/at', method: 'GET', count: 1, avg_time_ms: 2.5, error_rate: 1 },
      { endpoint: '/er', method: 'GET', count: 1, avg_time_ms: 1 },
      { endpoint: '/no-avg', method: 'GET', count: 1, error_rate: 1 },
    ]
    await vm.buildChart()
    expect(mockSetOption).toHaveBeenCalled()
  })

  describe('可观测性面板（长期项 3）', () => {
    function mockMetrics(payload: Record<string, unknown>) {
      const base = mockGet.getMockImplementation() as (url: string) => Promise<unknown>
      mockGet.mockImplementation((url: string) => {
        if (url === '/system/metrics') {
          return Promise.resolve({ data: { success: true, data: payload } })
        }
        return base(url)
      })
    }

    it('business + slow_api_top 齐全 → 渲染计数卡与慢请求', async () => {
      mockMetrics({
        business: { 'data_package.import': 3, 'data_package.import_failed': 1, 'custom.event': 5 },
        observability: {
          slow_api_top: [{ method: 'GET', path: '/api/v1/villages', elapsed_ms: 1200 }],
        },
      })
      const wrapper = mountComponent()
      await advanceFakeTimersAndFlush()
      // 按计数降序：custom.event(5) → 3 → 1，未知事件回退用 key 作标签
      const values = wrapper.findAll('.business-value').map((n) => n.text())
      expect(values).toEqual(['5', '3', '1'])
      const labels = wrapper.findAll('.business-label').map((n) => n.text())
      expect(labels).toContain('custom.event')
      expect(labels).toContain('数据包导入')
      expect(wrapper.find('.slow-list').text()).toContain('/api/v1/villages')
      expect(wrapper.find('.slow-list').text()).toContain('1200 ms')
    })

    it('只有 observability（无 business）→ 显示暂无业务事件', async () => {
      mockMetrics({ observability: { slow_api_top: [] } })
      const wrapper = mountComponent()
      await advanceFakeTimersAndFlush()
      expect(wrapper.find('.business-empty').text()).toContain('暂无业务事件')
      expect(wrapper.find('.slow-top').exists()).toBe(false)
    })

    it('只有 business（无 observability）→ 渲染计数但不显示慢请求', async () => {
      mockMetrics({ business: { 'backup.create': 2 } })
      const wrapper = mountComponent()
      await advanceFakeTimersAndFlush()
      expect(wrapper.findAll('.business-value').map((n) => n.text())).toEqual(['2'])
      expect(wrapper.find('.slow-top').exists()).toBe(false)
    })
  })
})
