/**
 * SystemStatus.vue 测试
 * 覆盖：快照加载（在线/离线/无数据）、数据库大小、同步时间文案分支、
 * CPU/内存告警等级、刷新按钮、轮询与清理
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import SystemStatus from '@/components/business/SystemStatus.vue'

enableAutoUnmount(afterEach)

vi.mock('@element-plus/icons-vue', () => ({
  Timer: { template: '<i />' },
  Coin: { template: '<i />' },
  Monitor: { template: '<i />' },
  Files: { template: '<i />' },
  Cpu: { template: '<i />' },
  Refresh: { template: '<i />' },
}))

const mocks = vi.hoisted(() => ({
  getMonitorSnapshot: vi.fn(),
  getDatabaseFileSize: vi.fn(),
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/api/systemMonitor', () => ({
  getMonitorSnapshot: (...a: any[]) => mocks.getMonitorSnapshot(...a),
  getDatabaseFileSize: (...a: any[]) => mocks.getDatabaseFileSize(...a),
}))

vi.mock('@/utils/logger', () => ({ logger: mocks.logger }))

function mountStatus(props: Record<string, unknown> = {}) {
  return mount(SystemStatus, {
    props,
    global: {
      stubs: {
        'el-icon': { template: '<i class="stub-icon"><slot /></i>' },
        'el-button': {
          props: {
            disabled: { type: Boolean, default: false },
            loading: { type: Boolean, default: false },
          },
          emits: ['click'],
          template: '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

const snapshot = {
  success: true,
  data: {
    cpu_usage: 75.6,
    memory_usage: 80.2,
    process_memory_mb: 123,
    process_threads: 5,
  },
}

describe('SystemStatus.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getMonitorSnapshot.mockResolvedValue(snapshot)
    mocks.getDatabaseFileSize.mockResolvedValue({ success: true, data: { size_bytes: 500 * 1024 * 1024 } })
  })

  it('初始加载快照并渲染各指标', async () => {
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()

    expect(mocks.getMonitorSnapshot).toHaveBeenCalled()
    expect(wrapper.text()).toContain('在线')
    expect(wrapper.text()).toContain('76%')
    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('123MB')
    expect(wrapper.text()).toContain('5线程')
    expect(wrapper.text()).toContain('500.0 MB')
    expect(wrapper.text()).toContain('刚刚')
  })

  it('数据库大小：0 / GB / 默认 MB 文案', async () => {
    mocks.getDatabaseFileSize.mockResolvedValue({ success: true, data: { size_bytes: 0 } })
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    expect(wrapper.text()).toContain('-- MB')

    const state = (wrapper.vm as any).$.setupState
    state.dbSizeBytes = 2 * 1024 * 1024 * 1024
    await nextTick()
    expect(wrapper.text()).toContain('2.00 GB')

    state.dbSizeBytes = 300 * 1024 * 1024
    await nextTick()
    expect(wrapper.text()).toContain('300.0 MB')
  })

  it('快照失败时标记离线并保留数据', async () => {
    mocks.getMonitorSnapshot.mockRejectedValue(new Error('net'))
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    expect(wrapper.text()).toContain('离线')
  })

  it('success 为 false 或缺少 data 时不更新指标', async () => {
    mocks.getMonitorSnapshot.mockResolvedValueOnce({ success: false, data: snapshot.data })
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    expect(wrapper.text()).toContain('在线')

    mocks.getMonitorSnapshot.mockResolvedValueOnce({ success: true })
    await (wrapper.vm as any).$.setupState.fetchSnapshot()
    await flushPromises()
    // 保持原数据（cpu 仍为 0 默认）
    expect(wrapper.text()).toContain('0%')
  })

  it('快照字段缺失/为 0 时使用回退值', async () => {
    mocks.getMonitorSnapshot.mockResolvedValue({
      success: true,
      data: { cpu_usage: 0, memory_usage: undefined, process_memory_mb: 0, process_threads: 0 },
    })
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    expect(wrapper.text()).toContain('0%')
    expect(wrapper.text()).toContain('0MB')
    expect(wrapper.text()).toContain('0线程')
  })

  it('getDatabaseFileSize 失败时降级为 0', async () => {
    mocks.getDatabaseFileSize.mockRejectedValue(new Error('x'))
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    expect(wrapper.text()).toContain('-- MB')
  })

  it('同步时间文案分支', async () => {
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    const state = (wrapper.vm as any).$.setupState

    state.lastSyncTime = new Date(Date.now() - 30 * 1000)
    await nextTick()
    expect(wrapper.text()).toContain('刚刚')

    state.lastSyncTime = new Date(Date.now() - 5 * 60 * 1000)
    await nextTick()
    expect(wrapper.text()).toContain('5分钟前')

    state.lastSyncTime = new Date(Date.now() - 2 * 3600 * 1000)
    await nextTick()
    expect(wrapper.text()).toContain('2小时前')

    state.lastSyncTime = new Date(Date.now() - 50 * 3600 * 1000)
    await nextTick()
    expect(wrapper.text()).not.toContain('分钟前')
    expect(wrapper.text()).not.toContain('小时前')

    state.lastSyncTime = null
    await nextTick()
    expect(wrapper.text()).toContain('--:--')
  })

  it('CPU/内存告警等级 class', async () => {
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    const state = (wrapper.vm as any).$.setupState

    state.cpuPercent = 80
    state.memPercent = 80
    await nextTick()
    let fills = wrapper.findAll('.status-bar__fill')
    expect(fills[0].classes()).toContain('status-bar__fill--warning')
    expect(fills[1].classes()).toContain('status-bar__fill--warning')

    state.cpuPercent = 95
    state.memPercent = 90
    await nextTick()
    fills = wrapper.findAll('.status-bar__fill')
    expect(fills[0].classes()).toContain('status-bar__fill--danger')
    expect(fills[1].classes()).toContain('status-bar__fill--danger')
  })

  it('刷新按钮：手动触发 refresh 并展示同步中', async () => {
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    mocks.getMonitorSnapshot.mockClear()
    await wrapper.find('button.stub-btn').trigger('click')
    await flushPromises()
    expect(mocks.getMonitorSnapshot).toHaveBeenCalled()
    expect(mocks.getDatabaseFileSize).toHaveBeenCalled()
    expect(wrapper.text()).toContain('同步')
  })

  it('refresh 的 Promise.all 拒绝时记录错误日志（防御性 catch 分支）', async () => {
    const allSpy = vi.spyOn(Promise, 'all').mockRejectedValueOnce(new Error('boom'))
    try {
      const wrapper = mountStatus({ pollInterval: 0 })
      await flushPromises()
      expect(mocks.logger.error).toHaveBeenCalledWith('[SystemStatus] 刷新失败:', expect.any(Error))
      wrapper.unmount()
    } finally {
      allSpy.mockRestore()
    }
  })

  it('showRefresh prop 声明存在但模板未使用（死 props，仅验证挂载）', () => {
    const wrapper = mountStatus({ pollInterval: 0, showRefresh: false })
    // 模板始终渲染刷新按钮
    expect(wrapper.find('button.stub-btn').exists()).toBe(true)
  })

  it('轮询：pollInterval > 0 时定时拉取快照，卸载后清理', async () => {
    vi.useFakeTimers()
    const wrapper = mountStatus({ pollInterval: 1000 })
    await flushPromises()
    mocks.getMonitorSnapshot.mockClear()
    vi.advanceTimersByTime(3000)
    expect(mocks.getMonitorSnapshot).toHaveBeenCalledTimes(3)
    vi.useRealTimers()
    wrapper.unmount()
  })

  // 2026-09-30 深审修复：onMounted 内 await refresh() 之后才 setInterval，
  // await 期间卸载会创建"永不清理"的定时器（onUnmounted 只清当时已存在的 timer）。
  it('await 期间卸载 → 不再创建轮询定时器（卸载竞态）', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = mountStatus({ pollInterval: 1000 })
      wrapper.unmount() // 在 refresh() 的 await 完成前卸载
      await flushPromises()
      mocks.getMonitorSnapshot.mockClear()
      vi.advanceTimersByTime(5000)
      expect(mocks.getMonitorSnapshot).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('pollInterval=0 时不启动轮询', async () => {
    vi.useFakeTimers()
    const wrapper = mountStatus({ pollInterval: 0 })
    await flushPromises()
    mocks.getMonitorSnapshot.mockClear()
    vi.advanceTimersByTime(5000)
    expect(mocks.getMonitorSnapshot).not.toHaveBeenCalled()
    vi.useRealTimers()
    wrapper.unmount()
  })
})

