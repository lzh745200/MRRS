/**
 * components/system/SelfCheckCard.vue 测试（四指标 100%）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockSelfCheck, mockPushSafe } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockSelfCheck: vi.fn(),
  mockPushSafe: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))
vi.mock('@/api/selfCheck', () => ({ getSelfCheck: mockSelfCheck }))
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

import SelfCheckCard from '@/components/system/SelfCheckCard.vue'

const STUBS = {
  'el-card': { template: '<div class="card"><slot name="header" /><slot /></div>' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-tag': {
    props: ['type'],
    template: '<span class="tag" :data-type="type"><slot /></span>',
  },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

const OK_REPORT = {
  generated_at: '2026-10-23T17:00:00',
  status: 'ok',
  summary: { check_count: 6, error_count: 0, warn_count: 0, issue_count: 0 },
  checks: [
    { name: '组织单位码', level: 'ok', detail: '全部规范', count: 0 },
    { name: '组织层级', level: 'warn', detail: '1 个跨级挂接', count: 1 },
  ],
}

function factory() {
  return mount(SelfCheckCard, { global: { stubs: STUBS } })
}

describe('components/system/SelfCheckCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPushSafe.mockClear()
  })

  it('挂载即执行自检并渲染结论', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()

    expect(mockSelfCheck).toHaveBeenCalled()
    const text = wrapper.text()
    expect(text).toContain('组织单位码')
    expect(text).toContain('组织层级')
    expect(text).toContain('共 6 项')
    expect(text).toContain('2026-10-23 17:00:00')
  })

  it('状态标签：ok → success', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.summaryTag?.type).toBe('success')
    expect(wrapper.vm.summaryTag?.label).toBe('正常')
  })

  it('状态标签：warn → warning / error → danger', async () => {
    mockSelfCheck.mockResolvedValue({ ...OK_REPORT, status: 'warn' })
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.summaryTag?.type).toBe('warning')

    mockSelfCheck.mockResolvedValue({ ...OK_REPORT, status: 'error' })
    await wrapper.vm.runCheck()
    expect(wrapper.vm.summaryTag?.type).toBe('danger')
  })

  it('未知 level 回退为原值 / warning 标签', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.levelLabel('mystery')).toBe('mystery')
    expect(wrapper.vm.levelTagType('mystery')).toBe('warning')
  })

  it('无报告时显示提示文案', async () => {
    mockSelfCheck.mockRejectedValue(new Error('boom'))
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.text()).toContain('点击「重新检查」执行配置一致性体检')
    expect(wrapper.vm.report).toBeNull()
  })

  it('generated_at 缺失时回退为 -，未知状态回退 warning', async () => {
    mockSelfCheck.mockResolvedValue({ ...OK_REPORT, generated_at: '', status: 'mystery' })
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.generatedAt).toBe('-')
    expect(wrapper.vm.summaryTag?.type).toBe('warning')
  })

  it('自检失败提示错误且不写入报告', async () => {
    mockSelfCheck.mockRejectedValue(new Error('network'))
    const wrapper = factory()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('自检失败，请稍后重试')
    expect(wrapper.vm.report).toBeNull()
  })

  it('点击重新检查再次请求', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()
    const before = mockSelfCheck.mock.calls.length
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(mockSelfCheck.mock.calls.length).toBeGreaterThan(before)
  })
})

  it('非正常项给出直达入口并跳转到对应 console tab', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()
    const warn = wrapper.vm.report!.checks[1]
    expect(wrapper.vm.actionLink(warn)).toBe('/system/console/org?tab=organizations')
    // 走真实点击路径（模板内联处理器也要被执行，否则函数覆盖率会缺一角）
    const btn = wrapper.findAll('button').find((b) => b.text().includes('去处理'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/system/console/org?tab=organizations')
  })

  it('正常项不给入口（避免噪音），未知项也不给', async () => {
    mockSelfCheck.mockResolvedValue(OK_REPORT)
    const wrapper = factory()
    await flushPromises()
    const ok = wrapper.vm.report!.checks[0]
    expect(wrapper.vm.actionLink(ok)).toBe('')
    const before = mockPushSafe.mock.calls.length
    wrapper.vm.goFix({ name: '未登记项', level: 'warn', detail: '', count: 1 })
    expect(mockPushSafe.mock.calls.length).toBe(before)
  })

  it('PII 密钥异常项锚到密钥管理页', async () => {
    mockSelfCheck.mockResolvedValue({
      ...OK_REPORT,
      status: 'error',
      checks: [{ name: 'PII 密钥', level: 'error', detail: '指纹为空', count: 1 }],
    })
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.actionLink(wrapper.vm.report!.checks[0])).toBe(
      '/system/console/security?tab=secrets'
    )
  })